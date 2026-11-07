/**
 * GameScraper - Modern Video Game Deals & Price Tracker Dashboard
 * Vanilla JavaScript Single Page Application Controller
 */

'use strict';

const App = {
    currentSection: 'dashboard',
    currentPage: 1,
    pageSize: 24,
    totalPages: 1,
    filters: {
        sort: 'discount',
        genre: '',
        store_id: '',
        min_price: '',
        max_price: '',
        min_discount: 0,
        free: false,
        popular_only: false
    },
    stores: [],
    genres: [],
    charts: {
        history: null,
        modalHistory: null
    },

    async init() {
        this.setupNavigation();
        this.setupSearch();
        this.setupFilters();
        this.setupModals();
        this.setupRefreshButton();
        this.setupMobileMenu();

        // Load stores & genres for select dropdowns
        await this.loadStoresAndGenres();

        // Load dashboard by default
        await this.navigate('dashboard');
    },

    // -------------------------------------------------------------
    // Navigation
    // -------------------------------------------------------------
    setupNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const section = item.getAttribute('data-section');
                if (section) this.navigate(section);
            });
        });

        document.querySelectorAll('[data-navigate]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const section = link.getAttribute('data-navigate');
                if (section) this.navigate(section);
            });
        });

        // Price Alert Tabs (Active / Triggered)
        document.querySelectorAll('.alert-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                document.querySelectorAll('.alert-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.alerts-tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                const targetId = tab.getAttribute('data-tab');
                const content = document.getElementById(targetId);
                if (content) content.classList.add('active');
            });
        });
    },

    setupMobileMenu() {
        const btn = document.getElementById('mobile-menu-btn');
        const sidebar = document.getElementById('sidebar');
        if (btn && sidebar) {
            btn.addEventListener('click', () => {
                sidebar.classList.toggle('open');
            });
        }
    },

    async navigate(section) {
        this.currentSection = section;

        // Update nav items
        document.querySelectorAll('.nav-item').forEach(el => {
            el.classList.toggle('active', el.getAttribute('data-section') === section);
        });

        // Hide all sections, show target
        document.querySelectorAll('.content-section').forEach(sec => {
            sec.classList.remove('active');
        });
        const target = document.getElementById(`${section}-section`);
        if (target) {
            target.classList.add('active');
        }

        // Close sidebar on mobile
        const sidebar = document.getElementById('sidebar');
        if (sidebar && sidebar.classList.contains('open')) {
            sidebar.classList.remove('open');
        }

        // Update Top Bar Title
        const titleMap = {
            dashboard: 'Dashboard Overview',
            deals: 'Best Game Deals',
            explore: 'Explore & Search Games',
            wishlist: 'My Wishlist',
            alerts: 'Price Alerts & Notifications',
            history: 'Price History & Analytics'
        };
        const pageTitle = document.getElementById('page-title');
        if (pageTitle) pageTitle.textContent = titleMap[section] || 'GameScraper';

        // Load section specific data
        switch (section) {
            case 'dashboard':
                await Dashboard.load();
                break;
            case 'deals':
                await Deals.load(1);
                break;
            case 'wishlist':
                await Wishlist.load();
                break;
            case 'alerts':
                await Alerts.load();
                break;
            case 'history':
                // Initial prompt state
                break;
        }
    },

    // -------------------------------------------------------------
    // Stores & Genres Cache
    // -------------------------------------------------------------
    async loadStoresAndGenres() {
        try {
            const [storesRes, genresRes] = await Promise.all([
                fetch('/api/stores').then(r => r.json()),
                fetch('/api/genres').then(r => r.json())
            ]);

            this.stores = Array.isArray(storesRes) ? storesRes : [];
            this.genres = Array.isArray(genresRes) ? genresRes : [];

            // Populate store dropdown
            const storeSelect = document.getElementById('filter-store');
            if (storeSelect) {
                storeSelect.innerHTML = '<option value="">All Stores</option>' +
                    this.stores.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
            }

            // Populate genre dropdown
            const genreSelect = document.getElementById('filter-genre');
            if (genreSelect) {
                genreSelect.innerHTML = '<option value="">All Genres</option>' +
                    this.genres.map(g => `<option value="${g}">${g}</option>`).join('');
            }
        } catch (e) {
            console.error('Failed to load stores or genres:', e);
        }
    },

    // -------------------------------------------------------------
    // Search
    // -------------------------------------------------------------
    setupSearch() {
        const globalSearch = document.getElementById('global-search');
        const dropdown = document.getElementById('search-dropdown');

        if (globalSearch) {
            const debouncedSearch = this.debounce(async (query) => {
                if (!query || query.length < 2) {
                    if (dropdown) dropdown.innerHTML = '';
                    return;
                }
                const results = await Search.query(query);
                Search.renderDropdown(results, dropdown);
            }, 300);

            globalSearch.addEventListener('input', (e) => debouncedSearch(e.target.value.trim()));

            globalSearch.addEventListener('keydown', async (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (dropdown) dropdown.innerHTML = '';
                    const q = globalSearch.value.trim();
                    if (q) {
                        App.navigate('explore');
                        await Search.performSearch(q);
                    }
                }
            });

            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!globalSearch.contains(e.target) && dropdown && !dropdown.contains(e.target)) {
                    dropdown.innerHTML = '';
                }
            });
        }

        // History page search
        const historySearch = document.getElementById('history-search');
        const historyDropdown = document.getElementById('history-search-dropdown');
        if (historySearch) {
            const debouncedHistSearch = this.debounce(async (query) => {
                if (!query || query.length < 2) {
                    if (historyDropdown) historyDropdown.innerHTML = '';
                    return;
                }
                const results = await Search.query(query);
                Search.renderDropdown(results, historyDropdown, (gameId) => {
                    PriceHistory.loadForGame(gameId);
                    historyDropdown.innerHTML = '';
                    historySearch.value = '';
                });
            }, 300);

            historySearch.addEventListener('input', (e) => debouncedHistSearch(e.target.value.trim()));

            document.addEventListener('click', (e) => {
                if (!historySearch.contains(e.target) && historyDropdown && !historyDropdown.contains(e.target)) {
                    historyDropdown.innerHTML = '';
                }
            });
        }
    },

    // -------------------------------------------------------------
    // Filters & Sorting
    // -------------------------------------------------------------
    setupFilters() {
        const toggleBtn = document.getElementById('btn-toggle-filters');
        const filterPanel = document.getElementById('filter-panel');
        if (toggleBtn && filterPanel) {
            toggleBtn.addEventListener('click', () => {
                filterPanel.classList.toggle('open');
            });
        }

        const discountRange = document.getElementById('filter-min-discount');
        const discountVal = document.getElementById('discount-val');
        if (discountRange && discountVal) {
            discountRange.addEventListener('input', (e) => {
                discountVal.textContent = `${e.target.value}%`;
            });
        }

        const applyBtn = document.getElementById('btn-apply-filters');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => Deals.applyFilters());
        }

        const resetBtn = document.getElementById('btn-reset-filters');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => Deals.resetFilters());
        }

        const sortSelect = document.getElementById('sort-select');
        if (sortSelect) {
            sortSelect.addEventListener('change', () => {
                App.filters.sort = sortSelect.value;
                Deals.load(1);
            });
        }
    },

    // -------------------------------------------------------------
    // Modals
    // -------------------------------------------------------------
    setupModals() {
        // Game Detail Modal
        const gameModal = document.getElementById('game-modal');
        const closeGameBtn = document.getElementById('modal-close-game');
        if (closeGameBtn && gameModal) {
            closeGameBtn.addEventListener('click', () => gameModal.classList.remove('active'));
            gameModal.addEventListener('click', (e) => {
                if (e.target === gameModal) gameModal.classList.remove('active');
            });
        }

        // Alert Creation Modal
        const alertModal = document.getElementById('alert-modal');
        const closeAlertBtn = document.getElementById('modal-close-alert');
        if (closeAlertBtn && alertModal) {
            closeAlertBtn.addEventListener('click', () => alertModal.classList.remove('active'));
            alertModal.addEventListener('click', (e) => {
                if (e.target === alertModal) alertModal.classList.remove('active');
            });
        }

        const saveAlertBtn = document.getElementById('btn-save-alert');
        if (saveAlertBtn) {
            saveAlertBtn.addEventListener('click', async () => {
                const gameId = document.getElementById('alert-game-id').value;
                const targetPrice = document.getElementById('alert-target-price').value;
                if (!targetPrice || isNaN(targetPrice) || parseFloat(targetPrice) < 0) {
                    App.showToast('Please enter a valid target price', 'warning');
                    return;
                }
                await Alerts.create(gameId, parseFloat(targetPrice));
                if (alertModal) alertModal.classList.remove('active');
            });
        }

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (gameModal) gameModal.classList.remove('active');
                if (alertModal) alertModal.classList.remove('active');
            }
        });
    },

    // -------------------------------------------------------------
    // Refresh Button
    // -------------------------------------------------------------
    setupRefreshButton() {
        const btn = document.getElementById('btn-refresh-data');
        if (btn) {
            btn.addEventListener('click', async () => {
                btn.classList.add('loading');
                App.showToast('Fetching latest deals from CheapShark API...', 'info');
                try {
                    const res = await fetch('/api/scrape', { method: 'POST' });
                    const data = await res.json();
                    if (res.ok) {
                        App.showToast('Scraping initiated in background! Prices will refresh.', 'success');
                        setTimeout(() => {
                            if (App.currentSection === 'dashboard') Dashboard.load();
                            else if (App.currentSection === 'deals') Deals.load(App.currentPage);
                        }, 2500);
                    } else {
                        App.showToast(data.error || 'Failed to trigger scrape', 'error');
                    }
                } catch (e) {
                    App.showToast('Network error triggering price refresh', 'error');
                } finally {
                    setTimeout(() => btn.classList.remove('loading'), 1000);
                }
            });
        }
    },

    // -------------------------------------------------------------
    // UI Helpers
    // -------------------------------------------------------------
    formatPrice(price) {
        if (price === 0 || price === '0' || price === '0.00') return 'FREE';
        if (price === null || price === undefined || isNaN(price)) return 'N/A';
        return `$${parseFloat(price).toFixed(2)}`;
    },

    formatDiscount(percent) {
        const p = Math.round(parseFloat(percent) || 0);
        return p > 0 ? `-${p}%` : '';
    },

    showToast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const iconMap = {
            success: 'fa-check-circle',
            error: 'fa-circle-xmark',
            warning: 'fa-triangle-exclamation',
            info: 'fa-circle-info'
        };

        toast.innerHTML = `
            <i class="fa-solid ${iconMap[type] || 'fa-bell'}"></i>
            <span>${message}</span>
        `;

        container.appendChild(toast);
        setTimeout(() => toast.classList.add('show'), 10);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 400);
        }, 3500);
    },

    debounce(func, wait) {
        let timeout;
        return function (...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }
};

