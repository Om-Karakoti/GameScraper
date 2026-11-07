"""
GameScraper Configuration
=========================
Central configuration for API endpoints, database settings, and scraping parameters.
"""

# Database
DATABASE_PATH = 'gamescraper.db'

# CheapShark API
CHEAPSHARK_BASE_URL = 'https://www.cheapshark.com/api/1.0'

# Steam API
STEAM_API_URL = 'https://store.steampowered.com/api'

# Scraping Settings
SCRAPE_INTERVAL_MINUTES = 30
MAX_DEALS_PER_PAGE = 60
REQUEST_TIMEOUT = 15
POPULARITY_MIN_REVIEWS = 1000
POPULARITY_MIN_RATING = 70

# HTTP Headers
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)

# Supported Stores (CheapShark store ID -> friendly name)
SUPPORTED_STORES = {
    1: 'Steam',
    7: 'GOG',
    11: 'Humble Bundle',
    15: 'Fanatical',
    16: 'WinGameStore',
    21: 'Green Man Gaming',
    23: 'GamersGate',
    25: 'Epic Games Store',
    27: 'Gamesplanet',
    30: 'IndieGala',
    33: 'DLGamer',
    34: 'Noctre',
    35: 'DreamGame',
}
