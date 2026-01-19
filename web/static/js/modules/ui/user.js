
import { api } from '../api.js';
import { escapeHtml } from '../utils.js';
import { router } from '../router.js';
import { renderAvatarImg } from './avatar.js';

export async function initUserTab() {
    const container = document.getElementById('user-profile-container');
    container.innerHTML = '<div class="loading-spinner"></div>';

    try {
        const authData = await api.checkLogin();
        if (!authData || !authData.authenticated) {
            renderLoginPrompt(container);
        } else {
            const settings = await api.fetchUserSettings();
            renderUserProfile(container, settings || authData.user);
        }
    } catch (e) {
        console.error("User init error:", e);
        renderLoginPrompt(container);
    }
}

function renderLoginPrompt(container) {
    container.innerHTML = `
        <div class="login-container" style="max-width:480px; margin:0 auto; padding:20px;">
            <div style="text-align:center; margin-bottom:30px; padding:25px 20px; background:linear-gradient(135deg, rgba(99, 126, 96, 0.05) 0%, rgba(99, 126, 96, 0.02) 100%); border-radius:16px; border:1px solid rgba(99, 126, 96, 0.1);">
                <div style="font-size:2.5rem; margin-bottom:12px;">🎭</div>
                <h2 style="margin:0 0 12px 0; font-size:1.5rem; color:var(--text-primary); font-weight:700;">欢迎来到剧剧</h2>
                <p style="margin:0; color:var(--text-secondary); font-size:0.95rem;">登录后可管理订阅和接收推送</p>
            </div>

            <div class="login-tabs" style="display:flex; gap:10px; margin-bottom:25px; background:#f5f5f5; border-radius:12px; padding:5px;">
                <button id="tab-login" class="login-tab active" onclick="switchAuthTab('login')" style="flex:1; padding:12px; border:none; background:white; border-radius:10px; font-weight:600; cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,0.05);">登录</button>
                <button id="tab-register" class="login-tab" onclick="switchAuthTab('register')" style="flex:1; padding:12px; border:none; background:transparent; border-radius:10px; font-weight:500; cursor:pointer; color:#666;">注册</button>
            </div>

            <div id="view-login" class="auth-view">
                <form id="login-form" onsubmit="handleEmailLogin(event)">
                    <div style="margin-bottom:15px;">
                        <label style="font-size:0.9rem; color:#666; margin-bottom:6px; display:block;">邮箱地址</label>
                        <input type="email" id="login-email" required placeholder="your@email.com" style="width:100%; padding:14px 16px; border:1px solid #e0e0e0; border-radius:12px; font-size:1rem; box-sizing:border-box;">
                    </div>
                    <div style="margin-bottom:15px;">
                        <label style="font-size:0.9rem; color:#666; margin-bottom:6px; display:block;">密码</label>
                        <input type="password" id="login-password" required placeholder="输入密码" minlength="6" style="width:100%; padding:14px 16px; border:1px solid #e0e0e0; border-radius:12px; font-size:1rem; box-sizing:border-box;">
                    </div>
                    <div id="login-error" style="color:#ff4d4f; font-size:0.9rem; margin-bottom:10px; display:none;"></div>
                    <button type="submit" id="login-btn" style="width:100%; padding:14px; border:none; background:var(--primary-color); color:white; font-weight:600; border-radius:12px; font-size:1rem; cursor:pointer;">登录</button>
                </form>
            </div>

            <div style="display:flex; align-items:center; margin:30px 0; gap:15px;">
                <div style="flex:1; height:1px; background:#e0e0e0;"></div>
                <span style="color:#999; font-size:0.85rem;">或通过QQ机器人登录</span>
                <div style="flex:1; height:1px; background:#e0e0e0;"></div>
            </div>

            <div style="background:#f0f7ff; border:1px solid #d6e4ff; border-radius:12px; padding:16px; text-align:center;">
                <p style="margin:0 0 12px 0; color:#666; font-size:0.9rem;">向 QQ 机器人发送 <code style="background:#fff; padding:2px 8px; border-radius:4px; color:var(--primary-color);">/web</code> 获取登录链接</p>
                <button onclick="navigator.clipboard.writeText('3132859862')" style="background:#1890ff; color:white; border:none; padding:8px 16px; border-radius:8px; cursor:pointer;">复制机器人QQ: 3132859862</button>
            </div>
        </div>
    `;

    window.switchAuthTab = (tab) => {
        document.querySelectorAll('.auth-view').forEach(v => v.style.display = 'none');
        const viewEl = document.getElementById(`view-${tab}`);
        if (viewEl) viewEl.style.display = 'block';
    };

    window.handleEmailLogin = async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        const errorEl = document.getElementById('login-error');
        const btn = document.getElementById('login-btn');

        btn.disabled = true;
        btn.innerText = '登录中...';
        errorEl.style.display = 'none';

        try {
            const res = await fetch('/auth/email/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();

            if (!res.ok) throw new Error(data.error || '登录失败');
            window.location.reload();
        } catch (e) {
            errorEl.innerText = e.message;
            errorEl.style.display = 'block';
            btn.disabled = false;
            btn.innerText = '登录';
        }
    };
}

