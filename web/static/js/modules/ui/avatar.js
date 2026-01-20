import { api } from '../api.js';
import { UI } from './ui_shared.js';
import AnimalAvatarRaw from 'animal-avatar-generator';

/**
 * 头像模块 - 处理随机头像生成、裁切与上传 S3
 * 修复了 AnimalAvatar 导入兼容性问题及语法错误
 */

// 处理不同的导入场景 (ESM/CommonJS 互操作性)
console.log('Raw AnimalAvatar Import:', AnimalAvatarRaw);
let AnimalAvatar = AnimalAvatarRaw;
if (AnimalAvatarRaw && typeof AnimalAvatarRaw === 'object' && AnimalAvatarRaw.default) {
    AnimalAvatar = AnimalAvatarRaw.default;
    console.log('Used AnimalAvatar.default');
}
console.log('Final AnimalAvatar Constructor:', AnimalAvatar);

// 暴露给全局以便 HTML onclick 使用 (虽然建议用事件监听，但目前代码结构如此)
window.AnimalAvatar = AnimalAvatar;
window.UI = UI;

let avatarGen = null;
const initAvatarGen = () => {
    if (avatarGen) return avatarGen;
    try {
        if (typeof AnimalAvatar === 'function') {
            avatarGen = new AnimalAvatar();
            return avatarGen;
        } else {
            console.warn('AnimalAvatar is not a constructor:', AnimalAvatar);
            return null;
        }
    } catch (e) {
        console.error('Failed to initialize AnimalAvatar:', e);
        return null;
    }
};

// 初始尝试实例化
initAvatarGen();

export function renderAvatarImg(user, customStyle = '') {
    if (!user) user = {};
    const style = customStyle || 'width:100%;height:100%;object-fit:cover;';

    if (user.avatar_url) {
        return `<img src="${user.avatar_url}" style="${style}" onerror="this.onerror=null; console.error('Avatar load failed:', this.src); UI.toast('头像加载失败', 'error'); this.style.display='none';">`;
    }

    const seed = user.user_id || user.email || 'guest';
    const gen = initAvatarGen();

    if (gen) {
        try {
            const svg = gen.generate(seed);
            if (customStyle) {
                return `<div style="${customStyle}">${svg}</div>`;
            }
            return svg;
        } catch (e) {
            console.error('SVG Generation error:', e);
        }
    }
    return user.nickname ? user.nickname[0].toUpperCase() : 'U';
}

// --- 全局头像功能 ---

window.triggerAvatarUpload = () => {
    const input = document.getElementById('avatar-input');
    if (input) input.click();
};

window.shuffleAvatar = () => {
    const avatarContainer = document.getElementById('profile-avatar');
    const gen = initAvatarGen();
    if (gen && avatarContainer) {
        const randomSeed = Math.random().toString(36).substring(7);
        const svg = gen.generate(randomSeed);
        avatarContainer.innerHTML = svg;

        const saveActions = document.getElementById('avatar-save-actions');
        if (saveActions) {
            saveActions.style.display = 'flex';
            saveActions.dataset.tempSeed = randomSeed;
            saveActions.dataset.type = 'generated';
        }
    } else {
        UI.toast('头像生成器未准备就绪', 'error');
    }
};

window.saveCurrentAvatar = async () => {
    const saveActions = document.getElementById('avatar-save-actions');
    const statusEl = document.getElementById('save-status');
    if (!saveActions) return;

    const type = saveActions.dataset.type;
    const originalBtn = saveActions.innerHTML;
    saveActions.innerHTML = '<div class="spinner"></div> 保存中...';

    try {
        if (type === 'generated') {
            const seed = saveActions.dataset.tempSeed;
            const gen = initAvatarGen();
            if (seed && gen) {
                const svg = gen.generate(seed);
                const blob = new Blob([svg], { type: 'image/svg+xml' });
                const file = new File([blob], 'avatar.svg', { type: 'image/svg+xml' });

                const formData = new FormData();
                formData.append('file', file);

                // 头像上传逻辑 (后端需支持此路径)
                const res = await fetch('/api/user/avatar/upload', {
                    method: 'POST',
                    body: formData
                });

                if (!res.ok) throw new Error('上传失败');

                const data = await res.json();
                if (data.url) {
                    await api.updateUserSettings({ avatar_url: data.url });
                }
            }
        }

        saveActions.style.display = 'none';
        if (statusEl) {
            statusEl.innerHTML = '<span style="color:var(--primary-color)">头像更新成功</span>';
            setTimeout(() => { if (statusEl) statusEl.innerHTML = ''; }, 2000);
        }
    } catch (e) {
        console.error(e);
        UI.toast('保存失败: ' + e.message, 'error');
        saveActions.innerHTML = originalBtn;
    }
};

