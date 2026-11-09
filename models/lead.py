from extensions import db
from models.base import utcnow

LEAD_STATUSES = ("new", "contacted", "in_progress", "completed")
PROJECT_TYPES = (
    "Website",
    "Web application",
    "AI integration",
    "Prototype / idea",
    "Collaboration",
    "Something else",
)


class Lead(db.Model):
    """A confirmed enquiry submitted through the public form."""

    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    project_type = db.Column(db.String(60), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="new", index=True)
    private_notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
