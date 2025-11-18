from flask import Blueprint, render_template, request
from cpl.models import PointsTable, Match
from cpl.services.points import rebuild_points_table
from extensions import db

bp = Blueprint("stats", __name__, url_prefix="/stats")


@bp.route("/points-table")
def points_table():
    selected_season = request.args.get("season")

    # Get all completed matches for the selected season (or all if none selected)
    match_query = Match.query.filter(Match.status == "Completed")
    if selected_season:
        match_query = match_query.filter(Match.season == int(selected_season))

    completed_matches = match_query.all()

    # Update points table for each completed match
    for match in completed_matches:
        rebuild_points_table(match.season)

    # --- Step 2: Query PointsTable for display ---
    query = PointsTable.query
    if selected_season:
        query = query.filter(PointsTable.season == int(selected_season))

    standings = query.order_by(PointsTable.points.desc(), PointsTable.nrr.desc()).all()

    # --- Step 3: Distinct seasons for dropdown ---
    seasons = [s[0] for s in db.session.query(PointsTable.season).distinct().all()]

    return render_template(
        "stats/points_table.html",
        standings=standings,
        seasons=seasons,
        selected_season=selected_season
    )
