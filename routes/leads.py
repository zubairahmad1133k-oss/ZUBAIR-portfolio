"""Admin enquiry (lead) manager."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from extensions import db, login_manager
from models import Lead, Notification
from models.lead import LEAD_STATUSES

bp = Blueprint("admin_leads", __name__, url_prefix="/admin/enquiries")

STATUS_LABELS = {"new": "New", "contacted": "Contacted", "in_progress": "In progress", "completed": "Completed"}


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@bp.get("/")
def index():
    query = request.args.get("q", "").strip()[:100]
    status = request.args.get("status", "")
    statement = db.select(Lead).order_by(Lead.created_at.desc()).limit(200)
    if status in LEAD_STATUSES:
        statement = statement.where(Lead.status == status)
    if query:
        like = f"%{_escape_like(query)}%"
        statement = statement.where(db.or_(
            Lead.name.ilike(like, escape="\\"),
            Lead.email.ilike(like, escape="\\"),
            Lead.message.ilike(like, escape="\\"),
        ))
    leads = db.session.scalars(statement).all()
    counts = dict(db.session.execute(
        db.select(Lead.status, db.func.count(Lead.id)).group_by(Lead.status)
    ).all())
    return render_template(
        "admin/leads_list.html", leads=leads, q=query, status=status,
        counts=counts, total=sum(counts.values()), statuses=STATUS_LABELS,
    )


@bp.get("/<int:lead_id>")
def detail(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    # Opening the enquiry clears its notification.
    db.session.execute(
        db.update(Notification)
        .where(Notification.link == url_for("admin_leads.detail", lead_id=lead.id),
               Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.session.commit()
    return render_template("admin/lead_detail.html", lead=lead, statuses=STATUS_LABELS)


@bp.post("/<int:lead_id>")
def update(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    status = request.form.get("status", "")
    notes = request.form.get("private_notes", "").replace("\r\n", "\n").strip()
    if status not in LEAD_STATUSES:
        flash("Please choose a valid status.", "error")
    elif len(notes) > 5000:
        flash("Notes are too long (5000 characters max).", "error")
    else:
        lead.status = status
        lead.private_notes = notes
        db.session.commit()
        flash("Enquiry updated.", "success")
    return redirect(url_for("admin_leads.detail", lead_id=lead.id))


@bp.post("/<int:lead_id>/delete")
def delete(lead_id):
    lead = db.get_or_404(Lead, lead_id)
    db.session.execute(
        db.delete(Notification).where(Notification.link == url_for("admin_leads.detail", lead_id=lead.id))
    )
    db.session.delete(lead)
    db.session.commit()
    flash("Enquiry deleted.", "info")
    return redirect(url_for("admin_leads.index"))
