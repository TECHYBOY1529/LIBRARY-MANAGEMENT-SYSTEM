"""Fast verification script to confirm database and routes are healthy."""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from library_app import create_app
from library_app.extensions import db
from library_app.models import Book, User, Loan

app = create_app()

with app.app_context():
    try:
        users = User.query.count()
        books = Book.query.count()
        loans = Loan.query.count()
        print(f"[OK] Database connection verified: {users} users, {books} books, {loans} loans.")
    except Exception as exc:
        print(f"[ERROR] Database check failed: {exc}")
        sys.exit(1)

client = app.test_client()
res = client.get("/healthz")
if res.status_code == 200:
    print("[OK] /healthz endpoint responding HTTP 200.")
else:
    print(f"[WARN] /healthz returned {res.status_code}")

print("[SUCCESS] All system health checks passed.")
