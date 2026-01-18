
import { router } from './modules/router.js';
import { state } from './modules/state.js';
import { initErrorHandler } from './modules/error_handler.js';
import * as ui from './modules/ui.js';
import { loadHeatmap, updateLabCardStats } from './modules/heatmap.js?v=20260118_2';

// Init Global Error Handler
initErrorHandler();

// ... (existing code)


// Expose functions to global scope for HTML event handlers
window.router = router;
window.applyFilters = ui.applyFilters;
window.searchInCoCast = ui.searchInCoCast;
window.addCastInput = ui.addCastInput;
window.removeCastInput = ui.removeCastInput;
window.doCoCastSearch = ui.doCoCastSearch;
window.setCoCastRange = ui.setCoCastRange;
window.setQuickDate = ui.setQuickDate;
window.doDateSearch = ui.doDateSearch;
window.applyDateFilters = ui.applyDateFilters;
window.applyDetailFilters = ui.applyDetailFilters;
window.jumpToDetail = ui.jumpToDetail;
window.doLogout = ui.doLogout;
window.showAddSubModal = ui.showAddSubModal;
window.hideAddSubModal = ui.hideAddSubModal;
window.selectSubType = ui.selectSubType;
window.doAddSubscription = ui.doAddSubscription;
window.handleDeleteSubscription = ui.handleDeleteSubscription;

// Expose state for debugging if needed
window.appState = state;

document.addEventListener('DOMContentLoaded', () => {
    // ui.renderColumnToggles(); // Removed in v2.1 (No Table Header)
    ui.fetchUpdateStatus();
    ui.initActorAutocomplete();

    // Router Setup
    router.on('/', () => {
        ui.showTabContent('tab-hlq');
        if (state.allEvents.length === 0) {
            ui.initHlqTab();
        }
    });

    router.on('/detail/:id', (params) => {
        ui.showDetailView(params.id);
    });

    router.on('/date', (params, query) => {
        ui.showTabContent('tab-date');
        if (query.d) {
            const input = document.getElementById('date-input');
            if (input) {
                input.value = query.d;
                ui.doDateSearch();
            }
        }
    });

    router.on('/cocast', () => {
        ui.showTabContent('tab-cocast');
    });

    router.on('/lab', () => {
        ui.showTabContent('tab-lab');
        updateLabCardStats();
    });

    router.on('/lab/heatmap', () => {
        ui.showTabContent('tab-lab-heatmap');
        loadHeatmap();
    });

    router.on('/user', () => {
        ui.showTabContent('tab-user');
        ui.initUserTab();
    });

    router.on('/user/subscriptions', () => {
        ui.showTabContent('tab-user-subscriptions');
        ui.initSubscriptionManagement();
    });

    // Global search hook
    const globalSearchEl = document.getElementById('global-search');
    if (globalSearchEl) {
        globalSearchEl.addEventListener('input', ui.applyFilters);
    }

    // Global click for closing dropdowns (Autocomplete & Column Filters)
    document.addEventListener('click', (e) => {
        // Autocomplete
        if (!e.target.closest('.input-wrapper')) {
            document.querySelectorAll('.autocomplete-suggestions').forEach(el => el.style.display = 'none');
        }

        // Column Filters (in CoCast table)
        document.querySelectorAll('.filter-dropdown').forEach(dd => {
            if (!dd.contains(e.target) && !dd.parentNode.contains(e.target)) {
                dd.style.display = 'none';
            }
        });
    });

    // Changelog Modal (use event delegation since version-link is dynamically created)
    const changelogOverlay = document.getElementById('changelog-overlay');
    const changelogCloseBtn = document.getElementById('changelog-close-btn');

    // Event delegation for dynamically created version link
    document.addEventListener('click', (e) => {
        if (e.target.id === 'version-link' || e.target.closest('#version-link')) {
            e.preventDefault();
            changelogOverlay?.classList.add('active');
        }
    });

    if (changelogOverlay) {
        changelogCloseBtn?.addEventListener('click', () => {
            changelogOverlay.classList.remove('active');
        });

        changelogOverlay.addEventListener('click', (e) => {
            if (e.target === changelogOverlay) {
                changelogOverlay.classList.remove('active');
            }
        });
    }
});
