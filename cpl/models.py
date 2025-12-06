from datetime import datetime, timezone
from extensions import db
from flask_login import UserMixin
from sqlalchemy import Column, Integer, String, Enum, Numeric, Float, DateTime
import enum
from werkzeug.security import generate_password_hash, check_password_hash


# =====================================================
# SEASON MODEL
# =====================================================
class Season(db.Model):
    __tablename__ = "season"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, unique=True, nullable=False)

    auctions = db.relationship("Auction", back_populates="season", cascade="all, delete-orphan", lazy=True)
    player_seasons = db.relationship("PlayerSeason", back_populates="season", cascade="all, delete-orphan", lazy=True)
    points_rows = db.relationship("PointsTable", back_populates="season", cascade="all, delete-orphan", lazy=True)
    matches = db.relationship("Match", back_populates="season", cascade="all, delete-orphan", lazy=True)
    team_balances = db.relationship("TeamBalance", back_populates="season", cascade="all, delete-orphan", lazy=True)
    def __repr__(self):
        return f"<Season {self.year}>"


# =====================================================
# TEAM MODEL
# =====================================================
class Team(db.Model):
    __tablename__ = "team"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    short_code = db.Column(db.String(5), unique=True, nullable=False)
    city = db.Column(db.String(80))
    team_picture_url = db.Column(db.String(500))
    founded = db.Column(db.Integer)
    coach = db.Column(db.String(80))

    # Reciprocal relationships
    matches_as_team_a = db.relationship("Match", foreign_keys="Match.team_a_id", back_populates="team_a")
    matches_as_team_b = db.relationship("Match", foreign_keys="Match.team_b_id", back_populates="team_b")
    matches_won = db.relationship("Match", foreign_keys="Match.winner_id", back_populates="winner")

    players = db.relationship("Player", back_populates="team", lazy=True)
    player_seasons = db.relationship("PlayerSeason", back_populates="team", lazy=True)
    points_rows = db.relationship("PointsTable", back_populates="team", cascade="all, delete-orphan", lazy=True)
    balance = db.relationship("TeamBalance", back_populates="team", uselist=False)
    auction_purchases = db.relationship("AuctionPlayer", back_populates="sold_to_team", lazy=True)



# =====================================================
# TEAM BALANCE (like IPL purse)
# =====================================================
class TeamBalance(db.Model):
    __tablename__ = "teambalance"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), unique=True, nullable=False)
    season_id = db.Column(db.Integer, db.ForeignKey("season.id"), nullable=False)

    opening = db.Column(Numeric(12, 2), nullable=False)
    spent = db.Column(Numeric(12, 2), default=0)
    remaining = db.Column(Numeric(12, 2), default=0)
    max_players = db.Column(db.Integer, default=0)
    players_bought = db.Column(db.Integer, default=0)

    team = db.relationship("Team", back_populates="balance")
    season = db.relationship("Season", back_populates="team_balances")

# =====================================================
# PLAYER MODEL
# =====================================================
class Player(db.Model):
    __tablename__ = "player"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(40))
    jersey_number = db.Column(db.Integer)
    jersey_size = db.Column(db.String(10))
    payment_status = db.Column(db.String(20))
    photo_url = db.Column(db.String(255))

    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)
    team = db.relationship("Team", back_populates="players")

    seasons = db.relationship("PlayerSeason", back_populates="player", cascade="all, delete-orphan", lazy=True)
    auction_entries = db.relationship("AuctionPlayer", back_populates="player", cascade="all, delete-orphan", lazy=True)


