from pathlib import Path

from extensions import db
from models import Achievement, Goal, ProjectMedia
from tests.conftest import PDF, PNG, count, project_id, seed_projects, upload


def upload_files(client, *files, **fields):
    data = {"files": list(files), "kind": "screenshot", "folder": "Demo", **fields}
    return client.post("/admin/media/upload", data=data, content_type="multipart/form-data")


def test_image_upload_is_public_and_attached_to_project(app, admin_client):
    seed_projects(app)
    pid = project_id(app, "code-checker")
    assert upload_files(admin_client, upload(PNG, "shot.png"), project_id=str(pid), caption="Home").status_code == 302
    with app.app_context():
        item = db.session.scalars(db.select(ProjectMedia)).one()
        assert item.kind == "screenshot" and item.is_public and item.project_id == pid and item.folder == "Demo"
        stored = item.filename
    assert (Path(app.config["UPLOAD_FOLDER"]) / "public" / stored).is_file()
    assert admin_client.get(f"/media/{stored}").status_code == 200
    page = admin_client.get("/projects/code-checker").get_data(as_text=True)
    assert f"/media/{stored}" in page and "Screenshots" in page


def test_pdf_is_private(app, admin_client):
    upload_files(admin_client, upload(PDF, "spec.pdf"))
    with app.app_context():
        item = db.session.scalars(db.select(ProjectMedia)).one()
        stored, media_id = item.filename, item.id
        assert item.kind == "document" and not item.is_public
    assert (Path(app.config["UPLOAD_FOLDER"]) / "private" / stored).is_file()
    assert admin_client.get(f"/media/{stored}").status_code == 404          # never public
    assert admin_client.get(f"/admin/media/{media_id}/file").status_code == 200
    anonymous = app.test_client()
    assert anonymous.get(f"/admin/media/{media_id}/file").status_code == 302
    assert anonymous.get(f"/media/{stored}").status_code == 404


def test_dangerous_or_oversized_uploads_are_rejected(app, admin_client):
    upload_files(admin_client, upload(b"<?php echo 1; ?>", "evil.php"))
    upload_files(admin_client, upload(b"<svg onload=alert(1)>", "x.svg"))
    upload_files(admin_client, upload(PNG + b"0" * (6 * 1024 * 1024), "huge.png"))
    upload_files(admin_client, upload(b"", "empty.png"))
    assert count(app, ProjectMedia) == 0
    for folder in ("public", "private"):
        assert not list((Path(app.config["UPLOAD_FOLDER"]) / folder).iterdir())


def test_rename_organise_and_delete_media(app, admin_client):
    upload_files(admin_client, upload(PNG, "a.png"))
    with app.app_context():
        item = db.session.scalars(db.select(ProjectMedia)).one()
        media_id, stored = item.id, item.filename
    admin_client.post(f"/admin/media/{media_id}/edit", data={
        "display_name": "Landing page", "caption": "Hero", "folder": "Launch", "project_id": "", "kind": "image"})
    with app.app_context():
        item = db.session.get(ProjectMedia, media_id)
        assert (item.display_name, item.folder, item.kind) == ("Landing page", "Launch", "image")
    assert b"Landing page" in admin_client.get("/admin/media/?folder=Launch").data
    admin_client.post(f"/admin/media/{media_id}/delete")
    assert count(app, ProjectMedia) == 0
    assert not (Path(app.config["UPLOAD_FOLDER"]) / "public" / stored).exists()


def test_goals_and_achievements_are_manual(app, admin_client):
    admin_client.post("/admin/goals/new", data={"title": "Get 3 clients", "target_date": "2026-12-31"})
    with app.app_context():
        goal = db.session.scalars(db.select(Goal)).one()
        gid = goal.id
        assert goal.progress == 0 and not goal.is_completed          # nothing automatic
    admin_client.post(f"/admin/goals/{gid}/progress", data={"progress": "40"})
    admin_client.post(f"/admin/goals/{gid}/progress", data={"progress": "140"})   # invalid, ignored
    with app.app_context():
        assert db.session.get(Goal, gid).progress == 40
    admin_client.post(f"/admin/goals/{gid}/complete")
    with app.app_context():
        done = db.session.get(Goal, gid)
        assert done.is_completed and done.progress == 100 and done.completed_at
    admin_client.post("/admin/goals/achievements/new", data={"title": "First client", "goal_id": str(gid)})
    assert count(app, Achievement) == 1
    assert b"First client" in admin_client.get("/admin/goals/").data
    admin_client.post(f"/admin/goals/{gid}/reopen")
    with app.app_context():
        assert not db.session.get(Goal, gid).is_completed


def test_analyst_uses_rule_based_analysis_without_api_key(app, admin_client):
    seed_projects(app)
    response = admin_client.get("/admin/analyst/?range=30d")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Observed" in html and "0 page view" in html and "rule-based" in html
    assert "cannot tell you why" in html            # never pretends to know why visitors leave
    post = admin_client.post("/admin/analyst/", data={"ai": "1", "range": "30d"})
    assert post.status_code == 200 and b"No AI key is configured" in post.data


def test_analyst_reports_real_numbers(app, admin_client):
    seed_projects(app)
    visitor = app.test_client()  # a real visitor; the admin's own visits are never counted
    visitor.get("/projects/code-checker")
    visitor.post("/api/track", json={"type": "contact_click", "channel": "whatsapp", "path": "/"})
    html = admin_client.get("/admin/analyst/?range=today").get_data(as_text=True)
    assert "1 page view" in html and "Most viewed project: Code Checker" in html
    assert "WhatsApp 1" in html and "not counted as an enquiry" in html


def test_uploads_can_be_switched_off_for_hosts_without_storage(tmp_path):
    from app import create_app
    from tests.conftest import login, make_admin
    app = create_app("testing", overrides={"UPLOADS_ENABLED": False, "UPLOAD_FOLDER": str(tmp_path / "u")})
    make_admin(app)
    client = app.test_client()
    login(client)
    response = client.post("/admin/media/upload", data={"files": [upload(PNG, "a.png")], "folder": "x"},
                           content_type="multipart/form-data", follow_redirects=True)
    assert b"turned off on this host" in response.data
    assert count(app, ProjectMedia) == 0
