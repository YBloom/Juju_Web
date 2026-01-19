import { state } from '../state.js';
import { api } from '../api.js';
import { escapeHtml } from '../utils.js';

let currentSubTab = 'play';
let allSubscriptions = [];
let isEditMode = false;
let selectedSubIds = new Set();

const NOTIFICATION_LEVEL_MAP = {
    2: "上新/补票",
    3: "上新/补票/回流",
    4: "上新/补票/回流/票减",
    5: "全部动态"
};

function showToast(message, type = 'success') {
    let toast = document.getElementById('toast-notification');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast-notification';
        toast.style.cssText = `
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.85);
            color: white;
            padding: 12px 24px;
            border-radius: 50px;
            z-index: 10000;
            font-size: 14px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 8px;
            opacity: 0;
            transition: opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            pointer-events: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;
        document.body.appendChild(toast);
    }

    const icon = type === 'success' ? 'check_circle' : 'error_outline';
    const color = type === 'success' ? '#4ade80' : '#f87171'; // Green-400 : Red-400

    toast.innerHTML = `<i class="material-icons" style="color:${color}; font-size:18px;">${icon}</i> <span>${escapeHtml(message)}</span>`;

    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translate(-50%, -5px)';
    });

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translate(-50%, 0)';
    }, 3000);
}

export async function initSubscriptionManagement() {
    const container = document.getElementById('subscriptions-container');
    if (!container) return;

    container.innerHTML = '<div class="loading-spinner"></div>';

    try {
        allSubscriptions = await api.fetchSubscriptions();
        renderSubscriptionList();
    } catch (e) {
        console.error("Failed to load subscriptions:", e);
        container.innerHTML = `<div style="text-align:center; padding:40px; color:#999;">
            <i class="material-icons" style="font-size:48px; margin-bottom:10px;">error_outline</i>
            <p>获取订阅列表失败，请检查登录状态。</p>
            <button class="secondary-btn" onclick="initSubscriptionManagement()" style="margin-top:10px;">重试</button>
        </div>`;
    }


}

export function switchSubTab(type) {
    currentSubTab = type;

    // 更新 UI 状态
    document.querySelectorAll('#tab-user-subscriptions .sub-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.type === type);
    });

    renderSubscriptionList();
}

function renderSubscriptionList() {
    const container = document.getElementById('subscriptions-container');
    const subs = allSubscriptions.filter(sub => {
        const target = sub.targets?.[0];
        if (!target) return false;
        return target.kind === currentSubTab;
    });

    if (!subs || subs.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📭</div>
                <div class="empty-text">您还没有${currentSubTab === 'play' ? '剧目' : '演员'}订阅</div>
                <div class="empty-subtext">在上方添加您关注的${currentSubTab === 'play' ? '剧目' : '演员'}，<br>第一时间获取票务动态。</div>
            </div>
        `;
        return;
    }

    // Table layout
    let html = `
        <div class="data-table-container">
            <table class="data-table sub-table">
                <thead>
                    <tr>
                        ${isEditMode ? '<th style="width:40px;"><input type="checkbox" id="select-all-subs" onchange="subscription.toggleSelectAll(this.checked)"></th>' : ''}
                        <th>城市</th>
                        <th>名称</th>
                        <th>模式</th>
                        <th style="width:60px;">操作</th>
                    </tr>
                </thead>
                <tbody>
    `;

    subs.forEach(sub => {
        const target = sub.targets?.[0];
        if (!target) return;

        const city = target.city_filter || '-';
        const name = escapeHtml(target.name);
        const level = sub.options?.notification_level ?? 2;
        const levelText = NOTIFICATION_LEVEL_MAP[level] || `Lv.${level}`;
        const isSelected = selectedSubIds.has(sub.id);

        html += `
            <tr class="sub-table-row ${isSelected ? 'selected' : ''}">
                ${isEditMode ? `<td><input type="checkbox" class="sub-checkbox" data-id="${sub.id}" ${isSelected ? 'checked' : ''} onchange="subscription.toggleSubSelection('${sub.id}', this.checked)"></td>` : ''}
                <td class="city-cell">${escapeHtml(city)}</td>
                <td class="title-cell">${name}</td>
                <td><span class="level-tag">${escapeHtml(levelText)}</span></td>
                <td>
                    ${!isEditMode ? `<button class="icon-btn" onclick="handleDeleteSubscription('${sub.id}')" title="删除"><i class="material-icons">delete_outline</i></button>` : ''}
                </td>
            </tr>
        `;
    });

    html += `
                </tbody>
            </table>
        </div>
    `;

    container.innerHTML = html;
}

