"""Auth-Endpoints fuer Planung SBP."""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity
)
import bcrypt

from ..models import db, User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


@auth_bp.route("/status", methods=["GET"])
def auth_status():
    """Pruefen ob Admin existiert (fuer Setup-Redirect im Frontend)."""
    admin = User.query.filter_by(role="admin").first()
    musiker = User.query.filter_by(role="musiker").first()
    return jsonify({
        "admin_exists": admin is not None,
        "musiker_password_set": musiker is not None,
    })


@auth_bp.route("/setup", methods=["POST"])
def setup():
    """Erstmaliger Admin-Account."""
    # Nur wenn noch kein Admin existiert
    if User.query.filter_by(role="admin").first():
        return jsonify({"error": "Admin existiert bereits."}), 400

    data = request.get_json()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email und Passwort erforderlich."}), 400
    if len(password) < 8:
        return jsonify({"error": "Passwort muss mindestens 8 Zeichen haben."}), 400

    admin = User(
        email=email,
        password_hash=_hash_password(password),
        role="admin",
    )
    db.session.add(admin)
    db.session.commit()

    token = create_access_token(identity=str(admin.id), additional_claims={
        "role": "admin", "email": admin.email
    })
    return jsonify({
        "message": "Admin-Account erstellt.",
        "token": token,
        "user": {"id": admin.id, "email": admin.email, "role": "admin"},
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login (Admin per Email+PW, Musiker per PW)."""
    data = request.get_json()
    login_type = data.get("type", "admin")  # "admin" oder "musiker"

    if login_type == "admin":
        email = data.get("email", "").strip()
        password = data.get("password", "")

        admin = User.query.filter_by(email=email, role="admin").first()
        if not admin or not _check_password(password, admin.password_hash):
            return jsonify({"error": "Ungueltige Anmeldedaten."}), 401

        token = create_access_token(identity=str(admin.id), additional_claims={
            "role": "admin", "email": admin.email
        })
        return jsonify({
            "token": token,
            "user": {"id": admin.id, "email": admin.email, "role": "admin"},
        })

    elif login_type == "musiker":
        password = data.get("password", "")

        musiker = User.query.filter_by(role="musiker").first()
        if not musiker or not _check_password(password, musiker.password_hash):
            return jsonify({"error": "Ungueltiges Passwort."}), 401

        token = create_access_token(identity=str(musiker.id), additional_claims={
            "role": "musiker"
        })
        return jsonify({
            "token": token,
            "user": {"id": musiker.id, "role": "musiker"},
        })

    return jsonify({"error": "Ungueltiger Login-Typ."}), 400


@auth_bp.route("/musiker-password", methods=["POST"])
@jwt_required()
def set_musiker_password():
    """Musiker-Zugangpasswort setzen/aendern (nur Admin)."""
    claims = get_jwt_identity()
    # Admin-Check via JWT claims
    from flask_jwt_extended import get_jwt
    jwt_data = get_jwt()
    if jwt_data.get("role") != "admin":
        return jsonify({"error": "Nur Admin darf Musiker-Passwort setzen."}), 403

    data = request.get_json()
    password = data.get("password", "")
    if len(password) < 4:
        return jsonify({"error": "Passwort muss mindestens 4 Zeichen haben."}), 400

    musiker = User.query.filter_by(role="musiker").first()
    if musiker:
        musiker.password_hash = _hash_password(password)
    else:
        musiker = User(
            password_hash=_hash_password(password),
            role="musiker",
        )
        db.session.add(musiker)

    db.session.commit()
    return jsonify({"message": "Musiker-Passwort gesetzt."})


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """Aktueller Benutzer."""
    from flask_jwt_extended import get_jwt
    jwt_data = get_jwt()
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({"error": "Benutzer nicht gefunden."}), 404

    return jsonify({
        "id": user.id,
        "email": user.email,
        "role": user.role,
    })
