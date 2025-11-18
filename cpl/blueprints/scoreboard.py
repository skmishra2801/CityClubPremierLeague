from flask import render_template, Blueprint, url_for, redirect, request, flash

from cpl.models import Player, Match
from extensions import db

bp = Blueprint("scoreboard", __name__, url_prefix="/scoreboard")


match_store = {}


class Innings:
    def __init__(self, batting_team, bowling_team):
        self.batting_team = batting_team
        self.bowling_team = bowling_team
        self.total = 0
        self.wickets = 0
        self.overs_balls = 0  # total legal balls bowled
        self.batsmen = {}     # name -> Batsman
        self.bowlers = {}     # name -> Bowler
        self.on_strike = None
        self.non_strike = None
        self.current_bowler = None
        self.timeline = []    # list[BallEvent]
        self.over_events = {}  # over_idx -> list[BallEvent]

    @property
    def overs(self):
        return f"{self.overs_balls // 6}.{self.overs_balls % 6}"


class BallEvent:
    def __init__(self, over_num, ball_num, desc, runs, extras=None, wicket=False):
        self.over_num = over_num     # int (over index)
        self.ball_num = ball_num     # 1..6 or incremented for extra deliveries
        self.desc = desc             # short string for UI (e.g., "4", "W", "1lb", "Wd")
        self.runs = runs             # total runs added to team
        self.extras = extras or {}   # e.g., {"wd":1}, {"lb":1}, {"nb":1,"bat":2}
        self.wicket = wicket


class Bowler:
    def __init__(self, name):
        self.name = name
        self.overs_bowled_balls = 0  # track balls for partial overs
        self.runs_conceded = 0
        self.wickets = 0
        self.maidens = 0
        self.current_over_runs = 0

    @property
    def overs(self):
        return f"{self.overs_bowled_balls // 6}.{self.overs_bowled_balls % 6}"

    @property
    def economy(self):
        overs_decimal = self.overs_bowled_balls / 6 if self.overs_bowled_balls else 0
        return round(self.runs_conceded / overs_decimal, 2) if overs_decimal else 0.0


class Batsman:
    def __init__(self, name):
        self.name = name
        self.runs = 0
        self.balls = 0
        self.fours = 0
        self.sixes = 0
        self.out_desc = None

    @property
    def strike_rate(self):
        return round((self.runs / self.balls) * 100, 2) if self.balls else 0.0


def get_teams_from_match_schedule(match_id):
    match = Match.query.get(match_id)
    if match and "vs" in match.title:
        teamA, teamB = [team.strip() for team in match.title.split("vs")]
        return teamA, teamB
    return None, None


def get_players_by_team(team_id):
    players = Player.query.filter_by(team_id=team_id).all()
    return [p.name for p in players]


def ensure_batsman(name, innings):
    if name not in innings.batsmen:
        innings.batsmen[name] = Batsman(name)
    return innings.batsmen[name]


def ensure_bowler(name, innings):
    if name not in innings.bowlers:
        innings.bowlers[name] = Bowler(name)
    return innings.bowlers[name]


@bp.route("/")
def scoreboard_page():
    matches = Match.query.options(
        db.joinedload(Match.team_a),
        db.joinedload(Match.team_b)
    ).all()
    return render_template("scoreboard/list.html", matches=matches)


@bp.route("/scoreboard/<int:match_id>")
def scoreboard(match_id):
    match = Match.query.get(match_id)
    if not match:
        flash("⚠️ Could not find this match.", "danger")
        return redirect(url_for('matches.fixtures'))

    # ✅ Use team IDs directly
    players_teamA = get_players_by_team(match.team_a_id)
    players_teamB = get_players_by_team(match.team_b_id)

    # Initialize match store if not already
    if match_id not in match_store:
        match_store[match_id] = {
            "id": match_id,
            "innings": Innings(
                batting_team=match.team_a.name,  # assuming relationship
                bowling_team=match.team_b.name
            ),
            "overs_limit": 20
        }

    match_data = match_store[match_id]
    inns = match_data["innings"]
    batsmen = list(inns.batsmen.values())
    bowlers = list(inns.bowlers.values())

    return render_template(
        "scoreboard/scoreboard.html",
        match=match_data,
        inns=inns,
        batsmen=batsmen,
        bowlers=bowlers,
        players_teamA=players_teamA,
        players_teamB=players_teamB
    )
# @bp.route('/scoreboard/<int:match_id>')
# def scoreboard(match_id):
#     teamA, teamB = get_teams_from_match_schedule(match_id)
#     if not teamA or not teamB:
#         flash("⚠️ Could not find teams for this match.", "danger")
#         return redirect(url_for('matches.fixtures'))
#
#     players_teamA = get_players_by_team(teamA)
#     players_teamB = get_players_by_team(teamB)
#
#     if match_id not in match_store:
#         match_store[match_id] = {
#             "id": match_id,
#             "innings": Innings(batting_team=teamA, bowling_team=teamB),
#             "overs_limit": 20
#         }
#         inns = match_store[match_id]["innings"]
#         # set striker/non-striker and bowler as before...
#
#     match_data = match_store[match_id]
#     inns = match_data["innings"]
#     batsmen = list(inns.batsmen.values())
#     bowlers = list(inns.bowlers.values())
#
#     return render_template(
#         "scoreboard/scoreboard.html",
#         match=match_data,
#         inns=inns,
#         batsmen=batsmen,
#         bowlers=bowlers,
#         players_teamA=players_teamA,
#         players_teamB=players_teamB
#     )


