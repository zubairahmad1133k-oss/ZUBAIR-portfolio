"""Admin analytics page."""
from flask import Blueprint, render_template, request
from flask_login import current_user

from extensions import login_manager
from services import reports

bp = Blueprint("analytics", __name__, url_prefix="/admin/analytics")


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()


@bp.get("/")
def index():
    rng = reports.resolve_range(request.args)
    report = reports.build_report(rng)
    chart = dict(report["series"])
    chart["engagement"] = [
        {"title": row["title"], "views": row["views"]} for row in report["engagement"]
    ]
    return render_template("admin/analytics.html", report=report, rng=rng, chart=chart)
