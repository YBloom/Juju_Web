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