// =================================================================
// 1. DASHBOARD MODULE
// =================================================================
const Dashboard = {
    async load() {
        await Promise.all([
            this.loadStats(),
            this.loadTopDeals(),
            this.loadRecentDeals(),
            this.loadPopularGames()
        ]);
    },

    async loadStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();
            if (res.ok) {
                document.getElementById('stat-val-games').textContent = (data.total_games || 0).toLocaleString();
                document.getElementById('stat-val-deals').textContent = (data.total_deals || 0).toLocaleString();
                document.getElementById('stat-val-discount').textContent = `${Math.round(data.avg_discount || 0)}%`;

                if (data.best_deal) {
                    const best = data.best_deal;
                    document.getElementById('stat-val-best').innerHTML = `
                        <span style="font-size: 1.1rem; color: #10b981; font-weight:700;">-${best.discount_percent}%</span>
                        <div style="font-size: 0.75rem; color: #94a3b8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 140px;">${best.title}</div>
                    `;
                } else {
                    document.getElementById('stat-val-best').textContent = '—';
                }
            }
        } catch (e) {
            console.error('Failed to load dashboard stats:', e);
        }
    },

    async loadTopDeals() {
        const container = document.getElementById('dashboard-top-deals');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const res = await fetch('/api/deals?limit=8&sort=discount');
            const data = await res.json();
            if (res.ok && data.deals && data.deals.length > 0) {
                container.innerHTML = data.deals.map(deal => createGameCard(deal)).join('');
                attachCardEventListeners(container);
            } else {
                container.innerHTML = '<div class="empty-state"><p>No deals found yet. Click Refresh Data above.</p></div>';
            }
        } catch (e) {
            container.innerHTML = '<div class="empty-state"><p>Error loading top deals.</p></div>';
        }
    },

    async loadRecentDeals() {
        const container = document.getElementById('dashboard-recent-deals');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const res = await fetch('/api/deals?limit=8&sort=newest');
            const data = await res.json();
            if (res.ok && data.deals && data.deals.length > 0) {
                container.innerHTML = data.deals.map(deal => createGameCard(deal)).join('');
                attachCardEventListeners(container);
            } else {
                container.innerHTML = '<div class="empty-state"><p>No recently updated deals.</p></div>';
            }
        } catch (e) {
            container.innerHTML = '<div class="empty-state"><p>Error loading recent deals.</p></div>';
        }
    },

    async loadPopularGames() {
        const container = document.getElementById('dashboard-popular-games');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const res = await fetch('/api/deals?limit=8&sort=popularity&popular_only=true');
            const data = await res.json();
            if (res.ok && data.deals && data.deals.length > 0) {
                container.innerHTML = data.deals.map(deal => createGameCard(deal)).join('');
                attachCardEventListeners(container);
            } else {
                container.innerHTML = '<div class="empty-state"><p>No popular games found yet. Refresh data to discover games.</p></div>';
            }
        } catch (e) {
            container.innerHTML = '<div class="empty-state"><p>Error loading popular games.</p></div>';
        }
    }
};

