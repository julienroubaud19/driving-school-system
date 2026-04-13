"""API integration tests for the financial blueprint."""

from API_tests.conftest import login
from app.models.financial import Transaction


class TestFinancialRoutes:

    def test_transaction_list_requires_auth(self, client):
        resp = client.get('/financial/')
        assert resp.status_code in (302, 401)

    def test_transaction_list_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/financial/')
        assert resp.status_code == 200

    def test_create_transaction_page_returns_200(self, client, seed_data):
        login(client, 'frontdesk', 'FDesk123!@#$')
        resp = client.get('/financial/new')
        assert resp.status_code == 200

    def test_transaction_detail_not_found(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/financial/99999', follow_redirects=True)
        assert resp.status_code == 200
        assert b'not found' in resp.data.lower()

    def test_coach_cannot_create_transaction(self, client, seed_data):
        login(client, 'coach', 'Coach123!@#$')
        resp = client.get('/financial/new')
        assert resp.status_code == 403

    def test_import_page_requires_auth(self, client):
        resp = client.get('/financial/import')
        assert resp.status_code in (302, 401)

    def test_import_page_returns_200_for_authorized(self, client, seed_data):
        login(client, 'frontdesk', 'FDesk123!@#$')
        resp = client.get('/financial/import')
        assert resp.status_code == 200

    def test_closeout_requires_permission(self, client, seed_data):
        login(client, 'frontdesk', 'FDesk123!@#$')
        resp = client.get('/financial/closeout')
        assert resp.status_code == 403

    def test_download_file_requires_auth(self, client):
        resp = client.get('/financial/uploads/receipts/test.jpg')
        assert resp.status_code in (302, 401)

    def test_void_page_not_found(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/financial/99999/void', follow_redirects=True)
        assert resp.status_code == 200
        assert b'not found' in resp.data.lower()
