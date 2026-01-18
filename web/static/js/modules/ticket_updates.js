import { api } from './api.js';
import { router } from './router.js';
import { state } from './state.js';
import { formatSessionTime, escapeHtml } from './utils.js';

let updateStatusPollInterval = null;

// --- Initialization ---

export function initTicketUpdates() {
    renderFilterPills();
    fetchAndRenderUpdates();

    // Auto-refresh every 60s
    if (updateStatusPollInterval) clearInterval(updateStatusPollInterval);
    updateStatusPollInterval = setInterval(fetchUpdateStatus, 60000);

    // Expand/Collapse Card
    const card = document.getElementById('ticket-updates-card');
    const header = card.querySelector('.updates-header');
    const expandIcon = card.querySelector('.expand-icon');

    // Default expanded state
    card.classList.add('expanded');

    header.addEventListener('click', () => {
        card.classList.toggle('expanded');
        // Rotate icon
        if (card.classList.contains('expanded')) {
            expandIcon.style.transform = 'rotate(180deg)';
        } else {
            expandIcon.style.transform = 'rotate(0deg)';
        }
    });

    // Checkpill toggle (Show Cast)
    const castPill = document.getElementById('show-cast-pill');
    if (castPill) {
        castPill.addEventListener('click', () => {
            castPill.classList.toggle('active');
            // Toggle class on container instantly without re-render
            const listContainer = document.getElementById('updates-list');
            if (listContainer) {
                if (castPill.classList.contains('active')) {
                    listContainer.classList.add('show-cast-mode');
                } else {
                    listContainer.classList.remove('show-cast-mode');
                }
            }
        });
    }

    // Event Delegation for Updates List
    const listContainer = document.getElementById('updates-list');
    if (listContainer) {
        listContainer.addEventListener('click', (e) => {
            // Handle Detail Row Click (Navigation)
            const detailRow = e.target.closest('.detail-row');
            if (detailRow && detailRow.dataset.eventId) {
                e.stopPropagation();
                router.navigate(`/detail/${detailRow.dataset.eventId}`);
                return;
            }

            // Handle Summary Row Click (Toggle or Nav)
            const summaryRow = e.target.closest('.update-summary-row');
            if (summaryRow) {
                const groupId = summaryRow.dataset.groupId;
                const eventId = summaryRow.dataset.eventId;
                const canExpand = summaryRow.dataset.canExpand === 'true';

                if (canExpand) {
                    toggleDetail(groupId);
                } else if (eventId) {
                    router.navigate(`/detail/${eventId}`);
                }
            }
        });
    }
}

// --- Filter Logic ---

function renderFilterPills() {
    const container = document.getElementById('filter-pills-container');
    if (!container) return;

    // Bind Filter Pills
    const filterPills = container.querySelectorAll('.filter-pill:not(#show-cast-pill)');
    filterPills.forEach(pill => {
        pill.addEventListener('click', () => {
            pill.classList.toggle('active');
            fetchAndRenderUpdates();
        });
    });
}

async function fetchUpdateStatus() {
    const el = document.getElementById('update-status');
    if (!el) return;
    try {
        const res = await api.fetchUpdateStatus();
        if (res.hulaquan && res.hulaquan.last_updated) {
            const date = new Date(res.hulaquan.last_updated);
            const timeStr = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
            el.innerText = `最后更新: ${timeStr}`;
        }
    } catch (e) {
        console.warn('Status poll failed', e);
    }
}

// --- Data Fetching & Rendering ---

