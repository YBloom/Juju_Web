
import { state } from './state.js';
import { api } from './api.js';
import { router } from './router.js';
import { getCityScore, formatDateStr, formatDateDisplay, getNormalizedTitle, getPrice, escapeHtml } from './utils.js';
import { initTicketUpdates } from './ticket_updates.js';

// --- Tab Management ---

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

// --- Data & Initialization ---

export async function fetchUpdateStatus() {
    const statusEl = document.getElementById('update-status');
    if (!statusEl) return;

    try {
        const data = await api.fetchUpdateStatus();
        let html = '';

        if (data.hulaquan && data.hulaquan.last_updated) {
            const lastUpdate = new Date(data.hulaquan.last_updated);
            const now = new Date();
            const diffMs = now - lastUpdate;
            const diffMins = Math.floor(diffMs / 60000);

            if (diffMins < 60) {
                html += `呼啦圈数据: ${diffMins}分钟前更新`;
            } else if (diffMins < 1440) {
                const hours = Math.floor(diffMins / 60);
                html += `呼啦圈数据: ${hours}小时前更新`;
            } else {
                const days = Math.floor(diffMins / 1440);
                html += `呼啦圈数据: ${days}天前更新`;
            }

            if (!data.hulaquan.active) {
                html += ' (自动更新未启用)';
            }
        } else {
            html += '呼啦圈数据: 尚未同步';
        }

        html += ' | Saoju.net缓存: 24小时内有效';

        if (data.service_info) {
            html += `<div style="margin-top:4px;"><a href="#" id="version-link" class="version-link">${escapeHtml(data.service_info.version || 'v1.0')}</a> | 启动于: ${escapeHtml(data.service_info.start_time || '未知')}</div>`;
        }

        statusEl.innerHTML = html;
    } catch (e) {
        statusEl.innerHTML = '无法获取更新状态';
    }
}

export async function initHlqTab() {
    const container = document.getElementById('hlq-list-container');
    container.innerHTML = '<div style="padding:40px;text-align:center;color:#888">正在加载演出数据...</div>';

    try {
        const data = await api.fetchEventList();
        state.allEvents = data.results;
        renderCityFilterOptions();
        applyFilters();

        // Initialize Ticket Updates Dashboard
        initTicketUpdates();
    } catch (e) {
        container.innerHTML = `<div style="color:red;padding:20px;text-align:center">加载失败: ${escapeHtml(e.message)}</div>`;
    }
}

// --- List View ---

export function renderCityFilterOptions() {
    const cities = [...new Set(state.allEvents.map(e => e.city).filter(c => c))].sort();
    const toolbar = document.querySelector('.toolbar');

    // Legacy support: if toolbar exists, use it as container, otherwise check for new container
    let container = document.getElementById('top-filter-container');

    // Clean up old toolbar if it exists and we haven't migrated
    if (toolbar && !container) {
        toolbar.innerHTML = ''; // Clear legacy toolbar
        toolbar.id = 'top-filter-container'; // Reuse element
        toolbar.className = 'filter-pills-scroll-wrapper'; // Use new wrapper class
        toolbar.style.marginBottom = '20px';
        container = toolbar;
    }

    if (!container) return; // Should likely exist in index.html, but safety check

    // Generate Pills HTML
    // Fixed "All" pill
    const allActive = !document.getElementById('city-filter-value')?.value; // Simplified state check needed? 
    // Actually, let's use a simpler approach: Just render completely new HTML

    let html = `<div class="filter-pills-container" style="padding: 4px 2px;">
        <div class="filter-pill ${!state.cityFilter ? 'active' : ''}" data-city="">
            全部城市
        </div>`;

    cities.forEach(c => {
        const isActive = state.cityFilter === c;
        html += `<div class="filter-pill ${isActive ? 'active' : ''}" data-city="${escapeHtml(c)}">
            ${escapeHtml(c)}
        </div>`;
    });

    html += `</div>`;
    container.innerHTML = html;

    // Add listeners
    container.querySelectorAll('.filter-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            const city = pill.dataset.city || '';
            // Handle "All" case vs specific city
            state.cityFilter = city;
            renderCityFilterOptions(); // Re-render to update active state
            applyFilters();
        });
    });
}

export function applyFilters() {
    const events = state.allEvents || [];
    if (events.length === 0) {
        renderEventTable([]);
        return;
    }

    const currentCity = state.cityFilter;
    // Global Search
    const searchInput = document.getElementById('global-search');
    const searchValue = searchInput ? searchInput.value.trim().toLowerCase() : '';

    const filtered = events.filter(e => {
        // City Filter
        if (currentCity && e.city !== currentCity) return false;

        // Search Filter
        if (searchValue) {
            const title = e.title ? e.title.toLowerCase() : '';
            const city = e.city ? e.city.toLowerCase() : '';
            const location = e.location ? e.location.toLowerCase() : '';
            if (!title.includes(searchValue) && !city.includes(searchValue) && !location.includes(searchValue)) {
                return false;
            }
        }
        return true;
    });

    renderEventTable(filtered);
}
// Search listener
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('global-search');
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            // Debounce could be good, but for now direct call
            applyFilters();
        });
    }
});

export function renderEventTable(events) {
    const container = document.getElementById('hlq-list-container');
    if (!events || events.length === 0) {
        container.innerHTML = '<div style="padding:50px;text-align:center;color:#aaa">暂无符合条件的演出</div>';
        return;
    }

    // New Div Layout
    let html = `<div class="event-list-main">`;

    events.forEach(e => {
        const scheduleRange = e.schedule_range || '-';
        let showTitle = e.title;
        // Clean title: remove book title marks if present
        if (e.title) {
            const titleMatch = e.title.match(/[《](.*?)[》]/);
            if (titleMatch && titleMatch[1]) showTitle = titleMatch[1];
        }

        // v2.1 Layout
        // Left: City (Mobile: Gray, Fixed Width)
        // Center: Title (Bold)
        // Right/Bottom: Date

        html += `
        <div class="event-row" data-event-id="${e.id}">
            <!-- Left: City -->
            <div class="event-city">${escapeHtml(e.city)}</div>
            
            <!-- Center: Info -->
            <div class="event-info">
                <div class="event-title">${escapeHtml(showTitle)}</div>
                <div class="event-date">${escapeHtml(scheduleRange)}</div>
            </div>
            
            <!-- Right: Arrow (Optional, maybe for Desktop) -->
            <div class="event-arrow">›</div>
        </div>`;
    });

    html += '</div>';
    container.innerHTML = html;

    // Add Listeners
    container.querySelectorAll('.event-row').forEach(row => {
        row.addEventListener('click', () => {
            if (row.dataset.eventId) router.navigate(`/detail/${row.dataset.eventId}`);
        });
    });
}

// --- Detail View ---

export async function showDetailView(eventId) {
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    document.getElementById('detail-view').classList.remove('hidden');

    const container = document.getElementById('detail-content');
    container.innerHTML = '<div style="padding:40px;text-align:center">加载详情中...</div>';

    try {
        const data = await api.fetchEventDetail(eventId);
        if (data.results && data.results.length > 0) {
            renderDetailView(data.results[0]);

            // --- LOGGING ---
            const evt = data.results[0];
            try {
                fetch('/api/log/view', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: evt.title, id: evt.id })
                });
            } catch (ignore) { }
            // --- END LOGGING ---

        } else {
            container.innerHTML = '<div style="padding:40px;text-align:center;color:#999">未找到演出信息</div>';
        }
    } catch (e) {
        container.innerHTML = '<div style="padding:40px;text-align:center;color:red">加载失败。</div>';
    }
}

