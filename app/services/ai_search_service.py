"""Semantic knowledge-point search powered by DeepSeek.

The knowledge-point catalog is small, so it is sent in one request and the
model ranks concepts by meaning. This lets natural-language questions such as
"I wanna study Algorithm" reach the right material without keyword tricks.
"""
import json
import re

from sqlalchemy import func, select

from app.config import Config
from app.extensions import db
from app.models import (
    Course,
    KnowledgePoint,
    Resource,
    ResourceLocation,
)
from app.services.ai_service import _chat
from app.services.search_service import _serialize

MAX_MATCHES = 8

SEARCH_SYSTEM_PROMPT = (
    "You are a precise academic search engine for a university course hub. "
    "You receive a catalog of knowledge points and a student's question in "
    "natural language. Select the knowledge points that best answer it.\n"
    "Rules:\n"
    "- Return ONLY one valid JSON object, with no markdown or extra text.\n"
    "- Use only IDs present in the catalog. Never invent an ID.\n"
    "- Match meaning, not literal words. Understand synonyms, paraphrases "
    "and intent (for example 'I wanna study Algorithm' asks for algorithm "
    "topics; 'how is a table organised' may point to normalisation).\n"
    "- Rank by relevance and return at most 8 matches. Return an empty list "
    "when nothing is genuinely relevant.\n"
    "- Each reason is one short sentence in the same language as the answer.\n"
    "- Never mention numeric IDs in the answer or reasons; use topic names.\n"
    "- score is a number between 0 and 1.\n"
    'JSON format: {"answer":"...","matches":[{"id":123,"score":0.9,"reason":"..."}]}'
)


def _clean(text):
    """Make a catalog value safe for a single pipe-delimited line."""
    return " ".join(str(text or "").replace("|", "/").split())


def _catalog(course_code):
    """Build the candidate catalog and lookup maps for the requested scope."""
    statement = (
        select(KnowledgePoint, Course.course_code, Course.title)
        .join(Course, KnowledgePoint.course_id == Course.course_id)
        .order_by(Course.course_code, KnowledgePoint.name)
    )
    scope = (course_code or "").strip()
    if scope.lower() not in ("", "all", "any", "*"):
        statement = statement.where(
            func.lower(Course.course_code) == scope.lower()
        )
    rows = db.session.execute(statement).all()

    location_rows = db.session.execute(
        select(ResourceLocation.knowledge_point_id, Resource.title)
        .join(Resource, ResourceLocation.resource_id == Resource.resource_id)
    ).all()
    titles_by_point = {}
    for point_id, title in location_rows:
        bucket = titles_by_point.setdefault(point_id, [])
        if title not in bucket:
            bucket.append(title)

    lines = []
    courses = {}
    points = []
    for point, code, title in rows:
        points.append(point)
        courses[point.course_id] = (code, title)
        aliases = [_clean(a.alias) for a in point.aliases][:6]
        files = [_clean(t) for t in titles_by_point.get(point.knowledge_point_id, [])][:3]
        description = _clean(point.description)[:150]
        parts = [
            f"id={point.knowledge_point_id}",
            f"course={_clean(code)}",
            f"name={_clean(point.name)}",
            f"aliases={', '.join(aliases) or '-'}",
            f"description={description or '-'}",
            f"files={', '.join(files) or '-'}",
        ]
        lines.append("- " + " | ".join(parts))
    return lines, courses, points


def _parse_payload(raw):
    """Parse the model response, tolerating an optional code fence."""
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("AI search returned an unexpected payload.")
    return data


def _score(value):
    """Clamp a model-provided score into the 0-1 range."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.5
    return round(max(0.0, min(1.0, score)), 2)


def search(course_code, question, language="en"):
    """Rank knowledge points semantically for a natural-language question.

    Returns a dictionary with a short AI answer and serialized results that
    include the exact courseware pages. Raises RuntimeError/ValueError when the
    AI is unavailable so the API layer can fall back to keyword search.
    """
    if not Config.DEEPSEEK_API_KEY:
        raise RuntimeError("DeepSeek API key is not configured.")

    lines, courses, points = _catalog(course_code)
    index = {point.knowledge_point_id: point for point in points}
    scope = (course_code or "").strip()
    if scope.lower() in ("", "all", "any", "*"):
        scope_label = "All courses"
    else:
        scope_label = scope
    language_name = "Simplified Chinese" if language == "zh" else "English"

    user_prompt = (
        f"Student question: {question}\n"
        f"Course filter: {scope_label}\n"
        f"Write the answer and reasons in {language_name}.\n\n"
        f"Knowledge point catalog:\n" + "\n".join(lines[:120])
    )
    raw = _chat(
        SEARCH_SYSTEM_PROMPT,
        user_prompt,
        max_tokens=900,
        response_format={"type": "json_object"},
    )
    data = _parse_payload(raw)

    answer = str(data.get("answer") or "").strip()[:600]
    matches = data.get("matches")
    if not isinstance(matches, list):
        matches = []

    ranked = []
    seen = set()
    for item in matches:
        if not isinstance(item, dict):
            continue
        try:
            point_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if point_id not in index or point_id in seen:
            continue
        seen.add(point_id)
        reason = str(item.get("reason") or "").strip()[:220]
        ranked.append((_score(item.get("score")), point_id, reason))
    ranked.sort(key=lambda entry: -entry[0])
    ranked = ranked[:MAX_MATCHES]

    selected = [index[point_id] for _, point_id, _ in ranked]
    results = _serialize(selected, courses)
    reasons = {point_id: reason for _, point_id, reason in ranked}
    scores = {point_id: score for score, point_id, _ in ranked}
    for result in results:
        point_id = result["knowledge_point_id"]
        result["reason"] = reasons.get(point_id, "")
        result["score"] = scores.get(point_id, 0.5)

    return {"answer": answer, "count": len(results), "results": results}
