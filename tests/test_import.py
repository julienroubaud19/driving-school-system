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