export function toggleEditMode() {
    isEditMode = !isEditMode;
    selectedSubIds.clear();
    const btn = document.getElementById('batch-delete-btn');

    if (isEditMode) {
        btn.textContent = '取消';
        btn.classList.add('secondary');
    } else {
        btn.textContent = '多选删除';
        btn.classList.remove('secondary', 'danger');
    }

    renderSubscriptionList();
}

export function toggleSubSelection(id, checked) {
    if (checked) {
        selectedSubIds.add(id);
    } else {
        selectedSubIds.delete(id);
    }

    const btn = document.getElementById('batch-delete-btn');
    if (selectedSubIds.size > 0) {
        btn.textContent = `删除(${selectedSubIds.size})`;
        btn.classList.add('danger');
        btn.classList.remove('secondary');
    } else {
        btn.textContent = '取消';
        btn.classList.add('secondary');
        btn.classList.remove('danger');
    }
}

export function toggleSelectAll(checked) {
    const subs = allSubscriptions.filter(sub => {
        const target = sub.targets?.[0];
        if (!target) return false;
        return target.kind === currentSubTab;
    });

    if (checked) {
        subs.forEach(sub => selectedSubIds.add(sub.id));
    } else {
        selectedSubIds.clear();
    }

    renderSubscriptionList();
    toggleSubSelection(null, selectedSubIds.size > 0);
}

