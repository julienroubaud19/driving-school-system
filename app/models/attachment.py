import hashlib
from datetime import datetime, timezone

from app.extensions import db


class Attachment(db.Model):
    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_hash = db.Column(db.String(64), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    content_type = db.Column(db.String(100))  # receipt/review_image/evidence
    resource_type = db.Column(db.String(100))  # transaction/review/dispute
    resource_id = db.Column(db.Integer)
    version = db.Column(db.Integer, default=1)
    parent_id = db.Column(db.Integer, db.ForeignKey('attachments.id'), nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_duplicate = db.Column(db.Boolean, default=False)
    duplicate_of_id = db.Column(db.Integer, db.ForeignKey('attachments.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    uploader = db.relationship('User')
    parent = db.relationship('Attachment', remote_side=[id], foreign_keys=[parent_id],
                             backref='versions')
    duplicate_of = db.relationship('Attachment', remote_side=[id], foreign_keys=[duplicate_of_id])

    @staticmethod
    def compute_hash(file_data):
        return hashlib.sha256(file_data).hexdigest()

    @classmethod
    def find_by_hash(cls, file_hash, resource_type=None):
        query = cls.query.filter_by(file_hash=file_hash)
        if resource_type:
            query = query.filter_by(resource_type=resource_type)
        return query.first()
