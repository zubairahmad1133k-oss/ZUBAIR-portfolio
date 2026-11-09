"""Command-line tools:  flask --app app <command>

    init-db               create all database tables
    create-admin          create the first admin (asks for a password, never stored in files)
    reset-admin-password  set a new password for an existing admin
    seed-projects         add the starter projects (safe to run twice)
"""
import click

from extensions import db
from models import AdminUser, Project
from seed_data import INITIAL_PROJECTS
from services.seeding import seed_starter_projects
from utils import is_valid_email, password_problem


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create all database tables (safe to run again)."""
        db.create_all()
        click.echo("Database tables are ready.")

    @app.cli.command("create-admin")
    @click.option("--username", prompt="Admin username")
    @click.option("--email", prompt="Admin email")
    @click.password_option(prompt="Password (12+ characters)", confirmation_prompt=True)
    def create_admin(username, email, password):
        """Create the first admin account."""
        db.create_all()
        if db.session.scalar(db.select(AdminUser.id).limit(1)) is not None:
            raise click.ClickException(
                "An admin already exists. Use 'reset-admin-password' if you forgot the password."
            )
        username = username.strip()
        email = email.strip().lower()
        if len(username) < 3:
            raise click.ClickException("Username must be at least 3 characters.")
        if not is_valid_email(email):
            raise click.ClickException("That email address does not look valid.")
        problem = password_problem(password)
        if problem:
            raise click.ClickException(problem)

        admin = AdminUser(username=username, email=email)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin '{username}' created. Log in at /admin once the dashboard step is added.")

    @app.cli.command("reset-admin-password")
    @click.option("--username", prompt="Admin username")
    @click.password_option(prompt="New password (12+ characters)", confirmation_prompt=True)
    def reset_admin_password(username, password):
        """Set a new password (this also logs out all existing sessions)."""
        admin = db.session.scalar(db.select(AdminUser).where(AdminUser.username == username.strip()))
        if admin is None:
            raise click.ClickException("No admin with that username.")
        problem = password_problem(password)
        if problem:
            raise click.ClickException(problem)
        admin.set_password(password)
        db.session.commit()
        click.echo("Password updated.")

    @app.cli.command("seed-projects")
    def seed_projects():
        """Add the 4 starter projects if they are not already there."""
        db.create_all()
        added = seed_starter_projects()
        click.echo(f"Added {added} project(s); {len(INITIAL_PROJECTS) - added} already existed.")