// =================================================================
// 2. BEST DEALS / BROWSE MODULE
// =================================================================
const Deals = {
    async load(page = 1) {
        App.currentPage = page;
        const grid = document.getElementById('deals-grid');
        const countSpan = document.getElementById('deals-results-count');
        const pagination = document.getElementById('deals-pagination');

        if (grid) grid.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        // Construct Query Parameters
        const params = new URLSearchParams({
            page: page,
            limit: App.pageSize,
            sort: App.filters.sort
        });

        if (App.filters.genre) params.append('genre', App.filters.genre);
        if (App.filters.store_id) params.append('store_id', App.filters.store_id);
        if (App.filters.min_price) params.append('min_price', App.filters.min_price);
        if (App.filters.max_price) params.append('max_price', App.filters.max_price);
        if (App.filters.min_discount > 0) params.append('min_discount', App.filters.min_discount);
        if (App.filters.free) params.append('free', 'true');
        if (App.filters.popular_only) params.append('popular_only', 'true');

        try {
            const res = await fetch(`/api/deals?${params.toString()}`);
            const data = await res.json();

            if (res.ok && data.deals) {
                App.totalPages = data.total_pages || 1;
                const resultType = App.filters.popular_only ? 'popular games' : 'deals';
                if (countSpan) countSpan.textContent = `Showing ${data.deals.length} of ${data.total} ${resultType}`;

                if (data.deals.length > 0) {
                    grid.innerHTML = data.deals.map(deal => createGameCard(deal)).join('');
                    attachCardEventListeners(grid);
                    this.renderPagination(data.page, data.total_pages, pagination);
                } else {
                    grid.innerHTML = `
                        <div class="empty-state">
                            <i class="fa-solid fa-tags"></i>
                            <h3>No Deals Match Your Filter</h3>
                            <p>Try resetting filters or adjusting your price and discount limits.</p>
                        </div>
                    `;
                    if (pagination) pagination.innerHTML = '';
                }
            } else {
                grid.innerHTML = `<div class="empty-state"><p>${data.error || 'Failed to fetch deals'}</p></div>`;
            }
        } catch (e) {
            if (grid) grid.innerHTML = '<div class="empty-state"><p>Network error loading deals.</p></div>';
        }
    },

    applyFilters() {
        App.filters.genre = document.getElementById('filter-genre').value;
        App.filters.store_id = document.getElementById('filter-store').value;
        App.filters.min_price = document.getElementById('filter-min-price').value;
        App.filters.max_price = document.getElementById('filter-max-price').value;
        App.filters.min_discount = parseInt(document.getElementById('filter-min-discount').value) || 0;
        App.filters.free = document.getElementById('filter-free').checked;
        App.filters.popular_only = document.getElementById('filter-popular').value === 'true';

        // Reset to page 1 on filter application
        this.load(1);

        // On mobile, close filter panel after apply
        const panel = document.getElementById('filter-panel');
        if (panel && window.innerWidth < 768) {
            panel.classList.remove('open');
        }
    },

    resetFilters() {
        document.getElementById('filter-genre').value = '';
        document.getElementById('filter-store').value = '';
        document.getElementById('filter-min-price').value = '';
        document.getElementById('filter-max-price').value = '';
        document.getElementById('filter-min-discount').value = 0;
        document.getElementById('discount-val').textContent = '0%';
        document.getElementById('filter-free').checked = false;
        document.getElementById('filter-popular').value = 'false';

        App.filters = {
            sort: document.getElementById('sort-select').value || 'discount',
            genre: '',
            store_id: '',
            min_price: '',
            max_price: '',
            min_discount: 0,
            free: false,
            popular_only: false
        };

        this.load(1);
    },

    renderPagination(currentPage, totalPages, container) {
        if (!container || totalPages <= 1) {
            if (container) container.innerHTML = '';
            return;
        }

        let html = '';
        html += `<button class="page-btn" ${currentPage <= 1 ? 'disabled' : ''} onclick="Deals.load(${currentPage - 1})"><i class="fa-solid fa-chevron-left"></i></button>`;

        const startPage = Math.max(1, currentPage - 2);
        const endPage = Math.min(totalPages, currentPage + 2);

        if (startPage > 1) {
            html += `<button class="page-btn" onclick="Deals.load(1)">1</button>`;
            if (startPage > 2) html += `<span class="page-dots">...</span>`;
        }

        for (let p = startPage; p <= endPage; p++) {
            html += `<button class="page-btn ${p === currentPage ? 'active' : ''}" onclick="Deals.load(${p})">${p}</button>`;
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) html += `<span class="page-dots">...</span>`;
            html += `<button class="page-btn" onclick="Deals.load(${totalPages})">${totalPages}</button>`;
        }

        html += `<button class="page-btn" ${currentPage >= totalPages ? 'disabled' : ''} onclick="Deals.load(${currentPage + 1})"><i class="fa-solid fa-chevron-right"></i></button>`;

        container.innerHTML = html;
    }
};

