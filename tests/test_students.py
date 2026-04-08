from tests.conftest import login
from app.models.student import Student


def test_student_list(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/students/')
    assert resp.status_code == 200
    assert b'Students' in resp.data


def test_create_student(client, seed_data, db):
    login(client, 'frontdesk', 'FDesk123!@#$')
    resp = client.post('/students/new', data={
        'first_name': 'John',
        'last_name': 'Doe',
        'email': 'john@test.com',
        'phone': '555-1234',
        'status': 'enrolled',
        'location_id': seed_data['location'].id,
        'assigned_coach_id': 0,
    }, follow_redirects=True)
    assert resp.status_code == 200
    student = Student.query.filter_by(first_name='John', last_name='Doe').first()
    assert student is not None
    assert student.status == 'enrolled'


def test_view_student_detail(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    s = Student(first_name='Jane', last_name='Smith', location_id=seed_data['location'].id,
                handler_id=seed_data['admin'].id)
    db.session.add(s)
    db.session.commit()
    resp = client.get(f'/students/{s.id}')
    assert resp.status_code == 200
    assert b'Jane' in resp.data


def test_edit_student(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    s = Student(first_name='Edit', last_name='Me', location_id=seed_data['location'].id,
                handler_id=seed_data['admin'].id)
    db.session.add(s)
    db.session.commit()
    resp = client.post(f'/students/{s.id}/edit', data={
        'first_name': 'Edited',
        'last_name': 'Me',
        'status': 'active',
        'location_id': seed_data['location'].id,
        'assigned_coach_id': 0,
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(s)
    assert s.first_name == 'Edited'


def test_coach_sees_only_assigned_students(client, seed_data, db):
    coach = seed_data['coach']
    loc = seed_data['location']
    s1 = Student(first_name='Assigned', last_name='Student', location_id=loc.id,
                 assigned_coach_id=coach.id, handler_id=seed_data['admin'].id)
    s2 = Student(first_name='Other', last_name='Student', location_id=loc.id,
                 handler_id=seed_data['admin'].id)
    db.session.add_all([s1, s2])
    db.session.commit()

    login(client, 'coach', 'Coach123!@#$')
    resp = client.get('/students/')
    assert b'Assigned' in resp.data
    assert b'Other' not in resp.data


def test_add_student_note(client, seed_data, db):
    login(client, 'coach', 'Coach123!@#$')
    s = Student(first_name='Note', last_name='Test', location_id=seed_data['location'].id,
                assigned_coach_id=seed_data['coach'].id, handler_id=seed_data['admin'].id)
    db.session.add(s)
    db.session.commit()

    resp = client.post(f'/students/{s.id}/notes', data={
        'content': 'Great progress today!',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert s.notes.count() == 1
