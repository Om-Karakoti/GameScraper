"""
Steam API Supplementary Data
==============================
Enriches game records with genre, publisher, developer, description,
and high-resolution images from the Steam Store API.
"""

import logging
import time

import requests

import config
import database

logger = logging.getLogger(__name__)

# Module-level session for connection pooling
_session = requests.Session()
_session.headers.update({
    'User-Agent': config.USER_AGENT,
    'Accept': 'application/json',
})

# Steam enforces roughly 200 requests per 5 minutes.
# We stay safe with one request every 1.5 seconds.
_MIN_REQUEST_GAP = 1.5
_last_request_time = 0.0


def _throttle():
    """Ensure at least _MIN_REQUEST_GAP seconds between Steam API calls."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_REQUEST_GAP:
        time.sleep(_MIN_REQUEST_GAP - elapsed)
    _last_request_time = time.time()


def fetch_app_details(steam_app_id):
    """
    Fetch app details from the Steam Store API.

    Parameters
    ----------
    steam_app_id : str | int
        The Steam application ID.

    Returns
    -------
    dict | None
        Parsed app-data dict on success, None on failure or if the app
        is not found / not a game.
    """
    if not steam_app_id:
        return None

    steam_app_id = str(steam_app_id)
    url = f"{config.STEAM_API_URL}/appdetails"
    params = {'appids': steam_app_id}

    _throttle()

    try:
        resp = _session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except requests.exceptions.Timeout:
        logger.warning("Steam API request timed out for app %s", steam_app_id)
        return None
    except requests.exceptions.HTTPError as exc:
        logger.warning(
            "Steam API HTTP error %s for app %s",
            exc.response.status_code, steam_app_id,
        )
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning("Steam API request failed for app %s: %s", steam_app_id, exc)
        return None
    except ValueError:
        logger.warning("Steam API returned invalid JSON for app %s", steam_app_id)
        return None

    app_info = payload.get(steam_app_id)
    if not app_info or not app_info.get('success'):
        logger.debug("Steam API reports no data for app %s", steam_app_id)
        return None

    data = app_info.get('data', {})
    if not data:
        return None

    # Extract the fields we care about
    genres_list = data.get('genres', [])
    genre_str = ', '.join(g.get('description', '') for g in genres_list) if genres_list else None

    publishers = data.get('publishers', [])
    publisher_str = ', '.join(publishers) if publishers else None

    developers = data.get('developers', [])
    developer_str = ', '.join(developers) if developers else None

    release_info = data.get('release_date', {})
    release_date = release_info.get('date') if release_info else None

    result = {
        'genre': genre_str,
        'publisher': publisher_str,
        'developer': developer_str,
        'description': data.get('short_description') or None,
        'large_image_url': data.get('header_image') or None,
        'release_date': release_date,
    }

    logger.debug("Fetched Steam details for app %s: genre=%s", steam_app_id, genre_str)
    return result


def enrich_game_data(game_id):
    """
    Look up a game's steam_app_id and, if present, fetch supplementary
    details from Steam and update the local database record.

    Parameters
    ----------
    game_id : int
        Internal game ID.

    Returns
    -------
    bool
        True if the game was successfully enriched, False otherwise.
    """
    game = database.get_game_by_id(game_id)
    if not game:
        logger.debug("enrich_game_data: game %d not found", game_id)
        return False

    steam_app_id = game.get('steam_app_id')
    if not steam_app_id:
        logger.debug("enrich_game_data: game %d has no steam_app_id", game_id)
        return False

    details = fetch_app_details(steam_app_id)
    if not details:
        return False

    # Build update payload — only include fields with actual values
    update_data = {'cheapshark_id': game.get('cheapshark_id'), 'title': game['title']}
    for key in ('genre', 'publisher', 'developer', 'description',
                'large_image_url', 'release_date'):
        value = details.get(key)
        if value:
            update_data[key] = value

    if len(update_data) > 2:  # more than just cheapshark_id + title
        database.upsert_game(update_data)
        logger.info(
            "Enriched game %d (%s) with Steam data",
            game_id, game['title'],
        )
        return True

    return False
