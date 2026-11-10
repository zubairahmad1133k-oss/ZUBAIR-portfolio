"""Admin project manager: add, edit, delete, publish, reorder, preview."""
from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user

from extensions import db, login_manager
from models import Project
from models.notification import (
    KIND_PROJECT_PUBLISHED, KIND_PROJECT_UPDATED, add_notification,
)
from models.project import VISUAL_STYLES
from services.seeding import seed_starter_projects
from uploads import delete_public_file, save_public_image
from utils import clean_http_url, unique_slug

bp = Blueprint("admin_projects", __name__, url_prefix="/admin/projects")

TEXT_LIMITS = {
    "title": (120, "Title"),
    "category": (160, "Category"),
    "summary": (600, "Short description"),
    "description": (6000, "Full description"),
    "technologies": (300, "Technologies"),
    "icon": (16, "Icon"),
    "card_label": (40, "Card label"),
    "link_text": (120, "Card link text"),
}
URL_FIELDS = {"demo_url": "Demo URL", "github_url": "GitHub URL", "docs_url": "Documentation URL"}


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()


def _all_projects():
    return db.session.scalars(db.select(Project).order_by(Project.sort_order, Project.id)).all()


def _values_from_project(project: Project) -> dict:
    return {
        "title": project.title, "category": project.category, "summary": project.summary,
        "description": project.description, "technologies": project.technologies,
        "visual_class": project.visual_class, "icon": project.icon,
        "card_label": project.card_label or "", "link_text": project.link_text or "",
        "demo_url": project.demo_url or "", "github_url": project.github_url or "",
        "docs_url": project.docs_url or "",
        "thumbnail_url": project.thumbnail if project.thumbnail_is_external else "",
        "is_published": project.is_published, "is_placeholder": project.is_placeholder,
    }


def _default_values() -> dict:
    return {
        "title": "", "category": "", "summary": "", "description": "", "technologies": "",
        "visual_class": "visual-code", "icon": "✦", "card_label": "", "link_text": "",
        "demo_url": "", "github_url": "", "docs_url": "", "thumbnail_url": "",
        "is_published": False, "is_placeholder": False,
    }


def _read_form():
    """Return (cleaned_values, errors) from the submitted form."""
    form = request.form
    errors: list[str] = []
    values = _default_values()

    for field, (limit, label) in TEXT_LIMITS.items():
        raw = form.get(field, "").replace("\r\n", "\n").strip()
        if len(raw) > limit:
            errors.append(f"{label} is too long (max {limit} characters).")
        values[field] = raw

    values["technologies"] = ", ".join(
        t.strip() for t in values["technologies"].split(",") if t.strip()
    )
    values["icon"] = values["icon"] or "✦"
    visual = form.get("visual_class", "visual-code")
    values["visual_class"] = visual if visual in VISUAL_STYLES else "visual-code"

    for field, label in URL_FIELDS.items():
        try:
            values[field] = clean_http_url(form.get(field, "")) or ""
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            values[field] = form.get(field, "")

    image_url = form.get("thumbnail_url", "").strip()
    values["thumbnail_url"] = image_url
    if image_url:
        try:
            clean_http_url(image_url)
            if len(image_url) > 255:
                raise ValueError("The link is too long (255 characters max).")
        except ValueError as exc:
            errors.append(f"Thumbnail image link: {exc}")

    values["is_published"] = form.get("is_published") == "on"
    values["is_placeholder"] = form.get("is_placeholder") == "on"

    if not values["title"]:
        errors.append("Title is required.")
    if not values["summary"]:
        errors.append("Short description is required.")
    if not values["description"]:
        values["description"] = values["summary"]
    return values, errors


def _db_values(values: dict) -> dict:
    """Empty optional strings become NULL in the database."""
    cleaned = dict(values)
    cleaned.pop("thumbnail_url", None)  # not a database column; handled separately
    for key in ("card_label", "link_text", "demo_url", "github_url", "docs_url"):
        cleaned[key] = cleaned[key] or None
    return cleaned


def _render_form(project, values, status=200):
    return (
        render_template(
            "admin/project_form.html", project=project, values=values,
            visual_styles=VISUAL_STYLES,
        ),
        status,
    )


@bp.get("/")
def index():
    return render_template("admin/projects_list.html", projects=_all_projects())


