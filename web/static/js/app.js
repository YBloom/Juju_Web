// App State
// 快捷跳转同场查询
function searchInCoCast(castName) {
    router.navigate('/cocast');
    // 等待路由切换完成
    setTimeout(() => {
        const inputs = document.querySelectorAll('.cast-name-input');
        if (inputs.length > 0) {
            inputs[0].value = castName || '';
            // 清空后续输入框
            for (let i = 1; i < inputs.length; i++) inputs[i].value = '';
            doCoCastSearch();
        }
    }, 100);
}

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
    // 延迟初始化以确保 router 已就位
    initRouter();
    renderColumnToggles();
});

// --- Routing ---

function initRouter() {
    router.on('/', () => {
        showTabContent('tab-hlq');
        if (state.allEvents.length === 0) {
            initHlqTab();
        }
    });

    router.on('/detail/:id', (params) => {
        showDetailView(params.id);
    });

    router.on('/date', (params, query) => {
        showTabContent('tab-date');
        if (query.d) {
            const input = document.getElementById('date-input');
            if (input) {
                input.value = query.d;
                doDateSearch();
            }
        }
    });

    router.on('/cocast', () => {
        showTabContent('tab-cocast');
    });

    // 路由初始化在 router.js 中通过 DOMContentLoaded 处理
}

function showTabContent(tabId) {
    state.currentTab = tabId;

    // 更新导航按钮状态
    document.querySelectorAll('.nav-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.tab === tabId);
    });

    // 切换标签页内容
    document.querySelectorAll('.tab-content').forEach(c => {
        c.classList.toggle('active', c.id === tabId);
    });

    // 隐藏详情页，显示列表容器
    document.getElementById('detail-view').classList.add('hidden');
    // 确保主标签页容器可见（如果之前被详情页覆盖）
    document.querySelectorAll('.tab-content').forEach(c => {
        if (c.id === tabId) c.classList.remove('hidden');
    });

    // 初始化同场演员日期
    if (tabId === 'tab-cocast') {
        initCoCastDates();
    }
}

// 初始化同场演员日期范围（今天至一年后）
function initCoCastDates() {
    const startInput = document.getElementById('cocast-start-date');
    const endInput = document.getElementById('cocast-end-date');
    if (!startInput || !endInput) return;

    const now = new Date();
    const oneYearLater = new Date();
    oneYearLater.setFullYear(now.getFullYear() + 1);

    const formatDate = (date) => {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    };

    const todayStr = formatDate(now);
    const nextYearStr = formatDate(oneYearLater);

    // 始终确保限制生效
    startInput.min = "2023-01-01";
    endInput.min = "2023-01-01";
    endInput.max = nextYearStr;

    // 仅当为空时填充默认值
    if (!startInput.value) startInput.value = todayStr;
    if (!endInput.value) endInput.value = nextYearStr;
}

// 快捷设置同场演员日期范围
function setCoCastRange(type) {
    if (type === 'earliest') {
        const startInput = document.getElementById('cocast-start-date');
        if (startInput) startInput.value = "2023-01-01";
    }
}

