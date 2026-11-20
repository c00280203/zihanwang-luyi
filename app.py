import os
import re
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import URL

from models import (
    db, Course, KnowledgePoint, KnowledgePointAlias,
    Resource, ResourceLocation
)
from search_service import search_knowledge_points
from pdf_service import validate_registered_pdf


# Read PostgreSQL settings
load_dotenv(Path(__file__).with_name(".env"), override=False)

db_url = URL.create(
    drivername="postgresql+psycopg2",
    username=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
    host=os.getenv("PGHOST", "localhost"),
    port=int(os.getenv("PGPORT", "5432")),
    database=os.getenv("PGDATABASE"),
)

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Tests use a separate PostgreSQL schema; normal runs use the default schema.
schema = os.getenv("SOE206_DB_SCHEMA")
if schema:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", schema):
        raise ValueError("Invalid database schema name.")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"options": f"-csearch_path={schema},pg_catalog"}
    }
db.init_app(app)


@app.errorhandler(IntegrityError)
def handle_integrity_error(error):
    db.session.rollback()
    return jsonify({"error": "The change conflicts with an existing record or constraint."}), 409


@app.errorhandler(500)
def handle_server_error(error):
    db.session.rollback()
    return jsonify({"error": "The request could not be completed. Please try again."}), 500



@app.get("/")
def home():
    return render_template("index.html")


# Get the list of available courses
@app.get("/api/courses")
def get_courses():
    courses = db.session.execute(
        select(Course).order_by(Course.course_code)
    ).scalars().all()

    return jsonify([
        {
            "course_id": course.course_id,
            "course_code": course.course_code,
            "title": course.title,
        }
        for course in courses
    ])


# Search or browse knowledge points
@app.get("/api/search")
def search():
    course_code = request.args.get(
        "course", ""
    ).strip().upper()

    keyword = request.args.get("q", "").strip()

    if not course_code:
        return jsonify({
            "error": "Please select a course."
        }), 400

    if len(course_code) > 40 or len(keyword) > 200:
        return jsonify({
            "error": "Search input is too long."
        }), 400

    # Check whether the course exists
    course_id = db.session.execute(
        select(Course.course_id).where(
            Course.course_code == course_code
        )
    ).scalar_one_or_none()

    if course_id is None:
        return jsonify({
            "error": "Course not found."
        }), 404

    # Call the existing search service
    results = search_knowledge_points(
        course_code, keyword
    )

    return jsonify({
        "course": course_code,
        "query": keyword,
        "count": len(results),
        "results": results,
    })

# Admin page
@app.get("/admin")
def admin_page():
    return render_template("admin.html")


# Read knowledge points in a selected course
@app.get("/api/admin/knowledge-points")
def admin_get_knowledge_points():
    course_code = request.args.get(
        "course", ""
    ).strip().upper()

    if not course_code:
        return jsonify({
            "error": "Please select a course."
        }), 400

    course = db.session.execute(
        select(Course).where(
            Course.course_code == course_code
        )
    ).scalar_one_or_none()

    if course is None:
        return jsonify({
            "error": "Course not found."
        }), 404

    points = db.session.execute(
        select(KnowledgePoint)
        .where(KnowledgePoint.course_id == course.course_id)
        .order_by(KnowledgePoint.name)
    ).scalars().all()

    return jsonify({
        "course": course_code,
        "results": [
            {
                "id": point.knowledge_point_id,
                "name": point.name,
                "description": point.description or ""
            }
            for point in points
        ]
    })


# Create a new knowledge point
@app.post("/api/admin/knowledge-points")
def admin_create_knowledge_point():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Please provide valid JSON data."
        }), 400

    course_code = data.get("course_code")
    raw_name = data.get("name")
    description = data.get("description", "")

    if not all(isinstance(value, str) for value in
               (course_code, raw_name, description)):
        return jsonify({
            "error": "Invalid input format."
        }), 400

    course_code = course_code.strip().upper()
    name = " ".join(raw_name.strip().split())
    normalized_name = name.lower()
    description = description.strip()

    if not course_code or not name:
        return jsonify({
            "error": "Course and name are required."
        }), 400

    if (len(course_code) > 40
            or len(name) > 200
            or len(normalized_name) > 200):
        return jsonify({
            "error": "Input is too long."
        }), 400

    course = db.session.execute(
        select(Course).where(
            Course.course_code == course_code
        )
    ).scalar_one_or_none()

    if course is None:
        return jsonify({
            "error": "Course not found."
        }), 404

    point = KnowledgePoint(
        course_id=course.course_id,
        name=name,
        normalized_name=normalized_name,
        description=description or None
    )

    db.session.add(point)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": (
                "This knowledge point already exists "
                "in the selected course."
            )
        }), 409

    return jsonify({
        "message": "Knowledge point added successfully.",
        "id": point.knowledge_point_id,
        "name": point.name
    }), 201