const LEVEL_CONFIG = [
    { level: 0, features: { new: false, restock: false, back: false, decrease: false, increase: false} },
    { level: 1, features: { new: true, restock: false, back: false, decrease: false, increase: false } },
    { level: 2, features: { new: true, restock: true, back: false, decrease: false, increase: false } },
    { level: 3, features: { new: true, restock: true, back: true, decrease: false, increase: false } },
    { level: 4, features: { new: true, restock: true, back: true, decrease: true, increase: false } },
    { level: 5, features: { new: true, restock: true, back: true, decrease: true, increase: true } }
];

const FEATURE_LABELS = {
    new: '上新',
    restock: '补票',
    back: '回流',
    decrease: '票减',
    increase: '票增'
};

function renderUserProfile(container, user) {
    const globalLevel = user.global_notification_level !== undefined ? user.global_notification_level : 2;

    container.innerHTML = `
        <div class="user-card" style="background:#fff; border-radius:16px; box-shadow:0 4px 20px rgba(0,0,0,0.05); overflow:hidden;">
            <div style="padding:30px 20px; text-align:center; background:linear-gradient(180deg, #f9fafb 0%, #fff 100%); border-bottom:1px solid #eee;">
                <div style="position:relative; width:88px; height:88px; margin:0 auto 16px;">
                    <div id="profile-avatar" style="width:100%; height:100%; border-radius:50%; box-shadow:0 4px 12px rgba(0,0,0,0.08); border:3px solid #fff; overflow:hidden;">
                        ${renderAvatarImg(user, 'width:100%; height:100%; object-fit:cover;')}
                    </div>
                    
                    <button onclick="document.getElementById('avatar-input').click()" title="上传图片"
                        style="position:absolute; bottom:0; right:0; background:var(--primary-color); color:white; border:2px solid #fff; border-radius:50%; width:32px; height:32px; display:flex; align-items:center; justify-content:center; cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,0.15); z-index:2;">
                        <i class="material-icons" style="font-size:16px;">camera_alt</i>
                    </button>

                    <button onclick="shuffleAvatar()" title="随机生成"
                        style="position:absolute; bottom:0; left:0; background:#fff; color:#666; border:2px solid #edeff2; border-radius:50%; width:32px; height:32px; display:flex; align-items:center; justify-content:center; cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,0.15); z-index:2;">
                        <i class="material-icons" style="font-size:16px;">shuffle</i>
                    </button>
                </div>
                
                <div id="avatar-save-actions" style="display:none; justify-content:center; margin-bottom:10px; gap:10px;">
                     <button onclick="saveCurrentAvatar()" style="background:var(--primary-color); color:white; border:none; padding:4px 12px; border-radius:20px; font-size:0.8rem; cursor:pointer; display:flex; align-items:center; gap:4px;">
                        <i class="material-icons" style="font-size:14px;">check</i> 保存
                     </button>
                </div>
                
                <input type="file" id="avatar-input" accept="image/*" style="display:none;" onchange="handleAvatarFileSelect(event)">

                <div style="margin-bottom:8px; display:flex; align-items:center; justify-content:center; gap:8px;">
                    <h2 id="profile-nickname" style="margin:0; font-size:1.3rem; font-weight:700; color:#333;">${escapeHtml(user.nickname || 'Guest')}</h2>
                    <i class="material-icons" onclick="enableNicknameEdit()" style="font-size:1.1rem; color:#999; cursor:pointer;">edit</i>
                </div>
                
                <div style="display:flex; gap:8px; justify-content:center; flex-wrap:wrap;">
                    <!-- ID hidden -->
                    ${user.is_admin ? '<span style="background:#fff7e6; color:#fa8c16; padding:4px 10px; border-radius:20px; font-size:0.75rem; border:1px solid #ffd591;">管理员</span>' : ''}
                </div>

                <div id="edit-nickname-area" style="display:none; margin-top:15px; max-width:240px; margin:0 auto;">
                    <div style="display:flex; gap:8px;">
                        <input type="text" id="new-nickname" value="${escapeHtml(user.nickname || '')}" placeholder="新昵称"
                            style="flex:1; padding:8px 12px; border:1px solid #ddd; border-radius:8px; font-size:0.9rem;">
                        <button onclick="saveNickname()" style="background:var(--primary-color); color:white; border:none; border-radius:8px; padding:0 12px; cursor:pointer;">保存</button>
                        <button onclick="document.getElementById('edit-nickname-area').style.display='none'" style="background:#f5f5f5; color:#666; border:none; border-radius:8px; padding:0 12px; cursor:pointer;">取消</button>
                    </div>
                </div>
            </div>

            <div style="padding:24px;">
                <div style="margin-bottom:30px;">
                    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px;">
                        <h3 style="margin:0; font-size:1.05rem; color:#333; font-weight:600;">全局推送级别</h3>
                        <span id="save-status" style="font-size:0.8rem;"></span>
                    </div>

                    <p style="font-size:0.85rem; color:#666; margin-bottom:12px; line-height:1.5;">
                        这是您接收通知的<b>最低门槛</b>。特定订阅可以设置更高的级别，但永远不会低于此全局设定。
                    </p>
                    
                    <div class="level-selector-table" style="border:1px solid #eee; border-radius:12px; overflow:hidden;">
                        ${LEVEL_CONFIG.map(cfg => {
        const isSelected = globalLevel === cfg.level;
        return `
                            <div class="level-row ${isSelected ? 'selected' : ''}" 
                                 onclick="handleGlobalLevelChange(this, ${cfg.level})"
                                 style="display:flex; align-items:center; padding:10px 16px; border-bottom:1px solid #f5f5f5; cursor:pointer; background:${isSelected ? '#f6ffed' : '#fff'}; transition:all 0.2s;">
                                
                                <div style="flex:0 0 30px; display:flex; align-items:center; justify-content:center; margin-right:12px;">
                                    <div class="radio-indicator" style="width:18px; height:18px; border-radius:50%; border:2px solid ${isSelected ? 'var(--primary-color)' : '#ddd'}; display:flex; align-items:center; justify-content:center;">
                                        ${isSelected ? '<div style="width:10px; height:10px; border-radius:50%; background:var(--primary-color);"></div>' : ''}
                                    </div>
                                </div>

                                <div style="flex:0 0 50px; font-weight:600; color:#333; font-size:0.9rem;">Lv.${cfg.level}</div>

                                <div style="flex:1; display:flex; gap:12px; justify-content:flex-start;">
                                    ${Object.entries(FEATURE_LABELS).map(([key, label]) => {
            const enabled = cfg.features[key];
            return `
                                        <span style="font-size:0.8rem; color:${enabled ? (isSelected ? 'var(--primary-color)' : '#52c41a') : '#ddd'}; display:flex; align-items:center; gap:2px;">
                                            ${enabled ? '✅' : '⬜'} ${label}
                                        </span>
                                        `;
        }).join('')}
                                </div>
                            </div>
                            `;
    }).join('')}
                    </div>
                </div>

                <div style="border-top:1px solid #f0f0f0; padding-top:24px;">
                    <h3 style="margin:0 0 16px 0; font-size:1.05rem; color:#333; font-weight:600;">更多功能</h3>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
                        <div onclick="router.navigate('/user/subscriptions')" 
                             style="background:#f9fafb; padding:16px; border-radius:12px; cursor:pointer; text-align:center; transition:0.2s;"
                             onmouseover="this.style.background='#f0f2f5'" onmouseout="this.style.background='#f9fafb'">
                            <i class="material-icons" style="color:var(--primary-color); font-size:24px; margin-bottom:8px;">playlist_add_check</i>
                            <div style="font-size:0.9rem; color:#333; font-weight:500;">订阅管理</div>
                            <div style="font-size:0.75rem; color:#999; margin-top:4px;">查看与编辑关注项</div>
                        </div>
                        <div style="background:#f9fafb; padding:16px; border-radius:12px; text-align:center; opacity:0.6; cursor:not-allowed;">
                            <i class="material-icons" style="color:#aaa; font-size:24px; margin-bottom:8px;">history</i>
                            <div style="font-size:0.9rem; color:#aaa; font-weight:500;">推送历史</div>
                            <div style="font-size:0.75rem; color:#ccc; margin-top:4px;">(开发中)</div>
                        </div>
                    </div>
                </div>
            </div>

            <div style="padding:20px; text-align:center;">
                <button onclick="handleLogout()" style="color:#ff4d4f; background:none; border:none; padding:10px 20px; font-size:0.95rem; cursor:pointer; display:flex; align-items:center; justify-content:center; width:100%;">
                    <i class="material-icons" style="margin-right:6px; font-size:1.1rem;">logout</i> 退出登录
                </button>
            </div>
        </div>
    `;

    window.handleGlobalLevelChange = async (el, level) => {
        const allRows = container.querySelectorAll('.level-row');
        allRows.forEach(row => {
            row.classList.remove('selected');
            row.style.background = '#fff';
            row.querySelector('.radio-indicator').innerHTML = '';
            row.querySelector('.radio-indicator').style.border = '2px solid #ddd';
            row.querySelectorAll('span[style*="border-radius"]').forEach(tag => {
                tag.style.background = '#f5f5f5';
                tag.style.color = '#999';
            });
        });

        el.classList.add('selected');
        el.style.background = '#f6ffed';
        el.querySelector('.radio-indicator').innerHTML = '<div style="width:10px; height:10px; border-radius:50%; background:var(--primary-color);"></div>';
        el.querySelector('.radio-indicator').style.border = '2px solid var(--primary-color)';
        el.querySelectorAll('span[style*="border-radius"]').forEach(tag => {
            tag.style.background = 'rgba(82,196,26,0.1)';
            tag.style.color = 'var(--primary-color)';
        });

        const statusEl = document.getElementById('save-status');
        try {
            statusEl.innerHTML = '<span style="color:#666;">保存中...</span>';
            await api.updateGlobalLevel(level);
            statusEl.innerHTML = '<span style="color:var(--primary-color);">已保存</span>';
            setTimeout(() => statusEl.innerHTML = '', 2000);
        } catch (err) {
            console.error(err);
            statusEl.innerHTML = '<span style="color:#ff4d4f;">保存失败</span>';
            alert('设置更新失败: ' + err.message);
        }
    };

    window.enableNicknameEdit = () => {
        document.getElementById('edit-nickname-area').style.display = 'block';
        document.getElementById('new-nickname').focus();
    };

    window.saveNickname = async () => {
        const newName = document.getElementById('new-nickname').value.trim();
        if (!newName) return alert("昵称不能为空");

        try {
            await api.updateUserSettings({ nickname: newName });
            document.getElementById('profile-nickname').innerText = newName;
            document.getElementById('edit-nickname-area').style.display = 'none';
        } catch (e) {
            alert("保存失败: " + e.message);
        }
    };
}

window.handleLogout = async () => {
    if (confirm('确定要退出登录吗？')) {
        await api.logout();
        window.location.reload();
    }
};

export const doLogout = window.handleLogout;