async function showDetailView(eventId) {
    // 隐藏所有标签页，显示详情页
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    document.getElementById('detail-view').classList.remove('hidden');

    const container = document.getElementById('detail-content');
    container.innerHTML = '<div style="padding:40px;text-align:center">加载详情中...</div>';

    try {
        const res = await fetch(`/api/events/${eventId}`);
        const data = await res.json();
        if (data.results && data.results.length > 0) {
            renderDetailView(data.results[0]);
        } else {
            container.innerHTML = '<div style="padding:40px;text-align:center;color:#999">未找到演出信息</div>';
        }
    } catch (e) {
        container.innerHTML = '<div style="padding:40px;text-align:center;color:red">加载失败。</div>';
    }
}

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
    if (!events || events.length === 0) return events;

    // Calculate city frequency for the current set of events
    const cityCounts = {};
    events.forEach(e => {
        if (e.city) {
            cityCounts[e.city] = (cityCounts[e.city] || 0) + 1;
        }
    });

    return events.sort((a, b) => {
        // Priority 1: User-selected sort field if NOT default (city)
        if (state.sortField !== 'city') {
            let valA = a[state.sortField];
            let valB = b[state.sortField];

            if (state.sortField === 'stock') {
                valA = a.total_stock || 0;
                valB = b.total_stock || 0;
                return state.sortAsc ? valA - valB : valB - valA;
            }

            if (typeof valA === 'string') valA = valA.toLowerCase();
            if (typeof valB === 'string') valB = valB.toLowerCase();

            if (valA < valB) return state.sortAsc ? -1 : 1;
            if (valA > valB) return state.sortAsc ? 1 : -1;
        }

        // Priority 2: City Frequency (Count) - User request: cities with more shows first
        const countA = cityCounts[a.city] || 0;
        const countB = cityCounts[b.city] || 0;
        if (countA !== countB) {
            return countB - countA; // More shows first
        }

        // Priority 3: City name (Grouping cities together)
        if (a.city !== b.city) {
            return a.city.localeCompare(b.city, 'zh');
        }

        // Priority 4: Schedule start date - User request: latest start date first (Descending)
        // Extract start date from "2025-12-19 至 2026-01-04"
        const getStartDate = (range) => {
            if (!range) return new Date(0);
            const part = range.split('至')[0].trim();
            const d = new Date(part);
            return isNaN(d.getTime()) ? new Date(0) : d;
        };

        const dateA = getStartDate(a.schedule_range);
        const dateB = getStartDate(b.schedule_range);
        return dateB - dateA; // Latest date first
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
    <div class="data-table-container">
        <table class="data-table">
            <thead>
                <tr>
                    ${col.city ? '<th width="60" onclick="changeSort(\'city\')" class="sortable">城市</th>' : ''}
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
        html += `<tr onclick="router.navigate('/detail/${e.id}')">`;
        if (col.city) html += `<td class="city-cell" data-label="城市">${e.city}</td>`;
        if (col.update) html += `<td class="time-cell" data-label="排期">${scheduleRange}</td>`;
        if (col.title) html += `<td class="title-cell" data-label="剧目">${e.title}</td>`;
        if (col.stock) html += `<td data-label="总余票">${e.total_stock}</td>`;
        if (col.price) html += `<td data-label="票价范围">${e.price_range}</td>`;
        if (col.location) html += `<td data-label="场馆">${e.location || '-'}</td>`;
        html += `</tr>`;
    });

    html += '</tbody></table></div>';
    container.innerHTML = html;
}

// --- Detail & Other Tabs (Keep existing logic mostly, confirm variables) ---