function renderDetailView(event) {
    const container = document.getElementById('detail-content');
    const allTickets = event.tickets.sort((a, b) => new Date(a.session_time) - new Date(b.session_time));
    const hasCast = allTickets.some(t => t.cast && t.cast.length > 0);
    const years = [...new Set(allTickets.map(t => t.session_time ? new Date(t.session_time).getFullYear() : null).filter(y => y !== null))];
    const showYear = years.length > 1;
    const allPrices = [...new Set(allTickets.map(t => t.price))].sort((a, b) => a - b);

    state.currentDetailEvent = event;
    state.currentDetailTickets = allTickets;
    state.currentDetailShowYear = showYear;
    state.currentDetailHasCast = hasCast;

    let html = `
        <div style="background:#fcfcfc; padding:20px; border-radius:10px; border:1px solid #eee; margin-bottom:20px">
            <h2 style="margin-top:0; color:var(--primary-color)">${escapeHtml(event.title)}</h2>
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style="display:flex; gap:20px; color:#666">
                    <span>📍 ${escapeHtml(event.location || '未知场馆')}</span>
                    <span>📅 排期: ${escapeHtml(event.schedule_range || '待定')}</span>
                </div>
                <div style="font-size:0.85em; color:var(--text-secondary); opacity:0.8;">
                    💡 点击场次可跳转呼啦圈购票
                </div>
            </div>
        </div>
        
        <div style="background:rgba(99, 126, 96, 0.03); padding:20px; border-radius:18px; margin-bottom:20px; border:1px solid rgba(99, 126, 96, 0.1);">
            <div style="display:flex; flex-wrap:wrap; gap:15px; align-items:center;">
                <label style="display:flex; align-items:center; background:#fff; padding:6px 14px; border-radius:50px; border:1px solid var(--border-color); cursor:pointer; font-size:0.85rem; color:var(--text-secondary); transition: all 0.2s;">
                    <style>#filter-available:checked + span { color: var(--primary-color); font-weight: 600; }</style>
                    <input type="checkbox" id="filter-available" style="margin-right:6px"><span>只看有票</span>
                </label>
                <div style="width:1px; height:20px; background:var(--border-color);"></div>
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <span style="font-size:0.85rem; color:var(--text-secondary); margin-right:5px">价位:</span>
                    ${allPrices.map(price => `<label style="display:flex; align-items:center; background:#fff; padding:4px 12px; border-radius:50px; border:1px solid var(--border-color); cursor:pointer; font-size:0.8rem; color:var(--text-secondary);"><input type="checkbox" class="filter-price" value="${price}" checked style="margin-right:4px"><span>¥${price}</span></label>`).join('')}
                </div>
                ${hasCast ? `<div style="width:1px; height:20px; background:var(--border-color);"></div><div style="display:flex; align-items:center; background:#fff; padding:2px 4px 2px 14px; border-radius:50px; border:1px solid var(--border-color); flex:1; min-width:200px;"><i class="material-icons" style="font-size:1.1rem; color:var(--primary-color); margin-right:8px">search</i><input type="text" id="filter-cast" placeholder="输入演员姓名筛选场次..." style="border:none; outline:none; font-size:0.85rem; padding:8px 0; width:100%; color:var(--text-primary); background:transparent;"></div>` : ''}
            </div>
        </div>
        
        <div id="detail-table-container">
            <table class="data-table">
                <thead><tr><th>演出时间</th><th width="80">库存</th>${hasCast ? '<th>卡司</th>' : ''}<th width="150">价格</th></tr></thead>
                <tbody id="detail-table-body"></tbody>
            </table>
        </div>
    `;

    container.innerHTML = html;
    document.getElementById('filter-available')?.addEventListener('change', () => applyDetailFilters(event.id));
    document.querySelectorAll('.filter-price').forEach(el => el.addEventListener('change', () => applyDetailFilters(event.id)));
    document.getElementById('filter-cast')?.addEventListener('input', () => applyDetailFilters(event.id));

    renderDetailTableRows(allTickets, showYear, hasCast, event.id);
}

export function applyDetailFilters(eventId) {
    const { currentDetailTickets: allTickets, currentDetailShowYear: showYear, currentDetailHasCast: hasCast } = state;
    if (!allTickets) return;

    const onlyAvailable = document.getElementById('filter-available')?.checked || false;
    const selectedPrices = Array.from(document.querySelectorAll('.filter-price:checked')).map(cb => parseFloat(cb.value));
    const castSearch = document.getElementById('filter-cast')?.value.trim().toLowerCase() || '';

    let filtered = allTickets.filter(t => {
        if (onlyAvailable && (t.stock === 0 || t.status === 'sold_out')) return false;
        if (selectedPrices.length > 0 && !selectedPrices.includes(t.price)) return false;
        if (castSearch && hasCast) {
            const castNames = t.cast ? t.cast.map(c => c.name.toLowerCase()).join(' ') : '';
            if (!castNames.includes(castSearch)) return false;
        }
        return true;
    });

    renderDetailTableRows(filtered, showYear, hasCast, eventId);
}

function renderDetailTableRows(tickets, showYear, hasCast, eventId) {
    const tbody = document.getElementById('detail-table-body');
    if (!tbody) return;

    let html = '';
    tickets.forEach(t => {
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
            timeStr = showYear ? `${year}年${month}月${day}日 周${weekday} ${hours}:${minutes}` : `${month}月${day}日 周${weekday} ${hours}:${minutes}`;
        }

        const castStr = hasCast && t.cast && t.cast.length > 0 ? t.cast.map(c => `<span class="cast-link" data-name="${escapeHtml(c.name)}" style="color:var(--primary-color); cursor:pointer; text-decoration:underline;">${escapeHtml(c.name)}</span>`).join(' | ') : '-';

        let priceStr = t.price_label && t.price_label !== `¥${t.price}` ? t.price_label : (t.original_price && t.original_price !== t.price ? `${t.price}（原价${t.original_price}）` : `¥${t.price}`);
        const isSoldOut = (t.stock !== undefined ? t.stock : 0) === 0 || t.status === 'sold_out';

        let validFromInfo = '';
        if (t.valid_from) {
            validFromInfo = `<div style="font-size:0.8rem; color:#f59e0b; margin-top:4px; display:flex; align-items:center; gap:4px;">
                <span class="material-icons" style="font-size:1rem;">alarm</span>
                ${escapeHtml(t.valid_from)} 开票
            </div>`;
        }

        const sessionId = t.session_id || (t.session_time ? new Date(t.session_time).getTime() : '');

        html += `<tr class="${isSoldOut ? 'sold-out' : ''}" data-session-id="${sessionId}" style="cursor:pointer">
            <td class="time-cell" data-label="演出时间">${escapeHtml(timeStr)}${validFromInfo}</td>
            <td class="stock-cell" data-label="库存">${escapeHtml(t.stock)}/${escapeHtml(t.total_ticket)}</td>
            ${hasCast ? `<td class="cast-cell" data-label="卡司">${castStr}</td>` : ''}
            <td class="price-cell" data-label="价格">${escapeHtml(priceStr)}</td>
        </tr>`;
    });

    tbody.innerHTML = html || '<tr><td colspan="4" style="text-align:center;padding:40px;color:#999;">没有符合条件的场次</td></tr>';

    tbody.querySelectorAll('tr').forEach(row => row.addEventListener('click', () => window.open(`https://clubz.cloudsation.com/event/${eventId}.html`, '_blank')));
    tbody.querySelectorAll('.cast-link').forEach(span => span.addEventListener('click', (e) => { e.stopPropagation(); searchInCoCast(span.dataset.name); }));
}

// --- Co-Cast ---

