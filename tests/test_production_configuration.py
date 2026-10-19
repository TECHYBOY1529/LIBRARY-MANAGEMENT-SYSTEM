import pytest

from library_app import create_app
from library_app.extensions import db


def test_production_refuses_placeholder_secret():
    with pytest.raises(RuntimeError, match="Production requires SECRET_KEY"):
        create_app({
            "TESTING": True,
            "APP_ENV": "production",
            "SECRET_KEY": "replace-with-a-long-random-value",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        })


def test_production_uses_secure_cookie_and_health_headers():
    app = create_app({
        "TESTING": True,
        "APP_ENV": "production",
        "SECRET_KEY": "s" * 64,
        "SESSION_COOKIE_SECURE": True,
        "RATELIMIT_STORAGE_URI": "redis://localhost:6379/0",
        "PUBLIC_BASE_URL": "https://library.example.edu",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })
    with app.app_context():
        db.create_all()
    response = app.test_client().get("/healthz")
    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(("setting", "value", "message"), [
    ("SESSION_COOKIE_SECURE", False, "SESSION_COOKIE_SECURE=true"),
    ("RATELIMIT_STORAGE_URI", "memory://", "shared rate-limit storage"),
    ("PUBLIC_BASE_URL", "http://library.example.edu", "public HTTPS origin"),
    ("PUBLIC_BASE_URL", "https://localhost", "public HTTPS origin"),
    ("PUBLIC_BASE_URL", "https://library.example.edu/app", "public HTTPS origin"),
])
def test_production_rejects_unsafe_runtime_configuration(setting, value, message):
    config = {
        "TESTING": True,
        "APP_ENV": "production",
        "SECRET_KEY": "s" * 64,
        "SESSION_COOKIE_SECURE": True,
        "RATELIMIT_STORAGE_URI": "redis://localhost:6379/0",
        "PUBLIC_BASE_URL": "https://library.example.edu",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    }
    config[setting] = value
    with pytest.raises(RuntimeError, match=message):
        create_app(config)


def test_railway_postgres_url_uses_psycopg_without_sqlite_options(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://library:example@db.example.test/library")
    app = create_app({
        "TESTING": True, "SECRET_KEY": "test-only-secret-key",
        "APP_ENV": "development",
    })
    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql+psycopg://")
    assert app.config["SQLALCHEMY_ENGINE_OPTIONS"] == {"pool_pre_ping": True}
    with app.app_context():
        assert db.engine.url.drivername == "postgresql+psycopg"