// =================================================================
// 3. SEARCH & EXPLORE MODULE
// =================================================================
const Search = {
    async query(term) {
        try {
            const res = await fetch(`/api/search?q=${encodeURIComponent(term)}`);
            if (res.ok) {
                return await res.json();
            }
        } catch (e) {
            console.error('Search error:', e);
        }
        return [];
    },

    renderDropdown(results, container, customSelectCallback) {
        if (!container) return;
        if (!results || results.length === 0) {
            container.innerHTML = '<div class="search-item search-item-empty">No games found</div>';
            return;
        }

        container.innerHTML = results.slice(0, 8).map(game => `
            <div class="search-item" data-game-id="${game.id}">
                <img src="${game.thumb_url || '/static/images/placeholder.png'}" alt="${game.title}" class="search-thumb" onerror="this.src='/static/images/placeholder.png'">
                <div class="search-info">
                    <span class="search-title">${game.title}</span>
                    <span class="search-meta">${game.best_store_name || 'Store'} &bull; <strong style="color: #10b981;">${App.formatPrice(game.best_price)}</strong></span>
                </div>
            </div>
        `).join('');

        container.querySelectorAll('.search-item').forEach(el => {
            el.addEventListener('click', () => {
                const gameId = el.getAttribute('data-game-id');
                container.innerHTML = '';
                if (customSelectCallback) {
                    customSelectCallback(gameId);
                } else {
                    GameDetail.show(gameId);
                }
            });
        });
    },

    async performSearch(query) {
        const grid = document.getElementById('explore-grid');
        const title = document.getElementById('explore-title');
        const subtitle = document.getElementById('explore-subtitle');

        if (title) title.textContent = `Search Results: "${query}"`;
        if (subtitle) subtitle.textContent = 'Searching across all stores...';
        if (grid) grid.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        const results = await this.query(query);

        if (subtitle) subtitle.textContent = `Found ${results.length} matching game(s)`;

        if (results && results.length > 0) {
            // Map search results format to game card format
            const formatted = results.map(g => ({
                id: g.id,
                title: g.title,
                thumb_url: g.thumb_url,
                current_price: g.best_price,
                original_price: g.original_price,
                discount_percent: g.best_discount || 0,
                store_name: g.best_store_name,
                deal_url: g.best_deal_url,
                metacritic_score: g.metacritic_score,
                genre: g.genre,
                is_in_wishlist: g.is_in_wishlist
            }));
            grid.innerHTML = formatted.map(deal => createGameCard(deal)).join('');
            attachCardEventListeners(grid);
        } else {
            grid.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-magnifying-glass"></i>
                    <h3>No Matches Found</h3>
                    <p>No games matched "${query}". Try another title or explore best deals.</p>
                </div>
            `;
        }
    }
};

// =================================================================
// 4. GAME DETAIL & STORE COMPARISON MODAL
// =================================================================
const GameDetail = {
    async show(gameId) {
        const modal = document.getElementById('game-modal');
        const modalBody = document.getElementById('game-modal-body');
        if (!modal || !modalBody) return;

        modal.classList.add('active');
        modalBody.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const [gameRes, pricesRes, historyRes] = await Promise.all([
                fetch(`/api/games/${gameId}`).then(r => r.json()),
                fetch(`/api/games/${gameId}/prices`).then(r => r.json()),
                fetch(`/api/games/${gameId}/history?days=0`).then(r => r.json())
            ]);

            if (gameRes.error) {
                modalBody.innerHTML = `<div class="empty-state"><p>${gameRes.error}</p></div>`;
                return;
            }

            const game = gameRes;
            const prices = Array.isArray(pricesRes) ? pricesRes : [];
            const history = Array.isArray(historyRes) ? historyRes : [];

            // Identify lowest price
            let minPrice = Infinity;
            prices.forEach(p => {
                if (p.current_price !== null && p.current_price < minPrice) minPrice = p.current_price;
            });

            // Build Modal HTML
            modalBody.innerHTML = `
                <div class="game-detail-hero">
                    <img src="${game.large_image_url || game.thumb_url || '/static/images/placeholder.png'}" alt="${game.title}" class="hero-image" onerror="this.src='/static/images/placeholder.png'">
                    <div class="hero-overlay">
                        <div class="hero-content">
                            <h1 class="hero-title">${game.title}</h1>
                            <div class="hero-tags">
                                ${game.genre ? `<span class="badge badge-primary"><i class="fa-solid fa-tag"></i> ${game.genre}</span>` : ''}
                                ${game.platform ? `<span class="badge badge-secondary"><i class="fa-solid fa-desktop"></i> ${game.platform}</span>` : ''}
                                ${game.is_popular ? `<span class="badge badge-popular"><i class="fa-solid fa-star"></i> Popular · ${Number(game.steam_rating_count).toLocaleString()} reviews (${game.steam_rating_percent}% positive)</span>` : ''}
                                ${game.metacritic_score ? `<span class="badge badge-metacritic"><i class="fa-solid fa-star"></i> Metacritic: ${game.metacritic_score}</span>` : ''}
                                ${game.release_date ? `<span class="badge badge-secondary"><i class="fa-solid fa-calendar"></i> ${game.release_date}</span>` : ''}
                            </div>
                        </div>
                    </div>
                </div>

                <div class="detail-actions-bar">
                    <button class="btn-action ${game.is_in_wishlist ? 'active' : ''}" id="modal-wishlist-btn" data-game-id="${game.id}">
                        <i class="fa-${game.is_in_wishlist ? 'solid' : 'regular'} fa-heart"></i>
                        <span>${game.is_in_wishlist ? 'In Wishlist' : 'Add to Wishlist'}</span>
                    </button>
                    <button class="btn-action" id="modal-alert-btn" data-game-id="${game.id}" data-title="${encodeURIComponent(game.title)}" data-price="${game.best_price || 0}">
                        <i class="fa-solid fa-bell"></i>
                        <span>Set Price Alert</span>
                    </button>
                    ${game.best_deal_url ? `
                        <a href="${game.best_deal_url}" target="_blank" rel="noopener noreferrer" class="btn-primary">
                            <i class="fa-solid fa-cart-shopping"></i> Buy at Lowest Price (${App.formatPrice(game.best_price)})
                        </a>
                    ` : ''}
                </div>

                ${game.description ? `
                    <div class="detail-section">
                        <h3>About the Game</h3>
                        <p class="game-description">${game.description}</p>
                    </div>
                ` : ''}

                <!-- Price Comparison Table -->
                <div class="detail-section">
                    <h3><i class="fa-solid fa-code-compare"></i> Store Price Comparison</h3>
                    <div class="table-responsive">
                        <table class="price-table">
                            <thead>
                                <tr>
                                    <th>Store</th>
                                    <th>Current Price</th>
                                    <th>Original Price</th>
                                    <th>Discount</th>
                                    <th>Savings</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${prices.length > 0 ? prices.map(p => {
                                    const isCheapest = p.current_price === minPrice && minPrice !== Infinity;
                                    const savings = (p.original_price && p.current_price !== null) ? Math.max(0, p.original_price - p.current_price) : 0;
                                    return `
                                        <tr class="${isCheapest ? 'row-cheapest' : ''}">
                                            <td>
                                                <div class="store-cell">
                                                    <strong>${p.store_name}</strong>
                                                    ${isCheapest ? '<span class="badge-cheapest"><i class="fa-solid fa-trophy"></i> Best Price</span>' : ''}
                                                </div>
                                            </td>
                                            <td class="price-cell">
                                                <strong class="curr-price ${isCheapest ? 'cheapest-green' : ''}">${App.formatPrice(p.current_price)}</strong>
                                            </td>
                                            <td class="orig-price-cell">
                                                <span class="orig-price">${App.formatPrice(p.original_price)}</span>
                                            </td>
                                            <td>
                                                ${p.discount_percent > 0 ? `<span class="discount-pill">-${Math.round(p.discount_percent)}%</span>` : '0%'}
                                            </td>
                                            <td>
                                                <span class="savings-amount">${savings > 0 ? `Save $${savings.toFixed(2)}` : '—'}</span>
                                            </td>
                                            <td>
                                                ${p.deal_url ? `
                                                    <a href="${p.deal_url}" target="_blank" rel="noopener noreferrer" class="btn-deal">
                                                        Visit Store <i class="fa-solid fa-arrow-up-right-from-square"></i>
                                                    </a>
                                                ` : 'N/A'}
                                            </td>
                                        </tr>
                                    `;
                                }).join('') : '<tr><td colspan="6" style="text-align: center; color: #94a3b8;">No store pricing details found.</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Price History Chart in Modal -->
                <div class="detail-section">
                    <h3><i class="fa-solid fa-chart-line"></i> Price History</h3>
                    <div class="chart-container" style="position: relative; height: 260px; width: 100%;">
                        <canvas id="modal-history-chart"></canvas>
                    </div>
                    <div class="history-events" id="modal-history-events"></div>
                </div>
            `;

            // Modal Button Events
            const wBtn = document.getElementById('modal-wishlist-btn');
            if (wBtn) {
                wBtn.addEventListener('click', async () => {
                    await Wishlist.toggle(game.id, wBtn);
                    const isIn = wBtn.classList.contains('active');
                    wBtn.querySelector('span').textContent = isIn ? 'In Wishlist' : 'Add to Wishlist';
                    const icon = wBtn.querySelector('i');
                    icon.className = isIn ? 'fa-solid fa-heart' : 'fa-regular fa-heart';
                });
            }

            const aBtn = document.getElementById('modal-alert-btn');
            if (aBtn) {
                aBtn.addEventListener('click', () => {
                    Alerts.showCreateModal(game.id, game.title, game.best_price, game.thumb_url);
                });
            }

            // Render Chart
            this.renderHistoryChart(history, document.getElementById('modal-history-chart'));

        } catch (e) {
            console.error('Failed to load game modal:', e);
            modalBody.innerHTML = '<div class="empty-state"><p>Error loading game details.</p></div>';
        }
    },

    renderHistoryChart(historyData, canvas) {
        if (!canvas) return;
        if (App.charts.modalHistory) {
            App.charts.modalHistory.destroy();
            App.charts.modalHistory = null;
        }

        renderPriceHistoryEvents(
            historyData,
            document.getElementById('modal-history-events')
        );

        if (!historyData || historyData.length === 0) {
            const ctx = canvas.getContext('2d');
            ctx.font = '14px Inter, sans-serif';
            ctx.fillStyle = '#94a3b8';
            ctx.textAlign = 'center';
            ctx.fillText('No historical price points recorded yet.', canvas.width / 2, canvas.height / 2);
            return;
        }

        App.charts.modalHistory = new Chart(
            canvas,
            buildPriceHistoryChartConfig(historyData, true)
        );
    }
};

// =================================================================
// 5. WISHLIST MODULE
// =================================================================
const Wishlist = {
    async load() {
        const grid = document.getElementById('wishlist-grid');
        if (!grid) return;
        grid.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const res = await fetch('/api/wishlist');
            const list = await res.json();

            if (res.ok && Array.isArray(list) && list.length > 0) {
                grid.innerHTML = list.map(item => `
                    <div class="game-card wishlist-card" data-game-id="${item.game_id}">
                        <div class="card-thumb-wrap">
                            <img src="${item.thumb_url || '/static/images/placeholder.png'}" alt="${item.title}" class="card-thumb" onerror="this.src='/static/images/placeholder.png'">
                            ${item.discount_percent > 0 ? `<div class="discount-badge">-${Math.round(item.discount_percent)}%</div>` : ''}
                            <button class="btn-remove-wishlist" data-game-id="${item.game_id}" title="Remove from Wishlist">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        </div>
                        <div class="card-body">
                            <h3 class="card-title">${item.title}</h3>
                            <div class="card-store"><i class="fa-solid fa-store"></i> ${item.store_name || 'Store Deal'}</div>
                            <div class="card-price-row">
                                <div class="price-info">
                                    <span class="current-price">${App.formatPrice(item.current_price)}</span>
                                    ${item.original_price > item.current_price ? `<span class="original-price">${App.formatPrice(item.original_price)}</span>` : ''}
                                </div>
                                ${item.deal_url ? `
                                    <a href="${item.deal_url}" target="_blank" rel="noopener noreferrer" class="btn-buy-card" onclick="event.stopPropagation();">
                                        <i class="fa-solid fa-cart-shopping"></i> Buy
                                    </a>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                `).join('');

                // Remove button handlers
                grid.querySelectorAll('.btn-remove-wishlist').forEach(btn => {
                    btn.addEventListener('click', async (e) => {
                        e.stopPropagation();
                        const gId = btn.getAttribute('data-game-id');
                        await Wishlist.remove(gId);
                        btn.closest('.game-card').remove();
                    });
                });

                // Click card opens detail
                grid.querySelectorAll('.game-card').forEach(card => {
                    card.addEventListener('click', () => {
                        const gId = card.getAttribute('data-game-id');
                        GameDetail.show(gId);
                    });
                });

            } else {
                grid.innerHTML = `
                    <div class="empty-state">
                        <i class="fa-solid fa-heart-crack"></i>
                        <h3>Your Wishlist is Empty</h3>
                        <p>Click the heart icon on any game card to track it here!</p>
                    </div>
                `;
            }
        } catch (e) {
            grid.innerHTML = '<div class="empty-state"><p>Error loading wishlist.</p></div>';
        }
    },

    async toggle(gameId, buttonElement) {
        try {
            const isCurrentlyActive = buttonElement.classList.contains('active');
            if (isCurrentlyActive) {
                // Remove
                const res = await fetch(`/api/wishlist/${gameId}`, { method: 'DELETE' });
                if (res.ok) {
                    buttonElement.classList.remove('active');
                    const icon = buttonElement.querySelector('i');
                    if (icon) {
                        icon.classList.remove('fa-solid');
                        icon.classList.add('fa-regular');
                    }
                    App.showToast('Removed from wishlist', 'info');
                }
            } else {
                // Add
                const res = await fetch('/api/wishlist', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ game_id: parseInt(gameId) })
                });
                if (res.ok) {
                    buttonElement.classList.add('active');
                    const icon = buttonElement.querySelector('i');
                    if (icon) {
                        icon.classList.remove('fa-regular');
                        icon.classList.add('fa-solid');
                    }
                    App.showToast('Added to wishlist!', 'success');
                }
            }
        } catch (e) {
            App.showToast('Failed to update wishlist', 'error');
        }
    },

    async remove(gameId) {
        try {
            const res = await fetch(`/api/wishlist/${gameId}`, { method: 'DELETE' });
            if (res.ok) {
                App.showToast('Game removed from wishlist', 'info');
                const remaining = document.querySelectorAll('#wishlist-grid .game-card');
                if (remaining.length <= 1) {
                    Wishlist.load();
                }
            }
        } catch (e) {
            App.showToast('Error removing game from wishlist', 'error');
        }
    }
};

