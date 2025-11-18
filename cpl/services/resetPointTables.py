from cpl.models import PointsTable
from extensions import db


def reset_points_table(season: int):
    rows = PointsTable.query.filter_by(season=season).all()
    for row in rows:
        row.matches = 0
        row.wins = 0
        row.losses = 0
        row.ties = 0
        row.nr = 0
        row.points = 0
        row.nrr = 0.0
    db.session.commit()
