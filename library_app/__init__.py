import os
import secrets
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import click
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_wtf.csrf import CSRFError, CSRFProtect
from sqlalchemy import event, text
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter.errors import RateLimitExceeded

from .extensions import db, limiter, login_manager, migrate

csrf = CSRFProtect()


def _static_asset_version(static_folder, filename):
    """Return a per-file cache key so a running app serves the latest assets."""
    try:
        return format((Path(static_folder) / filename).stat().st_mtime_ns, "x")
    except OSError:
        return "0"


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    runtime_environment = os.getenv("APP_ENV", "development").strip().lower()
    database_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("MYSQL_PRIVATE_URL")
        or os.getenv("MYSQL_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("POSTGRESQL_URL")
        or ""
    ).strip()

    if not database_url:
        pghost = os.getenv("PGHOST")
        pguser = os.getenv("PGUSER")
        pgpassword = os.getenv("PGPASSWORD")
        pgdatabase = os.getenv("PGDATABASE", "railway")
        pgport = os.getenv("PGPORT", "5432")
        if pghost and pguser and pgpassword:
            database_url = f"postgresql+psycopg://{pguser}:{pgpassword}@{pghost}:{pgport}/{pgdatabase}"

    if not database_url or database_url == "sqlite:///library.db":
        instance_db = Path(app.instance_path) / "library.db"
        try:
            instance_db.parent.mkdir(parents=True, exist_ok=True)
            test_file = instance_db.parent / ".test_write"
            with open(test_file, "w") as tf:
                tf.write("ok")
            os.remove(test_file)
            database_url = f"sqlite:///{instance_db.resolve().as_posix()}"
        except OSError:
            tmp_db = Path("/tmp") / "library.db"
            tmp_db.parent.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{tmp_db.resolve().as_posix()}"

    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    elif database_url.startswith("mysql://"):
        database_url = "mysql+pymysql://" + database_url.removeprefix("mysql://")
    engine_options = {"pool_pre_ping": True}
    if database_url.startswith("sqlite:"):
        engine_options["connect_args"] = {"check_same_thread": False, "timeout": 30}

    public_base = os.getenv("PUBLIC_BASE_URL")
    if not public_base:
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RAILWAY_STATIC_URL") or os.getenv("RENDER_EXTERNAL_HOSTNAME")
        if railway_domain:
            public_base = f"https://{railway_domain}"
        else:
            public_base = "http://localhost:5000"
    public_base = public_base.rstrip("/")

    ratelimit_uri = (
        os.getenv("RATELIMIT_STORAGE_URI")
        or os.getenv("REDIS_URL")
        or os.getenv("REDIS_PRIVATE_URL")
        or "memory://"
    ).strip()
    app.config.from_mapping(
        APP_ENV=runtime_environment,
        SECRET_KEY=os.getenv("SECRET_KEY") or (None if runtime_environment == "production" else secrets.token_hex(32)),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS=engine_options,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "true" if runtime_environment == "production" else "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
        WTF_CSRF_TIME_LIMIT=3600,
        DEFAULT_LOAN_DAYS=int(os.getenv("DEFAULT_LOAN_DAYS", "14")),
        MAX_ACTIVE_LOANS_PER_MEMBER=int(os.getenv("MAX_ACTIVE_LOANS_PER_MEMBER", "5")),
        FINE_PER_DAY=float(os.getenv("FINE_PER_DAY", "1.00")),
        DEBUG=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        RATELIMIT_STORAGE_URI=ratelimit_uri,
        TRUST_PROXY=os.getenv("TRUST_PROXY", "false").lower() == "true",
        MAX_CONTENT_LENGTH=2 * 1024 * 1024 + 64 * 1024,
        PUBLIC_BASE_URL=public_base,
        MAIL_SERVER=os.getenv("MAIL_SERVER", ""),
        MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
        MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
        MAIL_SENDER=os.getenv("MAIL_SENDER", ""),
        MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "true").lower() == "true",
        PASSWORD_RESET_TOKEN_MINUTES=int(os.getenv("PASSWORD_RESET_TOKEN_MINUTES", "30")),
        BACKUP_RETENTION_DAYS=int(os.getenv("BACKUP_RETENTION_DAYS", "30")),
        LIBRARY_TIMEZONE=os.getenv("LIBRARY_TIMEZONE", "Asia/Kolkata").strip(),
    )
    if test_config:
        app.config.update(test_config)
    try:
        ZoneInfo(app.config["LIBRARY_TIMEZONE"])
    except (ZoneInfoNotFoundError, TypeError, ValueError) as error:
        raise ValueError("LIBRARY_TIMEZONE must be a valid IANA timezone, such as Asia/Kolkata.") from error
    if app.config["APP_ENV"] == "production":
        secret_key = app.config.get("SECRET_KEY")
        if not secret_key or len(secret_key) < 32 or secret_key.startswith("replace-"):
            raise RuntimeError("Production requires SECRET_KEY to be set to a random value of at least 32 characters.")
        if not app.config["SESSION_COOKIE_SECURE"]:
            raise RuntimeError("Production requires SESSION_COOKIE_SECURE=true so authentication cookies are sent only over HTTPS.")
        rate_limit_storage = urlsplit(app.config["RATELIMIT_STORAGE_URI"])
        if rate_limit_storage.scheme not in {"redis", "rediss"} or not rate_limit_storage.hostname:
            raise RuntimeError("Production requires shared rate-limit storage. Configure Redis with RATELIMIT_STORAGE_URI.")
        public_url = urlsplit(app.config["PUBLIC_BASE_URL"])
        if (public_url.scheme != "https" or not public_url.hostname
                or public_url.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
                or public_url.username or public_url.password or public_url.path not in {"", "/"}
                or public_url.query or public_url.fragment):
            raise RuntimeError("Production requires PUBLIC_BASE_URL to be a public HTTPS origin without credentials, query, or fragment.")
        if app.config["MAIL_SERVER"] and not app.config["MAIL_USE_TLS"]:
            raise RuntimeError("Production SMTP must use STARTTLS; set MAIL_USE_TLS=true.")
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
            app.logger.warning("SQLite production mode requires a persistent mounted volume, regular backups, and one application instance.")
        if not app.config["MAIL_SERVER"] or not app.config["MAIL_SENDER"]:
            app.logger.warning("Password-reset email is not configured; users will need administrator assistance to regain access.")
    if not 1 <= app.config["DEFAULT_LOAN_DAYS"] <= 365:
        raise ValueError("DEFAULT_LOAN_DAYS must be from 1 to 365.")
    if not 1 <= app.config["MAX_ACTIVE_LOANS_PER_MEMBER"] <= 50:
        raise ValueError("MAX_ACTIVE_LOANS_PER_MEMBER must be from 1 to 50.")
    if not math.isfinite(app.config["FINE_PER_DAY"]) or app.config["FINE_PER_DAY"] < 0:
        raise ValueError("FINE_PER_DAY must be a finite, nonnegative amount.")
    if not 5 <= app.config["PASSWORD_RESET_TOKEN_MINUTES"] <= 120:
        raise ValueError("PASSWORD_RESET_TOKEN_MINUTES must be from 5 to 120.")
    if not 1 <= app.config["BACKUP_RETENTION_DAYS"] <= 3650:
        raise ValueError("BACKUP_RETENTION_DAYS must be from 1 to 3650.")

    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    db.init_app(app)
    with app.app_context():
        @event.listens_for(db.engine, "connect")
        def enable_sqlite_foreign_keys(connection, _record):
            if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)

    from . import models  # noqa: F401
    from .auth import bp as auth_bp
    from .catalog import bp as catalog_bp
    from .quality import bp as quality_bp
    from .reports import bp as reports_bp
    from .main import bp as main_bp

    _db_bootstrapped = False

    @app.before_request
    def auto_bootstrap_first_request():
        nonlocal _db_bootstrapped
        if not _db_bootstrapped:
            try:
                db.create_all()
                from .models import User
                from .seed import seed_demo
                if not User.query.filter_by(role="admin").first():
                    seed_demo()
                _db_bootstrapped = True
            except Exception as bootstrap_err:
                app.logger.warning("Bootstrap notice: %s", bootstrap_err)
                _db_bootstrapped = True

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(catalog_bp, url_prefix="/library")
    app.register_blueprint(quality_bp, url_prefix="/quality")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    @app.get("/healthz")
    def health_check():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify(status="ok"), 200
        except Exception:
            db.session.rollback()
            app.logger.exception("Health check could not reach the database")
            return jsonify(status="unavailable"), 503

    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if app.config["APP_ENV"] == "production" and app.config["SESSION_COOKIE_SECURE"]:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.endpoint != "static":
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from .models import Notification
        unread_count = (
            Notification.query.filter_by(user_id=current_user.id, read_at=None).count()
            if current_user.is_authenticated else 0
        )
        return {
            "now_utc": datetime.now(timezone.utc),
            "current_user": current_user,
            "unread_notification_count": unread_count,
            "asset_version": lambda filename: _static_asset_version(app.static_folder, filename),
        }

    app.jinja_env.filters["from_json"] = json.loads
    from .barcode_utils import generate_code39_svg
    app.jinja_env.filters["barcode_svg"] = generate_code39_svg

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template("error.html", code=400, message="Your form expired or could not be verified. Please try again."), 400

    @app.errorhandler(RateLimitExceeded)
    def rate_limit_error(_error):
        return render_template("error.html", code=429, message="Too many attempts. Wait a moment, then try again."), 429

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="The requested page could not be found."), 404

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403, message="Your account does not have permission to access that page."), 403

    @app.errorhandler(413)
    def request_too_large(error):
        return render_template("error.html", code=413,
                               message=getattr(error, "description", "The request is too large. Please narrow the export or use a smaller file.")), 413

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        reference = secrets.token_hex(6)
        try:
            from flask_login import current_user
            from .models import BugIncident
            actor_id = current_user.id if current_user.is_authenticated else None
            incident = BugIncident(title="Unhandled application exception",
                                   description=f"Reference {reference}; endpoint={request.endpoint or 'unknown'}; path={request.path[:180]}",
                                   severity="high", created_by_id=actor_id)
            db.session.add(incident)
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Could not save application error reference %s", reference)
        app.logger.error("Unhandled application error reference %s", reference,
                         exc_info=(type(error), error, error.__traceback__))
        raw_err = str(getattr(error, "original_exception", error))
        user_msg = f"{raw_err} (Reference: {reference})" if raw_err else f"Something went wrong. Reference: {reference}."
        return render_template("error.html", code=500, message=user_msg), 500

    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables from the current model definitions."""
        with app.app_context():
            db.create_all()
        print("Database tables are ready.")

    @app.cli.command("backup-db")
    @click.option("--backup-dir", type=click.Path(file_okay=False, dir_okay=True, path_type=Path), default=None,
                  help="Destination directory. Defaults to instance/backups.")
    def backup_db_command(backup_dir):
        """Create an online-consistent backup of a file-backed SQLite database."""
        import sqlite3
        from datetime import datetime, timezone
        with app.app_context():
            if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
                raise click.ClickException("This command supports file-backed SQLite only. Use your PostgreSQL provider's backup tools.")
            source_name = db.engine.url.database
            if not source_name or source_name == ":memory:":
                raise click.ClickException("No file-backed SQLite database is configured.")
            source = Path(source_name)
            if not source.is_absolute():
                source = Path(app.instance_path) / source
            source = source.resolve()
            if not source.is_file():
                raise click.ClickException(f"Database file was not found: {source}")
            destination_dir = (Path(backup_dir) if backup_dir else Path(app.instance_path) / "backups").resolve()
            if destination_dir == source.parent or source == destination_dir:
                raise click.ClickException("Choose a backup directory separate from the database file.")
            destination_dir.mkdir(parents=True, exist_ok=True)
            if not destination_dir.is_dir():
                raise click.ClickException("Backup destination must be a directory.")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            target_path = destination_dir / f"library-{stamp}.sqlite3"
            try:
                with sqlite3.connect(source) as src, sqlite3.connect(target_path) as dst:
                    src.backup(dst)
                try:
                    target_path.chmod(0o600)
                except OSError:
                    pass
                retention = app.config["BACKUP_RETENTION_DAYS"]
                cutoff = datetime.now(timezone.utc).timestamp() - retention * 86400
                for old in destination_dir.glob("library-*.sqlite3"):
                    if old != target_path and old.stat().st_mtime < cutoff:
                        old.unlink(missing_ok=True)
            except Exception as error:
                target_path.unlink(missing_ok=True)
                if isinstance(error, click.ClickException):
                    raise
                raise click.ClickException(f"Could not create database backup: {error}") from error
            click.echo(f"SQLite backup created: {target_path}")

    @app.cli.command("purge-expired-records")
    def purge_expired_records_command():
        """Remove expired one-use tokens and abandoned catalog import previews."""
        from .services import purge_expired_records
        with app.app_context():
            res = purge_expired_records(source="cli")
        click.echo(f"Removed {res['catalog_import_previews']} expired catalog previews and {res['password_reset_tokens']} expired password-reset tokens.")

    @app.cli.command("catalog-summary")
    def catalog_summary_command():
        """Print an administrative summary of catalog titles, copies, circulation, and fines."""
        from .models import Book, BookCopy, Fine, Loan, Reservation
        from .time_utils import library_today
        with app.app_context():
            total_titles = Book.query.count()
            total_copies = BookCopy.query.count()
            available_copies = BookCopy.query.filter_by(status="available").count()
            loaned_copies = BookCopy.query.filter_by(status="loaned").count()
            active_loans = Loan.query.filter_by(status="active").count()
            overdue_loans = Loan.query.filter(Loan.status == "active", Loan.due_date < library_today()).count()
            pending_holds = Reservation.query.filter_by(status="waiting").count()
            ready_holds = Reservation.query.filter_by(status="ready").count()
            unpaid_fines = db.session.query(db.func.coalesce(db.func.sum(Fine.amount), 0.0)).filter_by(paid=False).scalar()
            click.echo("=== Library Catalog & Circulation Summary ===")
            click.echo(f"Titles: {total_titles} | Total Copies: {total_copies}")
            click.echo(f"Copy Inventory: Available={available_copies}, Loaned={loaned_copies}")
            click.echo(f"Circulation: Active Loans={active_loans}, Overdue={overdue_loans}")
            click.echo(f"Reservations: Waiting={pending_holds}, Ready={ready_holds}")
            click.echo(f"Outstanding Fines: ${float(unpaid_fines):.2f}")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        if app.config["APP_ENV"] == "production":
            raise click.ClickException("Demo accounts are disabled in production. Use the create-user command to provision staff.")
        from .seed import seed_demo
        with app.app_context():
            seed_demo()
        print("Fictional demo data is ready.")

    @app.cli.command("reset-demo")
    def reset_demo_command():
        from .seed import reset_demo
        if app.config["APP_ENV"] == "production":
            raise click.ClickException("Demo database reset is disabled in production.")
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
            user.auth_version = (user.auth_version or 0) + 1
            db.session.commit()
            print("Password updated.")

    @app.cli.command("create-user")
    @click.option("--email", prompt=True, help="Staff account email address.")
    @click.option("--name", "full_name", prompt=True, help="Staff member's full name.")
    @click.option("--role", type=click.Choice(["admin", "quality_manager"], case_sensitive=False), prompt=True)
    @click.password_option(confirmation_prompt=True, help="Password for the new staff account.")
    def create_user_command(email, full_name, role, password):
        """Provision an administrator or quality manager without demo credentials."""
        from .auth import valid_email
        from .models import User
        email = email.strip().lower()
        full_name = full_name.strip()
        role = role.lower()
        if not valid_email(email) or len(email) > 255:
            raise click.ClickException("Enter a valid email address.")
        if not 2 <= len(full_name) <= 120:
            raise click.ClickException("Name must contain 2–120 characters.")
        if not 12 <= len(password) <= 256:
            raise click.ClickException("Password must contain 12–256 characters.")
        with app.app_context():
            if User.query.filter_by(email=email).first():
                raise click.ClickException("An account with that email already exists.")
            user = User(full_name=full_name, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            from .services import audit
            audit(None, "provision_staff_account", "user", user.id, f"role={role}")
            db.session.commit()
        click.echo(f"Created {role.replace('_', ' ')} account for {email}.")

    return app
