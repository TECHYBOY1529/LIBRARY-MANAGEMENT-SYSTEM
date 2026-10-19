from flask import g

from library_app.extensions import db
from library_app.models import User

from .conftest import login


def test_registration_creates_member_and_hashes_password(client, app):
    response = client.post("/register", data={"full_name": "New Student", "email": "new@student.edu",
                                               "password": "StrongStudent!2026", "role": "admin"}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="new@student.edu").one()
        assert user.role == "member"
        assert user.password_hash != "StrongStudent!2026"
        assert user.check_password("StrongStudent!2026")


def test_registration_rejects_weak_password(client, app):
    response = client.post("/register", data={"full_name": "New Student", "email": "new@student.edu", "password": "short"})
    assert b"at least 10 characters" in response.data
    with app.app_context():
        assert User.query.filter_by(email="new@student.edu").first() is None


def test_login_and_logout(client, records):
    response = login(client, "member@test.edu", "MemberPassword!2026")
    assert b"MEMBER WORKSPACE" in response.data
    response = client.post("/logout", follow_redirects=True)
    assert b"Where would you like to go?" in response.data


def test_login_choice_and_role_specific_signin_pages(client):
    choice = client.get("/login")
    assert choice.status_code == 200
    assert b"Student" in choice.data
    assert b"Library management" in choice.data
    assert b"/login/student" in choice.data
    assert b"/login/management" in choice.data

    student = client.get("/login/student")
    assert b"STUDENT WORKSPACE" in student.data
    assert b"Create a student account" in student.data
    management = client.get("/login/management")
    assert b"LIBRARY TEAM" in management.data
    assert b"Create a student account" not in management.data


def test_unscoped_login_post_cannot_bypass_account_type_selection(client, records):
    response = client.post("/login", data={
        "email": "member@test.edu", "password": "MemberPassword!2026",
    }, follow_redirects=True)
    assert b"Choose Student or Library management" in response.data
    assert b"Student" in response.data and b"Library management" in response.data
    assert b"Where would you like to go?" in client.get("/account", follow_redirects=True).data