// 移除旧的导航函数，由路由接管
// function switchTab(tabId) ...
// function loadEventDetail(eventId) ...
// function closeDetail() ...

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
        
        <!-- 筛选控件 (胶囊化设计) -->
        <div style="background:rgba(99, 126, 96, 0.03); padding:20px; border-radius:18px; margin-bottom:20px; border:1px solid rgba(99, 126, 96, 0.1);">
            <div style="display:flex; flex-wrap:wrap; gap:15px; align-items:center;">
                <!-- 只看有票 -->
                <label style="display:flex; align-items:center; background:#fff; padding:6px 14px; border-radius:50px; border:1px solid var(--border-color); cursor:pointer; font-size:0.85rem; color:var(--text-secondary); transition: all 0.2s;">
                    <style>
                        #filter-available:checked + span { color: var(--primary-color); font-weight: 600; }
                    </style>
                    <input type="checkbox" id="filter-available" onchange="applyDetailFilters('${event.id}')" style="margin-right:6px">
                    <span>只看有票</span>
                </label>
                
                <div style="width:1px; height:20px; background:var(--border-color);"></div>

                <!-- 价位筛选 -->
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <span style="font-size:0.85rem; color:var(--text-secondary); margin-right:5px">价位:</span>
                    ${allPrices.map(price => `
                        <label style="display:flex; align-items:center; background:#fff; padding:4px 12px; border-radius:50px; border:1px solid var(--border-color); cursor:pointer; font-size:0.8rem; color:var(--text-secondary);">
                            <input type="checkbox" class="filter-price" value="${price}" checked onchange="applyDetailFilters('${event.id}')" style="margin-right:4px">
                            <span>¥${price}</span>
                        </label>
                    `).join('')}
                </div>
                
                ${hasCast ? `
                <div style="width:1px; height:20px; background:var(--border-color);"></div>
                <!-- 演员搜索 -->
                <div style="display:flex; align-items:center; background:#fff; padding:2px 4px 2px 14px; border-radius:50px; border:1px solid var(--border-color); flex:1; min-width:200px;">
                    <i class="material-icons" style="font-size:1.1rem; color:var(--primary-color); margin-right:8px">search</i>
                    <input 
                        type="text" 
                        id="filter-cast" 
                        placeholder="输入演员姓名筛选场次..." 
                        style="border:none; outline:none; font-size:0.85rem; padding:8px 0; width:100%; color:var(--text-primary); background:transparent;"
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

        const castStr = hasCast && t.cast && t.cast.length > 0
            ? t.cast.map(c => `<span class="cast-link" onclick="event.stopPropagation(); searchInCoCast('${c.name}')" style="color:var(--primary-color); cursor:pointer; text-decoration:underline;">${c.name}</span>`).join(' | ')
            : '-';
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
                ${hasCast ? `<td class="cast-cell" data-label="卡司" onclick="event.stopPropagation()">${castStr}</td>` : ''}
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

// 演员 A & B 查询辅助逻辑
function addCastInput() {
    const container = document.getElementById('cocast-inputs');
    const div = document.createElement('div');
    div.className = 'input-row';
    // Remove list attribute from HTML, will be added dynamically by JS
    div.innerHTML = '<input type="text" class="cast-name-input" placeholder="输入演员姓名" oninput="handleActorInput(this)">';
    container.appendChild(div);
}

// 动态处理演员输入联想
function handleActorInput(input) {
    if (input.value.trim().length > 0) {
        input.setAttribute('list', 'all-actor-list');
    } else {
        input.removeAttribute('list');
    }
}

// 初始化演员自动补全功能
async function initActorAutocomplete() {
    try {
        console.log("正在加载演员索引...");
        const res = await fetch('/api/meta/artists');
        if (!res.ok) throw new Error('Failed to fetch artists');
        const data = await res.json();
        const artists = data.artists || [];

        if (artists.length === 0) return;

        // Create datalist
        const datalist = document.createElement('datalist');
        datalist.id = 'all-actor-list';

        // Use document fragment for performance
        const fragment = document.createDocumentFragment();
        artists.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            fragment.appendChild(option);
        });
        datalist.appendChild(fragment);
        document.body.appendChild(datalist);

        // Handle existing inputs and add event listener
        document.querySelectorAll('.cast-name-input').forEach(input => {
            input.removeAttribute('list'); // Default no list
            input.addEventListener('input', () => handleActorInput(input));
        });

        console.log(`已加载 ${artists.length} 名演员索引`);
    } catch (e) {
        console.error("加载演员自动补全失败:", e);
    }
}

// Start initialization
initActorAutocomplete();

async function doCoCastSearch() {
    const btn = document.querySelector('.search-btn');
    if (!btn) return;

    // 如果已经在查询中，再次点击则取消
    if (btn.classList.contains('btn-searching')) {
        if (window.coCastPollInterval) {
            clearInterval(window.coCastPollInterval);
            window.coCastPollInterval = null;
        }
        resetSearchButton(btn);
        const resultsContainer = document.getElementById('cast-results');
        if (resultsContainer) resultsContainer.innerHTML = '<div style="padding:40px;text-align:center;color:#999">查询已取消</div>';
        return;
    }

    const inputs = document.querySelectorAll('.cast-name-input');
    const casts = Array.from(inputs).map(i => i.value.trim()).filter(v => v);
    if (casts.length === 0) return alert('请输入演员姓名');

    // 1. 瞬间闪亮动画
    btn.classList.add('btn-flash');
    setTimeout(() => btn.classList.remove('btn-flash'), 400);

    // 2. 变为“查询中”状态
    const originalContent = btn.innerHTML;
    btn.innerHTML = `<div>查询中</div><div class="cancel-text">点击取消</div>`;
    btn.classList.add('btn-searching');

    const onlyStudent = document.getElementById('student-only-toggle')?.checked || false;
    const resultsContainer = document.getElementById('cast-results');
    resultsContainer.innerHTML = `
        <div style="padding:40px; text-align:center; display:flex; flex-direction:column; align-items:center; gap:20px; background:rgba(99, 126, 96, 0.02); border-radius:24px; margin-top:20px; border:1px solid rgba(99, 126, 96, 0.05);">
            <div style="display:flex; align-items:center; gap:15px">
                <div class="spinner"></div>
                <div style="color:var(--primary-color); font-weight:600; font-size:1.1rem;" id="search-status-text">正在初始化查询...</div>
            </div>
            <div style="width:100%; max-width:400px;">
                <div style="margin-bottom: 8px; display: flex; justify-content: space-between; font-size:0.85rem; color:var(--text-secondary);">
                    <span>数据同步进度</span>
                    <span id="search-progress-text">0%</span>
                </div>
                <div style="background: rgba(0,0,0,0.05); border-radius: 50px; height: 10px; overflow: hidden; border:1px solid rgba(0,0,0,0.02);">
                    <div id="search-progress-bar" style="background: var(--primary-color); height: 100%; width: 0%; transition: width 0.4s cubic-bezier(0.1, 0.7, 0.1, 1); box-shadow: 0 0 10px rgba(99, 126, 96, 0.2);"></div>
                </div>
            </div>
            <div style="color:var(--text-secondary); font-size:0.85rem;">正在查询 ${casts.join(' & ')} 的同台场次，请稍候...</div>
        </div>
    `;

    try {
        const startInput = document.getElementById('cocast-start-date');
        const endInput = document.getElementById('cocast-end-date');
        const startDate = startInput ? startInput.value : "";
        const endDate = endInput ? endInput.value : "";

        if (startDate && startDate < "2023-01-01") {
            alert("开始日期不能早于 2023-01-01");
            resetSearchButton(btn);
            return;
        }

        const oneYearLater = new Date();
        oneYearLater.setFullYear(new Date().getFullYear() + 1);
        const nextYearStr = oneYearLater.toISOString().split('T')[0];

        if (endDate && endDate > nextYearStr) {
            alert(`结束日期不能晚于 ${nextYearStr}`);
            resetSearchButton(btn);
            return;
        }

        if (startDate && endDate && endDate < startDate) {
            alert("结束日期不能早于开始日期");
            resetSearchButton(btn);
            return;
        }

        const startRes = await fetch('/api/tasks/co-cast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                casts: casts.join(','),
                only_student: onlyStudent,
                start_date: startDate,
                end_date: endDate
            })
        });

        if (!startRes.ok) throw new Error("启动搜索任务失败");
        const { task_id } = await startRes.json();

        window.coCastPollInterval = setInterval(async () => {
            try {
                const statusRes = await fetch(`/api/tasks/${task_id}`);
                if (!statusRes.ok) {
                    clearInterval(window.coCastPollInterval);
                    resetSearchButton(btn);
                    resultsContainer.innerHTML = `<div style='color:red;padding:20px;text-align:center'>查询状态出错</div>`;
                    return;
                }

                const job = await statusRes.json();
                const pBar = document.getElementById('search-progress-bar');
                const pText = document.getElementById('search-progress-text');
                const sText = document.getElementById('search-status-text');

                if (pBar) pBar.style.width = `${job.progress}%`;
                if (pText) pText.innerText = `${job.progress}%`;
                if (sText) sText.innerText = job.message || "正匹配场次...";

                if (job.status === 'completed') {
                    clearInterval(window.coCastPollInterval);
                    finishSearchButton(btn);
                    setTimeout(() => {
                        renderCoCastResults(job.result.results, job.result.source, casts);
                    }, 400);
                } else if (job.status === 'failed') {
                    clearInterval(window.coCastPollInterval);
                    resetSearchButton(btn);
                    resultsContainer.innerHTML = `<div style='color:#d9534f;padding:40px;text-align:center;background:rgba(217,83,79,0.05);border-radius:24px;border:1px solid rgba(217,83,79,0.1);'>
                        <i class="material-icons" style="font-size:3rem;display:block;margin-bottom:10px">error_outline</i>
                        <div style="font-weight:600">查询失败</div>
                        <div style="font-size:0.85rem;margin-top:5px">${job.error || "未知错误"}</div>
                    </div>`;
                }
            } catch (pollErr) {
                console.error("Poll error:", pollErr);
            }
        }, 600);

    } catch (e) {
        resetSearchButton(btn);
        resultsContainer.innerHTML = `<div style='color:#d9534f;padding:40px;text-align:center'>❌ 发起查询失败: ${e.message}</div>`;
    }
}

// 辅助函数：恢复按钮原状
function resetSearchButton(btn) {
    btn.classList.remove('btn-searching');
    btn.innerHTML = `<i class="material-icons" style="margin-right: 8px; vertical-align: middle;">search</i> 查询`;
}

// 辅助函数：完成查询（带回弹动效）
function finishSearchButton(btn) {
    btn.classList.remove('btn-searching');
    btn.innerHTML = `<i class="material-icons" style="margin-right: 8px; vertical-align: middle;">search</i> 查询`;
    btn.classList.add('btn-success-back');
    setTimeout(() => btn.classList.remove('btn-success-back'), 600);
}

function renderCoCastResults(results, source, casts) {
    const container = document.getElementById('cast-results');
    if (!results || results.length === 0) {
        container.innerHTML = '<div style="padding:40px;text-align:center;color:#999">未找到同场演出</div>';
        return;
    }

    const isSaoju = source === 'saoju';
    const col = state.coCastCols || { index: true, others: true, location: true };
    state.lastCoCastResults = results;
    state.lastCoCastSource = source;
    state.lastCoCastCasts = casts; // Store casts for re-rendering

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

    const summaryHtml = calculateCoCastStats(filtered, casts);

    let html = `
        <div style="margin-bottom:20px;padding:15px;background:#f0f7ff;border-radius:12px;border-left:5px solid var(--primary-color)">
            ${summaryHtml}

        </div>
        <div style="margin-bottom:15px;padding:10px;background:#f0f7ff;border-radius:8px;border-left:4px solid var(--primary-color)">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
                <div>
                    <div style="font-size:1.1em;font-weight:600;color:var(--primary-color);margin-bottom:5px">🎭 查询到 ${results.length} 场同台演出</div>
                </div>
                <div style="display:flex;gap:10px;align-items:center;font-size:0.9em;flex-wrap:wrap">
                    <label style="cursor:pointer"><input type="checkbox" ${col.index ? 'checked' : ''} onchange="state.coCastCols.index = this.checked; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource, state.lastCoCastCasts)"> 序号</label>
                    <label style="cursor:pointer"><input type="checkbox" ${col.others ? 'checked' : ''} onchange="state.coCastCols.others = this.checked; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource, state.lastCoCastCasts)"> 其TA卡司</label>
                    <label style="cursor:pointer"><input type="checkbox" ${col.location ? 'checked' : ''} onchange="state.coCastCols.location = this.checked; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource, state.lastCoCastCasts)"> 剧场</label>
                    <span>|</span>
                    <select onchange="state.coCastYearFilter = this.value; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource, state.lastCoCastCasts)" style="padding:3px 8px;border-radius:4px">
                        <option value="">全部年份</option>
                        ${years.map(y => `<option value="${y}" ${selectedYear == y ? 'selected' : ''}>${y}年</option>`).join('')}
                    </select>
                    <button onclick="state.coCastDateSort = !state.coCastDateSort; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource, state.lastCoCastCasts)" 
                            style="padding:3px 10px;border-radius:4px;border:1px solid #ddd;background:white;cursor:pointer">
                        日期 ${sortAsc ? '↓' : '↑'}
                    </button>
                </div>
            </div>
        </div>
        <div class="data-table-container">
        <table class="data-table">
            <thead>
                <tr>
                    ${col.index ? '<th width="50">#</th>' : ''}
                    <th width="200">日期/时间</th>
                    <th width="60">城市</th>
                    <th>剧目</th>
                    <th width="120">角色</th>
                    ${col.location ? '<th>剧场</th>' : ''}
                    ${col.others ? '<th>其TA卡司</th>' : ''}
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
        const titleDisplay = (!isSaoju && r.event_id)
            ? `<span onclick="jumpToDetail('${r.event_id}', '${r.session_id || ''}')" style="cursor:pointer; color:var(--primary-color); font-weight:600; text-decoration:underline;">${r.title}</span>`
            : r.title;

        html += `
            <tr>
                ${col.index ? `<td data-label="#">${idx + 1}</td>` : ''}
                <td class="time-cell" data-label="日期/时间">${dateDisplay}</td>
                <td class="city-cell" data-label="城市">${r.city || '-'}</td>
                <td class="title-cell" data-label="剧目">${titleDisplay}</td>
                <td data-label="角色">${r.role || '-'}</td>
                ${col.location ? `<td data-label="剧场">${r.location || '-'}</td>` : ''}
                ${col.others ? `<td class="cast-cell" data-label="其TA卡司">${othersStr}</td>` : ''}
            </tr>
        `;
    });
    container.innerHTML = html + '</tbody></table></div>';
}

