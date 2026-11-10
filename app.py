"""Zubair OS — application factory.

Run locally:      flask --app app run
Production start: gunicorn "app:create_app()"
"""
import logging
import os
import secrets

from flask import Flask, g, render_template, request
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from config import get_config
from extensions import csrf, db, limiter, login_manager, migrate


def create_app(config_name: str | None = None, overrides: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    if overrides:
        app.config.update(overrides)  # used by the automated tests

    # ---- secret key: required in production, auto-generated for local dev ----
    if not app.config.get("SECRET_KEY"):
        if config_class.ENV_NAME == "production":
            raise RuntimeError(
                "SECRET_KEY is not set. Generate one with: "
                "python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        app.logger.warning(
            "SECRET_KEY not set: using a temporary key (logins reset on restart). "
            "Put a permanent one in your .env file."
        )

    # ---- folders ----
    upload_root = app.config["UPLOAD_FOLDER"]
    for folder in (upload_root, os.path.join(upload_root, "public"),
                   os.path.join(upload_root, "private"), os.path.join(app.root_path, "instance")):
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:  # read-only hosts (e.g. Vercel): the site still runs, uploads are off
            app.logger.warning("Could not create folder %s", folder)

    # Behind Render's proxy: trust one hop so client IPs / https are correct.
    if config_class.ENV_NAME == "production":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # ---- extensions ----
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)

    import models  # noqa: F401  (registers all tables)

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            raw_id, _, raw_version = user_id.partition(":")
            uid, version = int(raw_id), int(raw_version)
        except ValueError:
            return None
        user = db.session.get(models.AdminUser, uid)
        if user is not None and user.session_version == version:
            return user
        return None

    # Create any missing tables (never touches existing data), so new features
    # that add tables work without extra commands.
    with app.app_context():
        try:
            db.create_all()
        except Exception:  # noqa: BLE001 - the site can still start; /health will report the problem
            app.logger.exception("Could not create/check database tables")

    # ---- blueprints ----
    from routes.analyst import bp as analyst_bp
    from routes.analytics import bp as analytics_bp
    from routes.api import bp as api_bp
    from routes.authentication import bp as auth_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.goals import bp as goals_bp
    from routes.leads import bp as leads_bp
    from routes.media import bp as media_bp
    from routes.projects import bp as projects_bp
    from routes.public import bp as public_bp
    from routes.snippets import bp as snippets_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(snippets_bp)
    app.register_blueprint(leads_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(analyst_bp)
    app.register_blueprint(api_bp)

    # ---- CLI ----
    from cli import register_cli

    register_cli(app)

    # ---- template context ----
    @app.context_processor
    def inject_site():
        def unread_notifications() -> int:
            return db.session.scalar(
                db.select(db.func.count(models.Notification.id)).where(
                    models.Notification.is_read.is_(False)
                )
            ) or 0

        def new_enquiries() -> int:
            return db.session.scalar(
                db.select(db.func.count(models.Lead.id)).where(models.Lead.status == "new")
            ) or 0

        return {
            "site": app.config["SITE"],
            "unread_notifications": unread_notifications,
            "new_enquiries": new_enquiries,
            "uploads_enabled": app.config["UPLOADS_ENABLED"],
        }

    # ---- security headers ----
    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        )
        visitor_cookie = g.pop("visitor_cookie", None)
        if visitor_cookie:
            from services.tracking import COOKIE_MAX_AGE, COOKIE_NAME

            response.set_cookie(
                COOKIE_NAME, visitor_cookie, max_age=COOKIE_MAX_AGE, httponly=True,
                samesite="Lax", secure=config_class.ENV_NAME == "production",
            )
        if request.path.startswith("/admin"):
            # Private pages: never cached, never indexed.
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        if config_class.ENV_NAME == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    # ---- friendly, production-safe error pages ----
    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if error.code == 500:
            db.session.rollback()
        return (
            render_template(
                "errors/error.html", code=error.code, title=error.name,
                message=error.description,
            ),
            error.code,
        )

    if not app.debug and not app.testing:
        logging.basicConfig(level=logging.INFO)

    return app