export function initCoCastDates() {
    const startInput = document.getElementById('cocast-start-date');
    const endInput = document.getElementById('cocast-end-date');
    if (!startInput || !endInput) return;

    const now = new Date();
    const oneYearLater = new Date();
    oneYearLater.setFullYear(now.getFullYear() + 1);
    const todayStr = formatDateStr(now);
    const nextYearStr = formatDateStr(oneYearLater);

    startInput.min = "2023-01-01";
    endInput.min = "2023-01-01";
    endInput.max = nextYearStr;

    if (!startInput.value) startInput.value = todayStr;
    if (!endInput.value) endInput.value = nextYearStr;
}

export function searchInCoCast(castName) {
    router.navigate('/cocast');
    setTimeout(() => {
        const inputs = document.querySelectorAll('.cast-name-input');
        if (inputs.length > 0) {
            inputs[0].value = castName || '';
            for (let i = 1; i < inputs.length; i++) inputs[i].value = '';
            doCoCastSearch();
        }
    }, 100);
}

export function addCastInput() {
    const container = document.getElementById('cocast-inputs');
    const div = document.createElement('div');
    div.className = 'cocast-row';
    div.innerHTML = `<div class="input-wrapper"><input type="text" class="cast-name-input" placeholder="输入演员姓名" autocomplete="off"></div><button class="circle-btn remove" title="移除演员"><i class="material-icons">remove</i></button>`;
    container.appendChild(div);
    updateCastInputLabels();
    bindAutocomplete(div.querySelector('.cast-name-input'));
    div.querySelector('.remove').addEventListener('click', (e) => removeCastInput(e.target.closest('.circle-btn')));
}

export function removeCastInput(btn) {
    const row = btn.closest('.cocast-row');
    if (row && document.getElementById('cocast-inputs')) {
        row.remove();
        updateCastInputLabels();
    }
}

function updateCastInputLabels() {
    document.querySelectorAll('.cocast-row .cast-name-input').forEach((input, index) => {
        input.placeholder = `输入演员${String.fromCharCode(65 + (index % 26))}姓名`;
    });
}

export async function initActorAutocomplete() {
    try {
        const data = await api.fetchArtists();
        state.allArtistNames = data.artists || [];
        document.querySelectorAll('.cast-name-input').forEach(input => bindAutocomplete(input));
    } catch (e) {
        console.error("Failed to init actor autocomplete:", e);
    }
}

function bindAutocomplete(input) {
    if (!input) return;
    let dropdown = input.parentNode.querySelector('.autocomplete-suggestions');
    if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.className = 'autocomplete-suggestions';
        input.parentNode.appendChild(dropdown);
    }

    input.addEventListener('input', (e) => {
        const val = e.target.value.trim();
        if (!val) { dropdown.style.display = 'none'; return; }

        let matches = [];
        if (window.pinyinPro) {
            matches = state.allArtistNames.filter(name => {
                if (name.includes(val)) return true;
                try {
                    const firstLetters = window.pinyinPro.pinyin(name, { pattern: 'first', toneType: 'none', type: 'array' }).join('');
                    return firstLetters.includes(val.toLowerCase());
                } catch (e) { return false; }
            }).slice(0, 10);
        } else {
            matches = state.allArtistNames.filter(name => name.includes(val)).slice(0, 10);
        }
        renderSuggestions(dropdown, matches, input);
    });

    input.addEventListener('focus', () => { if (input.value.trim()) input.dispatchEvent(new Event('input')); });
}

function renderSuggestions(dropdown, matches, input) {
    dropdown.innerHTML = '';
    if (matches.length === 0) { dropdown.style.display = 'none'; return; }
    matches.forEach(name => {
        const item = document.createElement('div');
        item.className = 'autocomplete-item';
        item.textContent = name;
        item.addEventListener('click', () => { input.value = name; dropdown.style.display = 'none'; });
        dropdown.appendChild(item);
    });
    dropdown.style.display = 'block';
}

export async function doCoCastSearch() {
    const btn = document.querySelector('.search-btn');
    if (!btn) return;

    if (btn.classList.contains('btn-searching')) {
        if (window.coCastPollInterval) { clearInterval(window.coCastPollInterval); window.coCastPollInterval = null; }
        resetSearchButton(btn);
        document.getElementById('cast-results').innerHTML = '<div style="padding:40px;text-align:center;color:#999">查询已取消</div>';
        return;
    }

    const inputs = document.querySelectorAll('.cast-name-input');
    const casts = Array.from(inputs).map(i => i.value.trim()).filter(v => v);
    if (casts.length === 0) return alert('请输入演员姓名');

    btn.classList.add('btn-flash');
    setTimeout(() => btn.classList.remove('btn-flash'), 400);
    btn.innerHTML = `<div>查询中</div><div class="cancel-text">点击取消</div>`;
    btn.classList.add('btn-searching');

    const resultsContainer = document.getElementById('cast-results');
    resultsContainer.innerHTML = `<div style="padding:40px; text-align:center; display:flex; flex-direction:column; align-items:center; gap:20px; background:rgba(99, 126, 96, 0.02); border-radius:24px; margin-top:20px; border:1px solid rgba(99, 126, 96, 0.05);"><div style="display:flex; align-items:center; gap:15px"><div class="spinner"></div><div style="color:var(--primary-color); font-weight:600; font-size:1.1rem;" id="search-status-text">正在初始化查询...</div></div><div style="width:100%; max-width:400px;"><div style="margin-bottom: 8px; display: flex; justify-content: space-between; font-size:0.85rem; color:var(--text-secondary);"><span>数据同步进度</span><span id="search-progress-text">0%</span></div><div style="background: rgba(0,0,0,0.05); border-radius: 50px; height: 10px; overflow: hidden; border:1px solid rgba(0,0,0,0.02);"><div id="search-progress-bar" style="background: var(--primary-color); height: 100%; width: 0%; transition: width 0.4s cubic-bezier(0.1, 0.7, 0.1, 1); box-shadow: 0 0 10px rgba(99, 126, 96, 0.2);"></div></div></div><div style="color:var(--text-secondary); font-size:0.85rem;">正在查询 ${casts.join(' & ')} 的同台场次，请稍候...</div></div>`;

    try {
        const startInput = document.getElementById('cocast-start-date');
        const endInput = document.getElementById('cocast-end-date');
        const startDate = startInput ? startInput.value : "";
        const endDate = endInput ? endInput.value : "";

        if (startDate && startDate < "2023-01-01") { alert("开始日期不能早于 2023-01-01"); resetSearchButton(btn); return; }
        if (endDate && endDate < startDate) { alert("结束日期不能早于开始日期"); resetSearchButton(btn); return; }

        const res = await api.startCoCastTask({
            casts: casts.join(','),
            only_student: document.getElementById('student-only-toggle')?.checked || false,
            start_date: startDate,
            end_date: endDate
        });

        window.coCastPollInterval = setInterval(async () => {
            try {
                const job = await api.fetchTaskStatus(res.task_id);
                const pBar = document.getElementById('search-progress-bar');
                const pText = document.getElementById('search-progress-text');
                const sText = document.getElementById('search-status-text');
                if (pBar) pBar.style.width = `${job.progress}%`;
                if (pText) pText.innerText = `${job.progress}%`;
                if (sText) sText.innerText = job.message || "正匹配场次...";

                if (job.status === 'completed') {
                    clearInterval(window.coCastPollInterval);
                    finishSearchButton(btn);
                    setTimeout(() => renderCoCastResults(job.result.results, job.result.source, casts), 400);
                } else if (job.status === 'failed') {
                    clearInterval(window.coCastPollInterval);
                    resetSearchButton(btn);
                    resultsContainer.innerHTML = `<div style='color:#d9534f;padding:40px;text-align:center'>❌ 查询失败: ${job.error || "未知错误"}</div>`;
                }
            } catch (pollErr) { console.error("Poll error:", pollErr); }
        }, 600);
    } catch (e) {
        resetSearchButton(btn);
        resultsContainer.innerHTML = `<div style='color:#d9534f;padding:40px;text-align:center'>❌ 发起查询失败: ${e.message}</div>`;
    }
}

