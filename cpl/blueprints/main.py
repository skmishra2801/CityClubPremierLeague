# ipl/blueprints/main.py
from decimal import Decimal

from flask import Blueprint, render_template
from cpl.models import Match, PointsTable, Team, TeamBalance, Player
from extensions import db

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    latest_matches = Match.query.order_by(Match.match_date.desc()).limit(6).all()

    season = db.session.query(PointsTable.season).order_by(PointsTable.season.desc()).first()
    teams = {team.id: team for team in Team.query.all()}
    standings = []
    leaderboard = []
    if season:
        standings = PointsTable.query.filter_by(season=season[0]).order_by(PointsTable.points.desc(),
                                                                           PointsTable.nrr.desc()).limit(10).all()
        # Build leaderboard with recent form from Match table
        pos = 1
        for row in standings:
            team_id = row.team_id  # assuming PointsTable has team_id
            team_name = teams[row.team_id].name if row.team_id in teams else "Unknown"


            # Get all matches involving this team, ordered by date ascending
            matches = Match.query.filter(
                (Match.team_a_id == team_id) | (Match.team_b_id == team_id)
            ).order_by(Match.match_date.asc()).all()

            # Map to W/L
            recent_results = []
            for m in matches:
                if m.winner_id == team_id:
                    recent_results.append("W")
                else:
                    recent_results.append("L")

            # Join into a string (last 5 results for example)
            recent_form = " ".join(recent_results[-5:])  # last 5 matches

            leaderboard.append({
                "POS": pos,
                "team": team_name,
                "P": row.matches,
                "W": row.wins,
                "L": row.losses,
                "PTS": row.points,
                "recent_form": recent_form
            })
            pos += 1


    # Build team_summary list
    team_summary = []
    for team in teams.values():
        balance = TeamBalance.query.filter_by(team_id=team.id).first()
        players_count = Player.query.filter_by(team_id=team.id).count()

        opening = balance.opening if balance else Decimal("0")
        spent = balance.spent if balance else Decimal("0")
        remaining = balance.remaining if balance else (opening - spent)

        max_players = balance.max_players or 0
        players_bought = balance.players_bought or 0
        players_left = max_players - players_bought

        # ✅ Risk metric: remaining / players_left
        calculate = None
        if players_left > 0 and remaining > 0:
            calculate = remaining / Decimal(players_left)

        team_summary.append({
            "team": team.name,
            "openingbalance": balance.opening if balance else 0,
            "spentamount": balance.spent if balance else 0,
            "balance": balance.remaining if balance else 0,
            "players": players_count,
            "maxplayers":max_players,
            "calculate": calculate
        })



    return render_template("main/home.html", matches=latest_matches, standings=standings, teams=teams, team_summary=team_summary, leaderboard=leaderboard)
