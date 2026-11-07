import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

import database
from routes.api import api_bp


class PopularityAndHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'gamescraper.db')
        self.database_path_patch = patch.object(database, 'DATABASE_PATH', self.db_path)
        self.database_path_patch.start()
        self.addCleanup(self.database_path_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)
        with patch.object(database, 'sync_stores_from_api'):
            database.init_db()

    def add_game(self, title, rating_percent, rating_count):
        return database.upsert_game({
            'title': title,
            'steam_rating_percent': rating_percent,
            'steam_rating_count': rating_count,
        })

    def add_price(self, game_id, store_id, price, discount):
        database.upsert_price(
            game_id=game_id,
            store_id=store_id,
            current_price=price,
            original_price=price + 10,
            discount=discount,
            deal_id=f'{game_id}-{store_id}',
            deal_url='https://example.com/deal',
        )

    def test_popular_filter_includes_games_not_on_sale(self):
        popular_id = self.add_game('Popular sale', 70, 1000)
        regular_id = self.add_game('Regular sale', 90, 999)
        popular_not_on_sale_id = self.add_game('Popular regular price', 85, 2500)

        self.add_price(popular_id, 1, 5, 50)
        self.add_price(popular_id, 7, 4, 60)
        self.add_price(regular_id, 1, 5, 50)
        self.add_price(popular_not_on_sale_id, 1, 15, 0)

        popular_result = database.get_deals(popular_only=True, sort_by='popularity')
        self.assertEqual(
            {deal['title'] for deal in popular_result['deals']},
            {'Popular sale', 'Popular regular price'},
        )
        self.assertEqual(len(popular_result['deals']), 2)
        popular_sale = next(
            deal for deal in popular_result['deals'] if deal['title'] == 'Popular sale'
        )
        self.assertEqual(popular_sale['store_id'], 7)
        self.assertTrue(all(deal['is_popular'] for deal in popular_result['deals']))

        default_result = database.get_deals()
        self.assertEqual(
            {deal['title'] for deal in default_result['deals']},
            {'Popular sale', 'Regular sale'},
        )

        app = Flask(__name__)
        app.register_blueprint(api_bp)
        response = app.test_client().get('/api/deals?popular_only=true&sort=popularity')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {deal['title'] for deal in response.get_json()['deals']},
            {'Popular sale', 'Popular regular price'},
        )

    def test_price_history_reports_each_stores_price_direction(self):
        game_id = self.add_game('History test', 80, 1200)
        self.add_price(game_id, 1, 20, 0)
        self.add_price(game_id, 7, 30, 0)
        game = database.get_game_by_id(game_id)
        self.assertEqual(game['best_price'], 20)
        self.assertEqual(game['best_store_name'], 'Steam')
        self.add_price(game_id, 1, 15, 25)
        self.add_price(game_id, 7, 35, 0)

        history = database.get_price_history(game_id, days=0)
        steam_prices = [point for point in history if point['store_id'] == 1]
        gog_prices = [point for point in history if point['store_id'] == 7]

        self.assertIsNone(steam_prices[0]['previous_price'])
        self.assertEqual(steam_prices[1]['previous_price'], 20)
        self.assertEqual(steam_prices[1]['price_change'], -5)
        self.assertEqual(steam_prices[1]['change_type'], 'decrease')
        self.assertEqual(gog_prices[1]['previous_price'], 30)
        self.assertEqual(gog_prices[1]['price_change'], 5)
        self.assertEqual(gog_prices[1]['change_type'], 'increase')

        app = Flask(__name__)
        app.register_blueprint(api_bp)
        response = app.test_client().get(f'/api/games/{game_id}/history?days=0')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(
            point['store_id'] == 7 and point['change_type'] == 'increase'
            for point in response.get_json()
        ))

    def test_deals_can_be_searched_by_title(self):
        matching_id = self.add_game('Searchable Adventure', 85, 1400)
        self.add_game('Another Adventure', 80, 1200)
        self.add_price(matching_id, 1, 5, 50)

        result = database.get_deals(search_query='searchable')
        self.assertEqual([deal['title'] for deal in result['deals']], ['Searchable Adventure'])

        app = Flask(__name__)
        app.register_blueprint(api_bp)
        response = app.test_client().get('/api/deals?q=Searchable')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [deal['title'] for deal in response.get_json()['deals']],
            ['Searchable Adventure'],
        )

    def test_init_migrates_existing_games_table(self):
        legacy_path = os.path.join(self.temp_dir.name, 'legacy.db')
        connection = sqlite3.connect(legacy_path)
        try:
            connection.execute(
                'CREATE TABLE games (id INTEGER PRIMARY KEY, title TEXT NOT NULL)'
            )
        finally:
            connection.close()

        with patch.object(database, 'DATABASE_PATH', legacy_path):
            with patch.object(database, 'sync_stores_from_api'):
                database.init_db()

        connection = sqlite3.connect(legacy_path)
        try:
            columns = {row[1] for row in connection.execute('PRAGMA table_info(games)')}
        finally:
            connection.close()
        self.assertIn('steam_rating_percent', columns)
        self.assertIn('steam_rating_count', columns)


if __name__ == '__main__':
    unittest.main()