function resetSearchButton(btn) {
    btn.classList.remove('btn-searching');
    btn.innerHTML = `<i class="material-icons" style="margin-right: 8px; vertical-align: middle;">search</i> 查询`;
}

function finishSearchButton(btn) {
    btn.classList.remove('btn-searching');
    btn.innerHTML = `<i class="material-icons" style="margin-right: 8px; vertical-align: middle;">search</i> 查询`;
    btn.classList.add('btn-success-back');
    setTimeout(() => btn.classList.remove('btn-success-back'), 600);
}

function renderCoCastResults(results, source, casts) {
    const container = document.getElementById('cast-results');
    if (!results || results.length === 0) { container.innerHTML = '<div style="padding:40px;text-align:center;color:#999">未找到同场演出</div>'; return; }

    state.lastCoCastResults = results;
    state.lastCoCastSource = source;
    state.lastCoCastCasts = casts;

    const col = state.coCastCols;
    const isSaoju = source === 'saoju';

    const resultsWithYear = results.map(r => {
        let year = r.year;
        if (!year || isNaN(year)) {
            if (r._raw_time) year = new Date(r._raw_time).getFullYear();
            if (!year || isNaN(year)) year = new Date().getFullYear();
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
        <div class="cocast-summary-result">${summaryHtml}</div>
        <div class="cocast-control-panel">
            <div class="cocast-control-flex">
                <div><div class="cocast-result-title">🎭 查询到 ${results.length} 场同台演出</div></div>
                <div class="cocast-filters">
                    <label class="cocast-filter-label"><input type="checkbox" data-col="index" ${col.index ? 'checked' : ''}> 序号</label>
                    <label class="cocast-filter-label"><input type="checkbox" data-col="others" ${col.others ? 'checked' : ''}> 其TA卡司</label>
                    <label class="cocast-filter-label"><input type="checkbox" data-col="location" ${col.location ? 'checked' : ''}> 剧场</label>
                    <span class="cocast-filter-separator">|</span>
                    <select id="cocast-year-filter" class="cocast-year-select"><option value="">全部年份</option>${years.map(y => `<option value="${y}" ${selectedYear == y ? 'selected' : ''}>${y}年</option>`).join('')}</select>
                    <button id="cocast-sort-btn" class="cocast-sort-btn">日期 ${sortAsc ? '↓' : '↑'}</button>
                </div>
            </div>
        </div>
        <div class="data-table-container">
            <table class="data-table">
                <thead><tr>${col.index ? '<th width="40">#</th>' : ''}<th width="80">日期/时间</th><th width="40">城市</th><th>剧目</th><th>角色</th>${col.location ? '<th>剧场</th>' : ''}${col.others ? '<th>其TA卡司</th>' : ''}</tr></thead>
                <tbody>
    `;

    // ... render rows ...
    const uniqueYears = [...new Set(filtered.map(r => r.year))].filter(y => !isNaN(y));
    const showYearInTable = uniqueYears.length > 1;
    let lastYear = null, lastDate = null;

    filtered.forEach((r, idx) => {
        const currentYear = r.year;
        const parts = r.date ? r.date.trim().split(/\s+/) : [];
        const datePart = parts[0] || '';
        const timePart = parts[1] || '';

        let yearShow = true, dateShow = true;
        if (currentYear === lastYear) { yearShow = false; if (datePart === lastDate) dateShow = false; }
        if (!showYearInTable) yearShow = false;

        const yearHTML = showYearInTable ? `<span class="dt-year" style="${yearShow ? '' : 'visibility:hidden'}">${currentYear}年</span>` : '';
        const dateHTML = `<span class="dt-date" style="${dateShow ? '' : 'visibility:hidden'}">${datePart}</span>`;
        const timeHTML = `<span class="dt-time">${timePart}</span>`;
        const dateDisplay = `<div class="dt-container">${yearHTML}${dateHTML}${timeHTML}</div>`;

        lastYear = currentYear;
        lastDate = datePart;

        const titleDisplay = (!isSaoju && r.event_id) ? `<span class="jump-detail" data-id="${r.event_id}" data-sess="${r.session_id || ''}" style="cursor:pointer; color:var(--primary-color); font-weight:600; text-decoration:underline;">${escapeHtml(r.title)}</span>` : escapeHtml(r.title);

        const othersContent = (r.others && r.others.length > 0)
            ? `<div class="cast-list-layout">${r.others.map(c => {
                let text = escapeHtml(c);
                let title = escapeHtml(c);
                if (c.includes(':')) {
                    const parts = c.split(':');
                    const role = parts[0];
                    const name = parts[1];
                    text = `${escapeHtml(name)}<span class="cast-role-tiny">${escapeHtml(role)}</span>`;
                    title = `${escapeHtml(name)} 饰 ${escapeHtml(role)}`;
                }
                return `<div class="cast-item" title="${title}">${text}</div>`;
            }).join('')}</div>`
            : '-';

        html += `<tr>${col.index ? `<td data-label="#">${idx + 1}</td>` : ''}<td class="time-cell" data-label="日期/时间">${dateDisplay}</td><td class="city-cell" data-label="城市">${escapeHtml(r.city || '-')}</td><td class="title-cell" data-label="剧目">${titleDisplay}</td><td data-label="角色">${escapeHtml(r.role || '-')}</td>${col.location ? `<td data-label="剧场">${escapeHtml(r.location || '-')}</td>` : ''}${col.others ? `<td class="cast-cell" data-label="其TA卡司">${othersContent}</td>` : ''}</tr>`;
    });

    html += '</tbody></table></div>';
    container.innerHTML = html;

    // Bind internal events
    container.querySelectorAll('input[type=checkbox]').forEach(cb => {
        cb.addEventListener('change', (e) => { state.coCastCols[e.target.dataset.col] = e.target.checked; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource, state.lastCoCastCasts); });
    });
    document.getElementById('cocast-year-filter').addEventListener('change', (e) => { state.coCastYearFilter = e.target.value; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource, state.lastCoCastCasts); });
    document.getElementById('cocast-sort-btn').addEventListener('click', () => { state.coCastDateSort = !state.coCastDateSort; renderCoCastResults(state.lastCoCastResults, state.lastCoCastSource, state.lastCoCastCasts); });
    container.querySelectorAll('.jump-detail').forEach(span => {
        span.addEventListener('click', () => jumpToDetail(span.dataset.id, span.dataset.sess));
    });
}

function calculateCoCastStats(results, casts) {
    if (!results || results.length === 0) return '';
    const total = results.length;

    // Dynamic Header Text
    let headerText = '';
    if (casts.length === 1) {
        headerText = `${escapeHtml(casts[0])} 收录演出共 <span style="color:var(--primary-color); font-size:1.3rem; margin:0 4px">${total}</span> 场`;
    } else {
        headerText = `${escapeHtml(casts.join(' & '))} 同台共 <span style="color:var(--primary-color); font-size:1.3rem; margin:0 4px">${total}</span> 场`;
    }

    const groupMap = {};
    results.forEach(r => {
        const title = r.title || '未知剧目';
        const role = r.role || '未知角色';
        if (!groupMap[title]) groupMap[title] = { total: 0, roles: {} };
        groupMap[title].total++;
        groupMap[title].roles[role] = (groupMap[title].roles[role] || 0) + 1;
    });

    let html = `
        <div class="cocast-summary-minimal">
            <div class="cocast-display-header">
                ${headerText}
            </div>
            <div class="cocast-stats-container">`;

    Object.keys(groupMap).sort((a, b) => groupMap[b].total - groupMap[a].total).forEach(title => {
        const group = groupMap[title];
        html += `<div class="cocast-stat-card">
                    <div class="cocast-stat-card-header">
                        <span class="cocast-show-title">《${escapeHtml(title)}》</span>
                        <span class="cocast-show-count">${group.total}场</span>
                    </div>`;
        Object.keys(group.roles).sort((a, b) => group.roles[b] - group.roles[a]).forEach(role => {
            html += `<div class="cocast-role-row">
                        <span>${escapeHtml(role)}</span>
                        <span class="cocast-role-count">${group.roles[role]}场</span>
                    </div>`;
        });
        html += `</div>`;
    });
    html += `</div>
             <div class="cocast-footer">
                Generated by MusicalBot
             </div>
             </div>`;
    return html;
}

// --- Date Search ---

export async function doDateSearch() {
    const dateInput = document.getElementById('date-input');
    const resultsContainer = document.getElementById('date-results');
    const selectedDate = dateInput.value;

    if (!selectedDate) { resultsContainer.innerHTML = '<div style="padding:40px;text-align:center;color:#999">请选择日期</div>'; return; }

    if (!router.getCurrentPath().includes(`d=${selectedDate}`)) {
        window.history.replaceState(null, '', `#/date?d=${selectedDate}`);
    }

    resultsContainer.innerHTML = '<div style="padding:40px;text-align:center">正在查询中...</div>';

    try {
        const data = await api.fetchDateEvents(selectedDate);
        if (data.error) throw new Error(data.error);
        renderDateResults(data.results, selectedDate);
    } catch (e) {
        resultsContainer.innerHTML = `<div style="color:red;padding:20px;text-align:center">❌ 查询失败: ${e.message}</div>`;
    }
}

function renderDateResults(tickets, date) {
    const container = document.getElementById('date-results');
    if (!tickets || tickets.length === 0) { container.innerHTML = `<div style="padding:40px;text-align:center;color:#999">📅 ${date}<br><br>😴 该日期暂无学生票演出安排</div>`; return; }

    const allTickets = tickets.sort((a, b) => new Date(a.session_time) - new Date(b.session_time));
    const cities = [...new Set(allTickets.map(t => t.city).filter(c => c))].sort();
    const times = [...new Set(allTickets.map(t => { if (!t.session_time) return null; const d = new Date(t.session_time); return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); }).filter(v => v))].sort();

    state.currentDateTickets = allTickets;
    state.currentDate = date;

    let html = `
        <div style="margin-bottom:15px;padding:10px;background:#f0f7ff;border-radius:8px;border-left:4px solid var(--primary-color)"><div style="font-size:1.1em;font-weight:600;color:var(--primary-color);margin-bottom:5px">📅 ${date} - 查询到 ${tickets.length} 个场次</div></div>
        <div style="background:#f8f9fa; padding:15px 20px; border-radius:8px; margin-bottom:15px; border:1px solid #e0e0e0;">
            <div style="display:flex; flex-wrap:wrap; gap:20px; align-items:center;">
                <label style="display:flex; align-items:center; gap:6px; cursor:pointer; font-size:0.9em;"><input type="checkbox" id="date-filter-available"><span>只看有票</span></label>
                <div style="display:flex; align-items:center; gap:8px;"><span style="font-size:0.9em; font-weight:600; color:#666;">城市：</span><select id="date-filter-city" style="padding:6px 12px; border:1px solid #ddd; border-radius:6px; font-size:0.85em;"><option value="">全部</option>${cities.map(city => `<option value="${city}">${city}</option>`).join('')}</select></div>
                <div style="display:flex; align-items:center; gap:8px;"><span style="font-size:0.9em; font-weight:600; color:#666;">时间：</span><select id="date-filter-time" style="padding:6px 12px; border:1px solid #ddd; border-radius:6px; font-size:0.85em;"><option value="">全部</option>${times.map(time => `<option value="${time}">${time}</option>`).join('')}</select></div>
                <div style="display:flex; align-items:center; gap:8px;"><span style="font-size:0.9em; font-weight:600; color:#666;">搜索：</span><input type="text" id="date-filter-search" placeholder="剧目或演员名" style="padding:6px 12px; border:1px solid #ddd; border-radius:6px; font-size:0.85em; width:150px;"></div>
            </div>
        </div>
        <div id="date-table-container"><table class="data-table"><thead><tr><th width="40">序号</th><th width="60">时间</th><th width="60">城市</th><th>剧目</th><th width="80">余票</th><th width="180">卡司</th><th width="120">价格</th></tr></thead><tbody id="date-table-body"></tbody></table></div>
    `;

    container.innerHTML = html;
    document.getElementById('date-filter-available').addEventListener('change', () => applyDateFilters(date));
    document.getElementById('date-filter-city').addEventListener('change', () => applyDateFilters(date));
    document.getElementById('date-filter-time').addEventListener('change', () => applyDateFilters(date));
    document.getElementById('date-filter-search').addEventListener('input', () => applyDateFilters(date));

    renderDateTableRows(allTickets);
}

// --- User Profile ---

export async function initUserTab() {
    const container = document.getElementById('user-profile-container');
    container.innerHTML = '<div class="loading-spinner"></div>';

    try {
        const user = await api.checkLogin();
        if (!user || !user.logged_in) {
            renderLoginPrompt(container);
        } else {
            // Fetch comprehensive settings
            const settings = await api.fetchUserSettings();
            renderUserProfile(container, settings || user); // Fallback to auth user if settings fail?
        }
    } catch (e) {
        console.error("User init error:", e);
        renderLoginPrompt(container);
    }
}

function renderLoginPrompt(container) {
    container.innerHTML = `
        <div style="text-align:center; padding:40px 20px;">
            <div style="font-size:3rem; margin-bottom:20px;">🔒</div>
            <h3 style="margin:0 0 10px 0; color:var(--text-primary);">未登录</h3>
            <p style="color:var(--text-secondary); margin-bottom:30px;">请通过 QQ 机器人发送 <code>/web</code> 获取登录链接</p>
            <div style="padding:15px; background:#f5f5f5; border-radius:12px; display:inline-block; font-family:monospace; color:#666;">
                /web
            </div>
        </div>
    `;
}

async function renderUserProfile(container, user) {
    const mode = user.bot_interaction_mode || 'hybrid';

    const modeOptions = [
        {
            value: 'hybrid',
            label: '混合模式 (推荐)',
            desc: '显示精简列表 (Top 5) + 详情链接。平衡信息量与屏占比。',
            icon: 'view_agenda'
        },
        {
            value: 'lite',
            label: '极简模式',
            desc: '仅显示统计信息 + 详情链接。最少打扰。',
            icon: 'link'
        },
        {
            value: 'legacy',
            label: '传统模式',
            desc: '显示完整长列表文本。适合习惯旧版交互的用户。',
            icon: 'article'
        }
    ];

    container.innerHTML = `
        <div class="user-card" style="background:#fff; border-radius:16px; box-shadow:0 4px 20px rgba(0,0,0,0.05); overflow:hidden;">
            <div style="padding:30px 20px; text-align:center; border-bottom:1px solid #f0f0f0; background:linear-gradient(to bottom, #fff, #fafafa);">
                <div style="width:80px; height:80px; background:#eee; border-radius:50%; margin:0 auto 15px; display:flex; align-items:center; justify-content:center; font-size:2rem; overflow:hidden;">
                    ${user.avatar_url ? `<img src="${escapeHtml(user.avatar_url)}" style="width:100%;height:100%;object-fit:cover;">` : (user.nickname ? user.nickname[0].toUpperCase() : 'U')}
                </div>
                <h2 style="margin:0; font-size:1.4rem; font-weight:700;">${escapeHtml(user.nickname || 'Bot User')}</h2>
                <div style="margin-top:5px; color:#999; font-size:0.9rem;">ID: ${escapeHtml(user.user_id)}</div>
            </div>
            
            <div style="padding:20px;">
                <h3 style="font-size:1.1rem; margin:0 0 15px 0; display:flex; align-items:center;">
                    <i class="material-icons" style="margin-right:8px; color:var(--primary-color);">smart_toy</i> 
                    Bot 交互设置
                </h3>
                
                <div class="mode-selector" style="display:flex; flex-direction:column; gap:12px;">
                    ${modeOptions.map(opt => `
                        <label class="mode-option ${mode === opt.value ? 'selected' : ''}" style="display:flex; align-items:flex-start; padding:15px; border:2px solid transparent; border-radius:12px; background:#f8f9fa; cursor:pointer; transition:all 0.2s;">
                            <input type="radio" name="bot_mode" value="${opt.value}" ${mode === opt.value ? 'checked' : ''} style="display:none;">
                            <div style="margin-right:15px; margin-top:2px; color:${mode === opt.value ? 'var(--primary-color)' : '#bbb'};">
                                <i class="material-icons">${opt.icon}</i>
                            </div>
                            <div style="flex:1;">
                                <div style="font-weight:600; margin-bottom:4px; color:var(--text-primary);">${opt.label}</div>
                                <div style="font-size:0.85rem; color:var(--text-secondary); line-height:1.4;">${opt.desc}</div>
                            </div>
                            <div class="check-mark" style="width:20px; height:20px; border-radius:50%; border:2px solid ${mode === opt.value ? 'var(--primary-color)' : '#ddd'}; display:flex; align-items:center; justify-content:center;">
                                ${mode === opt.value ? `<div style="width:10px; height:10px; background:var(--primary-color); border-radius:50%;"></div>` : ''}
                            </div>
                        </label>
                    `).join('')}
                </div>
                
                <div id="save-status" style="margin-top:15px; text-align:center; min-height:20px; font-size:0.9rem;"></div>
            </div>

            <div style="padding:20px; border-top:1px solid #f0f0f0;">
                <button onclick="router.navigate('/user/subscriptions')" style="width:100%; padding:15px; border:none; background:#f0f7ff; color:var(--primary-color); font-weight:600; border-radius:12px; display:flex; align-items:center; justify-content:center; gap:8px; margin-bottom:10px;">
                    <i class="material-icons">notifications</i> 管理订阅
                </button>
                <button onclick="doLogout()" style="width:100%; padding:15px; border:none; background:#fff1f0; color:#ff4d4f; font-weight:600; border-radius:12px; display:flex; align-items:center; justify-content:center; gap:8px;">
                    <i class="material-icons">logout</i> 退出登录
                </button>
            </div>
        </div>
    `;

    // Bind events
    container.querySelectorAll('input[name="bot_mode"]').forEach(input => {
        input.addEventListener('change', async (e) => {
            const newMode = e.target.value;
            const statusEl = document.getElementById('save-status');

            // Update UI immediately for responsiveness
            container.querySelectorAll('.mode-option').forEach(el => {
                const isSelected = el.querySelector('input').value === newMode;
                el.classList.toggle('selected', isSelected);
                el.style.borderColor = isSelected ? 'var(--primary-color)' : 'transparent';
                el.style.background = isSelected ? 'rgba(99, 126, 96, 0.05)' : '#f8f9fa';

                const icon = el.children[1];
                icon.style.color = isSelected ? 'var(--primary-color)' : '#bbb';

                const check = el.children[3];
                check.style.borderColor = isSelected ? 'var(--primary-color)' : '#ddd';
                check.innerHTML = isSelected ? `<div style="width:10px; height:10px; background:var(--primary-color); border-radius:50%;"></div>` : '';
            });

            try {
                statusEl.innerHTML = '<span style="color:#666;">⏳ 正在保存...</span>';
                await api.updateUserSettings({ bot_interaction_mode: newMode });
                statusEl.innerHTML = '<span style="color:var(--primary-color);">✅ 设置已保存</span>';
                setTimeout(() => statusEl.innerHTML = '', 2000);
            } catch (err) {
                statusEl.innerHTML = '<span style="color:red;">❌ 保存失败，请重试</span>';
                console.error(err);
                // Revert UI? Maybe not necessary for simple toggle, just show error.
            }
        });
    });
}

};

