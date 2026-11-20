"""Knowledge-point search with intent-aware matching.

An exact substring pass runs first. When it finds nothing, a fuzzy fallback
compares meaningful word tokens so natural-language questions still reach the
right concept, while irrelevant stop-word collisions are ignored.
"""
import re

from sqlalchemy import select, or_, and_, func

from app.extensions import db
from app.models import (
    Course,
    KnowledgePoint,
    KnowledgePointAlias,
    Resource,
    ResourceLocation,
)

# Words that carry no search intent. Filtering them prevents a question such
# as "I wanna study neuron network" from matching every label via "i" or "do".
STOP_WORDS = frozenset({
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "its",
    "a", "an", "the", "this", "that", "these", "those",
    "is", "are", "was", "were", "be", "been", "being", "am",
    "do", "does", "did", "have", "has", "had", "having",
    "can", "could", "would", "should", "will", "shall", "may", "might", "must",
    "to", "of", "in", "on", "at", "by", "for", "with", "about", "into", "from",
    "and", "or", "but", "if", "so", "as", "than", "then",
    "want", "wanna", "wants", "need", "needs", "study", "studying", "learn",
    "learning", "know", "find", "show", "tell", "give", "suggest", "suggestion",
    "suggestions", "recommend", "please", "some", "any", "all", "there", "here",
    "what", "which", "who", "how", "why", "when", "where", "hey", "hi", "hello",
    "thanks", "thank", "much", "many", "get", "got", "looking", "look", "im",
    "ive", "dont", "doesnt", "students", "student", "anyone", "something",
})

# Lightweight concept hints so common wording differences still connect.
CONCEPT_HINTS = {
    "neuron": "neural",
    "neurons": "neural",
    "nn": "neural",
    "normalisation": "normalize",
    "normalise": "normalize",
    "normalization": "normalize",
    "normalizing": "normalize",
}


def _normalize(text):
    """Lowercase and collapse whitespace for consistent comparison."""
    return " ".join((text or "").strip().lower().split())


def _tokens(text):
    """Extract meaningful tokens, keeping both the stem and its concept hint.

    Retaining the original word alongside its hint lets typo tolerance compare
    a misspelling with the full form (normaliztion -> normalization) instead of
    only the shortened hint (normalize).
    """
    parts = re.findall(r"[\w]+", _normalize(text), flags=re.UNICODE)
    tokens = []
    for part in parts:
        if len(part) < 2 or part in STOP_WORDS:
            continue
        stem = part
        if len(stem) > 3 and stem.endswith("s") and not stem.endswith("ss"):
            stem = stem[:-1]
        tokens.append(stem)
        hint = CONCEPT_HINTS.get(part) or CONCEPT_HINTS.get(stem)
        if hint and hint not in tokens:
            tokens.append(hint)
    return tokens


def _edit_distance(a, b):
    """Levenshtein distance used only for typo-tolerant long words."""
    if abs(len(a) - len(b)) > 3:
        return 99
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (ca != cb),
            ))
        previous = current
    return previous[-1]


def _tokens_close(q_tokens, l_tokens):
    """Return near-matching token pairs for misspelled long words."""
    pairs = set()
    for q in q_tokens:
        if len(q) < 5:
            continue
        for l in l_tokens:
            if len(l) < 5 or abs(len(q) - len(l)) > 3:
                continue
            if _edit_distance(q, l) <= 2:
                pairs.add((q, l))
    return pairs


def _match_score(query, label, allow_typo=False):
    """Score a query against a label using whole-word overlap.

    Typo tolerance is opt-in and only used for short queries, because near
    matches on long natural-language questions create unrelated suggestions.
    """
    q_norm, l_norm = _normalize(query), _normalize(label)
    if not q_norm or not l_norm:
        return 0.0
    if q_norm in l_norm:
        return 1.0

    q_tokens, l_tokens = set(_tokens(query)), set(_tokens(label))
    if not q_tokens or not l_tokens:
        # CJK labels have no spaces, so fall back to substring containment.
        if q_norm in l_norm or l_norm in q_norm:
            return 0.7
        return 0.0

    overlap = q_tokens & l_tokens
    if not overlap and allow_typo:
        near = _tokens_close(q_tokens, l_tokens)
        if near:
            overlap = {q for q, _ in near}
    if not overlap:
        return 0.0
    # A query fully covered by the label is a strong signal; partial coverage
    # still helps when the student adds extra words to the question.
    coverage = len(overlap) / len(q_tokens)
    return round(min(0.55 + 0.4 * coverage, 0.95), 2)


