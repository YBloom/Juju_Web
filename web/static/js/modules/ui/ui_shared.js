export const UI = {
    // --- Toast Notification ---
    toast(message, type = 'success') {
        let toast = document.getElementById('toast-notification');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'toast-notification';
            toast.className = 'ui-toast'; // Using class for styling
            // Inline fallback styles if CSS not loaded
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

        const iconIcon = type === 'success' ? 'check_circle' : (type === 'error' ? 'error_outline' : 'info');
        const color = type === 'success' ? '#4ade80' : (type === 'error' ? '#f87171' : '#60a5fa');

        toast.innerHTML = `<i class="material-icons" style="color:${color}; font-size:18px;">${iconIcon}</i> <span>${escapeHtml(message)}</span>`;

        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translate(-50%, -5px)';
        });

        if (toast.timeoutId) clearTimeout(toast.timeoutId);

        toast.timeoutId = setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translate(-50%, 0)';
        }, 3000);
    },

    // --- Loading Spinner ---
    showLoading(container) {
        if (!container) return;
        container.innerHTML = `
            <div class="ui-loading-container" style="display:flex; justify-content:center; padding:40px;">
                <div class="spinner"></div>
            </div>
        `;
    },

    // --- Generic Modal ---
    modal({ title, content, actions, onClose }) {
        // Simple modal implementation
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay active';
        overlay.style.zIndex = '9999';

        const modal = document.createElement('div');
        modal.className = 'modal-content card';
        modal.style.maxWidth = '500px';
        modal.style.width = '90%';
        modal.style.animation = 'scaleIn 0.2s ease-out';

        let footerHtml = '';
        if (actions && actions.length > 0) {
            footerHtml = `<div class="modal-footer" style="padding-top:20px; display:flex; gap:10px; justify-content:flex-end;">
                ${actions.map(btn => `
                    <button class="btn ${btn.class || 'btn-secondary'}" id="${btn.id}">
                        ${btn.text}
                    </button>
                `).join('')}
            </div>`;
        }

        modal.innerHTML = `
            <div class="modal-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <h3 style="margin:0; font-size:1.2rem;">${escapeHtml(title)}</h3>
                <button class="btn-icon btn-ghost close-modal"><i class="material-icons">close</i></button>
            </div>
            <div class="modal-body">
                ${content}
            </div>
            ${footerHtml}
        `;

        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        const close = () => {
            overlay.remove();
            if (onClose) onClose();
        };

        // Bind Events
        modal.querySelector('.close-modal').onclick = close;
        overlay.onclick = (e) => {
            if (e.target === overlay) close();
        };

        // Bind Actions
        if (actions) {
            actions.forEach(btn => {
                const el = modal.querySelector(`#${btn.id}`);
                if (el) el.onclick = (e) => {
                    if (btn.onClick) btn.onClick(e, close);
                    else close();
                };
            });
        }

        return { close };
    },

    // --- Autocomplete Helper ---
    // A simplified generic autocomplete binder
    // logic simplified from subscription.js
    bindAutocomplete(inputEl, { fetchSuggestions, onSelect, renderItem }) {
        let dropdown = inputEl.nextElementSibling;
        if (!dropdown || !dropdown.classList.contains('autocomplete-suggestions')) {
            dropdown = document.createElement('div');
            dropdown.className = 'autocomplete-suggestions';
            inputEl.parentNode.insertBefore(dropdown, inputEl.nextSibling);
            // Ensure parent relative
            if (getComputedStyle(inputEl.parentNode).position === 'static') {
                inputEl.parentNode.style.position = 'relative';
            }
        }

        let timeout;
        const close = () => dropdown.style.display = 'none';

        inputEl.addEventListener('input', () => {
            clearTimeout(timeout);
            const val = inputEl.value.trim();
            if (!val) {
                close();
                return;
            }

            timeout = setTimeout(async () => {
                const items = await fetchSuggestions(val);
                if (!items || items.length === 0) {
                    dropdown.innerHTML = '<div class="autocomplete-no-results" style="padding:10px; color:#999; text-align:center;">未找到匹配项</div>';
                    dropdown.style.display = 'block';
                    return;
                }

                dropdown.innerHTML = items.map(item => `
                    <div class="autocomplete-item-wrapper">
                        ${renderItem ? renderItem(item) : `<div class="autocomplete-item p-sm">${escapeHtml(item.label)}</div>`}
                    </div>
                `).join('');

                dropdown.style.display = 'block';

                // Bind clicks
                dropdown.querySelectorAll('.autocomplete-item-wrapper').forEach((el, index) => {
                    el.onclick = () => {
                        onSelect(items[index]);
                        close();
                    };
                });

            }, 300);
        });

        // Close on click outside
        document.addEventListener('click', (e) => {
            if (!inputEl.contains(e.target) && !dropdown.contains(e.target)) {
                close();
            }
        });
    }
};

// Internal Helper
function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