// =================================================================
// 6. PRICE ALERTS MODULE
// =================================================================
const Alerts = {
    async load() {
        const activeList = document.getElementById('active-alerts-list');
        const triggeredList = document.getElementById('triggered-alerts-list');

        if (activeList) activeList.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';
        if (triggeredList) triggeredList.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const res = await fetch('/api/alerts');
            const data = await res.json();

            if (res.ok && Array.isArray(data)) {
                const activeAlerts = data.filter(a => !a.is_triggered && a.is_active);
                const triggeredAlerts = data.filter(a => a.is_triggered);

                // Render Active
                if (activeList) {
                    if (activeAlerts.length > 0) {
                        activeList.innerHTML = activeAlerts.map(a => this.renderAlertCard(a, false)).join('');
                        this.attachAlertEvents(activeList);
                    } else {
                        activeList.innerHTML = `
                            <div class="empty-state">
                                <i class="fa-solid fa-bell-slash"></i>
                                <h3>No Active Alerts</h3>
                                <p>Set a target price on any game to be notified when it drops!</p>
                            </div>
                        `;
                    }
                }

                // Render Triggered
                if (triggeredList) {
                    if (triggeredAlerts.length > 0) {
                        triggeredList.innerHTML = triggeredAlerts.map(a => this.renderAlertCard(a, true)).join('');
                        this.attachAlertEvents(triggeredList);
                    } else {
                        triggeredList.innerHTML = `
                            <div class="empty-state">
                                <i class="fa-solid fa-bullhorn"></i>
                                <h3>No Triggered Alerts Yet</h3>
                                <p>When a tracked game reaches or drops below your target price, it will show here.</p>
                            </div>
                        `;
                    }
                }
            }
        } catch (e) {
            console.error('Failed to load alerts:', e);
        }
    },

    renderAlertCard(alert, isTriggered) {
        return `
            <div class="alert-card ${isTriggered ? 'alert-card-triggered' : ''}" data-alert-id="${alert.id}">
                <img src="${alert.thumb_url || '/static/images/placeholder.png'}" alt="${alert.title}" class="alert-thumb" onerror="this.src='/static/images/placeholder.png'">
                <div class="alert-body">
                    <h3 class="alert-title">${alert.title}</h3>
                    <div class="alert-meta">
                        <span class="alert-target">Target: <strong>${App.formatPrice(alert.target_price)}</strong></span>
                        <span class="alert-current">Current: <strong>${App.formatPrice(alert.current_price)}</strong></span>
                        ${isTriggered ? `
                            <span class="badge badge-success"><i class="fa-solid fa-circle-check"></i> Price Dropped to ${App.formatPrice(alert.triggered_price)}!</span>
                        ` : `
                            <span class="badge badge-warning"><i class="fa-solid fa-clock"></i> Monitoring</span>
                        `}
                    </div>
                </div>
                <div class="alert-actions">
                    ${isTriggered && alert.deal_url ? `
                        <a href="${alert.deal_url}" target="_blank" rel="noopener noreferrer" class="btn-primary btn-sm">
                            <i class="fa-solid fa-cart-shopping"></i> Buy Now
                        </a>
                    ` : ''}
                    <button class="btn-danger-outline btn-sm btn-delete-alert" data-alert-id="${alert.id}" title="Delete Alert">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            </div>
        `;
    },

    attachAlertEvents(container) {
        container.querySelectorAll('.btn-delete-alert').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const alertId = btn.getAttribute('data-alert-id');
                await Alerts.delete(alertId);
                btn.closest('.alert-card').remove();
            });
        });
    },

    showCreateModal(gameId, title, currentPrice, thumbUrl) {
        const modal = document.getElementById('alert-modal');
        if (!modal) return;

        document.getElementById('alert-game-id').value = gameId;
        document.getElementById('alert-game-title').textContent = title;
        document.getElementById('alert-current-price').textContent = App.formatPrice(currentPrice);
        document.getElementById('alert-game-thumb').src = thumbUrl || '/static/images/placeholder.png';

        // Suggest a 20% discount target
        const suggested = currentPrice ? (parseFloat(currentPrice) * 0.8).toFixed(2) : '9.99';
        document.getElementById('alert-target-price').value = suggested;

        modal.classList.add('active');
    },

    async create(gameId, targetPrice) {
        try {
            const res = await fetch('/api/alerts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ game_id: parseInt(gameId), target_price: targetPrice })
            });
            const data = await res.json();
            if (res.ok) {
                App.showToast('Price alert successfully set!', 'success');
            } else {
                App.showToast(data.error || 'Failed to set price alert', 'error');
            }
        } catch (e) {
            App.showToast('Network error setting alert', 'error');
        }
    },

    async delete(alertId) {
        try {
            const res = await fetch(`/api/alerts/${alertId}`, { method: 'DELETE' });
            if (res.ok) {
                App.showToast('Alert deleted', 'info');
            }
        } catch (e) {
            App.showToast('Error deleting alert', 'error');
        }
    }
};

