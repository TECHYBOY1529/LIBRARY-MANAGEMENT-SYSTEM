from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from time import perf_counter

from flask import current_app
from sqlalchemy import func

from .extensions import db
from .models import (AuditLog, BookCopy, Complaint, Feedback, Fine, ImprovementAction,
                     InventoryAudit, Loan, Notification, PdcaCycle, Reservation, SystemSetting, User, utcnow)
from .time_utils import library_today


def configured_value(key):
    """Read an administrator-managed setting, falling back to validated app config."""
    row = db.session.get(SystemSetting, key)
    raw = row.value if row else current_app.config[key]
    if key == "DEFAULT_LOAN_DAYS":
        return int(raw)
    if key == "FINE_PER_DAY":
        return Decimal(str(raw))
    return raw


def audit(user, action, entity, entity_id=None, detail=""):
    db.session.add(AuditLog(user_id=user.id if user else None, action=action,
                            entity_type=entity, entity_id=entity_id, detail=detail[:500]))


def notify(user_id, title, message, kind="general", reference_key=None):
    if reference_key and Notification.query.filter_by(reference_key=reference_key).first():
        return
    db.session.add(Notification(user_id=user_id, title=title, message=message, kind=kind, reference_key=reference_key))


def issue_book(member_id, book_id, staff_user, loan_days=14, reservation_id=None):
    """Issue an available copy atomically and reject duplicate active loans by title."""
    started = perf_counter()
    try:
        if not isinstance(loan_days, int) or not 1 <= loan_days <= 365:
            raise ValueError("Loan period must be between 1 and 365 days.")
        member = db.session.get(User, member_id)
        if not member or member.role != "member" or not member.active:
            raise ValueError("Select an active library member.")
        active_same_title = db.session.query(Loan.id).join(BookCopy).filter(
            Loan.member_id == member_id, Loan.status == "active", BookCopy.book_id == book_id
        ).first()
        if active_same_title:
            raise ValueError("This member already has an active loan for that title.")
        reservation = None
        if reservation_id:
            reservation = (Reservation.query.filter_by(id=reservation_id, member_id=member_id,
                                                        book_id=book_id, status="ready")
                           .with_for_update().populate_existing().first())
            if not reservation:
                raise ValueError("That reservation is not ready for this member.")
            copy = BookCopy.query.filter_by(book_id=book_id, status="reserved").with_for_update().first()
        else:
            copy = BookCopy.query.filter_by(book_id=book_id, status="available").with_for_update().first()
        if not copy:
            raise ValueError("No available copy remains for this book.")
        copy.status = "loaned"
        loan = Loan(copy_id=copy.id, member_id=member_id, issued_by_id=staff_user.id,
                    due_date=library_today() + timedelta(days=loan_days), status="active")
        db.session.add(loan)
        db.session.flush()
        loan.issue_seconds = max(0, round((perf_counter() - started) * 1000))
        if reservation:
            reservation.status = "fulfilled"
            reservation.fulfilled_at = utcnow()
        notify(member_id, "Book issued", f"{copy.book.title} is due {loan.due_date.isoformat()}.", "due", f"loan:{loan.id}:due")
        audit(staff_user, "issue_book", "loan", loan.id, f"copy={copy.barcode}; member={member_id}")
        db.session.commit()
        return loan
    except Exception:
        db.session.rollback()
        raise


