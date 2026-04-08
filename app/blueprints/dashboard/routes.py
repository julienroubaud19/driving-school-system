import json

from flask import render_template, request, send_from_directory, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user

from app.blueprints.dashboard import bp
from app.models.location import Location
from app.models.user import User, Role
from app.services.rbac import permission_required
from app.services.report_service import (
    get_approval_turnaround, get_coach_utilization,
    get_retention_rate, get_community_activity,
    get_financial_summary, export_report,
)
from app.utils.helpers import is_htmx_request, parse_date_range


@bp.route('/')
@login_required
def index():
    locations = Location.query.filter_by(is_active=True).all()
    location_id = request.args.get('location_id', type=int)
    date_from, date_to = parse_date_range()

    kw = dict(location_id=location_id, date_from=date_from, date_to=date_to)

    turnaround = get_approval_turnaround(**kw)
    utilization = get_coach_utilization(**kw)
    retention = get_retention_rate(**kw)
    community = get_community_activity(**kw)
    financial = get_financial_summary(**kw)

    if is_htmx_request():
        return render_template('dashboard/partials/_kpi_tiles.html',
                               turnaround=turnaround, utilization=utilization,
                               retention=retention, community=community,
                               financial=financial)

    return render_template('dashboard/index.html',
                           locations=locations,
                           turnaround=turnaround, utilization=utilization,
                           retention=retention, community=community,
                           financial=financial)


@bp.route('/drilldown/<string:kpi>')
@login_required
def drilldown(kpi):
    location_id = request.args.get('location_id', type=int)
    date_from, date_to = parse_date_range()
    kw = dict(location_id=location_id, date_from=date_from, date_to=date_to)

    if kpi == 'turnaround':
        data = get_approval_turnaround(**kw)
    elif kpi == 'utilization':
        data = get_coach_utilization(**kw)
    elif kpi == 'retention':
        data = get_retention_rate(**kw)
    elif kpi == 'community':
        data = get_community_activity(**kw)
    elif kpi == 'financial':
        data = get_financial_summary(**kw)
    else:
        data = {}

    if is_htmx_request():
        return render_template('dashboard/partials/_drilldown.html', kpi=kpi, data=data)

    return render_template('dashboard/drilldown.html', kpi=kpi, data=data)


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
