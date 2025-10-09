// static/js/script.js
// 版本: 1.0.0
document.addEventListener('DOMContentLoaded', function() {
    // 可以在这里添加一些全局的JavaScript交互逻辑
    console.log("iShoot website loaded.");

    // --- 历史数据页面彩球高亮逻辑 ---
    const historyTableContainer = document.querySelector('.table-responsive');

    if (historyTableContainer) {
        // 检测是否是触摸设备
        const isTouchDevice = () => {
            return ('ontouchstart' in window) ||
                   (navigator.maxTouchPoints > 0) ||
                   (navigator.msMaxTouchPoints > 0);
        };

        // 高亮/取消高亮逻辑函数
        const toggleHighlight = (targetBall) => {
            // 移除所有现有的高亮
            document.querySelectorAll('.lottery-ball.highlighted').forEach(ball => {
                ball.classList.remove('highlighted');
            });

            if (targetBall) {
                const ballNumber = targetBall.dataset.number;
                const ballType = targetBall.dataset.type;

                if (ballNumber && ballType) {
                    // 高亮所有匹配的彩球
                    document.querySelectorAll(`.lottery-ball[data-number="${ballNumber}"][data-type="${ballType}"]`).forEach(ball => {
                        ball.classList.add('highlighted');
                    });
                }
            }
        };

        if (isTouchDevice()) {
            // 移动端使用点击事件
            historyTableContainer.addEventListener('click', function(event) {
                const targetBall = event.target.closest('.lottery-ball');
                if (targetBall) {
                    // 如果点击的球已经高亮，则取消所有高亮
                    if (targetBall.classList.contains('highlighted')) {
                        document.querySelectorAll('.lottery-ball.highlighted').forEach(ball => {
                            ball.classList.remove('highlighted');
                        });
                    } else {
                        // 否则高亮点击的球及其所有匹配项
                        toggleHighlight(targetBall);
                    }
                } else {
                    // 点击非彩球区域，取消所有高亮
                    document.querySelectorAll('.lottery-ball.highlighted').forEach(ball => {
                        ball.classList.remove('highlighted');
                    });
                }
            });
        } else {
            // 电脑端使用鼠标悬停事件
            historyTableContainer.addEventListener('mouseover', function(event) {
                const targetBall = event.target.closest('.lottery-ball');
                if (targetBall) {
                    toggleHighlight(targetBall);
                }
            });

            historyTableContainer.addEventListener('mouseout', function(event) {
                // 鼠标移开时，移除所有高亮
                document.querySelectorAll('.lottery-ball.highlighted').forEach(ball => {
                    ball.classList.remove('highlighted');
                });
            });
        }
    }
});
