"""
GameScraper API Routes
======================
RESTful API blueprint providing endpoints for deals, games, price comparison,
wishlist management, price alerts, and administrative actions.
"""

import logging
import threading
from flask import Blueprint, jsonify, request

from database import (
    get_game_by_id,
    search_games,
    get_deals,
    get_game_prices,
    get_price_history,
    get_wishlist,
    add_to_wishlist,
    remove_from_wishlist,
    is_in_wishlist,
    get_alerts,
    create_alert,
    update_alert,
    delete_alert,
    check_alerts,
    get_dashboard_stats,
    get_genres,
    get_stores,
    get_all_games_for_comparison,
)

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@api_bp.route('/stats', methods=['GET'])
def stats():
    """Return aggregate dashboard statistics.

    Returns:
        JSON with total_games, total_deals, avg_discount, best_deal.
    """
    try:
        data = get_dashboard_stats()
        return jsonify(data), 200
    except Exception as exc:
        logger.exception("Error fetching dashboard stats")
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/stores', methods=['GET'])
def stores():
    """Return the list of supported stores.

    Returns:
        JSON list of store objects.
    """
    try:
        data = get_stores()
        return jsonify(data), 200
    except Exception as exc:
        logger.exception("Error fetching stores")
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/genres', methods=['GET'])
def genres():
    """Return all distinct game genres.

    Returns:
        JSON list of genre strings.
    """
    try:
        data = get_genres()
        return jsonify(data), 200
    except Exception as exc:
        logger.exception("Error fetching genres")
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Deals & Games
# ---------------------------------------------------------------------------

