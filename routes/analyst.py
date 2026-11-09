"""Admin AI Analyst page (rule-based by default, AI optional)."""
from flask import Blueprint, current_app, render_template, request
from flask_login import current_user

from extensions import limiter, login_manager
from services import analyst, reports

bp = Blueprint("admin_analyst", __name__, url_prefix="/admin/analyst")


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()


@bp.route("/", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def index():
    source = request.form if request.method == "POST" else request.args
    rng = reports.resolve_range(source)
    analysis = analyst.analyse(rng)
    key = current_app.config.get("ANTHROPIC_API_KEY")
    narrative = ai_error = None
    if request.method == "POST" and request.form.get("ai") == "1":
        if not key:
            ai_error = "No AI key is configured, so the rule-based analysis is shown."
        else:
            try:
                narrative = analyst.ai_explain(analysis, rng["label"], key, current_app.config["ANTHROPIC_MODEL"])
            except analyst.AnalystError as exc:
                ai_error = f"{exc} The rule-based analysis is still shown below."
    return render_template(
        "admin/analyst.html", rng=rng, analysis=analysis, ai_enabled=bool(key),
        narrative=narrative, ai_error=ai_error,
    )
