from tests.conftest import login
from app.models.financial import Transaction, TransactionVersion, MonthlyCloseout
from app.services.financial_service import void_transaction, create_reversal


def test_transaction_list(client, seed_data):
    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/financial/')
    assert resp.status_code == 200


def test_create_transaction(client, seed_data, db):
    login(client, 'frontdesk', 'FDesk123!@#$')
    resp = client.post('/financial/new', data={
        'type': 'income',
        'amount': '250.00',
        'payee': 'John Doe',
        'description': 'Lesson payment',
        'category': 'Tuition',
        'payment_method': 'cash',
        'location_id': seed_data['location'].id,
    }, follow_redirects=True)
    assert resp.status_code == 200
    txn = Transaction.query.filter_by(payee='John Doe').first()
    assert txn is not None
    assert txn.amount == 250.0
    assert txn.fingerprint_hash is not None


def test_edit_transaction_creates_version(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    txn = Transaction(type='income', amount=100, payee='Test', payment_method='cash',
                      location_id=seed_data['location'].id, handler_id=seed_data['admin'].id)
    txn.compute_fingerprint()
    db.session.add(txn)
    db.session.commit()

    resp = client.post(f'/financial/{txn.id}/edit', data={
        'type': 'income',
        'amount': '150.00',
        'payee': 'Test Updated',
        'payment_method': 'card',
        'location_id': seed_data['location'].id,
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert len(txn.versions) > 0


def test_void_transaction_with_supervisor(client, seed_data, db, app):
    """Void requires a different supervisor to approve."""
    # Create a second admin to act as supervisor
    from app.models.user import User
    admin2 = User(username='admin2', email='admin2@test.local',
                  role_id=seed_data['admin_role'].id,
                  location_id=seed_data['location'].id, is_active=True)
    admin2.set_password('Admin123!@#$')
    db.session.add(admin2)
    db.session.commit()

    login(client, 'admin', 'Admin123!@#$')
    txn = Transaction(type='expense', amount=50, payee='Vendor',
                      payment_method='cash', location_id=seed_data['location'].id,
                      handler_id=seed_data['admin'].id, status='active')
    txn.compute_fingerprint()
    db.session.add(txn)
    db.session.commit()

    resp = client.post(f'/financial/{txn.id}/void', data={
        'reason': 'Duplicate entry',
        'approved_by': admin2.id,
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(txn)
    assert txn.status == 'voided'


def test_void_self_approval_rejected(app, seed_data, db):
    """Self-approval for void must be rejected."""
    txn = Transaction(type='expense', amount=50, payee='Vendor',
                      payment_method='cash', location_id=seed_data['location'].id,
                      handler_id=seed_data['admin'].id, status='active')
    txn.compute_fingerprint()
    db.session.add(txn)
    db.session.commit()

    result, error = void_transaction(txn.id, 'test reason',
                                     seed_data['admin'].id, seed_data['admin'].id)
    assert result is None
    assert 'cannot approve your own' in error


def test_reverse_transaction_with_supervisor(client, seed_data, db):
    """Reversal requires a different supervisor to approve."""
    from app.models.user import User
    admin2 = User(username='admin2', email='admin2@test.local',
                  role_id=seed_data['admin_role'].id,
                  location_id=seed_data['location'].id, is_active=True)
    admin2.set_password('Admin123!@#$')
    db.session.add(admin2)
    db.session.commit()

    login(client, 'admin', 'Admin123!@#$')
    txn = Transaction(type='income', amount=200, payee='Client',
                      payment_method='card', location_id=seed_data['location'].id,
                      handler_id=seed_data['admin'].id, status='active')
    txn.compute_fingerprint()
    db.session.add(txn)
    db.session.commit()

    resp = client.post(f'/financial/{txn.id}/reverse', data={
        'approved_by': admin2.id,
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(txn)
    assert txn.status == 'reversed'
    reversal = Transaction.query.filter_by(reversal_of_id=txn.id).first()
    assert reversal is not None
    assert reversal.amount == -200


def test_reverse_self_approval_rejected(app, seed_data, db):
    """Self-approval for reversal must be rejected."""
    txn = Transaction(type='income', amount=200, payee='Client',
                      payment_method='card', location_id=seed_data['location'].id,
                      handler_id=seed_data['admin'].id, status='active')
    txn.compute_fingerprint()
    db.session.add(txn)
    db.session.commit()

    result, error = create_reversal(txn.id, seed_data['admin'].id, seed_data['admin'].id)
    assert result is None
    assert 'cannot approve your own' in error


def test_reversal_version_records_correct_old_status(app, seed_data, db):
    """Version history should record the actual old status, not 'reversed'."""
    from app.models.user import User
    admin2 = User(username='admin2', email='admin2@test.local',
                  role_id=seed_data['admin_role'].id,
                  location_id=seed_data['location'].id, is_active=True)
    admin2.set_password('Admin123!@#$')
    db.session.add(admin2)
    db.session.commit()

    txn = Transaction(type='income', amount=200, payee='Client',
                      payment_method='card', location_id=seed_data['location'].id,
                      handler_id=seed_data['admin'].id, status='active')
    txn.compute_fingerprint()
    db.session.add(txn)
    db.session.commit()

    reversal, error = create_reversal(txn.id, seed_data['admin'].id, admin2.id)
    assert reversal is not None
    version = TransactionVersion.query.filter_by(transaction_id=txn.id).first()
    assert version is not None
    changes = version.get_changes()
    assert changes['status'][0] == 'active'
    assert changes['status'][1] == 'reversed'


def test_closed_transaction_not_editable(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    txn = Transaction(type='income', amount=100, payee='Closed',
                      payment_method='cash', location_id=seed_data['location'].id,
                      handler_id=seed_data['admin'].id, status='closed')
    txn.compute_fingerprint()
    db.session.add(txn)
    db.session.commit()

    resp = client.post(f'/financial/{txn.id}/edit', data={
        'type': 'income', 'amount': '200', 'payee': 'Changed',
        'payment_method': 'cash', 'location_id': seed_data['location'].id,
    }, follow_redirects=True)
    assert b'cannot be edited' in resp.data.lower() or txn.payee == 'Closed'


def test_monthly_closeout(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    txn = Transaction(type='income', amount=300, payee='Pre-close',
                      payment_method='cash', location_id=seed_data['location'].id,
                      handler_id=seed_data['admin'].id, status='active')
    txn.compute_fingerprint()
    db.session.add(txn)
    db.session.commit()

    resp = client.post('/financial/closeout', data={
        'location_id': seed_data['location'].id,
        'month': txn.created_at.month,
        'year': txn.created_at.year,
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(txn)
    assert txn.status == 'closed'


def test_cross_location_financial_access_denied(client, seed_data, db):
    """FrontDesk user from location2 cannot access transaction from location1."""
    txn = Transaction(type='income', amount=100, payee='Location1Only',
                      payment_method='cash', location_id=seed_data['location'].id,
                      handler_id=seed_data['admin'].id, status='active')
    txn.compute_fingerprint()
    db.session.add(txn)
    db.session.commit()

    login(client, 'frontdesk2', 'FDesk123!@#$')
    resp = client.get(f'/financial/{txn.id}')
    assert resp.status_code == 403


def test_cross_location_financial_list_filtered(client, seed_data, db):
    """FrontDesk user from location2 should only see their location's transactions."""
    txn1 = Transaction(type='income', amount=100, payee='Loc1Txn',
                       payment_method='cash', location_id=seed_data['location'].id,
                       handler_id=seed_data['admin'].id, status='active')
    txn1.compute_fingerprint()
    txn2 = Transaction(type='income', amount=200, payee='Loc2Txn',
                       payment_method='cash', location_id=seed_data['location2'].id,
                       handler_id=seed_data['frontdesk2'].id, status='active')
    txn2.compute_fingerprint()
    db.session.add_all([txn1, txn2])
    db.session.commit()

    login(client, 'frontdesk2', 'FDesk123!@#$')
    resp = client.get('/financial/')
    assert b'Loc2Txn' in resp.data
    assert b'Loc1Txn' not in resp.data


def test_admin_sees_all_locations_financial(client, seed_data, db):
    """Admin can see transactions from all locations."""
    txn1 = Transaction(type='income', amount=100, payee='Loc1Admin',
                       payment_method='cash', location_id=seed_data['location'].id,
                       handler_id=seed_data['admin'].id, status='active')
    txn1.compute_fingerprint()
    txn2 = Transaction(type='income', amount=200, payee='Loc2Admin',
                       payment_method='cash', location_id=seed_data['location2'].id,
                       handler_id=seed_data['frontdesk2'].id, status='active')
    txn2.compute_fingerprint()
    db.session.add_all([txn1, txn2])
    db.session.commit()

    login(client, 'admin', 'Admin123!@#$')
    resp = client.get('/financial/')
    assert b'Loc1Admin' in resp.data
    assert b'Loc2Admin' in resp.data
