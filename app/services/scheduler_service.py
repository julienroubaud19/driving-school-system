from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.audit import ReportSchedule, ReportExecution
from app.services.report_service import (
    get_approval_turnaround, get_coach_utilization,
    get_retention_rate, get_community_activity,
    get_financial_summary, export_report,
)
from app.services.audit_service import log_event

REPORT_FUNCS = {
    'turnaround': get_approval_turnaround,
    'utilization': get_coach_utilization,
    'retention': get_retention_rate,
    'community': get_community_activity,
    'financial': get_financial_summary,
}

FREQUENCY_DELTAS = {
    'daily': timedelta(days=1),
    'weekly': timedelta(weeks=1),
    'monthly': timedelta(days=30),
}


def compute_next_run(frequency, from_time=None):
    base = from_time or datetime.now(timezone.utc)
    delta = FREQUENCY_DELTAS.get(frequency, timedelta(days=1))
    return base + delta


def create_schedule(report_name, frequency, location_id, fmt, user_id):
    schedule = ReportSchedule(
        report_name=report_name,
        frequency=frequency,
        location_id=location_id or None,
        format=fmt,
        created_by=user_id,
        next_run_at=compute_next_run(frequency),
    )
    db.session.add(schedule)
    db.session.commit()

    log_event('report_schedule_created', user_id=user_id,
              resource_type='report_schedule', resource_id=schedule.id,
              detail={'report_name': report_name, 'frequency': frequency})
    return schedule


def run_due_schedules():
    now = datetime.now(timezone.utc)
    due = ReportSchedule.query.filter(
        ReportSchedule.is_active == True,
        ReportSchedule.next_run_at <= now,
    ).all()

    results = []
    for schedule in due:
        result = execute_scheduled_report(schedule)
        results.append(result)
    return results


def execute_scheduled_report(schedule):
    func = REPORT_FUNCS.get(schedule.report_name)
    if not func:
        execution = ReportExecution(
            schedule_id=schedule.id,
            status='failed',
            error_message=f'Unknown report: {schedule.report_name}',
        )
        db.session.add(execution)
        db.session.commit()
        return execution

    try:
        kw = dict(location_id=schedule.location_id)
        data = func(**kw)
        if not isinstance(data, list):
            data = [data]

        filename, filepath = export_report(data, f'scheduled_{schedule.report_name}', schedule.format)

        execution = ReportExecution(
            schedule_id=schedule.id,
            file_path=filepath,
            status='success',
        )
        db.session.add(execution)

        schedule.last_run_at = datetime.now(timezone.utc)
        schedule.next_run_at = compute_next_run(schedule.frequency, schedule.last_run_at)
        db.session.commit()

        log_event('scheduled_report_executed', user_id=schedule.created_by,
                  resource_type='report_schedule', resource_id=schedule.id,
                  detail={'filename': filename})
        return execution

    except Exception as e:
        execution = ReportExecution(
            schedule_id=schedule.id,
            status='failed',
            error_message=str(e),
        )
        db.session.add(execution)

        schedule.last_run_at = datetime.now(timezone.utc)
        schedule.next_run_at = compute_next_run(schedule.frequency, schedule.last_run_at)
        db.session.commit()
        return execution
