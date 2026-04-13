"""API integration tests for the dashboard blueprint."""

from API_tests.conftest import login


class TestDashboardRoutes:

    def test_dashboard_requires_auth(self, client):
        resp = client.get('/dashboard/')
        assert resp.status_code in (302, 401)

    def test_dashboard_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/dashboard/')
        assert resp.status_code == 200

    def test_drilldown_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        for kpi in ['turnaround', 'utilization', 'retention', 'community', 'financial']:
            resp = client.get(f'/dashboard/drilldown/{kpi}')
            assert resp.status_code == 200, f'Drilldown {kpi} failed'

    def test_drilldown_unknown_kpi_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/dashboard/drilldown/nonexistent')
        assert resp.status_code == 200

    def test_export_requires_permission(self, client, seed_data):
        login(client, 'coach', 'Coach123!@#$')
        resp = client.post('/dashboard/export/financial', data={'format': 'json'})
        assert resp.status_code == 403

    def test_export_unknown_report_redirects(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.post('/dashboard/export/nonexistent', data={'format': 'json'},
                           follow_redirects=True)
        assert resp.status_code == 200
        assert b'Unknown report' in resp.data

    def test_schedules_requires_auth(self, client):
        resp = client.get('/dashboard/schedules')
        assert resp.status_code in (302, 401)

    def test_schedules_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/dashboard/schedules')
        assert resp.status_code == 200
