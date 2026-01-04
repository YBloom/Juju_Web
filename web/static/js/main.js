
import { router } from './modules/router.js';
import { state } from './modules/state.js';
import * as ui from './modules/ui.js';

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
});
