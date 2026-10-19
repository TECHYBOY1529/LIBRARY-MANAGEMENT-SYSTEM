import pytest

from library_app import create_app
from library_app.extensions import db
from library_app.models import Author, Book, BookCopy, Category, Course, Publisher, User


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-only-secret-key",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "DEFAULT_LOAN_DAYS": 14,
        "FINE_PER_DAY": 1.25,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def records(app):
    with app.app_context():
        admin = User(full_name="Test Librarian", email="admin@test.edu", role="admin")
        admin.set_password("AdminPassword!2026")
        manager = User(full_name="Test Quality Manager", email="quality@test.edu", role="quality_manager")
        manager.set_password("QualityPassword!2026")
        member = User(full_name="Test Member", email="member@test.edu", role="member")
        member.set_password("MemberPassword!2026")
        other = User(full_name="Other Member", email="other@test.edu", role="member")
        other.set_password("OtherPassword!2026")
        author, category, publisher = Author(name="Test Author"), Category(name="Test Category"), Publisher(name="Test Publisher")
        course = Course(name="Test BSc Course")
        db.session.add_all([admin, manager, member, other, author, category, publisher, course])
        db.session.flush()
        book = Book(isbn="9781234567890", title="Test Book", author_id=author.id,
                    category_id=category.id, publisher_id=publisher.id, course_id=course.id,
                    semester=2, publication_year=2024)
        db.session.add(book)
        db.session.flush()
        copy = BookCopy(book_id=book.id, barcode="TEST-001")
        db.session.add(copy)
        db.session.commit()
        return {"admin_id": admin.id, "manager_id": manager.id, "member_id": member.id,
                "other_id": other.id, "book_id": book.id, "copy_id": copy.id,
                "author_id": author.id, "category_id": category.id, "publisher_id": publisher.id,
                "course_id": course.id}


def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)
