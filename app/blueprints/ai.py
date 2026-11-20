"""AI summarisation API blueprint."""
from flask import Blueprint, jsonify, request

from app.services import ai_service, content_service
from app.utils.decorators import login_required

ai_bp = Blueprint("ai", __name__)


@ai_bp.post("/summary/<int:resource_id>")
@login_required()
def summary(resource_id):
    """Generate a key-points summary for one courseware file."""
    resource = content_service.get_resource(resource_id)
    if not resource:
        return jsonify({"error": "Resource not found."}), 404

    body = request.get_json(silent=True) or {}
    language = body.get("language", "en")
    if language not in ("en", "zh"):
        language = "en"

    try:
        text = ai_service.summarize(resource, language=language)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception:
        return jsonify({"error": "AI summary failed. Please try again."}), 502

    return jsonify(
        {
            "resource_id": resource_id,
            "title": resource.title,
            "language": language,
            "summary": text,
        }
    )