export async function batchDeleteSubscriptions() {
    if (selectedSubIds.size === 0) return;

    if (!confirm(`确定要删除选中的 ${selectedSubIds.size} 项订阅吗？`)) return;

    const btn = document.getElementById('batch-delete-btn');
    btn.disabled = true;

    try {
        for (const id of selectedSubIds) {
            await api.deleteSubscription(id);
        }

        selectedSubIds.clear();
        isEditMode = false;
        await initSubscriptionManagement();
        showToast(`成功删除订阅`);
    } catch (e) {
        showToast('删除失败: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}


function addSubInputRow() {
    const container = document.getElementById('sub-inputs-container');
    const type = document.getElementById('selected-sub-type').value;
    const row = document.createElement('div');
    row.className = 'sub-row';

    // Check if it's the first row to determine if we show + or -
    const isFirst = container.querySelectorAll('.sub-row').length === 0;

    row.innerHTML = `
        <div class="input-wrapper">
            <input type="text" class="sub-row-input" placeholder="${type === 'play' ? '搜索剧目名称...' : '搜索演员姓名...'}" autocomplete="off">
            <div class="autocomplete-suggestions"></div>
            <input type="hidden" class="sub-row-target-id">
            <input type="hidden" class="sub-row-target-name">
        </div>
        ${isFirst ?
            `<button class="circle-btn add" onclick="subscription.addSubInputRow()" title="添加更多"><i class="material-icons">add</i></button>` :
            `<button class="circle-btn remove" onclick="this.closest('.sub-row').remove()" title="移除"><i class="material-icons">remove</i></button>`
        }
    `;

    container.appendChild(row);
    bindSubAutocomplete(row.querySelector('.sub-row-input'));
}

function bindSubAutocomplete(input) {
    if (!input) return;
    const dropdown = input.parentNode.querySelector('.autocomplete-suggestions');
    const targetIdInput = input.parentNode.querySelector('.sub-row-target-id');
    const targetNameInput = input.parentNode.querySelector('.sub-row-target-name');

    const handleInput = async () => {
        const val = input.value.trim();
        const type = document.getElementById('selected-sub-type').value;

        if (!val) {
            dropdown.style.display = 'none';
            return;
        }

        dropdown.style.display = 'block';
        dropdown.innerHTML = '<div class="autocomplete-loading">搜索中...</div>';

        let matches = [];

        if (type === 'play') {
            matches = state.allEvents
                .filter(e => {
                    if (!e.title) return false;
                    const valLower = val.toLowerCase();
                    const titleMatcher = e.title.match(/[《](.*?)[》]/);
                    const pureTitle = titleMatcher ? titleMatcher[1] : e.title;

                    return e.title.toLowerCase().includes(valLower) ||
                        (pureTitle && pureTitle.toLowerCase().includes(valLower));
                })
                .slice(0, 10)
                .map(e => {
                    const titleMatcher = e.title.match(/[《](.*?)[》]/);
                    const pureName = titleMatcher ? titleMatcher[1] : e.title;
                    return {
                        id: e.id,
                        city: e.city || '未知',
                        display_name: `[${e.city || '未知'}] ${pureName}`,
                        pure_name: pureName
                    };
                });
        } else {
            let artistNames = state.allArtistNames || [];
            const pinyin = window.pinyinPro;

            matches = artistNames.filter(name => {
                if (name.includes(val)) return true;
                try {
                    if (pinyin) {
                        const firstLetters = pinyin.pinyin(name, { pattern: 'first', toneType: 'none', type: 'array' }).join('');
                        return firstLetters.includes(val.toLowerCase());
                    }
                } catch (e) { return false; }
                return false;
            }).slice(0, 10).map(name => ({
                id: '',
                display_name: name,
                pure_name: name
            }));
        }

        if (matches.length === 0) {
            dropdown.innerHTML = '<div class="autocomplete-no-results">未找到匹配项</div>';
            return;
        }

        dropdown.innerHTML = matches.map(m => `
            <div class="autocomplete-item" onclick="subscription.selectSubSuggestionRow(this, '${escapeHtml(m.pure_name)}', '${m.id}', '${escapeHtml(m.city || '')}')">
                <div class="ac-title">${escapeHtml(m.display_name)}</div>
            </div>
        `).join('');
    };

    let timeout;
    input.addEventListener('input', () => {
        clearTimeout(timeout);
        timeout = setTimeout(handleInput, 300);
    });

    input.addEventListener('focus', () => {
        if (input.value.trim()) handleInput();
    });
}

export function selectSubSuggestionRow(itemEl, name, id, city = '') {
    const row = itemEl.closest('.sub-row');
    const input = row.querySelector('.sub-row-input');
    const dropdown = row.querySelector('.autocomplete-suggestions');
    const targetIdInput = row.querySelector('.sub-row-target-id');
    const targetNameInput = row.querySelector('.sub-row-target-name');

    // Format: [City] Name for plays
    const displayValue = city ? `[${city}] ${name}` : name;

    input.value = displayValue;
    targetIdInput.value = id || '';
    targetNameInput.value = name || '';
    dropdown.style.display = 'none';
}

export async function doAddSubscription(e) {
    if (e) e.preventDefault();
    const btn = document.querySelector('.submit-sub-btn') || document.querySelector('#add-sub-modal .primary-btn');
    const type = document.getElementById('selected-sub-type').value;
    const level = document.getElementById('sub-level-select')?.value || 2;
    const include = document.getElementById('sub-include-input')?.value;
    const exclude = document.getElementById('sub-exclude-input')?.value;

    const rows = document.querySelectorAll('.sub-row');
    const targets = [];

    rows.forEach(row => {
        const name = row.querySelector('.sub-row-target-name').value || row.querySelector('.sub-row-input').value;
        const id = row.querySelector('.sub-row-target-id').value;
        if (name) {
            targets.push({
                kind: type === 'play' ? 'play' : (type === 'actor' ? 'actor' : 'event'),
                target_id: id,
                name: name,
                city_filter: null, // Removed city filter
                include_plays: include ? include.split(/[,，]/) : null,
                exclude_plays: exclude ? exclude.split(/[,，]/) : null
            });
        }
    });

    // Check for Duplicates
    const duplicates = targets.filter(t => {
        return allSubscriptions.some(sub => {
            const existing = sub.targets?.[0];
            if (!existing || existing.kind !== t.kind) return false;
            // Check ID match or Name match (if ID is missing)
            if (existing.target_id && t.target_id && existing.target_id === t.target_id) return true;
            if (existing.name === t.name) return true;
            return false;
        });
    });

    if (duplicates.length > 0) {
        const names = duplicates.map(d => d.name).join(', ');
        showToast(`已订阅: ${names}`, 'error');
        return;
    }

    if (targets.length === 0) return showToast('请输入订阅目标', 'error');

    btn.disabled = true;
    const originalText = btn.innerText;
    btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px;border-color:#fff;border-bottom-color:transparent;"></div> 添加中...';

    try {
        // Sequentially create subscriptions for each target
        for (const target of targets) {
            await api.createSubscription({
                targets: [target],
                options: {
                    notification_level: parseInt(level)
                }
            });
        }

        initSubscriptionManagement();
        hideAddSubModal();
        showToast('订阅添加成功！');
    } catch (e) {
        showToast('添加失败: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

export async function handleDeleteSubscription(id) {
    if (!confirm('确定要取消此订阅吗？')) return;
    try {
        await api.deleteSubscription(id);
        initSubscriptionManagement();
        showToast('订阅已取消');
    } catch (e) {
        showToast('取消失败: ' + e.message, 'error');
    }
}

export function showAddSubModal() {
    document.getElementById('add-sub-modal').classList.add('active');
    const container = document.getElementById('sub-inputs-container');
    container.querySelectorAll('.sub-row').forEach(r => r.remove()); // Clear old inputs
    addSubInputRow(); // Initialize with one row

    const type = document.getElementById('selected-sub-type')?.value;
    const actorFilters = document.getElementById('actor-filters-group');
    if (actorFilters) actorFilters.style.display = type === 'actor' ? 'block' : 'none';
}

export function hideAddSubModal() {
    document.getElementById('add-sub-modal').classList.remove('active');
}

export function selectSubType(type) {
    document.querySelectorAll('.type-option').forEach(b => {
        b.classList.toggle('active', b.dataset.type === type);
        b.style.borderColor = b.dataset.type === type ? 'var(--primary-color)' : '#eee';
        const icon = b.querySelector('.material-icons');
        if (icon) icon.style.color = b.dataset.type === type ? 'var(--primary-color)' : '#666';
    });
    document.getElementById('selected-sub-type').value = type;

    // Update labels and placeholders
    document.getElementById('target-label').innerText = type === 'play' ? '剧目名称' : '演员姓名';

    // Clear and re-add first row
    const container = document.getElementById('sub-inputs-container');
    container.querySelectorAll('.sub-row').forEach(r => r.remove());
    addSubInputRow();

    const actorFilters = document.getElementById('actor-filters-group');
    if (actorFilters) actorFilters.style.display = type === 'actor' ? 'block' : 'none';
}

// Internal Helper for Row Addition
export { addSubInputRow };

// Global click to close suggestions
document.addEventListener('click', (e) => {
    if (!e.target.closest('.input-wrapper')) {
        document.querySelectorAll('.autocomplete-suggestions').forEach(d => d.style.display = 'none');
    }
});
