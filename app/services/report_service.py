import csv
import io
import json
import os
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.student import Student
from app.models.financial import Transaction
from app.models.review import Review, Dispute
from app.models.audit import AuditEvent


def get_approval_turnaround(location_id=None, date_from=None, date_to=None):
    from app.models.moderation import ModerationQueue
    query = ModerationQueue.query.filter(ModerationQueue.handled_at.isnot(None))
    if date_from:
        query = query.filter(ModerationQueue.created_at >= date_from)
    if date_to:
        query = query.filter(ModerationQueue.created_at <= date_to)

    items = query.all()
    if not items:
        return {'avg_hours': 0, 'count': 0}

    total_hours = sum(
        (i.handled_at - i.created_at).total_seconds() / 3600 for i in items
    )
    return {'avg_hours': round(total_hours / len(items), 2), 'count': len(items)}


def get_coach_utilization(location_id=None, date_from=None, date_to=None):
    from app.models.user import User, Role
    coach_role = Role.query.filter_by(name='Coach').first()
    if not coach_role:
        return []

    coaches = User.query.filter_by(role_id=coach_role.id, is_active=True)
    if location_id:
        coaches = coaches.filter_by(location_id=location_id)

    result = []
    for coach in coaches.all():
        student_count = Student.query.filter_by(assigned_coach_id=coach.id)
        if date_from:
            student_count = student_count.filter(Student.created_at >= date_from)
        if date_to:
            student_count = student_count.filter(Student.created_at <= date_to)
        result.append({
            'coach_id': coach.id,
            'coach_name': coach.username,
            'student_count': student_count.count(),
        })
    return result


def get_retention_rate(location_id=None, date_from=None, date_to=None):
    query = Student.query
    if location_id:
        query = query.filter_by(location_id=location_id)
    if date_from:
        query = query.filter(Student.enrollment_date >= date_from)
    if date_to:
        query = query.filter(Student.enrollment_date <= date_to)

    total = query.count()
    active = query.filter(Student.status.in_(['active', 'completed'])).count()
    withdrawn = query.filter_by(status='withdrawn').count()

    return {
        'total': total,
        'active': active,
        'withdrawn': withdrawn,
        'retention_pct': round((active / total * 100) if total else 0, 1),
    }


def get_community_activity(location_id=None, date_from=None, date_to=None):
    review_q = Review.query
    if location_id:
        review_q = review_q.filter_by(location_id=location_id)
    if date_from:
        review_q = review_q.filter(Review.created_at >= date_from)
    if date_to:
        review_q = review_q.filter(Review.created_at <= date_to)

    total_reviews = review_q.count()
    approved_reviews = review_q.filter_by(status='approved').count()
    dispute_q = Dispute.query
    if date_from:
        dispute_q = dispute_q.filter(Dispute.created_at >= date_from)
    if date_to:
        dispute_q = dispute_q.filter(Dispute.created_at <= date_to)
    total_disputes = dispute_q.count()

    return {
        'total_reviews': total_reviews,
        'approved_reviews': approved_reviews,
        'total_disputes': total_disputes,
    }


def get_financial_summary(location_id=None, date_from=None, date_to=None):
    query = Transaction.query.filter(Transaction.status.in_(['active', 'closed']))
    if location_id:
        query = query.filter_by(location_id=location_id)
    if date_from:
        query = query.filter(Transaction.created_at >= date_from)
    if date_to:
        query = query.filter(Transaction.created_at <= date_to)

    income = sum(t.amount for t in query.filter_by(type='income').all())
    expenses = sum(t.amount for t in query.filter_by(type='expense').all())

    return {
        'total_income': round(income, 2),
        'total_expenses': round(expenses, 2),
        'net': round(income - expenses, 2),
        'transaction_count': query.count(),
    }


def export_report(data, report_name, fmt='csv'):
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f'{report_name}_{timestamp}.{fmt}'
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'exports', filename)

    if fmt == 'csv' and isinstance(data, list) and data:
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
    else:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        if fmt == 'json':
            pass
        else:
            filename = filename.replace(f'.{fmt}', '.json')

    return filename, filepath
