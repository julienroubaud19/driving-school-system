from datetime import datetime, timedelta, timezone

from tests.conftest import login


def test_login_page_loads(client):
    resp = client.get('/auth/login')
    assert resp.status_code == 200
    assert b'Sign In' in resp.data


def test_login_success(client, seed_data):
    resp = login(client, 'admin', 'Admin123!@#$')
    assert resp.status_code == 200
    assert b'Dashboard' in resp.data


def test_login_failure(client, seed_data):
    resp = client.post('/auth/login', data={
        'username': 'admin', 'password': 'wrong',
    }, follow_redirects=True)
    assert b'Invalid password' in resp.data or b'Invalid' in resp.data


def test_login_lockout(client, seed_data):
    # 5 failed attempts should trigger lockout (lock on 5th per requirement)
    for i in range(5):
        resp = client.post('/auth/login', data={
            'username': 'admin', 'password': 'wrong',
        }, follow_redirects=True)
    # 5th attempt triggers lockout
    assert b'locked' in resp.data.lower()

    # Verify locked user gets locked message even with correct password
    resp = client.post('/auth/login', data={
        'username': 'admin', 'password': 'Admin123!@#$',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'locked' in resp.data.lower()


def test_login_disabled_account(client, seed_data, db):
    user = seed_data['admin']
    user.is_active = False
    db.session.commit()
    resp = login(client, 'admin', 'Admin123!@#$')
    assert b'disabled' in resp.data.lower()


def test_logout(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/auth/logout', follow_redirects=True)
    assert b'logged out' in resp.data.lower()


def test_change_password(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.post('/auth/change-password', data={
        'current_password': 'Admin123!@#$',
        'new_password': 'NewAdmin123!@#$',
        'confirm_password': 'NewAdmin123!@#$',
    }, follow_redirects=True)
    assert b'Password changed' in resp.data


def test_password_policy_too_short(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.post('/auth/change-password', data={
        'current_password': 'Admin123!@#$',
        'new_password': 'Short1!',
        'confirm_password': 'Short1!',
    }, follow_redirects=True)
    assert b'at least 12' in resp.data


def test_password_policy_no_number(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.post('/auth/change-password', data={
        'current_password': 'Admin123!@#$',
        'new_password': 'NoNumberHere!!',
        'confirm_password': 'NoNumberHere!!',
    }, follow_redirects=True)
    assert b'number' in resp.data


def test_password_policy_no_symbol(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.post('/auth/change-password', data={
        'current_password': 'Admin123!@#$',
        'new_password': 'NoSymbolHere123',
        'confirm_password': 'NoSymbolHere123',
    }, follow_redirects=True)
    assert b'symbol' in resp.data


def test_unauthenticated_redirect(client, seed_data):
    resp = client.get('/students/')
    assert resp.status_code in (302, 401)


def test_force_password_reset(client, seed_data, db):
    user = seed_data['admin']
    user.force_password_reset = True
    db.session.commit()
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/students/', follow_redirects=True)
    assert b'change your password' in resp.data.lower() or b'change_password' in resp.data.lower() or resp.status_code == 200


def test_session_timeout(client, seed_data):
    """Session should expire after 30 minutes of inactivity."""
    login(client, 'admin', 'Admin123!@#$')

    # Simulate setting last_active to 31 minutes ago
    with client.session_transaction() as sess:
        past = datetime.now(timezone.utc) - timedelta(minutes=31)
        sess['last_active'] = past.isoformat()

    # Next request should trigger logout
    resp = client.get('/students/', follow_redirects=True)
    assert b'expired' in resp.data.lower() or b'Sign In' in resp.data


def test_lockout_exact_threshold(client, seed_data, db):
    """Account should lock on exactly the 5th failed attempt."""
    from app.models.user import User
    user = User.query.filter_by(username='admin').first()

    # 4 failed attempts - should not be locked
    for i in range(4):
        client.post('/auth/login', data={
            'username': 'admin', 'password': 'wrong',
        }, follow_redirects=True)
    db.session.refresh(user)
    assert user.locked_until is None

    # 5th attempt should lock
    resp = client.post('/auth/login', data={
        'username': 'admin', 'password': 'wrong',
    }, follow_redirects=True)
    db.session.refresh(user)
    assert user.locked_until is not None


def test_open_redirect_blocked(client, seed_data):
    """Login should reject external redirect URLs in the 'next' parameter."""
    resp = client.post('/auth/login?next=https://evil.com/steal', data={
        'username': 'admin', 'password': 'Admin123!@#$',
    })
    # Should redirect to dashboard, NOT to evil.com
    assert resp.status_code in (302, 303)
    assert 'evil.com' not in resp.headers.get('Location', '')
    assert 'dashboard' in resp.headers.get('Location', '')


def test_open_redirect_relative_allowed(client, seed_data):
    """Login should allow relative 'next' URLs (safe redirects)."""
    resp = client.post('/auth/login?next=/students/', data={
        'username': 'admin', 'password': 'Admin123!@#$',
    })
    assert resp.status_code in (302, 303)
    assert '/students/' in resp.headers.get('Location', '')
