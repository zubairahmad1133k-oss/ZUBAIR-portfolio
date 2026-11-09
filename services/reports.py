"""Analytics queries. Every number comes from rows in the database; nothing is
estimated, sampled or invented. All times are UTC."""
from datetime import date, datetime, time, timedelta

from extensions import db
from models import ContactEvent, Lead, Notification, PageEvent, Project, ProjectView, Visitor
from models.base import utcnow

PRESETS = {"today": ("Today", 1), "7d": ("Last 7 days", 7), "30d": ("Last 30 days", 30), "90d": ("Last 90 days", 90)}
CHANNEL_LABELS = {"whatsapp": "WhatsApp", "email": "Email"}


# ---------------------------------------------------------------- range
def resolve_range(args) -> dict:
    """Turn ?range=...&from=...&to=... into a validated date range."""
    today = utcnow().date()
    key, note = args.get("range", "7d"), None

    if key == "custom":
        try:
            first = date.fromisoformat(args.get("from", ""))
            last = date.fromisoformat(args.get("to", ""))
            if last < first:
                raise ValueError("end before start")
            if (last - first).days > 365:
                raise ValueError("too long")
            return _range("custom", f"{first:%d %b %Y} – {last:%d %b %Y}", first, last, None)
        except ValueError:
            key, note = "7d", "Those custom dates were not valid (max 1 year), so the last 7 days are shown."

    if key not in PRESETS:
        key = "7d"
    label, days = PRESETS[key]
    return _range(key, label, today - timedelta(days=days - 1), today, note)


def _range(key, label, first: date, last: date, note) -> dict:
    return {
        "key": key, "label": label, "note": note,
        "first": first, "last": last,
        "start": datetime.combine(first, time.min),
        "end": datetime.combine(last + timedelta(days=1), time.min),  # exclusive
        "days": (last - first).days + 1,
    }


# ---------------------------------------------------------------- counts
def _scalar(statement) -> int:
    return db.session.scalar(statement) or 0


def page_views(start, end) -> int:
    return _scalar(db.select(db.func.count(PageEvent.id)).where(
        PageEvent.created_at >= start, PageEvent.created_at < end))


def unique_visitors(start, end) -> int:
    return _scalar(db.select(db.func.count(db.distinct(PageEvent.visitor_id))).where(
        PageEvent.created_at >= start, PageEvent.created_at < end,
        PageEvent.visitor_id.is_not(None)))


def project_views(start, end) -> int:
    return _scalar(db.select(db.func.count(ProjectView.id)).where(
        ProjectView.created_at >= start, ProjectView.created_at < end))


def enquiries(start, end) -> int:
    return _scalar(db.select(db.func.count(Lead.id)).where(
        Lead.created_at >= start, Lead.created_at < end))


def contact_clicks(start, end) -> dict:
    rows = db.session.execute(
        db.select(ContactEvent.channel, db.func.count(ContactEvent.id))
        .where(ContactEvent.created_at >= start, ContactEvent.created_at < end)
        .group_by(ContactEvent.channel)
    ).all()
    counts = {channel: count for channel, count in rows}
    return {
        "whatsapp": counts.get("whatsapp", 0),
        "email": counts.get("email", 0),
        "total": sum(counts.values()),
    }


# ---------------------------------------------------------------- series
def daily_series(rng) -> dict:
    start, end = rng["start"], rng["end"]
    day = db.func.date(PageEvent.created_at)
    traffic = {
        str(d): (views, visitors)
        for d, views, visitors in db.session.execute(
            db.select(day, db.func.count(PageEvent.id), db.func.count(db.distinct(PageEvent.visitor_id)))
            .where(PageEvent.created_at >= start, PageEvent.created_at < end)
            .group_by(day)
        ).all()
    }
    pday = db.func.date(ProjectView.created_at)
    pviews = {
        str(d): count
        for d, count in db.session.execute(
            db.select(pday, db.func.count(ProjectView.id))
            .where(ProjectView.created_at >= start, ProjectView.created_at < end)
            .group_by(pday)
        ).all()
    }
    labels, views, visitors, projects = [], [], [], []
    for offset in range(rng["days"]):
        current = rng["first"] + timedelta(days=offset)
        key = current.isoformat()
        labels.append(key)
        views.append(traffic.get(key, (0, 0))[0])
        visitors.append(traffic.get(key, (0, 0))[1])
        projects.append(pviews.get(key, 0))
    return {"labels": labels, "page_views": views, "visitors": visitors, "project_views": projects}


