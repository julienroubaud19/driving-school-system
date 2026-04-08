from datetime import datetime, timezone

from app.extensions import db


class ModerationQueue(db.Model):
    __tablename__ = 'moderation_queue'

    id = db.Column(db.Integer, primary_key=True)
    content_type = db.Column(db.String(50), nullable=False)  # review / note
    content_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(100), nullable=False)  # auto_word_match/rate_limit/manual_report/blacklist
    flagged_words = db.Column(db.Text)
    status = db.Column(db.String(20), default='held')  # held/approved/rejected
    handled_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    handled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    handler = db.relationship('User', backref='moderation_handled')
    logs = db.relationship('ModerationLog', backref='queue_item', cascade='all, delete-orphan')


class ModerationLog(db.Model):
    __tablename__ = 'moderation_logs'

    id = db.Column(db.Integer, primary_key=True)
    queue_id = db.Column(db.Integer, db.ForeignKey('moderation_queue.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    performer = db.relationship('User')


class SensitiveWord(db.Model):
    __tablename__ = 'sensitive_words'

    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class UserBlacklist(db.Model):
    __tablename__ = 'user_blacklist'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.Text)
    blacklisted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', foreign_keys=[user_id], backref='blacklist_entries')
    admin = db.relationship('User', foreign_keys=[blacklisted_by])
