from app import create_app
from extensions import limiter
from tests.conftest import PASSWORD, login, make_admin

PROTECTED = [
    "/admin/", "/admin/projects/", "/admin/analytics/", "/admin/enquiries/",
    "/admin/media/", "/admin/goals/", "/admin/analyst/", "/admin/account",
]


def test_valid_login_reaches_dashboard(app, client):
    make_admin(app)
    response = login(client)
    assert response.status_code == 302 and response.headers["Location"].endswith("/admin/")
    assert b"Welcome back" in client.get("/admin/").data


def test_invalid_login_is_rejected_with_generic_message(app, client):
    make_admin(app)
    wrong_password = login(client, password="Wrong-Password-1")
    wrong_user = login(client, username="nobody")
    for response in (wrong_password, wrong_user):
        assert response.status_code == 200
        assert b"Incorrect username or password" in response.data
    assert client.get("/admin/").status_code == 302  # still logged out


def test_every_admin_page_requires_login(client):
    for path in PROTECTED:
        response = client.get(path)
        assert response.status_code == 302, path
        assert "/admin/login" in response.headers["Location"], path


def test_admin_post_routes_require_login(client):
    for path in ("/admin/projects/new", "/admin/media/upload", "/admin/goals/new", "/admin/account/password"):
        response = client.post(path, data={})
        assert response.status_code == 302, path
        assert "/admin/login" in response.headers["Location"], path


def test_logout_ends_session(admin_client):
    assert admin_client.post("/admin/logout").status_code == 302
    assert admin_client.get("/admin/").status_code == 302


def test_login_redirect_cannot_leave_the_site(app, client):
    make_admin(app)
    response = client.post("/admin/login?next=//evil.example", data={"username": "zubair", "password": PASSWORD})
    assert "evil.example" not in response.headers["Location"]


def test_csrf_blocks_forms_without_token(app, client):
    make_admin(app)
    app.config["WTF_CSRF_ENABLED"] = True
    response = client.post("/admin/login", data={"username": "zubair", "password": PASSWORD})
    assert response.status_code == 400


def test_login_is_rate_limited(tmp_path):
    app = create_app("testing", overrides={"RATELIMIT_ENABLED": True, "UPLOAD_FOLDER": str(tmp_path / "u")})
    try:
        client = app.test_client()
        statuses = [login(client, password="Wrong-Password-1").status_code for _ in range(7)]
        assert 429 in statuses
    finally:
        limiter.reset()


def test_password_change_signs_out_other_sessions(app, admin_client):
    other = app.test_client()
    assert login(other).status_code == 302
    response = admin_client.post("/admin/account/password", data={
        "current_password": PASSWORD, "new_password": "Brand-New-Pass-99", "confirm_password": "Brand-New-Pass-99"})
    assert response.status_code == 302
    assert admin_client.get("/admin/").status_code == 200   # this session stays alive
    assert other.get("/admin/").status_code == 302          # the other one is signed out


def test_weak_new_password_is_refused(app, admin_client):
    admin_client.post("/admin/account/password", data={
        "current_password": PASSWORD, "new_password": "short", "confirm_password": "short"})
    admin_client.post("/admin/logout")
    assert login(admin_client, password="short").status_code == 200
    assert login(admin_client).status_code == 302


def test_setup_creates_first_admin_then_closes(app, client):
    response = client.post("/admin/setup", data={
        "setup_token": "test-setup-token", "username": "newadmin", "email": "n@example.com",
        "password": "First-Admin-Pass-1", "confirm": "First-Admin-Pass-1"})
    assert response.status_code == 302
    assert login(client, username="newadmin", password="First-Admin-Pass-1").status_code == 302
    again = app.test_client().get("/admin/setup")
    assert again.status_code == 302 and "/admin/login" in again.headers["Location"]


def test_setup_refuses_wrong_token(app, client):
    client.post("/admin/setup", data={"setup_token": "wrong", "username": "xxxxx", "email": "n@example.com",
                                      "password": "First-Admin-Pass-1", "confirm": "First-Admin-Pass-1"})
    assert login(client, username="xxxxx", password="First-Admin-Pass-1").status_code == 200


def test_reset_password_with_setup_token(app, client):
    make_admin(app)
    response = client.post("/admin/reset-password", data={
        "setup_token": "test-setup-token", "username": "zubair",
        "password": "Another-Pass-77", "confirm": "Another-Pass-77"})
    assert response.status_code == 302
    assert login(client, password=PASSWORD).status_code == 200                # old password no longer works
    assert login(client, password="Another-Pass-77").status_code == 302       # the new one does


def test_reset_refused_with_wrong_token_or_weak_password(app, client):
    make_admin(app)
    base = {"username": "zubair", "password": "Another-Pass-77", "confirm": "Another-Pass-77"}
    client.post("/admin/reset-password", data={**base, "setup_token": "wrong"})
    client.post("/admin/reset-password", data={**base, "setup_token": "test-setup-token",
                                               "password": "weak", "confirm": "weak"})
    assert login(client, password=PASSWORD).status_code == 302                # password unchanged


def test_reset_names_the_real_username_only_after_a_correct_token(app, client):
    make_admin(app, username="realname")
    guess = {"username": "guess", "password": "Another-Pass-77", "confirm": "Another-Pass-77"}
    right = client.post("/admin/reset-password", data={**guess, "setup_token": "test-setup-token"})
    assert b"realname" in right.data
    wrong = client.post("/admin/reset-password", data={**guess, "setup_token": "wrong-token"})
    assert b"realname" not in wrong.data


def test_reset_and_setup_are_off_when_no_token_is_configured(tmp_path):
    from app import create_app
    app = create_app("testing", overrides={"ADMIN_SETUP_TOKEN": None, "UPLOAD_FOLDER": str(tmp_path / "u")})
    client = app.test_client()
    assert client.get("/admin/reset-password").status_code == 404
    assert client.get("/admin/setup").status_code == 404
