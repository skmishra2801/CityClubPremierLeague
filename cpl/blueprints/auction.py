from flask import Blueprint, render_template, request, redirect, url_for, flash
from cpl.models import Player, Team
from extensions import db

bp = Blueprint("auction", __name__, url_prefix="/auction")


@bp.route("/", methods=["GET", "POST"])
def auction_page():
    players = Player.query.all()
    teams = Team.query.all()

    if request.method == "POST":
        player_id = request.form.get("player_id")
        team_id = request.form.get("team_id")

        player = Player.query.get(player_id)
        if player and team_id:
            player.team_id = team_id
            db.session.commit()
            flash(f"{player.name} sold to {Team.query.get(team_id).name}!", "success")
            return redirect(url_for("auction.auction_page"))

    return render_template("auction/auction.html", players=players, teams=teams)
