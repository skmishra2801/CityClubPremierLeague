from flask import Blueprint, render_template, request, redirect, url_for, flash
from cpl.models import Player, Team
from extensions import db
import cloudinary.uploader

bp = Blueprint("players", __name__, url_prefix="/players")


@bp.route("/")
def list_players():
    players = Player.query.all()
    teams = {t.id: t for t in Team.query.all()}
    return render_template("players/list.html", players=players, teams=teams)


@bp.route("/add", methods=["GET", "POST"])
def add_player():
    if request.method == "POST":
        name = request.form["name"]
        role = request.form["role"]
        jersey_number = request.form.get("jersey_number")
        jersey_size = request.form.get("jersey_size")
        payment_status = request.form.get("payment_status")
        team_id = request.form.get("team_id")

        photo_url = None
        photo_file = request.files.get("photo")
        if photo_file and photo_file.filename:
            upload_result = cloudinary.uploader.upload(photo_file)
            photo_url = upload_result.get("secure_url")

        new_player = Player(
            name=name,
            role=role,
            jersey_number=jersey_number,
            jersey_size=jersey_size,
            payment_status=payment_status,
            team_id=team_id,
            photo_url=photo_url
        )
        db.session.add(new_player)
        db.session.commit()

        flash("Player added successfully!", "success")
        return redirect(url_for("players.list_players"))

    teams = Team.query.all()
    return render_template("players/add.html", teams=teams)


@bp.route("/edit/<int:player_id>", methods=["GET", "POST"])
def edit_player(player_id):
    player = Player.query.get_or_404(player_id)
    if request.method == "POST":
        player.name = request.form["name"]
        player.role = request.form["role"]
        player.jersey_number = request.form.get("jersey_number")
        player.jersey_size = request.form.get("jersey_size")
        player.payment_status = request.form.get("payment_status")
        player.team_id = request.form.get("team_id")

        # handle photo update if new file uploaded
        photo_file = request.files.get("photo")
        if photo_file and photo_file.filename:
            upload_result = cloudinary.uploader.upload(photo_file)
            player.photo_url = upload_result.get("secure_url")

        db.session.commit()
        flash("Player updated successfully!", "success")
        return redirect(url_for("players.list_players"))

    teams = Team.query.all()
    return render_template("players/edit.html", player=player, teams=teams)


@bp.route("/delete/<int:player_id>", methods=["POST"])
def delete_player(player_id):
    player = Player.query.get_or_404(player_id)
    db.session.delete(player)
    db.session.commit()
    flash("Player deleted successfully!", "success")
    return redirect(url_for("players.list_players"))
