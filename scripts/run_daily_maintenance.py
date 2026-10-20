#!/usr/bin/env python3
"""Automated Daily Maintenance Runner for Campus Library Management System.

Can be triggered by Linux cron jobs, Windows Task Scheduler, Railway cron jobs,
or cloud health watchers to perform routine database hygiene:
  1. Purges expired password reset tokens and temporary import previews.
  2. Refreshes due-date reminders and overdue notifications.
  3. Checks catalog integrity metrics and logs an audit trail entry.

Usage:
    python scripts/run_daily_maintenance.py [--dry-run]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure root workspace directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from library_app import create_app
from library_app.extensions import db
from library_app.models import BookCopy, Loan, Reservation
from library_app.services import (
    audit,
    expired_record_counts,
    purge_expired_records,
    refresh_loan_notifications,
)
from library_app.time_utils import library_today


def execute_maintenance(dry_run: bool = False) -> dict:
    app = create_app()
    with app.app_context():
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "expired_previews": expired_record_counts(),
            "notifications_dispatched": 0,
            "purged": {},
            "active_loans": 0,
            "overdue_loans": 0,
            "waiting_holds": 0,
        }

        # 1. Circulation counts
        today = library_today()
        results["active_loans"] = Loan.query.filter_by(status="active").count()
        results["overdue_loans"] = (
            Loan.query.filter(Loan.status == "active", Loan.due_date < today).count()
        )
        results["waiting_holds"] = Reservation.query.filter_by(status="waiting").count()

        if dry_run:
            print("[DRY RUN] Maintenance preview:")
            print(json.dumps(results, indent=2))
            return results

        # 2. Purge expired temporary records
        purged = purge_expired_records(source="scheduled_maintenance")
        results["purged"] = purged

        # 3. Refresh due and overdue reminders
        refresh_loan_notifications()
        results["notifications_refreshed"] = True

        # 4. Record maintenance audit trail
        audit(
            None,
            "daily_maintenance_run",
            "system",
            None,
            f"active={results['active_loans']}, overdue={results['overdue_loans']}, purged={purged}",
        )
        db.session.commit()

        print("[SUCCESS] Daily maintenance executed successfully.")
        print(json.dumps(results, indent=2))
        return results


def main():
    parser = argparse.ArgumentParser(description="Run daily maintenance tasks.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview counts without modifying database records.",
    )
    args = parser.parse_args()

    try:
        execute_maintenance(dry_run=args.dry_run)
    except Exception as e:
        print(f"[ERROR] Maintenance run failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
