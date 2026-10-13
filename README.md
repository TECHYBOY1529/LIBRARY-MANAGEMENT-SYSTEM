# Campus Library Management System with TQM

A modular library management web application for a college or university academic project. It combines copy-level inventory and circulation with member feedback, complaint handling, root-cause analysis, corrective actions, PDCA cycles, operational reports, and a data-backed quality dashboard.

> **Demo data:** the seed script creates explicitly fictional accounts, books, loans, feedback, and complaints. It contains no real library-member data. The demo accounts and fallback development secret are for local use only.

## Features

- **Three roles:** Admin/Librarian, Member/Student, and Quality Manager, with backend route authorization and role-specific navigation.
- **Catalog and inventory:** manage books, authors, categories, publishers, ISBNs, years, and individually barcoded copies. Search by title, author, ISBN, category, and availability.
- **Circulation:** issue/return procedures, due dates, overdue tracking, configurable fines, reservations and FIFO waitlists, member history, and in-app notifications.
- **Member services:** self-registration, secure login/logout, own loans and fines, 1–5 categorized feedback, complaint status tracking, and notifications.
- **TQM workflows:** complaint categorization, Pareto analysis, satisfaction trends, six-dimension Fishbone/Ishikawa and 5 Whys records, assigned improvement actions, physical inventory audits, and stage-gated PDCA cycles.
- **Quality analytics:** database-backed KPIs, borrowing and satisfaction charts, problem-category counts, and PDCA status/outcomes. A KPI shows **Insufficient data** when it has no usable sample.
- **Reports:** inventory, borrowing/returns, overdue loans, fines, and member-activity CSV exports.
- **Security and quality controls:** Werkzeug password hashing, session security, CSRF protection, server-side validation, foreign-key enforcement, audit log, transaction rollback, and pytest coverage.

See [TQM implementation and KPI formulas](docs/TQM_IMPLEMENTATION.md), [database schema](docs/DATABASE_SCHEMA.md), and [system architecture](docs/ARCHITECTURE.md).

## Technology stack

- Frontend: HTML5, CSS3, JavaScript, Bootstrap 5, Chart.js
- Backend: Python 3.10+, Flask, Flask-Login, Flask-WTF
- Database: SQLite, Flask-SQLAlchemy / SQLAlchemy
- Password hashing: Werkzeug secure password hash utilities
- Tests: pytest

Bootstrap, Chart.js, and the font stylesheet load from CDNs in a browser; an internet connection is needed for those visual assets. The Flask server and SQLite database run locally.

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

The `.env` file and local database are excluded by `.gitignore`. Do not commit secrets or real member data.

## Database setup and demo accounts

Initialize an empty database:

```powershell
python -m flask --app run.py init-db
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

The seed password is **only a local development convenience**; replace it before demonstrating on a shared machine. To remove the seeded users and demo rows, back up any data you want to keep, then remove the local database file `library.db` in the project root and run `init-db` without `seed-demo`. You can also disable ordinary member accounts in **Members**. Never point the destructive reset command at a database containing real records.

## Run locally

```powershell
python run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Registering through the public form always creates a Member/Student account; staff accounts are local demo seeds or accounts provisioned by an administrator.

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

The suite covers registration and authentication, role authorization, book creation/editing and validation, issuing and returning, inventory consistency, duplicate and unavailable-loan prevention, late-fine calculation, rollback, feedback and complaints, reservation checkout, PDCA sequencing, KPI edge cases, and Pareto calculations. It uses a fresh in-memory SQLite database; it does not change the local demo database.

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

This is a local academic prototype, not a production multi-branch deployment. Notifications are in-app (no email/SMS provider); no payment gateway or barcode hardware integration is included. The issue-time KPI measures the server-side issue operation, not a physical queue or total desk interaction. The dashboard withholds control limits because it does not have the consistent rational subgroups needed to calculate statistically valid limits. Replace the fictional seed data with institution-approved, privacy-reviewed records before any real-world evaluation.
