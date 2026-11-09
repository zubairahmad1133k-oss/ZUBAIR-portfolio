from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models.base import utcnow


class AdminUser(UserMixin, db.Model):
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    # Bumped on password change so every older login session stops working.
    session_version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)
        self.session_version = (self.session_version or 0) + 1

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str:  # used by Flask-Login to store the session
        return f"{self.id}:{self.session_version}"

    def __repr__(self) -> str:
        return f"<AdminUser {self.username}>"