def return_book(loan_id, staff_user, fine_per_day=Decimal("1.00")):
    """Return one active loan, assess fine and release/allocate its copy in one transaction."""
    try:
        try:
            fine_per_day = Decimal(str(fine_per_day))
        except InvalidOperation as error:
            raise ValueError("Daily fine rate must be a valid amount.") from error
        if not fine_per_day.is_finite() or fine_per_day < 0:
            raise ValueError("Daily fine rate cannot be negative.")
        loan = (db.session.query(Loan).filter_by(id=loan_id)
                .with_for_update().populate_existing().first())
        if not loan or loan.status != "active":
            raise ValueError("That loan is not active and cannot be returned again.")
        loan.returned_at = utcnow()
        loan.returned_to_id = staff_user.id
        loan.status = "returned"
        days_late = max(0, (library_today() - loan.due_date).days)
        amount = (Decimal(days_late) * fine_per_day).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if amount > 0:
            db.session.add(Fine(loan_id=loan.id, amount=amount))
            notify(loan.member_id, "Fine assessed", f"A fine of {amount:.2f} was assessed for a late return.", "fine")
        copy = loan.copy
        waiting = Reservation.query.filter_by(book_id=copy.book_id, status="waiting").order_by(Reservation.created_at).first()
        if waiting:
            waiting.status = "ready"
            waiting.fulfilled_at = utcnow()
            copy.status = "reserved"
            notify(waiting.member_id, "Reserved book ready", f"A copy of {copy.book.title} is ready for pickup.", "reservation", f"reservation:{waiting.id}:ready")
        else:
            copy.status = "available"
        notify(loan.member_id, "Book returned", f"{copy.book.title} has been checked in.", "return")
        audit(staff_user, "return_book", "loan", loan.id, f"fine={amount:.2f}")
        db.session.commit()
        return loan
    except Exception:
        db.session.rollback()
        raise


def refresh_loan_notifications(member_id=None):
    """Create one due-soon/overdue reminder per active loan; safe to call repeatedly."""
    query = Loan.query.filter_by(status="active")
    if member_id is not None:
        query = query.filter_by(member_id=member_id)
    today = library_today()
    for loan in query.all():
        if loan.due_date < today:
            notify(loan.member_id, "Book overdue", f"{loan.copy.book.title} was due {loan.due_date.isoformat()}. Please return it or contact the library.", "overdue", f"loan:{loan.id}:overdue")
        elif loan.due_date <= today + timedelta(days=3):
            notify(loan.member_id, "Book due soon", f"{loan.copy.book.title} is due {loan.due_date.isoformat()}.", "due", f"loan:{loan.id}:due")
    db.session.commit()


def cancel_reservation(reservation_id, actor):
    """Cancel a waiting/ready reservation and release or reassign its held copy safely."""
    try:
        reservation = db.session.query(Reservation).filter_by(id=reservation_id).with_for_update().first()
        if not reservation or reservation.status not in {"waiting", "ready"}:
            raise ValueError("Only a waiting or ready reservation can be cancelled.")
        was_ready = reservation.status == "ready"
        reservation.status = "cancelled"
        if was_ready:
            copy = BookCopy.query.filter_by(book_id=reservation.book_id, status="reserved").order_by(BookCopy.id).first()
            next_in_queue = Reservation.query.filter_by(book_id=reservation.book_id, status="waiting").order_by(Reservation.created_at).first()
            if copy and next_in_queue:
                next_in_queue.status = "ready"
                next_in_queue.fulfilled_at = utcnow()
                notify(next_in_queue.member_id, "Reserved book ready", f"A copy of {copy.book.title} is ready for pickup.", "reservation", f"reservation:{next_in_queue.id}:ready")
            elif copy:
                copy.status = "available"
        audit(actor, "cancel_reservation", "reservation", reservation.id, reservation.book.title)
        db.session.commit()
        return reservation
    except Exception:
        db.session.rollback()
        raise


