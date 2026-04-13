import os
import pytest

from app import create_app
from app.extensions import db as _db
from app.models.user import User, Role, Permission, role_permissions
from app.models.location import Location
from app.models.notification import NotificationType
from app.models.review import RatingDimension
from config import TestConfig


@pytest.fixture(scope='session')
def app():
    app = create_app(TestConfig)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    yield app


@pytest.fixture(autouse=True)
def db(app):
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seed_data(db):
    """Create minimal seed data for API tests."""
    perms = {}
    for code in ['student.view', 'student.create', 'student.edit', 'student.add_note',
                 'financial.view', 'financial.create', 'financial.edit', 'financial.void',
                 'financial.closeout', 'financial.import',
                 'review.view', 'review.create', 'review.dispute', 'review.moderate',
                 'report.view', 'report.export',
                 'admin.users', 'admin.config', 'admin.audit']:
        p = Permission(codename=code, description=code)
        db.session.add(p)
        perms[code] = p
    db.session.flush()

    admin_role = Role(name='Administrator', description='Admin')
    db.session.add(admin_role)
    db.session.flush()
    admin_role.permissions = list(perms.values())

    frontdesk_role = Role(name='FrontDesk', description='Front Desk')
    db.session.add(frontdesk_role)
    db.session.flush()
    frontdesk_role.permissions = [perms[c] for c in [
        'student.view', 'student.create', 'student.edit', 'student.add_note',
        'financial.view', 'financial.create', 'financial.edit', 'financial.import',
        'review.view', 'review.create', 'report.view',
    ]]

    coach_role = Role(name='Coach', description='Coach')
    db.session.add(coach_role)
    db.session.flush()
    coach_role.permissions = [perms[c] for c in [
        'student.view', 'student.add_note', 'review.view', 'review.create',
        'review.dispute', 'report.view',
    ]]

    auditor_role = Role(name='Auditor', description='Auditor')
    db.session.add(auditor_role)
    db.session.flush()
    auditor_role.permissions = [perms[c] for c in [
        'student.view', 'financial.view', 'review.view',
        'report.view', 'report.export', 'admin.audit',
    ]]

    loc = Location(name='Main Branch', address='100 Main St', phone='555-0100')
    db.session.add(loc)
    loc2 = Location(name='Downtown Branch', address='250 Center Ave', phone='555-0200')
    db.session.add(loc2)
    db.session.flush()

    admin = User(username='admin', email='admin@test.local',
                 role_id=admin_role.id, location_id=loc.id, is_active=True)
    admin.set_password('Admin123!@#$')
    db.session.add(admin)

    frontdesk = User(username='frontdesk', email='fd@test.local',
                     role_id=frontdesk_role.id, location_id=loc.id, is_active=True)
    frontdesk.set_password('FDesk123!@#$')
    db.session.add(frontdesk)

    coach = User(username='coach', email='coach@test.local',
                 role_id=coach_role.id, location_id=loc.id, is_active=True)
    coach.set_password('Coach123!@#$')
    db.session.add(coach)

    auditor = User(username='auditor', email='auditor@test.local',
                   role_id=auditor_role.id, location_id=loc.id, is_active=True)
    auditor.set_password('Audit123!@#$')
    db.session.add(auditor)

    for code, label in [('registration_approved', 'Registration Approved'),
                        ('dispute_assigned', 'Dispute Assigned'),
                        ('monthly_report_ready', 'Monthly Report Ready')]:
        db.session.add(NotificationType(codename=code, label=label))

    for name, label, order in [('professionalism', 'Professionalism', 1),
                                ('overall', 'Overall Score', 2)]:
        db.session.add(RatingDimension(name=name, label=label, sort_order=order))

    db.session.commit()
    return {
        'admin': admin, 'frontdesk': frontdesk, 'coach': coach,
        'auditor': auditor, 'location': loc, 'location2': loc2,
        'admin_role': admin_role,
    }


def login(client, username, password):
    return client.post('/auth/login', data={
        'username': username, 'password': password,
    }, follow_redirects=True)