def test_student_signin_opens_student_dashboard_and_rejects_staff(client, records):
    response = client.post("/login/student", data={
        "email": "member@test.edu", "password": "MemberPassword!2026",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"MEMBER WORKSPACE" in response.data

    client.post("/logout")
    response = client.post("/login/student", data={
        "email": "admin@test.edu", "password": "AdminPassword!2026",
    }, follow_redirects=True)
    assert b"Email or password was not recognized." in response.data
    assert b"Where would you like to go?" in client.get("/account", follow_redirects=True).data


def test_management_signin_opens_staff_dashboard_and_rejects_students(client, records):
    response = client.post("/login/management", data={
        "email": "admin@test.edu", "password": "AdminPassword!2026",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Add a book" in response.data

    client.post("/logout")
    response = client.post("/login/management", data={
        "email": "member@test.edu", "password": "MemberPassword!2026",
    }, follow_redirects=True)
    assert b"Email or password was not recognized." in response.data
    assert b"Where would you like to go?" in client.get("/account", follow_redirects=True).data


def test_account_profile_and_password_update(client, records, app):
    login(client, "member@test.edu", "MemberPassword!2026")
    response = client.get("/account")
    assert response.status_code == 200
    assert b"Change password" in response.data

    response = client.post("/account", data={
        "form_action": "profile",
        "full_name": "Updated Member",
        "email": "updated.member@test.edu",
    }, follow_redirects=True)
    assert b"Your profile has been updated" in response.data
    with app.app_context():
        member = db.session.get(User, records["member_id"])
        assert member.full_name == "Updated Member"
        assert member.email == "updated.member@test.edu"

    response = client.post("/account", data={
        "form_action": "password",
        "current_password": "MemberPassword!2026",
        "new_password": "UpdatedPassword!2026",
        "confirm_password": "UpdatedPassword!2026",
    }, follow_redirects=True)
    assert b"Your password has been changed. Sign in again." in response.data
    with app.app_context():
        member = db.session.get(User, records["member_id"])
        assert member.check_password("UpdatedPassword!2026")
        assert member.auth_version == 1


def test_password_change_invalidates_other_signed_in_sessions(app, records):
    first_client = app.test_client()
    second_client = app.test_client()
    login(first_client, "member@test.edu", "MemberPassword!2026")
    g.pop("_login_user", None)
    login(second_client, "member@test.edu", "MemberPassword!2026")
    g.pop("_login_user", None)

    response = first_client.post("/account", data={
        "form_action": "password",
        "current_password": "MemberPassword!2026",
        "new_password": "UpdatedPassword!2026",
        "confirm_password": "UpdatedPassword!2026",
    }, follow_redirects=True)
    assert b"Your password has been changed. Sign in again." in response.data
    g.pop("_login_user", None)
    assert b"Where would you like to go?" in second_client.get("/account", follow_redirects=True).data


def test_member_suspension_revokes_sessions_even_after_reactivation(app, records):
    admin_client = app.test_client()
    member_client = app.test_client()
    login(admin_client, "admin@test.edu", "AdminPassword!2026")
    g.pop("_login_user", None)
    member_login = login(member_client, "member@test.edu", "MemberPassword!2026")
    assert b"MEMBER WORKSPACE" in member_login.data
    g.pop("_login_user", None)
    with member_client.session_transaction() as member_session:
        assert member_session.get("_auth_version") == 0

    path = f"/library/members/{records['member_id']}/update"
    profile = {"full_name": "Test Member", "email": "member@test.edu"}
    suspended = admin_client.post(path, data=profile, follow_redirects=True)
    assert b"Member record updated" in suspended.data
    reactivated = admin_client.post(path, data={**profile, "active": "on"}, follow_redirects=True)
    assert b"Member record updated" in reactivated.data

    with app.app_context():
        member = db.session.get(User, records["member_id"])
        assert member.active is True and member.auth_version == 2
    g.pop("_login_user", None)
    response = member_client.get("/account", follow_redirects=True)
    assert b"Where would you like to go?" in response.data


def test_login_is_rate_limited(client):
    response = None
    for _ in range(11):
        response = client.post("/login", data={"email": "unknown@test.edu", "password": "wrong"})
    assert response.status_code == 429


def test_health_endpoint_has_security_headers(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_role_access_control(client, records):
    login(client, "member@test.edu", "MemberPassword!2026")
    assert client.get("/library/books/new").status_code == 403
    assert client.get("/quality/").status_code == 403
    assert client.get("/library/history").status_code == 200

    client.post("/logout")
    login(client, "quality@test.edu", "QualityPassword!2026")
    assert client.get("/quality/").status_code == 200
    assert client.get("/library/loans").status_code == 403
    assert client.get("/library/history").status_code == 403
    assert client.get("/library/fines").status_code == 403
    assert client.get("/reports/members.csv").status_code == 403
    assert client.get("/reports/quality.csv").status_code == 200


def test_member_cannot_view_another_members_records(client, records, app):
    login(client, "member@test.edu", "MemberPassword!2026")
    with app.app_context():
        from library_app.models import Loan
        loan = Loan(copy_id=records["copy_id"], member_id=records["other_id"], issued_by_id=records["admin_id"],
                    due_date=__import__("datetime").date.today())
        db.session.add(loan)
        db.session.commit()
    response = client.get("/library/history")
    assert b"Test Book" not in response.data


def test_role_specific_dashboards_and_staff_views_render(client, records):
    login(client, "admin@test.edu", "AdminPassword!2026")
    for path in ["/dashboard", "/library/books", "/library/books/new", "/library/metadata/authors",
                 "/library/metadata/categories", "/library/metadata/publishers", "/library/members",
                 "/library/loans", "/library/history", "/library/fines", "/library/copies",
                 "/library/reservations", "/quality/", "/quality/feedback/register", "/quality/complaints",
                 "/quality/root-cause", "/quality/actions", "/quality/pdca", "/quality/inventory-audit",
                 "/reports/", "/reports/inventory.csv", "/reports/loans.csv", "/reports/overdue.csv",
                 "/reports/fines.csv", "/reports/members.csv", "/reports/quality.csv",
                 "/reports/pareto.csv", "/reports/borrowing-trends.csv"]:
        response = client.get(path)
        assert response.status_code == 200, f"{path}: {response.status_code}"
    client.post("/logout")
    login(client, "quality@test.edu", "QualityPassword!2026")
    assert b"QUALITY MANAGER WORKSPACE" in client.get("/dashboard").data
    assert b"Admin / Librarian" not in client.get("/dashboard").data
    client.post("/logout")
    login(client, "member@test.edu", "MemberPassword!2026")
    for path in ["/dashboard", "/library/books", "/library/history", "/library/my-reservations",
                 "/library/fines", "/notifications", "/quality/feedback", "/quality/complaints/new",
                 "/quality/complaints/mine"]:
        response = client.get(path)
        assert response.status_code == 200, f"{path}: {response.status_code}"
