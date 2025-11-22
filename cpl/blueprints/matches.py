from flask import Blueprint, render_template, request, flash, redirect, url_for

from cpl.blueprints.admin import admin_required
from cpl.models import Match, Team, PointsTable
from datetime import datetime

from cpl.services.points import rebuild_points_table
from extensions import db
bp = Blueprint("matches", __name__)


@bp.route("/")
def fixtures():
    upcoming_matches = Match.query.filter(Match.status.in_(["Scheduled", "Live"])) \
                                  .order_by(Match.match_date.asc()).all()
    completed_matches = Match.query.filter_by(status="Completed") \
                                   .order_by(Match.match_date.desc()).all()

    # Build a dict of teams keyed by ID
    teams = {t.id: t for t in Team.query.all()}

    return render_template("matches/fixtures.html",
                           upcoming_matches=upcoming_matches,
                           completed_matches=completed_matches,
                           teams=teams)


@bp.route("/results")
def results():
    page = request.args.get("page", 1, type=int)
    per_page = 10

    selected_season = request.args.get("season")
    selected_team = request.args.get("team")
    selected_venue = request.args.get("venue")

    query = Match.query.filter(Match.status == "Completed")

    if selected_season:
        query = query.filter(Match.season == selected_season)

    if selected_team:
        team_obj = Team.query.filter_by(short_code=selected_team).first()
        if team_obj:
            query = query.filter(
                (Match.team_a_id == team_obj.id) | (Match.team_b_id == team_obj.id)
            )

    if selected_venue:
        query = query.filter(Match.venue.ilike(f"%{selected_venue}%"))

    pagination = query.order_by(Match.match_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    matches = pagination.items

    seasons = [s[0] for s in db.session.query(PointsTable.season).distinct().all()]
    teams = Team.query.all()
    teams_dict = {t.id: t for t in teams}

    return render_template(
        "matches/results.html",
        matches=matches,
        pagination=pagination,
        seasons=seasons,
        teams=teams,
        teams_dict=teams_dict,
        selected_season=selected_season,
        selected_team=selected_team,
        selected_venue=selected_venue,
    )


@bp.route("/<int:match_id>")
def detail(match_id):
    match = Match.query.get_or_404(match_id)
    teams = {team.id: team for team in Team.query.all()}  # 👈 dictionary with team IDs as keys
    return render_template("matches/detail.html", match=match, teams=teams)


# Create fixture form
@bp.route("/create", methods=["GET", "POST"])
@admin_required
def create_fixture():
    if request.method == "POST":
        team_a_id = request.form["team_a"]
        team_b_id = request.form["team_b"]
        venue = request.form["venue"]
        match_date = datetime.strptime(request.form["match_date"], "%Y-%m-%dT%H:%M")
        season = datetime.strptime(request.form["season"], "%Y-%m").year

        new_match = Match(
            title=f"{Team.query.get(team_a_id).short_code} vs {Team.query.get(team_b_id).short_code}",
            venue=venue,
            match_date=match_date,
            team_a_id=team_a_id,
            team_b_id=team_b_id,
            status="Scheduled",
            season=season
        )
        db.session.add(new_match)
        db.session.commit()
        flash("Fixture created successfully!", "success")
        return redirect(url_for("matches.fixtures"))
    teams = Team.query.order_by(Team.name.asc()).all()
    return render_template("matches/create_fixture.html", teams=teams)


@bp.route("/complete/<int:match_id>", methods=["POST"])
@admin_required
def complete_match(match_id):
    match = Match.query.get_or_404(match_id)
    winner_team_id = request.form.get("winner_team_id")
    score_summary = request.form.get("score_summary")

    if winner_team_id == "tie":
        match.winner_id = None
        match.result = "Match tied"

    elif winner_team_id == "nr":
        match.winner_id = None
        match.result = "No Result"

    elif winner_team_id:
        winner_team_id = int(winner_team_id)
        winner = Team.query.get(winner_team_id)
        loser_id = match.team_a_id if winner_team_id == match.team_b_id else match.team_b_id
        loser = Team.query.get(loser_id)

        # ✅ Always set winner_id
        match.winner_id = winner_team_id
        match.result = f"{winner.short_code} won against {loser.short_code}"
        match.status = "Completed"
        # match.score_summary = score_summary
        team_a_runs = request.form.get("team_a_runs")
        team_a_wickets = request.form.get("team_a_wickets")
        team_a_overs = request.form.get("team_a_overs")

        team_b_runs = request.form.get("team_b_runs")
        team_b_wickets = request.form.get("team_b_wickets")
        team_b_overs = request.form.get("team_b_overs")

        # Build a clean summary string
        match.score_summary = f"{team_a_runs}/{team_a_wickets} ({team_a_overs} ov) vs {team_b_runs}/{team_b_wickets} ({team_b_overs} ov)"
        db.session.commit()  # commit after setting winner_id
        rebuild_points_table(match.season)
        flash("Match marked as completed and points table updated!", "success")

    return redirect(url_for("matches.results"))
