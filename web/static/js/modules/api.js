// API Interaction Module

export const api = {
    // Auth
    async getPublicConfig() {
        if (this._configCache) return this._configCache;
        try {
            const res = await fetch('/api/meta/config');
            if (res.ok) {
                this._configCache = await res.json();
                return this._configCache;
            }
        } catch (e) { console.error("Config load failed", e); }
        return { bot_uin: "3044829389" }; // Fallback
    },

    async checkLogin() {
        // Use new router endpoint
        const res = await fetch('/auth/me');
        return await res.json();
    },

    async logout() {
        const res = await fetch('/auth/logout', { method: 'POST' });
        return await res.json();
    },

    // User Settings
    async fetchUserSettings() {
        const res = await fetch('/api/user/settings');
        if (res.status === 401) return null;
        if (!res.ok) throw new Error("获取设置失败");
        return await res.json();
    },

    async updateUserSettings(data) {
        const res = await fetch('/api/user/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error("更新设置失败");
        return await res.json();
    },

    async updateGlobalLevel(level) {
        const res = await fetch(`/api/subscriptions/global-level?level=${level}`, {
            method: 'PATCH'
        });
        if (!res.ok) throw new Error("更新全局级别失败");
        return await res.json();
    },

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
    },

    // Ticket Updates
    async fetchRecentUpdates(limit = 20, types = "new,restock,back") {
        const res = await fetch(`/api/tickets/recent-updates?limit=${limit}&types=${types}`);
        if (!res.ok) throw new Error("获取票务更新失败");
        return await res.json();
    },

    // Alias for v2.1 compat
    async fetchTicketUpdates() {
        return this.fetchRecentUpdates(50, "new,restock,back,pending");
    },

    // Subscriptions
    async fetchSubscriptions() {
        const res = await fetch('/api/subscriptions');
        if (!res.ok) throw new Error("获取订阅列表失败");
        return await res.json();
    },

    async createSubscription(data) {
        const res = await fetch('/api/subscriptions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error("创建订阅失败");
        return await res.json();
    },

    async deleteSubscription(id) {
        // Legacy: Deletes entire subscription container
        const res = await fetch(`/api/subscriptions/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error("删除订阅失败");
        return await res.json();
    },

    async deleteSubscriptionTarget(targetId) {
        // New: Deletes specific target
        const res = await fetch(`/api/subscriptions/targets/${targetId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error("删除订阅目标失败");
        return await res.json();
    },

    async updateSubscriptionOptions(id, data) {
        const res = await fetch(`/api/subscriptions/options/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!res.ok) throw new Error("更新订阅选项失败");
        return await res.json();
    }
};
