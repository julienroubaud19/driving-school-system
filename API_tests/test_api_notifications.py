"""API integration tests for the notifications blueprint."""

from API_tests.conftest import login


class TestNotificationsRoutes:

    def test_notification_center_requires_auth(self, client):
        resp = client.get('/notifications/')
        assert resp.status_code in (302, 401)

    def test_notification_center_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/notifications/')
        assert resp.status_code == 200

    def test_notification_count_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/notifications/count')
        assert resp.status_code == 200

    def test_subscriptions_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/notifications/subscriptions')
        assert resp.status_code == 200

    def test_mark_all_read_requires_auth(self, client):
        resp = client.post('/notifications/read-all')
        assert resp.status_code in (302, 401)

    def test_count_requires_auth(self, client):
        resp = client.get('/notifications/count')
        assert resp.status_code in (302, 401)
