from flask import Blueprint, render_template, request
from cpl.models import PointsTable, Match, Season, Team
from cpl.services.points import rebuild_points_table
from extensions import db

bp = Blueprint("stats", __name__, url_prefix="/stats")


@bp.route("/points-table")
def points_table():
    # -------------------------
    # SEASON SELECTION
    # -------------------------
    selected_year = request.args.get("year", type=int)
    seasons = Season.query.order_by(Season.year.desc()).all()
    years = [s.year for s in seasons]

    # Default year = latest season
    if not selected_year and seasons:
        selected_year = seasons[0].year

    # Find the season object that matches the selected_year
    selected_season = next((s for s in seasons if s.year == selected_year), None)
    selected_season_id = selected_season.id if selected_season else None

    # -------------------------
    # FETCH COMPLETED MATCHES
    # -------------------------
    match_query = Match.query.filter(Match.status.isnot(None))
    if selected_season_id:
        match_query = match_query.filter(Match.season_id == selected_season_id)

    completed_matches = match_query.order_by(Match.match_date.asc()).all()

    # -------------------------
    # BUILD POINTS TABLE FROM MATCHES
    # -------------------------
    teams_dict = {t.id: t for t in Team.query.all()}
    leaderboard = {
        tid: {
            "team": teams_dict[tid].name if tid in teams_dict else f"Team {tid}",
            "P": 0,
            "W": 0,
            "L": 0,
            "T": 0,
            "PTS": 0,
            "runs_scored": 0,
            "balls_faced": 0,
            "runs_conceded": 0,
            "balls_bowled": 0,
            "recent_results": []
        }
        for tid in teams_dict.keys()
    }

    for m in completed_matches:
        if not m.toss_winner:
            continue

        team1, team2 = m.team_a_id, m.team_b_id
        if not team1 or not team2:
            continue

        # Played
        leaderboard[team1]["P"] += 1
        leaderboard[team2]["P"] += 1

        # Runs/balls for NRR
        leaderboard[team1]["runs_scored"] += (m.first_innings_score or 0)
        leaderboard[team1]["balls_faced"] += (m.first_innings_balls or 0)
        leaderboard[team1]["runs_conceded"] += (m.second_innings_score or 0)
        leaderboard[team1]["balls_bowled"] += (m.second_innings_balls or 0)

        leaderboard[team2]["runs_scored"] += (m.second_innings_score or 0)
        leaderboard[team2]["balls_faced"] += (m.second_innings_balls or 0)
        leaderboard[team2]["runs_conceded"] += (m.first_innings_score or 0)
        leaderboard[team2]["balls_bowled"] += (m.first_innings_balls or 0)

        # Outcome
        if m.winner_id is None:
            leaderboard[team1]["T"] += 1
            leaderboard[team2]["T"] += 1
            leaderboard[team1]["PTS"] += 1
            leaderboard[team2]["PTS"] += 1
            leaderboard[team1]["recent_results"].append("T")
            leaderboard[team2]["recent_results"].append("T")
        else:
            winner = m.winner_id
            loser = team1 if winner == team2 else team2
            leaderboard[winner]["W"] += 1
            leaderboard[winner]["PTS"] += 2
            leaderboard[winner]["recent_results"].append("W")
            leaderboard[loser]["L"] += 1
            leaderboard[loser]["recent_results"].append("L")

    # -------------------------
    # FINAL STANDINGS LIST
    # -------------------------
    final_board = []
    sorted_rows = sorted(
        leaderboard.items(),
        key=lambda x: (-x[1]["PTS"], -x[1]["W"], x[1]["team"])
    )

    for idx, (tid, row) in enumerate(sorted_rows, start=1):
        overs_faced = (row["balls_faced"] / 6.0) if row["balls_faced"] else 0.0
        overs_bowled = (row["balls_bowled"] / 6.0) if row["balls_bowled"] else 0.0
        nrr = 0.0
        if overs_faced > 0 and overs_bowled > 0:
            nrr = (row["runs_scored"] / overs_faced) - (row["runs_conceded"] / overs_bowled)

        recent_form_str = " ".join(row["recent_results"][-5:])

        final_board.append({
            "POS": idx,
            "team": row["team"],
            "P": row["P"],
            "W": row["W"],
            "L": row["L"],
            "T": row["T"],
            "PTS": row["PTS"],
            "NRR": round(nrr, 2),
            "recent_form": recent_form_str
        })

    # -------------------------
    # DISTINCT SEASONS FOR DROPDOWN
    # -------------------------
    season_ids = [s[0] for s in db.session.query(Match.season_id).distinct().all()]

    return render_template(
        "stats/points_table.html",
        standings=final_board,
        seasons=season_ids,
        selected_season=selected_season_id,
        selected_year=selected_year,
        years = years,
        active_tab="points"
    )

