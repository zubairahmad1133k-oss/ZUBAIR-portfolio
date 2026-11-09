from extensions import db
from models.base import utcnow


class Goal(db.Model):
    __tablename__ = "goals"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    target_date = db.Column(db.Date)
    progress = db.Column(db.Integer, nullable=False, default=0)  # 0-100, set by you
    is_completed = db.Column(db.Boolean, nullable=False, default=False, index=True)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    achievements = db.relationship("Achievement", back_populates="goal")


class Achievement(db.Model):
    __tablename__ = "achievements"

    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey("goals.id", ondelete="SET NULL"))
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    achieved_on = db.Column(db.Date)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    goal = db.relationship("Goal", back_populates="achievements")
