from flask import Blueprint, render_template, request, flash, redirect, url_for

from cpl.blueprints.admin import admin_required
from cpl.models import Team, Match, PointsTable, TeamBalance, PlayerSeason, Player, Season
from extensions import db
import cloudinary.uploader
from flask import Response
import pandas as pd
import io
from sqlalchemy import distinct

bp = Blueprint("teams", __name__, url_prefix="/teams")

@bp.route("/season/<int:season_id>")
def season_teams(season_id):
    # Get distinct team IDs
    team_ids = (
        db.session.query(distinct(PlayerSeason.team_id))
        .filter(PlayerSeason.season_id == season_id, PlayerSeason.team_id.isnot(None))
        .all()
    )
    team_ids = [tid[0] for tid in team_ids]  # flatten list of tuples

    # Query Team objects
    teams = Team.query.filter(Team.id.in_(team_ids)).all()
    print(teams)

    return render_template("teams/list.html", teams=teams, season_id=season_id)


@bp.route("/")
def list_teams():
    # Season selection
    selected_year = request.args.get("year", type=int)
    seasons = Season.query.order_by(Season.year.desc()).all()
    years = [s.year for s in seasons]

    if not selected_year and seasons:
        selected_year = seasons[0].year

    selected_season = next((s for s in seasons if s.year == selected_year), None)
    selected_season_id = selected_season.id if selected_season else None

    # Pagination setup
    page = request.args.get("page", 1, type=int)
    per_page = 10

    teams = []
    pagination = None

    if selected_season_id:
        # Get distinct team IDs for this season
        team_ids = (
            db.session.query(PlayerSeason.team_id)
            .filter(PlayerSeason.season_id == selected_season_id,
                    PlayerSeason.team_id.isnot(None))
            .distinct()
            .all()
        )
        team_ids = [tid[0] for tid in team_ids]

        # Paginate only those teams
        pagination = Team.query.filter(Team.id.in_(team_ids))\
            .order_by(Team.name.asc())\
            .paginate(page=page, per_page=per_page, error_out=False)

        teams = pagination.items

    return render_template(
        "teams/list.html",
        teams=teams,
        pagination=pagination,
        years=years,
        selected_year=selected_year
    )


@bp.route("/<int:team_id>")
def team_detail(team_id):
    team = Team.query.get_or_404(team_id)

    # Selected year from query params
    selected_year = request.args.get("year", type=int)

    # All seasons for dropdown
    seasons = Season.query.order_by(Season.year.desc()).all()
    years = [s.year for s in seasons]

    # Default year = latest season
    if not selected_year and seasons:
        selected_year = seasons[0].year

    # Get Season object
    season_obj = Season.query.filter_by(year=selected_year).first()

    players = []
    if season_obj:
        # Get PlayerSeason rows for this team & selected season
        ps_rows = PlayerSeason.query.filter_by(
            team_id=team.id,
            season_id=season_obj.id
        ).all()

        # Fetch Player objects
        player_ids = [ps.player_id for ps in ps_rows]
        players = Player.query.filter(Player.id.in_(player_ids)).all()

    return render_template(
        "teams/detail.html",
        team=team,
        players=players,
        years=years,
        selected_year=selected_year
    )



@bp.route("/<int:team_id>/export")
def export_team_players(team_id):
    team = Team.query.get_or_404(team_id)

    # Selected year from query params
    selected_year = request.args.get("year", type=int)

    # Default year = latest season
    season_obj = None
    if selected_year:
        season_obj = Season.query.filter_by(year=selected_year).first()
    else:
        season_obj = Season.query.order_by(Season.year.desc()).first()
        selected_year = season_obj.year if season_obj else None

    players = []
    if season_obj:
        ps_rows = PlayerSeason.query.filter_by(
            team_id=team.id,
            season_id=season_obj.id
        ).all()

        player_ids = [ps.player_id for ps in ps_rows]
        players = Player.query.filter(Player.id.in_(player_ids)).all()

    # Build data for Excel
    data = []
    for player in players:
        # Assuming PlayerSeason has jersey_number and jersey_size
        ps = next((row for row in ps_rows if row.player_id == player.id), None)
        data.append({
            "TeamName": team.name,
            "PlayerName": player.name,
            "Role": player.role,
            "JerseyNumber": player.jersey_number if player else "",
            "JerseySize": player.jersey_size if player else ""
        })

    df = pd.DataFrame(data)

    # Write to Excel in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Players")

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment;filename={team.name}_{selected_year}_players.xlsx"
        }
    )


@bp.route("/add", methods=["GET", "POST"])
@admin_required
def add_team():
    if request.method == "POST":
        name = request.form["name"]
        short_code = request.form["short_code"]
        city = request.form.get("city")
        coach = request.form.get("coach")

        team_picture_url = None
        if "team_picture" in request.files:
            file = request.files["team_picture"]
            if file:
                # Upload to Cloudinary
                upload_result = cloudinary.uploader.upload(file)
                team_picture_url = upload_result["secure_url"]

        new_team = Team(
            name=name,
            short_code=short_code,
            city=city,
            coach=coach,
            team_picture_url=team_picture_url
        )
        db.session.add(new_team)
        db.session.commit()

        flash("Team added successfully!", "success")
        return redirect(url_for("teams.list_teams"))

    return render_template("teams/add_team.html")


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

    pagination = query.order_by(Match.match_date.desc()).paginate(page=page, per_page=per_page, error_out=False)
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
        selected_venue=selected_venue
    )


@bp.route("/init_balances", methods=["GET", "POST"])
@admin_required
def init_balances():
    if request.method == "POST":
        opening_amount = float(request.form.get("opening_amount", 0))
        max_players = int(request.form.get("max_players", 25))  # optional field

        teams = Team.query.all()
        created = 0

        for team in teams:
            balance = TeamBalance.query.filter_by(team_id=team.id).first()
            if not balance:
                balance = TeamBalance(
                    team_id=team.id,
                    opening=opening_amount,
                    spent=0,
                    remaining=opening_amount,
                    max_players=max_players,
                    players_bought=0
                )
                db.session.add(balance)
                created += 1
            else:
                # If balance already exists, update opening & remaining
                balance.opening = opening_amount
                balance.remaining = opening_amount - (balance.spent or 0)

        db.session.commit()
        flash(f"Initialized/updated balances for {created} teams!", "success")
        return redirect(url_for("main.home"))

    # GET request → show form
    return render_template("teams/init_balances.html")
