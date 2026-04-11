import json

from flask import render_template, redirect, url_for, flash, request, send_from_directory
from flask_login import login_required, current_user

from app.blueprints.financial import bp
from app.blueprints.financial.forms import TransactionForm, VoidForm, CloseoutForm, ImportForm
from app.extensions import db
from app.models.financial import Transaction, TransactionVersion, MonthlyCloseout, BulkImportBatch, BulkImportRow
from app.models.location import Location
from app.services.rbac import permission_required
from app.services.financial_service import (
    compute_fingerprint, find_duplicates, record_version,
    void_transaction, create_reversal, close_month,
)
from app.services.import_service import parse_csv, parse_excel, preview_import, execute_import
from app.services.audit_service import log_event
from app.utils.file_storage import save_file
from app.utils.helpers import is_htmx_request, paginate_query


@bp.route('/')
@login_required
@permission_required('financial.view')
def list_transactions():
    query = Transaction.query

    if current_user.role.name not in ('Administrator', 'Auditor') and current_user.location_id:
        query = query.filter_by(location_id=current_user.location_id)

    location_id = request.args.get('location_id', type=int)
    if location_id:
        query = query.filter_by(location_id=location_id)

    txn_type = request.args.get('type')
    if txn_type:
        query = query.filter_by(type=txn_type)

    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)

    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            db.or_(
                Transaction.payee.ilike(f'%{search}%'),
                Transaction.description.ilike(f'%{search}%'),
            )
        )

    query = query.order_by(Transaction.created_at.desc())
    pagination = paginate_query(query)
    locations = Location.query.filter_by(is_active=True).all()

    if is_htmx_request():
        return render_template('financial/partials/_transaction_table.html',
                               transactions=pagination, locations=locations)

    return render_template('financial/list.html',
                           transactions=pagination, locations=locations)


@bp.route('/new', methods=['GET', 'POST'])
@login_required
@permission_required('financial.create')
def create():
    form = TransactionForm()
    _populate_location_choices(form)

    if form.validate_on_submit():
        receipt_path = None
        if form.receipt.data:
            receipt_path = save_file(form.receipt.data, 'receipts')

        txn = Transaction(
            type=form.type.data,
            amount=form.amount.data,
            payee=form.payee.data,
            description=form.description.data,
            category=form.category.data,
            payment_method=form.payment_method.data,
            location_id=form.location_id.data,
            handler_id=current_user.id,
            receipt_path=receipt_path,
        )
        txn.compute_fingerprint()

        dupes = find_duplicates(txn.fingerprint_hash)
        if dupes:
            flash(f'Warning: {len(dupes)} potential duplicate(s) found. Transaction saved as draft.', 'warning')
            txn.status = 'draft'
        else:
            txn.status = 'active'

        db.session.add(txn)
        db.session.commit()

        log_event('transaction_created', user_id=current_user.id,
                  resource_type='transaction', resource_id=txn.id)
        flash('Transaction created.', 'success')
        return redirect(url_for('financial.detail', transaction_id=txn.id))

    return render_template('financial/form.html', form=form, title='New Transaction')


@bp.route('/<int:transaction_id>')
@login_required
@permission_required('financial.view')
def detail(transaction_id):
    txn = db.session.get(Transaction, transaction_id)
    if not txn:
        flash('Transaction not found.', 'danger')
        return redirect(url_for('financial.list_transactions'))

    if current_user.role.name not in ('Administrator', 'Auditor') and current_user.location_id:
        if txn.location_id != current_user.location_id:
            from flask import abort
            abort(403)

    versions = TransactionVersion.query.filter_by(transaction_id=txn.id)\
        .order_by(TransactionVersion.version_number).all()
    return render_template('financial/detail.html', txn=txn, versions=versions)


