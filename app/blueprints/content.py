"""Courseware API blueprint."""
from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.extensions import db
from app.models import Course
from app.services import content_service, storage_service
from app.utils.decorators import admin_required, login_required
from app.utils.text_extract import extract_pdf_text, extract_pptx_text

content_bp = Blueprint("content", __name__)


@content_bp.get("/courses")
def courses():
    """List all courses."""
    from app.services.search_service import list_courses

    return jsonify(list_courses())


@content_bp.get("/resources")
@login_required()
def resources():
    """List courseware, optionally filtered by ?course=<code>."""
    return jsonify(content_service.list_resources(request.args.get("course")))


@content_bp.post("/upload")
@admin_required
def upload():
    """Upload a new courseware file (administrator only)."""
    file = request.files.get("file")
    course_code = (request.form.get("course_code") or "").strip().upper()
    title = (request.form.get("title") or "").strip()
    if not file or not course_code or not title:
        return jsonify({"error": "File, course and title are required."}), 400

    suffix = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
    if suffix not in ("pdf", "pptx"):
        return jsonify({"error": "Only PDF and PPTX files are supported."}), 400

    from sqlalchemy import func

    course = db.session.scalar(
        db.select(Course).where(func.lower(Course.course_code) == course_code.lower())
    )
    if not course:
        return jsonify({"error": "Course not found."}), 400

    total_pages = content_service.count_pages(file, suffix)
    file.stream.seek(0)
    file_url = storage_service.save_file(file, file.filename)
    try:
        resource = content_service.add_resource(
            course.course_id, title, file_url, suffix, total_pages, current_user.id
        )
    except Exception:
        storage_service.delete_file(file_url)
        db.session.rollback()
        return jsonify({"error": "Unable to register this file."}), 409

    return jsonify({"message": "Uploaded.", "resource_id": resource.resource_id}), 201


@content_bp.delete("/resources/<int:resource_id>")
@admin_required
def delete_resource(resource_id):
    """Delete a courseware file and its mappings (administrator only)."""
    file_url, error = content_service.delete_resource(resource_id)
    if error:
        return jsonify({"error": error}), 404
    storage_service.delete_file(file_url)
    return jsonify({"message": "Resource deleted."})


@content_bp.get("/preview-text/<int:resource_id>")
@login_required()
def preview_text(resource_id):
    """Return extracted text of a resource for debugging (limited length)."""
    resource = content_service.get_resource(resource_id)
    if not resource:
        return jsonify({"error": "Resource not found."}), 404
    try:
        data = storage_service.fetch_bytes(resource)
        text = (
            extract_pptx_text(data, max_chars=4000)
            if resource.file_type == "pptx"
            else extract_pdf_text(data, max_chars=4000)
        )
    except Exception:
        return jsonify({"error": "Unable to read this file."}), 500
    return jsonify({"text": text})
