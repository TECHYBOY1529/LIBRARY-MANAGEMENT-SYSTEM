from datetime import date, datetime, timedelta, timezone

from library_app.extensions import db
from library_app.models import Complaint, Feedback, ImprovementAction, Loan, Reservation, User
from library_app.services import kpi_summary, pareto_data
from .conftest import login


def test_feedback_and_complaint_submission(client, records, app):
    login(client, "member@test.edu", "MemberPassword!2026")
    response = client.post("/quality/feedback", data={"category": "staff_service", "rating": "5", "comments": "Helpful desk support."}, follow_redirects=True)
    assert b"feedback has been recorded" in response.data
    response = client.post("/quality/complaints/new", data={"category": "waiting_time", "subject": "Long wait", "description": "The queue was long at noon."}, follow_redirects=True)
    assert b"complaint was submitted" in response.data
    with app.app_context():
        assert Feedback.query.one().rating == 5
        complaint = Complaint.query.one()
        assert complaint.member_id == records["member_id"]
        assert complaint.status == "open"


def test_member_cannot_change_complaint_status(client, records, app):
    with app.app_context():
        complaint = Complaint(member_id=records["member_id"], category="other", subject="Test", description="Test complaint")
        db.session.add(complaint)
        db.session.commit()
        complaint_id = complaint.id
    login(client, "member@test.edu", "MemberPassword!2026")
    assert client.post(f"/quality/complaints/{complaint_id}/status", data={"status": "resolved"}).status_code == 403


def test_action_and_pdca_workflow(client, records, app):
    login(client, "quality@test.edu", "QualityPassword!2026")
    response = client.post("/quality/actions", data={"problem": "Slow queue", "root_cause": "Only one desk", "corrective_action": "Open second desk", "owner_id": records["manager_id"], "deadline": (date.today()+timedelta(days=5)).isoformat()}, follow_redirects=True)
    assert b"Improvement action assigned" in response.data
    with app.app_context():
        action = ImprovementAction.query.one()
        action_id = action.id
    client.post(f"/quality/actions/{action_id}/status", data={"status": "completed"})
    response = client.post("/quality/pdca", data={"title": "Queue experiment", "problem": "Queue too long", "measurable_target": "Under five minutes", "baseline": "8 minute median", "plan": "Add a temporary desk"}, follow_redirects=True)
    assert b"PDCA cycle started" in response.data
    with app.app_context():
        from library_app.models import PdcaCycle
        cycle = PdcaCycle.query.one()
        cycle_id = cycle.id
    response = client.post(f"/quality/pdca/{cycle_id}/advance", data={"phase": "check", "check_result": "out of order"}, follow_redirects=True)
    assert b"Plan \xe2\x86\x92 Do \xe2\x86\x92 Check \xe2\x86\x92 Act" in response.data
    for phase, data in [("do", {"do_notes": "Second desk opened."}), ("check", {"check_result": "Median fell to five minutes."}), ("act", {"act_decision": "Standardize the desk on peak days."}), ("complete", {"outcome": "Target achieved and standardized."})]:
        response = client.post(f"/quality/pdca/{cycle_id}/advance", data={"phase": phase, **data}, follow_redirects=True)
        assert response.status_code == 200
    with app.app_context():
        cycle = db.session.get(PdcaCycle, cycle_id)
        assert cycle.phase == "complete"
        assert cycle.outcome.startswith("Target achieved")


