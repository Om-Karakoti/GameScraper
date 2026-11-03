"""
APScheduler-based Scraping Scheduler
======================================
Manages periodic deal scraping, Steam enrichment, and price-alert checks
using APScheduler's BackgroundScheduler.
"""

import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import config
import database
from scraper import cheapshark, steam

logger = logging.getLogger(__name__)

# Lock to prevent overlapping runs of the main scrape job.
_scrape_lock = threading.Lock()

# Module-level scheduler reference so it can be shut down cleanly.
_scheduler = None


def start_scheduler(app):
    """
    Initialise and start the background scheduler.

    * Runs an initial scrape immediately (3 pages).
    * Schedules ``scrape_all_deals`` to repeat every
      ``config.SCRAPE_INTERVAL_MINUTES`` minutes.

    Parameters
    ----------
    app : flask.Flask
        The Flask application instance (needed for app context in jobs).
    """
    global _scheduler

    _scheduler = BackgroundScheduler(daemon=True)

    # Recurring job
    _scheduler.add_job(
        func=scrape_all_deals,
        trigger=IntervalTrigger(minutes=config.SCRAPE_INTERVAL_MINUTES),
        args=[app],
        id='scrape_all_deals',
        name='Scrape all deals from CheapShark',
        replace_existing=True,
        max_instances=1,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started – recurring scrape every %d minutes",
        config.SCRAPE_INTERVAL_MINUTES,
    )

    # Fire the initial scrape in a background thread so the app starts up
    # quickly while data is being fetched.
    threading.Thread(
        target=run_initial_scrape,
        args=(app,),
        name='InitialScrapeThread',
        daemon=True,
    ).start()


def run_initial_scrape(app):
    """
    One-time startup scrape: fetch 3 pages of deals and process them.

    Parameters
    ----------
    app : flask.Flask
        Flask app instance for establishing application context.
    """
    logger.info("Running initial scrape (3 pages) …")
    with app.app_context():
        total_processed = 0
        for page in range(3):
            try:
                deals = cheapshark.fetch_deals(page=page)
                if not deals:
                    logger.info("Initial scrape: no more deals at page %d", page)
                    break
                count = cheapshark.process_deals(deals)
                total_processed += count
            except Exception:
                logger.exception("Initial scrape error on page %d", page)

        logger.info("Initial scrape complete – %d deals processed", total_processed)

        # Quick enrichment pass for the freshly loaded games
        _enrich_batch(limit=20)

        # Check alerts against newly loaded prices
        try:
            triggered = database.check_alerts()
            if triggered:
                logger.info("Initial scrape triggered %d alert(s)", len(triggered))
        except Exception:
            logger.exception("Error checking alerts after initial scrape")


def scrape_all_deals(app):
    """
    Full scrape cycle (scheduled to run periodically):

    1. Fetch pages 0-4 of deals from CheapShark and process them.
    2. Enrich a batch of games that are missing genre/details via Steam.
    3. Check all active price alerts.

    Parameters
    ----------
    app : flask.Flask
        Flask app instance for application context.
    """
    if not _scrape_lock.acquire(blocking=False):
        logger.warning("scrape_all_deals skipped – previous run still in progress")
        return

    try:
        with app.app_context():
            logger.info("Scheduled scrape starting (pages 0–4) …")
            total_processed = 0

            for page in range(5):
                try:
                    deals = cheapshark.fetch_deals(page=page)
                    if not deals:
                        logger.info("No more deals at page %d – stopping", page)
                        break
                    count = cheapshark.process_deals(deals)
                    total_processed += count
                except Exception:
                    logger.exception("Error scraping deals page %d", page)

            logger.info("Deal scrape finished – %d deals processed", total_processed)

            # Enrich games missing detailed info
            _enrich_batch(limit=30)

            # Check price alerts
            try:
                triggered = database.check_alerts()
                if triggered:
                    logger.info("Scrape cycle triggered %d alert(s)", len(triggered))
            except Exception:
                logger.exception("Error checking alerts during scheduled scrape")

            logger.info("Scheduled scrape cycle complete")
    finally:
        _scrape_lock.release()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _enrich_batch(limit=30):
    """
    Fetch Steam details for up to *limit* games that are missing
    genre or description data and have a steam_app_id.
    """
    db = database.get_db()
    try:
        rows = db.execute(
            """
            SELECT id, title, steam_app_id
              FROM games
             WHERE steam_app_id IS NOT NULL
               AND steam_app_id != ''
               AND (genre IS NULL OR genre = '' OR description IS NULL OR description = '')
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        db.close()

    if not rows:
        logger.debug("No games to enrich")
        return

    enriched = 0
    for row in rows:
        try:
            if steam.enrich_game_data(row['id']):
                enriched += 1
        except Exception:
            logger.exception("Error enriching game %d (%s)", row['id'], row['title'])

    logger.info("Enriched %d / %d games via Steam API", enriched, len(rows))
