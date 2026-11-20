"""Database models.

The schema keeps the original knowledge-point navigation domain and adds
user accounts for authentication and role-based access control.
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import (
    BigInteger,
    Identity,
    ForeignKeyConstraint,
    UniqueConstraint,
    CheckConstraint,
    Index,
    String,
)

from app.extensions import db


class User(UserMixin, db.Model):
    """A registered account. Either an administrator or a student."""

    __tablename__ = "app_user"

    id = db.Column(BigInteger, Identity(always=True), primary_key=True)
    email = db.Column(String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(String(255), nullable=False)
    role = db.Column(String(20), nullable=False, default="student")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'student')", name="user_role_check"),
    )

    @property
    def is_admin(self):
        """Return True when this user has the administrator role."""
        return self.role == "admin"

    def set_password(self, password):
        """Store a salted hash of the given plaintext password."""
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Return True when the plaintext password matches the stored hash."""
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, password)


class Course(db.Model):
    """A course that owns knowledge points and courseware resources."""

    __tablename__ = "course"

    course_id = db.Column(BigInteger, Identity(always=True), primary_key=True)
    course_code = db.Column(String(80), nullable=False, unique=True)
    title = db.Column(String(200), nullable=False)

    knowledge_points = db.relationship(
        "KnowledgePoint", back_populates="course", passive_deletes="all"
    )
    resources = db.relationship(
        "Resource", back_populates="course", passive_deletes="all"
    )


class KnowledgePoint(db.Model):
    """A concept that can be searched and mapped to courseware pages."""

    __tablename__ = "knowledge_point"

    knowledge_point_id = db.Column(
        BigInteger, Identity(always=True), primary_key=True
    )
    course_id = db.Column(
        BigInteger,
        db.ForeignKey("course.course_id", ondelete="CASCADE"),
        nullable=False,
    )
    name = db.Column(String(200), nullable=False)
    normalized_name = db.Column(String(200), nullable=False)
    description = db.Column(db.Text)

    __table_args__ = (
        UniqueConstraint(
            "course_id", "normalized_name", name="uq_kp_name_in_course"
        ),
        UniqueConstraint(
            "knowledge_point_id", "course_id", name="uq_kp_id_course"
        ),
    )

    course = db.relationship("Course", back_populates="knowledge_points")
    aliases = db.relationship(
        "KnowledgePointAlias",
        back_populates="knowledge_point",
        passive_deletes="all",
    )


class KnowledgePointAlias(db.Model):
    """An alternative name that maps to a knowledge point."""

    __tablename__ = "knowledge_point_alias"

    alias_id = db.Column(BigInteger, Identity(always=True), primary_key=True)
    knowledge_point_id = db.Column(
        BigInteger,
        db.ForeignKey("knowledge_point.knowledge_point_id", ondelete="CASCADE"),
        nullable=False,
    )
    alias = db.Column(String(200), nullable=False)
    normalized_alias = db.Column(String(200), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "knowledge_point_id", "normalized_alias", name="uq_alias_per_point"
        ),
        Index("idx_alias_lookup", "normalized_alias"),
    )

    knowledge_point = db.relationship(
        "KnowledgePoint", back_populates="aliases"
    )


class Resource(db.Model):
    """A courseware file (PDF or PPTX) registered for a course."""

    __tablename__ = "resource"

    resource_id = db.Column(BigInteger, Identity(always=True), primary_key=True)
    course_id = db.Column(
        BigInteger,
        db.ForeignKey("course.course_id", ondelete="CASCADE"),
        nullable=False,
    )
    title = db.Column(String(250), nullable=False)
    file_url = db.Column(db.Text, nullable=False)
    file_type = db.Column(String(10), nullable=False, default="pdf")
    total_pages = db.Column(db.Integer, nullable=False, default=1)
    uploaded_by = db.Column(
        BigInteger, db.ForeignKey("app_user.id", ondelete="SET NULL")
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("resource_id", "course_id", name="uq_resource_id_course"),
        UniqueConstraint(
            "course_id", "file_url", name="uq_resource_file_in_course"
        ),
        CheckConstraint("total_pages >= 1", name="resource_total_pages_check"),
        CheckConstraint(
            "file_type IN ('pdf', 'pptx')", name="resource_file_type_check"
        ),
    )

    course = db.relationship("Course", back_populates="resources")
    locations = db.relationship(
        "ResourceLocation", back_populates="resource", passive_deletes="all"
    )


class ResourceLocation(db.Model):
    """Maps a knowledge point to a specific page inside a courseware file."""

    __tablename__ = "resource_location"

    location_id = db.Column(BigInteger, Identity(always=True), primary_key=True)
    course_id = db.Column(BigInteger, nullable=False)
    knowledge_point_id = db.Column(BigInteger, nullable=False)
    resource_id = db.Column(BigInteger, nullable=False)
    page_number = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Text)

    __table_args__ = (
        ForeignKeyConstraint(
            ["knowledge_point_id", "course_id"],
            ["knowledge_point.knowledge_point_id", "knowledge_point.course_id"],
            name="fk_location_point_same_course",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["resource_id", "course_id"],
            ["resource.resource_id", "resource.course_id"],
            name="fk_location_resource_same_course",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "knowledge_point_id",
            "resource_id",
            "page_number",
            name="uq_point_resource_page",
        ),
        CheckConstraint(
            "page_number >= 1", name="resource_location_page_number_check"
        ),
        Index("idx_location_point_course", "knowledge_point_id", "course_id"),
        Index("idx_location_resource_course", "resource_id", "course_id"),
    )

    resource = db.relationship("Resource", back_populates="locations")
