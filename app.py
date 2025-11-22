from flask import Flask
from datetime import datetime
from config import Config
from extensions import db

# Blueprints
from cpl.blueprints.main import bp as main_bp
from cpl.blueprints.matches import bp as matches_bp
from cpl.blueprints.teams import bp as teams_bp
from cpl.blueprints.stats import bp as stats_bp
from cpl.blueprints.admin import bp as admin_bp
from cpl.blueprints.players import bp as players_bp
from cpl.blueprints.auction import bp as auction_bp
from cpl.blueprints.scoreboard import bp as scoreboard_bp



def create_app():
    app = Flask(__name__, static_folder="cpl/static", template_folder="cpl/templates")
    app.config.from_object(Config)
    db.init_app(app)

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(matches_bp, url_prefix="/matches")
    app.register_blueprint(teams_bp, url_prefix="/teams")
    app.register_blueprint(stats_bp, url_prefix="/stats")
    # app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(players_bp, url_prefix="/players")
    app.register_blueprint(auction_bp, url_prefix="/auction")
    app.register_blueprint(scoreboard_bp, url_prefix="/scoreboard")
    app.register_blueprint(admin_bp)

    # Create tables
    with app.app_context():
        db.create_all()

    # Global context (year for footer)
    @app.context_processor
    def inject_year():
        return {"year": datetime.utcnow().year}

    return app


app = create_app()
