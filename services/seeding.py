"""Adds the four starter projects (safe to run more than once)."""
from extensions import db
from models import Project
from seed_data import INITIAL_PROJECTS


def seed_starter_projects() -> int:
    """Insert any starter project that is missing. Returns how many were added."""
    added = 0
    for data in INITIAL_PROJECTS:
        if db.session.scalar(db.select(Project.id).where(Project.slug == data["slug"])) is not None:
            continue
        db.session.add(Project(description=data["summary"], is_published=True, **data))
        added += 1
    db.session.commit()
    return added
