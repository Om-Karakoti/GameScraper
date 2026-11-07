"""
GameScraper Database Module
============================
SQLite database layer with full CRUD operations for games, prices, wishlists, and alerts.
"""

import sqlite3
import logging
from datetime import datetime, timedelta

from config import (
    DATABASE_PATH,
    POPULARITY_MIN_RATING,
    POPULARITY_MIN_REVIEWS,
    SUPPORTED_STORES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    logo_url TEXT,
    icon_url TEXT,
    website_url TEXT
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    cheapshark_id TEXT UNIQUE,
    steam_app_id TEXT,
    thumb_url TEXT,
    large_image_url TEXT,
    metacritic_score INTEGER,
    metacritic_url TEXT,
    steam_rating_percent INTEGER,
    steam_rating_count INTEGER,
    release_date TEXT,
    genre TEXT,
    publisher TEXT,
    developer TEXT,
    platform TEXT DEFAULT 'PC',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    store_id INTEGER NOT NULL,
    current_price REAL,
    original_price REAL,
    discount_percent INTEGER DEFAULT 0,
    deal_id TEXT,
    deal_url TEXT,
    is_on_sale INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY (store_id) REFERENCES stores(id),
    UNIQUE(game_id, store_id)
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    store_id INTEGER NOT NULL,
    price REAL NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY (store_id) REFERENCES stores(id)
);

CREATE TABLE IF NOT EXISTS wishlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL UNIQUE,
    notes TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS price_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    target_price REAL NOT NULL,
    is_active INTEGER DEFAULT 1,
    is_triggered INTEGER DEFAULT 0,
    triggered_at TIMESTAMP,
    triggered_price REAL,
    triggered_store TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);
"""


# ---------------------------------------------------------------------------
# Initialisation helpers
# ---------------------------------------------------------------------------

def init_db():
    """Create all tables and seed the stores table from config and API."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(_SCHEMA)

    game_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(games)")
    }
    if 'steam_rating_percent' not in game_columns:
        conn.execute("ALTER TABLE games ADD COLUMN steam_rating_percent INTEGER")
    if 'steam_rating_count' not in game_columns:
        conn.execute("ALTER TABLE games ADD COLUMN steam_rating_count INTEGER")

    # Seed stores from config
    for store_id, store_name in SUPPORTED_STORES.items():
        conn.execute(
            "INSERT OR IGNORE INTO stores (id, name) VALUES (?, ?)",
            (store_id, store_name),
        )

    conn.commit()
    conn.close()

    # Automatically fetch and sync all active stores from CheapShark
    sync_stores_from_api()
    logger.info("Database initialised and stores seeded.")


STORE_WEBSITES = {
    1: 'https://store.steampowered.com',
    2: 'https://www.gamersgate.com',
    3: 'https://www.greenmangaming.com',
    4: 'https://www.amazon.com',
    5: 'https://www.gamestop.com',
    6: 'https://www.direct2drive.com',
    7: 'https://www.gog.com',
    8: 'https://www.ea.com',
    9: 'http://www.getgamesgo.com',
    10: 'http://www.shinyloot.com',
    11: 'https://www.humblebundle.com/store',
    12: 'http://www.desura.com',
    13: 'https://store.ubisoft.com',
    14: 'https://indiegamestand.com',
    15: 'https://www.fanatical.com',
    16: 'https://www.gamesrocket.com',
    17: 'https://gamesrepublic.com',
    18: 'https://store.silagames.com',
    19: 'https://playfield.io',
    20: 'https://www.imperialgames.com',
    21: 'https://www.wingamestore.com',
    22: 'https://funstock.co.uk',
    23: 'https://www.gamebillet.com',
    24: 'https://www.voidu.com',
    25: 'https://store.epicgames.com',
    26: 'https://www.razer.com',
    27: 'https://us.gamesplanet.com',
    28: 'https://www.dlgamer.com',
    29: 'https://2game.com',
    30: 'https://www.indiegala.com',
    31: 'https://battle.net',
    32: 'https://www.allyouplay.com',
    33: 'https://www.dlgamer.com',
    34: 'https://noctre.com',
    35: 'https://www.dreamgame.com',
}


