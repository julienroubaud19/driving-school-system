from datetime import datetime, timezone

from urllib.parse import urlparse

from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from app.blueprints.auth import bp
from app.blueprints.auth.forms import LoginForm, ChangePasswordForm
from app.extensions import db
from app.services.auth_service import attempt_login, validate_password
from app.services.audit_service import log_event


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user, error = attempt_login(
            form.username.data, form.password.data,
            ip_address=request.remote_addr,
        )
        if user:
            login_user(user)
            session['last_active'] = datetime.now(timezone.utc).isoformat()
            next_page = request.args.get('next')
            if next_page:
                parsed = urlparse(next_page)
                if parsed.netloc or parsed.scheme:
                    next_page = None
            return redirect(next_page or url_for('dashboard.index'))
        flash(error, 'danger')

    return render_template('auth/login.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    log_event('logout', user_id=current_user.id, ip_address=request.remote_addr)
    logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return render_template('auth/change_password.html', form=form)

        if form.new_password.data != form.confirm_password.data:
            flash('New passwords do not match.', 'danger')
            return render_template('auth/change_password.html', form=form)

        errors = validate_password(form.new_password.data)
        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('auth/change_password.html', form=form)

        current_user.set_password(form.new_password.data)
        current_user.force_password_reset = False
        db.session.commit()

        log_event('password_changed', user_id=current_user.id, ip_address=request.remote_addr)
        flash('Password changed successfully.', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('auth/change_password.html', form=form)
