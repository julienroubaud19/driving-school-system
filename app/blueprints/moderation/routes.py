from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.blueprints.moderation import bp
from app.extensions import db
from app.models.moderation import ModerationQueue, ModerationLog, SensitiveWord, UserBlacklist
from app.models.review import Review
from app.models.user import User
from app.services.rbac import permission_required
from app.services.moderation_service import approve_content, reject_content
from app.services.audit_service import log_event
from app.utils.helpers import is_htmx_request, paginate_query


@bp.route('/')
@login_required
@permission_required('review.moderate')
def queue():
    status = request.args.get('status', 'held')
    query = ModerationQueue.query.filter_by(status=status)\
        .order_by(ModerationQueue.created_at.desc())
    pagination = paginate_query(query)

    if is_htmx_request():
        return render_template('moderation/partials/_queue_table.html', items=pagination)

    return render_template('moderation/queue.html', items=pagination, current_status=status)


@bp.route('/<int:item_id>/approve', methods=['POST'])
@login_required
@permission_required('review.moderate')
def approve(item_id):
    notes = request.form.get('notes', '')
    approve_content(item_id, current_user.id, notes)
    log_event('moderation_approved', user_id=current_user.id,
              resource_type='moderation', resource_id=item_id)
    flash('Content approved.', 'success')

    if is_htmx_request():
        return _render_queue_partial()
    return redirect(url_for('moderation.queue'))


@bp.route('/<int:item_id>/reject', methods=['POST'])
@login_required
@permission_required('review.moderate')
def reject(item_id):
    notes = request.form.get('notes', '')
    reject_content(item_id, current_user.id, notes)
    log_event('moderation_rejected', user_id=current_user.id,
              resource_type='moderation', resource_id=item_id)
    flash('Content rejected.', 'danger')

    if is_htmx_request():
        return _render_queue_partial()
    return redirect(url_for('moderation.queue'))


@bp.route('/<int:item_id>/detail')
@login_required
@permission_required('review.moderate')
def detail(item_id):
    item = db.session.get(ModerationQueue, item_id)
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('moderation.queue'))

    content_obj = None
    if item.content_type == 'review':
        content_obj = db.session.get(Review, item.content_id)

    logs = ModerationLog.query.filter_by(queue_id=item.id)\
        .order_by(ModerationLog.created_at).all()

    return render_template('moderation/detail.html', item=item,
                           content_obj=content_obj, logs=logs)


@bp.route('/words')
@login_required
@permission_required('review.moderate')
def word_list():
    words = SensitiveWord.query.order_by(SensitiveWord.word).all()
    return render_template('moderation/words.html', words=words)


@bp.route('/words/add', methods=['POST'])
@login_required
@permission_required('review.moderate')
def add_word():
    word = request.form.get('word', '').strip()
    category = request.form.get('category', '').strip()
    if word:
        sw = SensitiveWord(word=word, category=category)
        db.session.add(sw)
        db.session.commit()
        flash(f'Word "{word}" added.', 'success')
    return redirect(url_for('moderation.word_list'))


@bp.route('/words/<int:word_id>/toggle', methods=['POST'])
@login_required
@permission_required('review.moderate')
def toggle_word(word_id):
    sw = db.session.get(SensitiveWord, word_id)
    if sw:
        sw.is_active = not sw.is_active
        db.session.commit()
    return redirect(url_for('moderation.word_list'))


@bp.route('/blacklist')
@login_required
@permission_required('review.moderate')
def blacklist():
    entries = UserBlacklist.query.order_by(UserBlacklist.created_at.desc()).all()
    return render_template('moderation/blacklist.html', entries=entries)


@bp.route('/blacklist/add', methods=['POST'])
@login_required
@permission_required('review.moderate')
def add_blacklist():
    user_id = request.form.get('user_id', type=int)
    reason = request.form.get('reason', '')
    if user_id:
        entry = UserBlacklist(
            user_id=user_id, reason=reason,
            blacklisted_by=current_user.id,
        )
        db.session.add(entry)
        db.session.commit()
        flash('User blacklisted.', 'success')
    return redirect(url_for('moderation.blacklist'))


def _render_queue_partial():
    query = ModerationQueue.query.filter_by(status='held')\
        .order_by(ModerationQueue.created_at.desc())
    pagination = paginate_query(query)
    return render_template('moderation/partials/_queue_table.html', items=pagination)
