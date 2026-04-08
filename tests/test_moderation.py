from tests.conftest import login
from app.models.moderation import ModerationQueue, SensitiveWord, ModerationLog
from app.models.review import Review
from app.services.moderation_service import check_content, approve_content, reject_content


def test_moderation_queue_page(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/moderation/')
    assert resp.status_code == 200


def test_word_filter_flags_content(client, seed_data, db, app):
    sw = SensitiveWord(word='badword', category='profanity', is_active=True)
    db.session.add(sw)
    db.session.commit()

    r = Review(content='This contains badword in it', location_id=seed_data['location'].id,
               created_by=seed_data['admin'].id, status='pending')
    db.session.add(r)
    db.session.commit()

    item = check_content(r.content, 'review', r.id, seed_data['admin'].id)
    assert item is not None
    db.session.refresh(item)
    assert 'auto_word_match' in item.reason
    assert 'badword' in item.flagged_words


def test_approve_moderation_item(client, seed_data, db, app):
    r = Review(content='Pending approval', location_id=seed_data['location'].id,
               created_by=seed_data['admin'].id, status='pending')
    db.session.add(r)
    db.session.flush()
    item = ModerationQueue(content_type='review', content_id=r.id,
                           reason='manual_report', status='held')
    db.session.add(item)
    db.session.commit()

    with app.app_context():
        approve_content(item.id, seed_data['admin'].id, 'Looks fine')

    db.session.refresh(item)
    assert item.status == 'approved'
    db.session.refresh(r)
    assert r.status == 'approved'
    logs = ModerationLog.query.filter_by(queue_id=item.id).all()
    assert len(logs) == 1
    assert logs[0].action == 'approved'


def test_reject_moderation_item(client, seed_data, db, app):
    r = Review(content='Rejected content', location_id=seed_data['location'].id,
               created_by=seed_data['admin'].id, status='pending')
    db.session.add(r)
    db.session.flush()
    item = ModerationQueue(content_type='review', content_id=r.id,
                           reason='auto_word_match', status='held')
    db.session.add(item)
    db.session.commit()

    with app.app_context():
        reject_content(item.id, seed_data['admin'].id, 'Violation')

    db.session.refresh(item)
    assert item.status == 'rejected'
    db.session.refresh(r)
    assert r.status == 'rejected'


def test_add_sensitive_word(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.post('/moderation/words/add', data={
        'word': 'testword',
        'category': 'test',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert SensitiveWord.query.filter_by(word='testword').first() is not None


def test_toggle_sensitive_word(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    sw = SensitiveWord(word='toggleme', is_active=True)
    db.session.add(sw)
    db.session.commit()

    resp = client.post(f'/moderation/words/{sw.id}/toggle', follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(sw)
    assert sw.is_active is False
