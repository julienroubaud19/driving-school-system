from tests.conftest import login
from app.models.review import Review, RatingDimension, RatingScore, ReviewLike, Dispute
from app.models.student import Student


def test_review_list(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/reviews/')
    assert resp.status_code == 200


def test_create_review(client, seed_data, db):
    login(client, 'frontdesk', 'FDesk123!@#$')
    dim = RatingDimension.query.first()
    resp = client.post('/reviews/new', data={
        'content': 'Great driving instructor!',
        'coach_id': 0,
        'location_id': seed_data['location'].id,
        f'score_{dim.id}': 5,
    }, follow_redirects=True)
    assert resp.status_code == 200
    review = Review.query.filter_by(content='Great driving instructor!').first()
    assert review is not None


def test_like_review(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    r = Review(content='Likeable', location_id=seed_data['location'].id,
               created_by=seed_data['admin'].id, status='approved')
    db.session.add(r)
    db.session.commit()

    resp = client.post(f'/reviews/{r.id}/like', follow_redirects=True)
    assert resp.status_code == 200
    assert ReviewLike.query.filter_by(review_id=r.id, user_id=seed_data['admin'].id).first() is not None

    # Unlike
    resp = client.post(f'/reviews/{r.id}/like', follow_redirects=True)
    assert ReviewLike.query.filter_by(review_id=r.id, user_id=seed_data['admin'].id).first() is None


def test_report_review(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    r = Review(content='Reportable', location_id=seed_data['location'].id,
               created_by=seed_data['admin'].id, status='approved')
    db.session.add(r)
    db.session.commit()

    resp = client.post(f'/reviews/{r.id}/report', data={
        'reason': 'Inappropriate content',
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_dispute_review(client, seed_data, db):
    login(client, 'coach', 'Coach123!@#$')
    r = Review(content='Disputable', location_id=seed_data['location'].id,
               created_by=seed_data['frontdesk'].id, status='approved')
    db.session.add(r)
    db.session.commit()

    resp = client.post(f'/reviews/{r.id}/dispute', data={
        'statement': 'This review is inaccurate',
    }, follow_redirects=True)
    assert resp.status_code == 200
    d = Dispute.query.filter_by(review_id=r.id).first()
    assert d is not None
    assert d.status == 'open'


def test_arbitrate_dispute(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    r = Review(content='Disputed review', location_id=seed_data['location'].id,
               created_by=seed_data['frontdesk'].id, status='disputed')
    db.session.add(r)
    db.session.flush()
    d = Dispute(review_id=r.id, initiated_by=seed_data['coach'].id,
                statement='Unfair review')
    db.session.add(d)
    db.session.commit()

    resp = client.post(f'/reviews/dispute/{d.id}/arbitrate', data={
        'outcome': 'Review upheld after investigation.',
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(d)
    assert d.status == 'resolved'
    assert d.arbitration_outcome == 'Review upheld after investigation.'
