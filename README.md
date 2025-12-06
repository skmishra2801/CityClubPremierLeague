# Scoreboard — In-memory innings version

Files provided:
- `app/scoreboard.py` — Flask blueprint (replace your existing scoreboard blueprint)
- `templates/scoreboard/scoreboard.html` — Scoreboard template
- `static/css/score.css` — Styles for the scoreboard

Notes:
- This uses an in-memory `match_store` (Python dict). It does NOT persist innings to the DB.
- Player select dropdowns use `PlayerSeason.player.name`. Ensure your `PlayerSeason` model has a `player` relationship.
- Routes:
  - `GET /scoreboard/<match_id>` — show scoreboard (initialize match_store entry if absent)
  - `POST /scoreboard/set_striker` — set striker
  - `POST /scoreboard/set_non_striker` — set non-striker
  - `POST /scoreboard/set_bowler` — set bowler
  - `POST /scoreboard/set_overs_limit` — set overs for current match/innings
  - `POST /scoreboard/update_ball` — submit a ball
  - `POST /scoreboard/start_second_innings` — start the second innings after first finishes

Testing checklist:
1. Open a match scoreboard URL (e.g., `/scoreboard/1`) — UI initializes.
2. Set striker and bowler.
3. Record balls; totals and overs should update.
4. Set overs_limit via the form to test innings end.
5. When innings finishes (overs limit reached or 10 wickets), banner appears and inputs are disabled. Click Start 2nd Innings to continue.

If you want persistence (store innings to DB) say so and I'll provide the SQLAlchemy model + migration script.
