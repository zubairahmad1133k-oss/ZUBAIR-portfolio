"""Import every model so SQLAlchemy knows about all tables."""
from models.admin import AdminUser
from models.analytics import ContactEvent, PageEvent, ProjectView, Visitor
from models.goal import Achievement, Goal
from models.lead import Lead
from models.notification import Notification
from models.project import CodeSnippet, Project, ProjectMedia

__all__ = [
    "AdminUser", "Project", "ProjectMedia", "Visitor", "PageEvent",
    "ProjectView", "ContactEvent", "Lead", "Notification", "Goal", "Achievement", "CodeSnippet",
]
