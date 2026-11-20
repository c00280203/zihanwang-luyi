"""Curated knowledge-point seeds derived from courseware topics.

Each entry lists knowledge points and aliases for a course. Mappings point to
page 1 of the matching courseware, giving students a useful starting point;
administrators can refine exact pages later.
"""
import re

from app.extensions import db
from app.models import Course, KnowledgePoint, KnowledgePointAlias, Resource, ResourceLocation


SEEDS = {
    "AIP202TC": [
        ("Linear Regression", ["Linear Regression", "Least Squares", "线性回归"]),
        ("Logistic Regression", ["Logistic Regression", "Sigmoid", "逻辑回归"]),
        ("Support Vector Machine", ["SVM", "Support Vector Machine", "支持向量机"]),
        ("K-Nearest Neighbors", ["KNN", "K-Nearest Neighbors", "K近邻"]),
        ("Kernel Methods", ["Kernel", "Kernel Trick", "核方法"]),
        ("Decision Tree", ["Decision Tree", "决策树"]),
        ("Model Selection", ["Model Selection", "Cross Validation", "模型选择"]),
        ("Clustering", ["Clustering", "K-Means", "聚类"]),
        ("Principal Component Analysis", ["PCA", "Principal Component Analysis", "主成分分析"]),
        ("Neural Network", ["Neural Network", "Neural Networks", "Neuron Network", "Artificial Neural Network", "神经网络", "神经元网络"]),
        ("Deep Learning", ["Deep Learning", "Deep Neural Network", "深度学习"]),
    ],
    "CSI205TC": [
        ("Application Layer", ["Application Layer", "HTTP", "DNS", "应用层"]),
        ("Transport Layer", ["Transport Layer", "TCP", "UDP", "传输层"]),
        ("Network Layer", ["Network Layer", "IP", "Routing", "网络层"]),
        ("Link Layer", ["Link Layer", "Ethernet", "链路层"]),
        ("Subnet Masks", ["Subnet Mask", "Subnetting", "子网掩码"]),
        ("Distributed Computing", ["Distributed Computing", "分布式计算"]),
        ("HDFS", ["HDFS", "Hadoop Distributed File System"]),
        ("MapReduce", ["MapReduce", "Hadoop", "Spark"]),
    ],
    "ENT207TC": [
        ("Prototype", ["Prototype", "MVP", "原型"]),
        ("Customer Discovery", ["Customer Discovery", "Interview", "客户发现"]),
        ("Value Proposition", ["Value Proposition", "价值主张"]),
        ("Business Model Canvas", ["Business Model", "Canvas", "商业模式"]),
        ("Pitch", ["Pitch", "Promo", "路演"]),
        ("DeepSeek API", ["DeepSeek", "API Key", "AI Integration"]),
    ],
    "SOE206TC": [
        ("SQL Joins", ["JOIN", "Natural Join", "Outer Join", "连接查询"]),
        ("SQL Views", ["View", "视图"]),
        ("Third Normal Form", ["3NF", "Normalization", "第三范式"]),
        ("Nested Queries", ["Subquery", "Subqueries", "嵌套查询"]),
        ("Data Warehouse", ["Data Warehouse", "OLAP", "ETL", "数据仓库"]),
        ("UML Diagrams", ["UML", "Class Diagram", "Use Case", "Sequence Diagram"]),
        ("ORM", ["ORM", "Object Relational Mapping"]),
        ("XML", ["XML", "XPath"]),
        ("Database Design", ["Database Design", "ER Model", "数据库设计"]),
    ],
}


def normalize(text):
    """Normalize a string for consistent fuzzy matching."""
    return " ".join((text or "").strip().lower().split())


def seed_knowledge_points():
    """Create knowledge points, aliases and first-page mappings for all courses."""
    courses = db.session.scalars(db.select(Course)).all()
    by_code = {c.course_code: c for c in courses}

    for code_prefix, entries in SEEDS.items():
        course = next((c for code, c in by_code.items() if code.startswith(code_prefix)), None)
        if not course:
            continue

        resources = db.session.scalars(
            db.select(Resource).where(Resource.course_id == course.course_id)
        ).all()
        if not resources:
            continue

        for name, aliases in entries:
            kp = db.session.scalar(
                db.select(KnowledgePoint).where(
                    KnowledgePoint.course_id == course.course_id,
                    KnowledgePoint.normalized_name == normalize(name),
                )
            )
            if not kp:
                kp = KnowledgePoint(
                    course_id=course.course_id,
                    name=name,
                    normalized_name=normalize(name),
                    description="Key concept in " + course.title + ".",
                )
                db.session.add(kp)
                db.session.flush()

                for alias in aliases:
                    exists = db.session.scalar(
                        db.select(KnowledgePointAlias).where(
                            KnowledgePointAlias.knowledge_point_id == kp.knowledge_point_id,
                            KnowledgePointAlias.normalized_alias == normalize(alias),
                        )
                    )
                    if not exists:
                        db.session.add(
                            KnowledgePointAlias(
                                knowledge_point_id=kp.knowledge_point_id,
                                alias=alias,
                                normalized_alias=normalize(alias),
                            )
                        )

                # Map to the courseware whose title best matches, else the first one.
                target = _best_resource(name, resources) or resources[0]
                db.session.add(
                    ResourceLocation(
                        course_id=course.course_id,
                        knowledge_point_id=kp.knowledge_point_id,
                        resource_id=target.resource_id,
                        page_number=1,
                        note="Suggested location; refine the exact page if needed.",
                    )
                )
    db.session.flush()


def _best_resource(name, resources):
    """Find a resource whose title shares a meaningful word with the point."""
    keywords = [w.lower() for w in re.split(r"\W+", name) if len(w) > 3]
    for resource in resources:
        title = resource.title.lower()
        if any(word in title for word in keywords):
            return resource
    return None
