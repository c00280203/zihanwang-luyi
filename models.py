from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    Identity,
    ForeignKeyConstraint,
    UniqueConstraint,
    CheckConstraint,
    Index,
)

db = SQLAlchemy()

# 1. Course
class Course(db.Model):
    __tablename__ = "course"

    course_id = db.Column(
        db.BigInteger, Identity(always=True), primary_key=True
    )
    course_code = db.Column(
        db.String(40), nullable=False, unique=True
    )
    title = db.Column(db.String(200), nullable=False)

    knowledge_points = db.relationship(
        "KnowledgePoint", back_populates="course"
    )
    resources = db.relationship(
        "Resource", back_populates="course"
    )


# 2. Knowledge Point
class KnowledgePoint(db.Model):
    __tablename__ = "knowledge_point"

    knowledge_point_id = db.Column(
        db.BigInteger, Identity(always=True), primary_key=True
    )
    course_id = db.Column(
        db.BigInteger,
        db.ForeignKey("course.course_id", ondelete="RESTRICT"),
        nullable=False,
    )
    name = db.Column(db.String(200), nullable=False)
    normalized_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    __table_args__ = (
        UniqueConstraint(
            "course_id", "normalized_name",
            name="uq_kp_name_in_course",
        ),
        UniqueConstraint(
            "knowledge_point_id", "course_id",
            name="uq_kp_id_course",
        ),
    )

    course = db.relationship(
        "Course", back_populates="knowledge_points"
    )
    aliases = db.relationship(
        "KnowledgePointAlias",
        back_populates="knowledge_point",
        passive_deletes="all",
    )


# 3. Knowledge Point Alias
class KnowledgePointAlias(db.Model):
    __tablename__ = "knowledge_point_alias"

    alias_id = db.Column(
        db.BigInteger, Identity(always=True), primary_key=True
    )
    knowledge_point_id = db.Column(
        db.BigInteger,
        db.ForeignKey(
            "knowledge_point.knowledge_point_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    alias = db.Column(db.String(200), nullable=False)
    normalized_alias = db.Column(db.String(200), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "knowledge_point_id", "normalized_alias",
            name="uq_alias_per_point",
        ),
        Index("idx_alias_lookup", "normalized_alias"),
    )

    knowledge_point = db.relationship(
        "KnowledgePoint", back_populates="aliases"
    )


# 4. PDF Resource
class Resource(db.Model):
    __tablename__ = "resource"

    resource_id = db.Column(
        db.BigInteger, Identity(always=True), primary_key=True
    )
    course_id = db.Column(
        db.BigInteger,
        db.ForeignKey("course.course_id", ondelete="RESTRICT"),
        nullable=False,
    )
    title = db.Column(db.String(250), nullable=False)
    file_url = db.Column(db.Text, nullable=False)
    total_pages = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "resource_id", "course_id",
            name="uq_resource_id_course",
        ),
        UniqueConstraint("course_id", "file_url", name="uq_resource_file_in_course"),
        CheckConstraint(
            "total_pages >= 1",
            name="resource_total_pages_check",
        ),
    )

    course = db.relationship(
        "Course", back_populates="resources"
    )


# 5. Resource Location
class ResourceLocation(db.Model):
    __tablename__ = "resource_location"

    location_id = db.Column(
        db.BigInteger, Identity(always=True), primary_key=True
    )
    course_id = db.Column(db.BigInteger, nullable=False)
    knowledge_point_id = db.Column(db.BigInteger, nullable=False)
    resource_id = db.Column(db.BigInteger, nullable=False)
    page_number = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Text)

    __table_args__ = (
        ForeignKeyConstraint(
            ["knowledge_point_id", "course_id"],
            [
                "knowledge_point.knowledge_point_id",
                "knowledge_point.course_id",
            ],
            name="fk_location_point_same_course",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["resource_id", "course_id"],
            [
                "resource.resource_id",
                "resource.course_id",
            ],
            name="fk_location_resource_same_course",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "knowledge_point_id",
            "resource_id",
            "page_number",
            name="uq_point_resource_page",
        ),
        CheckConstraint(
            "page_number >= 1",
            name="resource_location_page_number_check",
        ),
        Index(
            "idx_location_point_course",
            "knowledge_point_id",
            "course_id",
        ),
        Index(
            "idx_location_resource_course",
            "resource_id",
            "course_id",
        ),
    )
