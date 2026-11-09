"""Admin: curated code excerpts shown on a project's public page.

Visitors see exactly the text saved here and nothing else. No file paths,
repositories or downloads are exposed, so the full project stays private.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from extensions import db, login_manager
from models import CodeSnippet, Project
from models.project import SNIPPET_LANGUAGES

bp = Blueprint("admin_snippets", __name__, url_prefix="/admin/projects/<int:project_id>/code")

MAX_CODE_CHARS = 12000
MAX_CODE_LINES = 300


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()


def _read_form():
    form = request.form
    values = {
        "title": form.get("title", "").strip(),
        "language": form.get("language", "text"),
        "description": form.get("description", "").strip(),
        "code": form.get("code", "").replace("\r\n", "\n").strip("\n").rstrip(),
    }
    errors = []
    if not values["title"]:
        errors.append("Title is required.")
    elif len(values["title"]) > 120:
        errors.append("Title is too long (120 characters max).")
    if values["language"] not in SNIPPET_LANGUAGES:
        values["language"] = "text"
    if len(values["description"]) > 300:
        errors.append("Description is too long (300 characters max).")
    if not values["code"]:
        errors.append("Paste the code excerpt you want to show.")
    elif len(values["code"]) > MAX_CODE_CHARS or values["code"].count("\n") + 1 > MAX_CODE_LINES:
        errors.append(f"Keep excerpts short: up to {MAX_CODE_LINES} lines / {MAX_CODE_CHARS} characters.")
    return values, errors


def _page(project, values, editing=None, status=200):
    return (
        render_template(
            "admin/snippets.html", project=project, snippets=project.snippets,
            values=values, editing=editing, languages=SNIPPET_LANGUAGES,
        ),
        status,
    )


def _blank():
    return {"title": "", "language": "python", "description": "", "code": ""}


@bp.route("/", methods=["GET", "POST"])
def index(project_id):
    project = db.get_or_404(Project, project_id)
    if request.method == "GET":
        return _page(project, _blank())
    values, errors = _read_form()
    if errors:
        for message in errors:
            flash(message, "error")
        return _page(project, values, status=400)
    last = db.session.scalar(
        db.select(db.func.max(CodeSnippet.sort_order)).where(CodeSnippet.project_id == project.id)
    ) or 0
    db.session.add(CodeSnippet(project_id=project.id, sort_order=last + 1, **values))
    db.session.commit()
    flash("Code excerpt added. It is now visible on the project page if the project is published.", "success")
    return redirect(url_for("admin_snippets.index", project_id=project.id))


@bp.route("/<int:snippet_id>/edit", methods=["GET", "POST"])
def edit(project_id, snippet_id):
    project = db.get_or_404(Project, project_id)
    snippet = db.get_or_404(CodeSnippet, snippet_id)
    if snippet.project_id != project.id:
        abort(404)
    if request.method == "GET":
        values = {"title": snippet.title, "language": snippet.language,
                  "description": snippet.description, "code": snippet.code}
        return _page(project, values, editing=snippet)
    values, errors = _read_form()
    if errors:
        for message in errors:
            flash(message, "error")
        return _page(project, values, editing=snippet, status=400)
    for key, value in values.items():
        setattr(snippet, key, value)
    db.session.commit()
    flash("Code excerpt saved.", "success")
    return redirect(url_for("admin_snippets.index", project_id=project.id))


@bp.post("/<int:snippet_id>/delete")
def delete(project_id, snippet_id):
    snippet = db.get_or_404(CodeSnippet, snippet_id)
    if snippet.project_id != project_id:
        abort(404)
    db.session.delete(snippet)
    db.session.commit()
    flash("Code excerpt removed.", "info")
    return redirect(url_for("admin_snippets.index", project_id=project_id))