def sync_stores_from_api():
    """Fetch stores from CheapShark /stores and insert/update them in DB."""
    try:
        from scraper import cheapshark
        stores = cheapshark.fetch_stores()
        if not stores:
            return
        conn = sqlite3.connect(DATABASE_PATH)
        for s in stores:
            s_id = int(s.get('storeID', 0))
            s_name = s.get('storeName', f'Store #{s_id}')
            images = s.get('images', {})
            logo_url = f"https://www.cheapshark.com{images.get('logo', '')}" if images.get('logo') else None
            icon_url = f"https://www.cheapshark.com{images.get('icon', '')}" if images.get('icon') else None
            website_url = STORE_WEBSITES.get(s_id)
            conn.execute(
                """
                INSERT INTO stores (id, name, logo_url, icon_url, website_url)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    logo_url = COALESCE(excluded.logo_url, stores.logo_url),
                    icon_url = COALESCE(excluded.icon_url, stores.icon_url),
                    website_url = COALESCE(excluded.website_url, stores.website_url)
                """,
                (s_id, s_name, logo_url, icon_url, website_url)
            )
        conn.commit()
        conn.close()
        logger.info("Synced %d stores from CheapShark API", len(stores))
    except Exception as exc:
        logger.warning("Could not sync stores from CheapShark API: %s", exc)


