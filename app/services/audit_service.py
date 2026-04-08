import json
from datetime import datetime, timedelta, timezone

from app.extensions import db


def log_event(event_type, user_id=None, ip_address=None,
              resource_type=None, resource_id=None, detail=None):
    from app.models.audit import AuditEvent
    event = AuditEvent(
        event_type=event_type,
        user_id=user_id,
        ip_address=ip_address,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=json.dumps(detail) if detail else None,
    )
    db.session.add(event)
    db.session.commit()
    return event


def check_anomalies():
    from app.models.audit import AuditEvent, AnomalyFlag
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    failed_logins = AuditEvent.query.filter(
        AuditEvent.event_type == 'login_locked',
        AuditEvent.created_at >= one_hour_ago,
    ).count()

    if failed_logins >= 10:
        existing = AnomalyFlag.query.filter(
            AnomalyFlag.flag_type == 'failed_login_spike',
            AnomalyFlag.created_at >= one_hour_ago,
        ).first()
        if not existing:
            flag = AnomalyFlag(
                flag_type='failed_login_spike',
                description=f'{failed_logins} locked accounts in the last hour',
                metric_value=failed_logins,
                threshold_value=10,
            )
            db.session.add(flag)
            db.session.commit()

    from app.models.review import Dispute
    open_disputes = Dispute.query.filter(
        Dispute.created_at >= one_hour_ago,
    ).count()
    if open_disputes >= 5:
        existing = AnomalyFlag.query.filter(
            AnomalyFlag.flag_type == 'high_dispute_rate',
            AnomalyFlag.created_at >= one_hour_ago,
        ).first()
        if not existing:
            flag = AnomalyFlag(
                flag_type='high_dispute_rate',
                description=f'{open_disputes} disputes opened in the last hour',
                metric_value=open_disputes,
                threshold_value=5,
            )
            db.session.add(flag)
            db.session.commit()
