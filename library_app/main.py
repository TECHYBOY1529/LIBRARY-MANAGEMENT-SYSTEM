import calendar
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload

from .extensions import db
from .models import AuditLog, Book, BookCopy, BugIncident, Category, Complaint, Course, Feedback, ImprovementAction, Loan, Notification, Reservation, SystemSetting, User, utcnow
from .security import roles_required
from .services import kpi_summary, refresh_loan_notifications, time_series_monthly

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@bp.get("/dashboard")
@login_required
def dashboard():
    discovery_books = (Book.query.options(joinedload(Book.author), joinedload(Book.category),
                                          joinedload(Book.course), selectinload(Book.copies))
                       .order_by(Book.created_at.desc(), Book.id.desc()).limit(12).all())
    course_shelves = (db.session.query(Course.id, Course.name, func.count(Book.id))
                      .outerjoin(Book, Book.course_id == Course.id).group_by(Course.id, Course.name)
                      .having(func.count(Book.id) > 0).order_by(Course.name).all())
    subject_shelves = (db.session.query(Category.id, Category.name, func.count(Book.id))
                       .outerjoin(Book, Book.category_id == Category.id).group_by(Category.id, Category.name)
                       .having(func.count(Book.id) > 0).order_by(Category.name).all())
    discovery = {"discovery_books": discovery_books, "course_shelves": course_shelves,
                 "subject_shelves": subject_shelves}
    if current_user.role == "member":
        refresh_loan_notifications(current_user.id)
        loans = Loan.query.filter_by(member_id=current_user.id, status="active").order_by(Loan.due_date).all()
        history_count = Loan.query.filter_by(member_id=current_user.id).count()
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(5).all()
        reservations = Reservation.query.filter_by(member_id=current_user.id, status="ready").all()
        return render_template("dashboard_member.html", loans=loans, history_count=history_count,
                               notifications=notifications, reservations=reservations, **discovery)
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
        return render_template("dashboard_quality.html", summary=quality_summary, kpis=kpi_summary(), **discovery)
    copy_status = {status: count for status, count in db.session.query(BookCopy.status, func.count(BookCopy.id)).group_by(BookCopy.status).all()}
    summary["total_copies"] = sum(copy_status.values())
    summary["reserved_copies"] = copy_status.get("reserved", 0)
    summary["maintenance_copies"] = copy_status.get("maintenance", 0)
    trend = time_series_monthly(Loan, Loan.issued_at, utcnow() - timedelta(days=180))
    due_soon = (Loan.query.filter(Loan.status == "active", Loan.due_date >= date.today(),
                                  Loan.due_date <= date.today() + timedelta(days=7))
                .options(joinedload(Loan.copy).joinedload(BookCopy.book), joinedload(Loan.member))
                .order_by(Loan.due_date.asc()).limit(5).all())
    return render_template("dashboard_staff.html", summary=summary, kpis=kpi_summary(),
                           role_label="Admin / Librarian", trend=trend, due_soon=due_soon,
                           recent_books=discovery_books[:4], **discovery)


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


@bp.get("/help")
@login_required
def help_page():
    return render_template("help.html")


@bp.get("/about")
@login_required
def about_page():
    return render_template("about.html")


@bp.get("/calendar")
@login_required
def due_calendar():
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)
    if not 2000 <= year <= 2100 or not 1 <= month <= 12:
        year, month = today.year, today.month
    first = date(year, month, 1)
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    query = (Loan.query.filter(Loan.status == "active", Loan.due_date >= first, Loan.due_date < next_month)
             .options(joinedload(Loan.member), joinedload(Loan.copy).joinedload(BookCopy.book)))
    if current_user.role == "member":
        query = query.filter(Loan.member_id == current_user.id)
    loans = query.order_by(Loan.due_date, Loan.member_id).all()
    by_day = {}
    for loan in loans:
        by_day.setdefault(loan.due_date.day, []).append(loan)
    previous = first - timedelta(days=1)
    following = next_month
    return render_template("due_calendar.html", year=year, month=month, weeks=calendar.monthcalendar(year, month),
                           by_day=by_day, month_name=calendar.month_name[month], previous=previous,
                           following=following, today=today)


