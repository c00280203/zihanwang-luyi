from sqlalchemy import select, or_, and_

from models import (
    db,
    Course,
    KnowledgePoint,
    KnowledgePointAlias,
    Resource,
    ResourceLocation,
)


def search_knowledge_points(course_code, keyword):
    """
    Search knowledge points within one selected course.
    Match names or aliases and return mapped PDF locations.
    """

    course_code = course_code.strip().upper()
    search_term = " ".join(keyword.strip().lower().split())

    # Find knowledge points within the selected course
    statement = (
        select(KnowledgePoint)
        .join(Course, KnowledgePoint.course_id == Course.course_id)
        .where(Course.course_code == course_code)
    )

    # An empty keyword means browsing all knowledge points
    if search_term:
        statement = statement.where(
            or_(
                KnowledgePoint.normalized_name.contains(search_term, autoescape=True),
                KnowledgePoint.aliases.any(
                    KnowledgePointAlias.normalized_alias.contains(
                        search_term, autoescape=True
                    )
                ),
            )
        )

    statement = statement.order_by(KnowledgePoint.name)

    knowledge_points = db.session.execute(
        statement
    ).scalars().all()

    if not knowledge_points:
        return []

    # Fetch every matching point's mappings in one batch (avoid N+1 queries).
    location_rows = db.session.execute(
        select(ResourceLocation, Resource)
        .join(Resource, and_(
            ResourceLocation.resource_id == Resource.resource_id,
            ResourceLocation.course_id == Resource.course_id,
        ))
        .where(
            ResourceLocation.knowledge_point_id.in_(
                [point.knowledge_point_id for point in knowledge_points]
            ),
            ResourceLocation.course_id == knowledge_points[0].course_id,
        )
        .order_by(Resource.title, ResourceLocation.page_number, ResourceLocation.location_id)
    ).all()
    locations = {point.knowledge_point_id: [] for point in knowledge_points}
    for location, resource in location_rows:
        locations[location.knowledge_point_id].append({
            "location_id": location.location_id,
            "resource_title": resource.title,
            "file_url": resource.file_url,
            "page_number": location.page_number,
            "note": location.note,
        })
    return [{
        "knowledge_point_id": point.knowledge_point_id,
        "name": point.name,
        "description": point.description,
        "locations": locations[point.knowledge_point_id],
    } for point in knowledge_points]
