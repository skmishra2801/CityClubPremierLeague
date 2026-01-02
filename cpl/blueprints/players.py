from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from cpl.blueprints.admin import admin_required
from cpl.models import Player, Team, PlayerSeason, Season
from extensions import db
import cloudinary.uploader

bp = Blueprint("players", __name__, url_prefix="/players")


# -----------------------------------------------------
# LIST PLAYERS (FILTER BY SEASON)
# -----------------------------------------------------
@bp.route("/")
def list_players():
    selected_year = request.args.get("year")

    # If no year selected → choose latest season
    if not selected_year:
        latest_season = Season.query.order_by(Season.year.desc()).first()
        selected_year = latest_season.year if latest_season else datetime.now().year

    # List of all years (for filter dropdown)
    years = [s.year for s in Season.query.order_by(Season.year.desc()).all()]

    # Get season object for the selected year
    season_obj = Season.query.filter_by(year=int(selected_year)).first()

    if not season_obj:
        players = []
        season_rows = []
    else:
        # Get PlayerSeason rows for this season
        season_rows = PlayerSeason.query.filter_by(season_id=season_obj.id).all()
        player_ids = [row.player_id for row in season_rows]

        # Fetch players in this season
        players = Player.query.filter(Player.id.in_(player_ids)).all()

    # Map player_id → PlayerSeason row (for template)
    season_map = {row.player_id: row for row in season_rows}

    # Map teams
    teams = {t.id: t for t in Team.query.all()}

    return render_template(
        "players/list.html",
        players=players,
        teams=teams,
        years=years,
        selected_year=int(selected_year),
        season_map=season_map
    )


# -----------------------------------------------------
# ADD PLAYER
# -----------------------------------------------------
# @bp.route("/add", methods=["GET", "POST"])
# def add_player():
#     if request.method == "POST":
#         name = request.form["name"]
#         role = request.form["role"]
#         jersey_number = request.form.get("jersey_number")
#         jersey_size = request.form.get("jersey_size")
#         payment_status = request.form.get("payment_status")
#
#         team_id = request.form.get("team_id")
#         team_id = int(team_id) if team_id and team_id.isdigit() else None
#
#         season_year = request.form.get("season_year")
#
#         # Upload photo
#         photo_url = None
#         photo_file = request.files.get("photo")
#         if photo_file and photo_file.filename:
#             upload_result = cloudinary.uploader.upload(photo_file)
#             photo_url = upload_result.get("secure_url")
#
#         # Create Player (base details only)
#         new_player = Player(
#             name=name,
#             role=role,
#             jersey_number=jersey_number,
#             jersey_size=jersey_size,
#             payment_status=payment_status,
#             photo_url=photo_url
#         )
#         db.session.add(new_player)
#         db.session.commit()  # commit to get player.id
#
#         # Create PlayerSeason row
#         if season_year:
#             season = Season.query.filter_by(year=int(season_year)).first()
#
#             if season:
#                 ps = PlayerSeason(
#                     season_id=season.id,
#                     player_id=new_player.id,
#                     team_id=team_id  # can be None if unassigned
#                 )
#                 db.session.add(ps)
#                 db.session.commit()
#
#         flash("Player added successfully!", "success")
#         return redirect(url_for("players.list_players"))
#
#     teams = Team.query.all()
#     seasons = Season.query.order_by(Season.year.desc()).all()
#
#     return render_template("players/add.html", teams=teams, seasons=seasons)

@bp.route("/add", methods=["GET", "POST"])
def add_player():
    if request.method == "POST":
        # Collect form data but don't commit yet
        form_data = {
            "name": request.form["name"],
            "role": request.form["role"],
            "jersey_number": request.form.get("jersey_number"),
            "jersey_size": request.form.get("jersey_size"),
            "payment_status": request.form.get("payment_status"),
            "team_id": request.form.get("team_id"),
            "season_year": request.form.get("season_year"),
        }

        # Handle photo upload temporarily (optional: store in session)
        photo_file = request.files.get("photo")
        photo_url = None
        if photo_file and photo_file.filename:
            upload_result = cloudinary.uploader.upload(photo_file)
            photo_url = upload_result.get("secure_url")
        form_data["photo_url"] = photo_url

        # Render preview template
        return render_template("players/preview.html", data=form_data)

    teams = Team.query.all()
    seasons = Season.query.order_by(Season.year.desc()).all()
    return render_template("players/add.html", teams=teams, seasons=seasons)


