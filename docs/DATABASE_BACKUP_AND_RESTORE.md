# Database backup and restore

Back up the database before applying migrations or performing maintenance. Store backups outside the repository, restrict access to them, and keep a retention schedule that meets the library's recovery needs. Database backups contain account and circulation records; never commit them to Git.

## Local SQLite

With the default local configuration, the database is `instance/library.db`. From the repository root in PowerShell, create a consistent snapshot using Python's SQLite backup API:

```powershell
python -c "import sqlite3; from pathlib import Path; from datetime import datetime; folder=Path.home()/'library-backups'; folder.mkdir(exist_ok=True); path=folder/f'library-{datetime.now():%Y%m%d-%H%M%S}.sqlite'; source=sqlite3.connect('instance/library.db'); target=sqlite3.connect(path); source.backup(target); target.close(); source.close(); print(path)"
```

If `DATABASE_URL` points somewhere else, use that database file as the source instead. Do not copy a live SQLite database file directly while the application is writing to it; the backup API also accounts for SQLite's journal mode.

To restore, stop the application first and make a separate backup of the current database. Then replace the source and destination paths below with the selected backup file and the configured database file:

```powershell
python -c "import sqlite3; source=sqlite3.connect(r'C:\path\to\library-backup.sqlite'); target=sqlite3.connect('instance/library.db'); source.backup(target); target.close(); source.close()"
```

Start the application and check that expected books, members, and loans are present before resuming use.

## PostgreSQL

Set `DATABASE_URL` in the PowerShell session to the database connection URL. Keep the URL private. The following commands write a timestamped custom-format backup under your user profile:

```powershell
$backup = Join-Path $env:USERPROFILE ("library-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".dump")
pg_dump --format=custom --file="$backup" "$env:DATABASE_URL"
```

For recovery, provision a separate empty PostgreSQL database, set `RESTORE_DATABASE_URL` to its connection URL, and restore there first:

```powershell
pg_restore --no-owner --dbname="$env:RESTORE_DATABASE_URL" "$backup"
```

Verify the restored data before switching the application to that database. Avoid restoring over the active database until the recovery has been reviewed.

## Before and after a migration

Take and retain a backup before running `python -m flask --app run.py db upgrade`. After the migration, start the application and verify the main catalog and circulation workflows. Keep the pre-migration backup until the upgraded database has been checked and accepted.
