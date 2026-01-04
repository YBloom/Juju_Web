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
        stock: true
    },
    // Filter Settings
    filterCity: '',
    // Co-Cast Column Settings
    coCastCols: {
        index: true,
        others: true,
        location: true
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

function changeSort(field) {
    if (state.sortField === field) {
        state.sortAsc = !state.sortAsc;
    } else {
        state.sortField = field;
        state.sortAsc = true; // default asc for new field? usually desc for dates, but let's stick to true
    }
    applyFilters();
}

function sortEvents(events) {
    return events.sort((a, b) => {
        // Priority 1: Selected Sort Field
        let valA = a[state.sortField];
        let valB = b[state.sortField];

        // Special handling for stock (numeric)
        if (state.sortField === 'stock') {
            valA = a.total_stock || 0;
            valB = b.total_stock || 0;
            return state.sortAsc ? valA - valB : valB - valA;
        }

        // Special handling for city (custom score)
        if (state.sortField === 'city') {
            const scoreA = getCityScore(valA);
            const scoreB = getCityScore(valB);
            if (scoreA !== scoreB) {
                // Always adhere to priority order if different groups? 
                // User wants sorting capability. If they click city, they probably want grouping.
                // Let's keep the custom group logic as primary for 'city' sort.
                // If asc, standard group order. If desc, reverse?
                return state.sortAsc ? scoreA - scoreB : scoreB - scoreA;
            }
        }

        // Standard string comparison for Title/City(same group)
        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();

        if (valA < valB) return state.sortAsc ? -1 : 1;
        if (valA > valB) return state.sortAsc ? 1 : -1;

        // Fallback: Date Descending
        return new Date(b.update_time) - new Date(a.update_time);
    });
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
        renderCityFilterOptions();
        applyFilters();
    } catch (e) {
        container.innerHTML = `<div style="color:red;padding:20px;text-align:center">加载失败: ${e.message}</div>`;
    }
}

function renderCityFilterOptions() {
    // Extract unique cities
    const cities = [...new Set(state.allEvents.map(e => e.city).filter(c => c))].sort();

    // Check if UI exists
    const toolbar = document.querySelector('.toolbar');
    let select = document.getElementById('city-filter');
    if (!select) {
        const div = document.createElement('div');
        div.style.marginRight = '15px';
        div.innerHTML = `
            <select id="city-filter" onchange="applyFilters()" style="padding: 5px 10px; border-radius: 8px; border: 1px solid #ddd;">
                <option value="">所有城市</option>
            </select>
        `;
        // Insert before column config or at end
        const colConfig = toolbar.querySelector('.column-config');
        if (colConfig) {
            toolbar.insertBefore(div, colConfig);
        } else {
            toolbar.appendChild(div);
        }
        select = document.getElementById('city-filter');
    }

    // Populate
    // Keep "All" option
    select.innerHTML = '<option value="">所有城市</option>';
    cities.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.innerText = c;
        select.appendChild(opt);
    });
}

function applyFilters() {
    let filtered = state.allEvents;

    // Text search filter (if search box exists)
    const searchBox = document.getElementById('global-search');
    if (searchBox) {
        const q = searchBox.value.trim().toLowerCase();
        if (q) {
            filtered = filtered.filter(e =>
                (e.title && e.title.toLowerCase().includes(q)) ||
                (e.location && e.location.toLowerCase().includes(q)) ||
                (e.city && e.city.includes(q))
            );
        }
    }

    // City Filter
    const cityVal = document.getElementById('city-filter') ? document.getElementById('city-filter').value : '';
    if (cityVal) {
        filtered = filtered.filter(e => e.city === cityVal);
    }

    // Sort
    state.displayEvents = sortEvents(filtered);
    renderEventTable(state.displayEvents);
}

