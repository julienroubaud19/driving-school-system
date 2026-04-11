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


def get_approval_turnaround_records(location_id=None, date_from=None, date_to=None, page=1, per_page=25):
    from app.models.moderation import ModerationQueue
    query = ModerationQueue.query.filter(ModerationQueue.handled_at.isnot(None))
    if date_from:
        query = query.filter(ModerationQueue.created_at >= date_from)
    if date_to:
        query = query.filter(ModerationQueue.created_at <= date_to)
    query = query.order_by(ModerationQueue.handled_at.desc())

    items = query.limit(per_page).offset((page - 1) * per_page).all()
    total = query.count()
    records = []
    for item in items:
        hours = (item.handled_at - item.created_at).total_seconds() / 3600
        records.append({
            'id': item.id,
            'description': f'{item.content_type} #{item.content_id}',
            'submitted_at': item.created_at.strftime('%Y-%m-%d %H:%M'),
            'approved_at': item.handled_at.strftime('%Y-%m-%d %H:%M'),
            'hours': round(hours, 1),
            'status': item.status,
        })
    return records, total


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


def get_coach_utilization_records(location_id=None, date_from=None, date_to=None, page=1, per_page=25):
    from app.models.user import User, Role
    coach_role = Role.query.filter_by(name='Coach').first()
    if not coach_role:
        return [], 0

    coaches = User.query.filter_by(role_id=coach_role.id, is_active=True)
    if location_id:
        coaches = coaches.filter_by(location_id=location_id)

    records = []
    for coach in coaches.all():
        students_q = Student.query.filter_by(assigned_coach_id=coach.id)
        if date_from:
            students_q = students_q.filter(Student.created_at >= date_from)
        if date_to:
            students_q = students_q.filter(Student.created_at <= date_to)
        for student in students_q.all():
            records.append({
                'coach_id': coach.id,
                'name': coach.username,
                'student_id': student.id,
                'student_name': student.full_name,
                'student_count': students_q.count(),
                'enrolled': student.enrollment_date.strftime('%Y-%m-%d') if student.enrollment_date else '--',
                'status': student.status,
            })

    total = len(records)
    start = (page - 1) * per_page
    return records[start:start + per_page], total


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


def get_retention_records(location_id=None, date_from=None, date_to=None, page=1, per_page=25):
    query = Student.query
    if location_id:
        query = query.filter_by(location_id=location_id)
    if date_from:
        query = query.filter(Student.enrollment_date >= date_from)
    if date_to:
        query = query.filter(Student.enrollment_date <= date_to)
    query = query.order_by(Student.enrollment_date.desc())

    total = query.count()
    students = query.limit(per_page).offset((page - 1) * per_page).all()
    records = []
    for s in students:
        records.append({
            'id': s.id,
            'student_name': s.full_name,
            'enrolled_on': s.enrollment_date.strftime('%Y-%m-%d') if s.enrollment_date else '--',
            'status': s.status,
            'location': s.location.name if s.location else '--',
        })
    return records, total


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


def get_community_records(location_id=None, date_from=None, date_to=None, page=1, per_page=25):
    review_q = Review.query
    if location_id:
        review_q = review_q.filter_by(location_id=location_id)
    if date_from:
        review_q = review_q.filter(Review.created_at >= date_from)
    if date_to:
        review_q = review_q.filter(Review.created_at <= date_to)
    review_q = review_q.order_by(Review.created_at.desc())

    dispute_q = Dispute.query
    if date_from:
        dispute_q = dispute_q.filter(Dispute.created_at >= date_from)
    if date_to:
        dispute_q = dispute_q.filter(Dispute.created_at <= date_to)
    dispute_q = dispute_q.order_by(Dispute.created_at.desc())

    records = []
    for r in review_q.all():
        records.append({
            'type': 'review',
            'id': r.id,
            'author': r.author.username if r.author else '--',
            'subject': (r.content[:80] + '...') if len(r.content) > 80 else r.content,
            'status': r.status,
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    for d in dispute_q.all():
        records.append({
            'type': 'dispute',
            'id': d.id,
            'author': d.initiator.username if d.initiator else '--',
            'subject': f'Dispute for review #{d.review_id}',
            'status': d.status,
            'created_at': d.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    records.sort(key=lambda x: x['created_at'], reverse=True)
    total = len(records)
    start = (page - 1) * per_page
    return records[start:start + per_page], total


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


def get_financial_records(location_id=None, date_from=None, date_to=None, page=1, per_page=25):
    query = Transaction.query.filter(Transaction.status.in_(['active', 'closed']))
    if location_id:
        query = query.filter_by(location_id=location_id)
    if date_from:
        query = query.filter(Transaction.created_at >= date_from)
    if date_to:
        query = query.filter(Transaction.created_at <= date_to)
    query = query.order_by(Transaction.created_at.desc())

    total = query.count()
    transactions = query.limit(per_page).offset((page - 1) * per_page).all()
    records = []
    for t in transactions:
        records.append({
            'id': t.id,
            'date': t.created_at.strftime('%Y-%m-%d'),
            'payee': t.payee,
            'description': t.description or '--',
            'category': t.category or '--',
            'income': t.amount if t.type == 'income' else None,
            'expense': t.amount if t.type == 'expense' else None,
            'status': t.status,
        })
    return records, total


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
