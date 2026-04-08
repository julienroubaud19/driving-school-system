from flask import request


def is_htmx_request():
    return request.headers.get('HX-Request') == 'true'


def paginate_query(query, page=None, per_page=20):
    if page is None:
        page = request.args.get('page', 1, type=int)
    return query.paginate(page=page, per_page=per_page, error_out=False)


def parse_date_range():
    from datetime import datetime
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d')
        except ValueError:
            date_from = None
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d')
        except ValueError:
            date_to = None
    return date_from, date_to
