from flask import Blueprint, render_template, request, flash, redirect, url_for

from cpl.blueprints.admin import admin_required
from cpl.models import Team, Match, PointsTable, TeamBalance
from extensions import db
import cloudinary.uploader

bp = Blueprint("teams", __name__, url_prefix="/teams")


@bp.route("/")
def list_teams():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    pagination = Team.query.order_by(Team.name.asc()).paginate(page=page, per_page=per_page, error_out=False)
    teams = pagination.items
    return render_template("teams/list.html", teams=teams, pagination=pagination)


@bp.route("/<int:team_id>")
def team_detail(team_id):
    team = Team.query.get_or_404(team_id)
    # assuming you have a relationship Team.players
    players = team.players
    return render_template("teams/detail.html", team=team, players=players)


@bp.route("/add", methods=["GET", "POST"])
@admin_required
def add_team():
    if request.method == "POST":
        name = request.form["name"]
        short_code = request.form["short_code"]
        city = request.form.get("city")
        coach = request.form.get("coach")

        logo_url = None
        if "logo_file" in request.files:
            file = request.files["logo_file"]
            if file:
                # Upload to Cloudinary
                upload_result = cloudinary.uploader.upload(file)
                logo_url = upload_result["secure_url"]  # hosted URL

        new_team = Team(
            name=name,
            short_code=short_code,
            city=city,
            coach=coach,
            logo_url=logo_url
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
