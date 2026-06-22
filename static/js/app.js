/**
 * 世界杯量化预测 - 前端交互
 * 数字滚动动画 + 概率条动画
 */
document.addEventListener('DOMContentLoaded', () => {
    animateProbNumbers();
    animateProbBars();
});

/** 概率数字滚动动画 */
function animateProbNumbers() {
    const elements = document.querySelectorAll('.prob-number[data-target]');
    elements.forEach((el, index) => {
        const target = parseInt(el.dataset.target, 10);
        if (isNaN(target)) return;

        let current = 0;
        const duration = 1200;
        const startTime = performance.now() + index * 100;

        function tick(now) {
            const elapsed = now - startTime;
            if (elapsed < 0) {
                requestAnimationFrame(tick);
                return;
            }
            const progress = Math.min(elapsed / duration, 1);
            // ease-out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            current = Math.round(eased * target);
            el.textContent = current + '%';
            if (progress < 1) {
                requestAnimationFrame(tick);
            }
        }
        requestAnimationFrame(tick);
    });
}

/** 概率条宽度动画 */
function animateProbBars() {
    const segments = document.querySelectorAll('.bar-segment[data-width]');
    segments.forEach((seg, i) => {
        const w = seg.dataset.width;
        setTimeout(() => {
            seg.style.width = w + '%';
        }, 300 + i * 80);
    });
}
