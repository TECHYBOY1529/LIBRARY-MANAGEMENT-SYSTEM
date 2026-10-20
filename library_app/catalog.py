import csv
import io
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import contains_eager, selectinload
from werkzeug.utils import secure_filename

from .extensions import db
from .models import Author, Book, BookCopy, CatalogImportBatch, Category, Course, Loan, Publisher, Reservation, User, utcnow
from .security import roles_required
from .services import audit, cancel_reservation, configured_value, issue_book, return_book
from .time_utils import library_today

bp = Blueprint("catalog", __name__)
LOOKUPS = {"authors": Author, "categories": Category, "publishers": Publisher, "courses": Course}
MAX_IMPORT_TOTAL_COPIES = 10_000


def is_valid_isbn(value):
    """Return whether an ISBN-10 or ISBN-13 has a valid check digit."""
    normalized = re.sub(r"[-\s]", "", value).upper()
    if re.fullmatch(r"\d{9}[\dX]", normalized):
        checksum = sum((10 - index) * (10 if digit == "X" else int(digit))
                       for index, digit in enumerate(normalized))
        return checksum % 11 == 0
    if re.fullmatch(r"\d{13}", normalized):
        checksum = sum(int(digit) * (1 if index % 2 == 0 else 3)
                       for index, digit in enumerate(normalized[:12]))
        return (10 - checksum % 10) % 10 == int(normalized[-1])
    return False


@bp.get("/books")
@login_required
def books():
    query = (Book.query.join(Book.author).join(Book.category).join(Book.publisher).outerjoin(Book.course)
             .options(contains_eager(Book.author), contains_eager(Book.category), contains_eager(Book.publisher),
                      contains_eager(Book.course), selectinload(Book.copies)))
    q = request.args.get("q", "").strip()[:120]
    category_id = request.args.get("category", type=int)
    course_id = request.args.get("course", type=int)
    semester = request.args.get("semester", type=int)
    if semester is not None and not 1 <= semester <= 12:
        semester = None
    availability = request.args.get("availability", "")
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Book.title.ilike(like), Book.isbn.ilike(like), Author.name.ilike(like),
                                    Category.name.ilike(like), Publisher.name.ilike(like), Course.name.ilike(like)))
    if category_id:
        query = query.filter(Book.category_id == category_id)
    if course_id:
        query = query.filter(Book.course_id == course_id)
    if semester and 1 <= semester <= 12:
        query = query.filter(Book.semester == semester)
    if availability == "available":
        query = query.filter(Book.copies.any(status="available"))
    elif availability == "unavailable":
        query = query.filter(~Book.copies.any(status="available"))
    sort = request.args.get("sort", "title")
    ordering = {"title": Book.title.asc(), "year_desc": Book.publication_year.desc(),
                "year_asc": Book.publication_year.asc(), "author": Author.name.asc()}.get(sort, Book.title.asc())
    pagination = query.order_by(ordering, Book.id.asc()).paginate(page=request.args.get("page", 1, type=int), per_page=15, error_out=False)
    return render_template("books.html", pagination=pagination,
                           categories=Category.query.order_by(Category.name).all(),
                           courses=Course.query.order_by(Course.name).all(), q=q, sort=sort,
                           category_id=category_id, course_id=course_id, semester=semester,
                           availability=availability)


