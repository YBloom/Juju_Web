// Ticket Updates Dashboard Module
// 票务动态模块 - 聚合摘要行 + 可展开详情

import { api } from './api.js';

const EXPAND_THRESHOLD = 5; // 超过此数量直接跳转，否则可展开

// Initialize ticket updates dashboard
export async function initTicketUpdates() {
    const container = document.getElementById('ticket-updates-card');
    if (!container) return;

    // Bind toggle event
    const header = container.querySelector('.updates-header');
    if (header) {
        header.addEventListener('click', toggleUpdatesCard);
    }

    // Bind filter checkboxes
    const filterCheckboxes = container.querySelectorAll('.filter-type');
    filterCheckboxes.forEach(cb => {
        cb.addEventListener('change', () => fetchAndRenderUpdates());
    });

    // Bind show cast toggle
    const showCastToggle = document.getElementById('show-cast-toggle');
    if (showCastToggle) {
        showCastToggle.addEventListener('change', () => {
            document.querySelectorAll('.detail-cast').forEach(el => {
                el.style.display = showCastToggle.checked ? 'inline' : 'none';
            });
        });
    }

    await fetchAndRenderUpdates();
}

// Fetch and render
async function fetchAndRenderUpdates() {
    const checkedTypes = Array.from(document.querySelectorAll('.filter-type:checked'))
        .map(cb => cb.value);

    if (checkedTypes.length === 0) {
        document.getElementById('updates-list').innerHTML = '<div class="no-updates">请选择筛选类型</div>';
        return;
    }

    try {
        const types = checkedTypes.join(',');
        const data = await api.fetchRecentUpdates(100, types);
        renderSummaryList(data.results || []);
    } catch (error) {
        console.error('Failed to fetch ticket updates:', error);
        document.getElementById('updates-list').innerHTML = '<div class="no-updates">加载失败</div>';
    }
}

