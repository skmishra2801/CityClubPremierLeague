# blueprints/scoreboard_ball_routes.py  (or append to scoreboard.py)
from flask import Blueprint, request, redirect, url_for, flash, jsonify, render_template
from extensions import db
from cpl.models import BallEvent, Match, Player, MatchScore, PlayerSeason, Team
from sqlalchemy import func

bp_ball = Blueprint("ball", __name__, url_prefix="/ball")  # or use your scoreboard bp

# ---------- helper: rebuild per-match MatchScore & PlayerSeason from BallEvent rows ----------
def rebuild_match_from_ballevents(match_id):
    """
    Recompute MatchScore rows and update PlayerSeason aggregates for the match.
    - Recreates/updates MatchScore rows per player per innings from ball_event rows.
    - Does not finalize points table / winner (call finalize_match separately).
    """
    # 1) Query events grouped by innings & player
    events = BallEvent.query.filter_by(match_id=match_id).order_by(BallEvent.innings_no, BallEvent.over_no, BallEvent.ball_no).all()

    # Build per-player & innings aggregates
    per_player_innings = {}  # (player_id, innings_no) -> dict
    for e in events:
        innings_no = e.innings_no or 1

        # batting: striker receives runs off bat only (others may have extras)
        if e.striker_id:
            key = (e.striker_id, innings_no)
            entry = per_player_innings.setdefault(key, {"batting_runs":0, "balls_faced":0, "fours":0, "sixes":0, "overs_bowled":0.0, "runs_conceded":0, "wickets_taken":0})
            # runs off bat
            entry["batting_runs"] += (e.runs or 0)
            # ball counts as legal unless extras indicate wd or nb
            extras = (e.extras or "").lower()
            is_legal = not ("wd" in extras or "nb" in extras)
            if is_legal:
                entry["balls_faced"] += 1
            if (e.runs or 0) == 4:
                entry["fours"] += 1
            if (e.runs or 0) == 6:
                entry["sixes"] += 1

        # bowling: bowler concedes runs & bowls balls (legal)
        if e.bowler_id:
            keyb = (e.bowler_id, e.innings_no)
            entryb = per_player_innings.setdefault(keyb, {"batting_runs":0, "balls_faced":0, "fours":0, "sixes":0, "overs_bowled":0.0, "runs_conceded":0, "wickets_taken":0})
            entryb["runs_conceded"] += ( (e.runs or 0) + (e.extras_runs or 0) )
            extras = (e.extras or "").lower()
            is_legal = not ("wd" in extras or "nb" in extras)
            if is_legal:
                entryb["overs_bowled"] += 1  # track as balls; will convert later

            if e.is_wicket:
                entryb["wickets_taken"] += 1

    # Convert balls->overs for bowlers (we tracked legal balls in overs_bowled as count; we need decimal)
    # but above we incremented overs_bowled as count of legal balls; convert:
    for k,v in per_player_innings.items():
        # overs_bowled currently stored as count of legal balls for bowlers
        if v.get("overs_bowled") and isinstance(v["overs_bowled"], int):
            v["overs_bowled"] = v["overs_bowled"] / 6.0

    # 2) Persist MatchScore rows
    # Clear or update: we will update existing rows or create new ones
    for (player_id, innings_no), vals in per_player_innings.items():
        ms = MatchScore.query.filter_by(match_id=match_id, player_id=player_id, innings_no=innings_no).first()
        if not ms:
            ms = MatchScore(match_id=match_id, player_id=player_id, innings_no=innings_no)
            db.session.add(ms)
        ms.batting_runs = vals.get("batting_runs", 0)
        ms.balls_faced = vals.get("balls_faced", 0)
        ms.fours = vals.get("fours", 0)
        ms.sixes = vals.get("sixes", 0)
        ms.overs_bowled = float(vals.get("overs_bowled", 0.0))
        ms.runs_conceded = vals.get("runs_conceded", 0)
        ms.wickets_taken = vals.get("wickets_taken", 0)

    db.session.commit()

    # 3) Optionally update PlayerSeason aggregates (incremental or full recalc)
    # Here let's update season aggregates by summing match_score for that season (safer)
    match = Match.query.get(match_id)
    if match:
        season_id = match.season_id
        # Get distinct player_ids in this match
        player_ids = db.session.query(MatchScore.player_id).filter_by(match_id=match_id).distinct().all()
        player_ids = [p[0] for p in player_ids]
        for pid in player_ids:
            # aggregate across all matches in season for player
            agg = db.session.query(
                func.coalesce(func.sum(MatchScore.batting_runs),0),
                func.coalesce(func.sum(MatchScore.balls_faced),0),
                func.coalesce(func.sum(MatchScore.overs_bowled),0.0),
                func.coalesce(func.sum(MatchScore.runs_conceded),0),
                func.coalesce(func.sum(MatchScore.wickets_taken),0)
            ).join(Match, Match.id == MatchScore.match_id).filter(
                Match.season_id == season_id,
                MatchScore.player_id == pid
            ).first()

            ps = PlayerSeason.query.filter_by(player_id=pid, season_id=season_id).first()
            if ps and agg:
                runs_scored, balls_faced_total, overs_bowled_total, runs_conceded_total, wickets_total = agg
                ps.runs_scored = int(runs_scored or 0)
                ps.matches_played = ps.matches_played or 0  # we won't recalc matches played here
                ps.overs_bowled = float(overs_bowled_total or 0.0)
                ps.wickets_taken = int(wickets_total or 0)
                # batting_average: maintain as runs / matches_played (if matches_played nonzero)
                if ps.matches_played and ps.matches_played > 0:
                    ps.batting_average = ps.runs_scored / ps.matches_played
                else:
                    ps.batting_average = 0.0
                if ps.wickets_taken:
                    ps.bowling_average = (ps.runs_scored if False else ps.runs_scored) / ps.wickets_taken  # placeholder; adjust as you prefer
                else:
                    ps.bowling_average = 0.0
    db.session.commit()