# =====================================================
# PLAYER SEASON STATS
# =====================================================
class PlayerSeason(db.Model):
    __tablename__ = "player_season"

    id = db.Column(db.Integer, primary_key=True)

    season_id = db.Column(db.Integer, db.ForeignKey("season.id"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)

    sold_price = db.Column(db.Numeric(10, 2), nullable=True)

    matches_played = db.Column(db.Integer, default=0)
    runs_scored = db.Column(db.Integer, default=0)
    batting_average = db.Column(db.Float, default=0.0)
    overs_bowled = db.Column(db.Float, default=0.0)
    wickets_taken = db.Column(db.Integer, default=0)
    bowling_average = db.Column(db.Float, default=0.0)

    season = db.relationship("Season", back_populates="player_seasons")
    player = db.relationship("Player", back_populates="seasons")
    team = db.relationship("Team", back_populates="player_seasons")


class Match(db.Model):
    __tablename__ = "match"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140))
    venue = db.Column(db.String(120))

    season_id = db.Column(db.Integer, db.ForeignKey("season.id"), nullable=False)
    season = db.relationship("Season", back_populates="matches")

    match_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(40))

    toss_winner = db.Column(db.String(200), nullable=True)
    toss_decision = db.Column(db.String(20), nullable=True)

    # First innings summary
    first_innings_score = db.Column(db.Integer, default=0)
    first_innings_wickets = db.Column(db.Integer, default=0)
    first_innings_balls = db.Column(db.Integer, default=0)
    first_innings_run_rate = db.Column(db.Float, default=0.0)

    # Second innings summary
    second_innings_score = db.Column(db.Integer, default=0)
    second_innings_wickets = db.Column(db.Integer, default=0)
    second_innings_balls = db.Column(db.Integer, default=0)
    second_innings_run_rate = db.Column(db.Float, default=0.0)

    # Teams
    team_a_id = db.Column(db.Integer, db.ForeignKey("team.id"))
    team_b_id = db.Column(db.Integer, db.ForeignKey("team.id"))
    winner_id = db.Column(db.Integer, db.ForeignKey("team.id"))

    team_a = db.relationship("Team", foreign_keys=[team_a_id], back_populates="matches_as_team_a")
    team_b = db.relationship("Team", foreign_keys=[team_b_id], back_populates="matches_as_team_b")
    winner = db.relationship("Team", foreign_keys=[winner_id], back_populates="matches_won")

    # Overs limits per innings
    overs_limit_innings1 = db.Column(db.Integer, nullable=True)
    overs_limit_innings2 = db.Column(db.Integer, nullable=True)

    points = db.Column(db.Integer, default=0)

    # Live state tracking
    current_innings_no = db.Column(db.Integer, default=1)  # 1 or 2
    current_on_strike_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=True)
    current_non_strike_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=True)
    current_bowler_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=True)

    # --- Helper methods ---
    @staticmethod
    def format_overs(balls: int) -> str:
        """
        Convert balls into cricket overs notation (e.g. 34 balls -> "5.4").
        """
        if balls is None or balls < 0:
            return "0.0"
        return f"{balls // 6}.{balls % 6}"

    @property
    def first_innings_overs(self) -> str:
        return self.format_overs(self.first_innings_balls)

    @property
    def second_innings_overs(self) -> str:
        return self.format_overs(self.second_innings_balls)
