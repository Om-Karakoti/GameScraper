"""
GameScraper View Routes
=======================
Blueprint serving the main front-end HTML page.
"""

from flask import Blueprint, render_template

views_bp = Blueprint('views', __name__)


@views_bp.route('/')
def index():
    """Render the main single-page application.

    Returns:
        Rendered index.html template.
    """
    return render_template('index.html')
