"""Authentication and account management service."""
from sqlalchemy import select, func

from app.extensions import db
from app.models import User


def find_by_email(email):
    """Return a user by email address, or None."""
    normalized = (email or "").strip().lower()
    return db.session.scalar(select(User).where(User.email == normalized))


def authenticate(email, password):
    """Verify credentials and return the matching user, or None."""
    user = find_by_email(email)
    if user and user.check_password(password):
        return user
    return None


def register_student(email, password):
    """Create a student account. Returns (user, error_message)."""
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        return None, "A valid email address is required."
    if len(password or "") < 6:
        return None, "Password must be at least 6 characters."
    if find_by_email(normalized):
        return None, "An account with this email already exists."

    user = User(email=normalized, role="student")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user, None


def create_account(email, password, role):
    """Create an account with a chosen role (admin use only)."""
    normalized = (email or "").strip().lower()
    if role not in ("admin", "student"):
        return None, "Invalid role."
    if not normalized or "@" not in normalized:
        return None, "A valid email address is required."
    if len(password or "") < 6:
        return None, "Password must be at least 6 characters."
    if find_by_email(normalized):
        return None, "An account with this email already exists."

    user = User(email=normalized, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user, None


def list_accounts(role=None):
    """List accounts, optionally filtered by role."""
    statement = select(User).order_by(User.id)
    if role in ("admin", "student"):
        statement = statement.where(User.role == role)
    return db.session.scalars(statement).all()


def delete_account(user_id, current_user_id):
    """Delete an account. Returns an error message or None on success."""
    if user_id == current_user_id:
        return "You cannot delete your own account."
    user = db.session.get(User, user_id)
    if not user:
        return "Account not found."
    if user.role == "admin":
        admin_count = db.session.scalar(
            select(func.count()).select_from(User).where(User.role == "admin")
        )
        if admin_count <= 1:
            return "At least one administrator must remain."
    db.session.delete(user)
    db.session.commit()
    return None