window.handleAvatarFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    showCropModal(file);
    e.target.value = '';
};

// --- 裁切模态框逻辑 ---
let cropper = null;

function showCropModal(file) {
    let modal = document.getElementById('avatar-crop-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'avatar-crop-modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:9999;display:flex;flex-direction:column;align-items:center;justify-content:center;';
        modal.innerHTML = `
            <div style="background:white;padding:20px;border-radius:12px;width:90%;max-width:500px;text-align:center;">
                <h3 style="margin-top:0;">裁切头像</h3>
                <div style="height:300px;background:#eee;margin-bottom:20px;">
                    <img id="crop-image" style="max-width:100%;max-height:100%;">
                </div>
                <div style="display:flex;justify-content:center;gap:15px;">
                    <button onclick="confirmCrop()" style="padding:8px 20px;background:var(--primary-color);color:white;border:none;border-radius:6px;cursor:pointer;">确定</button>
                    <button onclick="closeCropModal()" style="padding:8px 20px;background:#eee;color:#333;border:none;border-radius:6px;cursor:pointer;">取消</button>
                </div>
                <div id="crop-progress" style="margin-top:10px;color:#666;font-size:0.9em;"></div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    const img = document.getElementById('crop-image');
    const reader = new FileReader();
    reader.onload = (e) => {
        img.src = e.target.result;
        modal.style.display = 'flex';

        if (cropper) cropper.destroy();
        cropper = new window.Cropper(img, {
            aspectRatio: 1,
            viewMode: 1,
            dragMode: 'move',
            autoCropArea: 1,
            responsive: true
        });
    };
    reader.readAsDataURL(file);
}

window.closeCropModal = () => {
    const modal = document.getElementById('avatar-crop-modal');
    if (modal) modal.style.display = 'none';
    if (cropper) {
        cropper.destroy();
        cropper = null;
    }
};

window.confirmCrop = () => {
    if (!cropper) return;

    const progress = document.getElementById('crop-progress');
    if (progress) progress.innerText = '正在处理...';

    cropper.getCroppedCanvas({
        width: 300,
        height: 300,
        fillColor: '#fff',
        imageSmoothingEnabled: true,
        imageSmoothingQuality: 'high',
    }).toBlob(async (blob) => {
        if (!blob) {
            UI.toast('裁切失败', 'error');
            return;
        }

        if (progress) progress.innerText = '正在上传...';

        try {
            const timestamp = new Date().getTime();
            const filename = `avatar_${timestamp}.webp`;

            // 1. 获取预签名 URL
            const urlRes = await fetch(`/api/avatar/upload-url?filename=${filename}&content_type=image/webp`);
            if (!urlRes.ok) throw new Error('无法获取上传授权');

            const { upload_url, public_url } = await urlRes.json();

            // 2. 直接上传到 S3
            const uploadRes = await fetch(upload_url, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'image/webp'
                },
                body: blob
            });

            if (!uploadRes.ok) throw new Error('上传S3失败');

            // 3. 更新个人资料
            if (progress) progress.innerText = '更新个人资料...';
            await api.updateUserSettings({ avatar_url: public_url });

            // 4. 更新 UI
            closeCropModal();
            const avatarContainer = document.querySelector('#profile-avatar');
            if (avatarContainer) {
                console.log("Updating avatar UI with:", public_url);
                avatarContainer.innerHTML = `<img src="${public_url}" style="width:100%; height:100%; object-fit:cover;" onerror="this.onerror=null; console.error('Failed to load avatar:', this.src); UI.toast('头像图片加载失败，请检查网络', 'error');">`;
            }

            const saveActions = document.getElementById('avatar-save-actions');
            if (saveActions) saveActions.style.display = 'none';

        } catch (e) {
            console.error(e);
            UI.toast('上传失败: ' + e.message, 'error');
            closeCropModal();
        }
    }, 'image/webp', 0.85);
};