# Update an existing knowledge point
@app.put("/api/admin/knowledge-points/<int:point_id>")
def admin_update_knowledge_point(point_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data."}), 400

    course_code = data.get("course_code")
    raw_name = data.get("name")
    description = data.get("description", "")

    if not all(isinstance(v, str) for v in
               (course_code, raw_name, description)):
        return jsonify({"error": "Invalid input format."}), 400

    course_code = course_code.strip().upper()
    name = " ".join(raw_name.strip().split())
    normalized_name = name.lower()
    description = description.strip()

    if not course_code or not name:
        return jsonify({"error": "Course and name are required."}), 400

    if len(course_code) > 40 or len(name) > 200 or len(normalized_name) > 200:
        return jsonify({"error": "Input is too long."}), 400

    course = db.session.execute(
        select(Course).where(Course.course_code == course_code)
    ).scalar_one_or_none()

    point = db.session.get(KnowledgePoint, point_id)

    # Prevent changes to a knowledge point in another course
    if course is None or point is None:
        return jsonify({"error": "Knowledge point not found."}), 404

    if point.course_id != course.course_id:
        return jsonify({"error": "Knowledge point not found."}), 404

    point.name = name
    point.normalized_name = normalized_name
    point.description = description or None

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "This name already exists in the course."
        }), 409

    return jsonify({
        "message": "Knowledge point updated successfully.",
        "id": point.knowledge_point_id,
        "name": point.name
    })


# Delete an existing knowledge point
@app.delete("/api/admin/knowledge-points/<int:point_id>")
def admin_delete_knowledge_point(point_id):
    course_code = request.args.get(
        "course", ""
    ).strip().upper()

    if not course_code:
        return jsonify({"error": "Please select a course."}), 400

    course = db.session.execute(
        select(Course).where(Course.course_code == course_code)
    ).scalar_one_or_none()

    point = db.session.get(KnowledgePoint, point_id)

    if course is None or point is None:
        return jsonify({"error": "Knowledge point not found."}), 404

    if point.course_id != course.course_id:
        return jsonify({"error": "Knowledge point not found."}), 404

    db.session.delete(point)
    db.session.commit()

    return jsonify({
        "message": "Knowledge point deleted successfully."
    })


# Check that a knowledge point belongs to the selected course
def find_admin_point(point_id, course_code):
    point = db.session.get(KnowledgePoint, point_id)

    if point is None:
        return None

    course = db.session.get(Course, point.course_id)

    if course is None:
        return None

    if course.course_code != course_code.strip().upper():
        return None

    return point


# Read aliases
@app.get("/api/admin/knowledge-points/<int:point_id>/aliases")
def admin_get_aliases(point_id):
    course_code = request.args.get("course", "").strip().upper()
    point = find_admin_point(point_id, course_code)

    if point is None:
        return jsonify({"error": "Knowledge point not found."}), 404

    aliases = db.session.execute(
        select(KnowledgePointAlias)
        .where(
            KnowledgePointAlias.knowledge_point_id == point_id
        )
        .order_by(KnowledgePointAlias.alias)
    ).scalars().all()

    return jsonify({
        "results": [
            {
                "id": item.alias_id,
                "alias": item.alias
            }
            for item in aliases
        ]
    })


# Create an alias
@app.post("/api/admin/knowledge-points/<int:point_id>/aliases")
def admin_create_alias(point_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data."}), 400

    course_code = data.get("course_code")
    raw_alias = data.get("alias")

    if not isinstance(course_code, str) or not isinstance(raw_alias, str):
        return jsonify({"error": "Invalid input format."}), 400

    point = find_admin_point(point_id, course_code)

    if point is None:
        return jsonify({"error": "Knowledge point not found."}), 404

    alias = " ".join(raw_alias.strip().split())
    normalized_alias = alias.lower()

    if not alias or len(alias) > 200 or len(normalized_alias) > 200:
        return jsonify({"error": "Invalid alias length."}), 400

    if normalized_alias == point.normalized_name:
        return jsonify({
            "error": "The alias is the same as the knowledge point name."
        }), 400

    record = KnowledgePointAlias(
        knowledge_point_id=point_id,
        alias=alias,
        normalized_alias=normalized_alias
    )

    db.session.add(record)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "This alias already exists for this knowledge point."
        }), 409

    return jsonify({
        "message": "Alias added successfully.",
        "id": record.alias_id
    }), 201


