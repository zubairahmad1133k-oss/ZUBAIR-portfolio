from extensions import db
from models.base import utcnow

# Kinds of events shown in the dashboard activity feed.
KIND_NEW_LEAD = "new_lead"
KIND_PROJECT_PUBLISHED = "project_published"
KIND_PROJECT_UPDATED = "project_updated"
KIND_MEDIA_UPLOADED = "media_uploaded"
KIND_CONTACT_CLICK = "contact_click"


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(40), nullable=False, index=True)
    message = db.Column(db.String(300), nullable=False)
    link = db.Column(db.String(300))
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)


def add_notification(kind: str, message: str, link: str | None = None) -> Notification:
    """Queue an activity-feed entry. The caller commits the session."""
    note = Notification(kind=kind, message=message[:300], link=link)
    db.session.add(note)
    return note
