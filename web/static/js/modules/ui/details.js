
import { state } from '../state.js';
import { api } from '../api.js';
import { router } from '../router.js';
import { escapeHtml } from '../utils.js';
import { searchInCoCast } from './cocast.js';

export async function showDetailView(eventId) {
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    document.getElementById('detail-view').classList.remove('hidden');

    const container = document.getElementById('detail-content');
    container.innerHTML = '<div style="padding:40px;text-align:center">加载详情中...</div>';

    try {
        const data = await api.fetchEventDetail(eventId);
        if (data.results && data.results.length > 0) {
            renderDetailView(data.results[0]);

            // --- 记录日志 ---
            const evt = data.results[0];
            try {
                fetch('/api/log/view', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: evt.title, id: evt.id })
                });
            } catch (ignore) { }
            // --- 结束日志 ---

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
        <div class="page-header">
            <h2 class="page-title">${escapeHtml(event.title)}</h2>
            <div class="page-subtitle" style="display:flex; justify-content:space-between; align-items:flex-end;">
                <div style="display:flex; gap:12px;">
                    <span>📍 ${escapeHtml(event.location || '未知场馆')}</span>
                    <span>📅 排期: ${escapeHtml(event.schedule_range || '待定')}</span>
                </div>
                <div class="text-xs text-secondary">
                    💡 点击场次可跳转呼啦圈购票
                </div>
            </div>
        </div>
        
        <div class="card card-flat p-sm mb-md">
            <div class="filter-section">
                <!-- Top Row: Toggle & Prices -->
                <div class="flex items-center gap-sm flex-wrap" style="margin-bottom: ${hasCast ? '12px' : '0'}">
                    <label class="filter-pill-toggle" style="display:flex; align-items:center; background:#fff; padding:6px 14px; border-radius:50px; border:1px solid var(--border-color); cursor:pointer; font-size:0.85rem; color:var(--text-secondary); white-space:nowrap; flex-shrink:0;">
                        <style>#filter-available:checked + span { color: var(--primary-color); font-weight: 600; }</style>
                        <input type="checkbox" id="filter-available" style="margin-right:6px;"><span>只看有票</span>
                    </label>
                    <div style="width:1px; height:20px; background:var(--border-color); margin:0 4px;"></div>
                    <div class="flex items-center gap-xs flex-wrap">
                        <span style="font-size:0.85rem; color:var(--text-secondary); margin-right:4px; white-space:nowrap;">价位:</span>
                        ${allPrices.map(price => `<label style="display:inline-flex; align-items:center; background:#fff; padding:4px 10px; border-radius:50px; border:1px solid var(--border-color); cursor:pointer; font-size:0.8rem; color:var(--text-secondary); margin-bottom:4px; white-space:nowrap;"><input type="checkbox" class="filter-price" value="${price}" checked style="margin-right:4px"><span>¥${price}</span></label>`).join('')}
                    </div>
                </div>
                
                <!-- Bottom Row: Search (Full Width on Mobile) -->
                ${hasCast ? `
                <div class="search-row" style="width:100%;">
                    <div style="display:flex; align-items:center; background:#fff; padding:8px 14px; border-radius:50px; border:1px solid var(--border-color); width:100%;">
                        <i class="material-icons" style="font-size:1.1rem; color:var(--primary-color); margin-right:8px; flex-shrink:0;">search</i>
                        <input type="text" id="filter-cast" placeholder="搜卡司..." style="border:none; outline:none; font-size:0.9rem; width:100%; color:var(--text-primary); background:transparent; min-width:0;">
                    </div>
                </div>` : ''}
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
        if (t.valid_from && t.session_time) {
            const validFromDate = new Date(t.valid_from);
            const sessionDate = new Date(t.session_time);
            const now = new Date();
            // 只在开票时间在未来且在演出时间之前时显示
            if (validFromDate > now && validFromDate < sessionDate) {
                validFromInfo = `<div style="font-size:0.8rem; color:#f59e0b; margin-top:4px; display:flex; align-items:center; gap:4px;">
                    <span class="material-icons" style="font-size:1rem;">alarm</span>
                    ${escapeHtml(t.valid_from)} 开票
                </div>`;
            }
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

    if (!tbody.dataset.delegated) {
        tbody.addEventListener('click', (e) => {
            const castLink = e.target.closest('.cast-link');
            if (castLink) {
                e.stopPropagation();
                searchInCoCast(castLink.dataset.name);
                return;
            }

            const row = e.target.closest('tr');
            if (row) {
                window.open(`https://clubz.cloudsation.com/event/${eventId}.html`, '_blank');
            }
        });
        tbody.dataset.delegated = 'true';
    }
}

export function jumpToDetail(eventId, sessionId) {
    window.router.navigate('/detail/' + eventId);
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
