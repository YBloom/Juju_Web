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

    if (!feedbackOverlay || !openBtn) return;

    // Open Modal
    openBtn.addEventListener('click', () => {
        feedbackOverlay.classList.add('active');
        document.body.style.overflow = 'hidden'; // Prevent scrolling
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

            // UI Loading State
            submitBtn.disabled = true;
            const textSpan = submitBtn.querySelector('.btn-text');
            const originalText = textSpan ? textSpan.textContent : '提交反馈';
            if (textSpan) textSpan.textContent = '提交中...';

            try {
                const response = await fetch('/api/feedback', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    if (textSpan) textSpan.textContent = '提交成功 ✓';
                    submitBtn.style.background = '#4CAF50';
                    setTimeout(() => {
                        closeModal();
                        // Reset style
                        setTimeout(() => {
                            submitBtn.style.background = '';
                        }, 300);
                    }, 1000);
                } else {
                    const err = await response.json();
                    alert('提交失败: ' + (err.error || '未知错误'));
                    submitBtn.disabled = false;
                    if (textSpan) textSpan.textContent = originalText;
                }
            } catch (error) {
                console.error('Feedback error:', error);
                alert('网络错误，请稍后重试');
                submitBtn.disabled = false;
                if (textSpan) textSpan.textContent = originalText;
            }
        });
    }
}
