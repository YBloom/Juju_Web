
import { state } from '../state.js';
import { initCoCastDates } from './cocast.js';

export function showTabContent(tabId) {
    state.currentTab = tabId;

    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    const target = document.getElementById(tabId);
    if (target) {
        target.classList.add('active');
    }

    document.querySelectorAll('.nav-btn').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === tabId);
    });

    if (tabId === 'tab-date') {
        const dateInput = document.getElementById('date-input');
        if (dateInput && !dateInput.value) {
            const today = new Date().toISOString().split('T')[0];
            dateInput.value = today;
        }
    }

    document.getElementById('detail-view').classList.add('hidden');
    document.querySelectorAll('.tab-content').forEach(c => {
        if (c.id === tabId) c.classList.remove('hidden');
    });

    if (tabId === 'tab-cocast') {
        initCoCastDates();
    }
}