@bp.route("/confirm_add", methods=["POST"])
def confirm_add():
    name = request.form["name"]
    role = request.form["role"]
    jersey_number = request.form.get("jersey_number")
    jersey_size = request.form.get("jersey_size")
    payment_status = request.form.get("payment_status")
    team_id = request.form.get("team_id")
    team_id = int(team_id) if team_id and team_id.isdigit() else None
    photo_url = request.form.get("photo_url")

    # Create Player
    new_player = Player(
        name=name,
        role=role,
        jersey_number=jersey_number,
        jersey_size=jersey_size,
        payment_status=payment_status,
        photo_url=photo_url
    )
    db.session.add(new_player)
    db.session.commit()

    # Create PlayerSeason row only if team_id is provided
    if team_id:
        ps = PlayerSeason(
            player_id=new_player.id,
            team_id=team_id
        )
        db.session.add(ps)
        db.session.commit()

    flash("Player added successfully!", "success")
    return redirect(url_for("players.list_players"))


# -----------------------------------------------------
# EDIT PLAYER
# -----------------------------------------------------
@bp.route("/edit/<int:player_id>", methods=["GET", "POST"])
@admin_required
def edit_player(player_id):
    player = Player.query.get_or_404(player_id)

    if request.method == "POST":
        player.name = request.form["name"]
        player.role = request.form["role"]
        player.jersey_number = request.form.get("jersey_number")
        player.jersey_size = request.form.get("jersey_size")
        player.payment_status = request.form.get("payment_status")
        player.team_id = request.form.get("team_id")

        # photo update
        photo_file = request.files.get("photo")
        if photo_file and photo_file.filename:
            upload_result = cloudinary.uploader.upload(photo_file)
            player.photo_url = upload_result.get("secure_url")

        db.session.commit()
        flash("Player updated successfully!", "success")
        return redirect(url_for("players.list_players"))

    teams = Team.query.all()
    return render_template("players/edit.html", player=player, teams=teams)


# -----------------------------------------------------
# DELETE PLAYER
# -----------------------------------------------------
@bp.route("/delete/<int:player_id>", methods=["POST"])
@admin_required
def delete_player(player_id):
    player = Player.query.get_or_404(player_id)

    # Also delete related PlayerSeason entries
    PlayerSeason.query.filter_by(player_id=player_id).delete()

    db.session.delete(player)
    db.session.commit()

    flash("Player deleted successfully!", "success")
    return redirect(url_for("players.list_players"))

@bp.route("/assign", methods=["GET", "POST"])
def assign_player_to_season():
    seasons = Season.query.order_by(Season.year.desc()).all()
    players = Player.query.order_by(Player.name).all()
    teams = Team.query.order_by(Team.name).all()

    if request.method == "POST":
        season_id = request.form.get("season_id")
        player_id = request.form.get("player_id")
        team_id = request.form.get("team_id") or None

        # Check if already assigned
        exists = PlayerSeason.query.filter_by(
            season_id=season_id,
            player_id=player_id
        ).first()

        if exists:
            flash("Player already assigned to this season!", "warning")
            return redirect(url_for("players.assign_player_to_season"))

        new_ps = PlayerSeason(
            season_id=season_id,
            player_id=player_id,
            team_id=team_id
        )

        db.session.add(new_ps)
        db.session.commit()

        flash("Player assigned to season successfully!", "success")
        return redirect(url_for("players.list_players", year=Season.query.get(season_id).year))

    return render_template(
        "players/assign.html",
        players=players,
        seasons=seasons,
        teams=teams
    )
