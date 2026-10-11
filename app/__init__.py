"""
Application Factory
-------------------
Creates and configures the Flask app, registers blueprints,
initialises extensions, and wires up the APScheduler daily digest job.
"""

import logging
from flask import Flask, redirect, url_for
from flask_login import current_user

from app.extensions import db, login_manager, scheduler
from app.config import Config


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # ── Extensions ────────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in with your Google account."
    login_manager.login_message_category = "info"

    # ── User loader for Flask-Login ───────────────────────────────────────
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Required by Flask-Login
    User.__mro__  # ensure UserMixin is mixed in (done in model via flask_login)

    # ── OAuth ─────────────────────────────────────────────────────────────
    from app.routes.auth import init_oauth
    init_oauth(app)

    # ── Blueprints ────────────────────────────────────────────────────────
    from app.routes.auth import auth_bp
    from app.routes.groups import groups_bp
    from app.routes.queries import queries_bp
    from app.routes.replies import replies_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(queries_bp)
    app.register_blueprint(replies_bp)

    # Root redirect
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("groups.dashboard"))
        return redirect(url_for("auth.login"))

    # ── Database ──────────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()
        _setup_scheduler(app)

    return app


def _setup_scheduler(app: Flask):
    """Register and start the APScheduler daily digest job."""
    if scheduler.running:
        return

    scheduler.init_app(app)

    @scheduler.task("cron", id="daily_digest", hour=7, minute=0, timezone="UTC")
    def daily_digest_job():
        """Sends daily digest emails every day at 07:00 UTC."""
        with app.app_context():
            from app.services.email_service import EmailService
            logging.getLogger(__name__).info("Running daily digest job…")
            EmailService.send_daily_digest()

    scheduler.start()
    logging.getLogger(__name__).info("APScheduler started – daily digest at 07:00 UTC.")
