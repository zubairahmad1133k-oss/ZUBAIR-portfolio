import io

import pytest

from app import create_app
from extensions import db
from models import AdminUser, Project
from seed_data import INITIAL_PROJECTS

PASSWORD = "Correct-Horse-42"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
PDF = b"%PDF-1.4\n" + b"0" * 64
BROWSER = "Mozilla/5.0 (automated-test)"


@pytest.fixture()
def app(tmp_path):
    return create_app("testing", overrides={"UPLOAD_FOLDER": str(tmp_path / "uploads")})


@pytest.fixture()
def client(app):
    test_client = app.test_client()
    test_client.environ_base["HTTP_USER_AGENT"] = BROWSER  # analytics ignores empty agents
    return test_client


def make_admin(app, username="zubair", email="z@example.com", password=PASSWORD):
    with app.app_context():
        user = AdminUser(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()


def login(client, username="zubair", password=PASSWORD):
    return client.post("/admin/login", data={"username": username, "password": password})


@pytest.fixture()
def admin_client(app, client):
    make_admin(app)
    assert login(client).status_code == 302
    return client


def seed_projects(app):
    with app.app_context():
        for data in INITIAL_PROJECTS:
            db.session.add(Project(description=data["summary"], is_published=True, **data))
        db.session.commit()


def add_draft(app):
    with app.app_context():
        db.session.add(Project(title="Secret Draft", slug="secret-draft", summary="hidden",
                               description="hidden", is_published=False, sort_order=99))
        db.session.commit()


def project_id(app, slug):
    with app.app_context():
        return db.session.scalar(db.select(Project.id).where(Project.slug == slug))


def count(app, model):
    with app.app_context():
        return db.session.scalar(db.select(db.func.count(model.id)))


def upload(data_bytes, name):
    return (io.BytesIO(data_bytes), name)