// Render aggregated summary list
function renderSummaryList(updates) {
    const container = document.getElementById('updates-list');
    const showCast = document.getElementById('show-cast-toggle')?.checked ?? false;

    // 直接使用API返回的真实数据
    let allUpdates = updates || [];

    const checkedTypes = Array.from(document.querySelectorAll('.filter-type:checked')).map(cb => cb.value);
    allUpdates = allUpdates.filter(u => checkedTypes.includes(u.change_type));

    if (allUpdates.length === 0) {
        container.innerHTML = '<div class="no-updates">暂无票务动态</div>';
        return;
    }

    // Grouping
    const groupMap = new Map();
    allUpdates.forEach(u => {
        const key = `${u.event_title}__${u.change_type}`;
        if (!groupMap.has(key)) {
            groupMap.set(key, {
                event_id: u.event_id,
                event_title: u.event_title,
                change_type: u.change_type,
                created_at: u.created_at,
                sessions: []
            });
        }
        groupMap.get(key).sessions.push(u);
    });

    const groups = Array.from(groupMap.values());
    groups.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));

    // Status config - 绿色系统一配色
    const statusLabels = {
        restock: '回流',
        new: '上新',
        back: '补票',
        pending: '开票'
    };

    // Sort sessions by date (ascending) - 修复日期顺序为从近到远
    group.sessions.sort((a, b) => {
        const tA = a.session_time ? new Date(a.session_time).getTime() : 0;
        const tB = b.session_time ? new Date(b.session_time).getTime() : 0;
        return tA - tB;
    });

    // Render
    const html = groups.map((group, idx) => {
        const label = statusLabels[group.change_type] || '更新';
        const timeAgo = formatTimeAgo(group.created_at);
        const count = group.sessions.length;

        // Date range
        const dates = group.sessions
            .map(s => s.session_time ? new Date(s.session_time) : null)
            .filter(d => d && !isNaN(d.getTime()));
        // Already sorted above

        let dateRangeStr = '';
        let spanDays = 0;

        if (dates.length === 1) {
            dateRangeStr = formatShortDate(dates[0]);
        } else if (dates.length > 1) {
            const minDate = dates[0];
            const maxDate = dates[dates.length - 1];
            spanDays = Math.ceil((maxDate - minDate) / (1000 * 60 * 60 * 24));
            dateRangeStr = `${formatShortDate(minDate)} ~ ${formatShortDate(maxDate)}`;
        }

        // Weight class
        let weightClass = 'weight-single';
        if (spanDays > 7) weightClass = 'weight-wide';
        else if (spanDays >= 3) weightClass = 'weight-normal';

        const countStr = count > 1 ? `${count}场` : '';
        const canExpand = true; // Always allow expand if we want to see details, or keep threshold
        // User wants to see list, so maybe just stick to threshold or allow all?
        // Let's keep logic but maybe threshold was 5?
        // Actually user wants to see the list sorted.

        const groupId = `group-${idx}`;

        // Detail rows (only if canExpand)
        let detailHtml = '';
        if (canExpand) {
            const detailRows = group.sessions.map(s => {
                const time = s.session_time ? formatSessionTime(s.session_time) : '-';
                const price = s.price ? `¥${s.price}` : '';
                const stock = s.stock !== null ? `余${s.stock}` : '';
                // Ensure cast is array or parse it if string (just in case)
                let casts = s.cast_names || [];
                if (typeof casts === 'string') {
                    try { casts = JSON.parse(casts); } catch (e) { casts = [casts]; }
                }
                const cast = Array.isArray(casts) && casts.length ? casts.join(' ') : '';
                const isLow = s.stock !== null && s.stock <= 5;

                return `
                    <div class="detail-row" onclick="event.stopPropagation(); window.router?.navigate('/detail/${s.event_id || group.event_id}')">
                        <span class="detail-time">${time}</span>
                        <span class="detail-price">${price}</span>
                        <span class="detail-stock ${isLow ? 'low-stock' : ''}">${stock}</span>
                        <span class="detail-cast" style="display: ${showCast ? 'inline' : 'none'}">${cast}</span>
                    </div>
                `;
            }).join('');

            detailHtml = `<div class="detail-panel" id="${groupId}-detail" style="display:none;">${detailRows}</div>`;
        }

        // Click handler
        const clickAction = canExpand
            ? `toggleDetail('${groupId}')`
            : `window.router?.navigate('/detail/${group.event_id || ''}')`;

        return `
            <div class="update-summary-row ${weightClass}" data-type="${group.change_type}" onclick="${clickAction}">
                <span class="summary-badge">${label}</span>
                <span class="summary-title">《${group.event_title}》</span>
                <span class="summary-date-range">${dateRangeStr}</span>
                <span class="summary-count">${countStr}</span>
                <span class="summary-time">${timeAgo}</span>
                <span class="summary-arrow" id="${groupId}-arrow">${canExpand ? '▸' : '›'}</span>
            </div>
            ${detailHtml}
        `;
    }).join('');

    container.innerHTML = html || '<div class="no-updates">暂无票务动态</div>';

    // Expose toggle function
    window.toggleDetail = (groupId) => {
        const detail = document.getElementById(`${groupId}-detail`);
        const arrow = document.getElementById(`${groupId}-arrow`);
        if (detail) {
            const isHidden = detail.style.display === 'none';
            detail.style.display = isHidden ? 'block' : 'none';
            if (arrow) arrow.textContent = isHidden ? '▾' : '▸';
        }
    };
}

function formatShortDate(date) {
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${m}-${d}`;
}

function formatSessionTime(isoString) {
    try {
        const dt = new Date(isoString);
        const m = String(dt.getMonth() + 1).padStart(2, '0');
        const d = String(dt.getDate()).padStart(2, '0');
        const h = String(dt.getHours()).padStart(2, '0');
        const min = String(dt.getMinutes()).padStart(2, '0');
        const weekMap = ['日', '一', '二', '三', '四', '五', '六'];
        return `${m}-${d} 周${weekMap[dt.getDay()]} ${h}:${min}`;
    } catch { return '-'; }
}

function formatTimeAgo(dateString) {
    if (!dateString) return '';
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return '';
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);
        if (seconds < 60) return '刚刚';
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}分钟前`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}小时前`;
        return `${Math.floor(hours / 24)}天前`;
    } catch { return ''; }
}

function toggleUpdatesCard() {
    const body = document.getElementById('updates-body');
    const icon = document.querySelector('.updates-header .expand-icon');
    if (body && icon) {
        body.classList.toggle('collapsed');
        icon.textContent = body.classList.contains('collapsed') ? 'expand_more' : 'expand_less';
    }
}
