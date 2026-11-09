"""Dashboard overview, notifications and account settings."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user

from extensions import db, login_manager
from models import AdminUser, Goal, Lead, Notification, Project
from services import reports
from utils import is_valid_email, password_problem

bp = Blueprint("dashboard", __name__, url_prefix="/admin")


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()


def _count(query) -> int:
    return db.session.scalar(query) or 0


@bp.get("/")
def overview():
    total = _count(db.select(db.func.count(Project.id)))
    published = _count(db.select(db.func.count(Project.id)).where(Project.is_published.is_(True)))
    unread = _count(db.select(db.func.count(Notification.id)).where(Notification.is_read.is_(False)))
    new_leads = _count(db.select(db.func.count(Lead.id)).where(Lead.status == "new"))
    notifications = db.session.scalars(
        db.select(Notification).where(Notification.is_read.is_(False))
        .order_by(Notification.created_at.desc(), Notification.id.desc()).limit(10)
    ).all()
    rng = reports.resolve_range({"range": "7d"})
    active_goals = _count(db.select(db.func.count(Goal.id)).where(Goal.is_completed.is_(False)))
    done_goals = _count(db.select(db.func.count(Goal.id)).where(Goal.is_completed.is_(True)))
    return render_template(
        "admin/dashboard.html", total=total, published=published, drafts=total - published,
        unread=unread, new_leads=new_leads, notifications=notifications,
        visitors_7d=reports.unique_visitors(rng["start"], rng["end"]),
        activity=reports.recent_activity(10),
        active_goals=active_goals, done_goals=done_goals,
    )


@bp.post("/notifications/read")
def mark_notifications_read():
    db.session.execute(
        db.update(Notification).where(Notification.is_read.is_(False)).values(is_read=True)
    )
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("dashboard.overview"))


@bp.get("/account")
def account():
    return render_template("admin/account.html")


@bp.post("/account/profile")
def update_profile():
    email = request.form.get("email", "").strip().lower()
    if not is_valid_email(email):
        flash("That email address does not look valid.", "error")
        return redirect(url_for("dashboard.account"))
    taken = db.session.scalar(
        db.select(AdminUser.id).where(AdminUser.email == email, AdminUser.id != current_user.id)
    )
    if taken is not None:
        flash("That email is already used by another admin.", "error")
        return redirect(url_for("dashboard.account"))
    current_user.email = email
    db.session.commit()
    flash("Profile updated.", "success")
    return redirect(url_for("dashboard.account"))


@bp.post("/account/password")
def change_password():
    user = current_user._get_current_object()
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    if not user.check_password(current):
        flash("Your current password is not correct.", "error")
    elif new != confirm:
        flash("The two new passwords do not match.", "error")
    elif (problem := password_problem(new)) is not None:
        flash(problem, "error")
    else:
        user.set_password(new)  # also signs out every other session
        db.session.commit()
        login_user(user)        # keep THIS session alive with the new version
        flash("Password changed. Other devices have been signed out.", "success")
    return redirect(url_for("dashboard.account"))
