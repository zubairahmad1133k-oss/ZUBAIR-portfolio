"""Analytics tables. Privacy notes:

* No IP addresses, no user-agent strings and no fingerprints are stored.
* A visitor is just a random ID kept in a first-party cookie.
* Referrers are reduced to the host name only.
"""
from extensions import db
from models.base import utcnow

EVENT_PAGE_VIEW = "page_view"
CHANNEL_WHATSAPP = "whatsapp"
CHANNEL_EMAIL = "email"


class Visitor(db.Model):
    __tablename__ = "visitors"

    id = db.Column(db.Integer, primary_key=True)
    visitor_key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    first_seen = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_seen = db.Column(db.DateTime, nullable=False, default=utcnow)


class PageEvent(db.Model):
    __tablename__ = "page_events"

    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.Integer, db.ForeignKey("visitors.id", ondelete="SET NULL"), index=True)
    event_type = db.Column(db.String(32), nullable=False, default=EVENT_PAGE_VIEW, index=True)
    path = db.Column(db.String(300), nullable=False, default="/")
    referrer_host = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)


class ProjectView(db.Model):
    __tablename__ = "project_views"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visitor_id = db.Column(db.Integer, db.ForeignKey("visitors.id", ondelete="SET NULL"), index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    project = db.relationship("Project", back_populates="views")


class ContactEvent(db.Model):
    """A click on a contact button. This is NOT a confirmed enquiry."""

    __tablename__ = "contact_events"

    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.Integer, db.ForeignKey("visitors.id", ondelete="SET NULL"), index=True)
    channel = db.Column(db.String(20), nullable=False, index=True)  # whatsapp / email
    source_path = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
