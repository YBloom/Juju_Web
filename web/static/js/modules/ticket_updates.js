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

    // Bind filter checkboxes (Chips Logic)
    const filterCheckboxes = container.querySelectorAll('.filter-type');
    filterCheckboxes.forEach(cb => {
        cb.addEventListener('change', (e) => {
            // Toggle active class on parent label
            if (e.target.checked) {
                e.target.parentElement.classList.add('active');
            } else {
                e.target.parentElement.classList.remove('active');
            }
            fetchAndRenderUpdates();
        });
    });

    // Bind show cast toggle
    const showCastToggle = document.getElementById('show-cast-toggle');
    if (showCastToggle) {
        showCastToggle.addEventListener('change', (e) => {
            // Toggle active class
            if (e.target.checked) {
                e.target.parentElement.classList.add('active');
            } else {
                e.target.parentElement.classList.remove('active');
            }

            // Toggle visibility in details
            document.querySelectorAll('.detail-cast').forEach(el => {
                el.style.display = showCastToggle.checked ? 'inline' : 'none';
            });
        });
    }

    // Bind hide expired toggle
    const hideExpiredToggle = document.getElementById('hide-expired-toggle');
    if (hideExpiredToggle) {
        hideExpiredToggle.addEventListener('change', (e) => {
            // Toggle active class
            if (e.target.checked) {
                e.target.parentElement.classList.add('active');
            } else {
                e.target.parentElement.classList.remove('active');
            }
            fetchAndRenderUpdates();
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
    const hideExpired = document.getElementById('hide-expired-toggle')?.checked ?? true;

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
    const now = new Date();

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

    let groups = Array.from(groupMap.values());

    // 为每个组计算是否包含未结束的场次
    groups.forEach(group => {
        // 对每个组内的sessions排序:按场次时间升序
        group.sessions.sort((a, b) => {
            const tA = a.session_time ? new Date(a.session_time).getTime() : 0;
            const tB = b.session_time ? new Date(b.session_time).getTime() : 0;
            return tA - tB;
        });

        // 检查该组是否有未结束的场次
        group.hasActiveSessions = group.sessions.some(s => {
            if (!s.session_time) return false;
            return new Date(s.session_time) >= now;
        });

        // 获取最早的场次时间(用于排序)
        const validTimes = group.sessions
            .map(s => s.session_time ? new Date(s.session_time) : null)
            .filter(d => d && !isNaN(d.getTime()));
        group.earliestSessionTime = validTimes.length > 0 ? validTimes[0] : null;
    });

    // 如果启用"隐藏已结束",过滤掉所有场次都已结束的组
    if (hideExpired) {
        groups = groups.filter(g => g.hasActiveSessions);
    }

    // 智能排序:
    // 1. 优先级1: 是否有active场次 (有active的在前)
    // 2. 优先级2: 最早的场次时间 (升序,最早的在前)
    // 3. 优先级3: 检测时间 (降序,最新检测的在前)
    groups.sort((a, b) => {
        // 第一优先级: active场次优先
        if (a.hasActiveSessions !== b.hasActiveSessions) {
            return b.hasActiveSessions ? 1 : -1;
        }

        // 第二优先级: 最早的场次时间(升序)
        if (a.earliestSessionTime && b.earliestSessionTime) {
            const timeDiff = a.earliestSessionTime.getTime() - b.earliestSessionTime.getTime();
            if (timeDiff !== 0) return timeDiff;
        } else if (a.earliestSessionTime) {
            return -1;  // a有时间,b没有,a在前
        } else if (b.earliestSessionTime) {
            return 1;   // b有时间,a没有,b在前
        }

        // 第三优先级: 检测时间(降序)
        return new Date(b.created_at || 0) - new Date(a.created_at || 0);
    });

    // Status config - 统一命名
    const statusLabels = {
        restock: '回流',
        new: '上新',
        back: '补票',
        pending: '开票'
    };

    // Render
    const html = groups.map((group, idx) => {
        // Sessions已在分组阶段按场次时间升序排序
        const label = statusLabels[group.change_type] || '更新';
        const badgeClass = `type-${group.change_type}`; // e.g., type-restock
        const timeAgo = formatTimeAgo(group.created_at);
        const count = group.sessions.length;

        // Check if ANY session in this group has cast info
        const hasCastInfo = group.sessions.some(s => {
            let c = s.cast_names;
            if (typeof c === 'string') {
                // Try parsing, if fails treat as string
                try {
                    const parsed = JSON.parse(c);
                    return Array.isArray(parsed) && parsed.length > 0;
                } catch (e) { return !!c; }
            }
            return Array.isArray(c) && c.length > 0;
        });
        const castIndicatorHtml = hasCastInfo
            ? '<i class="material-icons cast-indicator" title="包含卡司信息">group</i>'
            : '';

        // Date range
        const dates = group.sessions
            .map(s => s.session_time ? new Date(s.session_time) : null)
            .filter(d => d && !isNaN(d.getTime()));

        let dateRangeStr = '';
        let spanDays = 0;

        if (dates.length > 0) {
            if (dates.length === 1) {
                dateRangeStr = formatShortDate(dates[0]);
            } else {
                const minDate = dates[0];
                const maxDate = dates[dates.length - 1];
                spanDays = Math.ceil((maxDate - minDate) / (1000 * 60 * 60 * 24));
                dateRangeStr = `${formatShortDate(minDate)} ~ ${formatShortDate(maxDate)}`;
            }
        }

        const countStr = count > 1 ? `${count}场` : '';
        const canExpand = true;
        const groupId = `group-${idx}`;

        // Detail rows (only if canExpand)
        let detailHtml = '';
        if (canExpand) {
            const now = new Date();
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

                // Check if session is expired (past time)
                const isExpired = s.session_time && new Date(s.session_time) < now;
                const expiredClass = isExpired ? 'expired' : '';
                const expiredLabel = isExpired ? '<span class="expired-label">已结束</span>' : '';

                return `
                    <div class="detail-row ${expiredClass}" onclick="event.stopPropagation(); window.router?.navigate('/detail/${s.event_id || group.event_id}')">
                        <span class="detail-time">${time}</span>
                        <span class="detail-price">${price}</span>
                        <span class="detail-stock ${isLow ? 'low-stock' : ''}">${stock}</span>
                        <span class="detail-cast" style="display: ${showCast ? 'inline' : 'none'}">${cast}</span>
                        ${expiredLabel}
                    </div>
                `;
            }).join('');

            detailHtml = `<div class="detail-panel" id="${groupId}-detail" style="display:none;">${detailRows}</div>`;
        }

        // Click handler
        const clickAction = canExpand
            ? `toggleDetail('${groupId}')`
            : `window.router?.navigate('/detail/${group.event_id || ''}')`;

        // Mobile Layout Structure: Badge+Title+Cast in one flex flow, Meta in another
        return `
            <div class="update-summary-row" data-type="${group.change_type}" onclick="${clickAction}">
                <!-- Title Group: Badge + Title + CastIcon -->
                <div class="summary-title">
                    <span class="summary-badge ${badgeClass}">${label}</span>
                    <span style="display:inline-block; margin-left:8px;">《${group.event_title}》</span>
                    ${castIndicatorHtml}
                </div>
                
                <!-- Meta Group: Date + Count + Time + Arrow -->
                <div class="summary-meta">
                    <span class="summary-date-range">${dateRangeStr}</span>
                    <span class="summary-count">${countStr}</span>
                    <span class="summary-time">${timeAgo}</span>
                    <span class="summary-arrow" id="${groupId}-arrow">${canExpand ? '▸' : '›'}</span>
                </div>
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