def project_engagement(start, end) -> list[dict]:
    """One row per published project (including ones with zero views)."""
    published = db.session.scalars(
        db.select(Project).where(Project.is_published.is_(True), Project.is_placeholder.is_(False))
        .order_by(Project.sort_order, Project.id)
    ).all()
    view_rows = {
        pid: (views, viewers)
        for pid, views, viewers in db.session.execute(
            db.select(ProjectView.project_id, db.func.count(ProjectView.id),
                      db.func.count(db.distinct(ProjectView.visitor_id)))
            .where(ProjectView.created_at >= start, ProjectView.created_at < end)
            .group_by(ProjectView.project_id)
        ).all()
    }
    click_rows = dict(db.session.execute(
        db.select(ContactEvent.source_path, db.func.count(ContactEvent.id))
        .where(ContactEvent.created_at >= start, ContactEvent.created_at < end,
               ContactEvent.source_path.like("/projects/%"))
        .group_by(ContactEvent.source_path)
    ).all())
    rows = []
    for project in published:
        views, viewers = view_rows.get(project.id, (0, 0))
        clicks = click_rows.get(f"/projects/{project.slug}", 0)
        rows.append({
            "id": project.id, "title": project.title, "slug": project.slug,
            "views": views, "viewers": viewers, "clicks": clicks,
            "has_media": bool(project.thumbnail or project.gallery),
            "summary_length": len(project.summary or ""),
            "description_length": len(project.description or ""),
        })
    rows.sort(key=lambda r: (-r["views"], r["title"].lower()))
    return rows


def trend(current: int, previous: int) -> dict:
    """Observed change versus the previous period of the same length."""
    if previous == 0 and current == 0:
        return {"direction": "flat", "text": "No activity in either period"}
    if previous == 0:
        return {"direction": "up", "text": f"Up from 0 (previous period had none)"}
    change = (current - previous) / previous * 100
    if abs(change) < 0.5:
        return {"direction": "flat", "text": f"Unchanged vs previous period ({previous})"}
    arrow = "up" if change > 0 else "down"
    return {"direction": arrow, "text": f"{change:+.0f}% vs previous period ({previous})"}


# ---------------------------------------------------------------- activity
def recent_activity(limit: int = 15) -> list[dict]:
    """Merge the latest genuine events into one feed, newest first."""
    items = []
    for visitor in db.session.scalars(db.select(Visitor).order_by(Visitor.first_seen.desc()).limit(limit)):
        items.append({"time": visitor.first_seen, "kind": "visitor", "text": "New visitor"})
    for created, title in db.session.execute(
        db.select(ProjectView.created_at, Project.title).select_from(ProjectView)
        .join(Project, Project.id == ProjectView.project_id)
        .order_by(ProjectView.created_at.desc()).limit(limit)
    ):
        items.append({"time": created, "kind": "project_view", "text": f"Project viewed: {title}"})
    for event in db.session.scalars(db.select(ContactEvent).order_by(ContactEvent.created_at.desc()).limit(limit)):
        label = CHANNEL_LABELS.get(event.channel, event.channel)
        items.append({"time": event.created_at, "kind": "contact_click",
                      "text": f"{label} button clicked (a click only, not an enquiry)"})
    for lead in db.session.scalars(db.select(Lead).order_by(Lead.created_at.desc()).limit(limit)):
        items.append({"time": lead.created_at, "kind": "lead", "text": f"New enquiry from {lead.name}"})
    for note in db.session.scalars(
        db.select(Notification).where(Notification.kind != "new_lead")
        .order_by(Notification.created_at.desc()).limit(limit)
    ):
        items.append({"time": note.created_at, "kind": note.kind, "text": note.message})
    items.sort(key=lambda item: item["time"], reverse=True)
    return items[:limit]


# ---------------------------------------------------------------- everything
def build_report(rng: dict) -> dict:
    start, end = rng["start"], rng["end"]
    length = end - start
    prev_start = start - length
    now = utcnow()
    today_start = datetime.combine(now.date(), time.min)
    tomorrow = today_start + timedelta(days=1)

    series = daily_series(rng)
    engagement = project_engagement(start, end)
    clicks = contact_clicks(start, end)
    views, uniques = page_views(start, end), unique_visitors(start, end)

    return {
        "range": rng,
        "views": views,
        "uniques": uniques,
        "project_views": project_views(start, end),
        "clicks": clicks,
        "enquiries": enquiries(start, end),
        "views_trend": trend(views, page_views(prev_start, start)),
        "uniques_trend": trend(uniques, unique_visitors(prev_start, start)),
        "total_visitors": _scalar(db.select(db.func.count(Visitor.id))),
        "today_visitors": unique_visitors(today_start, tomorrow),
        "week_visitors": unique_visitors(today_start - timedelta(days=6), tomorrow),
        "month_visitors": unique_visitors(today_start - timedelta(days=29), tomorrow),
        "engagement": engagement,
        "series": series,
        "activity": recent_activity(),
        "has_data": bool(views or clicks["total"] or enquiries(start, end)),
    }
