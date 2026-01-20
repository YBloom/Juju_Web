import { api } from '../api.js';
import { UI } from './ui_shared.js';
import AnimalAvatarRaw from 'animal-avatar-generator';

// Handle various import scenarios (ESM/CommonJS interop)
let AnimalAvatar = AnimalAvatarRaw;
if (AnimalAvatarRaw && AnimalAvatarRaw.default) {
    AnimalAvatar = AnimalAvatarRaw.default;
}

window.AnimalAvatar = AnimalAvatar;
window.UI = UI;

let avatarGen = null;
try {
    if (typeof AnimalAvatar === 'function') {
        avatarGen = new AnimalAvatar();
    } else {
        console.error('AnimalAvatar is not a constructor:', AnimalAvatar);
    }
} catch (e) {
    console.error('Failed to initialize AnimalAvatar:', e);
}

export function renderAvatarImg(user, customStyle = '') {
    if (!user) user = {};
    const style = customStyle || 'width:100%;height:100%;object-fit:cover;';

    if (user.avatar_url) {
        return `<img src="${user.avatar_url}" style="${style}" onerror="this.onerror=null; console.error('Avatar load failed:', this.src); UI.toast('头像加载失败', 'error'); this.style.display='none';">`;
    }
    // Specific check for 'user_' prefix to avoid generating for emails if wanted, but generally we want avatars for everyone.
    // Use user_id or email as seed.
    const seed = user.user_id || user.email || 'guest';

    // Re-attempt Init if null
    if (!avatarGen && typeof AnimalAvatar === 'function') {
        try {
            avatarGen = new AnimalAvatar();
        } catch (e) {
            console.error(e);
        }
    }

    if (avatarGen) {
        const svg = avatarGen.generate(seed);
        // If we have custom style, we should probably wrap the SVG or inject the style if it's a string
        if (customStyle) {
            return `<div style="${customStyle}">${svg}</div>`;
        }
        return svg;
    }
    return user.nickname ? user.nickname[0].toUpperCase() : 'U';
}

// Global Avatar Functions

window.triggerAvatarUpload = () => {
    document.getElementById('avatar-input').click();
};

window.shuffleAvatar = () => {
    const avatarContainer = document.getElementById('profile-avatar');
    if (avatarGen) {
        // Generate random seed
        const randomSeed = Math.random().toString(36).substring(7);
        const svg = avatarGen.generate(randomSeed);
        avatarContainer.innerHTML = svg;

        // Show save button
        const saveActions = document.getElementById('avatar-save-actions');
        if (saveActions) {
            saveActions.style.display = 'flex';
            saveActions.dataset.tempSeed = randomSeed;
            saveActions.dataset.type = 'generated';
        }
    }
};

