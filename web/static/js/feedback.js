// Feedback System Logic

document.addEventListener('DOMContentLoaded', () => {
    // Note: The HTML structure is statically added to index.html in the plan,
    // so we don't need to inject HTML here, just bind events.
    initFeedbackSystem();
});

function initFeedbackSystem() {
    const feedbackOverlay = document.getElementById('feedback-overlay');
    const openBtn = document.getElementById('feedback-entry-card');
    const closeBtn = document.getElementById('feedback-close-btn');
    const submitBtn = document.getElementById('feedback-submit-btn');
    const form = document.getElementById('feedback-form');

    // Tab Elements
    const tabSubmit = document.getElementById('fb-tab-submit');
    const tabWall = document.getElementById('fb-tab-wall');
    const viewSubmit = document.getElementById('fb-view-submit');
    const viewWall = document.getElementById('fb-view-wall');

    if (!feedbackOverlay || !openBtn) return;

    // Open Modal
    openBtn.addEventListener('click', () => {
        feedbackOverlay.classList.add('active');
        document.body.style.overflow = 'hidden'; // Prevent scrolling

        // Reset to default tab (Submit) when opening? Or keep last state?
        // Let's reset to Submit for better UX
        switchTab('submit');
    });

    // Close Modal
    const closeModal = () => {
        feedbackOverlay.classList.remove('active');
        document.body.style.overflow = '';
        // Reset form after transition
        setTimeout(() => {
            if (form) form.reset();
            const submitText = submitBtn.querySelector('.btn-text');
            if (submitText) submitText.textContent = '提交反馈';
            submitBtn.disabled = false;
        }, 300);
    };

    if (closeBtn) closeBtn.addEventListener('click', closeModal);

    // Click outside to close
    feedbackOverlay.addEventListener('click', (e) => {
        if (e.target === feedbackOverlay) {
            closeModal();
        }
    });

    // Tab Switching Logic
    function switchTab(tabName) {
        // Page Turn Animation Logic
        // [ Submit ] --Left--> [ Wall ]
        // Submit is "Left Page", Wall is "Right Page"? 
        // Or linear sequence. Let's assume linear: Submit(0) -> Wall(1)

        if (tabName === 'submit') {
            // Moving Back: Wall(1) -> Submit(0)
            // Wall slides out to Right
            viewWall.classList.remove('active', 'slide-left');
            viewWall.classList.add('slide-right');

            // Submit slides in from Left
            viewSubmit.classList.remove('slide-right', 'slide-left');
            viewSubmit.classList.add('active');

            tabSubmit.classList.add('active');
            tabWall.classList.remove('active');
        } else {
            // Moving Forward: Submit(0) -> Wall(1)
            // Submit slides out to Left
            viewSubmit.classList.remove('active', 'slide-right');
            viewSubmit.classList.add('slide-left');

            // Wall slides in from Right
            viewWall.classList.remove('slide-right', 'slide-left');
            viewWall.classList.add('active');

            tabSubmit.classList.remove('active');
            tabWall.classList.add('active');

            loadFeedbackWall();
        }
    }

    if (tabSubmit) tabSubmit.addEventListener('click', () => switchTab('submit'));
    if (tabWall) tabWall.addEventListener('click', () => switchTab('wall'));


    // Dynamic Placeholder Logic
    const typeInputs = document.querySelectorAll('input[name="feedback-type"]');
    const contentInput = document.getElementById('feedback-content');

    if (contentInput && typeInputs.length > 0) {
        const placeholders = {
            'bug': '哦莫，请告诉我们复现步骤，我们会尽快消灭它:O',
            'suggestion': '有更好的想法？欢迎您提出宝贵的优化建议，帮助我们做得更好(^^*)',
            'wish': '想要什么新功能？许个愿吧，万一实现了呢……!!!'
        };

        typeInputs.forEach(input => {
            input.addEventListener('change', () => {
                if (placeholders[input.value]) {
                    contentInput.placeholder = placeholders[input.value];
                }
            });
        });
    }

    // Handle Submit
    if (submitBtn) {
        submitBtn.addEventListener('click', async (e) => {
            e.preventDefault();

            const typeInput = document.querySelector('input[name="feedback-type"]:checked');
            const contentInput = document.getElementById('feedback-content');
            const contactInput = document.getElementById('feedback-contact');

            if (!contentInput || !contentInput.value.trim()) {
                alert('请填写反馈内容');
                contentInput.focus();
                return;
            }

            const data = {
                type: typeInput ? typeInput.value : 'suggestion',
                content: contentInput.value.trim(),
                contact: contactInput ? contactInput.value.trim() : ''
            };

            // UI Loading State & Animation
            submitBtn.disabled = true;
            const textSpan = submitBtn.querySelector('.btn-text');
            const originalText = textSpan ? textSpan.textContent : '提交反馈';
            if (textSpan) textSpan.textContent = '投递中...';

            // Add flying animation class
            const modal = document.querySelector('.feedback-modal');
            if (modal) modal.classList.add('flying');

            try {
                // Wait a bit for animation start before request, or parallel?
                // Visual effect first: 1s animation
                const animationPromise = new Promise(resolve => setTimeout(resolve, 800));

                const fetchPromise = fetch('/api/feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const [_, response] = await Promise.all([animationPromise, fetchPromise]);

                if (response.ok) {
                    if (textSpan) textSpan.textContent = '已送达 ✓';

                    // Already flew away, just close overlay
                    setTimeout(() => {
                        closeModal();

                        // 0.5s Delay -> Celebration
                        setTimeout(() => {
                            showCelebration();
                        }, 500);

                        // Reset style & animation class after close
                        setTimeout(() => {
                            if (modal) modal.classList.remove('flying');
                            submitBtn.style.background = '';
                        }, 300);
                    }, 200);
                } else {
                    let errMsg = '未知错误';
                    try {
                        const err = await response.json();
                        errMsg = err.error || errMsg;
                    } catch (e) {
                        // Fallback for non-JSON errors (e.g. 500 HTML)
                        errMsg = `服务器错误 (${response.status})`;
                    }

                    alert('提交失败: ' + errMsg);
                    submitBtn.disabled = false;
                    if (textSpan) textSpan.textContent = originalText;
                    if (modal) modal.classList.remove('flying'); // Reset position if failed
                }
            } catch (error) {
                console.error('Feedback error:', error);
                alert('网络错误，请稍后重试');
                submitBtn.disabled = false;
                if (textSpan) textSpan.textContent = originalText;
                if (modal) modal.classList.remove('flying');
            }
        });
    }
}

async function loadFeedbackWall() {
    const container = document.getElementById('feedback-wall-list');
    if (!container) return;

    container.innerHTML = '<div style="text-align:center; padding:20px; color:#999;">加载精选反馈...</div>';

    try {
        const res = await fetch('/api/feedbacks/public');
        if (!res.ok) throw new Error("Failed");
        const data = await res.json();

        const results = data.results || [];

        if (results.length === 0) {
            container.innerHTML = `
                <div class="wall-empty">
                    <i class="material-icons" style="font-size:48px; opacity:0.2;">inbox</i>
                    <p>暂时还没有精选反馈</p>
                    <p style="font-size:0.8rem;">快去提交第一条建议吧</p>
                </div>
            `;
            return;
        }

        container.innerHTML = results.map(item => {
            const typeMap = {
                'bug': { label: '🐞 Bug反馈', cls: 'bug' },
                'suggestion': { label: '💡 优化建议', cls: 'suggestion' },
                'wish': { label: '✨ 许愿池', cls: 'wish' }
            };
            const typeInfo = typeMap[item.type] || typeMap['suggestion'];
            const timeStr = new Date(item.created_at).toLocaleDateString();

            let replyHtml = '';
            if (item.admin_reply) {
                replyHtml = `
                    <div class="dev-reply">
                        <div class="dev-avatar">
                            <i class="material-icons" style="font-size:14px;">code</i>
                        </div>
                        <div class="dev-text">
                            <strong>开发者回复：</strong> ${escapeHtml(item.admin_reply)}
                        </div>
                    </div>
                `;
            }

            // 已解决状态标签
            const resolvedTag = item.status === 'closed'
                ? '<span class="wall-tag resolved">✅ 已解决</span>'
                : '';

            return `
                <div class="wall-card ${item.status === 'closed' ? 'resolved' : ''}">
                    <div class="wall-header">
                        <span class="wall-tag ${typeInfo.cls}">${typeInfo.label}</span>
                        ${resolvedTag}
                        <span class="wall-time">${timeStr}</span>
                    </div>
                    <div class="wall-content">${escapeHtml(item.content)}</div>
                    ${replyHtml}
                </div>
            `;
        }).join('');

    } catch (e) {
        container.innerHTML = '<div style="text-align:center; color:red; padding:20px;">加载失败，请稍后重试</div>';
    }
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function showCelebration() {
    const overlay = document.getElementById('celebration-overlay');
    const hint = document.getElementById('close-hint');
    if (!overlay) return;

    overlay.classList.add('active');
    if (hint) hint.classList.remove('visible');

    spawnConfetti();

    // Show hint after 3s
    const hintTimer = setTimeout(() => {
        if (hint && overlay.classList.contains('active')) {
            hint.classList.add('visible');
        }
    }, 3000);

    // Click to close
    const closeHandler = () => {
        overlay.classList.remove('active');
        if (hint) hint.classList.remove('visible');
        clearTimeout(hintTimer); // Stop hint if closed early

        overlay.removeEventListener('click', closeHandler);
        // Clean confetti
        const container = document.getElementById('confetti-container');
        if (container) container.innerHTML = '';
    };
    overlay.addEventListener('click', closeHandler);

    // Auto close logic removed as per user preference (manual close)
}

function spawnConfetti() {
    const container = document.getElementById('confetti-container');
    if (!container) return;
    container.innerHTML = ''; // Clear prev

    const colors = ['#ff9800', '#4caf50', '#ffeb3b']; // Orange, Green, Yellow

    // Origin: Right side, slightly top (where plane flew)
    // "From place where it disappeared" -> ~ Top 20%, Right 0%
    const particleCount = 60;

    for (let i = 0; i < particleCount; i++) {
        const el = document.createElement('div');
        el.classList.add('confetti');

        // Random color
        el.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];

        // Initial Position: Right Edge
        el.style.right = '-20px';
        el.style.top = '20%'; // Approx height where plane exits

        // Trajectory
        // Spray outwards: Left and Down/Up spread
        const angle = 135 + (Math.random() * 90 - 45); // Aim left (180) +/- 45deg -> 135 to 225? 
        // No, 180 is left. 
        // Plane went Top-Right (45deg). Confetti should probably explode *from* there *outwards*?
        // Or spray *into* the screen?
        // "Spray out some confetti" -> implies entering the screen from that spot.
        // So Moving Left (-X) and varying Y.

        // Random destination
        const flyX = -1 * (300 + Math.random() * 500); // 300 to 800px Left
        const flyY = (Math.random() * 600) - 300; // -300 to +300px Up/Down

        el.style.setProperty('--tx', `${flyX}px`);
        el.style.setProperty('--ty', `${flyY}px`);

        // Random animation duration
        const duration = 1 + Math.random() * 1.5;
        el.style.animation = `confettiFall ${duration}s ease-out forwards`;

        // Random delay
        el.style.animationDelay = `${Math.random() * 0.2}s`;

        container.appendChild(el);
    }
}
