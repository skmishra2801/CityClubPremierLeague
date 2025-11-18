from app import app
from extensions import db
# from cpl.models_backup import Team, Player, Match, News, Video, PointsTable
# from datetime import datetime, timedelta

with app.app_context():
    db.drop_all()
    db.create_all()

    # teams = [
    #     Team(name="Aahan", short_code="BBZ", city="Bhubaneswar", founded=2015, coach="A. Pradhan",
    #          logo_url="/static/images/Aahan.png"),
    #     Team(name="NSOLN", short_code="CCR", city="Cuttack", founded=2016, coach="S. Mishra",
    #          logo_url="/static/images/NSOLN.png"),
    #     Team(name="Thunder Strikers", short_code="CCR", city="Cuttack", founded=2016, coach="S. Mishra",
    #          logo_url="/static/images/Thunder Strikers.png"),
    #     Team(name="Vision Shilpi", short_code="CCR", city="Cuttack", founded=2016, coach="S. Mishra",
    #          logo_url="/static/images/Vision Shilpi.png"),
    # ]
    # db.session.add_all(teams); db.session.commit()

    # players = [
    #     Player(name="R. Das", role="Batter", nationality="India", team_id=teams[0].id),
    #     Player(name="K. Patnaik", role="Bowler", nationality="India", team_id=teams[0].id),
    #     Player(name="V. Sahu", role="All-rounder", nationality="India", team_id=teams[1].id),
    #     Player(name="M. Tripathi", role="Wicket-keeper", nationality="India", team_id=teams[1].id),
    # ]
    # db.session.add_all(players)

    # matches = [
    #     Match(title="BBZ vs CCR", venue="Kalinga Stadium", match_date=datetime.utcnow()+timedelta(days=1), team_a_id=teams[0].id, team_b_id=teams[1].id, status="Scheduled"),
    #     Match(title="CCR vs BBZ", venue="Barabati Stadium", match_date=datetime.utcnow()-timedelta(days=3), team_a_id=teams[1].id, team_b_id=teams[0].id, status="Completed", result="BBZ won by 5 wickets", score_summary="BBZ 168/5 (19.2) · CCR 165/7 (20)"),
    # ]
    # db.session.add_all(matches)

    # news = [
    #     News(title="Season Kickoff Announced", slug="season-kickoff", summary="Opening ceremony details and fixtures released.", body="<p>The season kicks off next week with a grand ceremony.</p>", image_url="/static/images/logo_cpl.png"),
    #     News(title="Captaincy Update", slug="captaincy-update", summary="Leadership changes across teams.", body="<p>Teams announced their captains ahead of the season.</p>", image_url="/static/images/logo_cpl.png"),
    # ]
    # db.session.add_all(news)
    #
    # videos = [
    #     Video(title="Behind the Scenes with BBZ", url="https://example.com/video1", thumbnail_url="/static/images/logo_cpl.png", duration_seconds=143),
    #     Video(title="CCR Training Highlights", url="https://example.com/video2", thumbnail_url="/static/images/logo_cpl.png", duration_seconds=231),
    # ]
    # db.session.add_all(videos)

    # pts = [
    #     PointsTable(season=2025, team_id=teams[0].id, matches=2, wins=1, losses=1, ties=0, nr=0, points=2, nrr=0.115),
    #     PointsTable(season=2025, team_id=teams[1].id, matches=2, wins=1, losses=1, ties=0, nr=0, points=2, nrr=-0.115),
    # ]
    # db.session.add_all(pts)

    db.session.commit()
    print("✅ Seed data loaded.")
