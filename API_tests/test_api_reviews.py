"""API integration tests for the reviews blueprint."""

from API_tests.conftest import login
from app.models.review import Review


class TestReviewsRoutes:

    def test_review_list_requires_auth(self, client):
        resp = client.get('/reviews/')
        assert resp.status_code in (302, 401)

    def test_review_list_returns_200(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/reviews/')
        assert resp.status_code == 200

    def test_create_review_page_returns_200(self, client, seed_data):
        login(client, 'frontdesk', 'FDesk123!@#$')
        resp = client.get('/reviews/new')
        assert resp.status_code == 200

    def test_review_detail_not_found(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/reviews/99999', follow_redirects=True)
        assert resp.status_code == 200
        assert b'not found' in resp.data.lower()

    def test_dispute_not_found(self, client, seed_data):
        login(client, 'admin', 'Admin123!@#$')
        resp = client.get('/reviews/dispute/99999/arbitrate', follow_redirects=True)
        assert resp.status_code == 200
        assert b'not found' in resp.data.lower()

    def test_like_requires_auth(self, client, seed_data, db):
        r = Review(content='Test', location_id=seed_data['location'].id,
                   created_by=seed_data['admin'].id, status='approved')
        db.session.add(r)
        db.session.commit()
        resp = client.post(f'/reviews/{r.id}/like')
        assert resp.status_code in (302, 401)
