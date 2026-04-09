import re
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.user import User
from app.services.audit_service import log_event


def validate_password(password):
    errors = []
    min_len = current_app.config['PASSWORD_MIN_LENGTH']
    if len(password) < min_len:
        errors.append(f'Password must be at least {min_len} characters.')
    if not re.search(r'\d', password):
        errors.append('Password must contain at least one number.')
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;\'`~]', password):
        errors.append('Password must contain at least one symbol.')
    return errors


def attempt_login(username, password, ip_address=None):
    user = User.query.filter_by(username=username).first()

    if not user:
        return None, 'Invalid username or password.'

    if not user.is_active:
        return None, 'Account is disabled. Contact an administrator.'

    if user.is_locked:
        locked = user.locked_until
        if locked.tzinfo is None:
            locked = locked.replace(tzinfo=timezone.utc)
        remaining = (locked - datetime.now(timezone.utc)).total_seconds()
        mins = max(1, int(remaining // 60))
        return None, f'Account is locked. Try again in {mins} minute(s).'

    if not user.check_password(password):
        user.failed_login_attempts += 1
        max_attempts = current_app.config['LOGIN_LOCKOUT_ATTEMPTS']
        if user.failed_login_attempts > max_attempts:
            lockout_mins = current_app.config['LOGIN_LOCKOUT_MINUTES']
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_mins)
            log_event('login_locked', user_id=user.id, ip_address=ip_address,
                      detail={'attempts': user.failed_login_attempts})
        db.session.commit()
        remaining = max_attempts - user.failed_login_attempts
        if remaining > 0:
            return None, f'Invalid password. {remaining} attempt(s) remaining.'
        return None, 'Account locked due to too many failed attempts.'

    user.failed_login_attempts = 0
    user.locked_until = None
    db.session.commit()

    log_event('login_success', user_id=user.id, ip_address=ip_address)
    return user, None
