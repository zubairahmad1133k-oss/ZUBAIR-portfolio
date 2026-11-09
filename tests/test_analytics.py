from extensions import db
from models import ContactEvent, PageEvent, ProjectView, Visitor
from services import reports
from tests.conftest import count, seed_projects


def test_visit_is_recorded_without_personal_data(app, client):
    client.get("/")
    assert count(app, PageEvent) == 1 and count(app, Visitor) == 1
    with app.app_context():
        event = db.session.scalars(db.select(PageEvent)).one()
        assert event.path == "/" and event.referrer_host is None
    cookie = client.get_cookie("zos_vid")
    assert cookie is not None and len(cookie.value) == 32


def test_returning_visitor_is_not_counted_twice_as_unique(app, client):
    client.get("/")
    client.get("/")
    assert count(app, Visitor) == 1 and count(app, PageEvent) == 2


def test_do_not_track_bots_and_admin_are_not_recorded(app, client, admin_client):
    other = app.test_client()
    other.get("/", headers={"DNT": "1", "User-Agent": "Mozilla/5.0"})
    other.get("/", headers={"Sec-GPC": "1", "User-Agent": "Mozilla/5.0"})
    other.get("/", headers={"User-Agent": "Googlebot/2.1"})
    other.get("/", headers={"User-Agent": ""})  # no user agent at all
    admin_client.get("/")  # logged-in admin
    assert count(app, PageEvent) == 0 and count(app, Visitor) == 0


def test_project_views_are_recorded_and_deduplicated(app, client):
    seed_projects(app)
    client.get("/projects/code-checker")
    client.get("/projects/code-checker")  # refresh within 30 minutes
    client.get("/projects/kpk-news")
    assert count(app, ProjectView) == 2
    assert count(app, PageEvent) == 3
    assert client.get("/projects/secret-nonexistent").status_code == 404
    assert count(app, ProjectView) == 2


def test_contact_clicks_are_recorded_separately_from_enquiries(app, client):
    client.get("/")
    ok = client.post("/api/track", json={"type": "contact_click", "channel": "whatsapp", "path": "/"})
    assert ok.status_code == 204
    client.post("/api/track", json={"type": "contact_click", "channel": "email", "path": "/"})
    client.post("/api/track", json={"type": "contact_click", "channel": "carrier-pigeon", "path": "/"})
    client.post("/api/track", json={"type": "other", "channel": "email", "path": "/"})
    assert count(app, ContactEvent) == 2
    from models import Lead
    assert count(app, Lead) == 0   # a click is never an enquiry


def test_report_numbers_match_recorded_events(app, client):
    seed_projects(app)
    client.get("/")
    client.get("/projects/code-checker")
    client.post("/api/track", json={"type": "contact_click", "channel": "whatsapp", "path": "/projects/code-checker"})
    with app.app_context():
        report = reports.build_report(reports.resolve_range({"range": "today"}))
        assert report["views"] == 2 and report["uniques"] == 1
        assert report["project_views"] == 1
        assert report["clicks"] == {"whatsapp": 1, "email": 0, "total": 1}
        assert report["enquiries"] == 0
        assert sum(report["series"]["page_views"]) == 2
        top = report["engagement"][0]
        assert top["slug"] == "code-checker" and top["views"] == 1 and top["clicks"] == 1


def test_empty_database_gives_zeroes_not_invented_numbers(app):
    with app.app_context():
        report = reports.build_report(reports.resolve_range({"range": "30d"}))
        assert report["views"] == 0 and report["uniques"] == 0 and report["has_data"] is False
        assert sum(report["series"]["page_views"]) == 0 and len(report["series"]["labels"]) == 30


def test_date_ranges(app):
    with app.app_context():
        assert reports.resolve_range({"range": "today"})["days"] == 1
        assert reports.resolve_range({"range": "90d"})["days"] == 90
        custom = reports.resolve_range({"range": "custom", "from": "2026-01-01", "to": "2026-01-10"})
        assert custom["days"] == 10 and custom["key"] == "custom"
        bad = reports.resolve_range({"range": "custom", "from": "nonsense", "to": "2026-01-10"})
        assert bad["key"] == "7d" and bad["note"]


def test_analytics_page_renders_for_admin(admin_client):
    for query in ("", "?range=today", "?range=90d", "?range=custom&from=2026-01-01&to=2026-01-31"):
        response = admin_client.get("/admin/analytics/" + query)
        assert response.status_code == 200
        assert b"CONFIRMED ENQUIRIES" in response.data