@bp.route("/update_ball", methods=["POST"])
def update_ball():
    match_id = int(request.form.get("match_id"))
    inns = match_store[match_id]["innings"]
    runs_bat = int(request.form.get("runs_bat", 0))
    wd = int(request.form.get("extras_wd", 0))
    nb = int(request.form.get("extras_nb", 0))
    lb = int(request.form.get("extras_lb", 0))
    b = int(request.form.get("extras_b", 0))
    wicket = bool(request.form.get("wicket"))
    dismissal_desc = request.form.get("dismissal_desc") or None

    extras = {}

    if wd: extras["wd"] = wd
    if nb: extras["nb"] = nb
    if lb: extras["lb"] = lb
    if b:  extras["b"] = b

    apply_ball(inns, runs_bat=runs_bat, extras=extras, wicket=wicket, dismissal_desc=dismissal_desc)
    return redirect(url_for("scoreboard.scoreboard", match_id=match_id))


def apply_ball(innings, runs_bat=0, extras=None, wicket=False, dismissal_desc=None, switch_strike_on_odd=True):
    """
    Apply a ball to the given innings.
    extras: dict like {"wd":1} or {"nb":1, "lb":1} etc.
    wicket: bool (only one wicket per ball in this simple model)
    runs_bat: runs off the bat (0-6)
    """
    inns = innings
    extras = extras or {}

    striker = inns.batsmen[inns.on_strike]
    bowler = inns.bowlers[inns.current_bowler]

    # Determine if the ball counts as legal (wd and nb do not count as legal deliveries)
    is_legal = ("wd" not in extras) and ("nb" not in extras)

    # Compute total runs for team this ball
    total_runs = runs_bat + sum(extras.values())

    # Update team total
    inns.total += total_runs

    # Update batsman stats (only runs off bat count)
    if is_legal:
        striker.balls += 1
    striker.runs += runs_bat
    if runs_bat == 4:
        striker.fours += 1
    elif runs_bat == 6:
        striker.sixes += 1

    # Update bowler figures
    bowler.runs_conceded += total_runs
    if is_legal:
        bowler.overs_bowled_balls += 1
        bowler.current_over_runs += total_runs

    # Wicket handling
    if wicket:
        inns.wickets += 1
        bowler.wickets += 1
        # If dismissal_desc is just the batsman's name, ignore it
        if dismissal_desc and dismissal_desc.strip().lower() == striker.name.lower():
            striker.out_desc = f"b {bowler.name}"
        else:
            striker.out_desc = dismissal_desc or f"b {bowler.name}"

    # Strike rotation
    rotate_strike = False
    odd_runs_trigger = (runs_bat % 2 == 1)
    odd_extras_trigger = ((extras.get("lb", 0) + extras.get("b", 0)) % 2 == 1)
    if switch_strike_on_odd and is_legal and (odd_runs_trigger or odd_extras_trigger):
        rotate_strike = True

    # End of over: if legal ball was 6th in over, rotate strike and reset over runs
    over_idx = inns.overs_balls // 6
    ball_no_in_over = (inns.overs_balls % 6) + (1 if is_legal else 0)
    desc = build_ball_desc(runs_bat, extras, wicket)
    event = BallEvent(over_num=over_idx,
                      ball_num=ball_no_in_over,
                      desc=desc,
                      runs=total_runs,
                      extras=extras,
                      wicket=wicket)

    inns.timeline.append(event)
    inns.over_events.setdefault(over_idx, []).append(event)

    if is_legal:
        inns.overs_balls += 1

    # If over completes
    if inns.overs_balls % 6 == 0 and inns.overs_balls != 0:
        if bowler.current_over_runs == 0:
            bowler.maidens += 1
        bowler.current_over_runs = 0
        rotate_strike = not rotate_strike

    if rotate_strike:
        inns.on_strike, inns.non_strike = inns.non_strike, inns.on_strike


def build_ball_desc(runs_bat, extras, wicket):
    if wicket:
        return "W"
    parts = []
    if "wd" in extras:
        parts.append(f"Wd{extras['wd']}")
    if "nb" in extras:
        nb = extras["nb"]
        bat_note = f"+{runs_bat}" if runs_bat else ""
        parts.append(f"Nb{nb}{bat_note}")
    if "lb" in extras:
        parts.append(f"LB{extras['lb']}")
    if "b" in extras:
        parts.append(f"B{extras['b']}")
    if runs_bat and "nb" not in extras:
        parts.append(str(runs_bat))
    return "+".join(parts) if parts else "0"


@bp.route("/set_striker", methods=["POST"])
def set_striker():
    match_id = int(request.form.get("match_id"))
    name = request.form.get("name")
    inns = match_store[match_id]["innings"]
    ensure_batsman(name, inns)
    inns.on_strike = name
    return redirect(url_for("scoreboard.scoreboard", match_id=match_id))


@bp.route("/set_non_striker", methods=["POST"])
def set_non_striker():
    match_id = int(request.form.get("match_id"))
    name = request.form.get("name")
    inns = match_store[match_id]["innings"]
    ensure_batsman(name, inns)
    inns.non_strike = name
    return redirect(url_for("scoreboard.scoreboard", match_id=match_id))


@bp.route("/set_bowler", methods=["POST"])
def set_bowler():
    match_id = int(request.form.get("match_id"))
    name = request.form.get("name")
    inns = match_store[match_id]["innings"]
    ensure_bowler(name, inns)
    inns.current_bowler = name
    return redirect(url_for("scoreboard.scoreboard", match_id=match_id))
