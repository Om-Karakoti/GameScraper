"""
CheapShark API Integration
============================
Fetches game deals, game details, search results, and store listings
from the CheapShark public API.
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

# Minimum delay between consecutive CheapShark requests (seconds).
_MIN_REQUEST_GAP = 0.3
_last_request_time = 0.0


def _throttle():
    """Respect a minimum gap between requests to avoid rate-limiting."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_REQUEST_GAP:
        time.sleep(_MIN_REQUEST_GAP - elapsed)
    _last_request_time = time.time()


def _get(endpoint, params=None):
    """
    Perform a throttled GET against the CheapShark API.

    Returns
    -------
    dict | list | None
        Parsed JSON on success, None on failure.
    """
    url = f"{config.CHEAPSHARK_BASE_URL}{endpoint}"
    _throttle()
    try:
        resp = _session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get('Retry-After', 5))
            logger.warning("CheapShark rate-limited; retrying in %ds", retry_after)
            time.sleep(retry_after)
            resp = _session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.error("CheapShark request timed out: %s", url)
    except requests.exceptions.HTTPError as exc:
        logger.error("CheapShark HTTP error %s: %s", exc.response.status_code, url)
    except requests.exceptions.RequestException as exc:
        logger.error("CheapShark request failed: %s", exc)
    except ValueError:
        logger.error("CheapShark returned invalid JSON from %s", url)
    return None


# ---------------------------------------------------------------------------
# Public API wrappers
# ---------------------------------------------------------------------------

def fetch_deals(page=0, page_size=60, sort_by='Deal Rating',
                store_id=None, min_price=0, max_price=50, on_sale=True):
    """
    Fetch a page of deals from the CheapShark /deals endpoint.

    Parameters
    ----------
    page : int
        Zero-indexed page number.
    page_size : int
        Number of results per page (max 60).
    sort_by : str
        One of 'Deal Rating', 'Title', 'Savings', 'Price', 'Metacritic',
        'Reviews', 'Release', 'Store', 'Recent'.
    store_id : int | None
        Filter to a specific CheapShark store ID.
    min_price : float
        Minimum sale price.
    max_price : float
        Maximum sale price.
    on_sale : bool
        Only include items currently on sale.

    Returns
    -------
    list[dict] | None
    """
    params = {
        'pageNumber': page,
        'pageSize': min(page_size, config.MAX_DEALS_PER_PAGE),
        'sortBy': sort_by,
        'lowerPrice': min_price,
        'upperPrice': max_price,
        'onSale': int(on_sale),
    }
    if store_id is not None:
        params['storeID'] = store_id

    data = _get('/deals', params=params)
    if data is None:
        logger.warning("fetch_deals returned no data (page=%d)", page)
        return None
    logger.info("Fetched %d deals from CheapShark (page %d)", len(data), page)
    return data


def fetch_game_details(cheapshark_game_id):
    """
    Fetch full game details from CheapShark /games?id=...

    Returns
    -------
    dict | None
    """
    data = _get('/games', params={'id': cheapshark_game_id})
    if data:
        logger.debug("Fetched details for CheapShark game %s", cheapshark_game_id)
    return data


def search_games(query):
    """
    Search for games by title via CheapShark /games?title=...

    Returns
    -------
    list[dict] | None
    """
    data = _get('/games', params={'title': query, 'limit': 20})
    if data:
        logger.info("CheapShark search '%s' returned %d results", query, len(data))
    return data


def fetch_stores():
    """
    Get the full list of stores from CheapShark /stores.

    Returns
    -------
    list[dict] | None
    """
    data = _get('/stores')
    if data:
        logger.info("Fetched %d stores from CheapShark", len(data))
    return data


# ---------------------------------------------------------------------------
# Processing helpers
# ---------------------------------------------------------------------------

def process_deals(deals_data):
    """
    Process a list of raw deal dicts from CheapShark and persist them
    to the local database.

    For each deal the function will:
    1. Upsert the game record.
    2. Upsert the price record (and record history if the price changed).

    Parameters
    ----------
    deals_data : list[dict]
        Raw deal objects as returned by the /deals endpoint.

    Returns
    -------
    int
        Number of deals successfully processed.
    """
    if not deals_data:
        return 0

    processed = 0

    for deal in deals_data:
        try:
            # --- Build game data ---
            game_data = {
                'title': deal.get('title', 'Unknown'),
                'cheapshark_id': deal.get('gameID'),
                'steam_app_id': deal.get('steamAppID') or None,
                'thumb_url': deal.get('thumb'),
                'metacritic_score': (
                    int(deal['metacriticScore'])
                    if deal.get('metacriticScore') and str(deal['metacriticScore']).isdigit()
                    else None
                ),
                'metacritic_url': deal.get('metacriticLink') or None,
            }

            game_id = database.upsert_game(game_data)

            # --- Build price data ---
            store_id = int(deal.get('storeID', 1))
            current_price = deal.get('salePrice', 0)
            original_price = deal.get('normalPrice', 0)
            savings = deal.get('savings', 0)
            deal_id = deal.get('dealID', '')
            deal_url = f"https://www.cheapshark.com/redirect?dealID={deal_id}"

            database.upsert_price(
                game_id=game_id,
                store_id=store_id,
                current_price=current_price,
                original_price=original_price,
                discount=savings,
                deal_id=deal_id,
                deal_url=deal_url,
            )

            processed += 1
        except Exception:
            logger.exception("Error processing deal: %s", deal.get('title', '?'))

    logger.info("Processed %d / %d deals", processed, len(deals_data))
    return processed