def kpi_summary(days=90, start_date=None, end_date=None):
    """Calculate current KPIs from records in the trailing period; absent samples are None."""
    if start_date and end_date:
        since = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        until = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        days = (end_date - start_date).days + 1
    else:
        since = utcnow() - timedelta(days=days)
        until = None
    def in_window(field):
        return [field >= since, field < until] if until else [field >= since]
    feedback = Feedback.query.filter(*in_window(Feedback.created_at)).all()
    loans = Loan.query.filter(*in_window(Loan.issued_at)).all()
    active_loans = Loan.query.filter_by(status="active").all()
    requests = Reservation.query.filter(*in_window(Reservation.created_at)).all()
    resolved = Complaint.query.filter(Complaint.status.in_(["resolved", "closed"]), Complaint.resolved_at.isnot(None), *in_window(Complaint.created_at)).all()
    total_complaints = Complaint.query.filter(*in_window(Complaint.created_at)).count()
    closed_count = len(resolved)
    actions = ImprovementAction.query.filter(ImprovementAction.status == "completed", *in_window(ImprovementAction.completed_at)).all()
    audit_records = InventoryAudit.query.filter(*in_window(InventoryAudit.created_at)).all()
    count_total = sum(a.checked_copies for a in audit_records)
    count_matching = sum(a.matching_copies for a in audit_records)
    return {
        "period_days": days,
        "satisfaction": round(sum(f.rating for f in feedback) / len(feedback), 2) if feedback else None,
        "availability_when_requested_pct": round(100 * sum(r.available_at_request for r in requests) / len(requests), 1) if requests else None,
        "avg_issue_processing_ms": round(sum(l.issue_seconds for l in loans if l.issue_seconds is not None) / len([l for l in loans if l.issue_seconds is not None]), 1) if any(l.issue_seconds is not None for l in loans) else None,
        "avg_complaint_resolution_days": round(sum((c.resolved_at - c.created_at).total_seconds() / 86400 for c in resolved) / len(resolved), 1) if resolved else None,
        "complaint_resolution_rate_pct": round(100 * closed_count / total_complaints, 1) if total_complaints else None,
        "overdue_loan_rate_pct": round(100 * sum(l.due_date < library_today() for l in active_loans) / len(active_loans), 1) if active_loans else None,
        "inventory_accuracy_pct": round(100 * count_matching / count_total, 1) if count_total else None,
        "actions_on_time_pct": round(100 * sum(a.completed_at.date() <= a.deadline for a in actions) / len(actions), 1) if actions else None,
        "borrowing_count": len(loans),
        "active_loans_count": len(active_loans),
        "data_sources": {
            "satisfaction": "Feedback ratings submitted in the trailing period; arithmetic mean, 1–5.",
            "availability_when_requested_pct": "Reservations created in the period; available copies at submission / all reservation requests. Proxy for availability on request.",
            "avg_issue_processing_ms": "Recorded server-side issue workflow duration for loans issued in the period; milliseconds.",
            "avg_complaint_resolution_days": "Resolved complaints created in the period; mean elapsed days from submission to resolution.",
            "complaint_resolution_rate_pct": "Complaints created in the period resolved or closed / all complaints created in the period.",
            "overdue_loan_rate_pct": "Active loans past due today / all currently active loans. Point-in-time rate.",
            "inventory_accuracy_pct": "Copies matching / copies checked in inventory audits recorded in the period.",
            "actions_on_time_pct": "Improvement actions completed in the period by deadline / all actions completed in the period.",
            "borrowing_count": "Loans issued in the trailing period.",
        }
    }


def time_series_monthly(model, field, since, value_fn=None, until=None):
    query = model.query.filter(field >= since)
    if until:
        query = query.filter(field < until)
    records = query.all()
    buckets = {}
    for record in records:
        dt = getattr(record, field.key)
        label = dt.strftime("%Y-%m")
        buckets.setdefault(label, []).append(value_fn(record) if value_fn else 1)
    labels = sorted(buckets)
    return {"labels": labels, "values": [round(sum(buckets[label]) / len(buckets[label]), 2) if value_fn else len(buckets[label]) for label in labels]}


def pareto_data(days=90, start_date=None, end_date=None):
    if start_date and end_date:
        since = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        until = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    else:
        since = utcnow() - timedelta(days=days)
        until = None
    complaint_query = db.session.query(Complaint.category, func.count(Complaint.id)).filter(Complaint.created_at >= since)
    feedback_query = db.session.query(Feedback.category, func.count(Feedback.id)).filter(Feedback.created_at >= since)
    if until:
        complaint_query = complaint_query.filter(Complaint.created_at < until)
        feedback_query = feedback_query.filter(Feedback.created_at < until)
    rows = complaint_query.group_by(Complaint.category).all()
    counts = dict(rows)
    fb = feedback_query.group_by(Feedback.category).all()
    for category, count in fb:
        counts[category] = counts.get(category, 0) + count
    sorted_items = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    total = sum(count for _, count in sorted_items)
    cumulative = 0
    return {"labels": [k.replace("_", " ").title() for k, _ in sorted_items],
            "counts": [v for _, v in sorted_items],
            "cumulative": [round((cumulative := cumulative + v) * 100 / total, 1) if total else 0 for _, v in sorted_items],
            "priority_category": sorted_items[0][0] if sorted_items else None,
            "total": total}
