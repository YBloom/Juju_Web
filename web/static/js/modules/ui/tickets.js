
import { state } from '../state.js';
import { api } from '../api.js';
import { router } from '../router.js';
import { escapeHtml, debounce } from '../utils.js';
import { initTicketUpdates } from '../ticket_updates.js';

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

export function renderCityFilterOptions() {
    const cities = [...new Set(state.allEvents.map(e => e.city).filter(c => c))].sort();
    let container = document.getElementById('top-filter-container');

    if (!container) return;

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

    // Use event delegation instead of multiple listeners
    if (!container.dataset.delegated) {
        container.addEventListener('click', (e) => {
            const pill = e.target.closest('.filter-pill');
            if (pill) {
                state.cityFilter = pill.dataset.city || '';
                renderCityFilterOptions();
                applyFilters();
            }
        });
        container.dataset.delegated = 'true';
    }
}

// Internal applyFilters without debounce for programmatic calls
function _applyFiltersInternal() {
    const events = state.allEvents || [];
    if (events.length === 0) {
        renderEventTable([]);
        return;
    }

    const currentCity = state.cityFilter;
    const globalSearchInput = document.getElementById('global-search');
    const globalSearchValue = globalSearchInput ? globalSearchInput.value.trim().toLowerCase() : '';

    const localSearchInput = document.getElementById('local-show-search');
    const localSearchValue = localSearchInput ? localSearchInput.value.trim().toLowerCase() : '';

    const filtered = events.filter(e => {
        if (currentCity && e.city !== currentCity) return false;

        // Global Search Logic (Broad)
        if (globalSearchValue) {
            const title = e.title ? e.title.toLowerCase() : '';
            const city = e.city ? e.city.toLowerCase() : '';
            const location = e.location ? e.location.toLowerCase() : '';
            if (!title.includes(globalSearchValue) && !city.includes(globalSearchValue) && !location.includes(globalSearchValue)) {
                return false;
            }
        }

        // Local Search Logic (Specific to List)
        if (localSearchValue) {
            const title = e.title ? e.title.toLowerCase() : '';
            // Only search title for local search as requested ("search show name")
            if (!title.includes(localSearchValue)) {
                return false;
            }
        }

        return true;
    });

    renderEventTable(filtered);
}

// Exported version with debounce
export const applyFilters = debounce(_applyFiltersInternal, 250);

export function renderEventTable(events) {
    const container = document.getElementById('hlq-list-container');
    const countEl = document.getElementById('hlq-list-count');

    if (countEl) {
        countEl.innerText = `(${events ? events.length : 0}部)`;
    }

    if (!events || events.length === 0) {
        container.innerHTML = '<div style="padding:50px;text-align:center;color:#aaa">暂无符合条件的演出</div>';
        return;
    }

    let html = `<div class="event-list-main clean-list inset-mobile">`;

    events.forEach(e => {
        // Calculate End Date from actual ticket sessions
        let dateDisplay = e.schedule_range || '';

        // Try to find the latest session time from tickets
        if (e.tickets && e.tickets.length > 0) {
            const lastSession = e.tickets.reduce((max, t) => {
                const tDate = new Date(t.session_time);
                return tDate > max ? tDate : max;
            }, new Date(0));

            if (lastSession.getTime() > 0) {
                const y = lastSession.getFullYear();
                const m = String(lastSession.getMonth() + 1).padStart(2, '0');
                const d = String(lastSession.getDate()).padStart(2, '0');
                dateDisplay = `至${y}.${m}.${d}`;
            }
        } else if (e.schedule_range && e.schedule_range.includes('-')) {
            // Fallback to schedule_range parsing if tickets not available
            const parts = e.schedule_range.split('-');
            if (parts.length === 2) {
                let endDate = parts[1].trim();
                // 统一使用 "." 作为分隔符
                endDate = endDate.replace(/-/g, '.');
                // Ensure year 2026 if missing
                if (!endDate.startsWith('202')) {
                    endDate = `2026.${endDate}`;
                }
                dateDisplay = `至${endDate}`;
            }
        }

        let showTitle = e.title;
        if (e.title) {
            const titleMatch = e.title.match(/[《](.*?)[》]/);
            if (titleMatch && titleMatch[1]) showTitle = titleMatch[1];
        }

        // Determine city color class
        let cityClass = 'badge-default';
        const city = e.city || '';
        if (city.includes('上海')) cityClass = 'badge-city-sh';
        else if (city.includes('南京')) cityClass = 'badge-city-nj';
        else if (city.includes('北京')) cityClass = 'badge-city-bj';
        else if (city.includes('广州') || city.includes('深圳')) cityClass = 'badge-city-gz';
        else if (city.includes('杭州')) cityClass = 'badge-city-hz';

        html += `
        <div class="event-row clean-list-item grid-3-cols" data-event-id="${e.id}">
            <div class="col-city">
                <span class="event-city-badge badge ${cityClass}">${escapeHtml(city)}</span>
            </div>
            <div class="col-title">
                <span class="event-title-text">${escapeHtml(showTitle)}</span>
            </div>
            <div class="col-date">
                <span class="event-date-text">${escapeHtml(dateDisplay)}</span>
            </div>
        </div>`;
    });

    html += '</div>';
    container.innerHTML = html;

    // Use event delegation
    if (!container.dataset.delegated) {
        container.addEventListener('click', (e) => {
            const row = e.target.closest('.event-row');
            if (row && row.dataset.eventId) {
                router.navigate(`/detail/${row.dataset.eventId}`);
            }
        });
        container.dataset.delegated = 'true';
    }
}
