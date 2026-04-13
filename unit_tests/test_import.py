"""Tests for the import service: CSV parsing, preview, validation, duplicate detection, and execution."""

from tests.conftest import login
from app.models.financial import Transaction, BulkImportBatch, BulkImportRow
from app.services.import_service import parse_csv, preview_import, execute_import


def test_parse_csv_valid(app):
    content = "type,amount,payee,date,location_id,payment_method\nincome,100,John,2025-01-01,1,cash\n"
    rows, columns = parse_csv(content, 'test.csv')
    assert len(rows) == 1
    assert 'type' in columns
    assert rows[0]['payee'] == 'John'


def test_preview_import_valid_rows(seed_data, db, app):
    rows = [
        {'type': 'income', 'amount': '100', 'payee': 'Alice', 'date': '2025-01-01',
         'location_id': str(seed_data['location'].id), 'payment_method': 'cash'},
        {'type': 'expense', 'amount': '50', 'payee': 'Bob', 'date': '2025-01-02',
         'location_id': str(seed_data['location'].id), 'payment_method': 'card'},
    ]
    columns = ['type', 'amount', 'payee', 'date', 'location_id', 'payment_method']

    batch = preview_import(rows, columns, seed_data['admin'].id, 'test.csv')
    assert batch is not None
    assert batch.row_count == 2
    assert batch.error_count == 0
    assert batch.status == 'previewing'


def test_preview_import_missing_fields(seed_data, db, app):
    rows = [
        {'type': 'income', 'amount': '', 'payee': '', 'date': '2025-01-01',
         'location_id': str(seed_data['location'].id), 'payment_method': 'cash'},
    ]
    columns = ['type', 'amount', 'payee', 'date', 'location_id', 'payment_method']

    batch = preview_import(rows, columns, seed_data['admin'].id, 'test.csv')
    assert batch.error_count >= 1
    error_row = BulkImportRow.query.filter_by(batch_id=batch.id, status='error').first()
    assert error_row is not None
    assert 'Missing required field' in error_row.error_message


def test_preview_import_invalid_amount(seed_data, db, app):
    rows = [
        {'type': 'income', 'amount': 'abc', 'payee': 'Test', 'date': '2025-01-01',
         'location_id': str(seed_data['location'].id), 'payment_method': 'cash'},
    ]
    columns = ['type', 'amount', 'payee', 'date', 'location_id', 'payment_method']

    batch = preview_import(rows, columns, seed_data['admin'].id, 'test.csv')
    assert batch.error_count >= 1


def test_preview_import_invalid_type(seed_data, db, app):
    rows = [
        {'type': 'refund', 'amount': '100', 'payee': 'Test', 'date': '2025-01-01',
         'location_id': str(seed_data['location'].id), 'payment_method': 'cash'},
    ]
    columns = ['type', 'amount', 'payee', 'date', 'location_id', 'payment_method']

    batch = preview_import(rows, columns, seed_data['admin'].id, 'test.csv')
    assert batch.error_count >= 1


def test_execute_import_creates_transactions(seed_data, db, app):
    rows = [
        {'type': 'income', 'amount': '100', 'payee': 'Import Alice', 'date': '2025-01-01',
         'location_id': str(seed_data['location'].id), 'payment_method': 'cash'},
    ]
    columns = ['type', 'amount', 'payee', 'date', 'location_id', 'payment_method']

    batch = preview_import(rows, columns, seed_data['admin'].id, 'test.csv')
    result_batch, msg = execute_import(batch.id, seed_data['admin'].id)
    assert result_batch is not None
    assert '1' in msg
    assert result_batch.status == 'imported'

    txn = Transaction.query.filter_by(payee='Import Alice').first()
    assert txn is not None
    assert txn.amount == 100.0


def test_execute_import_skips_duplicates_without_resolution(seed_data, db, app):
    """When an import row matches an existing transaction's fingerprint, it should be flagged as duplicate."""
    from app.services.financial_service import compute_fingerprint

    loc_id = seed_data['location'].id
    # Pre-compute a fingerprint with the exact same fields the import will use
    fp = compute_fingerprint('Dup Test', '100', '2025-06-15', str(loc_id), 'cash')

    existing = Transaction(type='income', amount=100, payee='Dup Test',
                           payment_method='cash', location_id=loc_id,
                           handler_id=seed_data['admin'].id, status='active',
                           fingerprint_hash=fp)
    db.session.add(existing)
    db.session.commit()

    rows = [
        {'type': 'income', 'amount': '100', 'payee': 'Dup Test', 'date': '2025-06-15',
         'location_id': str(loc_id), 'payment_method': 'cash'},
    ]
    columns = ['type', 'amount', 'payee', 'date', 'location_id', 'payment_method']

    batch = preview_import(rows, columns, seed_data['admin'].id, 'test.csv')
    assert batch.duplicate_count >= 1

    result_batch, msg = execute_import(batch.id, seed_data['admin'].id)
    assert '0' in msg


def test_import_route_requires_permission(client, seed_data):
    """Coach without financial.import should get 403."""
    login(client, 'coach', 'Coach123!@#$')
    resp = client.get('/financial/import')
    assert resp.status_code == 403


