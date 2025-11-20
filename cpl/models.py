from datetime import datetime, timezone
from extensions import db


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
