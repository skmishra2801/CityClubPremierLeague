from flask import Blueprint, render_template, request, redirect, url_for, flash
from cpl.models import Player, Team, TeamBalance
from extensions import db
from decimal import Decimal

bp = Blueprint("auction", __name__, url_prefix="/auction")


from decimal import Decimal

from decimal import Decimal

@bp.route("/", methods=["GET", "POST"])
def auction_page():
    players = Player.query.all()
    teams = Team.query.all()

    if request.method == "POST":
        player_id = request.form.get("player_id")
        team_id = request.form.get("team_id")
        amount = Decimal(request.form.get("amount", "0"))

        player = Player.query.get(player_id)
        if player and team_id and amount:
            team_id = int(team_id)

            # Assign player to team
            player.team_id = team_id
            player.amount = amount

            # Update TeamBalance
            team_balance = TeamBalance.query.filter_by(team_id=team_id).first()
            if team_balance:
                team_balance.spent = (team_balance.spent or Decimal("0")) + amount
                team_balance.remaining = (team_balance.opening or Decimal("0")) - (team_balance.spent or Decimal("0"))
                team_balance.players_bought = (team_balance.players_bought or 0) + 1

            db.session.commit()
            flash(f"{player.name} sold to {Team.query.get(team_id).name} for {amount}!", "success")
            return redirect(url_for("auction.auction_page"))

    return render_template("auction/auction.html", players=players, teams=teams)

