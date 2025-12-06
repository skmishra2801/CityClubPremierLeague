from decimal import Decimal
from flask import Blueprint, render_template, session, request

from cpl.blueprints import teams
from cpl.models import Match, Team, TeamBalance, Season, PlayerSeason
from extensions import db

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
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
    # TEAMS FOR SELECTED SEASON
    # -------------------------
    allteams = []
    if selected_season_id:
        team_ids = (
            db.session.query(PlayerSeason.team_id)
            .filter(PlayerSeason.season_id == selected_season_id,
                    PlayerSeason.team_id.isnot(None))
            .distinct()
            .all()
        )
        team_ids = [tid[0] for tid in team_ids]  # flatten list of tuples
        allteams = Team.query.filter(Team.id.in_(team_ids)).all()

    # Build a dict of all teams for quick lookup and purse section
    teams_dict = {t.id: t for t in Team.query.all()}
    # -------------------------
    # LATEST MATCHES
    # -------------------------
    latest_matches = (
        Match.query
        .filter_by(season_id=selected_season_id)  # restrict to chosen season
        .order_by(Match.match_date.desc())
        .limit(10)
        .all()
    )
    # -------------------------
    # LEADERBOARD (always use selected season, not hardcoded latest)
    # -------------------------
    final_board = []
    if selected_season_id:
        # Fetch all matches for the season
        matches = (
            Match.query
            .filter_by(season_id=selected_season_id)
            .order_by(Match.match_date.asc())
            .all()
        )

        # Initialize leaderboard rows for only the teams that appear in matches
        team_ids_in_matches = set()
        for m in matches:
            if m.team_a_id:
                team_ids_in_matches.add(m.team_a_id)
            if m.team_b_id:
                team_ids_in_matches.add(m.team_b_id)

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
            for tid in team_ids_in_matches
        }

        # Process each match
        for m in matches:
            # Only count matches where toss_winner is set (considered played)
            if not m.toss_winner:
                continue

            team1, team2 = m.team_a_id, m.team_b_id
            if not team1 or not team2:
                continue  # skip malformed rows

            # Both teams played
            leaderboard[team1]["P"] += 1
            leaderboard[team2]["P"] += 1

            # Runs/balls for NRR
            # Team A is first innings by your model fields; Team B is second innings
            leaderboard[team1]["runs_scored"] += (m.first_innings_score or 0)
            leaderboard[team1]["balls_faced"] += (m.first_innings_balls or 0)
            leaderboard[team1]["runs_conceded"] += (m.second_innings_score or 0)
            leaderboard[team1]["balls_bowled"] += (m.second_innings_balls or 0)

            leaderboard[team2]["runs_scored"] += (m.second_innings_score or 0)
            leaderboard[team2]["balls_faced"] += (m.second_innings_balls or 0)
            leaderboard[team2]["runs_conceded"] += (m.first_innings_score or 0)
            leaderboard[team2]["balls_bowled"] += (m.first_innings_balls or 0)

            # Outcome: winner_id None → tie; otherwise assign W/L
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

                # Safety: ensure winner/loser are in leaderboard
                if winner in leaderboard:
                    leaderboard[winner]["W"] += 1
                    leaderboard[winner]["PTS"] += 2
                    leaderboard[winner]["recent_results"].append("W")
                if loser in leaderboard:
                    leaderboard[loser]["L"] += 1
                    leaderboard[loser]["recent_results"].append("L")

        # Build final board with NRR, POS, last-5 recent form
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
    # TEAM SUMMARY / PURSE
    # -------------------------
    team_summary = []
    for team in teams_dict.values():
        balance = TeamBalance.query.filter_by(team_id=team.id, season_id=selected_season_id).first()

        if balance:
            opening = Decimal(balance.opening or 0)
            spent = Decimal(balance.spent or 0)
            # Only fall back if remaining is None, not if it's 0
            if balance.remaining is not None:
                remaining = Decimal(balance.remaining)
            else:
                remaining = opening - spent
            max_players = balance.max_players or 0
            players_bought = balance.players_bought or 0
            players_left = max_players - players_bought
        else:
            opening = spent = remaining = Decimal("0")
            max_players = players_bought = players_left = 0

        calculate = None
        if players_left > 0 and remaining > 0:
            calculate = remaining / Decimal(players_left)

        team_summary.append({
            "team": team.name,
            "openingbalance": opening,
            "spentamount": spent,
            "balance": remaining,
            "maxplayers": max_players,
            "players_bought": players_bought,
            "players_left": players_left,
            "calculate": calculate,
        })

    # -------------------------
    # RENDER TEMPLATE
    # -------------------------
    return render_template(
        "main/home.html",
        matches=latest_matches,
        teams=teams_dict,
        team_summary=team_summary,
        leaderboard=final_board,
        seasons=seasons,
        years=years,
        selected_season=selected_season,
        is_admin=session.get("is_admin"),
        allteams=allteams
    )
