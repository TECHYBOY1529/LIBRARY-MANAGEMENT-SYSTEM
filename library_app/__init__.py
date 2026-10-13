import os
import secrets
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import event

from .extensions import db, login_manager

csrf = CSRFProtect()


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///library.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"check_same_thread": False}},
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
        WTF_CSRF_TIME_LIMIT=3600,
        DEFAULT_LOAN_DAYS=int(os.getenv("DEFAULT_LOAN_DAYS", "14")),
        FINE_PER_DAY=float(os.getenv("FINE_PER_DAY", "1.00")),
        DEBUG=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
    if test_config:
        app.config.update(test_config)
    if not 1 <= app.config["DEFAULT_LOAN_DAYS"] <= 365:
        raise ValueError("DEFAULT_LOAN_DAYS must be from 1 to 365.")
    if not math.isfinite(app.config["FINE_PER_DAY"]) or app.config["FINE_PER_DAY"] < 0:
        raise ValueError("FINE_PER_DAY must be a finite, nonnegative amount.")

    db.init_app(app)
    with app.app_context():
        @event.listens_for(db.engine, "connect")
        def enable_sqlite_foreign_keys(connection, _record):
            if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401
    from .auth import bp as auth_bp
    from .catalog import bp as catalog_bp
    from .quality import bp as quality_bp
    from .reports import bp as reports_bp
    from .main import bp as main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(catalog_bp, url_prefix="/library")
    app.register_blueprint(quality_bp, url_prefix="/quality")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        return {"now_utc": datetime.now(timezone.utc), "current_user": current_user}

    app.jinja_env.filters["from_json"] = json.loads

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template("error.html", code=400, message="Your form expired or could not be verified. Please try again."), 400

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="The requested page could not be found."), 404

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="Your account does not have permission to access that page."), 403

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        app.logger.exception("Unhandled application error")
        return render_template("error.html", code=500, message="Something went wrong. Please try again or contact a librarian."), 500

    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables from the current model definitions."""
        with app.app_context():
            db.create_all()
        print("Database tables are ready.")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        from .seed import seed_demo
        with app.app_context():
            seed_demo()
        print("Fictional demo data is ready.")

    @app.cli.command("reset-demo")
    def reset_demo_command():
        from .seed import reset_demo
        with app.app_context():
            reset_demo()
        print("Demo database reset and reseeded.")

    @app.cli.command("send-loan-reminders")
    def send_loan_reminders_command():
        """Create one due-soon or overdue reminder per active loan; safe to rerun."""
        from .services import refresh_loan_notifications
        with app.app_context():
            refresh_loan_notifications()
        print("Due-date and overdue reminders refreshed.")

    @app.cli.command("set-password")
    @click.argument("email")
    def set_password_command(email):
        """Set a user password with a hidden terminal prompt."""
        from getpass import getpass
        from .models import User
        with app.app_context():
            user = User.query.filter_by(email=email.strip().lower()).first()
            if not user:
                print("No user account found for that email.")
                return
            first = getpass("New password (10 characters minimum): ")
            second = getpass("Confirm new password: ")
            if not 10 <= len(first) <= 256 or first != second:
                print("Password not changed. Use 10–256 characters and enter it twice identically.")
                return
            user.set_password(first)
            db.session.commit()
            print("Password updated.")

    return app