class MatchScore(db.Model):
    __tablename__ = "match_score"

    id = db.Column(db.Integer, primary_key=True)

    # Foreign keys
    match_id = db.Column(db.Integer, db.ForeignKey("match.id"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)   # ✅ fixed

    # Batting stats
    runs_scored = db.Column(db.Integer, default=0)   # ✅ rename from batting_runs for clarity
    batting_runs = db.Column(db.Integer, default=0)
    balls_faced = db.Column(db.Integer, default=0)
    fours = db.Column(db.Integer, default=0)
    sixes = db.Column(db.Integer, default=0)
    dismissal_desc = db.Column(db.String(200), nullable=True)
    is_out = db.Column(db.Boolean, default=False)

    # Bowling stats
    overs_bowled = db.Column(db.Integer, default=0)
    # overs_bowled = db.Column(db.Float, default=0.0)
    runs_conceded = db.Column(db.Integer, default=0)
    wickets_taken = db.Column(db.Integer, default=0)

    # Inning context
    innings_no = db.Column(db.Integer, default=1)

    # Relationships
    match = db.relationship("Match", backref="scores", lazy=True)
    player = db.relationship("Player", backref="match_scores", lazy=True)
    team = db.relationship("Team", backref="match_scores", lazy=True)

    def strike_rate(self):
        if self.balls_faced and self.balls_faced > 0:
            return round((self.runs_scored / self.balls_faced) * 100, 2)
        return 0.0

    def economy_rate(self):
        if self.overs_bowled and self.overs_bowled > 0:
            return round(self.runs_conceded / self.overs_bowled, 2)
        return 0.0

        # ✅ Computed property
    @property
    def computed_runs_scored(self):
        return (self.batting_runs or 0) + (self.fours or 0) * 4 + (self.sixes or 0) * 6

    @property
    def overs_notation(self):
        """Return overs in cricket notation (e.g., 2.3 means 2 overs + 3 balls)."""
        completed_overs = self.overs_bowled // 6
        remaining_balls = self.overs_bowled % 6
        return f"{completed_overs}.{remaining_balls}"



# =====================================================
# POINTS TABLE
# =====================================================
class PointsTable(db.Model):
    __tablename__ = "points_table"

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("season.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)

    matches = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    ties = db.Column(db.Integer, default=0)
    nr = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)
    nrr = db.Column(db.Float, default=0.0)
    total_runs_scored = db.Column(db.Integer, default=0)
    total_overs_faced = db.Column(db.Float, default=0.0)
    total_runs_conceded = db.Column(db.Integer, default=0)
    total_overs_bowled = db.Column(db.Float, default=0.0)

    team = db.relationship("Team", back_populates="points_rows")
    season = db.relationship("Season", back_populates="points_rows")


# =====================================================
# AUCTION MODELS
# =====================================================
class Auction(db.Model):
    __tablename__ = "auction"

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("season.id"), nullable=False)

    title = db.Column(db.String(120), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    season = db.relationship("Season", back_populates="auctions")
    players = db.relationship("AuctionPlayer", back_populates="auction", cascade="all, delete-orphan", lazy=True)


class AuctionPlayer(db.Model):
    __tablename__ = "auction_player"

    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(db.Integer, db.ForeignKey("auction.id"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)

    base_price = db.Column(Numeric(12, 2), default=0)
    sold_price = db.Column(Numeric(12, 2))
    sold_to_team_id = db.Column(db.Integer, db.ForeignKey("team.id"))
    status = db.Column(db.String(20), default="unsold")

    auction = db.relationship("Auction", back_populates="players")
    player = db.relationship("Player", back_populates="auction_entries")
    sold_to_team = db.relationship("Team", back_populates="auction_purchases")

    bids = db.relationship("AuctionBid", back_populates="auction_player", cascade="all, delete-orphan", lazy=True)


class AuctionBid(db.Model):
    __tablename__ = "auction_bid"

    id = db.Column(db.Integer, primary_key=True)
    auction_player_id = db.Column(db.Integer, db.ForeignKey("auction_player.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=False)

    bid_amount = db.Column(Numeric(12, 2), nullable=False)
    timestamp = db.Column(DateTime, default=datetime.utcnow)

    auction_player = db.relationship("AuctionPlayer", back_populates="bids")
    team = db.relationship("Team")


# =====================================================
# USER MODEL
# =====================================================
class RoleEnum(enum.Enum):
    admin = "admin"
    editor = "editor"
    viewer = "viewer"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.viewer, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == RoleEnum.admin

    def can_edit(self):
        return self.role in [RoleEnum.admin, RoleEnum.editor]

    def can_view(self):
        return True


# models.py (add this model)
class BallEvent(db.Model):
    __tablename__ = "ball_event"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("match.id"), nullable=False)
    innings_no = db.Column(db.Integer, default=1, nullable=False)
    over_no = db.Column(db.Integer, nullable=False)
    ball_no = db.Column(db.Integer, nullable=False)   # 1..6 (or >6 for free-hit/extra delivered balls if you track)
    striker_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=True)
    non_striker_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=True)
    bowler_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=True)
    toss_winner = db.Column(db.String(200), nullable=True)
    toss_decision = db.Column(db.String(20), nullable=True)
    current_innings_no = db.Column(db.Integer, default=1)
    current_on_strike_id = db.Column(db.Integer, nullable=True)
    current_non_strike_id = db.Column(db.Integer, nullable=True)
    current_bowler_id = db.Column(db.Integer, nullable=True)
    overs_limit_innings1 = db.Column(db.Integer, nullable=True)
    overs_limit_innings2 = db.Column(db.Integer, nullable=True)
    score_summary = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    runs = db.Column(db.Integer, default=0)           # runs off the bat
    extras = db.Column(db.String(50), nullable=True)  # 'wd','nb','b','lb' or json-like "wd:1" (simple)
    extras_runs = db.Column(db.Integer, default=0)    # total extras on this delivery (0 if none)
    is_wicket = db.Column(db.Boolean, default=False)
    dismissal_desc = db.Column(db.String(120), nullable=True)

    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    match = db.relationship("Match", backref="ball_events", lazy=True)
    striker = db.relationship("Player", foreign_keys=[striker_id])
    non_striker = db.relationship("Player", foreign_keys=[non_striker_id])
    bowler = db.relationship("Player", foreign_keys=[bowler_id])

    def total_runs(self):
        return (self.runs or 0) + (self.extras_runs or 0)


# Add near MatchScore in models.py

import json
from sqlalchemy import Text

class MatchBall(db.Model):
    __tablename__ = "match_ball"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("match.id"), nullable=False)
    innings_no = db.Column(db.Integer, default=1, nullable=False)

    # Over / ball bookkeeping (optional but helpful)
    over_num = db.Column(db.Integer, nullable=False, default=0)      # 0-based over index
    ball_in_over = db.Column(db.Integer, nullable=False, default=1)  # 1..6 (for legal ball), can increase for extras if required

    # Who bowled and who faced (store names and IDs for robustness)
    bowler_player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=True)
    batsman_player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=True)

    # Ball-level values
    runs_bat = db.Column(db.Integer, default=0)     # runs off the bat
    extras_json = db.Column(Text, default="{}")     # a JSON dict like {"wd":1,"nb":0,"lb":0,"b":0}
    total_runs = db.Column(db.Integer, default=0)   # runs_bat + sum(extras)
    wicket = db.Column(db.Boolean, default=False)
    dismissal_desc = db.Column(db.String(200), nullable=True)

    # timestamp (optional)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # relationships (optional convenience)
    match = db.relationship("Match", backref="balls")
    batsman = db.relationship("Player", foreign_keys=[batsman_player_id])
    bowler = db.relationship("Player", foreign_keys=[bowler_player_id])

    def extras(self):
        try:
            return json.loads(self.extras_json or "{}")
        except Exception:
            return {}


