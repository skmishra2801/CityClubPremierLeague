# ipl/blueprints/main.py
from flask import Blueprint, render_template
from cpl.models import Match, PointsTable, Team
from extensions import db

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    latest_matches = Match.query.order_by(Match.match_date.desc()).limit(6).all()

    season = db.session.query(PointsTable.season).order_by(PointsTable.season.desc()).first()
    standings = []
    if season:
        standings = PointsTable.query.filter_by(season=season[0]).order_by(PointsTable.points.desc(), PointsTable.nrr.desc()).limit(10).all()

    teams = {team.id: team for team in Team.query.all()}

    return render_template("main/home.html", matches=latest_matches, standings=standings, teams=teams)
