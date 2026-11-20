"""Page-serving blueprint."""
from flask import Blueprint, render_template
from flask_login import current_user

from app.utils.decorators import admin_required as _admin
from flask import redirect, url_for

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
def index():
    """Serve the public landing page, or the app for a signed-in user."""
    if not current_user.is_authenticated:
        return render_template("new/landing.html")
    return render_template("new/index.html")


@pages_bp.get("/login")
def login_page():
    """Render the login page."""
    return render_template("new/login.html")


@pages_bp.get("/register")
def register_page():
    """Render the student registration page."""
    return render_template("new/register.html")


@pages_bp.get("/admin")
def admin_page():
    """Render the administration page for administrators only."""
    if not current_user.is_authenticated:
        return redirect(url_for("pages.login_page"))
    if not current_user.is_admin:
        return redirect(url_for("pages.index"))
    return render_template("new/admin.html")
