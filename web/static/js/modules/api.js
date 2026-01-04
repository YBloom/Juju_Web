// API Interaction Module

export const api = {
    // Meta/Status
    async fetchUpdateStatus() {
        try {
            const res = await fetch('/api/meta/status');
            return await res.json();
        } catch (e) {
            console.error('Failed to fetch update status:', e);
            throw e;
        }
    },

    async fetchArtists() {
        try {
            const res = await fetch('/api/meta/artists');
            if (!res.ok) throw new Error('Failed to fetch artists');
            return await res.json();
        } catch (e) {
            console.error("Failed to init actor autocomplete:", e);
            throw e;
        }
    },

    // Events
    async fetchEventList() {
        const res = await fetch('/api/events/list');
        return await res.json();
    },

    async fetchEventDetail(eventId) {
        const res = await fetch(`/api/events/${eventId}`);
        return await res.json();
    },

    async fetchDateEvents(date) {
        const res = await fetch(`/api/events/date?date=${date}`);
        return await res.json();
    },

    // Co-Cast
    async startCoCastTask(params) {
        const res = await fetch('/api/tasks/co-cast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        });
        if (!res.ok) throw new Error("启动搜索任务失败");
        return await res.json();
    },

    async fetchTaskStatus(taskId) {
        const res = await fetch(`/api/tasks/${taskId}`);
        if (!res.ok) throw new Error("获取任务状态失败");
        return await res.json();
    }
};