def _locations_for(points):
    """Fetch page mappings for a set of knowledge points, across courses."""
    if not points:
        return {}
    rows = db.session.execute(
        select(ResourceLocation, Resource)
        .join(
            Resource,
            and_(
                ResourceLocation.resource_id == Resource.resource_id,
                ResourceLocation.course_id == Resource.course_id,
            ),
        )
        .where(
            ResourceLocation.knowledge_point_id.in_(
                [p.knowledge_point_id for p in points]
            )
        )
        .order_by(Resource.title, ResourceLocation.page_number)
    ).all()

    locations = {p.knowledge_point_id: [] for p in points}
    for location, resource in rows:
        bucket = locations.get(location.knowledge_point_id)
        if bucket is None:
            continue
        bucket.append(
            {
                "resource_id": resource.resource_id,
                "resource_title": resource.title,
                "file_url": resource.file_url,
                "file_type": resource.file_type,
                "page_number": location.page_number,
                "note": location.note,
            }
        )
    return locations


def _serialize(points, courses, fuzzy=False):
    """Build API result objects with course labels and page mappings."""
    locations = _locations_for(points)
    results = []
    for point in points:
        code, title = courses.get(point.course_id, ("", ""))
        results.append(
            {
                "knowledge_point_id": point.knowledge_point_id,
                "name": point.name,
                "description": point.description,
                "course_code": code,
                "course_title": title,
                "fuzzy": fuzzy,
                "locations": locations[point.knowledge_point_id],
            }
        )
    return results


def search(course_code, keyword):
    """Search knowledge points in one course, or in all courses when requested.

    An empty keyword returns every point in scope. Exact matches are returned
    first; otherwise an intent-aware fuzzy pass suggests genuinely related
    points from every course so a term typed under the wrong filter still helps.
    """
    scope = (course_code or "").strip()
    global_scope = scope.lower() in ("", "all", "any", "*")
    term = _normalize(keyword)

    statement = (
        select(KnowledgePoint, Course.course_code, Course.title)
        .join(Course, KnowledgePoint.course_id == Course.course_id)
    )
    if not global_scope:
        # Course codes mix upper- and lower-case, so compare case-insensitively.
        statement = statement.where(
            func.lower(Course.course_code) == scope.lower()
        )
    if term:
        statement = statement.where(
            or_(
                KnowledgePoint.normalized_name.contains(term, autoescape=True),
                KnowledgePoint.aliases.any(
                    KnowledgePointAlias.normalized_alias.contains(
                        term, autoescape=True
                    )
                ),
            )
        )
    statement = statement.order_by(Course.course_code, KnowledgePoint.name)
    rows = db.session.execute(statement).all()
    courses = {point.course_id: (code, title) for point, code, title in rows}
    points = [point for point, _, _ in rows]
    if points:
        return _serialize(points, courses)

    if not term:
        return []

    # Fuzzy fallback: require real word overlap so unrelated points are never
    # suggested just because a stop word appeared in both strings.
    candidates = db.session.execute(
        select(KnowledgePoint, Course.course_code, Course.title)
        .join(Course, KnowledgePoint.course_id == Course.course_id)
    ).all()
    # Only a single-word query gets typo tolerance. Natural-language questions
    # reduce to a couple of tokens after stop-word filtering and would trigger
    # false near-matches (e.g. neural/natural), so they stay on exact overlap.
    allow_typo = len(term.split()) == 1
    scored = []
    for point, code, title in candidates:
        labels = [point.name] + [alias.alias for alias in point.aliases]
        best = max(
            (_match_score(term, label, allow_typo) for label in labels),
            default=0.0,
        )
        if best >= 0.55:
            scored.append((best, point, code, title))
    scored.sort(key=lambda item: (-item[0], item[1].name))
    picked = scored[:8]
    courses = {point.course_id: (code, title) for _, point, code, title in picked}
    return _serialize([item[1] for item in picked], courses, fuzzy=True)


def list_courses():
    """Return all courses ordered by code."""
    courses = db.session.execute(
        select(Course).order_by(Course.course_code)
    ).scalars().all()
    return [
        {"course_code": c.course_code, "title": c.title}
        for c in courses
    ]