export async function fetchAndRenderUpdates() {
    const listContainer = document.getElementById('updates-list');

    // Get Checked Values from Pills
    const checkedTypes = Array.from(document.querySelectorAll('.filter-pill.active:not(#show-cast-pill)'))
        .map(p => p.dataset.value)
        .filter(v => v);

    const showCast = document.getElementById('show-cast-pill')?.classList.contains('active') || false;

    if (checkedTypes.length === 0) {
        listContainer.innerHTML = '<div style="padding:20px;text-align:center;color:#999">请选择至少一种动态类型</div>';
        return;
    }

    try {
        // Show loading skeleton or text if needed, but for updates we might want silent refresh if data exists
        if (!listContainer.hasChildNodes()) {
            listContainer.innerHTML = '<div style="padding:20px;text-align:center;color:#999">正在加载动态...</div>';
        }

        const data = await api.fetchTicketUpdates(); // Assuming API returns raw list
        const updates = data.results || [];

        // Client-side Filtering
        const filtered = updates.filter(u => checkedTypes.includes(u.change_type));

        if (filtered.length === 0) {
            listContainer.innerHTML = '<div style="padding:20px;text-align:center;color:#999">暂无相关动态</div>';
            return;
        }

        // Grouping & Sorting
        // 1. Group by Event ID (or visually group them)
        // User Logic: "Smart Snippets" -> Group by Event, Sort by UpdateTime

        const grouped = groupUpdatesByEvent(filtered);

        // Apply class based on current pill state (for initial load or re-renders)
        if (showCast) {
            listContainer.classList.add('show-cast-mode');
        } else {
            listContainer.classList.remove('show-cast-mode');
        }

        // Render
        renderSummaryList(listContainer, grouped);

    } catch (e) {
        console.error("Failed to fetch updates:", e);
        listContainer.innerHTML = '<div style="padding:20px;text-align:center;color:#999">加载失败，请刷新重试</div>';
    }
}

// --- Grouping Logic ---

function groupUpdatesByEvent(updates) {
    // Map: event_id -> { event_title, latest_at, sessions: [], types: Set }
    const groups = {};

    updates.forEach(u => {
        if (!groups[u.event_id]) {
            groups[u.event_id] = {
                event_id: u.event_id,
                event_title: u.event_title,
                latest_at: new Date(u.created_at),
                sessions: [],
                types: new Set()
            };
        }

        // Deduplicate sessions if needed? 
        // Logic: A session might have multiple updates. 
        // We just want unique sessions per event group for the "List" view of sessions.
        // But here `updates` are update logs. 
        // Let's store the update object itself as 'session' info

        const g = groups[u.event_id];
        if (new Date(u.created_at) > g.latest_at) g.latest_at = new Date(u.created_at);
        g.types.add(u.change_type);

        // Check for dupe session in this group (same ticket_id)
        // If same session, keep the LATEST update info (e.g. stock change)
        const existingSessIndex = g.sessions.findIndex(s => s.ticket_id === u.ticket_id);
        if (existingSessIndex >= 0) {
            // Replace if newer? Or prefer certain types?
            // Simple logic: overwrite
            g.sessions[existingSessIndex] = u;
        } else {
            g.sessions.push(u);
        }
    });

    // Convert to array and Sort Groups
    const groupArray = Object.values(groups).map(g => {
        // Determine primary type for Badge
        // Priority: restock > new > pending > back
        // Actually: new (上新) > restock (回流) > back (补票) > pending (开票) ?
        // User asked for specific color badges. 
        // Let's pick the "Most Important" type present in the set.
        const types = Array.from(g.types);
        let primaryType = types[0];
        if (types.includes('new')) primaryType = 'new';
        else if (types.includes('restock')) primaryType = 'restock';
        else if (types.includes('back')) primaryType = 'back';

        return { ...g, primaryType };
    });

    // Sort Groups: 
    // 1. Has Active Sessions (stock > 0) ?
    // 2. Latest Update Time DESC
    // 3. Earliest Session Time ASC (Secondary)

    groupArray.sort((a, b) => {
        const aHasStock = a.sessions.some(s => s.stock > 0);
        const bHasStock = b.sessions.some(s => s.stock > 0);
        if (aHasStock && !bHasStock) return -1;
        if (!aHasStock && bHasStock) return 1;

        return b.latest_at - a.latest_at;
    });

    return groupArray;
}

// --- Rendering Logic ---

