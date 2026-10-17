import json
from datetime import timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from .extensions import db
from .models import (Complaint, Feedback, ImprovementAction, InventoryAudit, Loan,
                     PdcaCycle, RootCauseAnalysis, User, utcnow)
from .security import roles_required
from .services import audit, kpi_summary, pareto_data, time_series_monthly

bp = Blueprint("quality", __name__)
CATEGORIES = {
    "book_availability": "Book availability", "staff_service": "Staff service",
    "waiting_time": "Waiting time", "cleanliness": "Cleanliness",
    "digital_access": "Digital access", "other": "Other",
}


@bp.route("/feedback", methods=["GET", "POST"])
@roles_required("member")
def feedback_submit():
    if request.method == "POST":
        category = request.form.get("category")
        rating = request.form.get("rating", type=int)
        comments = request.form.get("comments", "").strip()
        if category not in CATEGORIES or rating not in range(1, 6) or not comments or len(comments) > 2000:
            flash("Choose a category, rate from 1–5, and enter comments (up to 2,000 characters).", "danger")
        else:
            row = Feedback(member_id=current_user.id, category=category, rating=rating, comments=comments)
            db.session.add(row)
            db.session.commit()
            flash("Thank you. Your feedback has been recorded.", "success")
            return redirect(url_for("quality.feedback_submit"))
    return render_template("feedback_form.html", categories=CATEGORIES)


@bp.get("/feedback/register")
@roles_required("admin", "quality_manager")
def feedback_register():
    rows = Feedback.query.order_by(Feedback.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=20, error_out=False)
    return render_template("feedback_register.html", pagination=rows, categories=CATEGORIES)


@bp.route("/complaints/new", methods=["GET", "POST"])
@roles_required("member")
def complaint_new():
    if request.method == "POST":
        category = request.form.get("category")
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()
        if category not in CATEGORIES or not subject or len(subject) > 160 or not description or len(description) > 4000:
            flash("Provide a category, a subject (up to 160 characters), and a description (up to 4,000 characters).", "danger")
        else:
            row = Complaint(member_id=current_user.id, category=category, subject=subject, description=description)
            db.session.add(row)
            db.session.commit()
            flash("Your complaint was submitted. You can track its status here.", "success")
            return redirect(url_for("quality.my_complaints"))
    return render_template("complaint_form.html", categories=CATEGORIES)


@bp.get("/complaints/mine")
@roles_required("member")
def my_complaints():
    rows = Complaint.query.filter_by(member_id=current_user.id).order_by(Complaint.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=20, error_out=False)
    return render_template("complaints.html", pagination=rows, categories=CATEGORIES, staff_view=False)


@bp.get("/complaints")
@roles_required("admin", "quality_manager")
def complaints():
    query = Complaint.query
    search = request.args.get("q", "").strip()[:120]
    status = request.args.get("status", "")
    category = request.args.get("category", "")
    if search:
        pattern = f"%{search}%"
        query = query.outerjoin(User, Complaint.member_id == User.id).filter(
            or_(Complaint.subject.ilike(pattern), Complaint.description.ilike(pattern), User.full_name.ilike(pattern))
        )
    if status in {"open", "in_progress", "resolved", "closed"}:
        query = query.filter(Complaint.status == status)
    if category in CATEGORIES:
        query = query.filter(Complaint.category == category)
    rows = query.order_by(Complaint.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=20, error_out=False)
    return render_template("complaints.html", pagination=rows, categories=CATEGORIES, staff_view=True,
                           search=search, selected_status=status, selected_category=category)


@bp.post("/complaints/<int:complaint_id>/status")
@roles_required("admin", "quality_manager")
def complaint_status(complaint_id):
    row = db.get_or_404(Complaint, complaint_id)
    status = request.form.get("status")
    if status not in {"open", "in_progress", "resolved", "closed"}:
        flash("Choose a valid complaint status.", "danger")
    else:
        row.status = status
        row.resolved_at = utcnow() if status in {"resolved", "closed"} else None
        from .services import notify
        if row.member_id:
            notify(row.member_id, "Complaint update", f"Complaint #{row.id} is now {status.replace('_', ' ')}.", "complaint")
        audit(current_user, "update_complaint", "complaint", row.id, status)
        db.session.commit()
        flash("Complaint status updated and member notified.", "success")
    return redirect(url_for("quality.complaints"))