// Export logout function
export const doLogout = window.doLogout = async () => {
    if (confirm('确定要退出登录吗？')) {
        await api.logout();
        window.location.reload();
    }
};

function renderDateTableRows(tickets) {
    const tbody = document.getElementById('date-table-body');
    if (!tbody) return;

    const cityCounts = {};
    tickets.forEach(t => { if (t.city) cityCounts[t.city] = (cityCounts[t.city] || 0) + 1; });

    const displayTickets = [...tickets].sort((a, b) => {
        const timeA = a.session_time ? new Date(a.session_time).getTime() : 0;
        const timeB = b.session_time ? new Date(b.session_time).getTime() : 0;
        if (timeA !== timeB) return timeA - timeB;

        const countA = cityCounts[a.city] || 0;
        const countB = cityCounts[b.city] || 0;
        if (countA !== countB) return countB - countA;
        if ((a.city || '') !== (b.city || '')) return (a.city || '').localeCompare(b.city || '', 'zh');
        return getNormalizedTitle(a).localeCompare(getNormalizedTitle(b), 'zh') || getPrice(a.price) - getPrice(b.price);
    });

    let html = '';
    let lastGroupKey = '';
    displayTickets.forEach((t, index) => {
        const showTitle = getNormalizedTitle(t);
        const timeKey = t.session_time ? new Date(t.session_time).getTime() : 0;
        const currentGroupKey = `${timeKey}_${t.city || ''}_${showTitle}`;
        const isSameGroup = currentGroupKey === lastGroupKey;

        let timeStr = '待定';
        if (t.session_time) {
            const date = new Date(t.session_time);
            timeStr = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
        }

        const castStr = t.cast && t.cast.length > 0 ? t.cast.map(c => c.name).join(' | ') : '-';
        const isSoldOut = (t.stock !== undefined ? t.stock : 0) === 0 || t.status === 'sold_out';
        const groupClass = isSameGroup ? 'group-continue' : 'group-start';

        let priceStr = t.price_label && t.price_label !== `¥${t.price}` ? t.price_label : (t.original_price && t.original_price !== t.price ? `${t.price}（原价${t.original_price}）` : `¥${t.price}`);

        html += `<tr class="${isSoldOut ? 'sold-out' : ''} ${groupClass}" data-session-id="${t.session_id || timeKey}"><td style="text-align:center; color:#999; font-size:0.85em;">${index + 1}</td>`;
        if (isSameGroup) {
            html += `<td class="time-cell"></td><td class="city-cell"></td><td class="title-cell"></td><td class="stock-cell">${escapeHtml(t.stock)}/${escapeHtml(t.total_ticket)}</td><td class="cast-cell"></td>`;
        } else {
            html += `<td class="time-cell">${escapeHtml(timeStr)}</td><td class="city-cell">${escapeHtml(t.city || '-')}</td><td class="title-cell clickable-title" style="cursor:pointer; color:var(--primary-color); font-weight:600;" data-event-id="${t.event_id || t.id}" data-session-id="${t.session_id || ''}">${escapeHtml(showTitle)}</td><td class="stock-cell">${escapeHtml(t.stock)}/${escapeHtml(t.total_ticket)}</td><td class="cast-cell">${escapeHtml(castStr)}</td>`;
        }
        html += `<td class="price-cell" style="color:#e67e22; font-weight:bold;">${escapeHtml(priceStr)}</td></tr>`;
        lastGroupKey = currentGroupKey;
    });

    tbody.innerHTML = html || '<tr><td colspan="6" style="text-align:center;padding:40px;color:#999;">没有符合条件的场次</td></tr>';

    // Add Listeners
    tbody.querySelectorAll('.clickable-title').forEach(el => {
        el.addEventListener('click', () => jumpToDetail(el.dataset.eventId, el.dataset.sessionId));
    });
}

