from datetime import datetime, timezone

from app.extensions import db


class NotificationType(db.Model):
    __tablename__ = 'notification_types'

    id = db.Column(db.Integer, primary_key=True)
    codename = db.Column(db.String(100), unique=True, nullable=False)
    label = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)


class NotificationSubscription(db.Model):
    __tablename__ = 'notification_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notification_type_id = db.Column(db.Integer, db.ForeignKey('notification_types.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    digest_mode = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='notification_subscriptions')
    notification_type = db.relationship('NotificationType')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'notification_type_id', name='uq_user_notif_type'),
    )


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notification_type_id = db.Column(db.Integer, db.ForeignKey('notification_types.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)
    link = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False)
    is_digest = db.Column(db.Boolean, default=False)
    digest_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    read_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref='notifications')
    notification_type = db.relationship('NotificationType')


class NotificationRateLog(db.Model):
    __tablename__ = 'notification_rate_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
