"""Seed script: creates default roles, permissions, locations, notification types,
rating dimensions, and an admin user."""

from app import create_app
from app.extensions import db
from app.models.user import User, Role, Permission, role_permissions
from app.models.location import Location
from app.models.notification import NotificationType
from app.models.review import RatingDimension

app = create_app()

PERMISSIONS = [
    # Students
    ('student.view', 'View students'),
    ('student.create', 'Create students'),
    ('student.edit', 'Edit students'),
    ('student.add_note', 'Add student notes'),
    # Financial
    ('financial.view', 'View transactions'),
    ('financial.create', 'Create transactions'),
    ('financial.edit', 'Edit transactions'),
    ('financial.void', 'Void/reverse transactions'),
    ('financial.closeout', 'Perform monthly closeout'),
    ('financial.import', 'Bulk import transactions'),
    # Reviews
    ('review.view', 'View reviews'),
    ('review.create', 'Create reviews'),
    ('review.dispute', 'Dispute reviews'),
    ('review.moderate', 'Moderate reviews'),
    # Moderation (uses review.moderate)
    # Reports
    ('report.view', 'View reports/dashboards'),
    ('report.export', 'Export reports'),
    # Admin
    ('admin.users', 'Manage users'),
    ('admin.config', 'Manage configuration'),
    ('admin.audit', 'View audit logs'),
]

ROLES = {
    'Administrator': [p[0] for p in PERMISSIONS],  # all permissions
    'FrontDesk': [
        'student.view', 'student.create', 'student.edit', 'student.add_note',
        'financial.view', 'financial.create', 'financial.edit', 'financial.import',
        'review.view', 'review.create',
        'report.view',
    ],
    'Coach': [
        'student.view', 'student.add_note',
        'review.view', 'review.create', 'review.dispute',
        'report.view',
    ],
    'Auditor': [
        'student.view',
        'financial.view',
        'review.view',
        'report.view', 'report.export',
        'admin.audit',
    ],
}

LOCATIONS = [
    ('Main Branch', '100 Main Street, Anytown, ST 12345', '555-0100'),
    ('Downtown Branch', '250 Center Avenue, Anytown, ST 12345', '555-0200'),
    ('Suburban Center', '800 Oak Park Drive, Suburbia, ST 12346', '555-0300'),
]

NOTIFICATION_TYPES = [
    ('registration_approved', 'Registration Approved', 'Student registration has been approved'),
    ('registration_returned', 'Registration Returned', 'Student registration was returned for corrections'),
    ('document_review_needed', 'Document Review Needed', 'A document requires your review'),
    ('dispute_assigned', 'Dispute Assigned', 'A dispute has been assigned or resolved'),
    ('monthly_report_ready', 'Monthly Report Ready', 'A monthly report is available'),
]

RATING_DIMENSIONS = [
    ('professionalism', 'Professionalism', 1),
    ('punctuality', 'Punctuality', 2),
    ('vehicle_condition', 'Vehicle Condition', 3),
    ('overall', 'Overall Score', 4),
]


def seed():
    with app.app_context():
        db.create_all()

        # Permissions
        perm_map = {}
        for codename, desc in PERMISSIONS:
            p = Permission.query.filter_by(codename=codename).first()
            if not p:
                p = Permission(codename=codename, description=desc)
                db.session.add(p)
                db.session.flush()
            perm_map[codename] = p

        # Roles
        role_map = {}
        for role_name, perm_codes in ROLES.items():
            r = Role.query.filter_by(name=role_name).first()
            if not r:
                r = Role(name=role_name, description=f'{role_name} role')
                db.session.add(r)
                db.session.flush()
            r.permissions = [perm_map[c] for c in perm_codes]
            role_map[role_name] = r

        # Locations
        for name, address, phone in LOCATIONS:
            if not Location.query.filter_by(name=name).first():
                db.session.add(Location(name=name, address=address, phone=phone))

        db.session.flush()

        # Admin user
        admin_role = role_map['Administrator']
        main_loc = Location.query.filter_by(name='Main Branch').first()
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@drivingschool.local',
                role_id=admin_role.id,
                location_id=main_loc.id if main_loc else None,
                is_active=True,
            )
            admin.set_password('Admin123!@#$')
            db.session.add(admin)

        # Sample users for each role
        samples = [
            ('frontdesk1', 'frontdesk1@drivingschool.local', 'FrontDesk', 'FDesk123!@#$'),
            ('coach1', 'coach1@drivingschool.local', 'Coach', 'Coach123!@#$'),
            ('auditor1', 'auditor1@drivingschool.local', 'Auditor', 'Audit123!@#$'),
        ]
        for uname, email, rname, pwd in samples:
            if not User.query.filter_by(username=uname).first():
                u = User(
                    username=uname,
                    email=email,
                    role_id=role_map[rname].id,
                    location_id=main_loc.id if main_loc else None,
                    is_active=True,
                )
                u.set_password(pwd)
                db.session.add(u)

        # Notification types
        for codename, label, desc in NOTIFICATION_TYPES:
            if not NotificationType.query.filter_by(codename=codename).first():
                db.session.add(NotificationType(codename=codename, label=label, description=desc))

        # Rating dimensions
        for name, label, order in RATING_DIMENSIONS:
            if not RatingDimension.query.filter_by(name=name).first():
                db.session.add(RatingDimension(name=name, label=label, sort_order=order))

        db.session.commit()
        print('Seed completed successfully!')
        print('  Admin user: admin / Admin123!@#$')
        print('  FrontDesk:  frontdesk1 / FDesk123!@#$')
        print('  Coach:      coach1 / Coach123!@#$')
        print('  Auditor:    auditor1 / Audit123!@#$')
        print(f'  Locations:  {", ".join(l[0] for l in LOCATIONS)}')


if __name__ == '__main__':
    seed()
