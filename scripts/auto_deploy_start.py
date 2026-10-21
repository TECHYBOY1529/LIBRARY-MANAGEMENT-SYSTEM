"""
Automatic deployment startup script for Railway / Render / PaaS.
- Ensures environment defaults are safely populated.
- Runs database table creation (db.create_all).
- Automatically seeds the demo admin user if the database is empty.
- Launches Gunicorn bound to the assigned port.
"""
import os
import secrets
import subprocess
import sys


def prepare_environment():
    """Ensure essential runtime environment variables exist to prevent boot crashes."""
    railway_domain = (
        os.getenv("RAILWAY_PUBLIC_DOMAIN")
        or os.getenv("RAILWAY_STATIC_URL")
        or os.getenv("RENDER_EXTERNAL_HOSTNAME")
    )
    if not os.getenv("PUBLIC_BASE_URL"):
        if railway_domain:
            os.environ["PUBLIC_BASE_URL"] = f"https://{railway_domain}"
        else:
            os.environ["PUBLIC_BASE_URL"] = "https://campus-library-production.up.railway.app"
            print("[AUTO-DEPLOY] Note: Set temporary fallback PUBLIC_BASE_URL. Configure PUBLIC_BASE_URL or generate a Railway domain.")

    if not os.getenv("SECRET_KEY"):
        os.environ["SECRET_KEY"] = secrets.token_hex(32)
        print("[AUTO-DEPLOY] Note: Generated fallback SECRET_KEY for this deployment.")

    if "TRUST_PROXY" not in os.environ:
        os.environ["TRUST_PROXY"] = "true"

    has_redis = bool(
        os.getenv("RATELIMIT_STORAGE_URI")
        or os.getenv("REDIS_URL")
        or os.getenv("REDIS_PRIVATE_URL")
    )
    if not has_redis and os.getenv("APP_ENV") == "production":
        print("[AUTO-DEPLOY] Warning: Redis is not detected. Setting APP_ENV=staging so deployment boots smoothly.")
        print("[AUTO-DEPLOY] Tip: In Railway dashboard, click '+ New -> Database -> Redis' to enable shared production rate limiting.")
        os.environ["APP_ENV"] = "staging"


def bootstrap_database():
    """Initialize tables and create default administrator if database is empty."""
    try:
        from library_app import create_app
        from library_app.extensions import db
        from library_app.models import User
        from library_app.seed import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, seed_demo

        app = create_app()
        with app.app_context():
            print("[AUTO-DEPLOY] Ensuring database schema exists...")
            db.create_all()

            admin = User.query.filter_by(role="admin").first()
            if not admin:
                print(f"[AUTO-DEPLOY] No admin found. Bootstrapping catalog and admin ({DEMO_ADMIN_EMAIL})...")
                try:
                    seed_demo()
                    print("[AUTO-DEPLOY] Database initialized successfully!")
                    print(f"[AUTO-DEPLOY] Admin Login: {DEMO_ADMIN_EMAIL}")
                    print(f"[AUTO-DEPLOY] Admin Password: {DEMO_ADMIN_PASSWORD}")
                except Exception as seed_err:
                    print(f"[AUTO-DEPLOY] Note: Seed warning: {seed_err}")
            else:
                print(f"[AUTO-DEPLOY] Database ready with existing admin: {admin.email}")
    except Exception as exc:
        print(f"[AUTO-DEPLOY] Database initialization notice: {exc}", file=sys.stderr)


def start_server():
    """Launch production WSGI server (Gunicorn)."""
    port = os.getenv("PORT", "5000")
    workers = os.getenv("WEB_CONCURRENCY", "2")
    print(f"[AUTO-DEPLOY] Launching Gunicorn on 0.0.0.0:{port} with {workers} workers...")

    cmd = [
        sys.executable,
        "-m",
        "gunicorn",
        "run:app",
        "--bind",
        f"0.0.0.0:{port}",
        "--workers",
        str(workers),
        "--timeout",
        "120",
        "--access-logfile",
        "-",
        "--error-logfile",
        "-",
    ]

    if hasattr(os, "execvp") and sys.platform != "win32":
        os.execvp(cmd[0], cmd)
    else:
        sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    prepare_environment()
    bootstrap_database()
    start_server()
