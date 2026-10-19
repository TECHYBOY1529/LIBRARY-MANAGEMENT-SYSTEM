# Campus Library Management System with TQM

A modular library management web application for a college or university academic project. It combines copy-level inventory and circulation with member feedback, complaint handling, root-cause analysis, corrective actions, PDCA cycles, operational reports, and a data-backed quality dashboard.

> **Demo data:** the seed script creates explicitly fictional accounts, books, loans, feedback, and complaints. It contains no real library-member data. The demo accounts and fallback development secret are for local use only.

## Features

- **Three roles:** Admin/Librarian, Member/Student, and Quality Manager, with backend route authorization and role-specific navigation.
- **Catalog and inventory:** manage books, authors, subjects, courses, semesters, publishers, ISBNs, years, and individually barcoded copies. Search by title, author, ISBN, subject, course, publisher, semester, and availability; sort and paginate results; validate and preview CSV imports before commit.
- **Circulation:** issue/return procedures, due dates, overdue tracking, configurable fines, reservations and FIFO waitlists, member history, and in-app notifications.
- **Member services:** self-registration, secure login/logout, own loans and fines, 1–5 categorized feedback, complaint status tracking, and notifications.
- **TQM workflows:** complaint categorization, Pareto analysis, satisfaction trends, six-dimension Fishbone/Ishikawa and 5 Whys records, assigned improvement actions, physical inventory audits, and stage-gated PDCA cycles.
- **Quality analytics:** database-backed KPIs, borrowing and satisfaction charts, problem-category counts, and PDCA status/outcomes. A KPI shows **Insufficient data** when it has no usable sample.
- **Reports:** date-filtered inventory, borrowing/returns, overdue loans, fines, member activity, quality KPI, Pareto, and trend reports in CSV, Excel, and printable PDF.
- **Usability and accessibility:** responsive, photo-led academic library UI with local book photography, role-specific dashboards, personal light/dark themes, high contrast, adjustable text size, keyboard navigation/search shortcuts, confirmation dialogs, due-date calendar, Help/FAQ, and About page.
- **Security and reliability:** Werkzeug password hashing, one-use expiring password-reset links (SMTP configuration required), session security, CSRF protection, server-side validation, role checks, foreign-key enforcement, audit history, incident tracking, transaction rollback, SQLite backup command, and pytest coverage.
- **Production foundations:** fail-closed production secret checks, secure session cookies, request throttling for login/registration, response security headers, `/healthz`, SQLAlchemy migrations, PostgreSQL support, and Gunicorn deployment.
- **Account settings:** members and staff can update their profile and change passwords after verifying the current password.

See [TQM implementation and KPI formulas](docs/TQM_IMPLEMENTATION.md), [database schema](docs/DATABASE_SCHEMA.md), and [system architecture](docs/ARCHITECTURE.md).

## Technology stack

- Frontend: HTML5, CSS3, JavaScript, Bootstrap 5, Chart.js
- Backend: Python 3.10+, Flask, Flask-Login, Flask-WTF, Flask-Limiter
- Database: SQLite for local/demo use; PostgreSQL supported for hosted use through Flask-SQLAlchemy / SQLAlchemy
- Password hashing: Werkzeug secure password hash utilities
- Deployment and migrations: Gunicorn, Flask-Migrate / Alembic
- Tests: pytest

Bootstrap and Chart.js load from CDNs in a browser; an internet connection is needed for those visual assets. The interface uses system fonts.

## Installation and setup (Windows PowerShell)

