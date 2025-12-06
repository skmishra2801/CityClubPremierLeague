from flask import Blueprint, render_template, request, redirect, url_for, flash
from cpl.blueprints.admin import admin_required
from cpl.models import Player, Team, TeamBalance, Season, PlayerSeason, MatchScore
from extensions import db
from decimal import Decimal

bp = Blueprint("auction", __name__, url_prefix="/auction")


@bp.route("/", methods=["GET", "POST"])
@admin_required
def auction_page():
    selected_year = request.form.get("year") or request.args.get("year")

    seasons = Season.query.order_by(Season.year.desc()).all()
    years = [s.year for s in seasons]

    if not selected_year:
        latest_season = seasons[0] if seasons else None
        selected_year = latest_season.year if latest_season else None

    season_obj = Season.query.filter_by(year=int(selected_year)).first() if selected_year else None

    all_players = Player.query.all()
    players = all_players

    if season_obj:
        sold_rows = PlayerSeason.query.filter_by(season_id=season_obj.id).all()
        sold_ids = {row.player_id for row in sold_rows}
        players = [p for p in all_players if p.id not in sold_ids]

    teams = {t.id: t for t in Team.query.all()}

    # ─────────────────────────────
    # Player summaries (always computed if season exists)
    # ─────────────────────────────
    player_summaries = {}
    if season_obj:
        for p in players:
            match_scores = MatchScore.query.filter_by(
                player_id=p.id
            ).all()

            # Batting
            # match_played = sum(1 for ms in match_scores if ms.match_id)
            # Collect distinct match IDs
            distinct_match_ids = {ms.match_id for ms in match_scores if ms.match_id}

            # Number of matches played
            match_played = len(distinct_match_ids)
            total_runs = sum(ms.batting_runs for ms in match_scores)
            times_out = sum(1 for ms in match_scores if ms.is_out)
            batting_avg = round(total_runs / times_out, 2) if times_out > 0 else None
            total_balls_faced = sum(ms.balls_faced for ms in match_scores)  # assuming you store balls faced
            strike_rate = (round(total_runs / total_balls_faced * 100, 2) if total_balls_faced > 0 else None)
            highest_score = max((ms.batting_runs for ms in match_scores), default=0)
            # Bowling
            wickets_taken =  sum(1 for ms in match_scores if ms.wickets_taken)
            runs_conceded = sum(ms.runs_conceded for ms in match_scores)
            balls_bowled = sum(ms.overs_bowled for ms in match_scores)  # assuming you store balls bowled
            overs_bowled = balls_bowled / 6 if balls_bowled else 0
            bowling_economy = (runs_conceded / overs_bowled) if overs_bowled > 0 else None

            player_summaries[p.id] = {
                "batting_avg": batting_avg,
                "total_runs": total_runs,
                "bowling_economy": bowling_economy,
                "runs_conceded": runs_conceded,
                "overs_bowled": overs_bowled,
                "match_played":match_played,
                "wickets_taken": wickets_taken,
                "strike_rate": strike_rate,
                "highest_score": highest_score
            }

    # ─────────────────────────────
    # POST → Auction Submission
    # ─────────────────────────────
    if request.method == "POST":
        player_id = request.form.get("player_id")
        team_id = request.form.get("team_id")
        amount = Decimal(request.form.get("amount", "0"))

        if not season_obj:
            flash("Season not selected or invalid!", "danger")
            return redirect(url_for("auction.auction_page"))

        player = Player.query.get(player_id)

        if player and team_id is not None and amount is not None:
            team_id = int(team_id)

            ps = PlayerSeason.query.filter_by(
                player_id=player.id, season_id=season_obj.id
            ).first()

            if not ps:
                ps = PlayerSeason(
                    player_id=player.id,
                    season_id=season_obj.id,
                    sold_price=amount,
                    team_id=team_id,
                )
                db.session.add(ps)
            else:
                ps.sold_price = amount
                ps.team_id = team_id

            team_balance = TeamBalance.query.filter_by(team_id=team_id).first()
            if team_balance:
                team_balance.spent = (team_balance.spent or 0) + amount
                team_balance.remaining = (team_balance.opening or 0) - team_balance.spent
                team_balance.players_bought = (team_balance.players_bought or 0) + 1

            db.session.commit()

            flash(f"{player.name} sold to {teams[team_id].name} for {amount}!", "success")
            return redirect(url_for("auction.auction_page", year=selected_year))

    # Render page
    return render_template(
        "auction/auction.html",
        players=players,
        teams=teams,
        years=years,
        selected_year=int(selected_year) if selected_year else None,
        player_summaries=player_summaries,
    )

