from tests.conftest import login
from app.models.notification import (
    Notification, NotificationSubscription, NotificationType, NotificationRateLog,
)
from app.services.notification_service import notify


def test_notification_center(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/notifications/')
    assert resp.status_code == 200


def test_notification_delivery_with_subscription(client, seed_data, db, app):
    user = seed_data['admin']
    ntype = NotificationType.query.filter_by(codename='registration_approved').first()
    sub = NotificationSubscription(
        user_id=user.id, notification_type_id=ntype.id, is_active=True
    )
    db.session.add(sub)
    db.session.commit()

    notif = notify(user.id, 'registration_approved', 'Test Title', 'Test Body')
    assert notif is not None
    assert notif.title == 'Test Title'


def test_notification_blocked_without_subscription(client, seed_data, app):
    user = seed_data['admin']
    notif = notify(user.id, 'registration_approved', 'Blocked', 'Body')
    assert notif is None


def test_mark_notification_read(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    n = Notification(user_id=seed_data['admin'].id, title='Read me', body='body')
    db.session.add(n)
    db.session.commit()

    resp = client.post(f'/notifications/{n.id}/read', follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(n)
    assert n.is_read is True


def test_mark_all_read(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    for i in range(3):
        db.session.add(Notification(user_id=seed_data['admin'].id, title=f'N{i}', body='b'))
    db.session.commit()

    resp = client.post('/notifications/read-all', follow_redirects=True)
    assert resp.status_code == 200
    unread = Notification.query.filter_by(user_id=seed_data['admin'].id, is_read=False).count()
    assert unread == 0


def test_notification_count_endpoint(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    db.session.add(Notification(user_id=seed_data['admin'].id, title='Unread', body='b'))
    db.session.commit()

    resp = client.get('/notifications/count')
    assert resp.status_code == 200


def test_subscriptions_page(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/notifications/subscriptions')
    assert resp.status_code == 200


def test_notification_rate_limit(seed_data, db, app):
    """Notifications should be rate-limited to 5 per user per hour."""
    user = seed_data['admin']
    ntype = NotificationType.query.filter_by(codename='registration_approved').first()
    sub = NotificationSubscription(
        user_id=user.id, notification_type_id=ntype.id, is_active=True
    )
    db.session.add(sub)
    db.session.commit()

    # Send 5 notifications (all should succeed)
    for i in range(5):
        result = notify(user.id, 'registration_approved', f'Title {i}', f'Body {i}')
        assert result is not None

    # 6th notification should be rate limited
    result = notify(user.id, 'registration_approved', 'Over limit', 'Body')
    assert result is None

    # Verify rate log entries
    count = NotificationRateLog.query.filter_by(user_id=user.id).count()
    assert count == 5
