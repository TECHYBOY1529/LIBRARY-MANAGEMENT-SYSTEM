import csv
import io
from datetime import date, timedelta

from flask import Blueprint, Response, render_template
from .models import Book, Complaint, Fine, Loan, User, utcnow
from .security import roles_required
from .services import kpi_summary, pareto_data, time_series_monthly

bp = Blueprint("reports", __name__)


@bp.get("/")
@roles_required("admin", "quality_manager")
def index():
    return render_template("reports.html")


def csv_response(filename, headers, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    def safe_cell(value):
        if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
            return "'" + value
        return value
    writer.writerows([[safe_cell(value) for value in row] for row in rows])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@bp.get("/inventory.csv")
@roles_required("admin", "quality_manager")
def inventory_csv():
    rows = Book.query.order_by(Book.title).all()
    return csv_response("inventory-report.csv", ["ISBN", "Title", "Author", "Category", "Publisher", "Year", "Total copies", "Available copies"],
                        [[b.isbn, b.title, b.author.name, b.category.name, b.publisher.name, b.publication_year, b.total_copies, b.available_copies] for b in rows])


@bp.get("/loans.csv")
@roles_required("admin")
def loans_csv():
    rows = Loan.query.order_by(Loan.issued_at.desc()).all()
    return csv_response("borrowing-report.csv", ["Loan ID", "Member", "ISBN", "Title", "Issued", "Due", "Returned", "Status", "Issue operation ms"],
                        [[r.id, r.member.full_name, r.copy.book.isbn, r.copy.book.title, r.issued_at.isoformat(), r.due_date.isoformat(), r.returned_at.isoformat() if r.returned_at else "", r.status, r.issue_seconds if r.issue_seconds is not None else ""] for r in rows])


@bp.get("/overdue.csv")
@roles_required("admin")
def overdue_csv():
    rows = Loan.query.filter(Loan.status == "active", Loan.due_date < date.today()).order_by(Loan.due_date).all()
    return csv_response("overdue-report.csv", ["Loan ID", "Member", "Email", "Title", "Due date", "Days overdue"],
                        [[r.id, r.member.full_name, r.member.email, r.copy.book.title, r.due_date.isoformat(), (date.today() - r.due_date).days] for r in rows])


@bp.get("/fines.csv")
@roles_required("admin")
def fines_csv():
    rows = Fine.query.join(Loan).order_by(Fine.assessed_at.desc()).all()
    return csv_response("fines-report.csv", ["Fine ID", "Member", "Title", "Amount", "Paid", "Assessed"],
                        [[r.id, r.loan.member.full_name, r.loan.copy.book.title, str(r.amount), r.paid, r.assessed_at.isoformat()] for r in rows])


@bp.get("/members.csv")
@roles_required("admin")
def members_csv():
    rows = User.query.filter_by(role="member").order_by(User.full_name).all()
    return csv_response("member-activity-report.csv", ["Member ID", "Name", "Email", "Active", "Loans", "Open complaints"],
                        [[r.id, r.full_name, r.email, r.active, Loan.query.filter_by(member_id=r.id).count(), Complaint.query.filter_by(member_id=r.id).filter(Complaint.status.in_(["open", "in_progress"])).count()] for r in rows])


@bp.get("/quality.csv")
@roles_required("admin", "quality_manager")
def quality_csv():
    summary = kpi_summary(90)
    labels = {
        "satisfaction": ("Average customer satisfaction", "/ 5"),
        "availability_when_requested_pct": ("Available when requested", "%"),
        "avg_issue_processing_ms": ("Average issue operation time", "ms"),
        "avg_complaint_resolution_days": ("Average complaint resolution time", "days"),
        "complaint_resolution_rate_pct": ("Complaint resolution rate", "%"),
        "overdue_loan_rate_pct": ("Overdue loan rate", "%"),
        "inventory_accuracy_pct": ("Inventory accuracy", "%"),
        "actions_on_time_pct": ("Actions completed on time", "%"),
        "borrowing_count": ("Borrowing activity", "loans"),
    }
    rows = [[label, summary[key] if summary[key] is not None else "Insufficient data", unit,
             "Point-in-time" if key == "overdue_loan_rate_pct" else "90 days",
             summary["data_sources"][key]] for key, (label, unit) in labels.items()]
    return csv_response("quality-kpi-report.csv", ["KPI", "Value", "Unit", "Reporting period", "Formula / data source"], rows)


@bp.get("/pareto.csv")
@roles_required("admin", "quality_manager")
def pareto_csv():
    data = pareto_data(90)
    rows = [[label, count, cumulative, data["priority_category"] == label.lower().replace(" ", "_")]
            for label, count, cumulative in zip(data["labels"], data["counts"], data["cumulative"])]
    return csv_response("problem-pareto-report.csv", ["Category", "Problem count", "Cumulative percent", "Most frequent"], rows)


@bp.get("/borrowing-trends.csv")
@roles_required("admin", "quality_manager")
def borrowing_trends_csv():
    since = utcnow() - timedelta(days=90)
    data = time_series_monthly(Loan, Loan.issued_at, since)
    return csv_response("borrowing-trends.csv", ["Month", "Loans issued"], zip(data["labels"], data["values"]))