@bp.route("/root-cause", methods=["GET", "POST"])
@roles_required("admin", "quality_manager")
def root_cause():
    if request.method == "POST":
        problem = request.form.get("problem_statement", "").strip()
        root = request.form.get("root_cause", "").strip()
        complaint_id = request.form.get("complaint_id", type=int) or None
        whys = [request.form.get(f"why{i}", "").strip() for i in range(1, 6)]
        whys = [why for why in whys if why]
        if len(problem) < 5 or len(problem) > 500 or len(root) < 5 or len(root) > 2000 or any(len(v) > 1500 for v in whys):
            flash("Enter a clear problem and root cause. Each field must fit its limit.", "danger")
        elif complaint_id and not db.session.get(Complaint, complaint_id):
            flash("Select an existing complaint or leave it blank.", "danger")
        else:
            item = RootCauseAnalysis(
                complaint_id=complaint_id, problem_statement=problem, root_cause=root,
                people=request.form.get("people", "").strip()[:2000],
                processes=request.form.get("processes", "").strip()[:2000],
                technology=request.form.get("technology", "").strip()[:2000],
                materials_resources=request.form.get("materials_resources", "").strip()[:2000],
                environment=request.form.get("environment", "").strip()[:2000],
                policies=request.form.get("policies", "").strip()[:2000],
                whys_json=json.dumps(whys), created_by_id=current_user.id)
            db.session.add(item)
            audit(current_user, "create_root_cause", "rootcauseanalysis", None, problem[:200])
            db.session.commit()
            flash("Root-cause analysis recorded.", "success")
            return redirect(url_for("quality.root_cause"))
    analyses = RootCauseAnalysis.query.order_by(RootCauseAnalysis.created_at.desc()).all()
    complaints_open = Complaint.query.filter(Complaint.status.in_(["open", "in_progress"])).order_by(Complaint.created_at.desc()).all()
    return render_template("root_cause.html", analyses=analyses, complaints=complaints_open)


@bp.route("/actions", methods=["GET", "POST"])
@roles_required("admin", "quality_manager")
def actions():
    if request.method == "POST":
        from datetime import date
        problem = request.form.get("problem", "").strip()
        root = request.form.get("root_cause", "").strip()
        correction = request.form.get("corrective_action", "").strip()
        owner_id = request.form.get("owner_id", type=int)
        try:
            deadline = date.fromisoformat(request.form.get("deadline", ""))
        except ValueError:
            deadline = None
        owner = db.session.get(User, owner_id) if owner_id else None
        if not problem or len(problem) > 300 or not root or not correction or len(correction) > 3000 or not deadline or not owner or owner.role not in {"admin", "quality_manager"}:
            flash("Enter a problem, root cause, corrective action, valid staff owner, and deadline.", "danger")
        else:
            row = ImprovementAction(problem=problem, root_cause=root, corrective_action=correction,
                                    owner_id=owner_id, deadline=deadline, created_by_id=current_user.id)
            db.session.add(row)
            db.session.flush()
            audit(current_user, "create_improvement_action", "improvement_action", row.id)
            db.session.commit()
            flash("Improvement action assigned.", "success")
            return redirect(url_for("quality.actions"))
    query = ImprovementAction.query
    search = request.args.get("q", "").strip()[:120]
    status_filter = request.args.get("status", "")
    if search:
        pattern = f"%{search}%"
        query = query.outerjoin(User, ImprovementAction.owner_id == User.id).filter(
            or_(ImprovementAction.problem.ilike(pattern), ImprovementAction.corrective_action.ilike(pattern), User.full_name.ilike(pattern))
        )
    if status_filter in {"pending", "in_progress", "completed"}:
        query = query.filter(ImprovementAction.status == status_filter)
    rows = query.order_by(ImprovementAction.deadline, ImprovementAction.id).paginate(
        page=request.args.get("page", 1, type=int), per_page=20, error_out=False)
    status_counts = dict(db.session.query(ImprovementAction.status, func.count(ImprovementAction.id)).group_by(ImprovementAction.status).all())
    owners = User.query.filter(User.role.in_(["admin", "quality_manager"]), User.active.is_(True)).order_by(User.full_name).all()
    return render_template("actions.html", pagination=rows, actions=rows.items, owners=owners,
                           status_counts=status_counts, search=search, selected_status=status_filter)


@bp.post("/actions/<int:action_id>/status")
@roles_required("admin", "quality_manager")
def action_status(action_id):
    row = db.get_or_404(ImprovementAction, action_id)
    status = request.form.get("status")
    if status not in {"pending", "in_progress", "completed"}:
        flash("Choose a valid action status.", "danger")
    else:
        row.status = status
        row.completed_at = utcnow() if status == "completed" else None
        audit(current_user, "update_improvement_action", "improvement_action", row.id, status)
        db.session.commit()
        flash("Improvement action updated.", "success")
    return redirect(url_for("quality.actions"))


