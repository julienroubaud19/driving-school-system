from tests.conftest import login
from app.models.financial import Transaction, MonthlyCloseout


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


def test_void_transaction(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    txn = Transaction(type='expense', amount=50, payee='Vendor',
                      payment_method='cash', location_id=seed_data['location'].id,
                      handler_id=seed_data['admin'].id, status='active')
    txn.compute_fingerprint()
    db.session.add(txn)
    db.session.commit()

    resp = client.post(f'/financial/{txn.id}/void', data={
        'reason': 'Duplicate entry',
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(txn)
    assert txn.status == 'voided'


def test_reverse_transaction(client, seed_data, db):
    login(client, 'admin', 'Admin123!@#$')
    txn = Transaction(type='income', amount=200, payee='Client',
                      payment_method='card', location_id=seed_data['location'].id,
                      handler_id=seed_data['admin'].id, status='active')
    txn.compute_fingerprint()
    db.session.add(txn)
    db.session.commit()

    resp = client.post(f'/financial/{txn.id}/reverse', follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(txn)
    assert txn.status == 'reversed'
    reversal = Transaction.query.filter_by(reversal_of_id=txn.id).first()
    assert reversal is not None
    assert reversal.amount == -200


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