# Update an alias
@app.put(
    "/api/admin/knowledge-points/<int:point_id>/aliases/<int:alias_id>"
)
def admin_update_alias(point_id, alias_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data."}), 400

    course_code = data.get("course_code")
    raw_alias = data.get("alias")

    if not isinstance(course_code, str) or not isinstance(raw_alias, str):
        return jsonify({"error": "Invalid input format."}), 400

    point = find_admin_point(point_id, course_code)
    record = db.session.get(KnowledgePointAlias, alias_id)

    if point is None or record is None:
        return jsonify({"error": "Alias not found."}), 404

    if record.knowledge_point_id != point_id:
        return jsonify({"error": "Alias not found."}), 404

    alias = " ".join(raw_alias.strip().split())
    normalized_alias = alias.lower()

    if not alias or len(alias) > 200 or len(normalized_alias) > 200:
        return jsonify({"error": "Invalid alias length."}), 400

    if normalized_alias == point.normalized_name:
        return jsonify({
            "error": "The alias is the same as the knowledge point name."
        }), 400

    record.alias = alias
    record.normalized_alias = normalized_alias

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "This alias already exists for this knowledge point."
        }), 409

    return jsonify({"message": "Alias updated successfully."})


# Delete an alias
@app.delete(
    "/api/admin/knowledge-points/<int:point_id>/aliases/<int:alias_id>"
)
def admin_delete_alias(point_id, alias_id):
    course_code = request.args.get("course", "").strip().upper()

    point = find_admin_point(point_id, course_code)
    record = db.session.get(KnowledgePointAlias, alias_id)

    if point is None or record is None:
        return jsonify({"error": "Alias not found."}), 404

    if record.knowledge_point_id != point_id:
        return jsonify({"error": "Alias not found."}), 404

    db.session.delete(record)
    db.session.commit()

    return jsonify({"message": "Alias deleted successfully."})

# Step 5.4.1: PDF resources and knowledge-point locations

# Read PDF resources belonging to one course
@app.get("/api/admin/resources")
def admin_get_resources():
    course_code = request.args.get(
        "course", ""
    ).strip().upper()

    course = db.session.execute(
        select(Course).where(
            Course.course_code == course_code
        )
    ).scalar_one_or_none()

    if course is None:
        return jsonify({"error": "Course not found."}), 404

    resources = db.session.execute(
        select(Resource)
        .where(Resource.course_id == course.course_id)
        .order_by(Resource.title)
    ).scalars().all()

    return jsonify({
        "results": [
            {
                "id": resource.resource_id,
                "title": resource.title,
                "file_url": resource.file_url,
                "total_pages": resource.total_pages
            }
            for resource in resources
        ]
    })


# Read PDF locations for one knowledge point
@app.get(
    "/api/admin/knowledge-points/<int:point_id>/locations"
)
def admin_get_locations(point_id):
    course_code = request.args.get(
        "course", ""
    ).strip().upper()

    # Reuse the helper from Step 5.3
    point = find_admin_point(point_id, course_code)

    if point is None:
        return jsonify({
            "error": "Knowledge point not found."
        }), 404

    rows = db.session.execute(
        select(ResourceLocation, Resource)
        .join(
            Resource,
            ResourceLocation.resource_id == Resource.resource_id
        )
        .where(
            ResourceLocation.knowledge_point_id == point_id,
            ResourceLocation.course_id == point.course_id,
            Resource.course_id == point.course_id
        )
        .order_by(
            Resource.title,
            ResourceLocation.page_number
        )
    ).all()

    return jsonify({
        "results": [
            {
                "id": location.location_id,
                "resource_id": resource.resource_id,
                "resource_title": resource.title,
                "page_number": location.page_number,
                "note": location.note or ""
            }
            for location, resource in rows
        ]
    })