function renderSummaryList(container, groups) {
    const now = new Date();
    const html = groups.map(group => {
        const timeAgo = formatTimeAgo(group.latest_at);

        // Determine Badge
        const typeLabels = {
            'new': { text: '上新', class: 'badge-new' },
            'pending': { text: '待开票', class: 'badge-pending' },
            'back': { text: '补票', class: 'badge-back' },
            'restock': { text: '回流', class: 'badge-restock' }
        };

        const badgeConfig = typeLabels[group.primaryType] || { text: '动态', class: 'badge-default' };
        let badgeClass = badgeConfig.class;
        const label = badgeConfig.text;

        const isHeroType = ['pending', 'new'].includes(group.primaryType);
        const isPending = group.primaryType === 'pending';

        // 1. Badge Logic
        if (group.primaryType === 'pending') {
            badgeClass = 'type-pending-hero';
        } else if (group.primaryType === 'new') {
            badgeClass = 'type-new-hero';
        }

        // 2. Valid From Grouping Logic (Only for Pending)
        let openTimeStr = '';
        if (isPending) {
            // Rely on backend-normalized valid_from strings (minute precision)
            const validTimes = [...new Set(group.sessions.map(s => s.valid_from).filter(t => t))].sort();

            if (validTimes.length === 1) {
                // All same valid_from -> Show in header
                openTimeStr = `<span class="open-time-tag">⏰ ${escapeHtml(validTimes[0])}</span>`;
            } else if (validTimes.length > 1) {
                // Multiple different times. Show the earliest? Or just "多场次"
                // User wants to see time. Let's show the first one and a hint.
                openTimeStr = `<span class="open-time-tag">⏰ ${escapeHtml(validTimes[0])} 等</span>`;
            } else {
                // No valid_from found? Try to find from "message" or other fields if needed?
                // Currently just empty.
            }
        }

        // Snippets (Top 3 Sessions) - Only for Non-Hero types (restock, back)
        // Sort sessions by time
        group.sessions.sort((a, b) => new Date(a.session_time) - new Date(b.session_time));

        const activeSessions = group.sessions.filter(s => new Date(s.session_time) > now);
        const snippetCandidates = activeSessions.length > 0 ? activeSessions : group.sessions;

        // Dedup by Date? (If multiple updates for same day). Already deduped by session_id.
        // Just take top 3 distinct dates logic if simpler? 
        // Start simple: Top 3 sessions (or 5 for pending since they are smaller)
        const sliceCount = isHeroType ? 5 : 3; // Kept variable but effectively unused if hidden
        const top3 = snippetCandidates.slice(0, sliceCount);

        let countStr = '';
        if (isHeroType) {
            // For Hero types (Pending/New), we hide snippets, so show TOTAL quantity.
            countStr = `共${group.sessions.length}场`;
        } else {
            // For others, show removed count
            const remainingCount = Math.max(0, group.sessions.length - sliceCount);
            if (remainingCount > 0) countStr = `+${remainingCount}`;
        }

        const canExpand = group.sessions.length > 0;
        const groupId = `group-${group.event_id}`;

        const snippetHtml = isHeroType ? '' : top3.map((s, i) => {
            const dt = new Date(s.session_time);
            const mon = dt.getMonth() + 1;
            const day = dt.getDate();
            const weekMap = ['日', '一', '二', '三', '四', '五', '六'];
            const week = weekMap[dt.getDay()];

            let stockHtml = '';

            // Only show stock info if NOT pending (and stock exists)
            // Actually, for restock/back, we DO show stock.
            if (s.stock !== null && s.stock !== undefined) {
                let stockClass = 'snippet-stock';
                let stockLabel = '充足';

                if (s.stock <= 0) { stockLabel = '售罄'; stockClass += ' sold-out'; }
                else if (s.stock <= 5) { stockLabel = `余${s.stock}`; stockClass += ' urgent'; }
                else if (s.stock <= 20) { stockLabel = `余${s.stock}`; stockClass += ' warning'; }
                else { stockLabel = `余${s.stock}`; }

                stockHtml = `<span class="${stockClass}">${escapeHtml(stockLabel)}</span>`;
            }

            const sep = i < top3.length - 1 ? '<span class="snippet-separator">·</span>' : '';
            return `<div class="snippet-item" style="display:inline-flex; align-items:center;">
                <span class="snippet-date">${mon}.${day} 周${week}</span>
                ${stockHtml}
            </div>${sep}`;
        }).join('');

        // --- Detail Rows (Hidden) ---
        let detailHtml = '';
        if (canExpand) {
            const detailRows = group.sessions.map(s => {
                let dateStr = '-', weekStr = '', timeStr = '';
                if (s.session_time) {
                    try {
                        const d = new Date(s.session_time);
                        const m = d.getMonth() + 1;
                        const day = d.getDate();
                        const h = String(d.getHours()).padStart(2, '0');
                        const min = String(d.getMinutes()).padStart(2, '0');
                        const weekMap = ['日', '一', '二', '三', '四', '五', '六'];

                        dateStr = `${m}月${day}日`;
                        weekStr = `周${weekMap[d.getDay()]}`;
                        timeStr = `${h}:${min}`;
                    } catch (e) { dateStr = s.session_time || '-'; }
                }

                const price = s.price ? `¥${s.price}` : '';
                const stock = s.stock !== null ? `余${s.stock}` : '';
                let casts = s.cast_names || [];
                if (typeof casts === 'string') { try { casts = JSON.parse(casts); } catch (e) { casts = [casts]; } }
                const cast = Array.isArray(casts) && casts.length ? casts.join(' ') : '';
                const isLow = s.stock !== null && s.stock <= 5;
                const isExpired = s.session_time && new Date(s.session_time) < now;
                const expiredClass = isExpired ? 'expired' : '';

                // Extra info (Open Time or Expired Label)
                let extraInfo = '';
                if (isExpired) {
                    extraInfo = '<span class="expired-label">已结束</span>';
                } else if (s.valid_from && isPending) {
                    // Collect unique times for the group to see if we have multiple waves
                    const uniqueTimes = [...new Set(group.sessions.map(ss => ss.valid_from).filter(t => t))];

                    if (uniqueTimes.length > 1) {
                        extraInfo = `<span style="color:#f59e0b; font-size:0.85em;">${escapeHtml(s.valid_from)}开抢</span>`;
                    }
                }

                return `
                    <div class="detail-row ${expiredClass}" data-event-id="${s.event_id || group.event_id}">
                        <span class="detail-date">${escapeHtml(dateStr)}</span>
                        <span class="detail-week">${escapeHtml(weekStr)}</span>
                        <span class="detail-hm">${escapeHtml(timeStr)}</span>
                        <span class="detail-price">${escapeHtml(price)}</span>
                        <span class="detail-stock ${isLow ? 'low-stock' : ''}">${escapeHtml(stock)}</span>
                        <span class="detail-cast">${escapeHtml(cast)}</span>
                        <span class="detail-extra">${extraInfo}</span>
                    </div>
                `;
            }).join('');
            detailHtml = `<div class="detail-panel" id="${groupId}-detail" style="display:none;">${detailRows}</div>`;
        }

        const clickAction = canExpand ? `toggleDetail('${groupId}')` : `window.router?.navigate('/detail/${group.event_id || ''}')`;

        // v2.1: Single Line Title + Badge | Right: Snippets (Desktop)
        return `
            <div class="update-summary-row" data-type="${group.primaryType}" data-group-id="${groupId}" data-event-id="${group.event_id || ''}" data-can-expand="${canExpand}">
                <div class="summary-top-line">
                    <div class="summary-title">
                        <span class="summary-badge ${badgeClass}">${escapeHtml(label)}</span>
                        <span class="summary-event-title" style="margin-left:8px;">${escapeHtml(cleanEventTitle(group.event_title))}</span>
                        ${openTimeStr}
                    </div>
                </div>
                
                <div class="snippet-row">
                    ${snippetHtml}
                    ${countStr ? `${snippetHtml ? '<span class="snippet-separator" style="color:#ddd; margin-left:10px;">|</span>' : ''} <span style="font-size:0.8em; color:#999;">${countStr}</span>` : ''}
                </div>
                
                 <div class="summary-meta" style="margin-left:auto; padding-left:10px;">
                    <span class="summary-time">${escapeHtml(timeAgo)}</span>
                    <span class="summary-arrow" id="${groupId}-arrow">${canExpand ? '▸' : '›'}</span>
                </div>
            </div>
            ${detailHtml}
        `;
    }).join('');

    container.innerHTML = html || '<div class="no-updates">暂无票务动态</div>';
}

// Local toggle helper
function toggleDetail(groupId) {
    const detail = document.getElementById(`${groupId}-detail`);
    const arrow = document.getElementById(`${groupId}-arrow`);
    if (detail) {
        const isHidden = detail.style.display === 'none';
        detail.style.display = isHidden ? 'block' : 'none';
        if (arrow) arrow.textContent = isHidden ? '▾' : '▸';
    }
}

// Helper: Time Ago
function formatTimeAgo(date) {
    const diff = (new Date() - date) / 1000;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
    return `${Math.floor(diff / 86400)}天前`;
}

// Helper: Clean Event Title
function cleanEventTitle(title) {
    if (!title) return '';
    const match = title.match(/《([^》]+)》/);
    if (match && match[1]) {
        return `《${match[1]}》`;
    }
    return title;
}
