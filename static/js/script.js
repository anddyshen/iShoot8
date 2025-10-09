// static/js/script.js
// 版本: 1.0.0
document.addEventListener('DOMContentLoaded', function() {
    // 可以在这里添加一些全局的JavaScript交互逻辑
    console.log("iShoot website loaded.");

    // --- 历史数据页面彩球高亮逻辑 ---
    const historyTableContainer = document.querySelector('.table-responsive');

    if (historyTableContainer) {
        historyTableContainer.addEventListener('mouseover', function(event) {
            const targetBall = event.target.closest('.lottery-ball');
            if (targetBall) {
                const ballNumber = targetBall.dataset.number;
                const ballType = targetBall.dataset.type;

                if (ballNumber && ballType) {
                    // 移除所有现有的高亮
                    document.querySelectorAll('.lottery-ball.highlighted').forEach(ball => {
                        ball.classList.remove('highlighted');
                    });

                    // 高亮所有匹配的彩球
                    document.querySelectorAll(`.lottery-ball[data-number="${ballNumber}"][data-type="${ballType}"]`).forEach(ball => {
                        ball.classList.add('highlighted');
                    });
                }
            }
        });

        historyTableContainer.addEventListener('mouseout', function(event) {
            // 鼠标移开时，移除所有高亮
            document.querySelectorAll('.lottery-ball.highlighted').forEach(ball => {
                ball.classList.remove('highlighted');
            });
        });
    }
});