@api_bp.route('/deals', methods=['GET'])
def deals():
    """Return a paginated, filterable list of game deals.

    Query Parameters:
        page (int): Page number, default 0.
        limit (int): Results per page, default 20.
        sort (str): Sort key — 'discount', 'price_asc', 'price_desc',
                     'newest', or 'metacritic'.
        min_discount (int): Minimum discount percentage.
        store_id (int): Filter by store ID.
        min_price (float): Minimum current price.
        max_price (float): Maximum current price.
        genre (str): Filter by genre.
        free (bool): If true, only free games.

    Returns:
        JSON with deals list, page, total_pages, and total count.
    """
    try:
        page = request.args.get('page', 0, type=int)
        limit = request.args.get('limit', 20, type=int)
        sort_by = request.args.get('sort', 'discount', type=str)
        min_discount = request.args.get('min_discount', 0, type=int)
        store_id = request.args.get('store_id', None, type=int)
        min_price = request.args.get('min_price', None, type=float)
        max_price = request.args.get('max_price', None, type=float)
        genre = request.args.get('genre', None, type=str)
        free_only = request.args.get('free', 'false', type=str).lower() in ('true', '1', 'yes')

        result = get_deals(
            page=page,
            limit=limit,
            sort_by=sort_by,
            min_discount=min_discount,
            store_id=store_id,
            min_price=min_price,
            max_price=max_price,
            genre=genre,
            free_only=free_only,
        )

        # result is expected to be a dict with 'deals' list and 'total' count
        deals_list = result.get('deals', [])
        total = result.get('total', 0)
        total_pages = max(1, -(-total // limit))  # ceiling division

        # Enrich each deal with wishlist status
        for deal in deals_list:
            try:
                deal['is_in_wishlist'] = is_in_wishlist(deal.get('id'))
            except Exception:
                deal['is_in_wishlist'] = False

        return jsonify({
            'deals': deals_list,
            'page': page,
            'total_pages': total_pages,
            'total': total,
        }), 200

    except Exception as exc:
        logger.exception("Error fetching deals")
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/games/<int:game_id>', methods=['GET'])
def game_detail(game_id):
    """Return full details for a single game including store prices,
    wishlist status, and active alerts.

    Args:
        game_id: Database primary key of the game.

    Returns:
        JSON with game details, prices, wishlist flag, and alerts.
    """
    try:
        game = get_game_by_id(game_id)
        if game is None:
            return jsonify({'error': 'Game not found'}), 404

        # Attach current store prices
        game['prices'] = get_game_prices(game_id)

        # Wishlist status
        game['is_in_wishlist'] = is_in_wishlist(game_id)

        # Active alerts for this game
        all_alerts = get_alerts()
        game['alerts'] = [
            a for a in all_alerts
            if a.get('game_id') == game_id
        ]

        return jsonify(game), 200

    except Exception as exc:
        logger.exception("Error fetching game %s", game_id)
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/search', methods=['GET'])
def search():
    """Search games by title substring.
    First searches local database. If fewer than 5 results are found,
    it queries CheapShark API dynamically, registers found games/deals,
    and returns rich combined results!

    Query Parameters:
        q (str): Search query string.

    Returns:
        JSON list of matching games with best prices.
    """
    try:
        query = request.args.get('q', '', type=str).strip()
        if not query:
            return jsonify({'error': 'Query parameter "q" is required'}), 400

        results = search_games(query, limit=20)
        
        # If few or no results found locally, search CheapShark dynamically
        if len(results) < 5:
            try:
                from scraper import cheapshark
                cs_results = cheapshark.search_games(query)
                if cs_results:
                    for item in cs_results[:10]:
                        cs_id = str(item.get('gameID', ''))
                        if not cs_id:
                            continue
                        # Fetch full deals for this game from CheapShark
                        g_details = cheapshark.fetch_game_details(cs_id)
                        if g_details and g_details.get('info'):
                            info = g_details['info']
                            game_data = {
                                'title': info.get('title', item.get('external', 'Unknown')),
                                'cheapshark_id': cs_id,
                                'steam_app_id': info.get('steamAppID') or item.get('steamAppID') or None,
                                'thumb_url': info.get('thumb') or item.get('thumb'),
                            }
                            from database import upsert_game, upsert_price
                            g_id = upsert_game(game_data)
                            for d in g_details.get('deals', []):
                                s_id = int(d.get('storeID', 1))
                                c_price = float(d.get('price', 0))
                                o_price = float(d.get('retailPrice', 0))
                                sav = float(d.get('savings', 0))
                                d_id = d.get('dealID', '')
                                d_url = f"https://www.cheapshark.com/redirect?dealID={d_id}"
                                upsert_price(
                                    game_id=g_id,
                                    store_id=s_id,
                                    current_price=c_price,
                                    original_price=o_price,
                                    discount=sav,
                                    deal_id=d_id,
                                    deal_url=d_url,
                                )
                    # Re-query local DB to include the freshly stored games
                    results = search_games(query, limit=20)
            except Exception as cs_err:
                logger.warning("Dynamic CheapShark search failed: %s", cs_err)

        return jsonify(results), 200

    except Exception as exc:
        logger.exception("Error searching games")
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Price Comparison & History
# ---------------------------------------------------------------------------

@api_bp.route('/games/<int:game_id>/prices', methods=['GET'])
def game_prices(game_id):
    """Return current prices for a game across all stores.

    Args:
        game_id: Database primary key of the game.

    Returns:
        JSON list of price objects per store.
    """
    try:
        game = get_game_by_id(game_id)
        if game is None:
            return jsonify({'error': 'Game not found'}), 404

        prices = get_game_prices(game_id)
        return jsonify(prices), 200

    except Exception as exc:
        logger.exception("Error fetching prices for game %s", game_id)
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/games/<int:game_id>/history', methods=['GET'])
def game_price_history(game_id):
    """Return historical price data for a game.

    Query Parameters:
        store_id (int, optional): Limit history to a specific store.
        days (int, optional): Number of days of history (default 90).

    Returns:
        JSON list of {price, store_name, store_id, recorded_at}.
    """
    try:
        game = get_game_by_id(game_id)
        if game is None:
            return jsonify({'error': 'Game not found'}), 404

        store_id = request.args.get('store_id', None, type=int)
        days = request.args.get('days', 90, type=int)

        history = get_price_history(game_id, store_id=store_id, days=days)
        return jsonify(history), 200

    except Exception as exc:
        logger.exception("Error fetching price history for game %s", game_id)
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/comparison', methods=['GET'])
def comparison():
    """Compare prices for a game across all stores by title.

    Query Parameters:
        title (str): Exact or partial game title to compare.

    Returns:
        JSON with game details and prices across all stores.
    """
    try:
        title = request.args.get('title', '', type=str).strip()
        if not title:
            return jsonify({'error': 'Query parameter "title" is required'}), 400

        data = get_all_games_for_comparison(title)
        return jsonify(data), 200

    except Exception as exc:
        logger.exception("Error comparing prices for '%s'", title)
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------

@api_bp.route('/wishlist', methods=['GET'])
def wishlist_list():
    """Return all wishlisted games with current prices.

    Returns:
        JSON list of wishlisted game objects.
    """
    try:
        data = get_wishlist()
        return jsonify(data), 200
    except Exception as exc:
        logger.exception("Error fetching wishlist")
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/wishlist', methods=['POST'])
def wishlist_add():
    """Add a game to the wishlist.

    JSON Body:
        game_id (int): ID of the game to add.

    Returns:
        JSON success or error message.
    """
    try:
        body = request.get_json(silent=True) or {}
        game_id = body.get('game_id')

        if game_id is None:
            return jsonify({'error': 'game_id is required'}), 400

        game_id = int(game_id)
        game = get_game_by_id(game_id)
        if game is None:
            return jsonify({'error': 'Game not found'}), 404

        if is_in_wishlist(game_id):
            return jsonify({'error': 'Game is already in wishlist'}), 409

        add_to_wishlist(game_id)
        return jsonify({'success': True, 'message': 'Game added to wishlist'}), 201

    except ValueError:
        return jsonify({'error': 'game_id must be an integer'}), 400
    except Exception as exc:
        logger.exception("Error adding to wishlist")
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/wishlist/<int:game_id>', methods=['DELETE'])
def wishlist_remove(game_id):
    """Remove a game from the wishlist.

    Args:
        game_id: Database primary key of the game.

    Returns:
        JSON success message.
    """
    try:
        remove_from_wishlist(game_id)
        return jsonify({'success': True, 'message': 'Game removed from wishlist'}), 200
    except Exception as exc:
        logger.exception("Error removing game %s from wishlist", game_id)
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Price Alerts
# ---------------------------------------------------------------------------

@api_bp.route('/alerts', methods=['GET'])
def alerts_list():
    """Return all price alerts with associated game info.

    Returns:
        JSON list of alert objects.
    """
    try:
        data = get_alerts()
        return jsonify(data), 200
    except Exception as exc:
        logger.exception("Error fetching alerts")
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/alerts', methods=['POST'])
def alerts_create():
    """Create a new price alert.

    JSON Body:
        game_id (int): ID of the game to watch.
        target_price (float): Price threshold to trigger the alert.

    Returns:
        JSON with success flag and new alert_id.
    """
    try:
        body = request.get_json(silent=True) or {}
        game_id = body.get('game_id')
        target_price = body.get('target_price')

        if game_id is None or target_price is None:
            return jsonify({'error': 'game_id and target_price are required'}), 400

        game_id = int(game_id)
        target_price = float(target_price)

        if target_price < 0:
            return jsonify({'error': 'target_price must be non-negative'}), 400

        game = get_game_by_id(game_id)
        if game is None:
            return jsonify({'error': 'Game not found'}), 404

        alert_id = create_alert(game_id, target_price)
        return jsonify({
            'success': True,
            'message': 'Alert created',
            'alert_id': alert_id,
        }), 201

    except (ValueError, TypeError):
        return jsonify({'error': 'game_id must be int, target_price must be numeric'}), 400
    except Exception as exc:
        logger.exception("Error creating alert")
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/alerts/<int:alert_id>', methods=['PUT'])
def alerts_update(alert_id):
    """Update an existing price alert.

    Args:
        alert_id: Database primary key of the alert.

    JSON Body (all optional):
        target_price (float): New target price.
        is_active (bool): Enable or disable the alert.

    Returns:
        JSON success message.
    """
    try:
        body = request.get_json(silent=True) or {}
        target_price = body.get('target_price')
        is_active = body.get('is_active')

        if target_price is not None:
            target_price = float(target_price)
            if target_price < 0:
                return jsonify({'error': 'target_price must be non-negative'}), 400

        if is_active is not None:
            is_active = bool(is_active)

        update_alert(alert_id, target_price=target_price, is_active=is_active)
        return jsonify({'success': True, 'message': 'Alert updated'}), 200

    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid data types in request body'}), 400
    except Exception as exc:
        logger.exception("Error updating alert %s", alert_id)
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/alerts/<int:alert_id>', methods=['DELETE'])
def alerts_delete(alert_id):
    """Delete a price alert.

    Args:
        alert_id: Database primary key of the alert.

    Returns:
        JSON success message.
    """
    try:
        delete_alert(alert_id)
        return jsonify({'success': True, 'message': 'Alert deleted'}), 200
    except Exception as exc:
        logger.exception("Error deleting alert %s", alert_id)
        return jsonify({'error': str(exc)}), 500


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@api_bp.route('/scrape', methods=['POST'])
def trigger_scrape():
    """Trigger a manual scrape in a background thread.

    Returns:
        JSON with status indicating scrape has started.
    """
    try:
        from flask import current_app
        from scraper.scheduler import run_initial_scrape

        app = current_app._get_current_object()
        thread = threading.Thread(
            target=run_initial_scrape,
            args=(app,),
            daemon=True,
        )
        thread.start()

        return jsonify({'status': 'scraping started'}), 200

    except ImportError:
        logger.warning("Scraper module not available; scrape not started")
        return jsonify({'error': 'Scraper module is not available'}), 503
    except Exception as exc:
        logger.exception("Error triggering scrape")
        return jsonify({'error': str(exc)}), 500