def test_kpis_are_calculated_and_missing_samples_stay_empty(app, records):
    with app.app_context():
        summary = kpi_summary()
        assert summary["satisfaction"] is None
        assert summary["inventory_accuracy_pct"] is None
        assert summary["complaint_resolution_rate_pct"] is None
        from library_app.models import InventoryAudit
        db.session.add_all([
            Feedback(member_id=records["member_id"], category="other", rating=4, comments="Good"),
            Feedback(member_id=records["other_id"], category="other", rating=2, comments="Fair"),
            InventoryAudit(checked_copies=10, matching_copies=9, audited_by_id=records["admin_id"]),
            Complaint(member_id=records["member_id"], category="other", subject="Resolved", description="Issue", status="resolved", created_at=datetime.now(timezone.utc)-timedelta(days=2), resolved_at=datetime.now(timezone.utc)-timedelta(days=1)),
            Complaint(member_id=records["member_id"], category="other", subject="Open", description="Issue"),
        ])
        db.session.commit()
        summary = kpi_summary()
        assert summary["satisfaction"] == 3.0
        assert summary["inventory_accuracy_pct"] == 90.0
        assert summary["complaint_resolution_rate_pct"] == 50.0
        assert summary["avg_complaint_resolution_days"] == 1.0
        assert summary["data_sources"]["overdue_loan_rate_pct"]


def test_pareto_uses_actual_categories(app, records):
    with app.app_context():
        db.session.add_all([Complaint(member_id=records["member_id"], category="waiting_time", subject="A", description="A"),
                            Complaint(member_id=records["other_id"], category="waiting_time", subject="B", description="B"),
                            Complaint(member_id=records["member_id"], category="cleanliness", subject="C", description="C")])
        db.session.commit()
        data = pareto_data()
        assert data["labels"][0] == "Waiting Time"
        assert data["counts"] == [2, 1]
        assert data["cumulative"] == [66.7, 100.0]


def test_reservation_request_records_availability_and_checkout(client, records, app):
    login(client, "member@test.edu", "MemberPassword!2026")
    response = client.post(f"/library/reserve/{records['book_id']}", follow_redirects=True)
    assert b"copy is ready now" in response.data
    with app.app_context():
        reservation = Reservation.query.one()
        assert reservation.available_at_request is True
        reservation_id = reservation.id
    client.post("/logout")
    login(client, "admin@test.edu", "AdminPassword!2026")
    response = client.post(f"/library/reservations/{reservation_id}/checkout", follow_redirects=True)
    assert b"checked out to the member" in response.data
    with app.app_context():
        assert Reservation.query.one().status == "fulfilled"
        assert Loan.query.one().member_id == records["member_id"]


def test_member_can_cancel_reservation_and_copy_is_released(client, records, app):
    login(client, "member@test.edu", "MemberPassword!2026")
    client.post(f"/library/reserve/{records['book_id']}")
    with app.app_context():
        reservation = Reservation.query.one()
        assert reservation.status == "ready"
        reservation_id = reservation.id
    response = client.post(f"/library/reservations/{reservation_id}/cancel", follow_redirects=True)
    assert b"Reservation cancelled" in response.data
    with app.app_context():
        assert Reservation.query.one().status == "cancelled"
        from library_app.models import BookCopy
        assert BookCopy.query.one().status == "available"


def test_seed_is_repeatable_and_contains_enough_fictional_data(app):
    from library_app.seed import seed_demo
    from library_app.models import Book, PdcaCycle, RootCauseAnalysis
    with app.app_context():
        seed_demo()
        first_counts = (Book.query.count(), User.query.filter_by(role="member").count(),
                        Complaint.query.count(), PdcaCycle.query.count())
        seed_demo()
        second_counts = (Book.query.count(), User.query.filter_by(role="member").count(),
                         Complaint.query.count(), PdcaCycle.query.count())
        assert first_counts == second_counts
        assert first_counts[0] >= 30
        assert first_counts[1] >= 10
        assert first_counts[2] >= 6
        assert RootCauseAnalysis.query.count() >= 1


def test_fictional_demo_quality_views_render(client, app):
    from library_app.seed import seed_demo
    with app.app_context():
        seed_demo()
    login(client, "quality@library.demo", "QualityDemo!2026")
    for path in ["/dashboard", "/quality/", "/quality/root-cause", "/quality/actions",
                 "/quality/pdca", "/quality/feedback/register", "/reports/quality.csv", "/reports/pareto.csv"]:
        response = client.get(path)
        assert response.status_code == 200, f"{path}: {response.status_code}"
    assert b"Peak hour queue" in client.get("/quality/root-cause").data
