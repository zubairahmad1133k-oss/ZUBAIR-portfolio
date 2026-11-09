"""Admin goals, progress and achievements. Everything here is entered by you;
nothing is calculated or awarded automatically."""
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from extensions import db, login_manager
from models import Achievement, Goal
from models.base import utcnow

bp = Blueprint("admin_goals", __name__, url_prefix="/admin/goals")


@bp.before_request
def require_login():
    if not current_user.is_authenticated:
        return login_manager.unauthorized()


def _date(raw: str):
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def _back():
    return redirect(url_for("admin_goals.index"))


@bp.get("/")
def index():
    goals = db.session.scalars(db.select(Goal)).all()
    active = sorted((g for g in goals if not g.is_completed),
                    key=lambda g: (g.target_date is None, g.target_date or date.max, g.created_at))
    done = sorted((g for g in goals if g.is_completed),
                  key=lambda g: g.completed_at or g.created_at, reverse=True)
    achievements = db.session.scalars(
        db.select(Achievement).order_by(Achievement.achieved_on.desc(), Achievement.id.desc())
    ).all()
    return render_template("admin/goals.html", active=active, done=done,
                           achievements=achievements, all_goals=goals)


@bp.post("/new")
def new_goal():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    raw_date = request.form.get("target_date", "")
    target = _date(raw_date)
    if not title or len(title) > 160:
        flash("Please enter a goal title (160 characters max).", "error")
    elif len(description) > 2000:
        flash("The description is too long (2000 characters max).", "error")
    elif raw_date and target is None:
        flash("That target date is not valid.", "error")
    else:
        db.session.add(Goal(title=title, description=description, target_date=target))
        db.session.commit()
        flash("Goal created.", "success")
    return _back()


@bp.post("/<int:goal_id>/progress")
def progress(goal_id):
    goal = db.get_or_404(Goal, goal_id)
    try:
        value = int(request.form.get("progress", ""))
    except ValueError:
        value = -1
    if not 0 <= value <= 100:
        flash("Progress must be a whole number from 0 to 100.", "error")
    else:
        goal.progress = value
        db.session.commit()
        flash("Progress updated.", "success")
    return _back()


@bp.post("/<int:goal_id>/complete")
def complete(goal_id):
    goal = db.get_or_404(Goal, goal_id)
    goal.is_completed, goal.progress, goal.completed_at = True, 100, utcnow()
    db.session.commit()
    flash("Goal marked as completed.", "success")
    return _back()


@bp.post("/<int:goal_id>/reopen")
def reopen(goal_id):
    goal = db.get_or_404(Goal, goal_id)
    goal.is_completed, goal.completed_at = False, None
    db.session.commit()
    flash("Goal reopened.", "info")
    return _back()


@bp.post("/<int:goal_id>/delete")
def delete_goal(goal_id):
    goal = db.get_or_404(Goal, goal_id)
    db.session.delete(goal)
    db.session.commit()
    flash("Goal deleted.", "info")
    return _back()


@bp.post("/achievements/new")
def new_achievement():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    when = _date(request.form.get("achieved_on", "")) or utcnow().date()
    raw_goal = request.form.get("goal_id", "")
    goal_id = int(raw_goal) if raw_goal.isdigit() and db.session.get(Goal, int(raw_goal)) else None
    if not title or len(title) > 160:
        flash("Please enter an achievement title (160 characters max).", "error")
    elif len(description) > 2000:
        flash("The description is too long (2000 characters max).", "error")
    else:
        db.session.add(Achievement(title=title, description=description, achieved_on=when, goal_id=goal_id))
        db.session.commit()
        flash("Achievement added.", "success")
    return _back()


@bp.post("/achievements/<int:achievement_id>/delete")
def delete_achievement(achievement_id):
    item = db.get_or_404(Achievement, achievement_id)
    db.session.delete(item)
    db.session.commit()
    flash("Achievement removed.", "info")
    return _back()
