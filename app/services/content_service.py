"""Courseware (Resource) management service."""
from sqlalchemy import select, func

from app.extensions import db
from app.models import Course, Resource, ResourceLocation


def list_resources(course_code=None):
    """Return resources, optionally filtered by course code."""
    statement = select(Resource, Course).join(Course, Resource.course_id == Course.course_id)
    if course_code:
        statement = statement.where(
            func.lower(Course.course_code) == course_code.lower()
        )
    statement = statement.order_by(Course.course_code, Resource.title)
    rows = db.session.execute(statement).all()
    return [
        {
            "resource_id": r.resource_id,
            "course_code": c.course_code,
            "title": r.title,
            "file_url": r.file_url,
            "file_type": r.file_type,
            "total_pages": r.total_pages,
        }
        for r, c in rows
    ]


def get_resource(resource_id):
    """Return a resource by id or None."""
    return db.session.get(Resource, resource_id)


def count_pages(file_storage, file_type):
    """Count pages in an uploaded PDF, or slides in a PPTX."""
    import io

    if file_type == "pdf":
        from pypdf import PdfReader

        return len(PdfReader(io.BytesIO(file_storage.read())).pages)
    from pptx import Presentation

    return len(Presentation(io.BytesIO(file_storage.read())).slides)


def add_resource(course_id, title, file_url, file_type, total_pages, uploader_id):
    """Create a resource record and return it."""
    resource = Resource(
        course_id=course_id,
        title=title,
        file_url=file_url,
        file_type=file_type,
        total_pages=total_pages,
        uploaded_by=uploader_id,
    )
    db.session.add(resource)
    db.session.commit()
    return resource


def delete_resource(resource_id):
    """Delete a resource and its mappings. Returns (file_url, error)."""
    resource = db.session.get(Resource, resource_id)
    if not resource:
        return None, "Resource not found."
    file_url = resource.file_url
    db.session.delete(resource)
    db.session.commit()
    return file_url, None