@bp.route("/pdca", methods=["GET", "POST"])
@roles_required("admin", "quality_manager")
def pdca():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        problem = request.form.get("problem", "").strip()
        target = request.form.get("measurable_target", "").strip()
        baseline = request.form.get("baseline", "").strip()
        plan = request.form.get("plan", "").strip()
        if not all([title, problem, target, baseline, plan]) or max(map(len, [title, problem, target, baseline, plan])) > 2000:
            flash("Complete the problem, measurable target, baseline, and plan fields.", "danger")
        else:
            row = PdcaCycle(title=title[:180], problem=problem, measurable_target=target[:300], baseline=baseline[:160], plan=plan, owner_id=current_user.id)
            db.session.add(row)
            db.session.flush()
            audit(current_user, "create_pdca_cycle", "pdca_cycle", row.id, "plan")
            db.session.commit()
            flash("PDCA cycle started in Plan.", "success")
            return redirect(url_for("quality.pdca"))
    cycles = PdcaCycle.query.order_by(PdcaCycle.started_at.desc()).all()
    return render_template("pdca.html", cycles=cycles)


@bp.post("/pdca/<int:cycle_id>/advance")
@roles_required("admin", "quality_manager")
def pdca_advance(cycle_id):
    cycle = db.get_or_404(PdcaCycle, cycle_id)
    next_phase = request.form.get("phase")
    expected = {"plan": "do", "do": "check", "check": "act", "act": "complete"}
    if expected.get(cycle.phase) != next_phase:
        flash("PDCA stages must be completed in Plan → Do → Check → Act order.", "danger")
        return redirect(url_for("quality.pdca"))
    field_for_phase = {"do": "do_notes", "check": "check_result", "act": "act_decision"}
    if next_phase == "complete":
        decision = cycle.act_decision.strip()
        if len(decision) < 10:
            flash("Record the Act decision before completing the cycle.", "danger")
            return redirect(url_for("quality.pdca"))
        cycle.outcome = request.form.get("outcome", "").strip()[:300]
        cycle.completed_at = utcnow()
    else:
        value = request.form.get(field_for_phase[next_phase], "").strip()
        if len(value) < 5 or len(value) > 3000:
            flash("Enter a meaningful stage result (5–3,000 characters).", "danger")
            return redirect(url_for("quality.pdca"))
        setattr(cycle, field_for_phase[next_phase], value)
    cycle.phase = next_phase
    audit(current_user, "advance_pdca", "pdca_cycle", cycle.id, next_phase)
    db.session.commit()
    flash(f"PDCA cycle moved to {next_phase.title()}.", "success")
    return redirect(url_for("quality.pdca"))


@bp.route("/inventory-audit", methods=["GET", "POST"])
@roles_required("admin", "quality_manager")
def inventory_audit():
    if request.method == "POST":
        checked = request.form.get("checked_copies", type=int)
        matching = request.form.get("matching_copies", type=int)
        notes = request.form.get("notes", "").strip()
        if checked is None or matching is None or checked < 1 or matching < 0 or matching > checked:
            flash("Enter a positive checked count and a matching count from 0 through the checked count.", "danger")
        else:
            row = InventoryAudit(checked_copies=checked, matching_copies=matching, notes=notes[:500], audited_by_id=current_user.id)
            db.session.add(row)
            audit(current_user, "record_inventory_audit", "inventory_audit", None, f"{matching}/{checked}")
            db.session.commit()
            flash("Inventory audit recorded.", "success")
            return redirect(url_for("quality.inventory_audit"))
    rows = InventoryAudit.query.order_by(InventoryAudit.created_at.desc()).all()
    return render_template("inventory_audit.html", audits=rows)


@bp.get("/")
@roles_required("admin", "quality_manager")
def dashboard():
    since = utcnow() - timedelta(days=90)
    satisfaction = time_series_monthly(Feedback, Feedback.created_at, since, lambda row: row.rating)
    borrowing = time_series_monthly(Loan, Loan.issued_at, since)
    complaint_counts = dict(db.session.query(Complaint.category, func.count(Complaint.id)).filter(Complaint.created_at >= since).group_by(Complaint.category).all())
    pareto = pareto_data(90)
    cycles = PdcaCycle.query.order_by(PdcaCycle.started_at.desc()).limit(30).all()
    kpis = kpi_summary(90)
    return render_template("quality_dashboard.html", kpis=kpis, satisfaction=satisfaction, borrowing=borrowing,
                           complaint_counts={CATEGORIES.get(k, k): v for k, v in complaint_counts.items()},
                           pareto=pareto, cycles=cycles)
