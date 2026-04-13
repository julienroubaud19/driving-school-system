"""Tests for anomaly detection and audit event logging."""

from datetime import datetime, timedelta, timezone

from tests.conftest import login
from app.models.audit import AuditEvent, AnomalyFlag
from app.services.audit_service import log_event, check_anomalies


def test_log_event_creates_audit_entry(seed_data, db, app):
    event = log_event('test_event', user_id=seed_data['admin'].id,
                      ip_address='127.0.0.1', resource_type='test',
                      resource_id=1, detail={'key': 'value'})
    assert event is not None
    assert event.event_type == 'test_event'
    detail = event.get_detail()
    assert detail['key'] == 'value'


def test_anomaly_login_spike(seed_data, db, app):
    """10+ locked accounts in 1 hour should trigger failed_login_spike anomaly."""
    for i in range(10):
        log_event('login_locked', user_id=seed_data['admin'].id, ip_address='127.0.0.1',
                  detail={'attempts': 6})

    check_anomalies()
    flag = AnomalyFlag.query.filter_by(flag_type='failed_login_spike').first()
    assert flag is not None
    assert flag.metric_value >= 10
    assert flag.threshold_value == 10


def test_anomaly_not_triggered_below_threshold(seed_data, db, app):
    """Less than 10 locked accounts should not trigger anomaly."""
    for i in range(5):
        log_event('login_locked', user_id=seed_data['admin'].id, ip_address='127.0.0.1',
                  detail={'attempts': 6})

    check_anomalies()
    flag = AnomalyFlag.query.filter_by(flag_type='failed_login_spike').first()
    assert flag is None


def test_anomaly_high_dispute_rate(seed_data, db, app):
    """5+ disputes in 1 hour should trigger high_dispute_rate anomaly."""
    from app.models.review import Review, Dispute
    for i in range(5):
        review = Review(content=f'Test review {i}', location_id=seed_data['location'].id,
                        created_by=seed_data['admin'].id, status='approved')
        db.session.add(review)
        db.session.flush()
        dispute = Dispute(review_id=review.id, initiated_by=seed_data['admin'].id,
                          statement=f'Dispute {i}', status='open')
        db.session.add(dispute)
    db.session.commit()

    check_anomalies()
    flag = AnomalyFlag.query.filter_by(flag_type='high_dispute_rate').first()
    assert flag is not None
    assert flag.metric_value >= 5


def test_anomaly_not_duplicated(seed_data, db, app):
    """Running check_anomalies twice should not create duplicate flags."""
    for i in range(10):
        log_event('login_locked', user_id=seed_data['admin'].id, ip_address='127.0.0.1')

    check_anomalies()
    check_anomalies()
    count = AnomalyFlag.query.filter_by(flag_type='failed_login_spike').count()
    assert count == 1
