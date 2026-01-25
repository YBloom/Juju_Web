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
            const detailRow = e.target.closest('.update-session-row');
            if (detailRow) {
                e.stopPropagation();
                // Detail rows in ticket updates usually don't have session-specific nav unless intended.
                // The old code navigated to /detail/:id. 
                // Assuming eventId is on the row or parent.
                // In render, .update-session-row has data-event-id.
                if (detailRow.dataset.eventId) {
                    router.navigate(`/detail/${detailRow.dataset.eventId}`);
                }
                return;
            }

            // Handle Summary Row/Compact Item Click (Toggle Details)
            const summaryRow = e.target.closest('.compact-list-item');
            if (summaryRow) {
                const canExpand = summaryRow.dataset.canExpand === 'true';
                const groupId = summaryRow.dataset.groupId;
                const eventId = summaryRow.dataset.eventId;

                if (canExpand && groupId) {
                    toggleDetail(groupId);
                } else if (eventId && !canExpand) {
                    // Fallback: If no details, maybe navigate?
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

        // Deduplication removed: Allow multiple updates for same ticket (e.g. New -> Restock)
        // 去重已移除：允许同一张票有多次更新（如：上新 -> 回流）
        g.sessions.push(u);
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

// --- Rendering Logic ---

function renderSummaryList(container, groups) {
    const now = new Date();
    const html = groups.slice(0, 20).map(group => {
        const timeAgo = formatTimeAgo(group.latest_at);

        // Extract City and Clean Title
        const { city, cleanTitle } = getDisplayInfo(group.event_id, group.event_title);

        const typeLabels = {
            'new': { text: '上新', class: 'badge-new-compact' },
            'pending': { text: '待开票', class: 'badge-pending-compact' },
            'back': { text: '补票', class: 'badge-back-compact' },
            'restock': { text: '回流', class: 'badge-restock-compact' }
        };

        const badgeConfig = typeLabels[group.primaryType];
        const badgeHtml = badgeConfig ? `<span class="compact-status-badge ${badgeConfig.class}">${badgeConfig.text}</span>` : '';

        // Meta Info Construction
        let metaInfo = '';

        // 1. Date Range & Count
        const validSessions = group.sessions.filter(s => s.session_time); // Simple filter
        const uniqueDates = [...new Set(validSessions.map(s => {
            const d = new Date(s.session_time);
            return `${d.getMonth() + 1}.${d.getDate()}`;
        }))].sort((a, b) => {
            const [m1, d1] = a.split('.').map(Number);
            const [m2, d2] = b.split('.').map(Number);
            return m1 === m2 ? d1 - d2 : m1 - m2;
        });

        let dateStr = '';
        if (uniqueDates.length > 0) {
            // 使用 "." 作为分隔符,不需要 "至" 前缀
            if (uniqueDates.length <= 2) dateStr = uniqueDates.map(d => `2026.${d}`).join(', ');
            else dateStr = `2026.${uniqueDates[0]}-2026.${uniqueDates[uniqueDates.length - 1]}`;
        }

        const sessionCount = group.sessions.length;
        const countStr = sessionCount > 0 ? `${sessionCount}场` : '';

        metaInfo = [dateStr, countStr].filter(Boolean).join(' · ');

        // Hero/Pending specific extra info (e.g. Open Time)
        if (group.primaryType === 'pending') {
            const validTimes = [...new Set(group.sessions.map(s => s.valid_from).filter(t => t))].sort();
            if (validTimes.length > 0) {
                metaInfo += ` · ${validTimes[0]}开抢`;
            }
        }

        const canExpand = group.sessions.length > 0;
        const groupId = `group-${group.event_id}`;

        // Detail Rows (Hidden)
        let detailHtml = '';
        if (canExpand) {
            // Sort sessions by date/time ascending (earliest first)
            const sortedSessions = [...group.sessions].sort((a, b) => {
                const dateA = a.session_time ? new Date(a.session_time) : new Date(0);
                const dateB = b.session_time ? new Date(b.session_time) : new Date(0);
                return dateA - dateB;
            });

            const detailRows = sortedSessions.map(s => {
                const d = new Date(s.session_time);
                const datePart = `2026.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
                const timePart = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
                const price = s.price ? `¥${s.price}` : '';
                const stock = s.stock !== null ? `余${s.stock}` : '';
                const isLow = s.stock !== null && s.stock <= 5;
                const urgentClass = isLow ? 'stock-urgent' : 'stock-normal';

                return `
                    <tr class="update-session-row" data-event-id="${s.event_id}">
                        <td class="col-date">${datePart} ${timePart}</td>
                        <td class="col-price">${price}</td>
                        <td class="col-stock">
                             <span class="${urgentClass}">${stock}</span>
                        </td>
                    </tr>
                `;
            }).join('');

            detailHtml = `
                <div class="updates-table-container" id="${groupId}-detail" style="display:none;">
                    <table class="updates-session-table">
                        <tbody>
                            ${detailRows}
                        </tbody>
                    </table>
                </div>
            `;
        }

        // Compact List Item Structure
        return `
            <div class="compact-list-item clean-list-item adaptive-row" data-group-id="${groupId}" data-can-expand="${canExpand}" data-event-id="${group.event_id}">
                <div class="cli-info-group">
                    <div class="cli-main-row grid-5-cols-updates">
                        <div class="col-type">${badgeHtml}</div>
                        <div class="col-title">${escapeHtml(city ? `[${city}] ${cleanTitle}` : cleanTitle)}</div>
                        <div class="col-dates">${escapeHtml(dateStr)}</div>
                        <div class="col-count">${escapeHtml(countStr)}</div>
                        <div class="col-time">${escapeHtml(timeAgo)}</div>
                    </div>
                </div>
                ${detailHtml}
            </div>
        `;
    }).join('');

    container.innerHTML = html || '<div class="no-updates">暂无票务动态</div>';
}

// --- Helper Functions ---

// Helper to get city from state or clean title
function getDisplayInfo(eventId, rawTitle) {
    let city = '';
    let cleanTitle = rawTitle || '';

    // 1. Try to find city from State (Source of Truth)
    if (state.allEvents && state.allEvents.length > 0) {
        const found = state.allEvents.find(e => String(e.id) === String(eventId));
        if (found && found.city) {
            city = found.city;
        }
    }

    // 2. Clean Title Logic
    // Step A: Remove ANY leading [xxx] or 【xxx】 tags (removes "Winter Warm", "Shanghai", etc. from string)
    cleanTitle = cleanTitle.replace(/^[\[【].*?[\]】]/, '').trim();

    // Step B: If there is a second tag remaining (unlikely but possible), remove it too? 
    // User only complained about the first one. Let's stick to first one for now, or use loop?
    // Usually only one prefix.

    // Step C: Extract core title from 《》 if present
    const bookNameMatch = cleanTitle.match(/[《](.*?)[》]/);
    if (bookNameMatch && bookNameMatch[1]) {
        cleanTitle = bookNameMatch[1].trim();
    }

    // Fallback: If city was NOT found in state, try to recover it from the original rawTitle if it looked like a city
    if (!city) {
        const fallbackMatch = rawTitle.match(/^[\[【](.+?)[\]】]/);
        if (fallbackMatch && fallbackMatch[1]) {
            // Check if it looks like a city (2-3 chars, usually) or just accept it?
            // User wants to remove "Winter Warm". That is long.
            // Cities are short: 上海, 北京.
            // Heuristic: If length < 4, assume city.
            const tag = fallbackMatch[1];
            if (tag.length < 4) {
                city = tag;
            }
        }
    }

    return { city, cleanTitle };
}

function getCityColorClass(city) {
    // Map common cities to color tags
    // User requested: "上海-LightBlue", "南京-LightPurple"
    if (!city) return '';

    if (city.includes('上海')) return 'tag-city-sh';
    if (city.includes('南京')) return 'tag-city-nj';
    if (city.includes('北京')) return 'tag-city-bj';
    if (city.includes('广州') || city.includes('深圳')) return 'tag-city-gz';
    if (city.includes('杭州')) return 'tag-city-hz';

    return 'tag-city-default';
}

// Local toggle helper
function toggleDetail(groupId) {
    const detail = document.getElementById(`${groupId}-detail`);
    if (detail) {
        const isHidden = detail.style.display === 'none';
        detail.style.display = isHidden ? 'block' : 'none';
    }
}

// Helper: Time Ago
function formatTimeAgo(date) {
    const diff = (new Date() - date) / 1000;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)}m`; // Compact: 30m
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`; // Compact: 8h
    return `${Math.floor(diff / 86400)}d`; // Compact: 1d
}

// Helper: Clean Event Title (Fallback)
function cleanEventTitle(title) {
    // Used inside extractCity logic now, but kept for safety if needed elsewhere
    // But confusingly extractCity returns cleanTitle. 
    // Let's just return title here to avoid double processing if not used.
    return title;
}
