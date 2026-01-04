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
            { id: 'update', label: '排期' },
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
                    ${col.update ? '<th width="180">排期</th>' : ''}
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
        const scheduleRange = e.schedule_range || '-';
        // HTML construction
        html += `<tr onclick="loadEventDetail('${e.id}')">`;
        if (col.city) html += `<td class="city-cell">${e.city}</td>`;
        if (col.update) html += `<td class="time-cell">${scheduleRange}</td>`;
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
                <span>📅 排期: ${event.schedule_range || '待定'}</span>
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

// --- Co-Cast (Updated) ---

// Inject toggle checkbox on load (simple hack since we don't edit HTML directly)
document.addEventListener('DOMContentLoaded', () => {
    const btnContainer = document.querySelector('#tab-cocast button[onclick="doCoCastSearch()"]').parentNode;
    if (btnContainer && !document.getElementById('student-only-toggle')) {
        const toggleLabel = document.createElement('label');
        toggleLabel.style.marginLeft = '15px';
        toggleLabel.style.fontSize = '0.9em';
        toggleLabel.style.cursor = 'pointer';
        toggleLabel.innerHTML = '<input type="checkbox" id="student-only-toggle"> 只看学生票 (Hulaquan)';
        btnContainer.appendChild(toggleLabel);
    }
});

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

    const onlyStudent = document.getElementById('student-only-toggle')?.checked || false;
    const container = document.getElementById('cast-results');

    // 初始化进度条 UI
    container.innerHTML = `
        <div style="padding: 20px; max-width: 600px; margin: 0 auto;">
            <div style="margin-bottom: 10px; display: flex; justify-content: space-between; font-weight: 500;">
                <span id="search-status-text">准备搜索...</span>
                <span id="search-progress-text">0%</span>
            </div>
            <div style="background: #eee; border-radius: 6px; height: 12px; overflow: hidden;">
                <div id="search-progress-bar" style="background: var(--primary-color); height: 100%; width: 0%; transition: width 0.3s ease;"></div>
            </div>
        </div>
    `;

    try {
        // 1. 启动任务
        const startRes = await fetch('/api/tasks/co-cast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ casts: names.join(','), only_student: onlyStudent })
        });

        if (!startRes.ok) throw new Error("启动搜索任务失败");
        const { task_id } = await startRes.json();

        // 2. 轮询状态
        const pollInterval = setInterval(async () => {
            try {
                const statusRes = await fetch(`/api/tasks/${task_id}`);
                if (!statusRes.ok) {
                    clearInterval(pollInterval);
                    container.innerHTML = `<div style='color:red;padding:20px;text-align:center'>查询状态出错</div>`;
                    return;
                }

                const job = await statusRes.json();

                // 更新 UI
                const pBar = document.getElementById('search-progress-bar');
                const pText = document.getElementById('search-progress-text');
                const sText = document.getElementById('search-status-text');

                if (pBar) pBar.style.width = `${job.progress}%`;
                if (pText) pText.innerText = `${job.progress}%`;
                if (sText) sText.innerText = job.message || "处理中...";

                if (job.status === 'completed') {
                    clearInterval(pollInterval);
                    // 稍微延迟一下让用看到100%
                    setTimeout(() => {
                        renderCoCastResults(job.result.results, job.result.source);
                    }, 500);
                } else if (job.status === 'failed') {
                    clearInterval(pollInterval);
                    container.innerHTML = `<div style='color:red;padding:20px;text-align:center'>❌ 查询失败: ${job.error || "未知错误"}</div>`;
                }
            } catch (pollErr) {
                console.error("Poll error:", pollErr);
            }
        }, 500);

    } catch (e) {
        container.innerHTML = `<div style='color:red;padding:20px;text-align:center'>❌ 发起查询失败: ${e.message}</div>`;
    }
}

function renderCoCastResults(results, source) {
    const container = document.getElementById('cast-results');
    if (!results || results.length === 0) {
        container.innerHTML = '<div style="padding:40px;text-align:center;color:#999">未找到同场演出</div>';
        return;
    }

    const isSaoju = source === 'saoju';
    // H: Hulaquan (Tickets), S: Saoju (Events)

    let html = `
        <div style="margin-bottom:15px;padding:10px;background:#f0f7ff;border-radius:8px;border-left:4px solid var(--primary-color)">
            <div style="font-size:1.1em;font-weight:600;color:var(--primary-color);margin-bottom:5px">
                🎭 查询到 ${results.length} 场同台演出
            </div>
            <div style="font-size:0.9em;color:#666">
                数据来源: ${isSaoju ? '扫剧网 (Saoju) - 排期&所有票务' : '呼啦圈 (Hulaquan) - 仅学生票'}
            </div>
        </div>
        <table class="data-table">
            <thead>
                <tr>
                    ${isSaoju ? '<th>日期/时间</th>' : '<th>时间</th>'}
                    <th>城市</th>
                    <th>剧目</th>
                    <th>同场卡司</th>
                    ${isSaoju ? '<th>剧场</th>' : '<th>余票</th>'}
                </tr>
            </thead>
            <tbody>
    `;

    results.forEach(item => {
        if (isSaoju) {
            // Saoju Item: { date, title, others, city, location, role }
            const othersStr = (item.others || []).join(' ');
            html += `
                <tr>
                    <td class="time-cell">${item.date}</td>
                    <td class="city-cell">${item.city}</td>
                    <td class="title-cell">${item.title}</td>
                    <td class="cast-cell">${othersStr}</td>
                    <td>${item.location}</td>
                </tr>
            `;
        } else {
            // Hulaquan Ticket: { title, session_time, cast: [{name}], stock, city? }
            const timeStr = new Date(item.session_time).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
            const castStr = item.cast.map(c => c.name).join(' ');
            html += `
                <tr>
                   <td class="time-cell">${timeStr}</td>
                   <td class="city-cell">${item.city || '-'}</td>
                   <td class="title-cell">${item.title}</td>
                   <td class="cast-cell">${castStr}</td>
                   <td>${item.stock}</td>
                </tr>
            `;
        }
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

// Global search function mainly for header call, mapped to live filter now
async function doGlobalSearch() {
    // Just trigger filter
    applyFilters();
}
