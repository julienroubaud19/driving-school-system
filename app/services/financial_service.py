import hashlib
import json
from datetime import datetime, timezone
from difflib import SequenceMatcher

from flask import current_app

from app.extensions import db
from app.models.financial import Transaction, TransactionVersion, MonthlyCloseout
from app.services.audit_service import log_event


def compute_fingerprint(payee, amount, date_str, location_id, payment_method):
    normalized = '|'.join([
        (payee or '').strip().lower(),
        f'{float(amount):.2f}',
        str(date_str or ''),
        str(location_id or ''),
        (payment_method or '').strip().lower(),
    ])
    return hashlib.sha256(normalized.encode()).hexdigest()


def find_duplicates(fingerprint, exclude_id=None):
    threshold = current_app.config['DUPLICATE_SIMILARITY_THRESHOLD']
    candidates = Transaction.query.filter(
        Transaction.fingerprint_hash.isnot(None),
        Transaction.status.notin_(['voided', 'reversed']),
    )
    if exclude_id:
        candidates = candidates.filter(Transaction.id != exclude_id)

    matches = []
    for t in candidates.all():
        similarity = SequenceMatcher(None, fingerprint, t.fingerprint_hash).ratio()
        if similarity >= threshold:
            matches.append((t, similarity))
    return matches


def record_version(transaction, changed_by_id, changes_dict):
    last_version = TransactionVersion.query.filter_by(
        transaction_id=transaction.id
    ).order_by(TransactionVersion.version_number.desc()).first()
    next_num = (last_version.version_number + 1) if last_version else 1

    version = TransactionVersion(
        transaction_id=transaction.id,
        version_number=next_num,
        field_changes=json.dumps(changes_dict),
        changed_by=changed_by_id,
    )
    db.session.add(version)
    return version


def void_transaction(transaction_id, reason, approved_by_id, user_id):
    txn = db.session.get(Transaction, transaction_id)
    if not txn or txn.status not in ('active', 'draft'):
        return None, 'Transaction cannot be voided.'

    txn.status = 'voided'
    txn.void_reason = reason
    txn.void_approved_by = approved_by_id

    record_version(txn, user_id, {'status': ['active', 'voided'], 'void_reason': [None, reason]})
    log_event('transaction_voided', user_id=user_id,
              resource_type='transaction', resource_id=txn.id,
              detail={'reason': reason})
    db.session.commit()
    return txn, None


def create_reversal(original_id, user_id, approved_by_id):
    original = db.session.get(Transaction, original_id)
    if not original:
        return None, 'Original transaction not found.'

    reversal = Transaction(
        type=original.type,
        amount=-original.amount,
        payee=original.payee,
        description=f'Reversal of transaction #{original.id}',
        category=original.category,
        payment_method=original.payment_method,
        location_id=original.location_id,
        handler_id=user_id,
        status='active',
        reversal_of_id=original.id,
        void_approved_by=approved_by_id,
    )
    reversal.compute_fingerprint()
    db.session.add(reversal)

    original.status = 'reversed'
    record_version(original, user_id, {'status': [original.status, 'reversed']})

    log_event('transaction_reversed', user_id=user_id,
              resource_type='transaction', resource_id=original.id)
    db.session.commit()
    return reversal, None


def close_month(location_id, month, year, user_id):
    existing = MonthlyCloseout.query.filter_by(
        location_id=location_id, month=month, year=year
    ).first()
    if existing:
        return None, 'This month is already closed.'

    closeout = MonthlyCloseout(
        location_id=location_id, month=month, year=year, closed_by=user_id,
    )
    db.session.add(closeout)
    db.session.flush()

    Transaction.query.filter(
        Transaction.location_id == location_id,
        Transaction.status == 'active',
        db.extract('month', Transaction.created_at) == month,
        db.extract('year', Transaction.created_at) == year,
    ).update({'status': 'closed', 'closeout_id': closeout.id}, synchronize_session='fetch')

    log_event('monthly_closeout', user_id=user_id,
              resource_type='closeout', resource_id=closeout.id,
              detail={'location_id': location_id, 'month': month, 'year': year})
    db.session.commit()
    return closeout, None
