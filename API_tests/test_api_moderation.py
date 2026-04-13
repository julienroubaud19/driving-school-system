"""API integration tests for the moderation blueprint."""

from API_tests.conftest import login


class TestModerationRoutes:

    def test_moderation_queue_requires_auth(self, client):
        resp = client.get('/moderation/')
        assert resp.status_code in (302, 401)

    def test_moderation_queue_requires_permission(self, client, seed_data):
        login(client, 'frontdesk', 'FDesk123!@#$')
        resp = client.get('/moderation/')
        assert resp.status_code == 403

    def test_moderation_queue_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/moderation/')
        assert resp.status_code == 200

    def test_word_list_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/moderation/words')
        assert resp.status_code == 200

    def test_blacklist_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/moderation/blacklist')
        assert resp.status_code == 200

    def test_moderation_detail_not_found(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/moderation/99999/detail', follow_redirects=True)
        assert resp.status_code == 200
        assert b'not found' in resp.data.lower()