# Create a new PDF location
@app.post(
    "/api/admin/knowledge-points/<int:point_id>/locations"
)
def admin_create_location(point_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data."}), 400

    course_code = data.get("course_code")
    resource_id = data.get("resource_id")
    page_number = data.get("page_number")
    note = data.get("note", "")

    if (
        not isinstance(course_code, str)
        or type(resource_id) is not int
        or type(page_number) is not int
        or not isinstance(note, str)
    ):
        return jsonify({
            "error": "Invalid input format."
        }), 400

    if resource_id < 1 or page_number < 1:
        return jsonify({
            "error": "Resource ID and page number must be positive."
        }), 400

    point = find_admin_point(point_id, course_code)
    resource = db.session.execute(
        select(Resource).where(Resource.resource_id == resource_id).with_for_update()
    ).scalar_one_or_none()

    if point is None or resource is None:
        return jsonify({
            "error": "Knowledge point or PDF not found."
        }), 404

    # Prevent mapping between different courses
    if resource.course_id != point.course_id:
        return jsonify({
            "error": "PDF and knowledge point belong to different courses."
        }), 400

    try:
        validate_registered_pdf(app.static_folder, resource.file_url, resource.total_pages)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409

    # Check the page against the registered PDF page count
    if page_number > resource.total_pages:
        return jsonify({
            "error": (
                f"Page number cannot exceed "
                f"{resource.total_pages}."
            )
        }), 400

    note = note.strip()

    if len(note) > 500:
        return jsonify({
            "error": "Note is too long."
        }), 400

    location = ResourceLocation(
        course_id=point.course_id,
        knowledge_point_id=point.knowledge_point_id,
        resource_id=resource.resource_id,
        page_number=page_number,
        note=note or None
    )

    db.session.add(location)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "This PDF page mapping already exists."
        }), 409

    return jsonify({
        "message": "PDF location added successfully.",
        "id": location.location_id
    }), 201

# Step 5.4.2: Update and delete PDF locations


@app.put(
    "/api/admin/knowledge-points/<int:point_id>/locations/<int:location_id>"
)
def admin_update_location(point_id, location_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data."}), 400

    course_code = data.get("course_code")
    page_number = data.get("page_number")
    note = data.get("note", "")

    if (
        not isinstance(course_code, str)
        or type(page_number) is not int
        or not isinstance(note, str)
    ):
        return jsonify({"error": "Invalid input format."}), 400

    point = find_admin_point(point_id, course_code)
    location = db.session.get(ResourceLocation, location_id)

    # Make sure the location belongs to this knowledge point
    if (
        point is None
        or location is None
        or location.knowledge_point_id != point.knowledge_point_id
        or location.course_id != point.course_id
    ):
        return jsonify({"error": "PDF location not found."}), 404

    resource = db.session.execute(
        select(Resource).where(Resource.resource_id == location.resource_id).with_for_update()
    ).scalar_one_or_none()

    if resource is None or resource.course_id != point.course_id:
        return jsonify({"error": "Invalid PDF resource."}), 409

    try:
        validate_registered_pdf(app.static_folder, resource.file_url, resource.total_pages)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409

    # Validate the page number
    if page_number < 1 or page_number > resource.total_pages:
        return jsonify({
            "error": (
                f"Page number must be between "
                f"1 and {resource.total_pages}."
            )
        }), 400

    note = note.strip()

    if len(note) > 500:
        return jsonify({"error": "Note is too long."}), 400

    # Update the existing mapping
    location.page_number = page_number
    location.note = note or None

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "This PDF page mapping already exists."
        }), 409

    return jsonify({
        "message": "PDF location updated successfully."
    })


@app.delete(
    "/api/admin/knowledge-points/<int:point_id>/locations/<int:location_id>"
)
def admin_delete_location(point_id, location_id):
    course_code = request.args.get(
        "course", ""
    ).strip().upper()

    point = find_admin_point(point_id, course_code)
    location = db.session.get(ResourceLocation, location_id)

    if (
        point is None
        or location is None
        or location.knowledge_point_id != point.knowledge_point_id
        or location.course_id != point.course_id
    ):
        return jsonify({"error": "PDF location not found."}), 404

    db.session.delete(location)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to delete PDF location."
        }), 409

    return jsonify({
        "message": "PDF location deleted successfully."
    })

