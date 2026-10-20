from datetime import date, timedelta
import pytest

from library_app import services
from library_app.barcode_utils import generate_code39_svg, generate_shelf_label_svg, sanitize_barcode
from library_app.extensions import db
from library_app.models import Book, BookCopy, Loan, Reservation, User
from .conftest import login


def test_barcode_utils_encoding():
    assert sanitize_barcode("bk-1234") == "BK-1234"
    assert sanitize_barcode("hello*world#") == "HELLO-WORLD-"

    svg = generate_code39_svg("BK-1001", bar_height=30)
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "BK-1001" in svg
    assert "<rect" in svg

    label_svg = generate_shelf_label_svg("BK-1001", "Introduction to Systems", "Shelf A3", 1)
    assert "<svg" in label_svg
    assert "CAMPUS CENTRAL LIBRARY" in label_svg
    assert "Introduction to Systems" in label_svg


def test_loan_renewal_flow(client, records, app):
    login(client, "admin@test.edu", "AdminPassword!2026")
    with app.app_context():
        admin = db.session.get(User, records["admin_id"])
        member = db.session.get(User, records["member_id"])

        # Issue book to member
        loan = services.issue_book(records["member_id"], records["book_id"], admin, loan_days=14)
        original_due = loan.due_date
        loan_id = loan.id

        # Renewal should extend due date
        renewed_loan = services.renew_loan(loan_id, member, extension_days=7)
        assert renewed_loan.due_date == original_due + timedelta(days=7)

        # Overdue loan cannot be renewed
        renewed_loan.due_date = date.today() - timedelta(days=2)
        db.session.commit()

        with pytest.raises(ValueError, match="Overdue books cannot be renewed"):
            services.renew_loan(loan_id, member, extension_days=7)


def test_loan_renewal_blocked_by_reservation(client, records, app):
    login(client, "admin@test.edu", "AdminPassword!2026")
    with app.app_context():
        admin = db.session.get(User, records["admin_id"])
        member = db.session.get(User, records["member_id"])

        loan = services.issue_book(records["member_id"], records["book_id"], admin, loan_days=14)
        loan_id = loan.id

        # Place a waiting reservation by another user
        res = Reservation(book_id=records["book_id"], member_id=records["admin_id"], status="waiting")
        db.session.add(res)
        db.session.commit()

        with pytest.raises(ValueError, match="another member has reserved this title"):
            services.renew_loan(loan_id, member, extension_days=7)


def test_max_active_loans_enforced(client, records, app):
    login(client, "admin@test.edu", "AdminPassword!2026")
    with app.app_context():
        admin = db.session.get(User, records["admin_id"])
        app.config["MAX_ACTIVE_LOANS_PER_MEMBER"] = 1

        services.issue_book(records["member_id"], records["book_id"], admin, loan_days=14)

        # Attempt to issue a second copy under a different book title
        book2 = Book(
            isbn="9780000000022",
            title="Second Title",
            publication_year=2024,
            author_id=records["author_id"],
            category_id=records["category_id"],
            publisher_id=records["publisher_id"],
            course_id=records["course_id"],
            semester=1,
        )
        db.session.add(book2)
        db.session.flush()
        copy2 = BookCopy(book_id=book2.id, barcode="BK-222-01", status="available")
        db.session.add(copy2)
        db.session.commit()

        with pytest.raises(ValueError, match="reached the limit"):
            services.issue_book(records["member_id"], book2.id, admin, loan_days=14)
