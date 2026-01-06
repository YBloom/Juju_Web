
import { router } from './modules/router.js';
import { state } from './modules/state.js';
import * as ui from './modules/ui.js';
import { loadHeatmap } from './modules/heatmap.js';

// Expose functions to global scope for HTML event handlers
window.router = router;
window.changeSort = ui.changeSort;
window.toggleColumn = ui.toggleColumn;
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

// Expose state for debugging if needed
window.appState = state;

document.addEventListener('DOMContentLoaded', () => {
    ui.renderColumnToggles();
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
    });

    router.on('/lab/heatmap', () => {
        ui.showTabContent('tab-lab-heatmap');
        loadHeatmap();
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

    // Changelog Modal
    const versionLink = document.getElementById('version-link');
    const changelogOverlay = document.getElementById('changelog-overlay');
    const changelogCloseBtn = document.getElementById('changelog-close-btn');

    if (versionLink && changelogOverlay) {
        versionLink.addEventListener('click', (e) => {
            e.preventDefault();
            changelogOverlay.classList.add('active');
        });

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
