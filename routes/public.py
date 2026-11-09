"""Public portfolio pages, SEO files, media serving and health check."""
from pathlib import Path
from xml.sax.saxutils import escape

from flask import (
    Blueprint, Response, abort, current_app, flash, jsonify, redirect,
    render_template, request, send_from_directory, url_for,
)
from sqlalchemy import text

from extensions import db, limiter
from models import Lead, Project
from models.lead import PROJECT_TYPES
from models.notification import KIND_NEW_LEAD, add_notification
from services.tracking import track_page
from utils import is_valid_email

bp = Blueprint("public", __name__)


def _render_home(status: int = 200, **extra):
    projects = db.session.scalars(Project.published_query()).all()
    html = render_template(
        "portfolio.html", projects=projects, project_types=PROJECT_TYPES, **extra
    )
    return html, status


@bp.get("/")
def home():
    track_page("/")
    return _render_home()


@bp.get("/projects/<slug>")
def project_detail(slug):
    project = db.session.scalar(
        db.select(Project).where(
            Project.slug == slug,
            Project.is_published.is_(True),
            Project.is_placeholder.is_(False),
        )
    )
    if project is None:
        abort(404)
    track_page(f"/projects/{project.slug}", project=project)
    return render_template("projects/detail.html", project=project)


ENQUIRY_THANKS = "Thank you! Your enquiry was sent. I will reply to your email address soon."


@bp.post("/enquiry")
@limiter.limit("5 per hour;20 per day")
def enquiry():
    """Public enquiry form. A saved enquiry is a CONFIRMED lead (unlike a button click)."""
    form = request.form
    values = {
        "name": form.get("name", "").strip(),
        "email": form.get("email", "").strip().lower(),
        "project_type": form.get("project_type", "").strip(),
        "message": form.get("message", "").replace("\r\n", "\n").strip(),
    }
    # Hidden "website" field: humans leave it empty, simple bots fill it in.
    if form.get("website", "").strip():
        flash(ENQUIRY_THANKS, "enquiry")
        return redirect(url_for("public.home") + "#enquiry")

    errors = []
    if not 2 <= len(values["name"]) <= 120:
        errors.append("Please enter your name (2–120 characters).")
    if not is_valid_email(values["email"]):
        errors.append("Please enter a valid email address.")
    if values["project_type"] not in PROJECT_TYPES:
        errors.append("Please choose a project type.")
    if not 10 <= len(values["message"]) <= 3000:
        errors.append("Please write a message of 10–3000 characters.")
    if errors:
        return _render_home(400, enquiry=values, enquiry_errors=errors)

    lead = Lead(**values)
    db.session.add(lead)
    db.session.flush()  # gives the lead its id for the notification link
    add_notification(
        KIND_NEW_LEAD, f"New enquiry from {lead.name} ({lead.project_type})",
        url_for("admin_leads.detail", lead_id=lead.id),
    )
    db.session.commit()
    flash(ENQUIRY_THANKS, "enquiry")
    return redirect(url_for("public.home") + "#enquiry")


@bp.get("/media/<path:filename>")
def media(filename):
    """Serve PUBLIC images only. Private documents never live in this folder."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in current_app.config["PUBLIC_MEDIA_EXTENSIONS"]:
        abort(404)
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / "public"
    return send_from_directory(folder, filename, max_age=3600)


@bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - report any database failure as unhealthy
        current_app.logger.exception("Health check: database unreachable")
        return jsonify(status="error", database="unreachable"), 503
    return jsonify(status="ok", database="ok")


def _site_root() -> str:
    return current_app.config["SITE_URL"] or request.url_root.rstrip("/")


@bp.get("/robots.txt")
def robots():
    body = (
        "User-agent: *\n"
        "Disallow: /admin\n"
        "Disallow: /api/\n"
        f"Sitemap: {_site_root()}/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap():
    root = _site_root()
    urls = [f"  <url><loc>{escape(root)}/</loc></url>"]
    for project in db.session.scalars(Project.published_query()):
        if project.is_placeholder:
            continue
        loc = escape(root + url_for("public.project_detail", slug=project.slug))
        lastmod = project.updated_at.date().isoformat()
        urls.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    return Response(xml, mimetype="application/xml")