@bp.route('/<int:transaction_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('financial.edit')
def edit(transaction_id):
    txn = db.session.get(Transaction, transaction_id)
    if not txn:
        flash('Transaction not found.', 'danger')
        return redirect(url_for('financial.list_transactions'))

    if current_user.role.name not in ('Administrator', 'Auditor') and current_user.location_id:
        if txn.location_id != current_user.location_id:
            from flask import abort
            abort(403)

    if not txn.is_editable:
        flash('This transaction cannot be edited.', 'warning')
        return redirect(url_for('financial.detail', transaction_id=txn.id))

    form = TransactionForm(obj=txn)
    _populate_location_choices(form)

    if form.validate_on_submit():
        changes = {}
        for field in ['type', 'amount', 'payee', 'description', 'category', 'payment_method', 'location_id']:
            old_val = getattr(txn, field)
            new_val = getattr(form, field).data
            if str(old_val) != str(new_val):
                changes[field] = [str(old_val), str(new_val)]

        form.populate_obj(txn)
        if form.receipt.data:
            txn.receipt_path = save_file(form.receipt.data, 'receipts')
        txn.compute_fingerprint()

        if changes:
            record_version(txn, current_user.id, changes)

        db.session.commit()
        log_event('transaction_updated', user_id=current_user.id,
                  resource_type='transaction', resource_id=txn.id,
                  detail={'changes': changes})
        flash('Transaction updated.', 'success')
        return redirect(url_for('financial.detail', transaction_id=txn.id))

    return render_template('financial/form.html', form=form, title='Edit Transaction', txn=txn)


@bp.route('/<int:transaction_id>/void', methods=['GET', 'POST'])
@login_required
@permission_required('financial.void')
def void(transaction_id):
    form = VoidForm()
    _populate_supervisor_choices(form)
    txn = db.session.get(Transaction, transaction_id)
    if not txn:
        flash('Transaction not found.', 'danger')
        return redirect(url_for('financial.list_transactions'))

    if form.validate_on_submit():
        result, error = void_transaction(txn.id, form.reason.data, form.approved_by.data, current_user.id)
        if error:
            flash(error, 'danger')
        else:
            flash('Transaction voided.', 'success')
        return redirect(url_for('financial.detail', transaction_id=txn.id))

    return render_template('financial/void.html', form=form, txn=txn)


@bp.route('/<int:transaction_id>/reverse', methods=['POST'])
@login_required
@permission_required('financial.void')
def reverse(transaction_id):
    approved_by_id = request.form.get('approved_by', type=int)
    if not approved_by_id:
        flash('Supervisor approval is required for reversals.', 'danger')
        return redirect(url_for('financial.detail', transaction_id=transaction_id))
    reversal, error = create_reversal(transaction_id, current_user.id, approved_by_id)
    if error:
        flash(error, 'danger')
    else:
        flash(f'Reversal transaction #{reversal.id} created.', 'success')
    return redirect(url_for('financial.detail', transaction_id=transaction_id))


@bp.route('/closeout', methods=['GET', 'POST'])
@login_required
@permission_required('financial.closeout')
def closeout():
    form = CloseoutForm()
    locations = Location.query.filter_by(is_active=True).all()
    form.location_id.choices = [(l.id, l.name) for l in locations]
    closeouts = MonthlyCloseout.query.order_by(MonthlyCloseout.closed_at.desc()).limit(20).all()

    if form.validate_on_submit():
        result, error = close_month(
            form.location_id.data, form.month.data, form.year.data, current_user.id
        )
        if error:
            flash(error, 'danger')
        else:
            flash(f'Month {form.month.data}/{form.year.data} closed successfully.', 'success')
        return redirect(url_for('financial.closeout'))

    return render_template('financial/closeout.html', form=form, closeouts=closeouts)


@bp.route('/import', methods=['GET', 'POST'])
@login_required
@permission_required('financial.import')
def bulk_import():
    form = ImportForm()

    if form.validate_on_submit():
        file = form.file.data
        filename = file.filename.lower()

        try:
            if filename.endswith('.csv'):
                content = file.read().decode('utf-8')
                rows, columns = parse_csv(content, filename)
            elif filename.endswith(('.xlsx', '.xls')):
                rows, columns = parse_excel(file)
            else:
                flash('Unsupported file format. Use CSV or Excel.', 'danger')
                return render_template('financial/import.html', form=form)

            batch = preview_import(rows, columns, current_user.id, filename)
            log_event('bulk_import_uploaded', user_id=current_user.id,
                      resource_type='import_batch', resource_id=batch.id)
            return redirect(url_for('financial.import_preview', batch_id=batch.id))

        except Exception as e:
            flash(f'Error parsing file: {str(e)}', 'danger')

    return render_template('financial/import.html', form=form)


@bp.route('/import/<int:batch_id>/preview')
@login_required
@permission_required('financial.import')
def import_preview(batch_id):
    batch = db.session.get(BulkImportBatch, batch_id)
    if not batch:
        flash('Batch not found.', 'danger')
        return redirect(url_for('financial.bulk_import'))

    rows = batch.rows.order_by(BulkImportRow.row_number).all()
    return render_template('financial/import_preview.html', batch=batch, rows=rows)


@bp.route('/import/<int:batch_id>/resolve/<int:row_id>', methods=['POST'])
@login_required
@permission_required('financial.import')
def resolve_duplicate(batch_id, row_id):
    row = db.session.get(BulkImportRow, row_id)
    if row and row.batch_id == batch_id:
        row.resolution = request.form.get('resolution', 'skip')
        db.session.commit()

    if is_htmx_request():
        batch = db.session.get(BulkImportBatch, batch_id)
        rows = batch.rows.order_by(BulkImportRow.row_number).all()
        return render_template('financial/partials/_import_rows.html', batch=batch, rows=rows)

    return redirect(url_for('financial.import_preview', batch_id=batch_id))


@bp.route('/import/<int:batch_id>/execute', methods=['POST'])
@login_required
@permission_required('financial.import')
def execute_batch_import(batch_id):
    batch, msg = execute_import(batch_id, current_user.id)
    if batch:
        log_event('bulk_import_executed', user_id=current_user.id,
                  resource_type='import_batch', resource_id=batch.id)
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('financial.list_transactions'))


def _populate_location_choices(form):
    locations = Location.query.filter_by(is_active=True).all()
    form.location_id.choices = [(l.id, l.name) for l in locations]


def _populate_supervisor_choices(form):
    from app.models.user import User, Role, Permission, role_permissions
    void_perm = Permission.query.filter_by(codename='financial.void').first()
    if void_perm:
        supervisor_role_ids = db.session.query(role_permissions.c.role_id).filter(
            role_permissions.c.permission_id == void_perm.id
        ).subquery()
        supervisors = User.query.filter(
            User.is_active == True,
            User.id != current_user.id,
            User.role_id.in_(db.session.query(supervisor_role_ids)),
        ).order_by(User.username).all()
    else:
        supervisors = []
    form.approved_by.choices = [(0, '-- Select Supervisor --')] + [
        (u.id, u.username) for u in supervisors
    ]
