from sqlalchemy import inspect

from extensions import db
from tests.conftest import add_draft, seed_projects

EXPECTED_TABLES = {
    "admin_users", "projects", "project_media", "visitors", "page_events", "project_views",
    "leads", "contact_events", "notifications", "goals", "achievements", "code_snippets",
}


def test_app_starts_and_health_check_works(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "ok"}


def test_database_initialisation_creates_every_table(app):
    with app.app_context():
        assert EXPECTED_TABLES <= set(inspect(db.engine).get_table_names())


def test_homepage_shows_only_published_projects(app, client):
    seed_projects(app)
    add_draft(app)
    html = client.get("/").get_data(as_text=True)
    assert "Code Checker" in html and "KPK News" in html and "Khan Academy" in html
    assert "What&#39;s Next?" in html or "What's Next?" in html
    assert "Secret Draft" not in html


def test_homepage_keeps_contact_details(app, client):
    html = client.get("/").get_data(as_text=True)
    assert "https://wa.me/923025852709" in html
    assert "mailto:zubairahmad1133k@gmail.com" in html


def test_project_detail_pages(app, client):
    seed_projects(app)
    add_draft(app)
    assert client.get("/projects/code-checker").status_code == 200
    assert client.get("/projects/secret-draft").status_code == 404   # unpublished stays private
    assert client.get("/projects/whats-next").status_code == 404     # placeholder has no page
    assert client.get("/projects/does-not-exist").status_code == 404


def test_robots_and_sitemap(app, client):
    seed_projects(app)
    add_draft(app)
    robots = client.get("/robots.txt").get_data(as_text=True)
    assert "Disallow: /admin" in robots and "sitemap.xml" in robots
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/projects/code-checker" in sitemap and "secret-draft" not in sitemap


def test_security_headers_present(client):
    headers = client.get("/").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