// 计算同场统计摘要
function calculateCoCastStats(results, casts) {
    if (!results || results.length === 0) return '';

    const total = results.length;
    const castNamesHeader = casts.join(' & ');

    // 分组统计：剧目 -> 角色组合 -> 场次
    const groupMap = {};
    results.forEach(r => {
        const title = r.title || '未知剧目';
        const role = r.role || '未知角色';

        if (!groupMap[title]) {
            groupMap[title] = {
                total: 0,
                roles: {}
            };
        }
        groupMap[title].total++;
        groupMap[title].roles[role] = (groupMap[title].roles[role] || 0) + 1;
    });

    let html = `
        <div style="margin-bottom:12px; font-weight:600; font-size:1.1rem; color:var(--primary-color);">
            ${castNamesHeader} 已经同台了 <span style="font-size:1.4rem; margin:0 4px;">${total}</span> 场
        </div>
        <div style="display:flex; flex-direction:column; gap:8px;">
    `;

    // 遍历剧目
    Object.keys(groupMap).sort((a, b) => groupMap[b].total - groupMap[a].total).forEach(title => {
        const group = groupMap[title];
        html += `
            <div style="display:flex; flex-direction:column; padding:8px 12px; background:rgba(99, 126, 96, 0.04); border-radius:10px;">
                <div style="font-weight:600; color:var(--text-primary); margin-bottom:4px;">
                    《${title}》 <span style="color:var(--primary-color); margin-left:8px;">${group.total}场</span>
                </div>
        `;

        // 遍历角色组合
        Object.keys(group.roles).sort((a, b) => group.roles[b] - group.roles[a]).forEach(role => {
            const count = group.roles[role];
            html += `
                <div style="font-size:0.85rem; color:var(--text-secondary); padding-left:12px; margin-top:2px;">
                    ${role}  <span style="opacity:0.8; margin-left:10px;">${count}场</span>
                </div>
            `;
        });

        html += `</div>`;
    });

    html += `</div>`;
    return html;
}

