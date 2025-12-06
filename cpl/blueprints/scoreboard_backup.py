from flask import (
    render_template, Blueprint, url_for, redirect, request, flash, jsonify, current_app
)
from sqlalchemy import func
import json
from extensions import db
from cpl.models import (
    Match, Season, PlayerSeason, Team, MatchScore,
    Player, MatchBall, PointsTable
)

bp = Blueprint("scoreboard", __name__, url_prefix="/scoreboard")


# ----------------------------
# Helpers: extras + DB reads
# ----------------------------
def _extras_from_mb(mb):
    try:
        return mb.extras() or {}
    except Exception:
        try:
            return json.loads(mb.extras_json or "{}")
        except Exception:
            return {}


def _balls_for_match(match_id):
    return MatchBall.query.filter_by(match_id=match_id).order_by(MatchBall.id).all()


def overs_to_float(overs_str: str) -> float:
    """
    Convert cricket overs notation (e.g. '5.4') into float overs (e.g. 5.666...).
    """
    if not overs_str:
        return 0.0
    try:
        parts = overs_str.split(".")
        overs = int(parts[0])
        balls = int(parts[1]) if len(parts) > 1 else 0
        return overs + balls / 6.0
    except ValueError:
        return 0.0


# ----------------------------
# Rebuild state from DB (grouped-by-overs)
# ----------------------------
def rebuild_state_from_db(match_id):
    match = Match.query.get(match_id)
    if not match:
        return {}

    balls = _balls_for_match(match_id)

    # two innings containers
    inns_state = {
        1: {"runs": 0, "wickets": 0, "balls": 0, "overs": "0.0",
            "batsmen": {}, "bowlers": {}, "on_strike": None, "non_strike": None,
            "current_bowler": None, "over_events": {}},
        2: {"runs": 0, "wickets": 0, "balls": 0, "overs": "0.0",
            "batsmen": {}, "bowlers": {}, "on_strike": None, "non_strike": None,
            "current_bowler": None, "over_events": {}}
    }

    def ensure_bat(inns, pid, name):
        if not name:
            return None
        b = inns["batsmen"]
        if name not in b:
            b[name] = {"id": pid, "name": name, "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "out_desc": None}
        return b[name]

    def ensure_bowl(inns, pid, name):
        if not name:
            return None
        b = inns["bowlers"]
        if name not in b:
            b[name] = {"id": pid, "name": name, "overs_balls": 0, "runs_conceded": 0, "wickets": 0,
                       "current_over_runs": 0, "maidens": 0}
        return b[name]

    # Use match fields (if present) as initial roles
    def apply_match_roles(inns, match, innings_no):
        try:
            if hasattr(match, "current_on_strike_id") and getattr(match, "current_on_strike_id", None):
                p = Player.query.get(getattr(match, "current_on_strike_id"))
                if p:
                    inns["on_strike"] = p.name
            if hasattr(match, "current_non_strike_id") and getattr(match, "current_non_strike_id", None):
                p = Player.query.get(getattr(match, "current_non_strike_id"))
                if p:
                    inns["non_strike"] = p.name
            if hasattr(match, "current_bowler_id") and getattr(match, "current_bowler_id", None):
                p = Player.query.get(getattr(match, "current_bowler_id"))
                if p:
                    inns["current_bowler"] = p.name
        except Exception:
            pass

    # set initial from match if available
    apply_match_roles(inns_state[1], match, 1)
    apply_match_roles(inns_state[2], match, 2)

    # iterate balls and build stats
    for mb in balls:
        inns_no = mb.innings_no or 1
        inns = inns_state.setdefault(inns_no, {"runs": 0, "wickets": 0, "balls": 0, "overs": "0.0",
                                               "batsmen": {}, "bowlers": {}, "on_strike": None, "non_strike": None,
                                               "current_bowler": None, "over_events": {}})

        extras = _extras_from_mb(mb)
        runs_bat = int(mb.runs_bat or 0)
        total_runs = int(mb.total_runs or 0)
        wicket = bool(mb.wicket)

        # resolve names
        batsman_name = None
        bowler_name = None
        if mb.batsman_player_id:
            pb = Player.query.get(mb.batsman_player_id)
            batsman_name = pb.name if pb else None
        if mb.bowler_player_id:
            pbo = Player.query.get(mb.bowler_player_id)
            bowler_name = pbo.name if pbo else None

        bentry = ensure_bat(inns, mb.batsman_player_id if mb.batsman_player_id else None, batsman_name)
        bowlentry = ensure_bowl(inns, mb.bowler_player_id if mb.bowler_player_id else None, bowler_name)

        # legal or not
        is_legal = ("wd" not in extras) and ("nb" not in extras)

        # update innings totals
        inns["runs"] += total_runs
        if wicket:
            inns["wickets"] += 1
        if is_legal:
            inns["balls"] += 1

        # batsman update
        if bentry:
            if is_legal:
                bentry["balls"] += 1
            bentry["runs"] += runs_bat
            if runs_bat == 4:
                bentry["fours"] += 1
            if runs_bat == 6:
                bentry["sixes"] += 1
            if wicket:
                bentry["out_desc"] = mb.dismissal_desc or f"b {bowler_name or 'bowler'}"

        # bowler update
        if bowlentry:
            bowlentry["runs_conceded"] += total_runs
            if is_legal:
                bowlentry["overs_balls"] += 1
                bowlentry["current_over_runs"] += total_runs
            if wicket:
                bowlentry["wickets"] += 1

        # group into overs (0-based index)
        over_idx = (inns["balls"] - 1) // 6 if is_legal and inns["balls"] > 0 else (inns["balls"] // 6)
        evt = {
            "id": mb.id,
            "desc": build_ball_desc(runs_bat, extras, wicket),
            "total": total_runs,
            "runs_bat": runs_bat,
            "extras": extras,
            "wicket": wicket,
            "batsman": batsman_name,
            "bowler": bowler_name,
            "ball_in_over": mb.ball_in_over if hasattr(mb, "ball_in_over") else None
        }
        inns["over_events"].setdefault(over_idx, []).append(evt)

        # update current roles (last known)
        if batsman_name:
            inns["on_strike"] = batsman_name
        if bowler_name:
            inns["current_bowler"] = bowler_name

        # odd-run rotation heuristic
        odd_from_bat = runs_bat % 2 == 1
        odd_from_extras = ((extras.get("lb", 0) + extras.get("b", 0)) % 2 == 1)
        if is_legal and (odd_from_bat or odd_from_extras):
            inns["on_strike"], inns["non_strike"] = inns.get("non_strike"), inns.get("on_strike")

        # end-of-over swap + maiden detection
        if is_legal and (inns["balls"] % 6 == 0):
            if bowlentry and bowlentry.get("current_over_runs", 0) == 0:
                bowlentry["maidens"] = bowlentry.get("maidens", 0) + 1
            if bowlentry:
                bowlentry["current_over_runs"] = 0
            inns["on_strike"], inns["non_strike"] = inns.get("non_strike"), inns.get("on_strike")

    # finalize overs string
    for i in (1, 2):
        b = inns_state[i]["balls"]
        inns_state[i]["overs"] = f"{b // 6}.{b % 6}"

    # build summary + computed result if both innings have balls
    summary = {
        "1": {"runs": inns_state[1]["runs"], "wickets": inns_state[1]["wickets"], "overs": inns_state[1]["overs"]},
        "2": {"runs": inns_state[2]["runs"], "wickets": inns_state[2]["wickets"], "overs": inns_state[2]["overs"]}
    }

    match_result = None
    if inns_state[1]["balls"] > 0 and inns_state[2]["balls"] > 0:
        r1 = inns_state[1]["runs"]
        r2 = inns_state[2]["runs"]
        if r1 > r2:
            match_result = f"Innings1 team won by {r1 - r2} runs"
        elif r2 > r1:
            w2 = inns_state[2]["wickets"]
            match_result = f"Innings2 team won by {10 - w2} wickets"
        else:
            match_result = "Match tied"

    return {"innings": inns_state, "summary": summary, "match_result": match_result}


# ----------------------------
# Routes
# ----------------------------
@bp.route("/")
def scoreboard_page():
    seasons_rows = Season.query.order_by(Season.year.desc()).all()
    seasons = [s.year for s in seasons_rows]
    selected_season = request.args.get("season", type=int)
    if not selected_season:
        selected_season = seasons[0] if seasons else None

    query = Match.query
    if selected_season:
        query = query.join(Match.season).filter(Season.year == selected_season)
    matches = query.order_by(Match.match_date.asc()).all()
    return render_template("scoreboard/list.html", matches=matches, seasons=seasons, selected_season=selected_season)


# @bp.route("/scoreboard/<int:match_id>")
# def scoreboard(match_id):
#     match = Match.query.get(match_id)
#     if not match:
#         flash("Match not found.", "danger")
#         return redirect(url_for("scoreboard.scoreboard_page"))
#
#     # ✅ Check toss_winner before proceeding
#     if not match.toss_winner:
#         flash("Toss not yet decided. Please set the toss.", "info")
#         return redirect(url_for("scoreboard.toss_page", match_id=match.id))
#
#     state = rebuild_state_from_db(match_id)
#     selected_tab = request.args.get("selected_tab", "team_a")
#
#     # --- Players by team ---
#     players_teamA = PlayerSeason.query.filter_by(
#         team_id=match.team_a_id,
#         season_id=match.season_id
#     ).all()
#
#     players_teamB = PlayerSeason.query.filter_by(
#         team_id=match.team_b_id,
#         season_id=match.season_id
#     ).all()
#
#     # --- Team objects ---
#     team_a = Team.query.get(match.team_a_id) if match.team_a_id else None
#     team_b = Team.query.get(match.team_b_id) if match.team_b_id else None
#
#     team_a_name = team_a.name if team_a else "Team A"
#     team_b_name = team_b.name if team_b else "Team B"
#
#     team_a_pic = team_a.team_picture_url if team_a and team_a.team_picture_url else "default-team-logo.png"
#     team_b_pic = team_b.team_picture_url if team_b and team_b.team_picture_url else "default-team-logo.png"
#
#     # --- Innings and overs ---
#     current_innings = getattr(match, "current_innings_no", 1) or 1
#     overs1 = getattr(match, "overs_limit_innings1", None)
#     overs2 = getattr(match, "overs_limit_innings2", None)
#
#     # --- Player dictionary ---
#     player_dict = {
#         ps.player.name: ps.player
#         for ps in PlayerSeason.query.filter_by(season_id=match.season_id).all()
#     }
#
#     # --- Helper function for overs/runs/wickets ---
#     innings_state = {
#         "first_innings_score": match.first_innings_score,
#         "first_innings_wickets": match.first_innings_wickets,
#         "first_innings_balls": match.first_innings_balls,
#         "second_innings_score": match.second_innings_score,
#         "second_innings_wickets": match.second_innings_wickets,
#         "second_innings_balls": match.second_innings_balls
#     }
#     def calc_innings_stats(innings_state):
#         def format_innings(balls, runs, wickets):
#             overs = balls // 6
#             balls_in_current_over = balls % 6
#             running_over = f"{overs}.{balls_in_current_over}"
#             return {
#                 "overs": running_over,
#                 "runs": runs,
#                 "wickets": wickets
#             }
#
#         first_innings = format_innings(
#             innings_state.get("first_innings_balls", 0),
#             innings_state.get("first_innings_score", 0),
#             innings_state.get("first_innings_wickets", 0)
#         )
#
#         second_innings = format_innings(
#             innings_state.get("second_innings_balls", 0),
#             innings_state.get("second_innings_score", 0),
#             innings_state.get("second_innings_wickets", 0)
#         )
#
#         return first_innings, second_innings
#     first_innings, second_innings = calc_innings_stats(innings_state)
#
#
#     # ✅ Decide batting/bowling team IDs based on innings
#     if current_innings == 1:
#         batting_team_id = match.team_a_id
#         bowling_team_id = match.team_b_id
#     else:
#         batting_team_id = match.team_b_id
#         bowling_team_id = match.team_a_id
#
#     # --- Squad lists ---
#     batting_players = PlayerSeason.query.filter_by(
#         team_id=batting_team_id,
#         season_id=match.season_id
#     ).all()
#
#     bowling_players = PlayerSeason.query.filter_by(
#         team_id=bowling_team_id,
#         season_id=match.season_id
#     ).all()
#
#     # --- Scores ---
#     scores = {
#         s.player_id: s
#         for s in MatchScore.query.filter_by(
#             match_id=match.id,
#             innings_no=current_innings
#         ).all()
#     }
#
#     batting_scores = MatchScore.query.filter_by(
#         match_id=match.id,
#         innings_no=current_innings,
#         team_id=batting_team_id
#     ).all()
#
#     bowling_scores = MatchScore.query.filter_by(
#         match_id=match.id,
#         innings_no=current_innings,
#         team_id=bowling_team_id
#     ).all()
#     # Query all ball records for this match + innings
#     balls = MatchBall.query.filter_by(match_id=match.id, innings_no=match.current_innings_no).all()
#     extras_summary = {
#         "nb": sum(ball.extras().get("nb", 0) for ball in balls),
#         "wd": sum(ball.extras().get("wd", 0) for ball in balls),
#         "b": sum(ball.extras().get("b", 0) for ball in balls),
#         "lb": sum(ball.extras().get("lb", 0) for ball in balls),
#         "pen": sum(ball.extras().get("pen", 0) for ball in balls),
#     }
#
#     extras_total = sum(extras_summary.values())
#
#     return render_template(
#         "scoreboard/scoreboard.html",
#         match=match,
#         extras_summary=extras_summary,
#         extras_total=extras_total,
#         state=state,
#         players_teamA=players_teamA,
#         players_teamB=players_teamB,
#         team_a_name=team_a_name,
#         team_b_name=team_b_name,
#         team_a_pic=team_a_pic,
#         team_b_pic=team_b_pic,
#         current_innings=current_innings,
#         overs1=overs1,
#         overs2=overs2,
#         # team_a_over=team_a_over,
#         # team_a_runs=team_a_runs,
#         # team_a_wkts=team_a_wkts,
#         # team_b_over=team_b_over,
#         # team_b_runs=team_b_runs,
#         # team_b_wkts=team_b_wkts,
#         batting_players=batting_players,
#         bowling_players=bowling_players,
#         selected_tab=selected_tab,
#         batting_scores=batting_scores,
#         bowling_scores=bowling_scores,
#         first_innings=first_innings,
#         second_innings=second_innings
#     )
@bp.route("/scoreboard/<int:match_id>")
def scoreboard(match_id):
    match = Match.query.get(match_id)
    if not match:
        flash("Match not found.", "danger")
        return redirect(url_for("scoreboard.scoreboard_page"))

    # ✅ Check toss_winner before proceeding
    if not match.toss_winner:
        flash("Toss not yet decided. Please set the toss.", "info")
        return redirect(url_for("scoreboard.toss_page", match_id=match.id))

    state = rebuild_state_from_db(match_id)
    selected_tab = request.args.get("selected_tab", "team_a")

    # --- Players by team ---
    players_teamA = PlayerSeason.query.filter_by(
        team_id=match.team_a_id,
        season_id=match.season_id
    ).all()
    players_teamB = PlayerSeason.query.filter_by(
        team_id=match.team_b_id,
        season_id=match.season_id
    ).all()

    # --- Team objects ---
    team_a = Team.query.get(match.team_a_id) if match.team_a_id else None
    team_b = Team.query.get(match.team_b_id) if match.team_b_id else None

    team_a_name = team_a.name if team_a else "Team A"
    team_b_name = team_b.name if team_b else "Team B"
    team_a_pic = team_a.team_picture_url if team_a and team_a.team_picture_url else "default-team-logo.png"
    team_b_pic = team_b.team_picture_url if team_b and team_b.team_picture_url else "default-team-logo.png"

    # --- Innings and overs ---
    current_innings = getattr(match, "current_innings_no", 1) or 1
    overs1 = getattr(match, "overs_limit_innings1", None)
    overs2 = getattr(match, "overs_limit_innings2", None)

    # --- Helper function for overs/runs/wickets ---
    def format_innings(balls, runs, wickets):
        overs = balls // 6
        balls_in_current_over = balls % 6
        running_over = f"{overs}.{balls_in_current_over}"
        return {"overs": running_over, "runs": runs, "wickets": wickets}

    first_innings = format_innings(
        match.first_innings_balls or 0,
        match.first_innings_score or 0,
        match.first_innings_wickets or 0
    )
    second_innings = format_innings(
        match.second_innings_balls or 0,
        match.second_innings_score or 0,
        match.second_innings_wickets or 0
    )

    # --- First innings data ---
    batting_scores_1 = MatchScore.query.filter_by(
        match_id=match.id, innings_no=1, team_id=match.team_a_id
    ).all()
    bowling_scores_1 = MatchScore.query.filter_by(
        match_id=match.id, innings_no=1, team_id=match.team_b_id
    ).all()
    balls_1 = MatchBall.query.filter_by(match_id=match.id, innings_no=1).all()
    extras_summary_1 = {
        "nb": sum(ball.extras().get("nb", 0) for ball in balls_1),
        "wd": sum(ball.extras().get("wd", 0) for ball in balls_1),
        "b":  sum(ball.extras().get("b", 0) for ball in balls_1),
        "lb": sum(ball.extras().get("lb", 0) for ball in balls_1),
        "pen": sum(ball.extras().get("pen", 0) for ball in balls_1),
    }
    extras_total_1 = sum(extras_summary_1.values())

    # --- Second innings data ---
    batting_scores_2 = MatchScore.query.filter_by(
        match_id=match.id, innings_no=2, team_id=match.team_b_id
    ).all()
    bowling_scores_2 = MatchScore.query.filter_by(
        match_id=match.id, innings_no=2, team_id=match.team_a_id
    ).all()
    balls_2 = MatchBall.query.filter_by(match_id=match.id, innings_no=2).all()
    extras_summary_2 = {
        "nb": sum(ball.extras().get("nb", 0) for ball in balls_2),
        "wd": sum(ball.extras().get("wd", 0) for ball in balls_2),
        "b":  sum(ball.extras().get("b", 0) for ball in balls_2),
        "lb": sum(ball.extras().get("lb", 0) for ball in balls_2),
        "pen": sum(ball.extras().get("pen", 0) for ball in balls_2),
    }
    extras_total_2 = sum(extras_summary_2.values())

    return render_template(
        "scoreboard/scoreboard.html",
        match=match,
        state=state,
        players_teamA=players_teamA,
        players_teamB=players_teamB,
        team_a_name=team_a_name,
        team_b_name=team_b_name,
        team_a_pic=team_a_pic,
        team_b_pic=team_b_pic,
        current_innings=current_innings,
        overs1=overs1,
        overs2=overs2,
        selected_tab=selected_tab,
        # First innings
        batting_scores_1=batting_scores_1,
        bowling_scores_1=bowling_scores_1,
        extras_summary_1=extras_summary_1,
        extras_total_1=extras_total_1,
        # Second innings
        batting_scores_2=batting_scores_2,
        bowling_scores_2=bowling_scores_2,
        extras_summary_2=extras_summary_2,
        extras_total_2=extras_total_2,
        first_innings=first_innings,
        second_innings=second_innings
    )

@bp.route("/set_striker", methods=["POST"])
def set_striker():
    match_id = int(request.form.get("match_id"))
    pid = int(request.form.get("player_id"))
    selected_tab = request.form.get("selected_tab", "team_a")

    match = Match.query.get(match_id)
    if not match:
        flash("Match not found.", "danger")
        return redirect(url_for("scoreboard.scoreboard_page"))

    # innings_no = match.current_innings_no or 1
    innings_no = int(request.form.get("innings_no", match.current_innings_no))
    print(innings_no)

    # Determine which team is batting this innings
    if match.toss_decision == "bat":
        # resolve toss_winner string to Team.id
        team_obj = Team.query.filter_by(name=match.toss_winner).first()
        if not team_obj:
            team_obj = Team.query.filter_by(short_code=match.toss_winner).first()
        if not team_obj:
            flash(f"Invalid toss winner: {match.toss_winner}", "danger")
            return redirect(url_for("scoreboard.scoreboard", match_id=match.id))

        first_batting_team_id = team_obj.id
    else:
        # resolve toss_winner string to Team.id
        team_obj = Team.query.filter_by(name=match.toss_winner).first()
        if not team_obj:
            team_obj = Team.query.filter_by(short_code=match.toss_winner).first()
        if not team_obj:
            flash(f"Invalid toss winner: {match.toss_winner}", "danger")
            return redirect(url_for("scoreboard.scoreboard", match_id=match.id))

        toss_winner_id = team_obj.id
        first_batting_team_id = match.team_a_id if toss_winner_id == match.team_b_id else match.team_b_id

    # second batting team id is whichever is not first
    second_batting_team_id = (
        match.team_a_id if first_batting_team_id == match.team_b_id else match.team_b_id
    )

    # finally decide batting team for current innings
    batting_team_id = first_batting_team_id if innings_no == 1 else second_batting_team_id

    try:
        # Ensure score record exists for this batsman in this innings
        ms = MatchScore.query.filter_by(
            match_id=match.id,
            player_id=pid,
            innings_no=innings_no
        ).first()

        if not ms:
            ms = MatchScore(
                match_id=match.id,
                player_id=pid,
                innings_no=innings_no,
                team_id=batting_team_id
            )
            db.session.add(ms)

        match.current_on_strike_id = pid
        db.session.commit()
        flash("Striker set successfully!", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error setting striker: %s", e)
        flash("Failed to set striker.", "danger")

    return redirect(
        url_for("scoreboard.scoreboard", match_id=match_id, selected_tab=selected_tab)
    )
@bp.route("/set_non_striker", methods=["POST"])
def set_non_striker():
    match_id = int(request.form.get("match_id"))
    pid = int(request.form.get("player_id"))
    selected_tab = request.form.get("selected_tab", "team_a")

    match = Match.query.get(match_id)
    if not match:
        flash("Match not found.", "danger")
        return redirect(url_for("scoreboard.scoreboard_page"))

    # IMPORTANT: prefer innings_no from the form, fall back to match.current_innings_no
    innings_no = int(request.form.get("innings_no", match.current_innings_no or 1))

    # --- Resolve toss_winner string to Team.id ---
    toss_winner_str = match.toss_winner
    team_obj = Team.query.filter_by(name=toss_winner_str).first()
    if not team_obj:
        team_obj = Team.query.filter_by(short_code=toss_winner_str).first()
    if not team_obj:
        flash(f"Invalid toss winner: {toss_winner_str}", "danger")
        return redirect(url_for("scoreboard.scoreboard", match_id=match_id, selected_tab=selected_tab))
    toss_winner_id = team_obj.id

    # --- Determine batting side ---
    if match.toss_decision == "bat":
        first_batting_team_id = toss_winner_id
    else:
        first_batting_team_id = match.team_a_id if toss_winner_id == match.team_b_id else match.team_b_id

    second_batting_team_id = match.team_a_id if first_batting_team_id == match.team_b_id else match.team_b_id
    batting_team_id = first_batting_team_id if innings_no == 1 else second_batting_team_id

    try:
        score = MatchScore.query.filter_by(
            match_id=match.id,
            player_id=pid,
            innings_no=innings_no
        ).first()

        if not score:
            score = MatchScore(
                match_id=match.id,
                player_id=pid,
                innings_no=innings_no,
                team_id=batting_team_id
            )
            db.session.add(score)

        match.current_non_strike_id = pid
        db.session.commit()
        flash("Non-striker set successfully!", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error setting non-striker: %s", e)
        flash("Error setting non-striker.", "danger")

    return redirect(url_for("scoreboard.scoreboard", match_id=match_id, selected_tab=selected_tab))


@bp.route("/set_bowler", methods=["POST"])
def set_bowler():
    match_id = int(request.form.get("match_id"))
    pid = int(request.form.get("player_id"))
    selected_tab = request.form.get("selected_tab", "team_a")

    match = Match.query.get(match_id)
    if not match:
        flash("Match not found.", "danger")
        return redirect(url_for("scoreboard.scoreboard_page"))

    # IMPORTANT: prefer innings_no from the form, fall back to match.current_innings_no
    innings_no = int(request.form.get("innings_no", match.current_innings_no or 1))

    # --- Resolve toss_winner string to Team.id ---
    toss_winner_str = match.toss_winner
    team_obj = Team.query.filter_by(name=toss_winner_str).first()
    if not team_obj:
        team_obj = Team.query.filter_by(short_code=toss_winner_str).first()
    if not team_obj:
        flash(f"Invalid toss winner: {toss_winner_str}", "danger")
        return redirect(url_for("scoreboard.scoreboard", match_id=match_id, selected_tab=selected_tab))
    toss_winner_id = team_obj.id

    # --- Determine batting/bowling sides ---
    if match.toss_decision == "bat":
        first_batting_team_id = toss_winner_id
    else:
        first_batting_team_id = match.team_a_id if toss_winner_id == match.team_b_id else match.team_b_id

    second_batting_team_id = match.team_a_id if first_batting_team_id == match.team_b_id else match.team_b_id

    batting_team_id = first_batting_team_id if innings_no == 1 else second_batting_team_id
    bowling_team_id = second_batting_team_id if innings_no == 1 else first_batting_team_id

    try:
        score = MatchScore.query.filter_by(
            match_id=match.id,
            player_id=pid,
            innings_no=innings_no
        ).first()

        if not score:
            score = MatchScore(
                match_id=match.id,
                player_id=pid,
                innings_no=innings_no,
                team_id=bowling_team_id   # ensure bowler belongs to bowling team
            )
            db.session.add(score)

        match.current_bowler_id = pid
        db.session.commit()
        flash("Bowler set successfully!", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error setting bowler: %s", e)
        flash("Error setting bowler.", "danger")

    return redirect(url_for("scoreboard.scoreboard", match_id=match_id, selected_tab=selected_tab))



@bp.route("/update_score/<int:match_id>", methods=["POST"])
def update_score(match_id):
    match = Match.query.get(match_id)
    if not match:
        flash("Match not found.", "danger")
        return redirect(url_for("scoreboard.scoreboard_page"))

    if not match.toss_winner:
        flash("Toss not yet decided. Please set the toss first.", "info")
        return redirect(url_for("scoreboard.toss_page", match_id=match.id))

    # Update only FINAL match result fields
    match.winner_id = request.form.get("winner_id", type=int)
    match.points = request.form.get("points", type=int)

    db.session.commit()
    flash("Match result updated successfully!", "success")
    return redirect(url_for("scoreboard.scoreboard", match_id=match.id))


# ----------------------------
# Add Ball (DB-only)
# ----------------------------
@bp.route("/update_ball", methods=["POST"])
@bp.route("/update_ball", methods=["POST"])
def update_ball():
    print("DEBUG: entered update_ball route", flush=True)

    match_id = int(request.form.get("match_id"))
    match = Match.query.get(match_id)
    if not match:
        flash("Match not found.", "danger")
        return redirect(url_for("scoreboard.scoreboard_page"))

    selected_tab = request.form.get("selected_tab", "team_a")
    innings_no = int(request.form.get("innings_no") or match.current_innings_no or 1)

    # --- Resolve toss winner to team_id ---
    toss_team = Team.query.filter_by(name=match.toss_winner).first() or \
                Team.query.filter_by(short_code=match.toss_winner).first()

    if not toss_team:
        flash("Invalid toss winner.", "danger")
        return redirect(url_for("scoreboard.scoreboard", match_id=match.id))

    toss_winner_id = toss_team.id
    opponent_id = match.team_b_id if toss_winner_id == match.team_a_id else match.team_a_id

    # Determine innings batting/bowling teams
    if match.toss_decision == "bat":
        first_batting_team_id = toss_winner_id
        first_bowling_team_id = opponent_id
    else:
        first_batting_team_id = opponent_id
        first_bowling_team_id = toss_winner_id

    second_batting_team_id = first_bowling_team_id
    second_bowling_team_id = first_batting_team_id

    batting_team_id = first_batting_team_id if innings_no == 1 else second_batting_team_id
    bowling_team_id = first_bowling_team_id if innings_no == 1 else second_bowling_team_id

    # --- Batsman & Bowler ---
    batsman_id = request.form.get("batsman_player_id", type=int) or match.current_on_strike_id
    bowler_id = request.form.get("bowler_player_id", type=int) or match.current_bowler_id

    if not batsman_id or not bowler_id:
        flash("Select striker + bowler first.", "warning")
        return redirect(url_for("scoreboard.scoreboard", match_id=match.id, selected_tab=selected_tab))

    # --- Runs & extras ---
    runs_bat = request.form.get("runs_bat", type=int) or 0
    extras = {}
    for k in ["wd", "nb", "lb", "b"]:
        val = request.form.get(f"extras_{k}", type=int) or 0
        if val > 0:
            extras[k] = val

    total_runs = runs_bat + sum(extras.values())
    legal = not ("wd" in extras or "nb" in extras)
    wicket = request.form.get("wicket") in ("on", "1", "true", "True")
    dismissal_desc = request.form.get("dismissal_desc") or None

    try:
        # 1️⃣ Insert MatchBall
        mb = MatchBall(
            match_id=match.id,
            innings_no=innings_no,
            batsman_player_id=batsman_id,
            bowler_player_id=bowler_id,
            runs_bat=runs_bat,
            extras_json=json.dumps(extras),
            total_runs=total_runs,
            wicket=wicket,
            dismissal_desc=dismissal_desc
        )
        db.session.add(mb)

        # 2️⃣ Update batting record
        ms_bat = MatchScore.query.filter_by(
            match_id=match.id, innings_no=innings_no, player_id=batsman_id
        ).first()

        if not ms_bat:
            ms_bat = MatchScore(
                match_id=match.id,
                innings_no=innings_no,
                player_id=batsman_id,
                team_id=batting_team_id
            )
            db.session.add(ms_bat)

        ms_bat.batting_runs += runs_bat
        ms_bat.balls_faced += (1 if legal else 0)
        if runs_bat == 4:
            ms_bat.fours += 1
        if runs_bat == 6:
            ms_bat.sixes += 1
        if wicket:
            ms_bat.is_out = True
            ms_bat.dismissal_desc = dismissal_desc

        # 3️⃣ Update bowling record
        ms_bowl = MatchScore.query.filter_by(
            match_id=match.id, innings_no=innings_no, player_id=bowler_id
        ).first()

        if not ms_bowl:
            ms_bowl = MatchScore(
                match_id=match.id,
                innings_no=innings_no,
                player_id=bowler_id,
                team_id=bowling_team_id
            )
            db.session.add(ms_bowl)

        ms_bowl.runs_conceded += total_runs
        ms_bowl.overs_bowled += (1 if legal else 0)
        if wicket:
            ms_bowl.wickets_taken += 1

        # 4️⃣ Update match totals (correct innings!)
        if innings_no == 1:
            match.first_innings_score += total_runs
            match.first_innings_wickets += (1 if wicket else 0)
            match.first_innings_balls += (1 if legal else 0)

            if match.first_innings_balls > 0:
                match.first_innings_run_rate = round(
                    match.first_innings_score / (match.first_innings_balls / 6), 2
                )

        else:  # innings_no == 2
            match.second_innings_score += total_runs
            match.second_innings_wickets += (1 if wicket else 0)
            match.second_innings_balls += (1 if legal else 0)

            if match.second_innings_balls > 0:
                match.second_innings_run_rate = round(
                    match.second_innings_score / (match.second_innings_balls / 6), 2
                )

        # 5️⃣ Auto-change strike
        if legal:
            if total_runs % 2 == 1:
                match.current_on_strike_id, match.current_non_strike_id = \
                    match.current_non_strike_id, match.current_on_strike_id

            # End of over strike flip
            balls_now = match.first_innings_balls if innings_no == 1 else match.second_innings_balls
            if balls_now % 6 == 0:
                match.current_on_strike_id, match.current_non_strike_id = \
                    match.current_non_strike_id, match.current_on_strike_id

        # 6️⃣ **Innings switching logic**
        if innings_no == 1:
            innings_over = False

            # Wickets end innings
            if match.first_innings_wickets >= 10:
                innings_over = True

            # Overs limit end innings
            if match.overs_limit_innings1 and \
               (match.first_innings_balls // 6) >= match.overs_limit_innings1:
                innings_over = True

            if innings_over:
                match.current_innings_no = 2
                match.current_on_strike_id = None
                match.current_non_strike_id = None
                match.current_bowler_id = None
                flash("First innings complete. Second innings begins!", "info")

        db.session.commit()

        # Refresh auto-computed state
        rebuild_state_from_db(match.id)

        flash("Ball recorded successfully!", "success")

    except Exception as e:
        db.session.rollback()
        print("ERROR in update_ball:", e, flush=True)
        flash("Error recording ball.", "danger")

    return redirect(url_for("scoreboard.scoreboard", match_id=match.id, selected_tab=selected_tab))


# ----------------------------
# Edit/Delete Ball
# ----------------------------
@bp.route("/edit_ball", methods=["POST"])
def edit_ball():
    ball_id = int(request.form.get("ball_id"))
    runs = int(request.form.get("runs", 0))
    wicket = request.form.get("wicket") in ("1", "on", "true", "True")
    desc = request.form.get("desc") or ""

    mb = MatchBall.query.get(ball_id)
    if not mb:
        flash("Ball not found.", "danger")
        return redirect(request.referrer or url_for("scoreboard.scoreboard_page"))

    try:
        extras = _extras_from_mb(mb)
        mb.runs_bat = runs
        mb.total_runs = runs + sum(extras.values())
        mb.wicket = bool(wicket)
        mb.dismissal_desc = desc
        db.session.commit()
        rebuild_matchscore_from_balls(mb.match_id)
        flash("Ball updated!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error editing ball: %s", e)
        flash("Error updating ball.", "danger")

    return redirect(url_for("scoreboard.scoreboard", match_id=mb.match_id))


@bp.route("/delete_ball/<int:ball_id>", methods=["POST"])
def delete_ball(ball_id):
    mb = MatchBall.query.get(ball_id)
    if not mb:
        flash("Ball not found.", "danger")
        return redirect(request.referrer or url_for("scoreboard.scoreboard_page"))
    match_id = mb.match_id
    try:
        db.session.delete(mb)
        db.session.commit()
        rebuild_matchscore_from_balls(match_id)
        flash("Ball deleted!", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error deleting ball: %s", e)
        flash("Error deleting ball.", "danger")
    return redirect(url_for("scoreboard.scoreboard", match_id=match_id))


# ----------------------------
# Start second innings (manual button when first innings complete)
# ----------------------------
@bp.route("/start_second_innings", methods=["POST"])
def start_second_innings():
    match_id = int(request.form.get("match_id"))
    match = Match.query.get(match_id)
    if not match:
        flash("Match not found.", "danger")
        return redirect(url_for("scoreboard.scoreboard_page"))

    # set current innings to 2 and optionally set overs limit per innings2
    try:
        setattr(match, "current_innings_no", 2)
        db.session.commit()
        flash("Second innings started.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error starting 2nd innings: %s", e)
        flash("Could not start second innings.", "danger")

    return redirect(url_for("scoreboard.scoreboard", match_id=match_id))


# ----------------------------
# Finish match
# ----------------------------
@bp.route("/finish_match", methods=["POST"])
def finish_match():
    match_id = int(request.form.get("match_id"))
    match = Match.query.get(match_id)

    if not match:
        flash("Match not found.", "danger")
        return redirect(url_for('scoreboard.scoreboard', match_id=match_id))

    try:
        finalize_match_db(match_id)
        flash("Match finalized successfully!", "success")
    except Exception as e:
        current_app.logger.error(f"Error finalizing match: {e}")
        flash("Error finalizing match.", "danger")

    return redirect(url_for('scoreboard.scoreboard', match_id=match_id))


# ----------------------------
# Toss endpoints
# ----------------------------
@bp.route("/toss/<int:match_id>")
def toss_page(match_id):
    match = Match.query.get(match_id)
    if not match:
        flash("Match not found", "danger")
        return redirect(url_for("scoreboard.scoreboard_page"))
    team_a = Team.query.get(match.team_a_id).name if match.team_a_id else "Team A"
    team_b = Team.query.get(match.team_b_id).name if match.team_b_id else "Team B"
    return render_template("toss.html", match=match, team_a=team_a, team_b=team_b)


@bp.route("/submit_toss", methods=["POST"])
def submit_toss():
    match_id = int(request.form.get("match_id"))
    winner = request.form.get("toss_winner")
    decision = request.form.get("decision")
    match = Match.query.get(match_id)
    if not match:
        flash("Match not found", "danger")
        return redirect(url_for("scoreboard.scoreboard_page"))
    try:
        setattr(match, "toss_winner", winner)
        setattr(match, "toss_decision", decision)
        setattr(match, "current_innings_no", 1)
        # set default overs if provided
        try:
            o1 = int(request.form.get("overs_limit_innings1") or 0)
            o2 = int(request.form.get("overs_limit_innings2") or 0)
            if o1 > 0:
                setattr(match, "overs_limit_innings1", o1)
            if o2 > 0:
                setattr(match, "overs_limit_innings2", o2)
        except Exception:
            pass
        db.session.commit()
        flash("Toss saved.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error saving toss: %s", e)
        flash("Error saving toss.", "danger")
    return redirect(url_for("scoreboard.scoreboard", match_id=match_id))


@bp.route("/set_overs_limit", methods=["POST"])
def set_overs_limit():
    match_id = request.form.get("match_id")
    match = Match.query.get(match_id)

    if not match:
        flash("Match not found.", "danger")
        return redirect(url_for("scoreboard.scoreboard", match_id=match_id))

    # Parse overs limit
    try:
        overs_limit = int(request.form.get("overs_limit"))
    except (ValueError, TypeError):
        flash("Invalid overs limit.", "danger")
        return redirect(url_for("scoreboard.scoreboard", match_id=match_id))

    # Validate range
    if overs_limit <= 0 or overs_limit > 50:
        flash("Overs must be between 1 and 50.", "warning")
        return redirect(url_for("scoreboard.scoreboard", match_id=match_id))

    # 🔥 Save same overs limit for both innings
    match.overs_limit_innings1 = overs_limit
    match.overs_limit_innings2 = overs_limit

    db.session.commit()

    flash(f"Overs limit set to {overs_limit} overs for both innings.", "success")
    return redirect(url_for("scoreboard.scoreboard", match_id=match_id))



def finalize_match_db(match_id):
    match = Match.query.get(match_id)

    if not match:
        raise Exception("Match not found")

    # Fetch both innings results
    innings1 = MatchBall.query.filter_by(match_id=match_id, innings_no=1).first()
    innings2 = MatchBall.query.filter_by(match_id=match_id, innings_no=2).first()

    if not innings1 or not innings2:
        raise Exception("Both innings must be completed before finalizing the match")

    total1 = innings1.total_runs
    total2 = innings2.total_runs

    teama_id = match.team_a_id
    teamb_id = match.team_b_id

    # Fetch team objects from DB
    team_a = Team.query.get(teama_id) if teama_id else None
    team_b = Team.query.get(teamb_id) if teamb_id else None

    # Extract names safely
    team_a_name = team_a.name if team_a else "Team A"
    team_b_name = team_b.name if team_b else "Team B"

    # Compare totals for result
    if total1 > total2:
        diff = total1 - total2
        match.result = f"{team_a_name} won by {diff} runs"
    elif total2 > total1:
        wickets_left = 10 - innings2.wickets
        match.result = f"{team_b_name} won by {wickets_left} wickets"
    else:
        match.result = "Match tied"

    match.completed = True
    db.session.commit()


# ----------------------------
# Helper: build ball description
# ----------------------------
def build_ball_desc(runs_bat, extras, wicket):
    if wicket:
        return "W"
    parts = []
    if extras.get("wd"):
        parts.append(f"Wd{extras['wd']}")
    if extras.get("nb") is not None and extras.get("nb") != 0:
        nb = extras.get("nb")
        bat_note = f"+{runs_bat}" if runs_bat else ""
        parts.append(f"Nb{nb}{bat_note}")
    if extras.get("lb"):
        parts.append(f"LB{extras['lb']}")
    if extras.get("b"):
        parts.append(f"B{extras['b']}")
    if runs_bat and not extras.get("nb"):
        parts.append(str(runs_bat))
    return "+".join(parts) if parts else "0"


# ----------------------------
# Rebuild MatchScore / PlayerSeason / Points logic (reused/adapted)
# ----------------------------
def rebuild_matchscore_from_balls(match_id):
    MatchScore.query.filter_by(match_id=match_id).delete()
    db.session.flush()
    balls = MatchBall.query.filter_by(match_id=match_id).order_by(MatchBall.id).all()
    accum = {}
    for mb in balls:
        pid = mb.batsman_player_id
        if pid:
            key = (pid, mb.innings_no)
            d = accum.setdefault(key, {"bat_runs": 0, "balls": 0, "fours": 0, "sixes": 0})
            d["bat_runs"] += int(mb.runs_bat or 0)
            extras = _extras_from_mb(mb)
            is_legal = ("wd" not in extras) and ("nb" not in extras)
            if is_legal:
                d["balls"] += 1
            if (mb.runs_bat or 0) == 4:
                d["fours"] += 1
            if (mb.runs_bat or 0) == 6:
                d["sixes"] += 1
        bpid = mb.bowler_player_id
        if bpid:
            keyb = (bpid, mb.innings_no, "bowl")
            dbk = accum.setdefault(keyb, {"overs_bowled_balls": 0, "runs_conceded": 0, "wickets": 0})
            extras = _extras_from_mb(mb)
            is_legal = ("wd" not in extras) and ("nb" not in extras)
            if is_legal:
                dbk["overs_bowled_balls"] += 1
            dbk["runs_conceded"] += int(mb.total_runs or 0)
            if mb.wicket:
                dbk["wickets"] += 1

    for (player_id, innings_no), vals in list(accum.items()):
        if isinstance(innings_no, str) and innings_no == "bowl":
            continue
        ms = MatchScore(match_id=match_id, player_id=player_id, innings_no=innings_no)
        ms.batting_runs = vals.get("bat_runs", 0)
        ms.balls_faced = vals.get("balls", 0)
        ms.fours = vals.get("fours", 0)
        ms.sixes = vals.get("sixes", 0)
        bow_key = (player_id, innings_no, "bowl")
        bowlvals = accum.get(bow_key)
        if bowlvals:
            ms.overs_bowled = (bowlvals["overs_bowled_balls"] / 6.0)
            ms.runs_conceded = bowlvals["runs_conceded"]
            ms.wickets_taken = bowlvals["wickets"]
        db.session.add(ms)
    db.session.commit()

    # update PlayerSeason
    match = Match.query.get(match_id)
    if not match:
        return
    season_id = match.season_id
    mss = MatchScore.query.filter_by(match_id=match_id).all()
    for ms in mss:
        ps = PlayerSeason.query.filter_by(player_id=ms.player_id, season_id=season_id).first()
        if not ps:
            continue
        ps.matches_played = (ps.matches_played or 0) + 1
        ps.batting_runs = (ps.batting_runs or 0) + (ms.batting_runs or 0)
        ps.overs_bowled = (ps.overs_bowled or 0.0) + (ms.overs_bowled or 0.0)
        ps.wickets_taken = (ps.wickets_taken or 0) + (ms.wickets_taken or 0)
        ps.batting_average = (ps.batting_runs / ps.matches_played) if ps.matches_played else 0
        ps.bowling_average = (ps.runs_conceded / ps.wickets_taken) if ps.wickets_taken else 0
    db.session.commit()


# compute_innings_totals / compute_match_nrr / update_points_table_for_match (unchanged, reuse previous implementations)
def _balls_to_overs(balls: int) -> float:
    return balls / 6.0 if balls is not None else 0.0


def _pick_innings_team(match_id: int, innings_no: int):
    q = (
        db.session.query(Player.team_id, func.count(MatchScore.id).label("cnt"))
        .join(Player, Player.id == MatchScore.player_id)
        .filter(MatchScore.match_id == match_id, MatchScore.innings_no == innings_no)
        .group_by(Player.team_id)
        .order_by(func.count(MatchScore.id).desc())
    )
    row = q.first()
    return row[0] if row else None


def compute_innings_totals(match_id: int, innings_no: int):
    team_id = _pick_innings_team(match_id, innings_no)
    if not team_id:
        return {"team_id": None, "runs": 0, "balls": 0, "overs": 0.0, "wickets": 0}
    runs_sum = (
                   db.session.query(func.coalesce(func.sum(MatchScore.batting_runs), 0))
                   .join(Player, Player.id == MatchScore.player_id)
                   .filter(MatchScore.match_id == match_id, MatchScore.innings_no == innings_no,
                           Player.team_id == team_id)
                   .scalar()
               ) or 0
    balls_sum = (
                    db.session.query(func.coalesce(func.sum(MatchScore.balls_faced), 0))
                    .join(Player, Player.id == MatchScore.player_id)
                    .filter(MatchScore.match_id == match_id, MatchScore.innings_no == innings_no,
                            Player.team_id == team_id)
                    .scalar()
                ) or 0
    wickets_sum = (
                      db.session.query(func.coalesce(func.sum(MatchScore.wickets_taken), 0))
                      .join(Player, Player.id == MatchScore.player_id)
                      .filter(MatchScore.match_id == match_id, MatchScore.innings_no == innings_no,
                              Player.team_id == team_id)
                      .scalar()
                  ) or 0
    overs_decimal = _balls_to_overs(int(balls_sum))
    return {"team_id": team_id, "runs": int(runs_sum), "balls": int(balls_sum), "overs": overs_decimal,
            "wickets": int(wickets_sum)}


def compute_match_nrr(match_id: int):
    inn1 = compute_innings_totals(match_id, 1)
    inn2 = compute_innings_totals(match_id, 2)
    if not inn1["team_id"] or not inn2["team_id"]:
        return {}
    teamA = inn1["team_id"]
    teamB = inn2["team_id"]
    runs_A = inn1["runs"]
    overs_A = inn1["overs"] if inn1["overs"] > 0 else 0.0
    runs_B = inn2["runs"]
    overs_B = inn2["overs"] if inn2["overs"] > 0 else 0.0
    rr_A = (runs_A / overs_A) if overs_A > 0 else 0.0
    rr_B = (runs_B / overs_B) if overs_B > 0 else 0.0
    nrr_A = rr_A - rr_B
    nrr_B = rr_B - rr_A
    return {teamA: nrr_A, teamB: nrr_B}


def update_points_table_for_match(match_id: int, win_points=2, tie_points=1, loss_points=0):
    match = Match.query.get(match_id)
    if not match:
        return
    inn1 = compute_innings_totals(match_id, 1)
    inn2 = compute_innings_totals(match_id, 2)
    if not inn1["team_id"] or not inn2["team_id"]:
        return
    teamA_id = inn1["team_id"]
    teamB_id = inn2["team_id"]
    runs_A = inn1["runs"]
    runs_B = inn2["runs"]
    if runs_A > runs_B:
        winner_id = teamA_id
        loser_id = teamB_id
        is_tie = False
    elif runs_B > runs_A:
        winner_id = teamB_id
        loser_id = teamA_id
        is_tie = False
    else:
        winner_id = None
        loser_id = None
        is_tie = True

    def _get_or_create_points(season_id, team_id):
        pt = PointsTable.query.filter_by(season_id=match.season_id, team_id=team_id).first()
        if not pt:
            pt = PointsTable(season_id=match.season_id, team_id=team_id)
            db.session.add(pt)
            db.session.flush()
        return pt

    ptA = _get_or_create_points(match.season_id, teamA_id)
    ptB = _get_or_create_points(match.season_id, teamB_id)

    ptA.matches = (ptA.matches or 0) + 1
    ptB.matches = (ptB.matches or 0) + 1

    if is_tie:
        ptA.ties = (ptA.ties or 0) + 1
        ptB.ties = (ptB.ties or 0) + 1
        ptA.points = (ptA.points or 0) + tie_points
        ptB.points = (ptB.points or 0) + tie_points
    else:
        if winner_id == teamA_id:
            ptA.wins = (ptA.wins or 0) + 1
            ptB.losses = (ptB.losses or 0) + 1
            ptA.points = (ptA.points or 0) + win_points
            ptB.points = (ptB.points or 0) + loss_points
        else:
            ptB.wins = (ptB.wins or 0) + 1
            ptA.losses = (ptA.losses or 0) + 1
            ptB.points = (ptB.points or 0) + win_points
            ptA.points = (ptA.points or 0) + loss_points

    nrrs = compute_match_nrr(match_id)
    nrrA_match = nrrs.get(teamA_id, 0.0)
    nrrB_match = nrrs.get(teamB_id, 0.0)

    def _update_nrr_row(pt_row, this_nrr):
        prev_matches = (pt_row.matches - 1) if pt_row.matches and pt_row.matches > 0 else 0
        prev_nrr = pt_row.nrr or 0.0
        new_nrr = ((prev_nrr * prev_matches) + this_nrr) / (prev_matches + 1) if (prev_matches + 1) > 0 else this_nrr
        pt_row.nrr = new_nrr

    _update_nrr_row(ptA, nrrA_match)
    _update_nrr_row(ptB, nrrB_match)

    db.session.commit()