def _validated_import_rows(rows):
    valid, errors, seen = [], [], set()
    accepted_copy_count = 0
    known_authors = {item.name.casefold(): item.id for item in Author.query.all()}
    known_categories = {item.name.casefold(): item.id for item in Category.query.all()}
    known_publishers = {item.name.casefold(): item.id for item in Publisher.query.all()}
    known_courses = {item.name.casefold(): item.id for item in Course.query.all()}
    existing_isbns = {re.sub(r"[-\s]", "", value).upper() for (value,) in db.session.query(Book.isbn).all()}
    for line, raw in enumerate(rows, start=2):
        data = {str(key or "").strip().lower(): str(value or "").strip() for key, value in raw.items()}
        isbn, title = data.get("isbn", ""), data.get("title", "")
        normalized = re.sub(r"[-\s]", "", isbn).upper()
        issues = []
        if not is_valid_isbn(isbn): issues.append("invalid ISBN")
        if not title or len(title) > 240: issues.append("title is required (maximum 240 characters)")
        try: year = int(data.get("publication_year", ""))
        except (TypeError, ValueError): year = 0
        if year < 1450 or year > library_today().year + 1: issues.append("invalid publication year")
        try: copies = int(data.get("copies", ""))
        except (TypeError, ValueError): copies = 0
        if not 1 <= copies <= 500: issues.append("copies must be between 1 and 500")
        elif accepted_copy_count + copies > MAX_IMPORT_TOTAL_COPIES:
            issues.append(f"an import can include at most {MAX_IMPORT_TOTAL_COPIES:,} copies in total")
        author_id = known_authors.get(data.get("author", "").casefold())
        category_name = (data.get("category") or data.get("subject", "")).strip()
        category_id = known_categories.get(category_name.casefold())
        publisher_id = known_publishers.get(data.get("publisher", "").casefold())
        course_name = data.get("course", "").strip().casefold()
        course_id = known_courses.get(course_name) if course_name else None
        semester_text = data.get("semester", "").strip()
        try: semester = int(semester_text) if semester_text else None
        except ValueError: semester = 0
        if bool(course_name) != bool(semester_text): issues.append("course and semester must be supplied together")
        if not author_id: issues.append("author must already exist in catalog metadata")
        if not category_id: issues.append("category must already exist in catalog metadata")
        if not publisher_id: issues.append("publisher must already exist in catalog metadata")
        if course_name and not course_id: issues.append("course must already exist in catalog metadata")
        if semester is not None and not 1 <= semester <= 12: issues.append("semester must be between 1 and 12")
        if normalized in seen or normalized in existing_isbns: issues.append("duplicate ISBN")
        seen.add(normalized)
        if issues:
            errors.append({"line": line, "isbn": isbn, "messages": issues})
        else:
            accepted_copy_count += copies
            valid.append({"isbn": normalized, "title": title, "publication_year": year, "copies": copies,
                          "author_id": author_id, "category_id": category_id, "publisher_id": publisher_id,
                          "course_id": course_id, "course_name": data.get("course", "").strip(),
                          "category_name": category_name, "semester": semester})
    return valid, errors


