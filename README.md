# GameScraper 🎮 – Multi-Store Video Game Deals & Price Tracker

**GameScraper** is a full-featured video game deal tracker and price comparison web dashboard built with Python, Flask, SQLite, APScheduler, Chart.js, and the CheapShark API.

It automatically tracks video game discounts across 35+ digital game storefronts (Steam, Epic Games Store, GOG, Green Man Gaming, Humble Bundle, Fanatical, GamersGate, and more), allowing gamers to discover the cheapest available prices without checking multiple sites.

---

## 🚀 Features

- **Centralized Dashboard**: Live statistics on total games, active deals, average discounts, top deals, and recently updated games.
- **Multi-Store Price Comparison**: Detailed comparison table showing prices across all digital stores, highlighting the lowest available price and exact dollar savings.
- **Dynamic Search**: Instant debounced search querying local records and automatically retrieving untracked titles on-the-fly from CheapShark.
- **Category & Deal Filters**: Filter by store, price range, minimum discount %, and free games.
- **Popularity Ranking**: Discover games with at least 1,000 Steam reviews and 70% positive ratings; popular games are collected even when they are not on sale.
- **Persistent Wishlist**: Save games to a personal wishlist persisted in SQLite.
- **Target Price Alerts**: Set custom target prices for any game with automatic price monitoring and dashboard notifications.
- **Interactive Price History**: Tracks price changes per store and shows dated drops and increases in Chart.js charts and a change timeline.
- **Direct Store Links**: Direct purchase URLs and store links to each deal.

---

## 🛠️ Tech Stack

- **Backend**: Python 3, Flask, Requests, BeautifulSoup4
- **Database**: SQLite (relational schema with cascading foreign keys)
- **Automation / Scheduler**: APScheduler (BackgroundScheduler)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript (SPA), Chart.js 4.4, FontAwesome 6

---

## 📦 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Om-Karakoti/GameScraper.git
   cd GameScraper
   ```

2. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```

5. **Open in browser:**
   Navigate to [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 📂 Project Structure

```text
GameScraper/
├── app.py                  # Application factory and Flask runner
├── config.py               # Application configuration and store mappings
├── database.py             # SQLite CRUD operations and schema management
├── requirements.txt        # Python package dependencies
├── .gitignore              # Ignored files (database, cache, virtualenvs)
├── routes/
│   ├── api.py              # REST API endpoints (/api/stats, /api/deals, /api/search, etc.)
│   └── views.py            # Main web UI route
├── scraper/
│   ├── cheapshark.py       # CheapShark API client with rate-limiting
│   ├── steam.py            # Steam Store API client for game metadata
│   └── scheduler.py        # Background scheduler for periodic price checks
├── static/
│   ├── css/
│   │   └── style.css       # Dark gaming-themed responsive stylesheet
│   └── js/
│       └── app.js          # Client-side SPA controller & Chart.js integration
└── templates/
    └── index.html          # Main application dashboard template
```

---

## 📜 License
MIT License
