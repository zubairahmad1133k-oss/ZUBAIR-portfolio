"""AI Analyst.

`analyse()` is rule-based and needs no API key: it only restates numbers that
are really in the database and labels everything it cannot know as a
possibility. `ai_explain()` is optional and only used when ANTHROPIC_API_KEY
is set; it receives the SAME computed facts (no raw visitor data).
"""
import json
import urllib.error
import urllib.request

from extensions import db
from models import Project
from services import reports

MIN_VIEWS_FOR_PATTERNS = 20
SHORT_DESCRIPTION = 150  # characters; a simple length heuristic, not a quality score


class AnalystError(Exception):
    pass


def analyse(rng: dict) -> dict:
    """Return {'facts', 'possible', 'suggestions', 'note'} for the date range."""
    report = reports.build_report(rng)
    length = rng["end"] - rng["start"]
    label = rng["label"].lower()
    facts, possible, suggestions = [], [], []
    views, uniques = report["views"], report["uniques"]
    clicks, enquiries = report["clicks"], report["enquiries"]
    rows = report["engagement"]
    enough = views >= MIN_VIEWS_FOR_PATTERNS
    note = None

    # ---- observed facts -------------------------------------------------
    facts.append(f"{label.capitalize()}: {views} page view(s) from {uniques} unique visitor(s).")
    if views or reports.page_views(rng["start"] - length, rng["start"]):
        facts.append(f"Page views {report['views_trend']['text'].lower()}.")
        facts.append(f"Unique visitors {report['uniques_trend']['text'].lower()}.")
    if report["project_views"]:
        facts.append(f"Projects were opened {report['project_views']} time(s).")
        ranked = [r for r in rows if r["views"] > 0]
        if ranked:
            top = ranked[0]
            facts.append(f"Most viewed project: {top['title']} ({top['views']} view(s), {top['viewers']} unique viewer(s)).")
            if len(ranked) > 1:
                facts.append("Others: " + ", ".join(f"{r['title']} ({r['views']})" for r in ranked[1:]) + ".")
    unseen = [r["title"] for r in rows if r["views"] == 0]
    if unseen and rows:
        facts.append("No views in this period: " + ", ".join(unseen) + ".")
    facts.append(f"Contact button clicks: {clicks['total']} (WhatsApp {clicks['whatsapp']}, email {clicks['email']}).")
    facts.append(f"Confirmed enquiries from the form: {enquiries}. A button click is not counted as an enquiry.")

    # ---- cautious possibilities (only when the data supports saying anything) ----
    if not enough:
        note = (f"Only {views} page view(s) so far. With fewer than {MIN_VIEWS_FOR_PATTERNS}, "
                "changes can easily be chance, so treat everything below as early signals.")
    else:
        if clicks["total"] and not enquiries:
            possible.append("People may prefer messaging you directly on WhatsApp or email to filling in the form. "
                            "The data cannot show whether those clicks became conversations.")
        if clicks["whatsapp"] > clicks["email"]:
            possible.append("WhatsApp is clicked more than email, so it may be the easier way for visitors to reach you.")
        elif clicks["email"] > clicks["whatsapp"]:
            possible.append("Email is clicked more than WhatsApp. Visitors may want a written record or a more formal route.")
        if report["project_views"] and views and report["project_views"] / views < 0.2:
            possible.append("Few visits lead to a project page. The project cards on the homepage may not be inviting enough to click, "
                            "or visitors may come only for contact details.")
        if unseen and report["project_views"]:
            possible.append("Projects with no views may be lower on the page, or their cards may be less eye-catching. This is a guess, not something the data proves.")
    possible.append("This tool records what happened, not why. It cannot tell you why anyone left the site.")

    # ---- suggestions -----------------------------------------------------
    published = db.session.scalars(
        db.select(Project).where(Project.is_published.is_(True), Project.is_placeholder.is_(False))
    ).all()
    for project in published:
        if len(project.description or "") < SHORT_DESCRIPTION:
            suggestions.append(f"{project.title}: the full description is short ({len(project.description or '')} characters). "
                               "Explain the problem it solves, what you built and what you learned.")
        if not (project.thumbnail or project.gallery):
            suggestions.append(f"{project.title}: add a thumbnail or screenshots so visitors can see the work.")
        if not project.snippets:
            suggestions.append(f"{project.title}: add 1–3 code highlights to show your skills without sharing the full source.")
        if not (project.demo_url or project.github_url or project.docs_url):
            suggestions.append(f"{project.title}: there is no demo, GitHub or documentation link. Even a short walkthrough video or write-up helps.")
    if not views:
        suggestions.append("Share your portfolio link (LinkedIn, WhatsApp status, GitHub profile) so real visitors can arrive.")
    if views and not clicks["total"] and not enquiries:
        suggestions.append("Make the contact options easier to find, for example a clear call to action at the end of each project page.")
    if not published:
        suggestions.append("Publish at least one project so there is something for visitors to explore.")
    return {"facts": facts, "possible": possible, "suggestions": suggestions, "note": note}


# --------------------------------------------------------------- optional AI
_SYSTEM = (
    "You are an analytics assistant for a personal developer portfolio. Use ONLY the facts you are given. "
    "Never invent numbers, visitors, reasons or events, and never claim to know why visitors leave. "
    "Write three short sections titled 'Observed', 'Possible explanations (uncertain)' and 'Suggested next steps'. "
    "Keep it under 250 words, plain language."
)


def ai_explain(analysis: dict, label: str, api_key: str, model: str) -> str:
    prompt = (
        f"Date range: {label}\n\nObserved facts:\n- " + "\n- ".join(analysis["facts"])
        + "\n\nRule-based possibilities:\n- " + "\n- ".join(analysis["possible"])
        + "\n\nRule-based suggestions:\n- " + "\n- ".join(analysis["suggestions"] or ["(none)"])
        + (f"\n\nData note: {analysis['note']}" if analysis["note"] else "")
    )
    body = json.dumps({
        "model": model, "max_tokens": 700, "system": _SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"content-type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise AnalystError(f"The AI service could not be reached ({exc.__class__.__name__}).") from exc
    text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text").strip()
    if not text:
        raise AnalystError("The AI service returned an empty answer.")
    return text