export function applyDateFilters(date) {
    const allTickets = state.currentDateTickets;
    if (!allTickets) return;

    const onlyAvailable = document.getElementById('date-filter-available')?.checked || false;
    const selectedCity = document.getElementById('date-filter-city')?.value || '';
    const selectedTime = document.getElementById('date-filter-time')?.value || '';
    const searchText = document.getElementById('date-filter-search')?.value.trim().toLowerCase() || '';

    let filtered = allTickets.filter(t => {
        if (onlyAvailable && (t.stock === 0 || t.status === 'sold_out')) return false;
        if (selectedCity && t.city !== selectedCity) return false;
        if (selectedTime) {
            if (!t.session_time) return false;
            const d = new Date(t.session_time);
            if (`${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}` !== selectedTime) return false;
        }
        if (searchText) {
            const titleLower = t.title ? t.title.toLowerCase() : '';
            const castNames = t.cast ? t.cast.map(c => c.name.toLowerCase()).join(' ') : '';
            if (!titleLower.includes(searchText) && !castNames.includes(searchText)) return false;
        }
        return true;
    });

    renderDateTableRows(filtered);
}

export function jumpToDetail(eventId, sessionId) {
    router.navigate('/detail/' + eventId);
    setTimeout(() => highlightSession(sessionId), 500);
}

