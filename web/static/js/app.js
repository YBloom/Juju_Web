// App State
const state = {
    allEvents: [], // Cache for HLQ list
    currentTab: 'tab-hlq'
};

document.addEventListener('DOMContentLoaded', () => {
    // Initial load
    initHlqTab();
});

function switchTab(tabId) {
    state.currentTab = tabId;

    // UI Update
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-target="${tabId}"]`).classList.add('active');

    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');

    // Hide details if open
    document.getElementById('detail-view').classList.add('hidden');
    document.getElementById('tab-hlq').classList.remove('hidden'); // Ensure list is visible when switching back

    if (tabId === 'tab-hlq' && state.allEvents.length === 0) {
        initHlqTab(); // Load data if empty
    }
}

// --- Hulaquan Tab Logic ---

async function initHlqTab() {
    const container = document.getElementById('hlq-list-container');
    container.innerHTML = '<div style="padding:20px;text-align:center">Loading events...</div>';

    try {
        const res = await fetch('/api/events/list');
        const data = await res.json();
        state.allEvents = data.results;
        renderEventTable(state.allEvents);
    } catch (e) {
        container.innerHTML = `<div style="color:red">Error loading events: ${e.message}</div>`;
    }
}

function renderEventTable(events) {
    const container = document.getElementById('hlq-list-container');
    if (!events || events.length === 0) {
        container.innerHTML = '<div style="padding:20px">No events found.</div>';
        return;
    }

    let html = `
        <table class="data-table">
            <thead>
                <tr>
                    <th width="80">城市</th>
                    <th width="200">最新更新</th>
                    <th>音乐剧</th>
                    <th>演出场馆</th>
                    <th width="100">操作</th>
                </tr>
            </thead>
            <tbody>
    `;

    events.forEach(e => {
        const updateTime = e.update_time ? new Date(e.update_time).toLocaleDateString() : '-';
        html += `
            <tr onclick="loadEventDetail('${e.id}')">
                <td class="city-cell">${extractCity(e.location) || '其他'}</td>
                <td class="time-cell">${updateTime}</td>
                <td class="title-cell">${e.title}</td>
                <td>${e.location || '-'}</td>
                <td><button onclick="event.stopPropagation(); loadEventDetail('${e.id}')">查看详情</button></td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

function extractCity(loc) {
    if (!loc) return '';
    if (loc.includes('上海')) return '上海';
    if (loc.includes('北京')) return '北京';
    if (loc.includes('广州')) return '广州';
    if (loc.includes('深圳')) return '深圳';
    return ''; // TODO: better city extraction
}

// --- Detail View Logic ---

async function loadEventDetail(eventId) {
    // Hide list, show detail
    document.getElementById('tab-hlq').classList.remove('active'); // Hide tab content wrapper temporarily? 
    // Actually better to keep tab active but hide list container and show detail container
    // But structure is MAIN -> Tab Content -> List. Detail view is sibling to Tab Contents?
    // Let's hide List Container inside tab-hlq

    // Better: We defined #detail-view as sibling to tabs in HTML.
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById('detail-view').classList.remove('hidden');

    const container = document.getElementById('detail-content');
    container.innerHTML = 'Loading details...';

    try {
        const res = await fetch(`/api/events/${eventId}`);
        const data = await res.json();
        if (data.results && data.results.length > 0) {
            renderDetailView(data.results[0]);
        } else {
            container.innerHTML = 'Event not found.';
        }
    } catch (e) {
        container.innerHTML = 'Error loading details.';
    }
}

function closeDetail() {
    document.getElementById('detail-view').classList.add('hidden');
    document.getElementById('tab-hlq').classList.add('active'); // Restore list view
}

function renderDetailView(event) {
    const container = document.getElementById('detail-content');

    // Render Tickets Table
    let html = `
        <h2>${event.title}</h2>
        <p>📍 ${event.location || 'Unknown Location'}</p>
        <div style="margin-top:20px">
            <table class="data-table">
                <thead>
                    <tr>
                        <th width="120">时间</th>
                        <th>状态</th>
                        <th>余票/总票</th>
                        <th>价格</th>
                        <th>卡司</th>
                    </tr>
                </thead>
                <tbody>
    `;

    // Sort logic
    const tickets = event.tickets.sort((a, b) => new Date(a.session_time) - new Date(b.session_time));

    tickets.forEach(t => {
        const timeStr = t.session_time ? new Date(t.session_time).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '待定';
        const castStr = t.cast.map(c => c.name).join(' ');
        const statusClass = t.stock > 0 ? 'active' : (t.status === 'pending' ? 'pending' : 'sold_out');
        const statusText = t.status === 'pending' ? '预售/待开' : (t.stock > 0 ? '热卖中' : '缺货');

        html += `
            <tr>
                <td class="time-cell">${timeStr}</td>
                <td><span class="badge ${statusClass}">${statusText}</span></td>
                <td>${t.stock}/${t.total_ticket}</td>
                <td>¥${t.price}</td>
                <td class="cast-cell">${castStr}</td>
            </tr>
        `;
    });

    html += '</tbody></table></div>';
    container.innerHTML = html;
}

// --- Co-Cast Logic ---

function addCastInput() {
    const container = document.getElementById('cocast-inputs');
    const div = document.createElement('div');
    div.className = 'input-row';
    div.innerHTML = '<input type="text" class="cast-name-input" placeholder="输入演员姓名">';
    container.appendChild(div);
}

async function doCoCastSearch() {
    const inputs = document.querySelectorAll('.cast-name-input');
    const names = Array.from(inputs).map(i => i.value.trim()).filter(v => v);

    if (names.length === 0) {
        alert("请至少输入一位演员姓名");
        return;
    }

    const container = document.getElementById('cast-results');
    container.innerHTML = 'Searching...';

    try {
        const res = await fetch(`/api/events/co-cast?casts=${names.join(',')}`);
        const data = await res.json();
        renderCoCastResults(data.results);
    } catch (e) {
        container.innerHTML = 'Error searching.';
    }
}

function renderCoCastResults(tickets) {
    const container = document.getElementById('cast-results');
    if (!tickets || tickets.length === 0) {
        container.innerHTML = '<div style="padding:20px">无同台场次</div>';
        return;
    }

    // Re-use detail table logic or simplified
    let html = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>剧目</th>
                    <th>时间</th>
                    <th>卡司</th>
                    <th>余票</th>
                </tr>
            </thead>
            <tbody>
    `;

    tickets.forEach(t => {
        const timeStr = new Date(t.session_time).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
        const castStr = t.cast.map(c => c.name).join(' ');
        html += `
            <tr>
                <td>${t.title}</td>
                <td class="time-cell">${timeStr}</td>
                <td class="cast-cell">${castStr}</td>
                <td>${t.stock}</td>
            </tr>
        `;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

// Helper: Global Search
async function doGlobalSearch() {
    const q = document.getElementById('global-search').value.trim();
    if (!q) return;

    // Switch to HLQ tab to show results? Or show in a modal?
    // Let's filter the HLQ list if loaded
    if (state.currentTab !== 'tab-hlq') {
        switchTab('tab-hlq');
    }

    // Assuming backend search
    const container = document.getElementById('hlq-list-container');
    container.innerHTML = 'Searching...';
    const res = await fetch(`/api/events/search?q=${q}`);
    const data = await res.json();

    // Convert search results (EventInfo) into table format
    // Search returns list of events with details tickets populated.
    // We just want listing.
    state.allEvents = data.results; // Override local list
    renderEventTable(state.allEvents);
}