// Add column filtering functionality
document.querySelectorAll('.cocast-table th[data-column]').forEach(header => {
    header.style.cursor = 'pointer';
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
// 快捷设置日期范围
function setCoCastRange(type) {
    const startInput = document.getElementById('cocast-start-date');
    const endInput = document.getElementById('cocast-end-date');
    if (!startInput || !endInput) return;

    if (type === 'earliest') {
        startInput.value = '2023-01-01';
    } else if (type === 'today') {
        const now = new Date();
        const yyyy = now.getFullYear();
        const mm = String(now.getMonth() + 1).padStart(2, '0');
        const dd = String(now.getDate()).padStart(2, '0');
        startInput.value = `${yyyy}-${mm}-${dd}`;
    }
}

// 快捷设置日期并搜索
function setQuickDate(type) {
    const input = document.getElementById('date-input');
    const now = new Date();
    let target = new Date();

    if (type === 'today') {
        target = now;
    } else if (type === 'weekend') {
        const day = now.getDay();
        const diff = (day === 0 ? 0 : 6 - day); // 如果是周日则选今天，否则选周六
        target.setDate(now.getDate() + diff);
    } else if (type === 'next_weekend') {
        const day = now.getDay();
        const diff = (day === 0 ? 6 : 6 - day) + 7; // 下周六
        target.setDate(now.getDate() + diff);
    }

    const yyyy = target.getFullYear();
    const mm = String(target.getMonth() + 1).padStart(2, '0');
    const dd = String(target.getDate()).padStart(2, '0');

    input.value = `${yyyy}-${mm}-${dd}`;
    doDateSearch();
}

async function doDateSearch() {
    const dateInput = document.getElementById('date-input');
    const resultsContainer = document.getElementById('date-results');

    const selectedDate = dateInput.value;

    if (!selectedDate) {
        resultsContainer.innerHTML = '<div style="padding:40px;text-align:center;color:#999">请选择日期</div>';
        return;
    }

    // 更新路由但不触发渲染（因为我们已经在这里处理了）
    const currentPath = router.getCurrentPath();
    if (!currentPath.includes(`d=${selectedDate}`)) {
        window.history.replaceState(null, '', `#/date?d=${selectedDate}`);
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
                        <th width="180">卡司</th>
                        <th width="100">价格</th>
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

        // 使用id或event_id字段
        const eventId = t.event_id || t.id;
        const sessionId = t.session_id || (t.session_time ? new Date(t.session_time).getTime() : '');

        html += `
            <tr class="${rowClass}" data-session-id="${sessionId}">
                <td class="time-cell" data-label="时间">${timeStr}</td>
                <td class="city-cell" data-label="城市">${t.city || '-'}</td>
                <td class="title-cell" data-label="剧目" 
                    style="cursor:pointer; color:var(--primary-color); font-weight:600;"
                    onclick="jumpToDetail('${eventId}', '${sessionId}')">
                    ${showTitle}
                </td>
                <td data-label="余票">${t.stock}/${t.total_ticket}</td>
                <td class="cast-cell" data-label="卡司">${castStr}</td>
                <td data-label="价格">¥${t.price}</td>
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
    router.navigate('/detail/' + eventId);

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

        // 添加高亮类
        targetRow.classList.add('highlight-row');

        // 动画结束后移除类
        setTimeout(() => {
            targetRow.classList.remove('highlight-row');
        }, 2500);
    }
}

// Global search function mainly for header call, mapped to live filter now
async function doGlobalSearch() {
    // Just trigger filter
    applyFilters();
}
