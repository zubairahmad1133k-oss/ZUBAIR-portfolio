"""Privacy-conscious visit tracking.

What is stored: a random visitor id (first-party cookie), the page path, and
the referring site's host name. What is NOT stored: IP address, user-agent,
or anything that identifies a person. Visitors who send Do-Not-Track or
Global-Privacy-Control are not tracked, and neither is the logged-in admin.
"""
import re
import secrets
from datetime import timedelta
from urllib.parse import urlparse

from flask import current_app, g, request
from flask_login import current_user

from extensions import db
from models import ContactEvent, PageEvent, ProjectView, Visitor
from models.base import utcnow

COOKIE_NAME = "zos_vid"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365
PROJECT_VIEW_WINDOW = timedelta(minutes=30)
_KEY_RE = re.compile(r"^[0-9a-f]{32}$")
_BOT_WORDS = (
    "bot", "crawl", "spider", "slurp", "preview", "headless", "curl", "wget",
    "python-requests", "monitor", "uptime", "lighthouse",
)
CONTACT_CHANNELS = ("whatsapp", "email")


def should_track() -> bool:
    if current_user.is_authenticated:
        return False
    if request.headers.get("DNT") == "1" or request.headers.get("Sec-GPC") == "1":
        return False
    agent = (request.headers.get("User-Agent") or "").lower()
    return bool(agent) and not any(word in agent for word in _BOT_WORDS)


def _get_or_create_visitor() -> Visitor:
    key = request.cookies.get(COOKIE_NAME, "")
    visitor = None
    if _KEY_RE.match(key):
        visitor = db.session.scalar(db.select(Visitor).where(Visitor.visitor_key == key))
    if visitor is None:
        key = secrets.token_hex(16)
        visitor = Visitor(visitor_key=key)
        db.session.add(visitor)
        db.session.flush()
    visitor.last_seen = utcnow()
    g.visitor_cookie = key  # app.py sets the cookie after the response is built
    return visitor


def _referrer_host() -> str | None:
    referrer = request.headers.get("Referer", "")
    host = urlparse(referrer).netloc.lower()[:255]
    if not host or host == request.host.lower():
        return None
    return host


def track_page(path: str, project=None) -> None:
    """Record a page view (and a project view). Never raises."""
    try:
        if not should_track():
            return
        visitor = _get_or_create_visitor()
        db.session.add(
            PageEvent(visitor_id=visitor.id, path=path[:300], referrer_host=_referrer_host())
        )
        if project is not None:
            recent = db.session.scalar(
                db.select(ProjectView.id).where(
                    ProjectView.project_id == project.id,
                    ProjectView.visitor_id == visitor.id,
                    ProjectView.created_at > utcnow() - PROJECT_VIEW_WINDOW,
                )
            )
            if recent is None:
                db.session.add(ProjectView(project_id=project.id, visitor_id=visitor.id))
        db.session.commit()
    except Exception:  # noqa: BLE001 - analytics must never break a page
        db.session.rollback()
        current_app.logger.exception("Could not record page view")


def track_contact_click(channel: str, path: str) -> bool:
    """Record a click on a contact button. Returns True if stored."""
    if channel not in CONTACT_CHANNELS:
        return False
    try:
        if not should_track():
            return False
        visitor = _get_or_create_visitor()
        db.session.add(ContactEvent(visitor_id=visitor.id, channel=channel, source_path=path[:300]))
        db.session.commit()
        return True
    except Exception:  # noqa: BLE001
        db.session.rollback()
        current_app.logger.exception("Could not record contact click")
        return False
