from datetime import datetime, timezone
from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, Integer, String, Enum
from sqlalchemy.orm import relationship
import enum
from werkzeug.security import generate_password_hash, check_password_hash


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    short_code = db.Column(db.String(5), unique=True, nullable=False)
    city = db.Column(db.String(80))
    logo_url = db.Column(db.String(255))
    founded = db.Column(db.Integer)
    coach = db.Column(db.String(80))

    # Relationships
    players = db.relationship("Player", back_populates="team", lazy=True)
    points_rows = db.relationship("PointsTable", back_populates="team", lazy=True)
    # Matches backrefs will be created automatically from Match relationships
    balance = db.relationship("TeamBalance", back_populates="team", uselist=False)
    # one balance row per team

class TeamBalance(db.Model):
    __tablename__ = "teambalance"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), unique=True, nullable=False)
    opening = db.Column(db.Numeric(12, 2), nullable=False)
    spent = db.Column(db.Numeric(12, 2), default=0)
    remaining = db.Column(db.Numeric(12, 2), default=0)
    max_players = db.Column(db.Integer, default=0)
    players_bought = db.Column(db.Integer, default=0)

    # Relationship back to Team
    team = db.relationship("Team", back_populates="balance")

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(40))
    jersey_number = db.Column(db.Integer)
    jersey_size = db.Column(db.String(10))
    payment_status = db.Column(db.String(20))
    photo_url = db.Column(db.String(255))  # Cloudinary URL
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)

    team = db.relationship("Team", back_populates="players")




class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140))
    venue = db.Column(db.String(120))
    season = db.Column(db.Integer, nullable=False)
    match_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(40))  # Scheduled, Live, Completed, No Result
    result = db.Column(db.String(160))
    score_summary = db.Column(db.String(255))
    # points_updated = db.Column(db.Boolean, default=False)
    points_applied = db.Column(db.Boolean, default=False)
    team_a_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)
    team_b_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)
    winner_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)

    # Relationships (define here, backrefs will appear on Team automatically)
    team_a = db.relationship("Team", foreign_keys=[team_a_id], backref="matches_as_team_a")
    team_b = db.relationship("Team", foreign_keys=[team_b_id], backref="matches_as_team_b")
    winner = db.relationship("Team", foreign_keys=[winner_id], backref="matches_won")


class PointsTable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    season = db.Column(db.Integer, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)
    matches = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    ties = db.Column(db.Integer, default=0)
    nr = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)
    nrr = db.Column(db.Float, default=0.0)

    team = db.relationship("Team", back_populates="points_rows")




# Define roles as an Enum for clarity
class RoleEnum(enum.Enum):
    admin = "admin"
    editor = "editor"
    viewer = "viewer"

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.viewer, nullable=False)

    # Example: relationship to posts/images/etc.
    # posts = relationship("Post", back_populates="author")

    def set_password(self, password):
        """Hash and store password securely."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == RoleEnum.admin

    def can_edit(self):
        return self.role in [RoleEnum.admin, RoleEnum.editor]

    def can_view(self):
        return True  # all roles can view




class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)
