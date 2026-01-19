
import { router } from '../router.js';
import { state } from '../state.js';
import { api } from '../api.js';
import { formatDateStr, escapeHtml } from '../utils.js';
import { jumpToDetail } from './details.js';

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
        state.artists = data.artists || [];  // 同时存储到 state.artists 供订阅功能使用
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
                <div><div class="cocast-result-title">🎭 查询到 ${new Set(results.map(r => r.session_id || `${r.title}_${r.date}_${r.location}`)).size} 场同台演出</div></div>
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
    // Deduplicate sessions
    const uniqueResults = [];
    const seen = new Set();
    results.forEach(r => {
        const key = r.session_id || `${r.title}_${r.date}_${r.location}`;
        if (!seen.has(key)) {
            seen.add(key);
            uniqueResults.push(r);
        }
    });

    const total = uniqueResults.length;

    // Dynamic Header Text
    let headerText = '';
    if (casts.length === 1) {
        headerText = `${escapeHtml(casts[0])} 收录演出共 <span style="color:var(--primary-color); font-size:1.3rem; margin:0 4px">${total}</span> 场`;
    } else {
        headerText = `${escapeHtml(casts.join(' & '))} 同台共 <span style="color:var(--primary-color); font-size:1.3rem; margin:0 4px">${total}</span> 场`;
    }

    const groupMap = {};
    uniqueResults.forEach(r => {
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
                Generated by 剧剧 (YYJ)
             </div>
             </div>`;
    return html;
}

export function setCoCastRange(type) {
    const startInput = document.getElementById('cocast-start-date');
    if (!startInput) return;
    if (type === 'earliest') startInput.value = '2023-01-01';
    else if (type === 'today') startInput.value = formatDateStr(new Date());
}
