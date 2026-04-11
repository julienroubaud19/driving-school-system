from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.notification import (
    Notification, NotificationRateLog, NotificationSubscription, NotificationType,
)


def notify(user_id, type_codename, title, body, link=None):
    ntype = NotificationType.query.filter_by(codename=type_codename).first()
    if not ntype:
        return None

    sub = NotificationSubscription.query.filter_by(
        user_id=user_id, notification_type_id=ntype.id, is_active=True
    ).first()
    if not sub:
        return None

    if sub.digest_mode:
        existing_digest = Notification.query.filter_by(
            user_id=user_id,
            notification_type_id=ntype.id,
            is_read=False,
            is_digest=True,
        ).first()

        if existing_digest:
            count = existing_digest.digest_count + 1
            existing_digest.digest_count = count
            existing_digest.title = f'{ntype.label} ({count} updates)'
            existing_digest.body = f'{body}\n---\n{existing_digest.body}'
            existing_digest.link = link or existing_digest.link
            existing_digest.created_at = datetime.now(timezone.utc)
            db.session.commit()
            return existing_digest

        notif = Notification(
            user_id=user_id,
            notification_type_id=ntype.id,
            title=f'{ntype.label} (1 update)',
            body=body,
            link=link,
            is_digest=True,
            digest_count=1,
        )
        db.session.add(notif)
        rate_log = NotificationRateLog(user_id=user_id)
        db.session.add(rate_log)
        db.session.commit()
        return notif

    rate_limit = current_app.config['NOTIFICATION_RATE_LIMIT']
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_count = NotificationRateLog.query.filter(
        NotificationRateLog.user_id == user_id,
        NotificationRateLog.sent_at >= one_hour_ago,
    ).count()

    if recent_count >= rate_limit:
        return None  # rate limited

    notif = Notification(
        user_id=user_id,
        notification_type_id=ntype.id,
        title=title,
        body=body,
        link=link,
    )
    db.session.add(notif)

    rate_log = NotificationRateLog(user_id=user_id)
    db.session.add(rate_log)

    db.session.commit()
    return notif


def mark_read(notification_id, user_id):
    notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if notif and not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        db.session.commit()
    return notif


def mark_all_read(user_id):
    now = datetime.now(timezone.utc)
    Notification.query.filter_by(user_id=user_id, is_read=False).update({
        'is_read': True, 'read_at': now,
    })
    db.session.commit()


def get_unread_count(user_id):
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()
