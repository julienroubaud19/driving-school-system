"""API integration tests for the admin blueprint."""

from API_tests.conftest import login


class TestAdminRoutes:

    def test_admin_users_requires_auth(self, client):
        resp = client.get('/admin/users')
        assert resp.status_code in (302, 401)

    def test_admin_users_requires_admin_role(self, client, seed_data):
        login(client, 'frontdesk', 'FDesk123!@#$')
        resp = client.get('/admin/users')
        assert resp.status_code == 403

    def test_admin_users_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/admin/users')
        assert resp.status_code == 200

    def test_admin_locations_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/admin/locations')
        assert resp.status_code == 200

    def test_admin_dimensions_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/admin/dimensions')
        assert resp.status_code == 200

    def test_admin_audit_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/admin/audit')
        assert resp.status_code == 200

    def test_admin_anomalies_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/admin/anomalies')
        assert resp.status_code == 200

    def test_admin_config_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/admin/config')
        assert resp.status_code == 200

    def test_coach_cannot_access_admin_audit(self, client, seed_data):
        login(client, 'coach', 'Coach123!@#$')
        resp = client.get('/admin/audit')
        assert resp.status_code == 403

    def test_admin_user_edit_not_found(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/admin/users/99999/edit', follow_redirects=True)
        assert resp.status_code == 200
        assert b'not found' in resp.data.lower()
