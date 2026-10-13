from datetime import date

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from .extensions import db
from .models import Book, BookCopy, Complaint, Feedback, ImprovementAction, Loan, Notification, Reservation, User
from .services import kpi_summary, refresh_loan_notifications

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@bp.get("/dashboard")
@login_required
def dashboard():
    if current_user.role == "member":
        refresh_loan_notifications(current_user.id)
        loans = Loan.query.filter_by(member_id=current_user.id, status="active").order_by(Loan.due_date).all()
        history_count = Loan.query.filter_by(member_id=current_user.id).count()
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(5).all()
        reservations = Reservation.query.filter_by(member_id=current_user.id, status="ready").all()
        return render_template("dashboard_member.html", loans=loans, history_count=history_count,
                               notifications=notifications, reservations=reservations)
    summary = {
        "books": Book.query.count(),
        "available": BookCopy.query.filter_by(status="available").count(),
        "members": User.query.filter_by(role="member", active=True).count(),
        "active_loans": Loan.query.filter_by(status="active").count(),
        "overdue": Loan.query.filter(Loan.status == "active", Loan.due_date < date.today()).count(),
        "complaints": Complaint.query.filter(Complaint.status.in_(["open", "in_progress"])).count(),
        "satisfaction": db.session.query(func.avg(Feedback.rating)).scalar(),
        "actions": ImprovementAction.query.filter(ImprovementAction.status != "completed").count(),
    }
    summary["satisfaction"] = round(summary["satisfaction"], 2) if summary["satisfaction"] is not None else None
    if current_user.role == "quality_manager":
        from .models import PdcaCycle
        quality_summary = {
            "pending_complaints": summary["complaints"],
            "open_actions": summary["actions"],
            "active_cycles": PdcaCycle.query.filter(PdcaCycle.phase != "complete").count(),
            "feedback_count": Feedback.query.count(),
            "satisfaction": summary["satisfaction"],
        }
        return render_template("dashboard_quality.html", summary=quality_summary, kpis=kpi_summary())
    return render_template("dashboard_staff.html", summary=summary, kpis=kpi_summary(),
                           role_label="Quality Manager" if current_user.role == "quality_manager" else "Admin / Librarian")


@bp.get("/notifications")
@login_required
def notifications():
    rows = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template("notifications.html", notifications=rows)


@bp.post("/notifications/<int:notification_id>/read")
@login_required
def mark_notification_read(notification_id):
    row = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    from .models import utcnow
    row.read_at = utcnow()
    db.session.commit()
    flash("Notification marked as read.", "success")
    return redirect(url_for("main.notifications"))