function highlightSession(sessionId) {
    if (!sessionId) return;
    const rows = document.querySelectorAll('#detail-table-body tr');
    let targetRow = null;
    rows.forEach(row => { if (row.getAttribute('data-session-id') === String(sessionId)) targetRow = row; });

    if (targetRow) {
        targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
        targetRow.classList.add('highlight-row');
        setTimeout(() => targetRow.classList.remove('highlight-row'), 2500);
    }
}

export function setCoCastRange(type) {
    const startInput = document.getElementById('cocast-start-date');
    if (!startInput) return;
    if (type === 'earliest') startInput.value = '2023-01-01';
    else if (type === 'today') startInput.value = formatDateStr(new Date());
}

export function setQuickDate(type) {
    const input = document.getElementById('date-input');
    const now = new Date();
    let target = new Date();

    if (type === 'today') target = now;
    else if (type === 'weekend') target.setDate(now.getDate() + (now.getDay() === 0 ? 0 : 6 - now.getDay()));
    else if (type === 'next_weekend') target.setDate(now.getDate() + (now.getDay() === 0 ? 6 : 6 - now.getDay()) + 7);

    input.value = formatDateStr(target);
    doDateSearch();
}

// --- User Management ---

export async function initUserTab() {
    const container = document.getElementById('user-profile-container');
    if (!container) return;

    container.innerHTML = '<div class="loading-spinner"></div><div style="text-align:center;margin-top:10px;color:#888;">正在加载账户信息...</div>';

    try {
        const res = await api.checkLogin();
        if (res.authenticated && res.user) {
            state.user = res.user;
            renderUserTab(res.user);
        } else {
            state.user = null;
            renderLoginPrompt();
        }
    } catch (e) {
        console.error("Auth check failed:", e);
        container.innerHTML = `<div style="text-align:center;padding:40px;color:red;">
            <i class="material-icons" style="font-size:48px;margin-bottom:10px;">error_outline</i><br>
            加载失败，请检查网络
        </div>`;
    }
}

function renderUserTab(user) {
    const container = document.getElementById('user-profile-container');

    const avatarUrl = user.avatar_url || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(user.nickname || 'User') + '&background=random';

    let html = `
        <div class="user-card" style="background:#fff; border-radius:18px; padding:30px 20px; box-shadow:0 4px 20px rgba(0,0,0,0.05); text-align:center; margin-bottom:20px;">
            <div class="user-avatar" style="width:80px; height:80px; border-radius:50%; overflow:hidden; margin:0 auto 15px; border:3px solid #f0f0f0;">
                <img src="${avatarUrl}" style="width:100%; height:100%; object-fit:cover;" alt="Avatar">
            </div>
            <h2 style="margin:0 0 5px; color:#333;">${escapeHtml(user.nickname || '未命名用户')}</h2>
            <div style="color:#888; font-size:0.9rem;">QQ: ${escapeHtml(user.user_id)}</div>
            
            <div style="margin-top:20px; display:flex; justify-content:center; gap:15px;">
                <div style="background:#f9f9f9; padding:10px 20px; border-radius:10px;">
                    <div style="font-weight:700; color:var(--primary-color); font-size:1.2rem;">${user.trust_score || 0}</div>
                    <div style="font-size:0.8rem; color:#666;">信誉分</div>
                </div>
            </div>
        </div>

        <div class="action-list" style="display:flex; flex-direction:column; gap:15px;">
            <button class="action-btn" style="background:#fff; border:1px solid #eee; padding:15px; border-radius:12px; display:flex; align-items:center; justify-content:space-between; font-size:1rem; cursor:pointer;" onclick="router.navigate('/user/subscriptions')">
                <div style="display:flex; align-items:center; gap:10px;">
                    <div style="background:#e3f2fd; color:#1976d2; padding:8px; border-radius:8px;"><i class="material-icons">notifications</i></div>
                    <span>我的订阅管理</span>
                </div>
                <i class="material-icons" style="color:#ccc;">chevron_right</i>
            </button>
            
            <button class="action-btn" onclick="doLogout()" style="background:#fff; border:1px solid #fee; color:#d32f2f; padding:15px; border-radius:12px; font-size:1rem; cursor:pointer; margin-top:10px;">
                退出登录
            </button>
        </div>
    `;

    container.innerHTML = html;
}

function renderLoginPrompt() {
    const container = document.getElementById('user-profile-container');
    container.innerHTML = `
        <div style="text-align:center; padding:40px 20px;">
            <i class="material-icons" style="font-size:64px; color:#ddd; margin-bottom:20px;">account_circle</i>
            <h3 style="margin:0 0 10px; color:#333;">请先登录</h3>
            <p style="color:#666; line-height:1.6;">
                为了保护您的隐私，Web 端账号需与 QQ 绑定。<br>
                请向机器人发送指令：
            </p>
            <div style="background:#f0f0f0; display:inline-block; padding:10px 20px; border-radius:8px; margin:15px 0; font-family:monospace; font-size:1.2rem; letter-spacing:1px; color:#333;">
                /web
            </div>
            <p style="color:#666; font-size:0.9rem;">
                点击机器人回复的链接，即可自动登录。
            </p>
        </div>
    `;
}

export async function doLogout() {
    if (!confirm("确定要退出登录吗？")) return;

    try {
        await api.logout();
        state.user = null;
        initUserTab(); // Re-init to show login prompt
    } catch (e) {
        alert("登出失败: " + e.message);
    }
}

// --- Subscription Management ---

export async function initSubscriptionManagement() {
    const container = document.getElementById('subscriptions-container');
    if (!container) return;

    container.innerHTML = '<div class="loading-spinner"></div>';

    try {
        const subs = await api.fetchSubscriptions();
        renderSubscriptionList(subs);
    } catch (e) {
        console.error("Failed to load subscriptions:", e);
        container.innerHTML = `<div style="text-align:center; padding:40px; color:#999;">
            <i class="material-icons" style="font-size:48px; margin-bottom:10px;">error_outline</i>
            <p>获取订阅列表失败，请检查登录状态。</p>
            <button class="secondary-btn" onclick="initSubscriptionManagement()" style="margin-top:10px;">重试</button>
        </div>`;
    }

    initSubscriptionAutocomplete();
}