// =================================================================
// 7. PRICE HISTORY MODULE
// =================================================================
const PriceHistory = {
    async loadForGame(gameId) {
        const container = document.getElementById('history-content');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const [game, history] = await Promise.all([
                fetch(`/api/games/${gameId}`).then(r => r.json()),
                fetch(`/api/games/${gameId}/history?days=0`).then(r => r.json())
            ]);

            if (game.error) {
                container.innerHTML = `<div class="empty-state"><p>${game.error}</p></div>`;
                return;
            }

            container.innerHTML = `
                <div class="history-game-header">
                    <img src="${game.thumb_url || '/static/images/placeholder.png'}" alt="${game.title}" class="history-game-thumb" onerror="this.src='/static/images/placeholder.png'">
                    <div>
                        <h2>${game.title}</h2>
                        <p style="color: #94a3b8;">Current Best Price: <strong style="color: #10b981;">${App.formatPrice(game.best_price)}</strong> on ${game.best_store_name || 'Store'}</p>
                    </div>
                </div>
                <div class="chart-container" style="position: relative; height: 380px; width: 100%; margin-top: 20px;">
                    <canvas id="standalone-history-chart"></canvas>
                </div>
                <div class="history-events" id="history-events"></div>
            `;

            const canvas = document.getElementById('standalone-history-chart');
            if (App.charts.history) {
                App.charts.history.destroy();
                App.charts.history = null;
            }

            renderPriceHistoryEvents(history, document.getElementById('history-events'));

            if (!history || history.length === 0) {
                const ctx = canvas.getContext('2d');
                ctx.font = '16px Inter, sans-serif';
                ctx.fillStyle = '#94a3b8';
                ctx.textAlign = 'center';
                ctx.fillText('No historical price points recorded for this game yet.', canvas.width / 2, canvas.height / 2);
                return;
            }

            App.charts.history = new Chart(
                canvas,
                buildPriceHistoryChartConfig(history, true)
            );

        } catch (e) {
            console.error('History load error:', e);
            container.innerHTML = '<div class="empty-state"><p>Error loading price history.</p></div>';
        }
    }
};

