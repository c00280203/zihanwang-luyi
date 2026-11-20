"""Database seeding helpers.

Creates the built-in accounts, the four courses, and imports reference
courseware (PDF/PPTX) from the "大三上课程" folder into the database.
"""
import shutil
from pathlib import Path

from app.config import BASE_DIR
from app.extensions import db
from app.models import Course, Resource, User


COURSES = [
    "AIP202TC-2627-S1-Machine Learning",
    "CSI205TC-2627-S1-Networking and Distributed Computing",
    "ENT207TC-2627-S1-Digital Startup Lab",
    "SOE206TC-2627-S1-Database Development and Design",
]

# Map reference folder names to full course codes.
FOLDER_TO_CODE = {
    "AIP202": COURSES[0],
    "CSI205": COURSES[1],
    "ENT207": COURSES[2],
    "SOE206": COURSES[3],
}


def seed_all():
    """Seed accounts, courses and courseware in one transaction."""
    _seed_accounts()
    course_map = _seed_courses()
    _import_courseware(course_map)
    from app.kp_seeder import seed_knowledge_points

    seed_knowledge_points()
    db.session.commit()
    print("Seed complete: accounts, courses, courseware and knowledge points are ready.")


def _seed_accounts():
    """Create the built-in administrator and student accounts if missing."""
    accounts = [
        ("admin@123.com", "123456", "admin"),
        ("student@123.com", "123456", "student"),
    ]
    for email, password, role in accounts:
        exists = db.session.scalar(db.select(User).where(User.email == email))
        if exists:
            continue
        user = User(email=email, role=role)
        user.set_password(password)
        db.session.add(user)


def _seed_courses():
    """Create the four courses and return a code-to-row mapping."""
    result = {}
    for code in COURSES:
        course = db.session.scalar(
            db.select(Course).where(Course.course_code == code)
        )
        if not course:
            title = code.split("-", 3)[-1] if "-" in code else code
            course = Course(course_code=code, title=title)
            db.session.add(course)
            db.session.flush()
        result[code] = course
    return result


def _import_courseware(course_map):
    """Copy reference PDF/PPTX files into static storage and register them.

    On a fresh clone the reference folder is missing (it is git-ignored), so
    fall back to the committed static/courseware files. This keeps seeding
    reproducible on Vercel/Supabase and any new machine.
    """
    source_root = BASE_DIR / "大三上课程"
    target_root = BASE_DIR / "static" / "courseware"
    target_root.mkdir(parents=True, exist_ok=True)

    if source_root.exists():
        _import_from_reference(source_root, target_root, course_map)
    else:
        print("Reference folder not found; seeding from static/courseware.")
        _import_from_static(target_root, course_map)
    db.session.flush()


def _register_resource(course, path, title, file_url, file_type):
    """Add a resource when a file with the same course and title is absent."""
    existing = db.session.scalar(
        db.select(Resource).where(
            Resource.course_id == course.course_id,
            Resource.title == title,
        )
    )
    if existing:
        return
    db.session.add(
        Resource(
            course_id=course.course_id,
            title=title,
            file_url=file_url,
            file_type=file_type,
            total_pages=_count_pages(path, file_type),
        )
    )


def _import_from_reference(source_root, target_root, course_map):
    """Import the original reference tree into static storage."""
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".pdf", ".pptx"):
            continue
        code = _match_course(path)
        if not code:
            continue
        course = course_map[code]
        safe_name = f"{course.course_id}_{path.stem}{path.suffix.lower()}"
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in safe_name)
        destination = target_root / safe_name
        if not destination.exists():
            shutil.copy2(path, destination)
        _register_resource(
            course, destination, path.stem,
            f"/static/courseware/{safe_name}", path.suffix.lower().lstrip("."),
        )


def _import_from_static(target_root, course_map):
    """Register already-committed static files by their course-id prefix."""
    id_to_course = {str(c.course_id): c for c in course_map.values()}
    for path in sorted(target_root.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (".pdf", ".pptx"):
            continue
        prefix = path.name.split("_", 1)[0]
        course = id_to_course.get(prefix)
        if not course:
            continue
        title = path.stem.split("_", 1)[1] if "_" in path.stem else path.stem
        _register_resource(
            course, path, title,
            f"/static/courseware/{path.name}", path.suffix.lower().lstrip("."),
        )


def _match_course(path):
    """Determine which course a reference file belongs to by its folder.

    Only path segments below the "大三上课程" root are considered, so the
    project directory name (which contains SOE206TC) cannot cause a false
    match.
    """
    parts = list(path.parts)
    try:
        root_index = parts.index("大三上课程")
        parts = parts[root_index + 1 :]
    except ValueError:
        parts = []

    for part in parts:
        upper = part.upper()
        for key, code in FOLDER_TO_CODE.items():
            if upper.startswith(key):
                return code
    return None


def _count_pages(path, file_type):
    """Count pages/slides of a file, returning 1 on failure."""
    try:
        if file_type == ".pdf":
            from pypdf import PdfReader

            return max(1, len(PdfReader(str(path)).pages))
        from pptx import Presentation

        return max(1, len(Presentation(str(path)).slides))
    except Exception:
        return 1
