"""Add the explicitly synthetic same-name demonstration to existing data."""
from sqlalchemy import select
from app import app
from models import db, Course, KnowledgePoint, Resource, ResourceLocation
from pdf_service import validate_registered_pdf

def add_demo_fixture():
    course = db.session.scalar(select(Course).where(Course.course_code == 'TEST002'))
    if course is None:
        raise ValueError('TEST002 is missing. Use seed.py for an empty database.')
    resource = db.session.scalar(select(Resource).where(Resource.course_id == course.course_id,
        Resource.file_url == '/static/pdfs/test002_notes.pdf'))
    if resource is None:
        raise ValueError('Register the TEST002 synthetic PDF before adding this fixture.')
    validate_registered_pdf(app.static_folder, resource.file_url, resource.total_pages)
    point = db.session.scalar(select(KnowledgePoint).where(KnowledgePoint.course_id == course.course_id,
        KnowledgePoint.normalized_name == 'natural join'))
    if point is None:
        point = KnowledgePoint(course_id=course.course_id, name='Natural Join', normalized_name='natural join',
            description='Synthetic demonstration record: independent TEST002 concept, not SOE206TC teaching content.')
        db.session.add(point); db.session.flush()
    elif not (point.description or '').startswith('Synthetic demonstration record:'):
        raise ValueError('An existing non-fixture Natural Join was found; no changes made.')
    mapping = db.session.scalar(select(ResourceLocation).where(
        ResourceLocation.knowledge_point_id == point.knowledge_point_id,
        ResourceLocation.resource_id == resource.resource_id, ResourceLocation.page_number == 4))
    if mapping is None:
        db.session.add(ResourceLocation(course_id=course.course_id,knowledge_point_id=point.knowledge_point_id,
            resource_id=resource.resource_id,page_number=4,note='Synthetic course-isolation demonstration; TEST002 only.'))
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        try:
            add_demo_fixture()
        except Exception:
            db.session.rollback()
            raise
        print('Synthetic TEST002 Natural Join fixture is ready; existing teaching records preserved.')
