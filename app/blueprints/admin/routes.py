from datetime import datetime, timezone

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.blueprints.admin import bp
from app.blueprints.admin.forms import UserForm, LocationForm, RatingDimensionForm
from app.extensions import db
from app.models.user import User, Role
from app.models.location import Location
from app.models.audit import AuditEvent, AnomalyFlag, AppConfig
from app.models.review import RatingDimension
from app.services.rbac import role_required
from app.services.auth_service import validate_password
from app.services.audit_service import log_event, check_anomalies
from app.utils.helpers import is_htmx_request, paginate_query


@bp.route('/users')
@login_required
@role_required('Administrator')
def users():
    query = User.query.order_by(User.username)
    pagination = paginate_query(query)
    return render_template('admin/users.html', users=pagination)


@bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@role_required('Administrator')
def create_user():
    form = UserForm()
    _populate_user_form(form)

    if form.validate_on_submit():
        if not form.password.data:
            flash('Password is required for new users.', 'danger')
            return render_template('admin/user_form.html', form=form, title='New User')

        errors = validate_password(form.password.data)
        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('admin/user_form.html', form=form, title='New User')

        user = User(
            username=form.username.data,
            email=form.email.data,
            role_id=form.role_id.data,
            location_id=form.location_id.data or None,
            is_active=form.is_active.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        log_event('user_created', user_id=current_user.id,
                  resource_type='user', resource_id=user.id)
        flash(f'User {user.username} created.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', form=form, title='New User')


@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('Administrator')
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.users'))

    form = UserForm(obj=user)
    _populate_user_form(form)

    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.role_id = form.role_id.data
        user.location_id = form.location_id.data or None
        user.is_active = form.is_active.data

        if form.password.data:
            errors = validate_password(form.password.data)
            if errors:
                for e in errors:
                    flash(e, 'danger')
                return render_template('admin/user_form.html', form=form, title='Edit User', user=user)
            user.set_password(form.password.data)

        db.session.commit()
        log_event('user_updated', user_id=current_user.id,
                  resource_type='user', resource_id=user.id)
        flash(f'User {user.username} updated.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', form=form, title='Edit User', user=user)


@bp.route('/users/<int:user_id>/force-reset', methods=['POST'])
@login_required
@role_required('Administrator')
def force_reset(user_id):
    user = db.session.get(User, user_id)
    if user:
        user.force_password_reset = True
        db.session.commit()
        log_event('force_password_reset', user_id=current_user.id,
                  resource_type='user', resource_id=user.id)
        flash(f'{user.username} will be required to change password on next login.', 'info')
    return redirect(url_for('admin.users'))


@bp.route('/users/<int:user_id>/unlock', methods=['POST'])
@login_required
@role_required('Administrator')
def unlock_user(user_id):
    user = db.session.get(User, user_id)
    if user:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()
        log_event('user_unlocked', user_id=current_user.id,
                  resource_type='user', resource_id=user.id)
        flash(f'{user.username} account unlocked.', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/locations')
@login_required
@role_required('Administrator')
def locations():
    locs = Location.query.order_by(Location.name).all()
    return render_template('admin/locations.html', locations=locs)


@bp.route('/locations/new', methods=['GET', 'POST'])
@login_required
@role_required('Administrator')
def create_location():
    form = LocationForm()
    if form.validate_on_submit():
        loc = Location(
            name=form.name.data, address=form.address.data,
            phone=form.phone.data, is_active=form.is_active.data,
        )
        db.session.add(loc)
        db.session.commit()
        flash(f'Location "{loc.name}" created.', 'success')
        return redirect(url_for('admin.locations'))
    return render_template('admin/location_form.html', form=form, title='New Location')


@bp.route('/locations/<int:loc_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('Administrator')
def edit_location(loc_id):
    loc = db.session.get(Location, loc_id)
    if not loc:
        flash('Location not found.', 'danger')
        return redirect(url_for('admin.locations'))
    form = LocationForm(obj=loc)
    if form.validate_on_submit():
        form.populate_obj(loc)
        db.session.commit()
        flash(f'Location "{loc.name}" updated.', 'success')
        return redirect(url_for('admin.locations'))
    return render_template('admin/location_form.html', form=form, title='Edit Location', location=loc)


@bp.route('/dimensions')
@login_required
@role_required('Administrator')
def dimensions():
    dims = RatingDimension.query.order_by(RatingDimension.sort_order).all()
    return render_template('admin/dimensions.html', dimensions=dims)


@bp.route('/dimensions/new', methods=['GET', 'POST'])
@login_required
@role_required('Administrator')
def create_dimension():
    form = RatingDimensionForm()
    if form.validate_on_submit():
        dim = RatingDimension(
            name=form.name.data, label=form.label.data,
            sort_order=int(form.sort_order.data or 0),
            is_active=form.is_active.data,
        )
        db.session.add(dim)
        db.session.commit()
        flash(f'Dimension "{dim.label}" created.', 'success')
        return redirect(url_for('admin.dimensions'))
    return render_template('admin/dimension_form.html', form=form, title='New Dimension')


@bp.route('/dimensions/<int:dim_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('Administrator')
def edit_dimension(dim_id):
    dim = db.session.get(RatingDimension, dim_id)
    if not dim:
        flash('Dimension not found.', 'danger')
        return redirect(url_for('admin.dimensions'))
    form = RatingDimensionForm(obj=dim)
    if form.validate_on_submit():
        dim.name = form.name.data
        dim.label = form.label.data
        dim.sort_order = int(form.sort_order.data or 0)
        dim.is_active = form.is_active.data
        db.session.commit()
        flash(f'Dimension "{dim.label}" updated.', 'success')
        return redirect(url_for('admin.dimensions'))
    return render_template('admin/dimension_form.html', form=form, title='Edit Dimension', dimension=dim)


@bp.route('/audit')
@login_required
@role_required('Administrator')
def audit_log():
    check_anomalies()
    query = AuditEvent.query.order_by(AuditEvent.created_at.desc())

    event_type = request.args.get('event_type')
    if event_type:
        query = query.filter_by(event_type=event_type)

    user_id = request.args.get('user_id', type=int)
    if user_id:
        query = query.filter_by(user_id=user_id)

    pagination = paginate_query(query)
    event_types = db.session.query(AuditEvent.event_type).distinct().all()
    users = User.query.order_by(User.username).all()

    if is_htmx_request():
        return render_template('admin/partials/_audit_table.html', events=pagination)

    return render_template('admin/audit_log.html', events=pagination,
                           event_types=[e[0] for e in event_types], users=users)


@bp.route('/anomalies')
@login_required
@role_required('Administrator')
def anomalies():
    check_anomalies()
    flags = AnomalyFlag.query.order_by(AnomalyFlag.created_at.desc()).limit(50).all()
    return render_template('admin/anomalies.html', flags=flags)


@bp.route('/anomalies/<int:flag_id>/ack', methods=['POST'])
@login_required
@role_required('Administrator')
def acknowledge_anomaly(flag_id):
    flag = db.session.get(AnomalyFlag, flag_id)
    if flag:
        flag.acknowledged = True
        db.session.commit()
    return redirect(url_for('admin.anomalies'))


@bp.route('/config', methods=['GET', 'POST'])
@login_required
@role_required('Administrator')
def config():
    if request.method == 'POST':
        key = request.form.get('key', '').strip()
        value = request.form.get('value', '').strip()
        if key:
            cfg = AppConfig.query.filter_by(key=key).first()
            if cfg:
                cfg.set_value(value)
                cfg.updated_by = current_user.id
            else:
                cfg = AppConfig(key=key, updated_by=current_user.id)
                cfg.set_value(value)
                db.session.add(cfg)
            db.session.commit()
            flash(f'Config "{key}" saved.', 'success')
        return redirect(url_for('admin.config'))

    configs = AppConfig.query.order_by(AppConfig.key).all()
    return render_template('admin/config.html', configs=configs)


def _populate_user_form(form):
    roles = Role.query.order_by(Role.name).all()
    form.role_id.choices = [(r.id, r.name) for r in roles]

    locations = Location.query.filter_by(is_active=True).order_by(Location.name).all()
    form.location_id.choices = [(0, '-- None --')] + [(l.id, l.name) for l in locations]
