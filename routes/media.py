"""Admin media library: images, screenshots and private PDF documents."""
from flask import (
    Blueprint, abort, flash, redirect, render_template, request, send_from_directory, url_for,
)
from flask_login import current_user
from werkzeug.utils import secure_filename

from extensions import db, login_manager
from models import Project, ProjectMedia
from models.notification import KIND_MEDIA_UPLOADED, add_notification
from models.project import MEDIA_KINDS
from uploads import delete_media_file, private_folder, save_media_file

bp = Blueprint("admin_media", __name__, url_prefix="/admin/media")
MAX_FILES_PER_UPLOAD = 10


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()


def _projects():
    return db.session.scalars(db.select(Project).order_by(Project.sort_order, Project.id)).all()


def _project_id(raw: str):
    if raw and raw.isdigit() and db.session.get(Project, int(raw)) is not None:
        return int(raw)
    return None


def _folder(raw: str) -> str:
    return (raw or "").strip()[:80] or "General"


@bp.get("/")
def index():
    folder = request.args.get("folder", "")
    kind = request.args.get("kind", "")
    statement = db.select(ProjectMedia).order_by(ProjectMedia.created_at.desc(), ProjectMedia.id.desc())
    if folder:
        statement = statement.where(ProjectMedia.folder == folder)
    if kind in MEDIA_KINDS:
        statement = statement.where(ProjectMedia.kind == kind)
    items = db.session.scalars(statement).all()
    folders = db.session.scalars(db.select(ProjectMedia.folder).distinct().order_by(ProjectMedia.folder)).all()
    return render_template(
        "admin/media.html", items=items, folders=folders, folder=folder, kind=kind,
        projects=_projects(), kinds=MEDIA_KINDS,
    )


@bp.post("/upload")
def upload():
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        flash("Choose at least one file to upload.", "error")
        return redirect(url_for("admin_media.index"))
    image_kind = request.form.get("kind", "screenshot")
    if image_kind not in ("image", "screenshot"):
        image_kind = "screenshot"
    folder = _folder(request.form.get("folder", ""))
    project_id = _project_id(request.form.get("project_id", ""))
    caption = request.form.get("caption", "").strip()[:255] or None

    saved = 0
    for storage in files[:MAX_FILES_PER_UPLOAD]:
        try:
            info = save_media_file(storage)
        except ValueError as exc:
            flash(f"{storage.filename}: {exc}", "error")
            continue
        is_pdf = info["type"] == "pdf"
        label = (secure_filename(storage.filename) or "file")[:255]
        db.session.add(ProjectMedia(
            project_id=project_id, filename=info["filename"], original_name=label,
            display_name=label, kind="document" if is_pdf else image_kind,
            mime_type=info["mime"], size_bytes=info["size"], folder=folder,
            is_public=not is_pdf, caption=caption,
        ))
        saved += 1
    if saved:
        add_notification(KIND_MEDIA_UPLOADED, f"{saved} file(s) uploaded to the media library")
        db.session.commit()
        flash(f"{saved} file(s) uploaded.", "success")
    if len(files) > MAX_FILES_PER_UPLOAD:
        flash(f"Only the first {MAX_FILES_PER_UPLOAD} files were processed.", "info")
    return redirect(url_for("admin_media.index"))


@bp.post("/<int:media_id>/edit")
def edit(media_id):
    item = db.get_or_404(ProjectMedia, media_id)
    name = request.form.get("display_name", "").strip()[:255]
    if not name:
        flash("The name cannot be empty.", "error")
        return redirect(url_for("admin_media.index"))
    if item.kind == "document" and not name.lower().endswith(".pdf"):
        name += ".pdf"
    item.display_name = name
    item.caption = request.form.get("caption", "").strip()[:255] or None
    item.folder = _folder(request.form.get("folder", ""))
    item.project_id = _project_id(request.form.get("project_id", ""))
    if item.kind != "document" and request.form.get("kind") in ("image", "screenshot"):
        item.kind = request.form["kind"]
    db.session.commit()
    flash("File details saved.", "success")
    return redirect(url_for("admin_media.index"))


@bp.post("/<int:media_id>/delete")
def delete(media_id):
    item = db.get_or_404(ProjectMedia, media_id)
    filename, private = item.filename, item.kind == "document"
    db.session.delete(item)
    db.session.commit()
    delete_media_file(filename, private)
    flash("File deleted.", "info")
    return redirect(url_for("admin_media.index"))


@bp.get("/<int:media_id>/file")
def file(media_id):
    """Private documents are only ever served here, to a logged-in admin."""
    item = db.get_or_404(ProjectMedia, media_id)
    if item.kind != "document":
        abort(404)
    return send_from_directory(
        private_folder(), item.filename, mimetype="application/pdf",
        as_attachment=request.args.get("download") == "1", download_name=item.display_name,
    )