def get_db():
    """Return a new connection with Row factory enabled."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# ---------------------------------------------------------------------------
# Game CRUD
# ---------------------------------------------------------------------------

def get_game_by_id(game_id):
    """Get a game by its internal ID, including its current best price."""
    db = get_db()
    try:
        row = db.execute(
            """
            SELECT g.*,
                   MIN(p.current_price) AS best_price,
                   p.store_id           AS best_store_id,
                   s.name               AS best_store_name,
                   s.logo_url           AS best_store_logo,
                   s.icon_url           AS best_store_icon,
                   s.website_url        AS best_store_website,
                   p.deal_url           AS best_deal_url,
                   p.discount_percent   AS best_discount
              FROM games g
         LEFT JOIN prices p ON p.game_id = g.id
         LEFT JOIN stores s ON s.id = p.store_id
             WHERE g.id = ?
          GROUP BY g.id
            """,
            (game_id,),
        ).fetchone()
        if not row:
            return None
        return _add_popularity_flag(dict(row))
    finally:
        db.close()


def _add_popularity_flag(game):
    """Mark games popular when they have broad and positive Steam reviews."""
    try:
        review_count = int(game.get('steam_rating_count') or 0)
        rating_percent = int(game.get('steam_rating_percent') or 0)
    except (TypeError, ValueError):
        review_count = 0
        rating_percent = 0
    game['is_popular'] = (
        review_count >= POPULARITY_MIN_REVIEWS
        and rating_percent >= POPULARITY_MIN_RATING
    )
    return game


def get_game_by_cheapshark_id(cs_id):
    """Look up a game by its CheapShark game ID."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT * FROM games WHERE cheapshark_id = ?", (cs_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def upsert_game(game_data):
    """
    Insert or update a game record.

    Parameters
    ----------
    game_data : dict
        Must include 'title'. Optional keys: cheapshark_id, steam_app_id,
        thumb_url, large_image_url, metacritic_score, metacritic_url,
        steam_rating_percent, steam_rating_count, release_date, genre,
        publisher, developer, platform, description.

    Returns
    -------
    int
        The game's row id.
    """
    db = get_db()
    try:
        cs_id = game_data.get('cheapshark_id')
        existing = None
        if cs_id:
            existing = db.execute(
                "SELECT id FROM games WHERE cheapshark_id = ?", (cs_id,)
            ).fetchone()

        if existing:
            game_id = existing['id']
            fields_to_update = {}
            for key in (
                'title', 'steam_app_id', 'thumb_url', 'large_image_url',
                'metacritic_score', 'metacritic_url', 'steam_rating_percent',
                'steam_rating_count', 'release_date', 'genre', 'publisher',
                'developer', 'platform', 'description',
            ):
                if key in game_data and game_data[key] is not None:
                    fields_to_update[key] = game_data[key]

            if fields_to_update:
                fields_to_update['updated_at'] = datetime.utcnow().isoformat()
                set_clause = ', '.join(f"{k} = ?" for k in fields_to_update)
                values = list(fields_to_update.values()) + [game_id]
                db.execute(
                    f"UPDATE games SET {set_clause} WHERE id = ?", values
                )
                db.commit()
            return game_id
        else:
            cols = ['title']
            vals = [game_data['title']]
            update_assignments = []
            for key in (
                'cheapshark_id', 'steam_app_id', 'thumb_url',
                'large_image_url', 'metacritic_score', 'metacritic_url',
                'steam_rating_percent', 'steam_rating_count', 'release_date',
                'genre', 'publisher', 'developer', 'platform', 'description',
            ):
                if key in game_data and game_data[key] is not None:
                    cols.append(key)
                    vals.append(game_data[key])
                    if key != 'cheapshark_id':
                        update_assignments.append(f"{key} = COALESCE(excluded.{key}, games.{key})")

            update_assignments.append("title = excluded.title")
            update_assignments.append("updated_at = CURRENT_TIMESTAMP")
            placeholders = ', '.join('?' for _ in cols)
            col_names = ', '.join(cols)
            update_str = ', '.join(update_assignments)

            if cs_id:
                cursor = db.execute(
                    f"""
                    INSERT INTO games ({col_names}) VALUES ({placeholders})
                    ON CONFLICT(cheapshark_id) DO UPDATE SET {update_str}
                    """,
                    vals,
                )
                db.commit()
                # If updated, cursor.lastrowid might be 0 in SQLite; query it
                if cursor.lastrowid:
                    return cursor.lastrowid
                row = db.execute("SELECT id FROM games WHERE cheapshark_id = ?", (cs_id,)).fetchone()
                return row['id']
            else:
                cursor = db.execute(
                    f"INSERT INTO games ({col_names}) VALUES ({placeholders})",
                    vals,
                )
                db.commit()
                return cursor.lastrowid
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Price CRUD
# ---------------------------------------------------------------------------

def upsert_price(game_id, store_id, current_price, original_price,
                 discount, deal_id, deal_url):
    """
    Insert or update a price record for a game/store pair.
    If the price has changed, a row is also appended to price_history.
    """
    db = get_db()
    try:
        current_price = float(current_price) if current_price is not None else 0.0
        original_price = float(original_price) if original_price is not None else 0.0
        discount = int(float(discount)) if discount is not None else 0
        store_id = int(store_id)
        is_on_sale = 1 if discount > 0 else 0

        existing = db.execute(
            "SELECT id, current_price FROM prices WHERE game_id = ? AND store_id = ?",
            (game_id, store_id),
        ).fetchone()

        now = datetime.utcnow().isoformat()

        if existing:
            old_price = existing['current_price']
            db.execute(
                """
                UPDATE prices
                   SET current_price   = ?,
                       original_price  = ?,
                       discount_percent = ?,
                       deal_id         = ?,
                       deal_url        = ?,
                       is_on_sale      = ?,
                       last_updated    = ?
                 WHERE id = ?
                """,
                (current_price, original_price, discount, deal_id,
                 deal_url, is_on_sale, now, existing['id']),
            )
            # Record history if price actually changed
            if old_price is None or abs(old_price - current_price) > 0.001:
                db.execute(
                    """
                    INSERT INTO price_history (game_id, store_id, price, recorded_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (game_id, store_id, current_price, now),
                )
        else:
            db.execute(
                """
                INSERT INTO prices
                    (game_id, store_id, current_price, original_price,
                     discount_percent, deal_id, deal_url, is_on_sale, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (game_id, store_id, current_price, original_price,
                 discount, deal_id, deal_url, is_on_sale, now),
            )
            # First price record goes to history too
            db.execute(
                """
                INSERT INTO price_history (game_id, store_id, price, recorded_at)
                VALUES (?, ?, ?, ?)
                """,
                (game_id, store_id, current_price, now),
            )

        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Deals listing
# ---------------------------------------------------------------------------

def get_deals(page=1, limit=20, sort_by='discount', min_discount=0,
              store_id=None, min_price=None, max_price=None,
              genre=None, free_only=False, popular_only=False, search_query=None):
    """
    Return paginated deals joined with game and store data.

    Returns
    -------
    tuple[list[dict], int]
        (list of deal dicts, total count matching filters)
    """
    db = get_db()
    try:
        conditions = [] if popular_only else ["p.is_on_sale = 1"]
        params = []

        if popular_only:
            conditions.extend((
                "COALESCE(g.steam_rating_count, 0) >= ?",
                "COALESCE(g.steam_rating_percent, 0) >= ?",
            ))
            params.extend((POPULARITY_MIN_REVIEWS, POPULARITY_MIN_RATING))

        if min_discount and int(min_discount) > 0:
            conditions.append("p.discount_percent >= ?")
            params.append(int(min_discount))

        if store_id:
            conditions.append("p.store_id = ?")
            params.append(int(store_id))

        if min_price is not None:
            conditions.append("p.current_price >= ?")
            params.append(float(min_price))

        if max_price is not None:
            conditions.append("p.current_price <= ?")
            params.append(float(max_price))

        if genre:
            conditions.append("g.genre LIKE ?")
            params.append(f"%{genre}%")

        if search_query and search_query.strip():
            escaped_query = search_query.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            conditions.append("g.title LIKE ? ESCAPE ?")
            params.extend((f"%{escaped_query}%", '\\'))

        if free_only:
            conditions.append("p.current_price = 0")

        where = " AND ".join(conditions)

        order_map = {
            'discount': 'p.discount_percent DESC',
            'price_asc': 'p.current_price ASC',
            'price_desc': 'p.current_price DESC',
            'title': 'g.title ASC',
            'metacritic': 'g.metacritic_score DESC',
            'newest': 'p.last_updated DESC',
            'popularity': 'g.steam_rating_count DESC, g.steam_rating_percent DESC, p.discount_percent DESC',
        }
        order = order_map.get(sort_by, 'p.discount_percent DESC')

        if popular_only:
            ranked_popular_prices = f"""
                WITH ranked_prices AS (
                    SELECT p.id AS price_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY p.game_id
                               ORDER BY p.current_price ASC,
                                        p.discount_percent DESC,
                                        p.last_updated DESC,
                                        p.id ASC
                           ) AS game_rank
                      FROM prices p
                      JOIN games g ON g.id = p.game_id
                     WHERE {where}
                )
            """
            count_query = ranked_popular_prices + """
                SELECT COUNT(*) AS cnt
                  FROM ranked_prices
                 WHERE game_rank = 1
            """
        else:
            ranked_popular_prices = ""
            count_query = f"""
                SELECT COUNT(*) AS cnt
                  FROM prices p
                  JOIN games g ON g.id = p.game_id
                 WHERE {where}
            """

        count_row = db.execute(count_query, params).fetchone()
        total = count_row['cnt'] if count_row else 0

        offset = (max(1, int(page)) - 1) * int(limit)

        if popular_only:
            rows_query = ranked_popular_prices + f"""
            SELECT g.*, p.current_price, p.original_price,
                   p.discount_percent, p.deal_id, p.deal_url,
                   p.is_on_sale, p.last_updated AS price_updated,
                   s.name AS store_name, s.id AS store_id,
                   s.logo_url AS store_logo_url, s.icon_url AS store_icon_url,
                   s.website_url AS store_website_url
              FROM prices p
              JOIN ranked_prices rp ON rp.price_id = p.id AND rp.game_rank = 1
              JOIN games g ON g.id = p.game_id
              JOIN stores s ON s.id = p.store_id
          ORDER BY {order}
             LIMIT ? OFFSET ?
            """
        else:
            rows_query = f"""
            SELECT g.*, p.current_price, p.original_price,
                   p.discount_percent, p.deal_id, p.deal_url,
                   p.is_on_sale, p.last_updated AS price_updated,
                   s.name AS store_name, s.id AS store_id,
                   s.logo_url AS store_logo_url, s.icon_url AS store_icon_url,
                   s.website_url AS store_website_url
              FROM prices p
              JOIN games g ON g.id = p.game_id
              JOIN stores s ON s.id = p.store_id
             WHERE {where}
          ORDER BY {order}
             LIMIT ? OFFSET ?
            """

        rows = db.execute(
            rows_query,
            params + [int(limit), offset],
        ).fetchall()

        deals_list = [_add_popularity_flag(dict(r)) for r in rows]
        return {'deals': deals_list, 'total': total}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_games(query, limit=20):
    """Search games by title using LIKE."""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT g.*,
                   MIN(p.current_price) AS best_price,
                   s.name               AS best_store_name,
                   s.logo_url           AS best_store_logo,
                   s.icon_url           AS best_store_icon,
                   s.website_url        AS best_store_website,
                   p.deal_url           AS best_deal_url,
                   p.discount_percent   AS best_discount
              FROM games g
         LEFT JOIN prices p ON p.game_id = g.id
         LEFT JOIN stores s ON s.id = p.store_id
             WHERE g.title LIKE ?
          GROUP BY g.id
          ORDER BY g.title ASC
             LIMIT ?
            """,
            (f"%{query}%", int(limit)),
        ).fetchall()
        return [_add_popularity_flag(dict(r)) for r in rows]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Prices & history
# ---------------------------------------------------------------------------

def get_game_prices(game_id):
    """Get all store prices for a given game."""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT p.*, s.name AS store_name, s.logo_url AS store_logo_url,
                   s.icon_url AS store_icon_url, s.website_url AS store_website_url
              FROM prices p
              JOIN stores s ON s.id = p.store_id
             WHERE p.game_id = ?
          ORDER BY p.current_price ASC
            """,
            (game_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def get_price_history(game_id, store_id=None, days=90):
    """
    Return historical price points for a game.
    Optionally filter by store and limit to the last N days.
    """
    db = get_db()
    try:
        params = [game_id]
        store_filter = ""
        if store_id:
            store_filter = " AND ph.store_id = ?"
            params.append(int(store_id))
        rows = db.execute(
            """
            SELECT ph.*, s.name AS store_name
              FROM price_history ph
              JOIN stores s ON s.id = ph.store_id
             WHERE ph.game_id = ?""" + store_filter + """
          ORDER BY ph.recorded_at ASC, ph.id ASC
            """,
            params,
        ).fetchall()
        history = []
        previous_prices = {}
        cutoff = None
        if days:
            cutoff = (datetime.utcnow() - timedelta(days=int(days))).isoformat()

        for row in rows:
            point = dict(row)
            previous_price = previous_prices.get(point['store_id'])
            point['previous_price'] = previous_price
            point['price_change'] = (
                round(point['price'] - previous_price, 2)
                if previous_price is not None else None
            )
            point['change_type'] = None
            if point['price_change'] is not None:
                if point['price_change'] > 0:
                    point['change_type'] = 'increase'
                elif point['price_change'] < 0:
                    point['change_type'] = 'decrease'
            previous_prices[point['store_id']] = point['price']
            if cutoff is None or point['recorded_at'] >= cutoff:
                history.append(point)
        return history
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------

def get_wishlist():
    """Return all wishlisted games with their current best price."""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT w.id AS wishlist_id, w.notes, w.added_at,
                   g.*,
                   MIN(p.current_price) AS best_price,
                   s.name               AS best_store_name,
                   s.logo_url           AS best_store_logo,
                   s.icon_url           AS best_store_icon,
                   s.website_url        AS best_store_website,
                   p.deal_url           AS best_deal_url,
                   p.discount_percent   AS best_discount
              FROM wishlist w
              JOIN games g ON g.id = w.game_id
         LEFT JOIN prices p ON p.game_id = g.id
         LEFT JOIN stores s ON s.id = p.store_id
          GROUP BY g.id
          ORDER BY w.added_at DESC
            """,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def add_to_wishlist(game_id, notes=None):
    """Add a game to the wishlist. Returns True on success, False if already present."""
    db = get_db()
    try:
        db.execute(
            "INSERT OR IGNORE INTO wishlist (game_id, notes) VALUES (?, ?)",
            (game_id, notes),
        )
        db.commit()
        return db.total_changes > 0
    finally:
        db.close()


def remove_from_wishlist(game_id):
    """Remove a game from the wishlist."""
    db = get_db()
    try:
        db.execute("DELETE FROM wishlist WHERE game_id = ?", (game_id,))
        db.commit()
    finally:
        db.close()


def is_in_wishlist(game_id):
    """Check whether a game is in the wishlist."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT 1 FROM wishlist WHERE game_id = ?", (game_id,)
        ).fetchone()
        return row is not None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Price Alerts
# ---------------------------------------------------------------------------

def get_alerts():
    """Return all price alerts with associated game info."""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT pa.*, g.title, g.thumb_url, g.cheapshark_id,
                   MIN(p.current_price) AS current_best_price,
                   s.name               AS current_best_store,
                   s.logo_url           AS current_best_store_logo,
                   s.icon_url           AS current_best_store_icon,
                   s.website_url        AS current_best_store_website
              FROM price_alerts pa
              JOIN games g ON g.id = pa.game_id
         LEFT JOIN prices p ON p.game_id = g.id
         LEFT JOIN stores s ON s.id = p.store_id
          GROUP BY pa.id
          ORDER BY pa.created_at DESC
            """,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def create_alert(game_id, target_price):
    """Create a new price alert. Returns the alert id."""
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO price_alerts (game_id, target_price) VALUES (?, ?)",
            (game_id, float(target_price)),
        )
        db.commit()
        return cursor.lastrowid
    finally:
        db.close()


def update_alert(alert_id, target_price=None, is_active=None):
    """Modify an existing alert's target price and/or active status."""
    db = get_db()
    try:
        fields = {}
        if target_price is not None:
            fields['target_price'] = float(target_price)
        if is_active is not None:
            fields['is_active'] = int(is_active)

        if not fields:
            return

        set_clause = ', '.join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [int(alert_id)]
        db.execute(f"UPDATE price_alerts SET {set_clause} WHERE id = ?", values)
        db.commit()
    finally:
        db.close()


def delete_alert(alert_id):
    """Remove a price alert."""
    db = get_db()
    try:
        db.execute("DELETE FROM price_alerts WHERE id = ?", (alert_id,))
        db.commit()
    finally:
        db.close()


def check_alerts():
    """
    Evaluate all active alerts against current best prices.
    If a game's best current price is at or below the target, trigger the alert.

    Returns
    -------
    list[dict]
        Alerts that were triggered during this check.
    """
    db = get_db()
    triggered = []
    try:
        alerts = db.execute(
            """
            SELECT pa.id AS alert_id, pa.game_id, pa.target_price,
                   MIN(p.current_price) AS best_price,
                   s.name               AS store_name
              FROM price_alerts pa
              JOIN prices p ON p.game_id = pa.game_id
              JOIN stores s ON s.id = p.store_id
             WHERE pa.is_active = 1 AND pa.is_triggered = 0
          GROUP BY pa.id
            """,
        ).fetchall()

        now = datetime.utcnow().isoformat()

        for alert in alerts:
            if alert['best_price'] is not None and alert['best_price'] <= alert['target_price']:
                db.execute(
                    """
                    UPDATE price_alerts
                       SET is_triggered    = 1,
                           triggered_at    = ?,
                           triggered_price = ?,
                           triggered_store = ?
                     WHERE id = ?
                    """,
                    (now, alert['best_price'], alert['store_name'],
                     alert['alert_id']),
                )
                triggered.append(dict(alert))
                logger.info(
                    "Alert %s triggered: game_id=%s price=%.2f store=%s",
                    alert['alert_id'], alert['game_id'],
                    alert['best_price'], alert['store_name'],
                )

        if triggered:
            db.commit()

        return triggered
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Dashboard & utility queries
# ---------------------------------------------------------------------------

def get_dashboard_stats():
    """
    Aggregate stats for the dashboard.

    Returns
    -------
    dict
        Keys: total_games, total_deals, avg_discount, best_deal (dict or None)
    """
    db = get_db()
    try:
        total_games = db.execute("SELECT COUNT(*) AS c FROM games").fetchone()['c']

        deals_row = db.execute(
            """
            SELECT COUNT(*)        AS total_deals,
                   AVG(discount_percent) AS avg_discount
              FROM prices
             WHERE is_on_sale = 1
            """
        ).fetchone()
        total_deals = deals_row['total_deals'] if deals_row else 0
        avg_discount = round(deals_row['avg_discount'] or 0, 1)

        best = db.execute(
            """
            SELECT g.title, g.thumb_url, p.current_price, p.original_price,
                   p.discount_percent, p.deal_url, s.name AS store_name,
                   s.logo_url AS store_logo_url, s.icon_url AS store_icon_url,
                   s.website_url AS store_website_url
              FROM prices p
              JOIN games g ON g.id = p.game_id
              JOIN stores s ON s.id = p.store_id
             WHERE p.is_on_sale = 1 AND p.current_price > 0
          ORDER BY p.discount_percent DESC
             LIMIT 1
            """,
        ).fetchone()

        return {
            'total_games': total_games,
            'total_deals': total_deals,
            'avg_discount': avg_discount,
            'best_deal': dict(best) if best else None,
        }
    finally:
        db.close()


def get_genres():
    """Return distinct genre values from the games table."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT DISTINCT genre FROM games WHERE genre IS NOT NULL AND genre != '' ORDER BY genre"
        ).fetchall()
        return [r['genre'] for r in rows]
    finally:
        db.close()


def get_stores():
    """Return all stores."""
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM stores ORDER BY name").fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def get_all_games_for_comparison(title):
    """
    Find all games matching *title* and return each with all of its store prices.

    Returns
    -------
    list[dict]
        Each dict has game fields plus a 'prices' list.
    """
    db = get_db()
    try:
        games = db.execute(
            "SELECT * FROM games WHERE title LIKE ? ORDER BY title",
            (f"%{title}%",),
        ).fetchall()

        results = []
        for game in games:
            g = dict(game)
            prices = db.execute(
                """
                SELECT p.*, s.name AS store_name
                  FROM prices p
                  JOIN stores s ON s.id = p.store_id
                 WHERE p.game_id = ?
              ORDER BY p.current_price ASC
                """,
                (g['id'],),
            ).fetchall()
            g['prices'] = [dict(p) for p in prices]
            results.append(g)

        return results
    finally:
        db.close()