@bp.get("/audit-log")
@roles_required("admin")
def audit_log():
    pagination = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=50, error_out=False)
    return render_template("audit_log.html", pagination=pagination)


@bp.route("/system-settings", methods=["GET", "POST"])
@roles_required("admin")
def system_settings():
    if request.method == "POST":
        days = request.form.get("default_loan_days", type=int)
        try:
            fine = Decimal(request.form.get("fine_per_day", ""))
        except (InvalidOperation, TypeError, ValueError):
            fine = Decimal("-1")
        if days is None or not 1 <= days <= 365:
            flash("The default loan period must be between 1 and 365 days.", "danger")
        elif not fine.is_finite() or not Decimal("0") <= fine <= Decimal("100000"):
            flash("The daily fine must be a finite amount from 0 to 100,000.", "danger")
        else:
            fine = fine.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            values = {"DEFAULT_LOAN_DAYS": str(days), "FINE_PER_DAY": f"{fine:.2f}"}
            for key, value in values.items():
                row = db.session.get(SystemSetting, key) or SystemSetting(key=key, value=value)
                row.value, row.updated_by_id = value, current_user.id
                db.session.add(row)
                current_app.config[key] = days if key == "DEFAULT_LOAN_DAYS" else float(fine)
            from .services import audit
            audit(current_user, "update_system_settings", "system_setting", None, f"loan_days={days}; fine={fine:.2f}")
            db.session.commit()
            flash("System settings saved.", "success")
        return redirect(url_for("main.system_settings"))
    settings = {
        "default_loan_days": int(SystemSetting.query.filter_by(key="DEFAULT_LOAN_DAYS").with_entities(SystemSetting.value).scalar() or current_app.config["DEFAULT_LOAN_DAYS"]),
        "fine_per_day": float(SystemSetting.query.filter_by(key="FINE_PER_DAY").with_entities(SystemSetting.value).scalar() or current_app.config["FINE_PER_DAY"]),
    }
    return render_template("system_settings.html", settings=settings)


@bp.route("/incidents", methods=["GET", "POST"])
@roles_required("admin", "quality_manager")
def incidents():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        severity = request.form.get("severity", "medium")
        if not 3 <= len(title) <= 180 or not 10 <= len(description) <= 3000:
            flash("Enter a title (3–180 characters) and description (10–3,000 characters).", "danger")
        elif severity not in {"low", "medium", "high"}:
            flash("Choose a valid incident severity.", "danger")
        else:
            item = BugIncident(title=title, description=description, severity=severity, created_by_id=current_user.id)
            db.session.add(item)
            db.session.flush()
            from .services import audit
            audit(current_user, "report_incident", "bug_incident", item.id, f"severity={severity}")
            db.session.commit()
            flash("Incident added to the tracking log.", "success")
            return redirect(url_for("main.incidents"))
    pagination = BugIncident.query.order_by(BugIncident.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=25, error_out=False)
    return render_template("incident_register.html", pagination=pagination)


@bp.post("/incidents/<int:incident_id>/status")
@roles_required("admin", "quality_manager")
def incident_status(incident_id):
    item = db.get_or_404(BugIncident, incident_id)
    status = request.form.get("status", "")
    if status not in {"open", "in_progress", "resolved"}:
        flash("Choose a valid incident status.", "danger")
    else:
        item.status = status
        item.resolved_at = utcnow() if status == "resolved" else None
        from .services import audit
        audit(current_user, "update_incident", "bug_incident", item.id, f"status={status}")
        db.session.commit()
        flash("Incident status updated.", "success")
    return redirect(url_for("main.incidents"))
