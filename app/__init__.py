import os
from datetime import datetime, timezone

from flask import Flask, redirect, url_for, request, session
from flask_login import current_user

from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    for sub in ('receipts', 'review_images', 'evidence', 'exports'):
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], sub), exist_ok=True)

    from app.extensions import db, login_manager, csrf
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.before_request
    def check_session_timeout():
        if current_user.is_authenticated:
            last_active = session.get('last_active')
            if last_active:
                last_dt = datetime.fromisoformat(last_active)
                diff = (datetime.now(timezone.utc) - last_dt).total_seconds()
                if diff > app.config['SESSION_TIMEOUT_MINUTES'] * 60:
                    from flask_login import logout_user
                    logout_user()
                    session.clear()
                    from flask import flash
                    flash('Session expired due to inactivity.', 'warning')
                    return redirect(url_for('auth.login'))
            session['last_active'] = datetime.now(timezone.utc).isoformat()

    @app.before_request
    def check_force_password_reset():
        if current_user.is_authenticated and current_user.force_password_reset:
            allowed = {'auth.change_password', 'auth.logout', 'static'}
            if request.endpoint and request.endpoint not in allowed:
                from flask import flash
                flash('You must change your password before continuing.', 'warning')
                return redirect(url_for('auth.change_password'))

    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.students import bp as students_bp
    from app.blueprints.financial import bp as financial_bp
    from app.blueprints.notifications import bp as notifications_bp
    from app.blueprints.reviews import bp as reviews_bp
    from app.blueprints.moderation import bp as moderation_bp
    from app.blueprints.dashboard import bp as dashboard_bp
    from app.blueprints.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(students_bp, url_prefix='/students')
    app.register_blueprint(financial_bp, url_prefix='/financial')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    app.register_blueprint(reviews_bp, url_prefix='/reviews')
    app.register_blueprint(moderation_bp, url_prefix='/moderation')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))

    @app.context_processor
    def inject_globals():
        from app.services.rbac import has_permission
        unread_count = 0
        if current_user.is_authenticated:
            from app.models.notification import Notification
            unread_count = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
        return dict(
            has_permission=has_permission,
            unread_count=unread_count,
            now=datetime.now(timezone.utc),
        )

    with app.app_context():
        db.create_all()

    return app
