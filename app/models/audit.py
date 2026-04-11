import json
from datetime import datetime, timezone

from app.extensions import db


class AuditEvent(db.Model):
    __tablename__ = 'audit_events'

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ip_address = db.Column(db.String(50))
    resource_type = db.Column(db.String(100))
    resource_id = db.Column(db.Integer)
    detail = db.Column(db.Text)  # JSON
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='audit_events')

    def get_detail(self):
        return json.loads(self.detail) if self.detail else {}


class AnomalyFlag(db.Model):
    __tablename__ = 'anomaly_flags'

    id = db.Column(db.Integer, primary_key=True)
    flag_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    metric_value = db.Column(db.Float)
    threshold_value = db.Column(db.Float)
    acknowledged = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class ReportSchedule(db.Model):
    __tablename__ = 'report_schedules'

    id = db.Column(db.Integer, primary_key=True)
    report_name = db.Column(db.String(100), nullable=False)
    frequency = db.Column(db.String(20), nullable=False)  # daily/weekly/monthly
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    format = db.Column(db.String(10), default='csv')  # csv/json
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_run_at = db.Column(db.DateTime, nullable=True)
    next_run_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    creator = db.relationship('User')
    location = db.relationship('Location')
    executions = db.relationship('ReportExecution', backref='schedule',
                                 order_by='ReportExecution.executed_at.desc()')


class ReportExecution(db.Model):
    __tablename__ = 'report_executions'

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('report_schedules.id'), nullable=False)
    file_path = db.Column(db.String(500))
    status = db.Column(db.String(20), default='success')  # success/failed
    error_message = db.Column(db.Text, nullable=True)
    executed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class AppConfig(db.Model):
    __tablename__ = 'app_config'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)  # JSON
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def get_value(self):
        return json.loads(self.value) if self.value else None

    def set_value(self, val):
        self.value = json.dumps(val)
