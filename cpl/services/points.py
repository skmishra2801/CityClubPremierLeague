from cpl.models import PointsTable, Match
from cpl.services.ScoreSummary import parse_score_summary
from cpl.services.resetPointTables import reset_points_table
from extensions import db


def rebuild_points_table(season: int):
    # Reset all rows for this season
    reset_points_table(season)

    matches = Match.query.filter_by(season=season, status="Completed").all()
    # Track totals for NRR
    team_stats = {}
    for match in matches:
        # Ensure rows exist for both teams
        for team_id in [match.team_a_id, match.team_b_id]:
            row = PointsTable.query.filter_by(season=season, team_id=team_id).first()
            if not row:
                row = PointsTable(season=season, team_id=team_id)
                db.session.add(row)
                db.session.flush()
            # Initialize team stats if not already
            if team_id not in team_stats:
                team_stats[team_id] = {
                    "runs_scored": 0,
                    "overs_faced": 0.0,
                    "runs_conceded": 0,
                    "overs_bowled": 0.0,
                }

        # Apply outcome
        if match.winner_id:
            winner_id = match.winner_id
            loser_id = match.team_a_id if winner_id == match.team_b_id else match.team_b_id

            w_row = PointsTable.query.filter_by(season=season, team_id=winner_id).first()
            l_row = PointsTable.query.filter_by(season=season, team_id=loser_id).first()

            w_row.matches += 1
            w_row.wins += 1
            w_row.points += 2

            l_row.matches += 1
            l_row.losses += 1

        elif "tie" in (match.result or "").lower():
            for team_id in [match.team_a_id, match.team_b_id]:
                row = PointsTable.query.filter_by(season=season, team_id=team_id).first()
                row.matches += 1
                row.ties += 1
                row.points += 1

        elif "no result" in (match.result or "").lower():
            for team_id in [match.team_a_id, match.team_b_id]:
                row = PointsTable.query.filter_by(season=season, team_id=team_id).first()
                row.matches += 1
                row.nr += 1
                row.points += 1

        # NRR logic
        if match.score_summary:
            parsed = parse_score_summary(match.score_summary)
            if parsed:
                runs_a, overs_a, runs_b, overs_b = parsed
                # Team A stats
                team_stats[match.team_a_id]["runs_scored"] += runs_a
                team_stats[match.team_a_id]["overs_faced"] += overs_a
                team_stats[match.team_a_id]["runs_conceded"] += runs_b
                team_stats[match.team_a_id]["overs_bowled"] += overs_b

                # Team B stats
                team_stats[match.team_b_id]["runs_scored"] += runs_b
                team_stats[match.team_b_id]["overs_faced"] += overs_b
                team_stats[match.team_b_id]["runs_conceded"] += runs_a
                team_stats[match.team_b_id]["overs_bowled"] += overs_a

    # Final NRR calculation (after processing all matches)
    for team_id, stats in team_stats.items():
        row = PointsTable.query.filter_by(season=season, team_id=team_id).first()
        if row:
            if stats["overs_faced"] > 0 and stats["overs_bowled"] > 0:
                row.nrr = (stats["runs_scored"] / stats["overs_faced"]) - (
                        stats["runs_conceded"] / stats["overs_bowled"]
                )

    db.session.commit()
