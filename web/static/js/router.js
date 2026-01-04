// 轻量级 Hash 路由模块
// 支持路径参数和查询参数解析

class Router {
    constructor() {
        this.routes = [];
        this.currentRoute = null;

        // 监听 hash 变化和页面加载
        window.addEventListener('hashchange', () => this.handleRoute());
        window.addEventListener('DOMContentLoaded', () => this.handleRoute());
    }

    /**
     * 注册路由
     * @param {string} path - 路径模式，支持参数如 '/detail/:id'
     * @param {function} handler - 路由处理函数
     */
    on(path, handler) {
        this.routes.push({ path, handler });
    }

    /**
     * 导航到指定路径
     * @param {string} path - 目标路径
     * @param {boolean} replace - 是否替换当前历史记录
     */
    navigate(path, replace = false) {
        // 确保路径以 / 开头
        if (!path.startsWith('/')) {
            path = '/' + path;
        }

        if (replace) {
            window.location.replace('#' + path);
        } else {
            window.location.hash = path;
        }
    }

    /**
     * 后退
     */
    back() {
        window.history.back();
    }

    /**
     * 前进
     */
    forward() {
        window.history.forward();
    }

    /**
     * 获取当前 Hash 路径（不含 #）
     */
    getCurrentPath() {
        const hash = window.location.hash;
        return hash ? hash.slice(1) : '/';
    }

    /**
     * 处理路由变化
     */
    handleRoute() {
        const path = this.getCurrentPath();
        const { route, params, query } = this.matchRoute(path);

        if (route) {
            this.currentRoute = { path, params, query };
            route.handler(params, query);
        } else {
            console.warn('No route matched for:', path);
            // 默认跳转到首页
            this.navigate('/', true);
        }
    }

    /**
     * 匹配路由并提取参数
     * @param {string} path - 当前路径
     * @returns {object} - { route, params, query }
     */
    matchRoute(path) {
        // 分离路径和查询字符串
        const [pathname, queryString] = path.split('?');
        const query = this.parseQuery(queryString);

        // 遍历注册的路由
        for (const route of this.routes) {
            const params = this.matchPath(route.path, pathname);
            if (params !== null) {
                return { route, params, query };
            }
        }

        return { route: null, params: {}, query };
    }

    /**
     * 匹配路径模式
     * @param {string} pattern - 路由模式，如 '/detail/:id'
     * @param {string} path - 实际路径，如 '/detail/123'
     * @returns {object|null} - 参数对象或 null
     */
    matchPath(pattern, path) {
        // 将模式和路径分割成段
        const patternParts = pattern.split('/').filter(p => p);
        const pathParts = path.split('/').filter(p => p);

        // 段数不同，不匹配
        if (patternParts.length !== pathParts.length) {
            return null;
        }

        const params = {};

        // 逐段比对
        for (let i = 0; i < patternParts.length; i++) {
            const patternPart = patternParts[i];
            const pathPart = pathParts[i];

            // 参数段（如 :id）
            if (patternPart.startsWith(':')) {
                const paramName = patternPart.slice(1);
                params[paramName] = decodeURIComponent(pathPart);
            }
            // 静态段必须完全匹配
            else if (patternPart !== pathPart) {
                return null;
            }
        }

        return params;
    }

    /**
     * 解析查询字符串
     * @param {string} queryString - 查询字符串
     * @returns {object} - 查询参数对象
     */
    parseQuery(queryString) {
        if (!queryString) return {};

        const params = {};
        const pairs = queryString.split('&');

        for (const pair of pairs) {
            const [key, value] = pair.split('=');
            if (key) {
                params[decodeURIComponent(key)] = value ? decodeURIComponent(value) : '';
            }
        }

        return params;
    }

    /**
     * 构建查询字符串
     * @param {object} params - 参数对象
     * @returns {string} - 查询字符串
     */
    buildQuery(params) {
        const pairs = [];
        for (const [key, value] of Object.entries(params)) {
            if (value !== null && value !== undefined && value !== '') {
                pairs.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
            }
        }
        return pairs.length > 0 ? '?' + pairs.join('&') : '';
    }
}

// 创建全局路由实例
const router = new Router();
