import hashlib
import json
from datetime import datetime, timezone

from app.extensions import db


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # income / expense
    amount = db.Column(db.Float, nullable=False)
    payee = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    payment_method = db.Column(db.String(50))  # cash/card/transfer/check
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    handler_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='active')  # draft/active/closed/voided/reversed
    receipt_path = db.Column(db.String(500))
    void_reason = db.Column(db.Text)
    void_approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reversal_of_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    closeout_id = db.Column(db.Integer, db.ForeignKey('monthly_closeouts.id'), nullable=True)
    fingerprint_hash = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    location = db.relationship('Location', backref='transactions')
    handler = db.relationship('User', foreign_keys=[handler_id], backref='handled_transactions')
    void_approver = db.relationship('User', foreign_keys=[void_approved_by])
    reversal_of = db.relationship('Transaction', remote_side=[id], backref='reversals')
    closeout = db.relationship('MonthlyCloseout', backref='transactions')
    versions = db.relationship('TransactionVersion', backref='transaction',
                               order_by='TransactionVersion.version_number')

    def compute_fingerprint(self):
        normalized = '|'.join([
            (self.payee or '').strip().lower(),
            f'{self.amount:.2f}',
            self.created_at.strftime('%Y-%m-%d') if self.created_at else '',
            str(self.location_id or ''),
            (self.payment_method or '').strip().lower(),
        ])
        self.fingerprint_hash = hashlib.sha256(normalized.encode()).hexdigest()
        return self.fingerprint_hash

    @property
    def is_editable(self):
        return self.status in ('draft', 'active')

    def __repr__(self):
        return f'<Transaction {self.id} {self.type} {self.amount}>'


class TransactionVersion(db.Model):
    __tablename__ = 'transaction_versions'

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    field_changes = db.Column(db.Text)  # JSON
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    changer = db.relationship('User')

    def get_changes(self):
        return json.loads(self.field_changes) if self.field_changes else {}


class MonthlyCloseout(db.Model):
    __tablename__ = 'monthly_closeouts'

    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    closed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    closed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='closed')

    location = db.relationship('Location', backref='closeouts')
    closer = db.relationship('User')

    __table_args__ = (
        db.UniqueConstraint('location_id', 'month', 'year', name='uq_closeout_location_month_year'),
    )


class BulkImportBatch(db.Model):
    __tablename__ = 'bulk_import_batches'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    row_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    duplicate_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='pending')  # pending/previewing/imported/failed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    uploader = db.relationship('User')
    rows = db.relationship('BulkImportRow', backref='batch', lazy='dynamic')


class BulkImportRow(db.Model):
    __tablename__ = 'bulk_import_rows'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('bulk_import_batches.id'), nullable=False)
    row_number = db.Column(db.Integer, nullable=False)
    raw_data = db.Column(db.Text)  # JSON
    status = db.Column(db.String(20), default='pending')  # pending/imported/error/duplicate
    error_message = db.Column(db.Text)
    matched_transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    resolution = db.Column(db.String(20))  # merge/keep/skip

    matched_transaction = db.relationship('Transaction')

    def get_data(self):
        return json.loads(self.raw_data) if self.raw_data else {}
