"""Standalone database integrity and catalog consistency verification script."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from library_app import create_app
from library_app.extensions import db
from library_app.models import Book, BookCopy, Fine, Loan, User


def run_catalog_integrity_check():
    app = create_app()
    issues = []

    with app.app_context():
        # 1. Check for orphaned copies
        orphan_copies = BookCopy.query.filter(~BookCopy.book_id.in_(db.session.query(Book.id))).count()
        if orphan_copies > 0:
            issues.append(f"Found {orphan_copies} book copies with invalid or missing book reference.")

        # 2. Check for active loans pointing to missing copies
        orphan_loans = Loan.query.filter(Loan.status == "active", ~Loan.copy_id.in_(db.session.query(BookCopy.id))).count()
        if orphan_loans > 0:
            issues.append(f"Found {orphan_loans} active loans referencing non-existent copy records.")

        # 3. Check for loaned copy state consistency
        loaned_copies = BookCopy.query.filter_by(status="loaned").all()
        for copy in loaned_copies:
            active_loan = Loan.query.filter_by(copy_id=copy.id, status="active").first()
            if not active_loan:
                issues.append(f"Copy {copy.barcode} (ID {copy.id}) is marked 'loaned' but has no active loan record.")

        # 4. Check for invalid or negative fine amounts
        negative_fines = Fine.query.filter(Fine.amount < 0).count()
        if negative_fines > 0:
            issues.append(f"Found {negative_fines} fine records with negative amount.")

        # 5. Check user account password hashing
        users = User.query.all()
        plain_passwords = [u.email for u in users if not (u.password_hash and ":" in u.password_hash)]
        if plain_passwords:
            issues.append(f"Found {len(plain_passwords)} users without valid hashed passwords: {plain_passwords}")

        # Summary output
        print("=== Library System Integrity Diagnostic ===")
        print(f"Verified {Book.query.count()} books and {BookCopy.query.count()} copy records.")
        print(f"Verified {Loan.query.count()} loans and {Fine.query.count()} fine records.")
        print(f"Verified {len(users)} user accounts.")

        if issues:
            print(f"\n[FAIL] {len(issues)} integrity issue(s) detected:")
            for issue in issues:
                print(f"  - {issue}")
            return 1
        else:
            print("\n[OK] All catalog, circulation, and security integrity checks passed cleanly.")
            return 0


if __name__ == "__main__":
    sys.exit(run_catalog_integrity_check())
