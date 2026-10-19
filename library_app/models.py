from datetime import datetime, timezone

from flask import session
from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager
from .time_utils import library_today


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    auth_version = db.Column(db.Integer, nullable=False, default=0, server_default=db.text("0"))
    role = db.Column(db.String(20), nullable=False, default="member", index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (CheckConstraint("role IN ('admin', 'member', 'quality_manager')", name="ck_user_role"),)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    if not user or not user.active:
        return None
    if session.get("_auth_version") != user.auth_version:
        session.pop("_user_id", None)
        session.pop("_fresh", None)
        session.pop("_auth_version", None)
        return None
    return user


class Author(db.Model):
    __tablename__ = "authors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)


class Publisher(db.Model):
    __tablename__ = "publishers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)


class Book(db.Model):
    __tablename__ = "books"
    id = db.Column(db.Integer, primary_key=True)
    isbn = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(240), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("authors.id", ondelete="RESTRICT"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    publisher_id = db.Column(db.Integer, db.ForeignKey("publishers.id", ondelete="RESTRICT"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)
    semester = db.Column(db.Integer, nullable=True)
    publication_year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    author = db.relationship(Author)
    category = db.relationship(Category)
    publisher = db.relationship(Publisher)
    course = db.relationship(Course)
    copies = db.relationship("BookCopy", back_populates="book", cascade="all, delete-orphan")
    @property
    def total_copies(self):
        return len(self.copies)
    @property
    def available_copies(self):
        return sum(copy.status == "available" for copy in self.copies)
    __table_args__ = (Index("ix_book_category_title", "category_id", "title"),
                      CheckConstraint("semester IS NULL OR semester BETWEEN 1 AND 12", name="ck_book_semester_range"))


class BookCopy(db.Model):
    __tablename__ = "book_copies"
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    barcode = db.Column(db.String(50), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="available", index=True)
    acquired_at = db.Column(db.Date, nullable=False, default=library_today)
    book = db.relationship(Book, back_populates="copies")
    __table_args__ = (CheckConstraint("status IN ('available', 'loaned', 'reserved', 'maintenance', 'lost')", name="ck_copy_status"),
                      Index("ix_bookcopy_book_status", "book_id", "status"))


class Loan(db.Model):
    __tablename__ = "loans"
    id = db.Column(db.Integer, primary_key=True)
    copy_id = db.Column(db.Integer, db.ForeignKey("book_copies.id", ondelete="RESTRICT"), nullable=False, index=True)
    member_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    issued_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    returned_to_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    issued_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    due_date = db.Column(db.Date, nullable=False, index=True)
    returned_at = db.Column(db.DateTime)
    issue_seconds = db.Column(db.Integer)
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    copy = db.relationship(BookCopy)
    member = db.relationship(User, foreign_keys=[member_id])
    issued_by = db.relationship(User, foreign_keys=[issued_by_id])
    returned_to = db.relationship(User, foreign_keys=[returned_to_id])
    fine = db.relationship("Fine", back_populates="loan", uselist=False, cascade="all, delete-orphan")
    __table_args__ = (
        CheckConstraint("status IN ('active', 'returned')", name="ck_loan_status"),
        Index("ix_loan_status_due_date", "status", "due_date"),
        Index("ix_loan_issued_at", "issued_at"),
        Index("uq_active_copy_loan", "copy_id", unique=True,
              sqlite_where=db.text("status = 'active'"),
              postgresql_where=db.text("status = 'active'")),
    )


class Reservation(db.Model):
    __tablename__ = "reservations"
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="waiting", index=True)
    available_at_request = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    fulfilled_at = db.Column(db.DateTime)
    book = db.relationship(Book)
    member = db.relationship(User)
    __table_args__ = (
        CheckConstraint("status IN ('waiting', 'ready', 'fulfilled', 'cancelled')", name="ck_reservation_status"),
        Index("uq_waiting_reservation", "book_id", "member_id", unique=True,
              sqlite_where=db.text("status IN ('waiting','ready')"),
              postgresql_where=db.text("status IN ('waiting','ready')")),
    )


class Fine(db.Model):
    __tablename__ = "fines"
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loans.id", ondelete="CASCADE"), unique=True, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    paid = db.Column(db.Boolean, nullable=False, default=False)
    assessed_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    loan = db.relationship(Loan, back_populates="fine")
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_fine_nonnegative"),)


class Feedback(db.Model):
    __tablename__ = "feedback"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    category = db.Column(db.String(40), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    comments = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    member = db.relationship(User)
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
        CheckConstraint("category IN ('book_availability','staff_service','waiting_time','cleanliness','digital_access','other')", name="ck_feedback_category"),
    )


class Complaint(db.Model):
    __tablename__ = "complaints"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    category = db.Column(db.String(40), nullable=False, index=True)
    subject = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    resolved_at = db.Column(db.DateTime)
    member = db.relationship(User)
    __table_args__ = (
        CheckConstraint("status IN ('open','in_progress','resolved','closed')", name="ck_complaint_status"),
        CheckConstraint("category IN ('book_availability','staff_service','waiting_time','cleanliness','digital_access','other')", name="ck_complaint_category"),
    )


class RootCauseAnalysis(db.Model):
    __tablename__ = "rootcauseanalyses"
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id", ondelete="SET NULL"), index=True)
    problem_statement = db.Column(db.String(500), nullable=False)
    people = db.Column(db.Text, default="")
    processes = db.Column(db.Text, default="")
    technology = db.Column(db.Text, default="")
    materials_resources = db.Column(db.Text, default="")
    environment = db.Column(db.Text, default="")
    policies = db.Column(db.Text, default="")
    whys_json = db.Column(db.Text, default="[]")
    root_cause = db.Column(db.Text, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    complaint = db.relationship(Complaint)
    created_by = db.relationship(User)


class ImprovementAction(db.Model):
    __tablename__ = "improvement_actions"
    id = db.Column(db.Integer, primary_key=True)
    problem = db.Column(db.String(300), nullable=False)
    root_cause = db.Column(db.Text, nullable=False)
    corrective_action = db.Column(db.Text, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    deadline = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    completed_at = db.Column(db.DateTime)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    owner = db.relationship(User, foreign_keys=[owner_id])
    created_by = db.relationship(User, foreign_keys=[created_by_id])
    __table_args__ = (CheckConstraint("status IN ('pending','in_progress','completed')", name="ck_action_status"),)


class PdcaCycle(db.Model):
    __tablename__ = "pdca_cycles"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    problem = db.Column(db.Text, nullable=False)
    measurable_target = db.Column(db.String(300), nullable=False)
    baseline = db.Column(db.String(160), nullable=False)
    plan = db.Column(db.Text, nullable=False)
    do_notes = db.Column(db.Text, default="")
    check_result = db.Column(db.Text, default="")
    act_decision = db.Column(db.Text, default="")
    phase = db.Column(db.String(10), nullable=False, default="plan", index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime)
    outcome = db.Column(db.String(300), default="")
    owner = db.relationship(User)
    __table_args__ = (CheckConstraint("phase IN ('plan','do','check','act','complete')", name="ck_pdca_phase"),)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer)
    detail = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    user = db.relationship(User)


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    kind = db.Column(db.String(30), nullable=False, default="general")
    reference_key = db.Column(db.String(120), unique=True)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    user = db.relationship(User)


class InventoryAudit(db.Model):
    __tablename__ = "inventory_audits"
    id = db.Column(db.Integer, primary_key=True)
    checked_copies = db.Column(db.Integer, nullable=False)
    matching_copies = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.String(500), default="")
    audited_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    audited_by = db.relationship(User)
    __table_args__ = (
        CheckConstraint("checked_copies > 0", name="ck_audit_checked_positive"),
        CheckConstraint("matching_copies >= 0 AND matching_copies <= checked_copies", name="ck_audit_matches_range"),
    )


class SystemSetting(db.Model):
    __tablename__ = "system_settings"
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.String(500), nullable=False)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    updated_by = db.relationship(User)


class InstitutionalLibraryFact(db.Model):
    """Public, source-attributed institutional facts; separate from live inventory."""
    __tablename__ = "institutional_library_facts"
    fact_key = db.Column(db.String(120), primary_key=True)
    fact_value = db.Column(db.Text, nullable=False)
    source_url = db.Column(db.String(500), nullable=False)
    source_checked_on = db.Column(db.Date, nullable=False)
    source_note = db.Column(db.Text, nullable=False, default="")


class BugIncident(db.Model):
    __tablename__ = "bug_incidents"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(12), nullable=False, default="medium", index=True)
    status = db.Column(db.String(16), nullable=False, default="open", index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    resolved_at = db.Column(db.DateTime)
    created_by = db.relationship(User)
    __table_args__ = (
        CheckConstraint("severity IN ('low','medium','high')", name="ck_bug_incident_severity"),
        CheckConstraint("status IN ('open','in_progress','resolved')", name="ck_bug_incident_status"),
    )


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime)
    user = db.relationship(User)


class CatalogImportBatch(db.Model):
    __tablename__ = "catalog_import_batches"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    rows_json = db.Column(db.Text, nullable=False)
    row_errors_json = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    imported_at = db.Column(db.DateTime)
    owner = db.relationship(User)
