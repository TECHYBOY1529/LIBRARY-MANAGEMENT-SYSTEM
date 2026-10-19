# Contributing

Thanks for helping improve the Campus Library Management System. Keep changes focused and preserve the existing Flask, SQLAlchemy, and Jinja architecture.

## Local setup

Use Python 3.10 or newer. From the repository root in Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app run.py init-db
python run.py
```

Set a private `SECRET_KEY` in `.env` before using the app beyond a local demo. Keep `.env`, local database files, and real member data out of Git.

## Change guidelines

- Keep route authorization on the server and retain CSRF protection, validation, and transactional database updates.
- Use database migrations for schema changes. Review generated migration files before applying them.
- Never run the demo reset command against a database that contains records you need to keep.
- Use fictional records for demonstrations and screenshots.
- Update the relevant documentation when a workflow, configuration option, or deployment step changes.
- Keep each commit focused on a complete, useful change and describe that change in its commit message.

## Local checks

Run the project test suite before proposing application changes:

```powershell
python -m pytest -v
```

For migration changes, also review the migration sequence and verify that the documented upgrade command applies cleanly to a disposable local database.
