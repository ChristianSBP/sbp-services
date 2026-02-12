"""Authentifizierung: Login, Setup, Logout."""

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user

import bcrypt

from .models import db, User
from .config import Config

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login-Seite fuer Admin und Musiker."""
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("musiker.dashboard"))

    # Pruefen ob Admin existiert — wenn nicht, zum Setup weiterleiten
    admin = User.query.filter_by(role="admin").first()
    if not admin:
        return redirect(url_for("auth.setup"))

    if request.method == "POST":
        login_type = request.form.get("login_type", "admin")

        if login_type == "admin":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")

            user = User.query.filter_by(email=email, role="admin").first()
            if user and bcrypt.checkpw(
                password.encode("utf-8"), user.password_hash.encode("utf-8")
            ):
                login_user(user)
                return redirect(url_for("admin.dashboard"))
            flash("E-Mail oder Passwort falsch.", "error")

        elif login_type == "musiker":
            password = request.form.get("musiker_password", "")
            musiker_user = User.query.filter_by(role="musiker").first()

            if musiker_user and bcrypt.checkpw(
                password.encode("utf-8"),
                musiker_user.password_hash.encode("utf-8"),
            ):
                login_user(musiker_user)
                return redirect(url_for("musiker.dashboard"))
            flash("Musiker-Passwort falsch.", "error")

    return render_template("login.html")


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """Erstmaliges Admin-Passwort setzen."""
    # Nur erlaubt wenn noch kein Admin existiert
    admin = User.query.filter_by(role="admin").first()
    if admin:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not password or len(password) < 6:
            flash("Passwort muss mindestens 6 Zeichen lang sein.", "error")
        elif password != password_confirm:
            flash("Passwoerter stimmen nicht ueberein.", "error")
        else:
            hashed = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

            user = User(email=email, password_hash=hashed, role="admin")
            db.session.add(user)
            db.session.commit()

            login_user(user)
            flash("Admin-Konto erstellt. Willkommen!", "success")
            return redirect(url_for("admin.dashboard"))

    return render_template("setup.html", admin_email=Config.ADMIN_EMAIL)


@auth_bp.route("/logout")
def logout():
    """Abmelden."""
    logout_user()
    return redirect(url_for("auth.login"))
