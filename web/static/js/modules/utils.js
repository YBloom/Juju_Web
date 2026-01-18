// Utility Functions

export function getCityScore(city) {
    if (!city || typeof city !== 'string') return 100;
    if (city.includes('上海')) return 0;
    if (city.includes('北京')) return 1;
    if (city.includes('广州')) return 2;
    if (city.includes('深圳')) return 3;
    if (city.includes('杭州')) return 4;
    return 100; // Others
}

export function formatDateStr(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

export function formatDateDisplay(dateStr) {
    const arr = dateStr.split('-');
    return `${arr[0]}年${arr[1]}月${arr[2]}日`;
}

export function formatSessionTime(isoStr) {
    if (!isoStr) return '';
    try {
        const d = new Date(isoStr);
        const m = d.getMonth() + 1;
        const day = d.getDate();
        const h = String(d.getHours()).padStart(2, '0');
        const min = String(d.getMinutes()).padStart(2, '0');
        const weekMap = ['日', '一', '二', '三', '四', '五', '六'];
        const week = weekMap[d.getDay()];
        return `${m}月${day}日 周${week} ${h}:${min}`;
    } catch (e) {
        return isoStr;
    }
}

export function getNormalizedTitle(t) {
    if (!t.title) return '';
    const match = t.title.match(/[《](.*?)[》]/);
    return match && match[1] ? match[1].trim() : t.title.trim();
}

export function getPrice(p) {
    if (typeof p === 'number') return p;
    if (!p) return 0;
    const str = String(p).replace(/[^\d.]/g, '');
    return parseFloat(str) || 0;
}

export function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Debounce function if needed in future
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