// =================================================================
// 8. CARD CREATION HELPER
// =================================================================
function parseHistoryDate(value) {
    const timestamp = String(value);
    return new Date(/[zZ]|[+-]\d{2}:\d{2}$/.test(timestamp) ? timestamp : `${timestamp}Z`);
}

function buildPriceHistoryChartConfig(historyData, showLegend) {
    const colors = ['#00d4ff', '#a78bfa', '#f59e0b', '#34d399', '#fb7185', '#60a5fa'];
    const stores = new Map();
    [...historyData]
        .sort((a, b) => parseHistoryDate(a.recorded_at) - parseHistoryDate(b.recorded_at))
        .forEach(point => {
            const key = String(point.store_id);
            if (!stores.has(key)) stores.set(key, { name: point.store_name || 'Store', points: [] });
            stores.get(key).points.push({
                x: parseHistoryDate(point.recorded_at).getTime(),
                y: Number(point.price),
                recorded_at: point.recorded_at,
                previous_price: point.previous_price,
                price_change: point.price_change,
                change_type: point.change_type
            });
        });

    return {
        type: 'line',
        data: {
            datasets: [...stores.values()].map((store, index) => {
                const color = colors[index % colors.length];
                return {
                    label: store.name,
                    data: store.points,
                    borderColor: color,
                    backgroundColor: `${color}26`,
                    borderWidth: 2,
                    stepped: 'after',
                    fill: false,
                    pointBackgroundColor: context => {
                        const movement = context.raw && context.raw.change_type;
                        if (movement === 'decrease') return '#34d399';
                        if (movement === 'increase') return '#fb7185';
                        return color;
                    },
                    pointBorderColor: '#fff',
                    pointRadius: 4,
                    pointHoverRadius: 6
                };
            })
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            parsing: false,
            interaction: { mode: 'nearest', intersect: false },
            plugins: {
                legend: { display: showLegend, labels: { color: '#e2e8f0' } },
                tooltip: {
                    backgroundColor: '#12121a',
                    titleColor: '#00d4ff',
                    bodyColor: '#e2e8f0',
                    borderColor: '#2a2a40',
                    borderWidth: 1,
                    callbacks: {
                        title: items => items.length
                            ? parseHistoryDate(items[0].raw.recorded_at).toLocaleString()
                            : '',
                        label: context => `${context.dataset.label}: $${context.raw.y.toFixed(2)}`,
                        afterLabel: context => {
                            const point = context.raw;
                            if (point.previous_price === null || point.previous_price === undefined) {
                                return 'First recorded price';
                            }
                            const amount = Math.abs(Number(point.price_change)).toFixed(2);
                            return point.change_type === 'decrease'
                                ? `Dropped $${amount} from $${Number(point.previous_price).toFixed(2)}`
                                : `Raised $${amount} from $${Number(point.previous_price).toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'linear',
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#94a3b8',
                        callback: value => new Date(Number(value)).toLocaleDateString()
                    }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#94a3b8',
                        callback: value => `$${value}`
                    }
                }
            }
        }
    };
}

function renderPriceHistoryEvents(historyData, container) {
    if (!container) return;
    container.innerHTML = '';
    const events = (historyData || [])
        .filter(point => point.previous_price !== null && point.previous_price !== undefined && point.price_change)
        .sort((a, b) => parseHistoryDate(b.recorded_at) - parseHistoryDate(a.recorded_at))
        .slice(0, 20);

    const heading = document.createElement('h4');
    heading.textContent = 'Recent price changes';
    container.appendChild(heading);

    if (!events.length) {
        const empty = document.createElement('p');
        empty.textContent = 'No price changes recorded yet. Changes will appear after the next price update.';
        container.appendChild(empty);
        return;
    }

    const list = document.createElement('ol');
    events.forEach(point => {
        const item = document.createElement('li');
        item.className = `history-event ${point.change_type}`;
        const direction = point.change_type === 'decrease' ? 'dropped' : 'raised';
        item.textContent = `${parseHistoryDate(point.recorded_at).toLocaleString()} · ${point.store_name}: $${Number(point.previous_price).toFixed(2)} → $${Number(point.price).toFixed(2)} (${direction} $${Math.abs(Number(point.price_change)).toFixed(2)})`;
        list.appendChild(item);
    });
    container.appendChild(list);
}

function createGameCard(game) {
    const discount = Math.round(parseFloat(game.discount_percent) || 0);
    const isFree = game.current_price === 0 || game.current_price === '0.00';
    const isWishlisted = !!game.is_in_wishlist;

    return `
        <div class="game-card" data-game-id="${game.id}">
            <div class="card-thumb-wrap">
                <img src="${game.thumb_url || '/static/images/placeholder.png'}" alt="${game.title}" class="card-thumb" onerror="this.src='/static/images/placeholder.png'">
                ${discount > 0 ? `<div class="discount-badge">-${discount}%</div>` : ''}
                ${isFree ? `<div class="free-badge">FREE</div>` : ''}
                <button class="wishlist-btn ${isWishlisted ? 'active' : ''}" data-game-id="${game.id}" title="${isWishlisted ? 'In Wishlist' : 'Add to Wishlist'}">
                    <i class="fa-${isWishlisted ? 'solid' : 'regular'} fa-heart"></i>
                </button>
            </div>
            <div class="card-body">
                <div class="card-meta">
                    <span class="store-tag"><i class="fa-solid fa-store"></i> ${game.store_name || 'Store'}</span>
                    ${game.is_popular ? `<span class="popularity-tag" title="${Number(game.steam_rating_percent)}% positive from Steam users"><i class="fa-solid fa-star"></i> Popular · ${Number(game.steam_rating_count).toLocaleString()} reviews</span>` : ''}
                    ${game.metacritic_score ? `<span class="meta-score" title="Metacritic Score"><i class="fa-solid fa-star"></i> ${game.metacritic_score}</span>` : ''}
                </div>
                <h3 class="card-title" title="${game.title}">${game.title}</h3>
                <div class="card-price-row">
                    <div class="price-info">
                        <span class="current-price ${isFree ? 'price-free' : ''}">${App.formatPrice(game.current_price)}</span>
                        ${game.original_price && game.original_price > game.current_price ? `<span class="original-price">${App.formatPrice(game.original_price)}</span>` : ''}
                    </div>
                    ${game.deal_url ? `
                        <a href="${game.deal_url}" target="_blank" rel="noopener noreferrer" class="btn-buy-card" onclick="event.stopPropagation();" title="Go to Store">
                            <i class="fa-solid fa-cart-shopping"></i> Deal
                        </a>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

function attachCardEventListeners(container) {
    if (!container) return;

    // Card click opens modal
    container.querySelectorAll('.game-card').forEach(card => {
        card.addEventListener('click', () => {
            const gameId = card.getAttribute('data-game-id');
            if (gameId) GameDetail.show(gameId);
        });
    });

    // Wishlist toggle button click
    container.querySelectorAll('.wishlist-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const gameId = btn.getAttribute('data-game-id');
            await Wishlist.toggle(gameId, btn);
        });
    });
}

// Start application
document.addEventListener('DOMContentLoaded', () => App.init());
