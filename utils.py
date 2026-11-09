"""Small helpers shared across the app."""
import re
from urllib.parse import urlparse

from sqlalchemy import select

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 12


def slugify(text: str) -> str:
    """'Code Checker!' -> 'code-checker'. Falls back to 'project'."""
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "project"


def unique_slug(session, model, title: str, exclude_id: int | None = None) -> str:
    """Return a slug for `title` that no other row of `model` uses."""
    base = slugify(title)
    candidate, n = base, 2
    while True:
        existing_id = session.scalar(select(model.id).where(model.slug == candidate))
        if existing_id is None or existing_id == exclude_id:
            return candidate
        candidate = f"{base}-{n}"
        n += 1


def is_valid_email(value: str) -> bool:
    return bool(value) and len(value) <= 255 and bool(_EMAIL_RE.match(value))


def password_problem(password: str) -> str | None:
    """Return a human-readable problem with the password, or None if it's OK."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
    if password.lower() == password or password.upper() == password:
        return "Use a mix of upper- and lower-case letters."
    if not any(ch.isdigit() for ch in password):
        return "Include at least one number."
    return None


def clean_http_url(value: str | None) -> str | None:
    """Return a tidy http(s) URL, None if blank, or raise ValueError."""
    value = (value or "").strip()
    if not value:
        return None
    if len(value) > 500:
        raise ValueError("A link is too long (500 characters max).")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Links must start with http:// or https://")
    return value


def is_safe_next(target: str) -> bool:
    """Only allow redirects to paths on this same site."""
    return bool(target) and target.startswith("/") and not target.startswith("//") and "\\" not in target