@bp.post("/seed")
def seed():
    """One-click starter projects (for hosts without a terminal)."""
    added = seed_starter_projects()
    if added:
        flash(f"Added {added} starter project(s).", "success")
    else:
        flash("The starter projects are already there.", "info")
    return redirect(url_for("admin_projects.index"))


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "GET":
        return _render_form(None, _default_values())

    values, errors = _read_form()
    thumbnail = None
    upload = request.files.get("thumbnail")
    if not errors and upload and upload.filename:
        try:
            thumbnail = save_public_image(upload)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        for message in errors:
            flash(message, "error")
        return _render_form(None, values, 400)

    last_order = db.session.scalar(db.select(db.func.max(Project.sort_order))) or 0
    project = Project(
        slug=unique_slug(db.session, Project, values["title"]),
        sort_order=last_order + 1, thumbnail=thumbnail or values["thumbnail_url"] or None,
        **_db_values(values),
    )
    db.session.add(project)
    if project.is_published:
        add_notification(KIND_PROJECT_PUBLISHED, f"Project published: {project.title}")
    db.session.commit()
    flash(f"'{project.title}' created.", "success")
    return redirect(url_for("admin_projects.index"))


@bp.route("/<int:project_id>/edit", methods=["GET", "POST"])
def edit(project_id):
    project = db.get_or_404(Project, project_id)
    if request.method == "GET":
        return _render_form(project, _values_from_project(project))

    values, errors = _read_form()
    new_thumbnail = None
    upload = request.files.get("thumbnail")
    if not errors and upload and upload.filename:
        try:
            new_thumbnail = save_public_image(upload)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        for message in errors:
            flash(message, "error")
        return _render_form(project, values, 400)

    was_published = project.is_published
    old_thumbnail = project.thumbnail
    for key, value in _db_values(values).items():
        setattr(project, key, value)

    remove_requested = request.form.get("remove_thumbnail") == "on"
    link = values["thumbnail_url"]
    if new_thumbnail:
        project.thumbnail = new_thumbnail
    elif remove_requested:
        project.thumbnail = None
    elif link:
        project.thumbnail = link
    elif old_thumbnail and old_thumbnail.startswith(("http://", "https://")):
        project.thumbnail = None  # the link box was emptied

    if project.is_published and not was_published:
        add_notification(KIND_PROJECT_PUBLISHED, f"Project published: {project.title}")
    else:
        add_notification(KIND_PROJECT_UPDATED, f"Project updated: {project.title}")
    db.session.commit()

    if (old_thumbnail and old_thumbnail != project.thumbnail
            and not old_thumbnail.startswith(("http://", "https://"))):
        delete_public_file(old_thumbnail)
    flash(f"'{project.title}' saved.", "success")
    return redirect(url_for("admin_projects.index"))


@bp.post("/<int:project_id>/toggle-publish")
def toggle_publish(project_id):
    project = db.get_or_404(Project, project_id)
    project.is_published = not project.is_published
    if project.is_published:
        add_notification(KIND_PROJECT_PUBLISHED, f"Project published: {project.title}")
        flash(f"'{project.title}' is now live on your portfolio.", "success")
    else:
        add_notification(KIND_PROJECT_UPDATED, f"Project unpublished: {project.title}")
        flash(f"'{project.title}' is now hidden (draft).", "info")
    db.session.commit()
    return redirect(url_for("admin_projects.index"))


@bp.post("/<int:project_id>/move/<direction>")
def move(project_id, direction):
    if direction not in ("up", "down"):
        abort(404)
    projects = _all_projects()
    ids = [p.id for p in projects]
    if project_id not in ids:
        abort(404)
    i = ids.index(project_id)
    j = i - 1 if direction == "up" else i + 1
    if 0 <= j < len(projects):
        projects[i], projects[j] = projects[j], projects[i]
    for position, item in enumerate(projects, start=1):
        item.sort_order = position
    db.session.commit()
    return redirect(url_for("admin_projects.index"))


@bp.post("/<int:project_id>/delete")
def delete(project_id):
    project = db.get_or_404(Project, project_id)
    title, thumbnail = project.title, project.thumbnail
    db.session.delete(project)
    db.session.commit()
    if thumbnail and not thumbnail.startswith(("http://", "https://")):
        delete_public_file(thumbnail)
    flash(f"'{title}' deleted.", "info")
    return redirect(url_for("admin_projects.index"))


@bp.get("/<int:project_id>/preview")
def preview(project_id):
    """Shows the public detail page, even for unpublished projects (admins only)."""
    project = db.get_or_404(Project, project_id)
    return render_template("projects/detail.html", project=project, preview=True)
