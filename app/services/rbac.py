from functools import wraps

from flask import abort
from flask_login import current_user


def has_permission(codename):
    if not current_user.is_authenticated:
        return False
    return current_user.has_permission(codename)


def permission_required(codename):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_permission(codename):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def role_required(*role_names):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role.name not in role_names:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator
