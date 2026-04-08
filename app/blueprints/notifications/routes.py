from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from app.blueprints.notifications import bp
from app.extensions import db
from app.models.notification import Notification, NotificationType, NotificationSubscription
from app.services.notification_service import mark_read, mark_all_read, get_unread_count
from app.utils.helpers import is_htmx_request, paginate_query


@bp.route('/')
@login_required
def center():
    query = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())

    filter_read = request.args.get('read')
    if filter_read == '0':
        query = query.filter_by(is_read=False)
    elif filter_read == '1':
        query = query.filter_by(is_read=True)

    pagination = paginate_query(query)

    if is_htmx_request():
        return render_template('notifications/partials/_notification_list.html',
                               notifications=pagination)

    return render_template('notifications/center.html', notifications=pagination)


@bp.route('/<int:notif_id>/read', methods=['POST'])
@login_required
def read(notif_id):
    mark_read(notif_id, current_user.id)
    if is_htmx_request():
        notif = db.session.get(Notification, notif_id)
        return render_template('notifications/partials/_notification_item.html', n=notif)
    return redirect(url_for('notifications.center'))


@bp.route('/read-all', methods=['POST'])
@login_required
def read_all():
    mark_all_read(current_user.id)
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notifications.center'))


@bp.route('/count')
@login_required
def count():
    c = get_unread_count(current_user.id)
    if is_htmx_request():
        return f'<span class="badge bg-danger rounded-pill">{c}</span>' if c else ''
    return jsonify(count=c)


@bp.route('/subscriptions', methods=['GET', 'POST'])
@login_required
def subscriptions():
    if request.method == 'POST':
        all_types = NotificationType.query.all()
        for nt in all_types:
            sub = NotificationSubscription.query.filter_by(
                user_id=current_user.id, notification_type_id=nt.id
            ).first()
            is_active = request.form.get(f'sub_{nt.id}') == 'on'
            digest = request.form.get(f'digest_{nt.id}') == 'on'
            if sub:
                sub.is_active = is_active
                sub.digest_mode = digest
            else:
                sub = NotificationSubscription(
                    user_id=current_user.id,
                    notification_type_id=nt.id,
                    is_active=is_active,
                    digest_mode=digest,
                )
                db.session.add(sub)
        db.session.commit()
        flash('Notification preferences saved.', 'success')
        return redirect(url_for('notifications.subscriptions'))

    types = NotificationType.query.all()
    subs = {s.notification_type_id: s for s in
            NotificationSubscription.query.filter_by(user_id=current_user.id).all()}
    return render_template('notifications/subscriptions.html', types=types, subs=subs)