function renderSubscriptionList(subs) {
    const container = document.getElementById('subscriptions-container');
    if (subs.length === 0) {
        container.innerHTML = `
            <div style="text-align:center; padding:60px 20px; color:#999; background:#fff; border-radius:24px; margin-top:20px;">
                <i class="material-icons" style="font-size:64px; margin-bottom:15px; color:#eee;">notifications_none</i>
                <p style="margin:0;">您还没有任何订阅</p>
                <p style="font-size:0.9rem; margin-top:5px;">订阅后，当有新票务动态时我们会通知您</p>
                <button class="primary-btn" onclick="showAddSubModal()" style="margin-top:20px; padding:10px 20px; border-radius:20px;">立即添加</button>
            </div>
        `;
        return;
    }

    const html = subs.map(sub => renderSubscriptionItem(sub)).join('');
    container.innerHTML = `<div style="display:flex; flex-direction:column; gap:15px; margin-top:20px;">${html}</div>`;
}

function renderSubscriptionItem(sub) {
    const target = sub.targets[0] || {};
    const options = sub.options || {};

    const icon = target.kind === 'play' ? 'theater_comedy' : 'person';
    const typeLabel = target.kind === 'play' ? '剧目' : '演员';

    const freqLabels = {
        'realtime': '实时',
        'hourly': '每小时',
        'daily': '每日'
    };

    return `
        <div class="sub-item" style="background:#fff; border-radius:18px; padding:20px; box-shadow:0 2px 10px rgba(0,0,0,0.03); display:flex; align-items:center; gap:15px;">
            <div style="background:#f5f5f5; color:#666; width:44px; height:44px; border-radius:12px; display:flex; align-items:center; justify-content:center;">
                <i class="material-icons">${icon}</i>
            </div>
            
            <div style="flex:1; overflow:hidden;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:0.8rem; color:var(--primary-color); background:rgba(108, 92, 231, 0.1); padding:2px 6px; border-radius:4px;">${typeLabel}</span>
                    <strong style="font-size:1.1rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(target.name || '未知')}</strong>
                </div>
                <div style="margin-top:5px; font-size:0.85rem; color:#888; display:flex; align-items:center; gap:10px;">
                    <span><i class="material-icons" style="font-size:0.9rem; vertical-align:text-bottom;">public</i> ${escapeHtml(target.city_filter || '全国')}</span>
                    <span><i class="material-icons" style="font-size:0.9rem; vertical-align:text-bottom;">history</i> ${freqLabels[options.freq] || '实时'}</span>
                </div>
            </div>
            
            <div style="display:flex; gap:10px;">
                <button class="icon-btn" onclick="handleDeleteSubscription(${sub.id})" style="color:#ff7675; background:rgba(255, 118, 117, 0.1); border:none; width:36px; height:36px; border-radius:10px; cursor:pointer;">
                    <i class="material-icons" style="font-size:20px;">delete_outline</i>
                </button>
            </div>
        </div>
    `;
}

export function showAddSubModal() {
    const modal = document.getElementById('add-sub-modal');
    if (modal) {
        modal.classList.add('active');
        // Reset form
        document.getElementById('sub-target-input').value = '';
        document.getElementById('sub-target-id').value = '';
        document.getElementById('sub-target-name').value = '';
        document.getElementById('sub-city-input').value = '';
        selectSubType('play');
    }
}

export function hideAddSubModal() {
    const modal = document.getElementById('add-sub-modal');
    if (modal) modal.classList.remove('active');
}

export function selectSubType(type) {
    const playOpt = document.getElementById('type-opt-play');
    const actorOpt = document.getElementById('type-opt-actor');
    const label = document.getElementById('target-label');
    const input = document.getElementById('sub-target-input');
    const typeInput = document.getElementById('selected-sub-type');

    typeInput.value = type;

    if (type === 'play') {
        playOpt.style.borderColor = 'var(--primary-color)';
        playOpt.querySelector('i').style.color = 'var(--primary-color)';
        actorOpt.style.borderColor = '#eee';
        actorOpt.querySelector('i').style.color = '#666';
        label.innerText = '剧目名称';
        input.placeholder = '输入剧名并选择...';
    } else {
        actorOpt.style.borderColor = 'var(--primary-color)';
        actorOpt.querySelector('i').style.color = 'var(--primary-color)';
        playOpt.style.borderColor = '#eee';
        playOpt.querySelector('i').style.color = '#666';
        label.innerText = '演员姓名';
        input.placeholder = '输入演员名并选择...';
    }

    // Clear autocomplete
    document.getElementById('sub-autocomplete-results').style.display = 'none';
    input.value = '';
    document.getElementById('sub-target-id').value = '';
    document.getElementById('sub-target-name').value = '';
}

export async function doAddSubscription() {
    const type = document.getElementById('selected-sub-type').value;
    const targetId = document.getElementById('sub-target-id').value;
    const targetName = document.getElementById('sub-target-name').value || document.getElementById('sub-target-input').value;
    const city = document.getElementById('sub-city-input').value;
    const freq = document.getElementById('sub-freq-select').value;

    if (!targetName) {
        alert("请输入订阅目标名称");
        return;
    }

    const data = {
        targets: [{
            kind: type,
            target_id: targetId || null,
            name: targetName,
            city_filter: city || null
        }],
        options: {
            freq: freq
        }
    };

    try {
        await api.createSubscription(data);
        hideAddSubModal();
        initSubscriptionManagement(); // Refresh
        alert("订阅成功！");
    } catch (e) {
        alert("订阅失败: " + e.message);
    }
}

export async function handleDeleteSubscription(id) {
    if (!confirm("确定要删除这项订阅吗？")) return;

    try {
        await api.deleteSubscription(id);
        initSubscriptionManagement(); // Refresh
    } catch (e) {
        alert("删除失败: " + e.message);
    }
}

function initSubscriptionAutocomplete() {
    const input = document.getElementById('sub-target-input');
    const results = document.getElementById('sub-autocomplete-results');
    const targetIdInput = document.getElementById('sub-target-id');
    const targetNameInput = document.getElementById('sub-target-name');

    if (!input) return;

    input.addEventListener('input', () => {
        const type = document.getElementById('selected-sub-type').value;
        const val = input.value.trim().toLowerCase();

        if (!val) {
            results.style.display = 'none';
            return;
        }

        let matches = [];
        if (type === 'play') {
            matches = state.allEvents.filter(e =>
                e.title.toLowerCase().includes(val)
            ).slice(0, 5);
        } else {
            matches = state.artists.filter(a =>
                a.name.toLowerCase().includes(val) || (a.pinyin && a.pinyin.includes(val))
            ).slice(0, 5);
        }

        if (matches.length > 0) {
            results.innerHTML = matches.map(m => `
                <div class="suggestion-item" onclick="selectSubSuggestion('${escapeHtml(m.title || m.name)}', '${m.id}')" style="padding:10px 15px; cursor:pointer; border-bottom:1px solid #f9f9f9;">
                    ${escapeHtml(m.title || m.name)}
                </div>
            `).join('');
            results.style.display = 'block';
        } else {
            results.style.display = 'none';
        }
    });
}

window.selectSubSuggestion = (name, id) => {
    document.getElementById('sub-target-input').value = name;
    document.getElementById('sub-target-id').value = id;
    document.getElementById('sub-target-name').value = name;
    document.getElementById('sub-autocomplete-results').style.display = 'none';
};
