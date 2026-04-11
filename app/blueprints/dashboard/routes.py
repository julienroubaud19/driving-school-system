import json

from flask import render_template, request, send_from_directory, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user

from app.blueprints.dashboard import bp
from app.extensions import db
from app.models.location import Location
from app.models.user import User, Role
from app.models.audit import ReportSchedule
from app.services.rbac import permission_required
from app.services.report_service import (
    get_approval_turnaround, get_coach_utilization,
    get_retention_rate, get_community_activity,
    get_financial_summary, export_report,
    get_approval_turnaround_records, get_coach_utilization_records,
    get_retention_records, get_community_records,
    get_financial_records,
)
from app.services.scheduler_service import create_schedule, run_due_schedules
from app.utils.helpers import is_htmx_request, parse_date_range


@bp.route('/')
@login_required
@permission_required('report.view')
def index():
    locations = Location.query.filter_by(is_active=True).all()
    location_id = request.args.get('location_id', type=int)
    coach_id = request.args.get('coach_id', type=int)
    category = request.args.get('category', '').strip()
    date_from, date_to = parse_date_range()

    kw = dict(location_id=location_id, date_from=date_from, date_to=date_to)

    turnaround = get_approval_turnaround(**kw)
    utilization = get_coach_utilization(**kw)
    retention = get_retention_rate(**kw)
    community = get_community_activity(**kw)
    financial = get_financial_summary(**kw)

    coach_role = Role.query.filter_by(name='Coach').first()
    coaches = []
    if coach_role:
        coaches = User.query.filter_by(role_id=coach_role.id, is_active=True).all()

    from app.models.financial import Transaction
    categories_q = db.session.query(Transaction.category).filter(
        Transaction.category.isnot(None), Transaction.category != ''
    ).distinct().all()
    categories = sorted(set(c[0] for c in categories_q if c[0]))

    if is_htmx_request():
        return render_template('dashboard/partials/_kpi_tiles.html',
                               turnaround=turnaround, utilization=utilization,
                               retention=retention, community=community,
                               financial=financial)

    return render_template('dashboard/index.html',
                           locations=locations, coaches=coaches,
                           categories=categories,
                           turnaround=turnaround, utilization=utilization,
                           retention=retention, community=community,
                           financial=financial)


@bp.route('/drilldown/<string:kpi>')
@login_required
@permission_required('report.view')
def drilldown(kpi):
    location_id = request.args.get('location_id', type=int)
    coach_id = request.args.get('coach_id', type=int)
    category = request.args.get('category', '').strip()
    date_from, date_to = parse_date_range()
    page = request.args.get('page', 1, type=int)

    kw = dict(location_id=location_id, date_from=date_from, date_to=date_to)
    page_kw = dict(**kw, page=page, per_page=25)

    record_funcs = {
        'turnaround': get_approval_turnaround_records,
        'utilization': get_coach_utilization_records,
        'retention': get_retention_records,
        'community': get_community_records,
        'financial': get_financial_records,
    }

    func = record_funcs.get(kpi)
    if func:
        data, total = func(**page_kw)
    else:
        data, total = [], 0

    if is_htmx_request():
        return render_template('dashboard/partials/_drilldown.html',
                               kpi=kpi, data=data, total=total, page=page)

    return render_template('dashboard/drilldown.html',
                           kpi=kpi, data=data, total=total, page=page)


@bp.route('/export/<string:report_name>', methods=['POST'])
@login_required
@permission_required('report.export')
def export(report_name):
    location_id = request.form.get('location_id', type=int)
    date_from, date_to = parse_date_range()
    kw = dict(location_id=location_id, date_from=date_from, date_to=date_to)
    fmt = request.form.get('format', 'csv')

    report_funcs = {
        'turnaround': get_approval_turnaround,
        'utilization': get_coach_utilization,
        'retention': get_retention_rate,
        'community': get_community_activity,
        'financial': get_financial_summary,
    }

    func = report_funcs.get(report_name)
    if not func:
        flash('Unknown report.', 'danger')
        return redirect(url_for('dashboard.index'))

    data = func(**kw)
    if not isinstance(data, list):
        data = [data]

    filename, filepath = export_report(data, report_name, fmt)
    flash(f'Report exported: {filename}', 'success')

    from flask import current_app
    import os
    return send_from_directory(
        os.path.join(current_app.config['UPLOAD_FOLDER'], 'exports'),
        filename, as_attachment=True,
    )


@bp.route('/schedules')
@login_required
@permission_required('report.export')
def schedules():
    all_schedules = ReportSchedule.query.order_by(ReportSchedule.created_at.desc()).all()
    locations = Location.query.filter_by(is_active=True).all()
    return render_template('dashboard/schedules.html',
                           schedules=all_schedules, locations=locations)


@bp.route('/schedules/new', methods=['POST'])
@login_required
@permission_required('report.export')
def create_report_schedule():
    report_name = request.form.get('report_name', '').strip()
    frequency = request.form.get('frequency', '').strip()
    location_id = request.form.get('location_id', type=int)
    fmt = request.form.get('format', 'csv')

    valid_reports = ['turnaround', 'utilization', 'retention', 'community', 'financial']
    valid_frequencies = ['daily', 'weekly', 'monthly']

    if report_name not in valid_reports:
        flash('Invalid report name.', 'danger')
        return redirect(url_for('dashboard.schedules'))

    if frequency not in valid_frequencies:
        flash('Invalid frequency. Choose daily, weekly, or monthly.', 'danger')
        return redirect(url_for('dashboard.schedules'))

    schedule = create_schedule(report_name, frequency, location_id, fmt, current_user.id)
    flash(f'Report schedule created: {report_name} ({frequency}).', 'success')
    return redirect(url_for('dashboard.schedules'))


@bp.route('/schedules/<int:schedule_id>/toggle', methods=['POST'])
@login_required
@permission_required('report.export')
def toggle_schedule(schedule_id):
    schedule = db.session.get(ReportSchedule, schedule_id)
    if schedule:
        schedule.is_active = not schedule.is_active
        db.session.commit()
        status = 'activated' if schedule.is_active else 'deactivated'
        flash(f'Schedule {status}.', 'success')
    return redirect(url_for('dashboard.schedules'))


@bp.route('/schedules/run', methods=['POST'])
@login_required
@permission_required('report.export')
def run_schedules():
    results = run_due_schedules()
    flash(f'{len(results)} scheduled report(s) executed.', 'success')
    return redirect(url_for('dashboard.schedules'))