```powershell
cd "D:\LIBRARY MANAGEMENT SYSTEM"
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and replace `SECRET_KEY` with a long random value before using the app beyond a local demo. For example, generate one in a terminal with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

The `.env` file and local database are excluded by `.gitignore`. Do not commit secrets or real member data. The development defaults are not production settings.

To enable password-reset emails, set `PUBLIC_BASE_URL` to the app's public HTTPS origin and configure `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_SENDER`, and `MAIL_USE_TLS`. Without SMTP, the app shows the same generic response but does not expose reset tokens or send links. Use the administrator `set-password` command instead.

## Database setup and demo accounts

Initialize an empty database:

```powershell
python -m flask --app run.py init-db
```

For an existing database, apply schema updates without dropping records:

```powershell
python -m flask --app run.py db upgrade
```

Seed clearly labeled fictional records (safe to rerun on a database that already has the demo admin):

```powershell
python -m flask --app run.py seed-demo
```

Or reset and recreate the local demo database:

```powershell
python -m flask --app run.py reset-demo
```

**`reset-demo` is destructive:** it drops every table in the configured database and re-seeds it. Use it only with the local demo database, never with data you need to keep. Standalone equivalents are in `scripts/`.

Local demo sign-ins after seeding:

| Role | Email | Initial local demo password |
|---|---|---|
| Admin/Librarian | `admin@library.demo` | `LibraryDemo!2026` |
| Quality Manager | `quality@library.demo` | `QualityDemo!2026` |
| Member/Student | `student01@library.demo` through `student12@library.demo` | `StudentDemo!2026` |

Change a demo password using the hidden terminal prompt:

```powershell
python -m flask --app run.py set-password admin@library.demo
```

The seed password is **only a local development convenience**; replace it before demonstrating on a shared machine. To remove the seeded users and demo rows, back up any data you want to keep, then remove `instance/library.db` and run `init-db` without `seed-demo`. You can also disable ordinary member accounts in **Members**. Never point the destructive reset command at a database containing real records.

For hosted deployments, create the schema from committed migrations with `python -m flask --app run.py db upgrade`, then create the first staff account interactively:

```powershell
python -m flask --app run.py create-user --email librarian@example.edu --name "Library Administrator" --role admin
```

The command prompts for a password without putting it in shell history. Use `--role quality_manager` to provision a quality manager. Production mode blocks demo seeding and destructive demo resets.

For a local file-backed SQLite database, create an online-consistent backup with `python -m flask --app run.py backup-db`. Backups go to `instance/backups` by default and files older than `BACKUP_RETENTION_DAYS` are pruned. PostgreSQL backups must use the hosting provider's backup tools. Expired reset tokens and abandoned import previews can be removed with `python -m flask --app run.py purge-expired-records`; this does not purge audit, circulation, member, or catalog history.

### Catalog CSV format

On the Book catalog page, select **Import CSV** and use the downloadable template. Required headers are `isbn,title,author,category,publisher,publication_year,copies`; `subject` can be used instead of `category`. Optional headers are `course,semester`. Course and subject names must already exist in Catalog metadata; semester must be from 1 to 12. Each import is capped at 500 rows and 2 MB, is previewed and validated before commit, and is rejected as a batch when any row has an error. Preview records expire after 30 minutes. Existing real catalog records are not assigned guessed course or semester values during migration; staff can classify them from the book editor.

The six locally stored book and library photographs are used as editorial discovery imagery. They are served from `library_app/static/images/books`, so the catalog does not fetch a third-party image at runtime. The photo provider's current use terms are documented at [Unsplash License](https://unsplash.com/license).

## Run locally

```powershell
python run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Registering through the public form always creates a Member/Student account; staff accounts are local demo seeds or accounts provisioned by an administrator.

## Railway deployment

Connect the GitHub repository and deploy its `main` branch. The project root is the repository root; there is no separate backend directory. Configure:

```text
Build command: pip install -r requirements.txt
Start command: gunicorn run:app --bind 0.0.0.0:$PORT
```

