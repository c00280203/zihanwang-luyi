"""Authentication API blueprint."""
from flask import Blueprint, jsonify, request, session
from flask_login import login_user, logout_user, current_user

from app.services import auth_service

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    """Log a user in with email and password."""
    body = request.get_json(silent=True) or {}
    user = auth_service.authenticate(body.get("email"), body.get("password"))
    if not user:
        return jsonify({"error": "Invalid email or password."}), 401
    login_user(user)
    return jsonify(
        {
            "message": "Logged in.",
            "user": {"id": user.id, "email": user.email, "role": user.role},
        }
    )


@auth_bp.post("/register")
def register():
    """Register a new student account."""
    body = request.get_json(silent=True) or {}
    user, error = auth_service.register_student(
        body.get("email"), body.get("password")
    )
    if error:
        return jsonify({"error": error}), 400
    login_user(user)
    return jsonify(
        {
            "message": "Registered.",
            "user": {"id": user.id, "email": user.email, "role": user.role},
        }
    )


@auth_bp.post("/logout")
def logout():
    """Log the current user out."""
    logout_user()
    session.clear()
    return jsonify({"message": "Logged out."})


@auth_bp.get("/me")
def me():
    """Return the current user's profile."""
    if not current_user.is_authenticated:
        return jsonify({"user": None})
    return jsonify(
        {
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "role": current_user.role,
            }
        }
    )