def test_import_batch_ownership_preview(client, seed_data, db, app):
    """A user cannot preview another user's import batch."""
    rows = [
        {'type': 'income', 'amount': '100', 'payee': 'Owner Test', 'date': '2025-01-01',
         'location_id': str(seed_data['location'].id), 'payment_method': 'cash'},
    ]
    columns = ['type', 'amount', 'payee', 'date', 'location_id', 'payment_method']

    batch = preview_import(rows, columns, seed_data['admin'].id, 'owner.csv')

    # frontdesk (different user) should be denied
    login(client, 'frontdesk', 'FDesk123!@#$')
    resp = client.get(f'/financial/import/{batch.id}/preview')
    assert resp.status_code == 403


def test_import_batch_ownership_execute(client, seed_data, db, app):
    """A user cannot execute another user's import batch."""
    rows = [
        {'type': 'income', 'amount': '100', 'payee': 'Exec Test', 'date': '2025-01-01',
         'location_id': str(seed_data['location'].id), 'payment_method': 'cash'},
    ]
    columns = ['type', 'amount', 'payee', 'date', 'location_id', 'payment_method']

    batch = preview_import(rows, columns, seed_data['admin'].id, 'exec.csv')

    login(client, 'frontdesk', 'FDesk123!@#$')
    resp = client.post(f'/financial/import/{batch.id}/execute')
    assert resp.status_code == 403


def test_import_batch_owner_can_preview(client, seed_data, db, app):
    """The batch owner should be able to preview their own batch."""
    rows = [
        {'type': 'income', 'amount': '100', 'payee': 'My Batch', 'date': '2025-01-01',
         'location_id': str(seed_data['location'].id), 'payment_method': 'cash'},
    ]
    columns = ['type', 'amount', 'payee', 'date', 'location_id', 'payment_method']

    batch = preview_import(rows, columns, seed_data['frontdesk'].id, 'mine.csv')

    login(client, 'frontdesk', 'FDesk123!@#$')
    resp = client.get(f'/financial/import/{batch.id}/preview')
    assert resp.status_code == 200


def test_admin_can_preview_any_batch(client, seed_data, db, app):
    """Admin should be able to preview any user's batch."""
    rows = [
        {'type': 'income', 'amount': '100', 'payee': 'Admin Access', 'date': '2025-01-01',
         'location_id': str(seed_data['location'].id), 'payment_method': 'cash'},
    ]
    columns = ['type', 'amount', 'payee', 'date', 'location_id', 'payment_method']

    batch = preview_import(rows, columns, seed_data['frontdesk'].id, 'fd.csv')

    login(client, 'admin', 'Admin123!@#$')
    resp = client.get(f'/financial/import/{batch.id}/preview')
    assert resp.status_code == 200


def test_merge_resolution_updates_existing_transaction(seed_data, db, app):
    """Merge resolution should update the matched transaction's fields."""
    from app.services.financial_service import compute_fingerprint

    loc_id = seed_data['location'].id
    fp = compute_fingerprint('Merge Target', '200', '2025-06-20', str(loc_id), 'card')

    existing = Transaction(type='income', amount=200, payee='Merge Target',
                           description='Old desc', category='Old Cat',
                           payment_method='card', location_id=loc_id,
                           handler_id=seed_data['admin'].id, status='active',
                           fingerprint_hash=fp)
    db.session.add(existing)
    db.session.commit()

    rows = [
        {'type': 'income', 'amount': '200', 'payee': 'Merge Target', 'date': '2025-06-20',
         'location_id': str(loc_id), 'payment_method': 'card',
         'description': 'New desc', 'category': 'New Cat'},
    ]
    columns = list(rows[0].keys())

    batch = preview_import(rows, columns, seed_data['admin'].id, 'merge.csv')
    dup_row = BulkImportRow.query.filter_by(batch_id=batch.id, status='duplicate').first()
    assert dup_row is not None

    dup_row.resolution = 'merge'
    db.session.commit()

    result_batch, msg = execute_import(batch.id, seed_data['admin'].id)
    assert result_batch is not None
    assert 'merged' in msg.lower()

    db.session.refresh(existing)
    assert existing.description == 'New desc'
    assert existing.category == 'New Cat'


def test_keep_resolution_creates_new_transaction(seed_data, db, app):
    """Keep resolution should import a new transaction alongside the existing one."""
    from app.services.financial_service import compute_fingerprint

    loc_id = seed_data['location'].id
    fp = compute_fingerprint('Keep Target', '300', '2025-06-25', str(loc_id), 'cash')

    existing = Transaction(type='income', amount=300, payee='Keep Target',
                           payment_method='cash', location_id=loc_id,
                           handler_id=seed_data['admin'].id, status='active',
                           fingerprint_hash=fp)
    db.session.add(existing)
    db.session.commit()
    existing_id = existing.id

    rows = [
        {'type': 'income', 'amount': '300', 'payee': 'Keep Target', 'date': '2025-06-25',
         'location_id': str(loc_id), 'payment_method': 'cash'},
    ]
    columns = list(rows[0].keys())

    batch = preview_import(rows, columns, seed_data['admin'].id, 'keep.csv')
    dup_row = BulkImportRow.query.filter_by(batch_id=batch.id, status='duplicate').first()
    assert dup_row is not None

    dup_row.resolution = 'keep'
    db.session.commit()

    result_batch, msg = execute_import(batch.id, seed_data['admin'].id)
    assert result_batch is not None
    assert 'kept as new' in msg.lower()

    all_matching = Transaction.query.filter_by(payee='Keep Target').all()
    assert len(all_matching) == 2