Set these service variables in Railway (use Railway's PostgreSQL service for hosted data):

```text
APP_ENV=production
FLASK_DEBUG=false
SECRET_KEY=<a new random value of at least 32 characters>
DATABASE_URL=${{Postgres.DATABASE_URL}}
SESSION_COOKIE_SECURE=true
TRUST_PROXY=true
RATELIMIT_STORAGE_URI=${{Redis.REDIS_URL}}
DEFAULT_LOAN_DAYS=14
FINE_PER_DAY=1.00
```

Adjust the Railway reference names to match your PostgreSQL and Redis service names and available connection variables. Railway supplies `PORT`; do not define it yourself. `TRUST_PROXY=true` is intended for a trusted Railway proxy. Redis gives rate limits shared storage across app restarts and instances; `memory://` is suitable only for a local/single-process demo.

After attaching the PostgreSQL URL, run `python -m flask --app run.py db upgrade` against the deployed service before opening the public domain. Then run the `create-user` command from the service shell to create the initial staff login. Do not run `seed-demo` or `reset-demo` in production. If using SQLite instead, mount a persistent Railway volume at `/app/instance`, keep `DATABASE_URL=sqlite:///library.db`, use one application instance, and configure backups. SQLite is intended here for local and small demonstration deployments.

To refresh one due-soon/overdue in-app notification per active loan, run this command daily (or when demonstrating overdue reminders):

```powershell
python -m flask --app run.py send-loan-reminders
```

## Screenshots

No screenshot images were generated for this workspace run because desktop browser capture could not verify the active browser URL. The [demonstration guide](docs/DEMONSTRATION_GUIDE.md) includes repeatable Admin, Member, and Quality Manager workflows for capturing the fictional demo screens locally.

## Testing

```powershell
python -m pytest -v
```

The suite covers registration and authentication, role authorization, password reset, book creation/editing/import validation, settings and audit history, reporting formats and date bounds, issuing and returning, inventory consistency, duplicate and unavailable-loan prevention, late-fine calculation, rollback, feedback and complaints, reservation checkout, PDCA sequencing, KPI edge cases, and Pareto calculations. It uses a fresh in-memory SQLite database; it does not change the local demo database.

## Project structure

```text
library-management-system/
├── library_app/
│   ├── __init__.py          # app factory, configuration, CLI commands, CSRF, errors
│   ├── auth.py              # register, login, logout
│   ├── catalog.py           # books, copies, members, loans, fines, reservations
│   ├── main.py              # role dashboards and notifications
│   ├── models.py            # normalized SQLAlchemy schema and constraints
│   ├── quality.py           # feedback, complaints, RCA, actions, PDCA, KPI charts
│   ├── reports.py           # report pages and CSV exports
│   ├── security.py          # route role decorator
│   ├── seed.py              # fictional, repeatable demo dataset
│   ├── services.py          # transactional circulation and analytics
│   ├── static/              # responsive CSS and JavaScript
│   └── templates/           # accessible Bootstrap/Jinja role-based views
├── docs/                    # database, TQM, architecture, report outline, demo guide
├── migrations/              # repeatable schema changes for deployed databases
├── scripts/                 # direct init, seed, reset entry points
├── tests/                   # pytest unit, integration, and workflow coverage
├── .env.example
├── .gitignore
├── requirements.txt
└── run.py
```

## Architecture and project documentation

- [Architecture and issue/return sequence diagrams](docs/ARCHITECTURE.md)
- [Database schema and relationships](docs/DATABASE_SCHEMA.md)
- [TQM techniques, KPI formulas, periods, sources, and limits](docs/TQM_IMPLEMENTATION.md)
- [Academic project report outline](docs/PROJECT_REPORT_OUTLINE.md)
- [Demonstration guide](docs/DEMONSTRATION_GUIDE.md)

## Limitations and academic use

This project now includes production deployment foundations, but it is not a fully managed library service. Password-reset email requires SMTP configuration; external email/SMS notifications, payment processing, barcode hardware, and institution-managed database encryption require approved providers and operational setup. SQLite is single-instance storage; use PostgreSQL for hosted multi-worker deployments. The issue-time KPI measures the server-side issue operation, not a physical queue or total desk interaction. The dashboard withholds control limits because it does not have the consistent rational subgroups needed to calculate statistically valid limits. Replace fictional seed data with institution-approved, privacy-reviewed records before any real-world evaluation.
