
import { state } from '../state.js';
import { api } from '../api.js';
import { debounce, escapeHtml, formatDateStr } from '../utils.js';
import { jumpToDetail } from './details.js';

export function initDateTab() {
    const input = document.getElementById('date-input');
    if (!input) return;

    if (!input.value) {
        input.value = new Date().toISOString().split('T')[0];
    }
    input.addEventListener('change', () => doDateSearch());
    doDateSearch();
}

export async function doDateSearch() {
    const dateInput = document.getElementById('date-input');
    const date = dateInput ? dateInput.value : '';
    if (!date) return;

    const container = document.getElementById('date-results');
    container.innerHTML = '<div style="padding:40px;text-align:center;color:#888">查询中...</div>';

    try {
        const data = await api.fetchDateEvents(date);
        renderDateResults(data.results, date);
    } catch (e) {
        container.innerHTML = `<div style="color:red;padding:20px;text-align:center">查询失败: ${escapeHtml(e.message)}</div>`;
    }
}

export const applyDateFilters = debounce((date) => {
    const { currentDateTickets: allTickets } = state;
    if (!allTickets) return;

    const onlyAvailable = document.getElementById('date-filter-available')?.checked || false;
    const cityFilter = document.getElementById('date-filter-city')?.value || '';
    const timeFilter = document.getElementById('date-filter-time')?.value || '';
    const searchText = document.getElementById('date-filter-search')?.value.trim().toLowerCase() || '';

    const filtered = allTickets.filter(t => {
        if (onlyAvailable && (t.stock === 0 || t.status === 'sold_out')) return false;
        if (cityFilter && t.city !== cityFilter) return false;
        if (timeFilter) {
            if (!t.session_time) return false;
            const d = new Date(t.session_time);
            const tStr = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
            if (tStr !== timeFilter) return false;
        }
        if (searchText) {
            const titleLower = t.title ? t.title.toLowerCase() : '';
            const castNames = t.cast ? t.cast.map(c => c.name.toLowerCase()).join(' ') : '';
            if (!titleLower.includes(searchText) && !castNames.includes(searchText)) return false;
        }
        return true;
    });

    renderDateTableRows(filtered);
}, 250);

function renderDateResults(tickets, date) {
    const container = document.getElementById('date-results');
    if (!tickets || tickets.length === 0) { container.innerHTML = `<div style="padding:40px;text-align:center;color:#999">📅 ${date}<br><br>😴 该日期暂无学生票演出安排</div>`; return; }

    const allTickets = tickets.sort((a, b) => new Date(a.session_time) - new Date(b.session_time));
    const cities = [...new Set(allTickets.map(t => t.city).filter(c => c))].sort();
    const times = [...new Set(allTickets.map(t => { if (!t.session_time) return null; const d = new Date(t.session_time); return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); }).filter(v => v))].sort();

    state.currentDateTickets = allTickets;
    state.currentDate = date;

    let html = `
        <div style="margin-bottom:15px;padding:10px;background:#f0f7ff;border-radius:8px;border-left:4px solid var(--primary-color)"><div style="font-size:1.1em;font-weight:600;color:var(--primary-color);margin-bottom:5px">📅 ${date} - 查询到 ${new Set(tickets.map(t => t.session_time)).size} 个场次</div></div>
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

    if (!tbody.dataset.delegated) {
        tbody.addEventListener('click', (e) => {
            const title = e.target.closest('.clickable-title');
            if (title && title.dataset.eventId) {
                jumpToDetail(title.dataset.eventId, title.dataset.sessionId);
            }
        });
        tbody.dataset.delegated = 'true';
    }
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

function getNormalizedTitle(t) {
    let title = t.title || '';
    const match = title.match(/[《](.*?)[》]/);
    if (match && match[1]) title = match[1];
    return title;
}

function getPrice(p) {
    return parseFloat(p) || 0;
}
