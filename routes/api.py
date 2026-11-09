"""Small JSON endpoints used by the public site's JavaScript."""
from flask import Blueprint, request

from extensions import limiter
from services.tracking import track_contact_click

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.post("/track")
@limiter.limit("60 per minute")
def track():
    """Records a contact-button click. Requires the CSRF header from the page."""
    data = request.get_json(silent=True) or {}
    if data.get("type") != "contact_click":
        return ("", 400)
    path = str(data.get("path", "/"))
    if not path.startswith("/") or path.startswith("//"):
        path = "/"
    track_contact_click(str(data.get("channel", "")), path)
    return ("", 204)
