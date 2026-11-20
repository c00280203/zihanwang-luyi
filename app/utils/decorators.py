"""Authorization decorators for API routes."""
from functools import wraps

from flask import jsonify
from flask_login import current_user


def login_required(api=True):
    """Require an authenticated user.

    Args:
        api: When True return JSON 401; otherwise let Flask-Login redirect.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                if api:
                    return jsonify({"error": "Authentication required."}), 401
                from flask import redirect, url_for

                return redirect(url_for("auth.login_page"))
            return view(*args, **kwargs)

        return wrapper

    return decorator


def admin_required(view):
    """Require an authenticated administrator account."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required."}), 401
        if not current_user.is_admin:
            return jsonify({"error": "Administrator access required."}), 403
        return view(*args, **kwargs)

    return wrapper
