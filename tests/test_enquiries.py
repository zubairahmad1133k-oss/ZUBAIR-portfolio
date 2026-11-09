from extensions import db
from models import Lead, Notification
from tests.conftest import count

VALID = {"name": "Ali Khan", "email": "ali@example.com", "project_type": "Website",
         "message": "I would like a website for my shop."}


def test_valid_enquiry_creates_lead_and_notification(app, client):
    response = client.post("/enquiry", data=VALID)
    assert response.status_code == 302
    with app.app_context():
        lead = db.session.scalars(db.select(Lead)).one()
        assert lead.status == "new" and lead.email == "ali@example.com"
        note = db.session.scalars(db.select(Notification)).one()
        assert note.kind == "new_lead" and not note.is_read and f"/admin/enquiries/{lead.id}" in note.link


def test_invalid_enquiries_are_rejected(app, client):
    for bad in ({**VALID, "email": "not-an-email"}, {**VALID, "name": ""},
                {**VALID, "project_type": "Hacking"}, {**VALID, "message": "short"}):
        assert client.post("/enquiry", data=bad).status_code == 400
    assert count(app, Lead) == 0


def test_honeypot_bots_get_no_lead(app, client):
    assert client.post("/enquiry", data={**VALID, "website": "http://spam.example"}).status_code == 302
    assert count(app, Lead) == 0


def test_enquiry_text_is_escaped_in_admin(app, client, admin_client):
    other = app.test_client()
    other.post("/enquiry", data={**VALID, "name": "<script>alert(1)</script>"})
    html = admin_client.get("/admin/enquiries/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


def test_admin_enquiry_workflow(app, client, admin_client):
    app.test_client().post("/enquiry", data=VALID)
    app.test_client().post("/enquiry", data={**VALID, "name": "Sara", "message": "Need an AI chatbot please."})
    with app.app_context():
        lead_id = db.session.scalar(db.select(Lead.id).where(Lead.name == "Ali Khan"))

    assert b"Ali Khan" in admin_client.get("/admin/enquiries/").data
    assert b"Sara" not in admin_client.get("/admin/enquiries/?q=website").data       # search
    assert b"Sara" in admin_client.get("/admin/enquiries/?q=chatbot").data

    admin_client.get(f"/admin/enquiries/{lead_id}")                                    # opening clears notification
    with app.app_context():
        unread = db.session.scalar(db.select(db.func.count(Notification.id)).where(Notification.is_read.is_(False)))
        assert unread == 1

    admin_client.post(f"/admin/enquiries/{lead_id}", data={"status": "in_progress", "private_notes": "Call Monday"})
    with app.app_context():
        lead = db.session.get(Lead, lead_id)
        assert lead.status == "in_progress" and lead.private_notes == "Call Monday"
    assert b"Ali Khan" in admin_client.get("/admin/enquiries/?status=in_progress").data
    assert b"Ali Khan" not in admin_client.get("/admin/enquiries/?status=completed").data

    admin_client.post(f"/admin/enquiries/{lead_id}", data={"status": "bogus", "private_notes": ""})
    with app.app_context():
        assert db.session.get(Lead, lead_id).status == "in_progress"                   # invalid status refused

    admin_client.post(f"/admin/enquiries/{lead_id}/delete")
    assert count(app, Lead) == 1


def test_mark_all_notifications_read(app, client, admin_client):
    app.test_client().post("/enquiry", data=VALID)
    assert b"New enquiry from Ali Khan" in admin_client.get("/admin/").data
    admin_client.post("/admin/notifications/read")
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Notification.id)).where(Notification.is_read.is_(False))) == 0


def test_project_actions_create_notifications(app, admin_client):
    admin_client.post("/admin/projects/new", data={
        "title": "Notified", "summary": "s", "category": "", "technologies": "", "visual_class": "visual-code",
        "icon": "x", "is_published": "on"})
    with app.app_context():
        messages = [n.message for n in db.session.scalars(db.select(Notification))]
    assert "Project published: Notified" in messages
