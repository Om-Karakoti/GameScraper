"""
GameScraper Flask Application
==============================
Entry point that creates, configures, and runs the Flask application.
Initialises the database, registers blueprints, starts the background
scraping scheduler, and kicks off an initial scrape on first launch.
"""

import os
import logging

from flask import Flask

from config import DATABASE_PATH
from database import init_db
from routes.api import api_bp
from routes.views import views_bp
from scraper.scheduler import start_scheduler


def create_app():
    """Application factory.

    Creates and configures the Flask app, initialises the SQLite database,
    registers API and view blueprints, starts the periodic scraping scheduler,
    and launches an initial background scrape.

    Returns:
        flask.Flask: The fully configured application instance.
    """
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.urandom(24).hex()
    app.config['DATABASE_PATH'] = DATABASE_PATH

    # ── Logging ──────────────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    # ── Database ─────────────────────────────────────────────────────────
    with app.app_context():
        init_db()

    # ── Blueprints ───────────────────────────────────────────────────────
    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    # ── Scheduler ────────────────────────────────────────────────────────
    start_scheduler(app)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000, use_reloader=False)
