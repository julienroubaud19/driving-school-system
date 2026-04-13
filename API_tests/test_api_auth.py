"""API integration tests for the auth blueprint."""

from API_tests.conftest import login


class TestAuthRoutes:

    def test_login_page_returns_200(self, client):
        resp = client.get('/auth/login')
        assert resp.status_code == 200

    def test_login_with_valid_credentials(self, client, seed_data):
        resp = client.post('/auth/login', data={
            'username': 'admin', 'password': 'Admin123!@#$',
        })
        assert resp.status_code in (200, 302)

    def test_login_with_invalid_credentials(self, client, seed_data):
        resp = client.post('/auth/login', data={
            'username': 'admin', 'password': 'wrongpassword',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Invalid' in resp.data or b'invalid' in resp.data

    def test_logout_redirects_to_login(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/auth/logout')
        assert resp.status_code == 302
        assert 'login' in resp.headers.get('Location', '')

    def test_change_password_requires_auth(self, client):
        resp = client.get('/auth/change-password')
        assert resp.status_code in (302, 401)

    def test_login_rejects_external_redirect(self, client, seed_data):
        resp = client.post('/auth/login?next=https://evil.com', data={
            'username': 'admin', 'password': 'Admin123!@#$',
        })
        assert resp.status_code in (200, 302)
        assert 'evil.com' not in resp.headers.get('Location', '')
