from tests.conftest import login
from app.models.student import Student
from app.models.financial import Transaction
from app.models.review import Review


def test_dashboard_loads(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/dashboard/')
    assert resp.status_code == 200
    assert b'Dashboard' in resp.data


def test_dashboard_with_data(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    loc = seed_data['location']

    # Add some data
    s = Student(first_name='A', last_name='B', location_id=loc.id,
                assigned_coach_id=seed_data['coach'].id, handler_id=seed_data['admin'].id)
    db.session.add(s)

    t = Transaction(type='income', amount=500, payee='Client', payment_method='cash',
                    location_id=loc.id, handler_id=seed_data['admin'].id, status='active')
    t.compute_fingerprint()
    db.session.add(t)

    r = Review(content='Good service', location_id=loc.id,
               created_by=seed_data['admin'].id, status='approved')
    db.session.add(r)
    db.session.commit()

    resp = client.get('/dashboard/')
    assert resp.status_code == 200


def test_dashboard_htmx_filter(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/dashboard/',
                      headers={'HX-Request': 'true'},
                      query_string={'location_id': seed_data['location'].id})
    assert resp.status_code == 200


def test_drilldown(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    for kpi in ['turnaround', 'utilization', 'retention', 'community', 'financial']:
        resp = client.get(f'/dashboard/drilldown/{kpi}')
        assert resp.status_code == 200


def test_export_report(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.post('/dashboard/export/financial', data={
        'format': 'json',
    })
    assert resp.status_code == 200


def test_admin_audit_log(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/admin/audit')
    assert resp.status_code == 200


def test_admin_anomalies(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/admin/anomalies')
    assert resp.status_code == 200


def test_admin_users_page(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/admin/users')
    assert resp.status_code == 200


def test_admin_locations_page(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/admin/locations')
    assert resp.status_code == 200


def test_admin_create_user(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.post('/admin/users/new', data={
        'username': 'newuser',
        'email': 'new@test.local',
        'password': 'NewUser123!@#$',
        'role_id': str(seed_data['admin_role'].id),
        'location_id': '0',
        'is_active': 'y',
    }, follow_redirects=True)
    assert resp.status_code == 200
    # Check the response either created user or shows the form
    assert b'newuser' in resp.data


def test_admin_config_page(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/admin/config')
    assert resp.status_code == 200


def test_admin_force_password_reset(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    target = seed_data['frontdesk']
    resp = client.post(f'/admin/users/{target.id}/force-reset', follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(target)
    assert target.force_password_reset is True
