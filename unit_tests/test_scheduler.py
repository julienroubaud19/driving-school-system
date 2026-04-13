"""Tests for the report scheduling service."""

from datetime import datetime, timedelta, timezone

from tests.conftest import login
from app.models.audit import ReportSchedule, ReportExecution
from app.services.scheduler_service import (
    create_schedule, run_due_schedules, execute_scheduled_report, compute_next_run,
)


def test_compute_next_run_daily():
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    next_run = compute_next_run('daily', base)
    assert next_run == base + timedelta(days=1)


def test_compute_next_run_weekly():
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    next_run = compute_next_run('weekly', base)
    assert next_run == base + timedelta(weeks=1)


def test_compute_next_run_monthly():
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    next_run = compute_next_run('monthly', base)
    assert next_run == base + timedelta(days=30)


def test_create_schedule(seed_data, db, app):
    schedule = create_schedule('financial', 'weekly', seed_data['location'].id,
                               'csv', seed_data['admin'].id)
    assert schedule is not None
    assert schedule.report_name == 'financial'
    assert schedule.frequency == 'weekly'
    assert schedule.is_active is True
    assert schedule.next_run_at is not None


def test_execute_scheduled_report(seed_data, db, app):
    schedule = create_schedule('retention', 'daily', None, 'json', seed_data['admin'].id)
    execution = execute_scheduled_report(schedule)
    assert execution is not None
    assert execution.status == 'success'
    assert execution.file_path is not None


def test_execute_unknown_report(seed_data, db, app):
    schedule = ReportSchedule(
        report_name='nonexistent', frequency='daily',
        format='csv', created_by=seed_data['admin'].id, is_active=True,
        next_run_at=datetime.now(timezone.utc),
    )
    db.session.add(schedule)
    db.session.commit()

    execution = execute_scheduled_report(schedule)
    assert execution.status == 'failed'
    assert 'Unknown report' in execution.error_message


def test_run_due_schedules_executes_overdue(seed_data, db, app):
    # Create a schedule that's overdue
    schedule = ReportSchedule(
        report_name='financial', frequency='daily',
        format='csv', created_by=seed_data['admin'].id, is_active=True,
        next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.session.add(schedule)
    db.session.commit()

    results = run_due_schedules()
    assert len(results) == 1
    assert results[0].status == 'success'

    db.session.refresh(schedule)
    assert schedule.last_run_at is not None
    # SQLite returns naive datetimes; compare accordingly
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    next_run = schedule.next_run_at
    if next_run.tzinfo is not None:
        next_run = next_run.replace(tzinfo=None)
    assert next_run > now_naive


def test_run_due_schedules_skips_inactive(seed_data, db, app):
    schedule = ReportSchedule(
        report_name='financial', frequency='daily',
        format='csv', created_by=seed_data['admin'].id, is_active=False,
        next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.session.add(schedule)
    db.session.commit()

    results = run_due_schedules()
    assert len(results) == 0


def test_run_due_schedules_skips_future(seed_data, db, app):
    schedule = ReportSchedule(
        report_name='financial', frequency='daily',
        format='csv', created_by=seed_data['admin'].id, is_active=True,
        next_run_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.session.add(schedule)
    db.session.commit()

    results = run_due_schedules()
    assert len(results) == 0
