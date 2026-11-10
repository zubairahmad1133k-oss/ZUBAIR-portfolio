from urllib.parse import urlparse

from extensions import db
from models.base import utcnow

# Gradient styles that already exist in the original portfolio CSS.
VISUAL_STYLES = {
    "visual-code": "Violet to teal (code)",
    "visual-news": "Plum to navy (media)",
    "visual-academy": "Green to indigo (education)",
    "visual-extra": "Amber to violet (future)",
}

MEDIA_KINDS = ("image", "screenshot", "document")


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    summary = db.Column(db.Text, nullable=False, default="")       # shown on the card
    description = db.Column(db.Text, nullable=False, default="")   # shown on the detail page
    category = db.Column(db.String(160), nullable=False, default="")  # e.g. "AI · Education · Development"
    technologies = db.Column(db.Text, nullable=False, default="")  # comma-separated
    visual_class = db.Column(db.String(32), nullable=False, default="visual-code")
    icon = db.Column(db.String(16), nullable=False, default="✦")
    card_label = db.Column(db.String(40))      # optional override of "PROJECT 01"
    link_text = db.Column(db.String(120))      # small line at the bottom of the card
    demo_url = db.Column(db.String(500))
    github_url = db.Column(db.String(500))
    docs_url = db.Column(db.String(500))
    thumbnail = db.Column(db.String(255))      # filename inside uploads/public
    is_published = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_placeholder = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    media = db.relationship(
        "ProjectMedia", back_populates="project", order_by="ProjectMedia.sort_order"
    )
    views = db.relationship(
        "ProjectView", back_populates="project",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    snippets = db.relationship(
        "CodeSnippet", back_populates="project", order_by="CodeSnippet.sort_order",
        cascade="all, delete-orphan", passive_deletes=True,
    )

    # ---- helpers -------------------------------------------------------
    @classmethod
    def published_query(cls):
        return db.select(cls).where(cls.is_published.is_(True)).order_by(cls.sort_order, cls.id)

    @property
    def thumbnail_is_external(self) -> bool:
        """True when the thumbnail is a link to an image hosted elsewhere."""
        return bool(self.thumbnail) and self.thumbnail.startswith(("http://", "https://"))

    @property
    def demo_host(self) -> str:
        """'https://www.example.com/app' -> 'example.com' (for the Visit button)."""
        host = urlparse(self.demo_url or "").netloc.lower()
        return host[4:] if host.startswith("www.") else host

    @property
    def tech_list(self) -> list[str]:
        return [t.strip() for t in (self.technologies or "").split(",") if t.strip()]

    @tech_list.setter
    def tech_list(self, items) -> None:
        self.technologies = ", ".join(t.strip() for t in items if t and t.strip())

    @property
    def description_paragraphs(self) -> list[str]:
        text = (self.description or "").replace("\r\n", "\n")
        return [p.strip() for p in text.split("\n\n") if p.strip()]

    @property
    def gallery(self):
        """Public images attached to this project (screenshots first-class)."""
        return [m for m in self.media if m.is_public and m.kind in ("screenshot", "image")]

    @property
    def documents(self):
        return [m for m in self.media if m.kind == "document"]

    def __repr__(self) -> str:
        return f"<Project {self.slug}>"


class ProjectMedia(db.Model):
    """A file in the media library; optionally attached to a project."""

    __tablename__ = "project_media"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    filename = db.Column(db.String(255), unique=True, nullable=False)  # stored name (random)
    original_name = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(255), nullable=False)           # editable label
    kind = db.Column(db.String(20), nullable=False, default="image")   # image/screenshot/document
    mime_type = db.Column(db.String(100), nullable=False, default="application/octet-stream")
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    folder = db.Column(db.String(80), nullable=False, default="General")
    is_public = db.Column(db.Boolean, nullable=False, default=False)
    caption = db.Column(db.String(255))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    project = db.relationship("Project", back_populates="media")

    @property
    def is_image(self) -> bool:
        return self.kind in ("image", "screenshot")


SNIPPET_LANGUAGES = {
    "python": "Python", "javascript": "JavaScript", "html": "HTML", "css": "CSS",
    "cpp": "C++", "c": "C", "java": "Java", "sql": "SQL", "bash": "Shell",
    "json": "JSON", "text": "Plain text",
}


class CodeSnippet(db.Model):
    """A short, hand-picked code excerpt you choose to show publicly.

    Visitors only ever see what is stored here. Nothing links to your real
    source files, so the rest of the project stays private.
    """

    __tablename__ = "code_snippets"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = db.Column(db.String(120), nullable=False)
    language = db.Column(db.String(30), nullable=False, default="text")
    description = db.Column(db.String(300), nullable=False, default="")
    code = db.Column(db.Text, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    project = db.relationship("Project", back_populates="snippets")

    @property
    def language_label(self) -> str:
        return SNIPPET_LANGUAGES.get(self.language, "Plain text")