// Hook global search input to live filter (if exists)
const globalSearchEl = document.getElementById('global-search');
if (globalSearchEl) {
    globalSearchEl.addEventListener('input', applyFilters);
}

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
                    ${col.city ? '<th width="80" onclick="changeSort(\'city\')" class="sortable">城市</th>' : ''}
                    ${col.update ? '<th width="180">排期</th>' : ''}
                    ${col.title ? '<th onclick="changeSort(\'title\')" class="sortable">剧目</th>' : ''}
                    ${col.stock ? '<th width="100" onclick="changeSort(\'stock\')" class="sortable">总余票</th>' : ''}
                    ${col.price ? '<th width="120">票价范围</th>' : ''}
                    ${col.location ? '<th>场馆</th>' : ''}
                </tr>
            </thead>
            <tbody>
    `;

    events.forEach(e => {
        const scheduleRange = e.schedule_range || '-';
        // HTML construction
        html += `<tr onclick="loadEventDetail('${e.id}')">`;
        if (col.city) html += `<td class="city-cell" data-label="城市">${e.city}</td>`;
        if (col.update) html += `<td class="time-cell" data-label="排期">${scheduleRange}</td>`;
        if (col.title) html += `<td class="title-cell" data-label="剧目">${e.title}</td>`;
        if (col.stock) html += `<td data-label="总余票">${e.total_stock}</td>`;
        if (col.price) html += `<td data-label="票价范围">${e.price_range}</td>`;
        if (col.location) html += `<td data-label="场馆">${e.location || '-'}</td>`;
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

    const allTickets = event.tickets.sort((a, b) => new Date(a.session_time) - new Date(b.session_time));

    // 检查是否有任何场次有卡司信息
    const hasCast = allTickets.some(t => t.cast && t.cast.length > 0);

    // 检查票价数据，提取多个年份
    const years = [...new Set(allTickets.map(t => {
        if (t.session_time) {
            return new Date(t.session_time).getFullYear();
        }
        return null;
    }).filter(y => y !== null))];
    const showYear = years.length > 1; // 只有多个年份时才显示年份

    // 提取所有唯一价格
    const allPrices = [...new Set(allTickets.map(t => t.price))].sort((a, b) => a - b);

    // 渲染筛选控件和表格
    let html = `
        <div style="background:#fcfcfc; padding:20px; border-radius:10px; border:1px solid #eee; margin-bottom:20px">
            <h2 style="margin-top:0; color:var(--primary-color)">${event.title}</h2>
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style="display:flex; gap:20px; color:#666">
                    <span>📍 ${event.location || '未知场馆'}</span>
                    <span>📅 排期: ${event.schedule_range || '待定'}</span>
                </div>
                <div style="font-size:0.85em; color:var(--text-secondary); opacity:0.8;">
                    💡 点击场次可跳转呼啦圈购票
                </div>
            </div>
        </div>
        
        <!-- 筛选控件 -->
        <div style="background:#f8f9fa; padding:15px 20px; border-radius:8px; margin-bottom:15px; border:1px solid #e0e0e0;">
            <div style="display:flex; flex-wrap:wrap; gap:20px; align-items:center;">
                <!-- 只看有票 -->
                <label style="display:flex; align-items:center; gap:6px; cursor:pointer; font-size:0.9em;">
                    <input type="checkbox" id="filter-available" onchange="applyDetailFilters('${event.id}')">
                    <span>只看有票</span>
                </label>
                
                <!-- 价位筛选 -->
                <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
                    <span style="font-size:0.9em; font-weight:600; color:#666;">价位：</span>
                    ${allPrices.map(price => `
                        <label style="display:flex; align-items:center; gap:4px; cursor:pointer; font-size:0.85em;">
                            <input type="checkbox" class="filter-price" value="${price}" checked onchange="applyDetailFilters('${event.id}')">
                            <span>¥${price}</span>
                        </label>
                    `).join('')}
                </div>
                
                ${hasCast ? `
                <!-- 演员搜索 -->
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:0.9em; font-weight:600; color:#666;">演员：</span>
                    <input 
                        type="text" 
                        id="filter-cast" 
                        placeholder="输入演员姓名筛选" 
                        style="padding:6px 12px; border:1px solid #ddd; border-radius:6px; font-size:0.85em; width:150px;"
                        oninput="applyDetailFilters('${event.id}')"
                    >
                </div>
                ` : ''}
            </div>
        </div>
        
        <div id="detail-table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>演出时间</th>
                        <th width="80">库存</th>
                        ${hasCast ? '<th>卡司</th>' : ''}
                        <th width="150">价格</th>
                    </tr>
                </thead>
                <tbody id="detail-table-body">
                </tbody>
            </table>
        </div>
    `;

    container.innerHTML = html;

    // 保存数据到全局，供筛选使用
    window.currentDetailEvent = event;
    window.currentDetailTickets = allTickets;
    window.currentDetailShowYear = showYear;
    window.currentDetailHasCast = hasCast;

    // 初始渲染所有票
    renderDetailTableRows(allTickets, showYear, hasCast, event.id);
}

// 渲染详情页表格行
function renderDetailTableRows(tickets, showYear, hasCast, eventId) {
    const tbody = document.getElementById('detail-table-body');
    if (!tbody) return;

    let html = '';

    tickets.forEach(t => {
        // 格式化时间：根据是否显示年份决定格式
        let timeStr = '待定';
        if (t.session_time) {
            const date = new Date(t.session_time);
            const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const weekday = weekdays[date.getDay()];
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');

            if (showYear) {
                timeStr = `${year}年${month}月${day}日 周${weekday} ${hours}:${minutes}`;
            } else {
                timeStr = `${month}月${day}日 周${weekday} ${hours}:${minutes}`;
            }
        }

        const castStr = t.cast && t.cast.length > 0 ? t.cast.map(c => c.name).join(' | ') : '';
        const stockVal = t.stock !== undefined ? t.stock : 0;

        // 格式化价格：显示完整的呼啦圈价格格式
        let priceStr = '';
        if (t.price_label && t.price_label !== `¥${t.price}`) {
            priceStr = t.price_label;
        } else if (t.original_price && t.original_price !== t.price) {
            priceStr = `${t.price}（原价${t.original_price}）`;
        } else {
            priceStr = `¥${t.price}`;
        }

        // 判断是否售罄
        const isSoldOut = stockVal === 0 || t.status === 'sold_out';
        const rowClass = isSoldOut ? 'sold-out' : '';

        // 生成sessionId用于定位（使用时间作为唯一标识）
        const sessionId = t.session_id || (t.session_time ? new Date(t.session_time).getTime() : '');

        html += `
            <tr class="${rowClass}" 
                data-session-id="${sessionId}"
                onclick="window.open('https://clubz.cloudsation.com/event/${eventId}.html', '_blank')" 
                style="cursor:pointer">
                <td class="time-cell" data-label="演出时间">${timeStr}</td>
                <td data-label="库存">${t.stock}/${t.total_ticket}</td>
                ${hasCast ? `<td class="cast-cell" data-label="卡司">${castStr}</td>` : ''}
                <td data-label="价格">${priceStr}</td>
            </tr>
        `;
    });

    tbody.innerHTML = html || '<tr><td colspan="4" style="text-align:center;padding:40px;color:#999;">没有符合条件的场次</td></tr>';
}

// 应用详情页筛选
function applyDetailFilters(eventId) {
    const allTickets = window.currentDetailTickets;
    const showYear = window.currentDetailShowYear;
    const hasCast = window.currentDetailHasCast;

    if (!allTickets) return;

    // 获取筛选条件
    const onlyAvailable = document.getElementById('filter-available')?.checked || false;
    const selectedPrices = Array.from(document.querySelectorAll('.filter-price:checked')).map(cb => parseFloat(cb.value));
    const castSearch = document.getElementById('filter-cast')?.value.trim().toLowerCase() || '';

    // 应用筛选
    let filtered = allTickets.filter(t => {
        // 只看有票
        if (onlyAvailable && (t.stock === 0 || t.status === 'sold_out')) {
            return false;
        }

        // 价位筛选
        if (selectedPrices.length > 0 && !selectedPrices.includes(t.price)) {
            return false;
        }

        // 演员搜索
        if (castSearch && hasCast) {
            const castNames = t.cast ? t.cast.map(c => c.name.toLowerCase()).join(' ') : '';
            if (!castNames.includes(castSearch)) {
                return false;
            }
        }

        return true;
    });

    renderDetailTableRows(filtered, showYear, hasCast, eventId);
}

// --- Co-Cast (Updated) ---

// Inject UI elements on load
document.addEventListener('DOMContentLoaded', () => {
    const btnContainer = document.querySelector('#tab-cocast button[onclick="doCoCastSearch()"]').parentNode;

    // 1. Student Toggle
    if (btnContainer && !document.getElementById('student-only-toggle')) {
        const toggleLabel = document.createElement('label');
        toggleLabel.style.marginLeft = '15px';
        toggleLabel.style.fontSize = '0.9em';
        toggleLabel.style.cursor = 'pointer';
        toggleLabel.innerHTML = '<input type="checkbox" id="student-only-toggle"> 只看学生票 (Hulaquan)';
        btnContainer.appendChild(toggleLabel);
    }

    // 2. Date Pickers
    const inputsContainer = document.getElementById('cocast-inputs');
    if (inputsContainer && !document.getElementById('cocast-date-container')) {
        const dateDiv = document.createElement('div');
        dateDiv.id = 'cocast-date-container';
        dateDiv.style.marginTop = '10px';
        dateDiv.style.padding = '10px';
        dateDiv.style.background = '#f9f9f9';
        dateDiv.style.borderRadius = '4px';
        dateDiv.style.display = 'flex';
        dateDiv.style.gap = '15px';
        dateDiv.style.alignItems = 'center';
        dateDiv.innerHTML = `
            <span style="font-size:0.9em;font-weight:bold;">📅 日期范围:</span>
            <input type="date" id="cocast-start-date" style="padding:4px;" title="开始日期">
            <span>至</span>
            <input type="date" id="cocast-end-date" style="padding:4px;" title="结束日期">
            <span style="font-size:0.8em;color:#666;">(默认查询一年)</span>
        `;
        inputsContainer.parentNode.insertBefore(dateDiv, inputsContainer.nextSibling);

        // Set constraints and defaults
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');
        const todayStr = `${yyyy}-${mm}-${dd}`;

        const nextYear = new Date(today);
        nextYear.setFullYear(today.getFullYear() + 1);
        const nextYearStr = nextYear.toISOString().split('T')[0];

        const maxDate = new Date(today);
        maxDate.setFullYear(today.getFullYear() + 2);
        const maxDateStr = maxDate.toISOString().split('T')[0];

        const minDateStr = "2021-01-01";

        const startInput = document.getElementById('cocast-start-date');
        const endInput = document.getElementById('cocast-end-date');

        startInput.value = todayStr;
        startInput.min = minDateStr;
        startInput.max = maxDateStr;

        endInput.value = nextYearStr;
        endInput.min = minDateStr;
        endInput.max = maxDateStr;
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

    // Date Logic
    const startInput = document.getElementById('cocast-start-date');
    const endInput = document.getElementById('cocast-end-date');

    const startDate = startInput ? startInput.value : "";
    const endDate = endInput ? endInput.value : "";

    // Validation
    const minDateStr = "2021-01-01";
    // Check ranges if needed, but HTML min/max attributes handle basic UI constraints.
    // Let's do a quick sane check
    if (startDate < minDateStr) {
        alert("开始日期不能早于 2023-01-01");
        return;
    }
    if (endDate < startDate) {
        alert("结束日期不能早于开始日期");
        return;
    }

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
            body: JSON.stringify({
                casts: names.join(','),
                only_student: onlyStudent,
                start_date: startDate,
                end_date: endDate
            })
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
    const col = state.coCastCols || { index: true, others: true, location: true };
    state.lastCoCastResults = results;
    state.lastCoCastSource = source;

    // Extract year properly from _raw_time
    const resultsWithYear = results.map(r => {
        let year = r.year;
        if (!year || isNaN(year)) {
            if (r._raw_time) {
                year = new Date(r._raw_time).getFullYear();
            }
            if (!year || isNaN(year)) {
                year = new Date().getFullYear();
            }
        }
        return { ...r, year };
    });

    const years = [...new Set(resultsWithYear.map(r => r.year))].filter(y => !isNaN(y)).sort((a, b) => b - a);
    const selectedYear = state.coCastYearFilter || '';
    const sortAsc = state.coCastDateSort !== false;
    let filtered = selectedYear ? resultsWithYear.filter(r => r.year == selectedYear) : resultsWithYear;
    filtered.sort((a, b) => {
        const timeA = a._raw_time || a.date;
        const timeB = b._raw_time || b.date;
        const diff = new Date(timeA) - new Date(timeB);
        return sortAsc ? diff : -diff;
    });

    let html = `
        <div style="margin-bottom:15px;padding:10px;background:#f0f7ff;border-radius:8px;border-left:4px solid var(--primary-color)">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
                <div>
                    <div style="font-size:1.1em;font-weight:600;color:var(--primary-color);margin-bottom:5px">🎭 查询到 ${results.length} 场同台演出</div>
                    <div style="font-size:0.85em;color:#666">数据来源: ${isSaoju ? '扫剧网' : '呼啦圈'}</div>
                </div>
                <div style="display:flex;gap:10px;align-items:center;font-size:0.9em;flex-wrap:wrap">
                    <label style="cursor:pointer"><input type="checkbox" ${col.index ? 'checked' : ''} onchange="state.coCastCols.index = this.checked; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource)"> 序号</label>
                    <label style="cursor:pointer"><input type="checkbox" ${col.others ? 'checked' : ''} onchange="state.coCastCols.others = this.checked; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource)"> 其他卡司</label>
                    <label style="cursor:pointer"><input type="checkbox" ${col.location ? 'checked' : ''} onchange="state.coCastCols.location = this.checked; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource)"> 剧场</label>
                    <span>|</span>
                    <select onchange="state.coCastYearFilter = this.value; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource)" style="padding:3px 8px;border-radius:4px">
                        <option value="">全部年份</option>
                        ${years.map(y => `<option value="${y}" ${selectedYear == y ? 'selected' : ''}>${y}年</option>`).join('')}
                    </select>
                    <button onclick="state.coCastDateSort = !state.coCastDateSort; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource)" 
                            style="padding:3px 10px;border-radius:4px;border:1px solid #ddd;background:white;cursor:pointer">
                        日期 ${sortAsc ? '↓' : '↑'}
                    </button>
                </div>
            </div>
        </div>
        <table class="data-table">
            <thead>
                <tr>
                    ${col.index ? '<th width="50">#</th>' : ''}
                    <th width="200">日期/时间</th>
                    <th width="80">城市</th>
                    <th>剧目</th>
                    <th width="120">角色</th>
                    ${col.others ? '<th>其他卡司</th>' : ''}
                    ${col.location ? '<th>剧场</th>' : ''}
                </tr>
            </thead>
            <tbody>
    `;

    // 判断是否只有一个年份
    const uniqueYears = [...new Set(filtered.map(r => r.year))].filter(y => !isNaN(y));
    const showYearInTable = uniqueYears.length > 1;

    let lastYear = null, lastDate = null;
    filtered.forEach((r, idx) => {
        const currentYear = r.year;
        const parts = r.date ? r.date.trim().split(/\s+/) : [];
        const datePart = parts[0] || '';
        const timePart = parts[1] || '';

        let yearShow = true;
        let dateShow = true;

        if (currentYear === lastYear) {
            yearShow = false;
            if (datePart === lastDate) {
                dateShow = false;
            }
        }

        // 如果只有一个年份，完全不显示年份
        if (!showYearInTable) {
            yearShow = false;
        }

        const yearHTML = showYearInTable ? `<span class="dt-year" style="${yearShow ? '' : 'visibility:hidden'}">${currentYear}年</span>` : '';
        const dateHTML = `<span class="dt-date" style="${dateShow ? '' : 'visibility:hidden'}">${datePart}</span>`;
        const timeHTML = `<span class="dt-time">${timePart}</span>`;

        const dateDisplay = `<div class="dt-container">${yearHTML}${dateHTML}${timeHTML}</div>`;

        lastYear = currentYear;
        lastDate = datePart;
        const othersStr = r.others && r.others.length > 0 ? r.others.join(', ') : '-';
        html += `
            <tr>
                ${col.index ? `<td data-label="#">${idx + 1}</td>` : ''}
                <td class="time-cell" data-label="日期/时间">${dateDisplay}</td>
                <td class="city-cell" data-label="城市">${r.city || '-'}</td>
                <td class="title-cell" data-label="剧目">${r.title}</td>
                <td data-label="角色">${r.role || '-'}</td>
                ${col.others ? `<td class="cast-cell" data-label="其他卡司">${othersStr}</td>` : ''}
                ${col.location ? `<td data-label="剧场">${r.location || '-'}</td>` : ''}
            </tr>
        `;
    });
    container.innerHTML = html + '</tbody></table>';
}

// Add column filtering functionality
document.querySelectorAll('.cocast-table th[data-column]').forEach(header => {
    header.style.cursor = 'pointer';
    header.style.position = 'relative';
    header.innerHTML += '<span class="filter-icon" style="margin-left: 5px; opacity: 0.5;">▼</span>'; // Add a filter icon

    header.addEventListener('click', (e) => {
        const column = header.dataset.column;
        const table = header.closest('table');
        const columnIndex = Array.from(header.parentNode.children).indexOf(header);
        const rows = Array.from(table.querySelectorAll('tbody tr'));

        // Create or toggle filter dropdown
        let filterDropdown = header.querySelector('.filter-dropdown');
        if (!filterDropdown) {
            filterDropdown = document.createElement('div');
            filterDropdown.className = 'filter-dropdown';
            filterDropdown.style.position = 'absolute';
            filterDropdown.style.backgroundColor = '#fff';
            filterDropdown.style.border = '1px solid #ddd';
            filterDropdown.style.padding = '10px';
            filterDropdown.style.zIndex = '100';
            filterDropdown.style.maxHeight = '200px';
            filterDropdown.style.overflowY = 'auto';
            filterDropdown.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
            filterDropdown.style.left = '0';
            filterDropdown.style.top = '100%';
            header.appendChild(filterDropdown);
        }
        filterDropdown.style.display = filterDropdown.style.display === 'block' ? 'none' : 'block';

        if (filterDropdown.style.display === 'block' && filterDropdown.children.length === 0) {
            const uniqueValues = new Set();
            rows.forEach(row => {
                const cellText = row.children[columnIndex].textContent.trim();
                if (cellText) uniqueValues.add(cellText);
            });

            const sortedValues = Array.from(uniqueValues).sort();

            // "Select All" option
            const selectAllDiv = document.createElement('div');
            selectAllDiv.innerHTML = `<label><input type="checkbox" class="filter-checkbox" value="all" checked> (全选)</label>`;
            filterDropdown.appendChild(selectAllDiv);

            sortedValues.forEach(value => {
                const div = document.createElement('div');
                div.innerHTML = `<label><input type="checkbox" class="filter-checkbox" value="${value}" checked> ${value}</label>`;
                filterDropdown.appendChild(div);
            });

            filterDropdown.querySelectorAll('.filter-checkbox').forEach(checkbox => {
                checkbox.addEventListener('change', (event) => {
                    if (event.target.value === 'all') {
                        const isChecked = event.target.checked;
                        filterDropdown.querySelectorAll('.filter-checkbox').forEach(cb => {
                            cb.checked = isChecked;
                        });
                    } else {
                        // If any specific item is unchecked, uncheck "Select All"
                        if (!event.target.checked) {
                            filterDropdown.querySelector('.filter-checkbox[value="all"]').checked = false;
                        } else {
                            // If all specific items are checked, check "Select All"
                            const allChecked = Array.from(filterDropdown.querySelectorAll('.filter-checkbox:not([value="all"])')).every(cb => cb.checked);
                            if (allChecked) {
                                filterDropdown.querySelector('.filter-checkbox[value="all"]').checked = true;
                            }
                        }
                    }
                    applyColumnFilter(table, columnIndex, filterDropdown);
                });
            });
        }

        // Close other dropdowns
        document.querySelectorAll('.filter-dropdown').forEach(dd => {
            if (dd !== filterDropdown) {
                dd.style.display = 'none';
            }
        });
        e.stopPropagation(); // Prevent document click from closing immediately
    });
});

// Close filter dropdowns when clicking outside
document.addEventListener('click', (e) => {
    document.querySelectorAll('.filter-dropdown').forEach(dd => {
        if (!dd.contains(e.target) && !dd.parentNode.contains(e.target)) {
            dd.style.display = 'none';
        }
    });
});


function applyColumnFilter(table, columnIndex, filterDropdown) {
    const selectedValues = Array.from(filterDropdown.querySelectorAll('.filter-checkbox:checked'))
        .filter(cb => cb.value !== 'all')
        .map(cb => cb.value);
    const rows = Array.from(table.querySelectorAll('tbody tr'));

    rows.forEach(row => {
        const cellText = row.children[columnIndex].textContent.trim();
        if (selectedValues.length === 0 || selectedValues.includes(cellText)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}


// Date search function
async function doDateSearch() {
    const dateInput = document.getElementById('date-input');
    const resultsContainer = document.getElementById('date-results');

    const selectedDate = dateInput.value;

    if (!selectedDate) {
        resultsContainer.innerHTML = '<div style="padding:40px;text-align:center;color:#999">请选择日期</div>';
        return;
    }

    resultsContainer.innerHTML = '<div style="padding:40px;text-align:center">正在查询中...</div>';

    try {
        const res = await fetch(`/api/events/date?date=${selectedDate}`);
        const data = await res.json();

        if (data.error) {
            resultsContainer.innerHTML = `<div style="color:red;padding:20px;text-align:center">❌ ${data.error}</div>`;
            return;
        }

        renderDateResults(data.results, selectedDate);
    } catch (e) {
        resultsContainer.innerHTML = `<div style="color:red;padding:20px;text-align:center">❌ 查询失败: ${e.message}</div>`;
    }
}

function renderDateResults(tickets, date) {
    const container = document.getElementById('date-results');

    if (!tickets || tickets.length === 0) {
        container.innerHTML = `
            <div style="padding:40px;text-align:center;color:#999">
                📅 ${date}<br><br>
                😴 该日期暂无学生票演出安排
            </div>
        `;
        return;
    }

    // 排序
    const allTickets = tickets.sort((a, b) => new Date(a.session_time) - new Date(b.session_time));

    // 提取唯一城市
    const cities = [...new Set(allTickets.map(t => t.city).filter(c => c))].sort();

    let html = `
        <div style="margin-bottom:15px;padding:10px;background:#f0f7ff;border-radius:8px;border-left:4px solid var(--primary-color)">
            <div style="font-size:1.1em;font-weight:600;color:var(--primary-color);margin-bottom:5px">
                📅 ${date} - 查询到 ${tickets.length} 个场次
            </div>
        </div>
        
        <!-- 筛选控件 -->
        <div style="background:#f8f9fa; padding:15px 20px; border-radius:8px; margin-bottom:15px; border:1px solid #e0e0e0;">
            <div style="display:flex; flex-wrap:wrap; gap:20px; align-items:center;">
                <!-- 只看有票 -->
                <label style="display:flex; align-items:center; gap:6px; cursor:pointer; font-size:0.9em;">
                    <input type="checkbox" id="date-filter-available" onchange="applyDateFilters('${date}')">
                    <span>只看有票</span>
                </label>
                
                <!-- 城市筛选 -->
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:0.9em; font-weight:600; color:#666;">城市：</span>
                    <select id="date-filter-city" onchange="applyDateFilters('${date}')" 
                            style="padding:6px 12px; border:1px solid #ddd; border-radius:6px; font-size:0.85em;">
                        <option value="">全部</option>
                        ${cities.map(city => `<option value="${city}">${city}</option>`).join('')}
                    </select>
                </div>
                
                <!-- 剧目/卡司搜索 -->
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:0.9em; font-weight:600; color:#666;">搜索：</span>
                    <input 
                        type="text" 
                        id="date-filter-search" 
                        placeholder="剧目或演员名" 
                        style="padding:6px 12px; border:1px solid #ddd; border-radius:6px; font-size:0.85em; width:150px;"
                        oninput="applyDateFilters('${date}')"
                    >
                </div>
            </div>
        </div>
        
        <div id="date-table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th width="60">时间</th>
                        <th width="60">城市</th>
                        <th>剧目</th>
                        <th width="80">余票</th>
                        <th width="100">价格</th>
                        <th width="180">卡司</th>
                    </tr>
                </thead>
                <tbody id="date-table-body">
                </tbody>
            </table>
        </div>
    `;

    container.innerHTML = html;

    // 保存数据到全局
    window.currentDateTickets = allTickets;
    window.currentDate = date;

    // 初始渲染
    renderDateTableRows(allTickets);
}

// 渲染日期查询表格行
function renderDateTableRows(tickets) {
    const tbody = document.getElementById('date-table-body');
    if (!tbody) return;

    let html = '';

    tickets.forEach(t => {
        // 格式化时间，只显示时分
        let timeStr = '待定';
        if (t.session_time) {
            const date = new Date(t.session_time);
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            timeStr = `${hours}:${minutes}`;
        }

        // 提取剧名（书名号内部）
        let showTitle = t.title;
        const titleMatch = t.title.match(/[《【](.*?)[》】]/);
        if (titleMatch && titleMatch[1]) {
            showTitle = titleMatch[1];
        }

        const castStr = t.cast && t.cast.length > 0 ? t.cast.map(c => c.name).join(' | ') : '-';
        const stockVal = t.stock !== undefined ? t.stock : 0;

        // 判断是否售罄
        const isSoldOut = stockVal === 0 || t.status === 'sold_out';
        const rowClass = isSoldOut ? 'sold-out' : '';

        // 构建跳转URL（包含场次ID用于滚动和高亮）
        const detailUrl = `#detail-${t.event_id}`;
        const sessionId = t.session_id || t.id || '';

        html += `
            <tr class="${rowClass}" data-session-id="${sessionId}">
                <td class="time-cell" data-label="时间">${timeStr}</td>
                <td class="city-cell" data-label="城市">${t.city || '-'}</td>
                <td class="title-cell" data-label="剧目" 
                    style="cursor:pointer; color:var(--primary-color); font-weight:600;"
                    onclick="jumpToDetail('${t.event_id}', '${sessionId}')">
                    ${showTitle}
                </td>
                <td data-label="余票">${t.stock}/${t.total_ticket}</td>
                <td data-label="价格">¥${t.price}</td>
                <td class="cast-cell" data-label="卡司">${castStr}</td>
            </tr>
        `;
    });

    tbody.innerHTML = html || '<tr><td colspan="6" style="text-align:center;padding:40px;color:#999;">没有符合条件的场次</td></tr>';
}

