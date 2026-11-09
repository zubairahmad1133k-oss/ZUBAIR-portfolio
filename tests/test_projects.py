from extensions import db
from models import Project, ProjectMedia
from tests.conftest import PNG, count, project_id, seed_projects, upload
from pathlib import Path


def form(**changes):
    data = {"title": "New Thing", "category": "Test", "summary": "A short summary.", "description": "",
            "technologies": "Python, Flask", "visual_class": "visual-code", "icon": "✦",
            "card_label": "", "link_text": "", "demo_url": "", "github_url": "", "docs_url": ""}
    data.update(changes)
    return data


def get_project(app, pid):
    with app.app_context():
        project = db.session.get(Project, pid)
        return {"title": project.title, "published": project.is_published, "slug": project.slug,
                "thumbnail": project.thumbnail, "description": project.description, "order": project.sort_order}


def test_create_project_as_draft_then_publish_and_unpublish(app, admin_client):
    response = admin_client.post("/admin/projects/new", data=form())
    assert response.status_code == 302
    pid = project_id(app, "new-thing")
    assert pid and get_project(app, pid)["published"] is False
    assert admin_client.get("/projects/new-thing").status_code == 404        # draft is private

    admin_client.post(f"/admin/projects/{pid}/toggle-publish")
    assert get_project(app, pid)["published"] is True
    assert admin_client.get("/projects/new-thing").status_code == 200

    admin_client.post(f"/admin/projects/{pid}/toggle-publish")
    assert get_project(app, pid)["published"] is False


def test_published_project_appears_on_homepage_automatically(app, admin_client):
    admin_client.post("/admin/projects/new", data=form(title="Auto Listed", is_published="on"))
    assert "Auto Listed" in admin_client.get("/").get_data(as_text=True)


def test_blank_description_falls_back_to_summary(app, admin_client):
    admin_client.post("/admin/projects/new", data=form(title="Fallback"))
    assert get_project(app, project_id(app, "fallback"))["description"] == "A short summary."


def test_edit_project(app, admin_client):
    seed_projects(app)
    pid = project_id(app, "code-checker")
    response = admin_client.post(f"/admin/projects/{pid}/edit", data=form(title="Code Checker v2", is_published="on"))
    assert response.status_code == 302
    info = get_project(app, pid)
    assert info["title"] == "Code Checker v2" and info["slug"] == "code-checker"  # slug stays stable


def test_validation_errors_do_not_save(app, admin_client):
    before = count(app, Project)
    assert admin_client.post("/admin/projects/new", data=form(title="")).status_code == 400
    assert admin_client.post("/admin/projects/new", data=form(demo_url="javascript:alert(1)")).status_code == 400
    assert count(app, Project) == before


def test_delete_project(app, admin_client):
    seed_projects(app)
    pid = project_id(app, "kpk-news")
    assert admin_client.post(f"/admin/projects/{pid}/delete").status_code == 302
    assert project_id(app, "kpk-news") is None
    assert admin_client.get("/projects/kpk-news").status_code == 404


def test_reorder_projects(app, admin_client):
    seed_projects(app)
    first, second = project_id(app, "code-checker"), project_id(app, "kpk-news")
    admin_client.post(f"/admin/projects/{second}/move/up")
    assert get_project(app, second)["order"] < get_project(app, first)["order"]


def test_preview_shows_unpublished_project_to_admin_only(app, admin_client, client):
    admin_client.post("/admin/projects/new", data=form(title="Hidden Preview"))
    pid = project_id(app, "hidden-preview")
    assert b"NOT visible to visitors" in admin_client.get(f"/admin/projects/{pid}/preview").data
    assert app.test_client().get(f"/admin/projects/{pid}/preview").status_code == 302


def test_thumbnail_upload_and_removal(app, admin_client):
    admin_client.post("/admin/projects/new", data=form(title="With Image", thumbnail=upload(PNG, "t.png")))
    pid = project_id(app, "with-image")
    stored = get_project(app, pid)["thumbnail"]
    assert stored and stored.endswith(".png")
    assert (Path(app.config["UPLOAD_FOLDER"]) / "public" / stored).is_file()
    assert admin_client.get(f"/media/{stored}").status_code == 200
    admin_client.post(f"/admin/projects/{pid}/edit", data=form(title="With Image", remove_thumbnail="on"))
    assert get_project(app, pid)["thumbnail"] is None
    assert not (Path(app.config["UPLOAD_FOLDER"]) / "public" / stored).exists()


def test_fake_image_is_rejected(app, admin_client):
    fake = b"<?php system($_GET['c']); ?>"
    response = admin_client.post("/admin/projects/new", data=form(title="Evil", thumbnail=upload(fake, "shell.php.png")))
    assert response.status_code == 400
    assert project_id(app, "evil") is None
    assert not list((Path(app.config["UPLOAD_FOLDER"]) / "public").iterdir())


def test_code_snippets_are_shown_publicly_and_escaped(app, admin_client):
    seed_projects(app)
    pid = project_id(app, "code-checker")
    admin_client.post(f"/admin/projects/{pid}/code/", data={
        "title": "Parser", "language": "python", "description": "Core idea", "code": "print('<b>hi</b>')"})
    html = admin_client.get("/projects/code-checker").get_data(as_text=True)
    assert "Parser" in html and "&lt;b&gt;hi&lt;/b&gt;" in html and "<b>hi</b>" not in html
    assert "complete source code is private" in html.lower()
    too_long = "x = 1\n" * 400
    assert admin_client.post(f"/admin/projects/{pid}/code/", data={
        "title": "Huge", "language": "python", "code": too_long}).status_code == 400


def test_project_page_links_to_the_original_website(app, admin_client):
    admin_client.post("/admin/projects/new", data=form(
        title="Linked Site", is_published="on", demo_url="https://www.example.com/app"))
    html = admin_client.get("/projects/linked-site").get_data(as_text=True)
    assert 'href="https://www.example.com/app"' in html
    assert "Visit example.com" in html and 'target="_blank"' in html and "noopener" in html
    admin_client.post("/admin/projects/new", data=form(title="No Link", is_published="on"))
    assert "LIVE WEBSITE" not in admin_client.get("/projects/no-link").get_data(as_text=True)


def test_one_click_starter_projects(app, admin_client):
    assert admin_client.post("/admin/projects/seed").status_code == 302
    assert count(app, Project) == 4
    admin_client.post("/admin/projects/seed")          # running it again adds nothing
    assert count(app, Project) == 4
    assert b"Code Checker" in admin_client.get("/").data
    assert app.test_client().post("/admin/projects/seed").status_code == 302   # needs login