window.saveCurrentAvatar = async () => {
    const saveActions = document.getElementById('avatar-save-actions');
    const statusEl = document.getElementById('save-status');
    const type = saveActions.dataset.type;

    // UI Loading state
    const originalBtn = saveActions.innerHTML;
    saveActions.innerHTML = '<div class="spinner"></div> 保存中...';

    try {
        if (type === 'generated') {
            const seed = saveActions.dataset.tempSeed;
            if (seed) {
                // Determine SVG content
                // Re-generate to get SVG string
                if (!avatarGen && typeof AnimalAvatar === 'function') {
                    avatarGen = new AnimalAvatar();
                }

                if (avatarGen) {
                    const svg = avatarGen.generate(seed);

                    // Convert SVG to Data URL or Blob to upload?
                    // Actually the backend might support saving current 'seed' if we had a field for it, 
                    // but here we probably want to save the SVG image or just the seed.
                    // However, the original code logic for 'shuffle' wasn't fully shown in snippets.
                    // Let's assume we upload the SVG as a file, or if backend supports 'avatar_seed'.
                    // Looking at API, we have `updateUserSettings({ avatar_url: ... })`.
                    // If we generate an SVG locally, we need to convert it to a file and upload it.
                    // OR, we just use the seed logic if the backend supported it.
                    // But `avatar_url` implies a static file.
                    // Let's try to convert SVG to Blob and upload.

                    const blob = new Blob([svg], { type: 'image/svg+xml' });
                    const file = new File([blob], 'avatar.svg', { type: 'image/svg+xml' });

                    // Reuse upload logic?
                    // Check if `api` has upload function. 
                    // `api.js` usually handles JSON. 
                    // We might need a separate upload endpoint.
                    // Original ui.js logic for shuffle saving:
                    /*
                       It wasn't explicit. Ideally we should have an endpoint to upload avatar.
                       Let's assume there is one: POST /api/user/avatar/upload
                    */

                    const formData = new FormData();
                    formData.append('file', file);

                    // Use fetch directly for upload as api wrapper might be JSON only
                    const res = await fetch('/api/user/avatar/upload', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await res.json();
                    if (data.url) {
                        await api.updateUserSettings({ avatar_url: data.url });
                    }
                }
            }

            saveActions.style.display = 'none';
            if (statusEl) {
                statusEl.innerHTML = '<span style="color:var(--primary-color)">头像更新成功</span>';
                setTimeout(() => statusEl.innerHTML = '', 2000);
            }
        } catch (e) {
            console.error(e);
            alert('保存失败: ' + e.message);
            saveActions.innerHTML = originalBtn;
        }
    };

    window.handleAvatarFileSelect = (e) => {
        const file = e.target.files[0];
        if (!file) return;

        // Show Cropper Modal
        showCropModal(file);
        e.target.value = ''; // Reset input
    };

    // Crop Modal Logic
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
                    <button onclick="closeCropModal()" style="padding:8px 20px;background:#eee;color:333;border:none;border-radius:6px;cursor:pointer;">取消</button>
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

    window.confirmCrop = () => { // Exported to window for HTML onclick
        if (!cropper) return;

        const progress = document.getElementById('crop-progress');
        progress.innerText = '正在处理...';

        cropper.getCroppedCanvas({
            width: 300,
            height: 300,
            fillColor: '#fff',
            imageSmoothingEnabled: true,
            imageSmoothingQuality: 'high',
        }).toBlob(async (blob) => {
            if (!blob) {
                alert('裁切失败');
                return;
            }

            progress.innerText = '正在上传...';

            try {
                // 1. Get Presigned URL
                const timestamp = new Date().getTime();
                // Use WebP for efficiency
                const filename = `avatar_${timestamp}.webp`;

                const urlRes = await fetch(`/api/avatar/upload-url?filename=${filename}&content_type=image/webp`);
                if (!urlRes.ok) throw new Error('无法获取上传授权');

                const { upload_url, public_url } = await urlRes.json();

                // 2. Upload to S3 directly
                const uploadRes = await fetch(upload_url, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'image/webp'
                    },
                    body: blob
                });

                if (!uploadRes.ok) throw new Error('上传S3失败');

                // 3. Update Profile
                progress.innerText = '更新个人资料...';
                // Use the public_url returned from sign endpoint
                await api.updateUserSettings({ avatar_url: public_url });

                // 4. Update UI
                closeCropModal();
                const avatarContainer = document.querySelector('#profile-avatar');
                // Re-render with new URL. If we used HTML, replace innerHTML.
                if (avatarContainer) {
                    // Ensure layout is correct (img inside div)
                    console.log("Updating avatar UI with:", public_url);
                    avatarContainer.innerHTML = `<img src="${public_url}" style="width:100%; height:100%; object-fit:cover;" onerror="console.error('Failed to load avatar:', this.src); UI.toast('头像图片加载失败，请检查网络', 'error');">`;
                }

                // Hide save button if visible
                const saveActions = document.getElementById('avatar-save-actions');
                if (saveActions) saveActions.style.display = 'none';

            } catch (e) {
                console.error(e);
                alert('上传失败: ' + e.message);
                closeCropModal();
            }
        }, 'image/webp', 0.85);
    };
