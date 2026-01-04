// App State
const state = {
    allEvents: [],
    displayEvents: [], // Filtered/Sorted list
    currentTab: 'tab-hlq',
    // Sort Settings
    sortField: 'city',
    sortAsc: true,
    // Column Visibility (Load from Storage)
    visibleColumns: JSON.parse(localStorage.getItem('hlq_columns')) || {
        city: true,
        update: true,
        title: true,
        location: false, // Default hidden
        price: true,
        stock: true,
        action: true
    }
};

document.addEventListener('DOMContentLoaded', () => {
    initHlqTab();
    renderColumnToggles();
});

// --- Settings & Columns ---

function renderColumnToggles() {
    // Inject column settings UI into toolbar if not exists
    const toolbar = document.querySelector('.toolbar');
    if (!toolbar.querySelector('.column-config')) {
        const div = document.createElement('div');
        div.className = 'column-config';
        div.style.display = 'flex';
        div.style.gap = '10px';
        div.style.alignItems = 'center';

        // Define toggleable columns map
        const cols = [
            { id: 'city', label: '城市' },
            { id: 'update', label: '更新时间' },
            { id: 'title', label: '剧名' },
            { id: 'location', label: '场馆' },
            { id: 'stock', label: '余票' },
            { id: 'price', label: '票价' },
        ];

        let html = '<span style="font-size:0.9em;color:var(--text-secondary)">显示列: </span>';
        cols.forEach(c => {
            const checked = state.visibleColumns[c.id] ? 'checked' : '';
            html += `<label style="font-size:0.85em;cursor:pointer"><input type="checkbox" onchange="toggleColumn('${c.id}')" ${checked}> ${c.label}</label>`;
        });

        div.innerHTML = html;
        toolbar.appendChild(div);
    }
}

function toggleColumn(colId) {
    state.visibleColumns[colId] = !state.visibleColumns[colId];
    localStorage.setItem('hlq_columns', JSON.stringify(state.visibleColumns));
    renderEventTable(state.displayEvents);
}

function sortEvents(events) {
    // Custom City Order: Shanghai > Beijing > Guangzhou > Shenzhen > Others
    // const cityOrder = {'上海': 0, '北京': 1, '广州': 2, '深圳': 3}; 
    // Wait, user said "Shanghai first".

    return events.sort((a, b) => {
        // First sort by City Priority
        const cityA = getCityScore(a.city);
        const cityB = getCityScore(b.city);

        if (cityA !== cityB) {
            return cityA - cityB;
        }

        // Then by chosen sort field (if we had clickable headers, for now default secondary sort)
        // Default secondary sort: Update Time Descending
        return new Date(b.update_time) - new Date(a.update_time);
    });
}

function getCityScore(city) {
    if (!city || typeof city !== 'string') return 100;
    if (city.includes('上海')) return 0;
    if (city.includes('北京')) return 1;
    if (city.includes('广州')) return 2;
    if (city.includes('深圳')) return 3;
    if (city.includes('杭州')) return 4;
    return 100; // Others
}

// --- Data Logic ---

async function initHlqTab() {
    const container = document.getElementById('hlq-list-container');
    container.innerHTML = '<div style="padding:40px;text-align:center;color:#888">正在加载演出数据...</div>';

    try {
        const res = await fetch('/api/events/list');
        const data = await res.json();
        state.allEvents = data.results;

        // Initial Sort & Filter
        applyFilters();
    } catch (e) {
        container.innerHTML = `<div style="color:red;padding:20px;text-align:center">加载失败: ${e.message}</div>`;
    }
}

function applyFilters() {
    // Filter
    const q = document.getElementById('global-search').value.trim().toLowerCase();

    let filtered = state.allEvents;
    if (q) {
        filtered = filtered.filter(e =>
            (e.title && e.title.toLowerCase().includes(q)) ||
            (e.location && e.location.toLowerCase().includes(q)) ||
            (e.city && e.city.includes(q))
        );
    }

    // Sort
    state.displayEvents = sortEvents(filtered);
    renderEventTable(state.displayEvents);
}

// Hook global search input to live filter
document.getElementById('global-search').addEventListener('input', applyFilters);

