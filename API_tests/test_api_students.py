"""API integration tests for the students blueprint."""

from API_tests.conftest import login


class TestStudentsRoutes:

    def test_student_list_requires_auth(self, client):
        resp = client.get('/students/')
        assert resp.status_code in (302, 401)

    def test_student_list_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/students/')
        assert resp.status_code == 200

    def test_create_student_page_returns_200(self, client, seed_data):
        login(client, 'frontdesk', 'FDesk123!@#$')
        resp = client.get('/students/new')
        assert resp.status_code == 200

    def test_student_detail_404_for_nonexistent(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/students/99999')
        assert resp.status_code == 404

    def test_coach_cannot_create_student(self, client, seed_data):
        login(client, 'coach', 'Coach123!@#$')
        resp = client.get('/students/new')
        assert resp.status_code == 403

    def test_create_student_via_post(self, client, seed_data):
        login(client, 'frontdesk', 'FDesk123!@#$')
        resp = client.post('/students/new', data={
            'first_name': 'Test',
            'last_name': 'Student',
            'email': 'test@student.local',
            'status': 'enrolled',
            'location_id': seed_data['location'].id,
            'assigned_coach_id': 0,
        }, follow_redirects=True)
        assert resp.status_code == 200
