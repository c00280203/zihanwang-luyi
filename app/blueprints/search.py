"""Search API blueprint."""
from flask import Blueprint, current_app, jsonify, request

from app.services import ai_search_service, search_service
from app.utils.decorators import login_required

search_bp = Blueprint("search", __name__)


def _search_args():
    """Read and validate the shared search query parameters."""
    course_code = (request.args.get("course") or "").strip()
    keyword = (request.args.get("q") or "").strip()
    if len(keyword) > 200:
        return None, None, (jsonify({"error": "Search input is too long."}), 400)
    return course_code, keyword, None


@search_bp.get("/")
@login_required()
def search():
    """Fuzzy-search knowledge points across one course or every course."""
    course_code, keyword, error = _search_args()
    if error:
        return error
    if not course_code:
        return jsonify({"error": "Please select a course."}), 400

    results = search_service.search(course_code, keyword)
    return jsonify(
        {
            "course": course_code,
            "query": keyword,
            "count": len(results),
            "results": results,
        }
    )


@search_bp.get("/ai")
@login_required()
def ai_search():
    """Semantic search: let AI match a natural-language question to topics.

    When the AI service is unavailable the endpoint degrades gracefully to the
    existing keyword search and reports the mode so the UI can explain it.
    """
    course_code, keyword, error = _search_args()
    if error:
        return error
    if not keyword:
        return jsonify({"error": "Please describe what you want to learn."}), 400

    language = (request.args.get("lang") or "en").strip().lower()
    if language not in ("en", "zh"):
        language = "en"

    try:
        payload = ai_search_service.search(course_code, keyword, language=language)
        payload.update(
            {
                "course": course_code,
                "query": keyword,
                "mode": "ai",
                "language": language,
            }
        )
        return jsonify(payload)
    except Exception as exc:
        current_app.logger.warning("AI search failed, using keyword search: %s", exc)
        results = search_service.search(course_code or "all", keyword)
        return jsonify(
            {
                "course": course_code,
                "query": keyword,
                "answer": "",
                "count": len(results),
                "results": results,
                "mode": "keyword",
                "language": language,
            }
        )