function renderEventTable(events) {
    const container = document.getElementById('hlq-list-container');
    if (!events || events.length === 0) {
        container.innerHTML = '<div style="padding:50px;text-align:center;color:#aaa">暂无符合条件的演出</div>';
        return;
    }

    const col = state.visibleColumns;

    let html = `
        <table class="data-table">
            <thead>
                <tr>
                    ${col.city ? '<th width="80">城市</th>' : ''}
                    ${col.update ? '<th width="150">更新</th>' : ''}
                    ${col.title ? '<th>剧目</th>' : ''}
                    ${col.stock ? '<th width="100">总余票</th>' : ''}
                    ${col.price ? '<th width="120">票价范围</th>' : ''}
                    ${col.location ? '<th>场馆</th>' : ''}
                    ${col.action ? '<th width="100">操作</th>' : ''}
                </tr>
            </thead>
            <tbody>
    `;

    events.forEach(e => {
        const updateTime = e.update_time ? new Date(e.update_time).toLocaleDateString() : '-';
        // HTML construction
        html += `<tr onclick="loadEventDetail('${e.id}')">`;
        if (col.city) html += `<td class="city-cell">${e.city}</td>`;
        if (col.update) html += `<td class="time-cell">${updateTime}</td>`;
        if (col.title) html += `<td class="title-cell">${e.title}</td>`;
        if (col.stock) html += `<td>${e.total_stock}</td>`;
        if (col.price) html += `<td>${e.price_range}</td>`;
        if (col.location) html += `<td>${e.location || '-'}</td>`;
        if (col.action) html += `<td><button onclick="event.stopPropagation(); loadEventDetail('${e.id}')">详情</button></td>`;
        html += `</tr>`;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

// --- Detail & Other Tabs (Keep existing logic mostly, confirm variables) ---

function switchTab(tabId) {
    state.currentTab = tabId;

    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-target="${tabId}"]`).classList.add('active');

    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');

    document.getElementById('detail-view').classList.add('hidden');
    document.getElementById('tab-hlq').classList.remove('hidden');

    if (tabId === 'tab-hlq' && state.allEvents.length === 0) {
        initHlqTab();
    }
}

async function loadEventDetail(eventId) {
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById('detail-view').classList.remove('hidden');

    const container = document.getElementById('detail-content');
    container.innerHTML = '<div style="padding:40px;text-align:center">加载详情中...</div>';

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
    // Restore tab
    document.getElementById(state.currentTab).classList.add('active');
}

function renderDetailView(event) {
    const container = document.getElementById('detail-content');

    let html = `
        <div style="background:#fcfcfc; padding:20px; border-radius:10px; border:1px solid #eee; margin-bottom:20px">
            <h2 style="margin-top:0; color:var(--primary-color)">${event.title}</h2>
            <div style="display:flex; gap:20px; color:#666">
                <span>📍 ${event.location || '未知场馆'}</span>
                <span>📅 更新于: ${new Date(event.update_time).toLocaleString()}</span>
            </div>
        </div>
        <div>
            <table class="data-table">
                <thead>
                    <tr>
                        <th width="140">时间</th>
                        <th>状态</th>
                        <th>库存</th>
                        <th>价格</th>
                        <th>卡司</th>
                    </tr>
                </thead>
                <tbody>
    `;

    const tickets = event.tickets.sort((a, b) => new Date(a.session_time) - new Date(b.session_time));

    tickets.forEach(t => {
        const timeStr = t.session_time ? new Date(t.session_time).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '待定';
        const castStr = t.cast.map(c => c.name).join(' | ');
        const statusClass = t.stock > 0 ? 'active' : (t.status === 'pending' ? 'pending' : 'sold_out');
        const statusText = t.status === 'pending' ? '预售' : (t.stock > 0 ? '热卖' : '缺货');

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

// --- Co-Cast (Keep existing) ---
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
    container.innerHTML = '<div style="text-align:center;padding:20px">查询中...</div>';

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
        container.innerHTML = '<div style="padding:40px;text-align:center;color:#999">未找到同场演出</div>';
        return;
    }

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

// Global search function mainly for header call, mapped to live filter now
async function doGlobalSearch() {
    // Just trigger filter
    applyFilters();
}