@bp.route("/books/import", methods=["GET", "POST"])
@roles_required("admin")
def books_import():
    if request.method == "POST" and request.form.get("action") == "upload":
        upload = request.files.get("file")
        if not upload or not upload.filename or not upload.filename.lower().endswith(".csv"):
            flash("Choose a CSV file to import.", "danger")
            return redirect(url_for("catalog.books_import"))
        content = upload.stream.read(2 * 1024 * 1024 + 1)
        if len(content) > 2 * 1024 * 1024:
            flash("The CSV file must be no larger than 2 MB.", "danger")
            return redirect(url_for("catalog.books_import"))
        try:
            reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
            expected = {"isbn", "title", "author", "publisher", "publication_year", "copies"}
            headers = {str(item or "").strip().lower() for item in (reader.fieldnames or [])}
            if not expected.issubset(headers) or not ({"category", "subject"} & headers): raise ValueError("CSV needs these columns: ISBN, title, author, subject (or category), publisher, publication_year, copies. Course and semester are optional.")
            source_rows = list(reader)
            if not source_rows: raise ValueError("The CSV contains no book rows.")
            if len(source_rows) > 500: raise ValueError("Import up to 500 book rows at a time.")
            valid, errors = _validated_import_rows(source_rows)
        except (UnicodeDecodeError, csv.Error, ValueError) as error:
            flash(str(error) or "The CSV file could not be read. Save it as UTF-8 and try again.", "danger")
            return redirect(url_for("catalog.books_import"))
        batch = CatalogImportBatch(owner_id=current_user.id, filename=secure_filename(upload.filename)[:255] or "catalog.csv",
                                   rows_json=json.dumps(valid), row_errors_json=json.dumps(errors),
                                   expires_at=utcnow() + timedelta(minutes=30))
        db.session.add(batch)
        db.session.commit()
        return render_template("catalog_import.html", batch=batch, preview=json.loads(batch.rows_json), errors=json.loads(batch.row_errors_json))
    batch_id = request.form.get("batch_id", type=int) if request.method == "POST" else request.args.get("batch_id", type=int)
    if request.method == "POST" and request.form.get("action") == "import":
        batch = CatalogImportBatch.query.filter_by(id=batch_id, owner_id=current_user.id).first_or_404()
        expires = batch.expires_at.replace(tzinfo=timezone.utc) if batch.expires_at.tzinfo is None else batch.expires_at
        if batch.imported_at or expires <= utcnow():
            flash("This preview has expired or has already been imported. Upload the file again.", "warning")
            return redirect(url_for("catalog.books_import"))
        rows = json.loads(batch.rows_json)
        errors = json.loads(batch.row_errors_json)
        if errors or not rows:
            flash("Fix every row error and upload the corrected CSV before importing.", "danger")
            return redirect(url_for("catalog.books_import", batch_id=batch.id))
        try:
            existing_isbns = {re.sub(r"[-\s]", "", value).upper() for (value,) in db.session.query(Book.isbn).all()}
            for data in rows:
                if data["isbn"] in existing_isbns:
                    raise ValueError(f"ISBN {data['isbn']} was added after this preview. Upload the file again to refresh validation.")
                book = Book(isbn=data["isbn"], title=data["title"], publication_year=data["publication_year"],
                            author_id=data["author_id"], category_id=data["category_id"], publisher_id=data["publisher_id"],
                            course_id=data.get("course_id"), semester=data.get("semester"))
                db.session.add(book)
                db.session.flush()
                for _ in range(data["copies"]):
                    db.session.add(BookCopy(book_id=book.id, barcode=f"LIB-{book.id:05d}-{uuid.uuid4().hex[:8].upper()}"))
                audit(current_user, "import_book", "book", book.id, f"batch={batch.id}; copies={data['copies']}")
            batch.imported_at = utcnow()
            db.session.commit()
        except (ValueError, IntegrityError) as error:
            db.session.rollback()
            flash(str(error) if isinstance(error, ValueError) else "An ISBN or barcode changed during import. No rows were imported; upload the CSV again.", "danger")
            return redirect(url_for("catalog.books_import"))
        flash(f"Imported {len(rows)} titles and their copies.", "success")
        return redirect(url_for("catalog.books"))
    if batch_id:
        batch = CatalogImportBatch.query.filter_by(id=batch_id, owner_id=current_user.id).first_or_404()
        expires = batch.expires_at.replace(tzinfo=timezone.utc) if batch.expires_at.tzinfo is None else batch.expires_at
        if expires <= utcnow() or batch.imported_at:
            flash("This preview is no longer available. Upload the CSV again.", "warning")
            return redirect(url_for("catalog.books_import"))
        return render_template("catalog_import.html", batch=batch, preview=json.loads(batch.rows_json), errors=json.loads(batch.row_errors_json))
    return render_template("catalog_import.html", batch=None, preview=[], errors=[])


def book_form_data():
    isbn = re.sub(r"[-\s]", "", request.form.get("isbn", "")).upper()
    title = request.form.get("title", "").strip()
    year = request.form.get("publication_year", type=int)
    author_id = request.form.get("author_id", type=int)
    category_id = request.form.get("category_id", type=int)
    publisher_id = request.form.get("publisher_id", type=int)
    course_id = request.form.get("course_id", type=int)
    semester = request.form.get("semester", type=int)
    if not is_valid_isbn(isbn):
        raise ValueError("Enter a valid ISBN (10 or 13 digits, hyphens allowed).")
    if not title or len(title) > 240:
        raise ValueError("Title is required and must be at most 240 characters.")
    if not year or year < 1450 or year > library_today().year + 1:
        raise ValueError("Enter a valid publication year.")
    if not all([db.session.get(Author, author_id), db.session.get(Category, category_id),
                db.session.get(Publisher, publisher_id), db.session.get(Course, course_id)]):
        raise ValueError("Choose an existing author, subject, publisher, and course.")
    if semester is None or not 1 <= semester <= 12:
        raise ValueError("Choose a semester from 1 to 12.")
    return {"isbn": isbn, "title": title, "publication_year": year, "author_id": author_id,
            "category_id": category_id, "publisher_id": publisher_id,
            "course_id": course_id, "semester": semester}