# Step 5.5.2 - Create a PDF resource
@app.post("/api/admin/resources")
def admin_create_resource():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data."}), 400

    course_code = data.get("course_code")
    title = data.get("title")
    file_url = data.get("file_url")
    total_pages = data.get("total_pages")

    if (
        not isinstance(course_code, str)
        or not isinstance(title, str)
        or not isinstance(file_url, str)
        or type(total_pages) is not int
    ):
        return jsonify({"error": "Invalid input format."}), 400

    course_code = course_code.strip().upper()
    title = title.strip()
    file_url = file_url.strip()

    if not title or len(title) > 250 or total_pages < 1:
        return jsonify({
            "error": "Invalid PDF title or page count."
        }), 400

    try:
        validate_registered_pdf(app.static_folder, file_url, total_pages)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    course = db.session.execute(
        select(Course).where(
            Course.course_code == course_code
        )
    ).scalar_one_or_none()

    if course is None:
        return jsonify({"error": "Course not found."}), 404

    existing = db.session.execute(
        select(Resource).where(
            Resource.course_id == course.course_id,
            Resource.file_url == file_url
        )
    ).scalar_one_or_none()

    if existing is not None:
        return jsonify({
            "error": "This PDF resource is already registered."
        }), 409

    resource = Resource(
        course_id=course.course_id,
        title=title,
        file_url=file_url,
        total_pages=total_pages
    )

    db.session.add(resource)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to create PDF resource."
        }), 409

    return jsonify({
        "message": "PDF resource added successfully.",
        "id": resource.resource_id
    }), 201

# Step 5.5.3 - Update PDF resource
@app.put("/api/admin/resources/<int:resource_id>")
def admin_update_resource(resource_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON data."}), 400

    course_code = data.get("course_code")
    title = data.get("title")
    file_url = data.get("file_url")
    total_pages = data.get("total_pages")

    if (
        not isinstance(course_code, str)
        or not isinstance(title, str)
        or not isinstance(file_url, str)
        or type(total_pages) is not int
    ):
        return jsonify({"error": "Invalid input format."}), 400

    course_code = course_code.strip().upper()
    title = title.strip()
    file_url = file_url.strip()

    if not title or len(title) > 250 or total_pages < 1:
        return jsonify({
            "error": "Invalid title or total page count."
        }), 400

    course = db.session.execute(
        select(Course).where(
            Course.course_code == course_code
        )
    ).scalar_one_or_none()

    resource = db.session.execute(
        select(Resource).where(Resource.resource_id == resource_id).with_for_update()
    ).scalar_one_or_none()

    if (
        course is None
        or resource is None
        or resource.course_id != course.course_id
    ):
        return jsonify({"error": "PDF resource not found."}), 404

    try:
        validate_registered_pdf(app.static_folder, file_url, total_pages)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    # Check existing knowledge-point mappings
    highest_page = db.session.execute(
        select(ResourceLocation.page_number)
        .where(ResourceLocation.resource_id == resource_id)
        .order_by(ResourceLocation.page_number.desc())
        .limit(1)
    ).scalar_one_or_none()

    if highest_page is not None:
        if file_url != resource.file_url:
            return jsonify({
                "error": (
                    "This PDF has existing mappings. "
                    "Remove them before changing the file."
                )
            }), 409

        if total_pages < highest_page:
            return jsonify({
                "error": (
                    "Total pages cannot be less than "
                    f"the highest mapped page ({highest_page})."
                )
            }), 400

    # Prevent duplicate paths in the same course
    duplicate = db.session.execute(
        select(Resource).where(
            Resource.course_id == course.course_id,
            Resource.file_url == file_url,
            Resource.resource_id != resource_id
        )
    ).scalar_one_or_none()

    if duplicate is not None:
        return jsonify({
            "error": "This PDF is already registered."
        }), 409

    resource.title = title
    resource.file_url = file_url
    resource.total_pages = total_pages

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to update PDF resource."
        }), 409

    return jsonify({
        "message": "PDF resource updated successfully."
    })


# Step 5.5.3 - Delete PDF resource
@app.delete("/api/admin/resources/<int:resource_id>")
def admin_delete_resource(resource_id):
    course_code = request.args.get(
        "course", ""
    ).strip().upper()

    course = db.session.execute(
        select(Course).where(
            Course.course_code == course_code
        )
    ).scalar_one_or_none()

    resource = db.session.execute(
        select(Resource).where(Resource.resource_id == resource_id).with_for_update()
    ).scalar_one_or_none()

    if (
        course is None
        or resource is None
        or resource.course_id != course.course_id
    ):
        return jsonify({"error": "PDF resource not found."}), 404

    # Do not delete a PDF used by knowledge points
    existing_mapping = db.session.execute(
        select(ResourceLocation.location_id)
        .where(ResourceLocation.resource_id == resource_id)
        .limit(1)
    ).scalar_one_or_none()

    if existing_mapping is not None:
        return jsonify({
            "error": (
                "This PDF is used by knowledge points. "
                "Delete its mappings first."
            )
        }), 409

    db.session.delete(resource)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to delete PDF resource."
        }), 409

    return jsonify({
        "message": "PDF resource deleted successfully."
    })

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=os.getenv("FLASK_DEBUG") == "1",
    )