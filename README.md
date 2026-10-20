# Campus Library Management System with TQM

A modular library management web application for a college or university academic project. It combines copy-level inventory and circulation with member feedback, complaint handling, root-cause analysis, corrective actions, PDCA cycles, operational reports, and a data-backed quality dashboard.

> **Demo data:** the seed script creates explicitly fictional accounts, books, loans, feedback, and complaints. It contains no real library-member data. The demo accounts and fallback development secret are for local use only.

## Features

- **Three roles:** Admin/Librarian, Member/Student, and Quality Manager, with separate Student and Library Management sign-in routes, backend account-type checks, role-specific dashboards, and role-based navigation.
- **Catalog and inventory:** manage books, authors, subjects, courses, semesters, publishers, ISBNs, years, and individually barcoded copies. Search by title, author, ISBN, subject, course, publisher, semester, and availability; sort and paginate results; validate and preview CSV imports before commit.
- **Institution profile data:** the `institutional_library_facts` table stores public, source-attributed Amrapali library facts separately from local books and copy records. It deliberately contains aggregate library information, not student rosters. Current webpage and 2025–26 prospectus counts are kept separately because the published totals differ; verify with the library before operational planning.
- **Circulation:** issue/return procedures, due dates, overdue tracking, configurable fines, reservations and FIFO waitlists, member history, and in-app notifications.
- **Member services:** self-registration, secure login/logout, own loans and fines, 1–5 categorized feedback, complaint status tracking, and notifications.
- **Account recovery:** expiring, one-use password-reset links; password changes and administrator resets revoke existing sessions.
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

### Run in Visual Studio Code

1. Open this project folder in VS Code and install the recommended Python extensions if prompted.
2. Select the project interpreter: press `Ctrl+Shift+P`, choose **Python: Select Interpreter**, and select `.venv\Scripts\python.exe`.
3. If this is a new local database, initialize it and optionally add fictional demo data in the integrated terminal:

   ```powershell
   python -m flask --app run.py init-db
   python -m flask --app run.py seed-demo
   ```

   For an existing database, apply updates with `python -m flask --app run.py db upgrade` instead of initializing it.
4. Open **Run and Debug** and press `F5`. VS Code starts the development server and opens `http://127.0.0.1:5000` in your browser. Stop it with `Shift+F5`.

The launch configuration loads `.env` automatically through the app when that file exists. If you have not created it, the app uses local development defaults.

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

Inspect inventory and circulation metrics in the console:

```powershell
python -m flask --app run.py catalog-summary
```

Run automated integrity checks across catalog copies, active loans, and account credentials:

```powershell
python scripts/check_catalog_health.py
```


### Catalog CSV format

On the Book catalog page, select **Import CSV** and use the downloadable template. Required headers are `isbn,title,author,category,publisher,publication_year,copies`; `subject` can be used instead of `category`. Optional headers are `course,semester`. Course and subject names must already exist in Catalog metadata; semester must be from 1 to 12. Each import is capped at 500 rows and 2 MB, is previewed and validated before commit, and is rejected as a batch when any row has an error. Preview records expire after 30 minutes. Existing real catalog records are not assigned guessed course or semester values during migration; staff can classify them from the book editor.

The six locally stored book and library photographs are used as editorial discovery imagery. They are served from `library_app/static/images/books`, so the catalog does not fetch a third-party image at runtime. The photo provider's current use terms are documented at [Unsplash License](https://unsplash.com/license).

### Presentation Decks & Review Visuals

The project includes structured presentation decks tailored for academic progress evaluations (Review 1 & Review 2):
- `Campus_Library_Management_System_Review_1_and_2_Pinterest_Edition.pptx`: Comprehensive 18-slide Pinterest-styled visual presentation covering problem statement, system architecture, ER diagrams, TQM Deming PDCA cycles, viva defenses, and live demo steps.
- `Campus_Library_Simple_Pinterest_Deck.pptx`: Fast-paced, high-impact 11-slide presentation deck designed for rapid class reviews and visual viva presentations.
- Visual assets in `library_app/static/images/presentation/`: anime-style hero library rendering, 3D circulation workflow diagram, and 3D TQM analytics artwork.

### Docker Containerization

Deploy the full stack (Flask + PostgreSQL 16 + Redis 7) with a single command:

```powershell
docker compose up --build -d
```

The application will be accessible at `http://localhost:5000` with automated health checks (`/healthz`).

### Automated Daily Maintenance

Run background database hygiene, purge temporary tokens, and refresh due-date reminders:

```powershell
python scripts/run_daily_maintenance.py
```

### Keyboard Command Palette (Ctrl+K)

Press `Ctrl+K` (or `Cmd+K`) from any page to open the instant Command Palette and jump directly between catalog shelves, circulation desks, quality registers, and administrative tools.

## Run locally

Stop any older server copy with `Ctrl+C` before restarting so it loads the latest project files. To use port 5002 explicitly:

```powershell
python -m flask --app run.py run --port 5002
```

Open [http://127.0.0.1:5002](http://127.0.0.1:5002) (or the same port you selected in the command). Registering through the public form always creates a Member/Student account; staff accounts are local demo seeds or accounts provisioned by an administrator.

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
PUBLIC_BASE_URL=https://<your-public-domain>
LIBRARY_TIMEZONE=Asia/Kolkata
DATABASE_URL=${{Postgres.DATABASE_URL}}
SESSION_COOKIE_SECURE=true
TRUST_PROXY=true
RATELIMIT_STORAGE_URI=${{Redis.REDIS_URL}}
DEFAULT_LOAN_DAYS=14
FINE_PER_DAY=1.00
```

Adjust the Railway reference names to match your PostgreSQL and Redis service names and available connection variables. Set `PUBLIC_BASE_URL` to the deployed HTTPS origin, not the placeholder above. Set `LIBRARY_TIMEZONE` to the timezone used for due dates and overdue reporting (Asia/Kolkata for Amrapali). Railway supplies `PORT`; do not define it yourself. Production startup rejects an insecure session-cookie setting, an HTTP/local public URL, or in-memory rate limits. `TRUST_PROXY=true` is intended for a trusted Railway proxy. Redis gives rate limits shared storage across app restarts and instances; `memory://` is suitable only for a local/single-process demo. Configure SMTP to enable self-service password resets; otherwise administrators must assist users.

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
