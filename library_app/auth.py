import hashlib
import re
import secrets
import smtplib
from datetime import timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlsplit

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from .extensions import db, limiter
from .models import PasswordResetToken, User, utcnow

bp = Blueprint("auth", __name__)


def valid_email(value):
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value or ""))


def send_password_reset_email(user, token):
    """Send a one-use password link; never write the raw token to logs."""
    server = current_app.config.get("MAIL_SERVER")
    sender = current_app.config.get("MAIL_SENDER")
    if not server or not sender:
        current_app.logger.warning("Password reset email is not configured.")
        return False
    link = f"{current_app.config['PUBLIC_BASE_URL']}/password-reset/{token}"
    message = EmailMessage()
    message["Subject"] = "Reset your Campus Library password"
    message["From"] = sender
    message["To"] = user.email
    message.set_content(
        f"Hello {user.full_name},\n\nUse this one-time link to reset your password. "
        f"It expires in {current_app.config['PASSWORD_RESET_TOKEN_MINUTES']} minutes.\n\n{link}\n\n"
        "If you did not request this, you can ignore this message."
    )
    try:
        with smtplib.SMTP(server, current_app.config["MAIL_PORT"], timeout=10) as smtp:
            if current_app.config["MAIL_USE_TLS"]:
                smtp.starttls()
            username = current_app.config.get("MAIL_USERNAME")
            password = current_app.config.get("MAIL_PASSWORD")
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        current_app.logger.exception("Password reset email could not be delivered.")
        return False


def usable_reset_token(token):
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = PasswordResetToken.query.filter_by(token_hash=digest, used_at=None).first()
    if not row:
        return None
    expires_at = row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at.tzinfo is None else row.expires_at
    return row if expires_at > utcnow() else None


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
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
@limiter.limit("10 per minute", methods=["POST"])
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
            session["_auth_version"] = user.auth_version
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


@bp.route("/password-reset", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def password_reset_request():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email, active=True).first() if valid_email(email) and len(email) <= 255 else None
        if user:
            now = utcnow()
            PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).update({"used_at": now})
            raw_token = secrets.token_urlsafe(32)
            reset = PasswordResetToken(
                user_id=user.id,
                token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                expires_at=now + timedelta(minutes=current_app.config["PASSWORD_RESET_TOKEN_MINUTES"]),
            )
            db.session.add(reset)
            db.session.commit()
            send_password_reset_email(user, raw_token)
        flash("If an active account matches that address, a reset link will be sent when email delivery is configured.", "info")
        return redirect(url_for("auth.password_reset_request"))
    return render_template("auth/password_reset_request.html")


@bp.route("/password-reset/<token>", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def password_reset(token):
    if len(token) > 128 or not usable_reset_token(token):
        flash("That password reset link is invalid or has expired. Request a new one.", "warning")
        return redirect(url_for("auth.password_reset_request"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")
        row = usable_reset_token(token)
        if not row:
            flash("That password reset link is invalid or has expired. Request a new one.", "warning")
            return redirect(url_for("auth.password_reset_request"))
        if not 10 <= len(password) <= 256:
            flash("Choose a password between 10 and 256 characters.", "danger")
        elif password != confirmation:
            flash("The password and confirmation do not match.", "danger")
        else:
            now = utcnow()
            claimed = PasswordResetToken.query.filter_by(id=row.id, used_at=None).filter(
                PasswordResetToken.expires_at > now
            ).update({"used_at": now}, synchronize_session=False)
            if claimed != 1:
                db.session.rollback()
                flash("That password reset link is invalid or has expired. Request a new one.", "warning")
                return redirect(url_for("auth.password_reset_request"))
            user = db.session.get(User, row.user_id)
            if not user or not user.active:
                db.session.rollback()
                flash("That password reset link is invalid or has expired. Request a new one.", "warning")
                return redirect(url_for("auth.password_reset_request"))
            user.set_password(password)
            user.auth_version += 1
            PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).update({"used_at": now})
            from .services import audit
            audit(user, "reset_password", "user", user.id)
            db.session.commit()
            logout_user()
            session.clear()
            flash("Your password has been reset. Sign in with the new password.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", token=token)


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        action = request.form.get("form_action")
        if action == "profile":
            name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            if len(name) < 2 or len(name) > 120:
                flash("Enter your name using 2–120 characters.", "danger")
            elif not valid_email(email) or len(email) > 255:
                flash("Enter a valid email address.", "danger")
            elif User.query.filter(User.email == email, User.id != current_user.id).first():
                flash("That email address is already in use.", "danger")
            else:
                current_user.full_name = name
                current_user.email = email
                from .services import audit
                audit(current_user, "update_account", "user", current_user.id)
                try:
                    db.session.commit()
                    flash("Your profile has been updated.", "success")
                except IntegrityError:
                    db.session.rollback()
                    flash("That email address is already in use.", "danger")
        elif action == "password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not current_user.check_password(current_password):
                flash("Your current password is not correct.", "danger")
            elif not 10 <= len(new_password) <= 256:
                flash("Choose a password between 10 and 256 characters.", "danger")
            elif new_password != confirm_password:
                flash("The new password and confirmation do not match.", "danger")
            elif current_user.check_password(new_password):
                flash("Choose a new password that differs from your current one.", "warning")
            else:
                current_user.set_password(new_password)
                current_user.auth_version += 1
                PasswordResetToken.query.filter_by(user_id=current_user.id, used_at=None).update({"used_at": utcnow()})
                from .services import audit
                audit(current_user, "change_password", "user", current_user.id)
                db.session.commit()
                logout_user()
                session.clear()
                flash("Your password has been changed. Sign in again.", "success")
                return redirect(url_for("auth.login"))
        else:
            flash("Choose a valid account action.", "danger")
        return redirect(url_for("auth.account"))
    return render_template("account.html")


@bp.post("/logout")
def logout():
    if current_user.is_authenticated:
        from .services import audit
        audit(current_user, "logout", "user", current_user.id)
        db.session.commit()
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