// 应用日期查询筛选
function applyDateFilters(date) {
    const allTickets = window.currentDateTickets;
    if (!allTickets) return;

    // 获取筛选条件
    const onlyAvailable = document.getElementById('date-filter-available')?.checked || false;
    const selectedCity = document.getElementById('date-filter-city')?.value || '';
    const searchText = document.getElementById('date-filter-search')?.value.trim().toLowerCase() || '';

    // 应用筛选
    let filtered = allTickets.filter(t => {
        // 只看有票
        if (onlyAvailable && (t.stock === 0 || t.status === 'sold_out')) {
            return false;
        }

        // 城市筛选
        if (selectedCity && t.city !== selectedCity) {
            return false;
        }

        // 剧目/卡司搜索
        if (searchText) {
            const titleLower = t.title ? t.title.toLowerCase() : '';
            const castNames = t.cast ? t.cast.map(c => c.name.toLowerCase()).join(' ') : '';
            if (!titleLower.includes(searchText) && !castNames.includes(searchText)) {
                return false;
            }
        }

        return true;
    });

    renderDateTableRows(filtered);
}

// 跳转到详情页并高亮场次
function jumpToDetail(eventId, sessionId) {
    // 加载详情页
    loadEventDetail(eventId);

    // 等待详情页渲染完成后滚动并高亮
    setTimeout(() => {
        highlightSession(sessionId);
    }, 500);
}

// 高亮指定场次
function highlightSession(sessionId) {
    if (!sessionId) return;

    // 查找对应的行
    const rows = document.querySelectorAll('#detail-table-body tr');
    let targetRow = null;

    // 尝试通过session_time匹配（需要后端支持）
    // 这里简化处理，可以通过其他方式定位
    rows.forEach((row, index) => {
        // 如果能找到包含sessionId的行
        if (row.getAttribute('data-session-id') === sessionId) {
            targetRow = row;
        }
    });

    if (targetRow) {
        // 滚动到目标行
        targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // 添加高亮动画
        targetRow.style.transition = 'background-color 0.3s ease';
        targetRow.style.backgroundColor = '#fff3cd';

        // 2秒后恢复
        setTimeout(() => {
            targetRow.style.backgroundColor = '';
        }, 2000);
    }
}

// Global search function mainly for header call, mapped to live filter now
async function doGlobalSearch() {
    // Just trigger filter
    applyFilters();
}
