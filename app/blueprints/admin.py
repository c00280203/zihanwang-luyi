"""Administration API blueprint."""
from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.services import auth_service
from app.utils.decorators import admin_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/accounts")
@admin_required
def accounts():
    """List accounts, optionally filtered by ?role=admin|student."""
    role = request.args.get("role")
    users = auth_service.list_accounts(role)
    return jsonify(
        [
            {"id": u.id, "email": u.email, "role": u.role}
            for u in users
        ]
    )


@admin_bp.post("/accounts")
@admin_required
def create_account():
    """Create an administrator or student account."""
    body = request.get_json(silent=True) or {}
    user, error = auth_service.create_account(
        body.get("email"), body.get("password"), body.get("role")
    )
    if error:
        return jsonify({"error": error}), 400
    return jsonify(
        {"id": user.id, "email": user.email, "role": user.role}
    ), 201


@admin_bp.delete("/accounts/<int:user_id>")
@admin_required
def delete_account(user_id):
    """Delete an account."""
    error = auth_service.delete_account(user_id, current_user.id)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"message": "Account deleted."})