@bp.route("/books/new", methods=["GET", "POST"])
@roles_required("admin")
def book_new():
    if request.method == "POST":
        try:
            data = book_form_data()
            count = request.form.get("copies", 0, type=int)
            if count < 1 or count > 500:
                raise ValueError("Initial copy count must be between 1 and 500.")
            if Book.query.filter_by(isbn=data["isbn"]).first():
                raise ValueError("That ISBN is already in the catalog.")
            book = Book(**data)
            db.session.add(book)
            db.session.flush()
            for index in range(count):
                db.session.add(BookCopy(book_id=book.id, barcode=f"LIB-{book.id:05d}-{index + 1:03d}"))
            audit(current_user, "create_book", "book", book.id, f"ISBN {book.isbn}; {count} copies")
            db.session.commit()
            flash("Book and copies added to the catalog.", "success")
            return redirect(url_for("catalog.books"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("Could not save the book. Check that its ISBN and barcode are unique.", "danger")
    return render_template("book_form.html", book=None, authors=Author.query.order_by(Author.name).all(), categories=Category.query.order_by(Category.name).all(), publishers=Publisher.query.order_by(Publisher.name).all(), courses=Course.query.order_by(Course.name).all())


@bp.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def book_edit(book_id):
    book = db.get_or_404(Book, book_id)
    if request.method == "POST":
        try:
            data = book_form_data()
            if Book.query.filter(Book.isbn == data["isbn"], Book.id != book.id).first():
                raise ValueError("That ISBN is already in the catalog.")
            add_count = request.form.get("add_copies", 0, type=int)
            if add_count < 0 or add_count > 500:
                raise ValueError("Copies to add must be between 0 and 500.")
            for key, value in data.items():
                setattr(book, key, value)
            existing = len(book.copies)
            for index in range(add_count):
                db.session.add(BookCopy(book_id=book.id, barcode=f"LIB-{book.id:05d}-{existing + index + 1:03d}"))
            audit(current_user, "edit_book", "book", book.id, f"added copies={add_count}")
            db.session.commit()
            flash("Book details saved.", "success")
            return redirect(url_for("catalog.books"))
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("Could not save changes. Check the ISBN and generated barcodes.", "danger")
    return render_template("book_form.html", book=book, authors=Author.query.order_by(Author.name).all(), categories=Category.query.order_by(Category.name).all(), publishers=Publisher.query.order_by(Publisher.name).all(), courses=Course.query.order_by(Course.name).all())


@bp.post("/books/<int:book_id>/delete")
@roles_required("admin")
def book_delete(book_id):
    book = db.get_or_404(Book, book_id)
    if Loan.query.join(BookCopy).filter(BookCopy.book_id == book.id).first():
        flash("This title has loan history and cannot be deleted. Mark its copies as lost or in maintenance instead.", "warning")
        return redirect(url_for("catalog.books"))
    title = book.title
    try:
        db.session.delete(book)
        audit(current_user, "delete_book", "book", book.id, title)
        db.session.commit()
        flash("Book removed from the catalog.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("The book could not be deleted because other records refer to it.", "danger")
    return redirect(url_for("catalog.books"))


@bp.route("/metadata/<kind>", methods=["GET", "POST"])
@roles_required("admin")
def metadata(kind):
    model = LOOKUPS.get(kind)
    if not model:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name or len(name) > 160:
            flash("Enter a name no longer than 160 characters.", "danger")
        else:
            item_id = request.form.get("item_id", type=int)
            item = db.session.get(model, item_id) if item_id else model()
            if not item:
                abort(404)
            item.name = name
            db.session.add(item)
            audit(current_user, "save_metadata", kind, item.id, name)
            try:
                db.session.commit()
                flash("Saved.", "success")
            except IntegrityError:
                db.session.rollback()
                flash("That name already exists or is in use.", "danger")
        return redirect(url_for("catalog.metadata", kind=kind))
    edit_id = request.args.get("edit", type=int)
    editing = db.session.get(model, edit_id) if edit_id else None
    return render_template("metadata.html", kind=kind, items=model.query.order_by(model.name).all(), editing=editing)


@bp.post("/metadata/<kind>/<int:item_id>/delete")
@roles_required("admin")
def metadata_delete(kind, item_id):
    model = LOOKUPS.get(kind)
    if not model:
        abort(404)
    item = db.session.get(model, item_id) or abort(404)
    db.session.delete(item)
    try:
        audit(current_user, "delete_metadata", kind, item.id, item.name)
        db.session.commit()
        flash("Removed.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("This value is assigned to a book and cannot be removed.", "warning")
    return redirect(url_for("catalog.metadata", kind=kind))


@bp.route("/members", methods=["GET", "POST"])
@roles_required("admin")
def members():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(name) < 2 or len(name) > 120 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 255 or not 10 <= len(password) <= 256:
            flash("Enter a valid name, email and a password of 10–256 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "danger")
        else:
            user = User(full_name=name, email=email, role="member")
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            audit(current_user, "register_member", "user", user.id)
            db.session.commit()
            flash("Member registered.", "success")
            return redirect(url_for("catalog.members"))
    rows = User.query.filter_by(role="member").order_by(User.full_name).paginate(page=request.args.get("page", 1, type=int), per_page=20, error_out=False)
    return render_template("members.html", pagination=rows)


@bp.post("/members/<int:user_id>/update")
@roles_required("admin")
def member_update(user_id):
    user = User.query.filter_by(id=user_id, role="member").first_or_404()
    name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    if len(name) < 2 or len(name) > 120 or len(email) > 255 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        flash("Enter a valid member name and email.", "danger")
    elif User.query.filter(User.email == email, User.id != user.id).first():
        flash("That email is already in use.", "danger")
    else:
        active = request.form.get("active") == "on"
        if user.active != active:
            user.auth_version += 1
        user.full_name, user.email = name, email
        user.active = active
        audit(current_user, "update_member", "user", user.id)
        db.session.commit()
        flash("Member record updated.", "success")
    return redirect(url_for("catalog.members"))


@bp.route("/loans", methods=["GET", "POST"])
@roles_required("admin")
def loans():
    if request.method == "POST":
        member_id = request.form.get("member_id", type=int)
        book_id = request.form.get("book_id", type=int)
        try:
            issue_book(member_id, book_id, current_user, configured_value("DEFAULT_LOAN_DAYS"))
            flash("Book issued successfully.", "success")
        except ValueError as error:
            flash(str(error), "danger")
        except Exception:
            current_app.logger.exception("Book issue failed")
            flash("The issue could not be completed; no inventory was changed.", "danger")
        return redirect(url_for("catalog.loans"))
    rows = Loan.query.order_by(Loan.status, Loan.due_date).paginate(page=request.args.get("page", 1, type=int), per_page=20, error_out=False)
    members = User.query.filter_by(role="member", active=True).order_by(User.full_name).all()
    books = Book.query.order_by(Book.title).all()
    ready_reservations = Reservation.query.filter_by(status="ready").order_by(Reservation.created_at).all()
    return render_template("loans.html", pagination=rows, members=members, books=books,
                           ready_reservations=ready_reservations, today=library_today(),
                           loan_days=configured_value("DEFAULT_LOAN_DAYS"), fine_rate=configured_value("FINE_PER_DAY"))


@bp.post("/loans/<int:loan_id>/return")
@roles_required("admin")
def loan_return(loan_id):
    try:
        return_book(loan_id, current_user, configured_value("FINE_PER_DAY"))
        flash("Return processed and inventory updated.", "success")
    except ValueError as error:
        flash(str(error), "danger")
    except Exception:
        current_app.logger.exception("Book return failed")
        flash("The return could not be completed; please retry.", "danger")
    return redirect(url_for("catalog.loans"))


@bp.get("/history")
@roles_required("admin", "member")
def history():
    query = Loan.query.order_by(Loan.issued_at.desc())
    if current_user.role == "member":
        query = query.filter_by(member_id=current_user.id)
    rows = query.paginate(page=request.args.get("page", 1, type=int), per_page=20, error_out=False)
    return render_template("history.html", pagination=rows)


@bp.post("/reserve/<int:book_id>")
@roles_required("member")
def reserve(book_id):
    book = db.get_or_404(Book, book_id)
    has_active_loan = db.session.query(Loan.id).join(BookCopy).filter(
        Loan.member_id == current_user.id,
        Loan.status == "active",
        BookCopy.book_id == book.id
    ).first()
    if has_active_loan:
        flash("You already have an active loan for this title.", "warning")
        return redirect(url_for("catalog.books"))
    existing = Reservation.query.filter(Reservation.book_id == book.id, Reservation.member_id == current_user.id,
                                        Reservation.status.in_(["waiting", "ready"])).first()
    if existing:
        flash("You already have a waiting reservation for this title.", "info")
    else:
        copy = BookCopy.query.filter_by(book_id=book.id, status="available").order_by(BookCopy.id).with_for_update().first()
        row = Reservation(book_id=book.id, member_id=current_user.id,
                          status="ready" if copy else "waiting", available_at_request=bool(copy),
                          fulfilled_at=utcnow() if copy else None)
        db.session.add(row)
        if copy:
            copy.status = "reserved"
            db.session.flush()
            from .services import notify
            notify(current_user.id, "Reserved book ready", f"A copy of {book.title} is ready for pickup.", "reservation")
        audit(current_user, "reserve_book", "reservation", None, book.title)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A reservation for this title was just recorded on your account.", "warning")
            return redirect(url_for("catalog.my_reservations"))
        flash("Reservation request recorded. A copy is ready now." if copy else "Reservation request recorded and added to the waiting list.", "success")
    return redirect(url_for("catalog.books"))


@bp.post("/reservations/<int:reservation_id>/checkout")
@roles_required("admin")
def reservation_checkout(reservation_id):
    reservation = db.get_or_404(Reservation, reservation_id)
    try:
        issue_book(reservation.member_id, reservation.book_id, current_user,
                   configured_value("DEFAULT_LOAN_DAYS"), reservation_id=reservation.id)
        flash("Ready reservation checked out to the member.", "success")
    except ValueError as error:
        flash(str(error), "danger")
    except Exception:
        current_app.logger.exception("Reservation checkout failed")
        flash("Checkout could not be completed; the reservation and copy were left unchanged.", "danger")
    return redirect(url_for("catalog.loans"))


@bp.get("/reservations")
@roles_required("admin")
def reservations():
    rows = Reservation.query.order_by(Reservation.status, Reservation.created_at).paginate(
        page=request.args.get("page", 1, type=int), per_page=25, error_out=False)
    return render_template("reservations.html", pagination=rows)


@bp.get("/my-reservations")
@roles_required("member")
def my_reservations():
    rows = Reservation.query.filter_by(member_id=current_user.id).order_by(Reservation.created_at.desc()).all()
    return render_template("my_reservations.html", reservations=rows)


@bp.post("/reservations/<int:reservation_id>/cancel")
@login_required
def reservation_cancel(reservation_id):
    reservation = db.get_or_404(Reservation, reservation_id)
    if current_user.role != "admin" and (current_user.role != "member" or reservation.member_id != current_user.id):
        abort(403)
    try:
        cancel_reservation(reservation.id, current_user)
        flash("Reservation cancelled.", "success")
    except ValueError as error:
        flash(str(error), "danger")
    return redirect(url_for("catalog.reservations" if current_user.role == "admin" else "main.dashboard"))


@bp.get("/fines")
@roles_required("admin", "member")
def fines():
    from .models import Fine
    query = Fine.query.join(Loan)
    if current_user.role == "member":
        query = query.filter(Loan.member_id == current_user.id)
    rows = query.order_by(Fine.assessed_at.desc()).all()
    return render_template("fines.html", fines=rows)


@bp.post("/fines/<int:fine_id>/paid")
@roles_required("admin")
def fine_paid(fine_id):
    from .models import Fine
    fine = db.get_or_404(Fine, fine_id)
    fine.paid = True
    audit(current_user, "mark_fine_paid", "fine", fine.id, str(fine.amount))
    db.session.commit()
    flash("Fine marked as paid.", "success")
    return redirect(url_for("catalog.fines"))


@bp.get("/copies")
@roles_required("admin")
def copies():
    query = BookCopy.query.join(Book)
    barcode_q = request.args.get("barcode", "").strip()[:50]
    status_q = request.args.get("status", "").strip()
    if barcode_q:
        query = query.filter(db.or_(BookCopy.barcode.ilike(f"%{barcode_q}%"), Book.title.ilike(f"%{barcode_q}%")))
    if status_q in {"available", "loaned", "reserved", "maintenance", "lost"}:
        query = query.filter(BookCopy.status == status_q)
    pagination = query.order_by(Book.title, BookCopy.barcode).paginate(
        page=request.args.get("page", 1, type=int), per_page=25, error_out=False
    )
    return render_template("copies.html", pagination=pagination, barcode_q=barcode_q, status_q=status_q)


@bp.post("/copies/<int:copy_id>/status")
@roles_required("admin")
def copy_status(copy_id):
    copy = db.get_or_404(BookCopy, copy_id)
    status = request.form.get("status")
    if status not in {"available", "maintenance", "lost"} or copy.status in {"loaned", "reserved"}:
        flash("Choose an allowed status. Loaned and reserved copies cannot be changed here.", "danger")
    else:
        copy.status = status
        audit(current_user, "update_copy_status", "book_copy", copy.id, status)
        db.session.commit()
        flash("Copy status updated.", "success")
    return redirect(url_for("catalog.copies"))
