from datetime import date, timedelta
from decimal import Decimal

import pytest

from library_app import services
from library_app.extensions import db
from library_app.models import Book, BookCopy, Fine, Loan, User
from .conftest import login


def test_admin_can_create_and_edit_book(client, records, app):
    login(client, "admin@test.edu", "AdminPassword!2026")
    payload = {"isbn": "9781111111111", "title": "Created Book", "publication_year": "2022",
               "author_id": records["author_id"], "category_id": records["category_id"],
               "publisher_id": records["publisher_id"], "copies": "2"}
    response = client.post("/library/books/new", data=payload, follow_redirects=True)
    assert b"Book and copies added" in response.data
    with app.app_context():
        book = Book.query.filter_by(isbn="9781111111111").one()
        assert book.total_copies == 2
        book_id = book.id
    payload.update({"isbn": "9781111111111", "title": "Edited Book", "add_copies": "1"})
    response = client.post(f"/library/books/{book_id}/edit", data=payload, follow_redirects=True)
    assert b"Book details saved" in response.data
    with app.app_context():
        book = db.session.get(Book, book_id)
        assert book.title == "Edited Book"
        assert book.total_copies == 3


def test_book_form_rejects_invalid_isbn(client, records, app):
    login(client, "admin@test.edu", "AdminPassword!2026")
    response = client.post("/library/books/new", data={"isbn": "bad", "title": "Invalid", "publication_year": "2024",
                                                        "author_id": records["author_id"], "category_id": records["category_id"],
                                                        "publisher_id": records["publisher_id"], "copies": "1"})
    assert response.status_code == 200
    assert b"valid ISBN" in response.data
    with app.app_context():
        assert Book.query.filter_by(title="Invalid").first() is None


def test_issue_return_inventory_and_fine(client, records, app):
    login(client, "admin@test.edu", "AdminPassword!2026")
    response = client.post("/library/loans", data={"member_id": records["member_id"], "book_id": records["book_id"]}, follow_redirects=True)
    assert b"Book issued successfully" in response.data
    with app.app_context():
        copy = db.session.get(BookCopy, records["copy_id"])
        loan = Loan.query.one()
        assert copy.status == "loaned"
        assert loan.due_date == date.today() + timedelta(days=14)
        loan.due_date = date.today() - timedelta(days=3)
        loan_id = loan.id
        db.session.commit()
    response = client.post(f"/library/loans/{loan_id}/return", follow_redirects=True)
    assert b"Return processed" in response.data
    with app.app_context():
        assert db.session.get(BookCopy, records["copy_id"]).status == "available"
        assert Loan.query.one().status == "returned"
        assert Fine.query.one().amount == Decimal("3.75")
        assert db.session.query(Loan).count() == 1


def test_duplicate_and_unavailable_issue_rejected(client, records, app):
    login(client, "admin@test.edu", "AdminPassword!2026")
    first = client.post("/library/loans", data={"member_id": records["member_id"], "book_id": records["book_id"]}, follow_redirects=True)
    assert b"Book issued successfully" in first.data
    duplicate = client.post("/library/loans", data={"member_id": records["member_id"], "book_id": records["book_id"]}, follow_redirects=True)
    assert b"already has an active loan" in duplicate.data
    unavailable = client.post("/library/loans", data={"member_id": records["other_id"], "book_id": records["book_id"]}, follow_redirects=True)
    assert b"No available copy" in unavailable.data
    with app.app_context():
        assert Loan.query.count() == 1
        assert BookCopy.query.one().status == "loaned"


def test_return_rejects_invalid_second_return(app, records):
    with app.app_context():
        admin = db.session.get(User, records["admin_id"])
        loan = services.issue_book(records["member_id"], records["book_id"], admin)
        services.return_book(loan.id, admin)
        with pytest.raises(ValueError, match="not active"):
            services.return_book(loan.id, admin)
        assert BookCopy.query.one().status == "available"


def test_issue_transaction_rolls_back_after_failure(app, records, monkeypatch):
    with app.app_context():
        admin = db.session.get(User, records["admin_id"])
        def fail_audit(*_args, **_kwargs):
            raise RuntimeError("simulated audit failure")
        monkeypatch.setattr(services, "audit", fail_audit)
        with pytest.raises(RuntimeError, match="simulated"):
            services.issue_book(records["member_id"], records["book_id"], admin)
        db.session.expire_all()
        assert BookCopy.query.one().status == "available"
        assert Loan.query.count() == 0


def test_return_transaction_rolls_back_after_failure(app, records, monkeypatch):
    with app.app_context():
        admin = db.session.get(User, records["admin_id"])
        loan = services.issue_book(records["member_id"], records["book_id"], admin)
        loan_id = loan.id
        original_due = loan.due_date
        loan.due_date = date.today() - timedelta(days=2)
        db.session.commit()
        def fail_audit(*_args, **_kwargs):
            raise RuntimeError("simulated audit failure")
        monkeypatch.setattr(services, "audit", fail_audit)
        with pytest.raises(RuntimeError, match="simulated"):
            services.return_book(loan_id, admin)
        db.session.expire_all()
        assert Loan.query.one().status == "active"
        assert BookCopy.query.one().status == "loaned"
        assert Fine.query.count() == 0


def test_csv_exports_escape_formula_cells():
    from library_app.reports import csv_response
    response = csv_response("safe.csv", ["Name", "Value"], [["=HYPERLINK(\"https://example.test\")", "normal"]])
    assert response.status_code == 200
    assert b"'=HYPERLINK" in response.data
