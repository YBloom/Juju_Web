document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
});

function setupTabs() {
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            // Add active to clicked
            tab.classList.add('active');
            document.getElementById(tab.dataset.target).classList.add('active');
        });
    });
}

// API Helpers
const API_BASE = '/api';

async function fetchAPI(endpoint, params = {}) {
    const query = new URLSearchParams(params).toString();
    const url = `${API_BASE}${endpoint}?${query}`;
    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('Network response was not ok');
        return await res.json();
    } catch (e) {
        console.error("API Error:", e);
        return { error: e.message };
    }
}

// Renderers
function renderResults(containerId, data) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';

    if (data.error) {
        container.innerHTML = `<div class="empty-state">⚠️ Error: ${data.error}</div>`;
        return;
    }

    if (!data.results || data.results.length === 0) {
        container.innerHTML = '<div class="empty-state">No results found</div>';
        return;
    }

    // Determine if data is Events (search) or Tickets (date/cast)
    // Structure: 
    // Event: {title, tickets: [...]}
    // Ticket: {title, session_time, ...}

    // We normalize to list of blocks
    if (data.results[0].tickets) {
        // It's a list of Events
        data.results.forEach(event => {
            const block = document.createElement('div');
            block.className = 'event-block';
            block.innerHTML = `<div class="event-header">${event.title} <span style="font-size:0.8em;font-weight:normal">${event.location || ''}</span></div>`;

            const list = document.createElement('div');
            list.className = 'result-list';

            // Filter out expired if needed, or sort
            const tickets = event.tickets.sort((a, b) => new Date(a.session_time) - new Date(b.session_time));

            tickets.forEach(t => {
                list.appendChild(createTicketCard(t));
            });

            block.appendChild(list);
            container.appendChild(block);
        });
    } else {
        // It's a list of Tickets
        const list = document.createElement('div');
        list.className = 'result-list';
        data.results.forEach(t => {
            list.appendChild(createTicketCard(t));
        });
        container.appendChild(list);
    }
}

function createTicketCard(ticket) {
    const card = document.createElement('div');
    card.className = 'ticket-card';

    const dateStr = ticket.session_time ? new Date(ticket.session_time).toLocaleString('zh-CN', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    }) : 'TBD';

    const castStr = ticket.cast ? ticket.cast.map(c => c.name).join(' | ') : 'TBD';
    const statusClass = ticket.stock > 0 ? 'active' : (ticket.status === 'pending' ? 'pending' : 'sold_out');
    const statusText = ticket.status === 'pending' ? 'PENDING' : (ticket.stock > 0 ? 'AVAILABLE' : 'SOLD OUT');

    card.innerHTML = `
        <div class="ticket-header">
            <span style="font-weight:700">${dateStr}</span>
            <span class="status ${statusClass}">${statusText}</span>
        </div>
        <div class="ticket-info">
            ${ticket.title} <span style="margin-left:10px">¥${ticket.price}</span> <span style="margin-left:10px">Stock: ${ticket.stock}</span>
        </div>
        <div class="cast-info">
            ${castStr}
        </div>
    `;
    return card;
}

// Action Handlers
async function doSearch() {
    const q = document.getElementById('search-input').value.trim();
    if (!q) return;

    const container = 'search-results';
    document.getElementById(container).innerHTML = '<div class="loading">Searching...</div>';

    const data = await fetchAPI('/events/search', { q });
    renderResults(container, data);
}

async function doDateSearch() {
    const date = document.getElementById('date-input').value;
    if (!date) return;

    const container = 'date-results';
    document.getElementById(container).innerHTML = '<div class="loading">Loading...</div>';

    const data = await fetchAPI('/events/date', { date });
    renderResults(container, data);
}

async function doCoCastSearch() {
    const casts = document.getElementById('cast-input').value.trim();
    if (!casts) return;

    const container = 'cast-results';
    document.getElementById(container).innerHTML = '<div class="loading">Searching...</div>';

    const data = await fetchAPI('/events/co-cast', { casts });
    renderResults(container, data);
}
