import re
from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import User

bp = Blueprint("auth", __name__)


def valid_email(value):
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value or ""))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(name) < 2 or len(name) > 120:
            flash("Enter your name (2–120 characters).", "danger")
        elif not valid_email(email) or len(email) > 255:
            flash("Enter a valid email address.", "danger")
        elif len(password) < 10 or len(password) > 256:
            flash("Use a password with at least 10 characters (maximum 256).", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
        else:
            user = User(full_name=name, email=email, role="member")
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("An account with that email already exists.", "danger")
            else:
                flash("Registration complete. You can now sign in.", "success")
                return redirect(url_for("auth.login"))
    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email, active=True).first()
        if len(password) <= 256 and user and user.check_password(password):
            session.clear()
            login_user(user, remember=False, fresh=True)
            session.permanent = True
            from .services import audit
            audit(user, "login", "user", user.id)
            db.session.commit()
            next_url = request.args.get("next", "")
            parsed_next = urlsplit(next_url)
            if next_url.startswith("/") and not next_url.startswith("//") and "\\" not in next_url and not parsed_next.scheme and not parsed_next.netloc:
                return redirect(next_url)
            return redirect(url_for("main.dashboard"))
        flash("Email or password was not recognized.", "danger")
    return render_template("auth/login.html")


@bp.post("/logout")
def logout():
    if current_user.is_authenticated:
        from .services import audit
        audit(current_user, "logout", "user", current_user.id)
        db.session.commit()
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
