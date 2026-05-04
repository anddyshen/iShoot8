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

// --- prediction.html 页面相关的 JavaScript 逻辑 ---

// Function to load and display active rules from backend
async function loadActiveRules(lotteryType, displayElementId) {
    const displayElement = document.getElementById(displayElementId);
    if (!displayElement) {
        console.error(`Display element with ID ${displayElementId} not found.`);
        return;
    }
    displayElement.innerHTML = '<p class="text-muted">加载后台配置规则中... <span class="loading-spinner"></span></p>';

    try {
        const response = await fetch(`/api/prediction/active_rules?lottery_type=${lotteryType}`);
        const data = await response.json();

        if (data.error) {
            displayElement.innerHTML = `<p class="text-danger">加载规则失败: ${data.error}</p>`;
            return;
        }

        if (data.active_rules && data.active_rules.length > 0) {
            let html = '<p><strong>当前激活的筛选规则:</strong></p><ul>';
            data.active_rules.forEach(rule => {
                let paramsHtml = '';
                if (Object.keys(rule.params).length > 0) {
                    paramsHtml = ' (参数: ';
                    paramsHtml += Object.entries(rule.params).map(([key, value]) => `${key}: ${JSON.stringify(value)}`).join(', ');
                    paramsHtml += ')';
                }
                html += `<li><strong>${rule.label}</strong>${paramsHtml} (组合逻辑: ${rule.logic})</li>`;
            });
            html += '</ul><p><strong>提示： 规则冲突优先级:</strong> 所有规则如果产生冲突，则按照顺序作为优先级，在先的优先考虑，舍弃后一条规则。</p>';
            displayElement.innerHTML = html;
        } else {
            displayElement.innerHTML = '<p class="text-muted">当前没有激活的筛选规则。</p>';
        }
    } catch (error) {
        console.error(`Error loading active rules for ${lotteryType}:`, error);
        displayElement.innerHTML = '<p class="text-danger">加载规则失败。</p>';
    }
}

// Helper function to get consecutive groups in JavaScript
function getConsecutiveGroupsJS(numbers) {
    if (!numbers || numbers.length === 0) {
        return {};
    }
    const sortedNumbers = [...new Set(numbers)].sort((a, b) => a - b);
    const groups = [];
    let currentGroup = [sortedNumbers[0]];

    for (let i = 1; i < sortedNumbers.length; i++) {
        if (sortedNumbers[i] === sortedNumbers[i - 1] + 1) {
            currentGroup.push(sortedNumbers[i]);
        } else {
            groups.push(currentGroup);
            currentGroup = [sortedNumbers[i]];
        }
    }
    groups.push(currentGroup);

    const consecutiveMap = {};
    groups.forEach((group, idx) => {
        if (group.length > 1) {
            group.forEach(ball => {
                consecutiveMap[ball] = idx % 3; // Cycle through 3 colors
            });
        }
    });
    return consecutiveMap;
}

// Function to render lottery balls (replicated from Jinja macro for JS use)
function renderBalls(balls, ballType, consecutiveMap = {}) {
    let html = '';
    const sortedBalls = [...balls].sort((a, b) => a - b);
    for (const ball of sortedBalls) {
        let consecutiveClass = '';
        if (ball in consecutiveMap) {
            consecutiveClass = `ball-consecutive-${consecutiveMap[ball]}`;
        }
        html += `<span class="lottery-ball ball-${ballType} ${consecutiveClass}">${String(ball).padStart(2, '0')}</span>`;
    }
    return html;
}

// Global chart instances (declared here to avoid conflicts with prediction.html)
let ssqFilterChart;
let dltFilterChart;

// Variables to keep track of the current offset being displayed for omitted balls
let currentSsqOmissionOffset = 0; // 0 means latest
let currentDltOmissionOffset = 0; // 0 means latest
let maxSsqOmissionOffset = 0; // Max historical offset available
let maxDltOmissionOffset = 0; // Max historical offset available

// New function to render balls with omission count
function renderBallsWithOmission(ballsWithOmission, ballType) {
    let html = '';
    // Ensure ballsWithOmission is an array before iterating
    if (!Array.isArray(ballsWithOmission)) {
        console.error("renderBallsWithOmission received non-array data:", ballsWithOmission);
        return ''; // Return empty string or handle error gracefully
    }
    for (const ballData of ballsWithOmission) {
        html += `
            <div class="lottery-ball-with-omission">
                <span class="lottery-ball ball-${ballType}">${String(ballData.ball).padStart(2, '0')}</span>
                <small class="omission-text">遗漏${ballData.current_omission}</small>
            </div>
        `;
    }
    return html;
}

// Function to update the display of the current omission issue
function updateOmissionIssueDisplay(lotteryType, issue, offset) {
    const displayElement = document.getElementById(`${lotteryType}_current_omission_issue_display`);
    if (displayElement) {
        displayElement.textContent = offset === 0 ? '最新一期' : `第 ${issue} 期`;
    }
    // Enable/disable buttons based on offset
    const prevBtn = document.getElementById(`${lotteryType}_prev_omission_issue_btn`);
    const nextBtn = document.getElementById(`${lotteryType}_next_omission_issue_btn`);
    
    // Use the correct max_offset for the current lottery type
    const currentMaxOffset = lotteryType === 'ssq' ? maxSsqOmissionOffset : maxDltOmissionOffset;

    if (prevBtn) prevBtn.disabled = offset >= currentMaxOffset;
    if (nextBtn) nextBtn.disabled = offset === 0;
}

// Load omitted balls via API
async function loadOmittedBalls(lotteryType, offset = 0) {
    const redContainer = document.getElementById(`${lotteryType}_omitted_red_balls`);
    const blueContainer = document.getElementById(`${lotteryType}_omitted_blue_balls`);
    const latestDrawLabel = document.getElementById(`${lotteryType}_latest_draw_label`);
    const latestDrawBallsContainer = document.getElementById(`${lotteryType}_latest_draw_balls`);
    const matchedOmittedBallsContainer = document.getElementById(`${lotteryType}_matched_omitted_balls`);
    
    redContainer.innerHTML = '<p class="text-muted">加载中... <span class="loading-spinner"></span></p>';
    blueContainer.innerHTML = '<p class="text-muted">加载中... <span class="loading-spinner"></span></p>';
    latestDrawLabel.innerHTML = '<strong>本期开奖号码:</strong> <span class="loading-spinner"></span>';
    latestDrawBallsContainer.innerHTML = '<p class="text-muted">加载中... <span class="loading-spinner"></span></p>';
    matchedOmittedBallsContainer.innerHTML = '<p class="text-muted">加载中... <span class="loading-spinner"></span></p>';

    let url = `/api/prediction/omitted_balls?lottery_type=${lotteryType}&offset=${offset}`;

    console.log(`Frontend: Fetching omitted balls for ${lotteryType}, offset=${offset}...`);
    try {
        const response = await fetch(url);
        const data = await response.json();

        console.log(`Frontend: Received response for ${lotteryType} omitted balls:`, data);

        if (data.error) {
            redContainer.innerHTML = `<p class="text-danger">加载失败: ${data.error}</p>`;
            blueContainer.innerHTML = `<p class="text-danger">加载失败: ${data.error}</p>`;
            latestDrawLabel.innerHTML = `<strong>本期开奖号码:</strong> <span class="text-danger">加载失败</span>`;
            latestDrawBallsContainer.innerHTML = `<p class="text-danger">加载失败: ${data.error}</p>`;
            matchedOmittedBallsContainer.innerHTML = `<p class="text-danger">加载失败: ${data.error}</p>`;
            return;
        }

        // Update current offset tracking variable and max offset
        if (lotteryType === 'ssq') {
            currentSsqOmissionOffset = offset;
            maxSsqOmissionOffset = data.max_offset;
        } else {
            currentDltOmissionOffset = offset;
            maxDltOmissionOffset = data.max_offset;
        }
        updateOmissionIssueDisplay(lotteryType, data.current_omission_issue, offset);

        redContainer.innerHTML = renderBallsWithOmission(data.red_balls, 'red');
        blueContainer.innerHTML = renderBallsWithOmission(data.blue_balls, 'blue');

        // Render latest draw balls (using display_red_balls and display_blue_balls from API)
        if (data.display_red_balls && data.display_blue_balls) {
            latestDrawLabel.innerHTML = `<strong>第 ${data.display_issue} 期开奖号码:</strong>`;
            const redConsecutiveMap = getConsecutiveGroupsJS(data.display_red_balls);
            const blueConsecutiveMap = getConsecutiveGroupsJS(data.display_blue_balls);
            latestDrawBallsContainer.innerHTML = `
                红球: ${renderBalls(data.display_red_balls, 'red', redConsecutiveMap)}
                蓝球: ${renderBalls(data.display_blue_balls, 'blue', blueConsecutiveMap)}
            `;
        } else {
            latestDrawLabel.innerHTML = `<strong>本期开奖号码:</strong>`;
            latestDrawBallsContainer.innerHTML = '<p class="text-muted">暂无数据。</p>';
        }

        // Render matched omitted balls
        if (data.matched_omitted_balls && data.matched_omitted_balls.length > 0) {
            matchedOmittedBallsContainer.innerHTML = renderBallsWithOmission(data.matched_omitted_balls, 'red'); // Assuming matched are red balls
        } else {
            matchedOmittedBallsContainer.innerHTML = '<p class="text-muted">无。</p>';
        }

        console.log(`Frontend: Successfully rendered omitted balls for ${lotteryType}.`);

    } catch (error) {
        console.error(`Frontend: Error loading omitted balls for ${lotteryType}:`, error);
        redContainer.innerHTML = '<p class="text-danger">加载失败。</p>';
        blueContainer.innerHTML = '<p class="text-danger">加载失败。</p>';
        latestDrawLabel.innerHTML = `<strong>本期开奖号码:</strong>`;
        latestDrawBallsContainer.innerHTML = '<p class="text-danger">加载失败。</p>';
        matchedOmittedBallsContainer.innerHTML = '<p class="text-danger">加载失败。</p>';
    }
}

// Tab switching logic
document.getElementById('ssq_prediction_tab').addEventListener('click', function(e) {
    e.preventDefault();
    document.getElementById('ssq_prediction_section').style.display = 'block';
    document.getElementById('dlt_prediction_section').style.display = 'none';
    this.classList.add('active');
    document.getElementById('dlt_prediction_tab').classList.remove('active');
    console.log("Switched to SSQ tab. Loading omitted and matched balls for SSQ.");
    updateFilterStatsDisplay('ssq', null); // Clear stats when switching tabs
    document.getElementById('dlt_filter_overview_card').style.display = 'none'; // Hide DLT overview when switching to SSQ
    loadOmittedBalls('ssq', currentSsqOmissionOffset); // Load data for SSQ when tab is clicked
    loadActiveRules('ssq', 'ssq_active_rules_display'); // Load active rules for SSQ
});

document.getElementById('dlt_prediction_tab').addEventListener('click', function(e) {
    e.preventDefault();
    document.getElementById('dlt_prediction_section').style.display = 'block';
    document.getElementById('ssq_prediction_section').style.display = 'none';
    this.classList.add('active');
    document.getElementById('ssq_prediction_tab').classList.remove('active');
    console.log("Switched to DLT tab. Loading omitted and matched balls for DLT.");
    updateFilterStatsDisplay('dlt', null); // Clear stats when switching tabs
    document.getElementById('ssq_filter_overview_card').style.display = 'none'; // Hide SSQ overview when switching to DLT
    loadOmittedBalls('dlt', currentDltOmissionOffset); // Load data for DLT when tab is clicked
    loadActiveRules('dlt', 'dlt_active_rules_display'); // Load active rules for DLT
});

// Event Listeners for omission navigation buttons
document.getElementById('ssq_prev_omission_issue_btn').addEventListener('click', () => {
    if (currentSsqOmissionOffset < maxSsqOmissionOffset) {
        loadOmittedBalls('ssq', currentSsqOmissionOffset + 1);
    }
});

document.getElementById('ssq_next_omission_issue_btn').addEventListener('click', () => {
    if (currentSsqOmissionOffset > 0) {
        loadOmittedBalls('ssq', currentSsqOmissionOffset - 1);
    }
});

document.getElementById('dlt_prev_omission_issue_btn').addEventListener('click', () => {
    if (currentDltOmissionOffset < maxDltOmissionOffset) {
        loadOmittedBalls('dlt', currentDltOmissionOffset + 1);
    }
});

document.getElementById('dlt_next_omission_issue_btn').addEventListener('click', () => {
    if (currentDltOmissionOffset > 0) {
        loadOmittedBalls('dlt', currentDltOmissionOffset - 1);
    }
});


// Generate Random Numbers
async function generateRandomNumbers(lotteryType, indexToRegenerate = null) {
    const numGenerate = indexToRegenerate === null ? document.getElementById(`${lotteryType}_num_generate`).value : 1;
    const outputDiv = document.getElementById(`${lotteryType}_random_numbers_output`);
    
    if (indexToRegenerate === null) { // Only clear if generating all
        outputDiv.innerHTML = '<p class="text-muted">生成中... <span class="loading-spinner"></span></p>';
    } else {
        // Show loading spinner on the specific card
        const card = outputDiv.querySelector(`.prediction-result-card:nth-child(${indexToRegenerate + 1})`);
        if (card) {
            card.querySelector('.card-title').innerHTML = `随机号码 ${indexToRegenerate + 1}: <span class="loading-spinner"></span>`;
        }
    }

    console.log(`Frontend: Generating random numbers for ${lotteryType}, count=${numGenerate}, index=${indexToRegenerate}...`);
    try {
        const response = await fetch('/api/prediction/generate_random', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                lottery_type: lotteryType, 
                count: parseInt(numGenerate)
            })
        });
        const data = await response.json();

        console.log(`Frontend: Received response for ${lotteryType} random numbers:`, data);

        if (data.error) {
            if (indexToRegenerate === null) {
                outputDiv.innerHTML = `<p class="text-danger">生成失败: ${data.error}</p>`;
            } else {
                const card = outputDiv.querySelector(`.prediction-result-card:nth-child(${indexToRegenerate + 1})`);
                if (card) {
                    card.querySelector('.card-title').innerHTML = `随机号码 ${indexToRegenerate + 1}: <span class="text-danger">生成失败</span>`;
                }
            }
            return;
        }

        if (indexToRegenerate === null) {
            let html = '';
            data.numbers.forEach((combo, index) => {
                const redBallsStr = combo.red_balls;
                const blueBallsStr = combo.blue_balls;
                const fullNumberStr = `红球: ${redBallsStr} 蓝球: ${blueBallsStr}`;

                html += `<div class="prediction-result-card random-generated">
                            <p class="card-title">随机号码 ${index + 1}:</p>
                            <p>红球: ${renderBalls(combo.red_balls.split(',').map(Number), 'red', getConsecutiveGroupsJS(combo.red_balls.split(',').map(Number)))}</p>
                            <p>蓝球: ${renderBalls(combo.blue_balls.split(',').map(Number), 'blue', getConsecutiveGroupsJS(combo.blue_balls.split(',').map(Number)))}</p>
                            <div class="number-stats mt-2">
                                <small>红球: 奇偶比 ${combo.stats.red_odd_even_ratio}, 和值 ${combo.stats.red_sum}, 跨度 ${combo.stats.red_span}, 大小比 ${combo.stats.red_size_ratio}</small><br>
                                <small>蓝球: 奇偶比 ${combo.stats.blue_odd_even_ratio}, 和值 ${combo.stats.blue_sum}, 跨度 ${combo.stats.blue_span}, 大小比 ${combo.stats.blue_size_ratio}</small>
                            </div>
                            <button class="btn btn-sm btn-outline-info me-2 regenerate-random-btn" data-lottery-type="${lotteryType}" data-index="${index}">重新生成</button>
                            <button class="btn btn-sm btn-outline-primary me-2 check-generated-rules-btn" data-lottery-type="${lotteryType}" data-red-balls="${redBallsStr}" data-blue-balls="${blueBallsStr}">检查规则</button>
                            <button class="btn btn-sm btn-outline-secondary me-2 copy-to-clipboard-btn" data-copy-text="${fullNumberStr}">复制结果</button>
                            <div class="rule-check-results mt-2" id="${lotteryType}_random_rule_check_${index}"></div>
                        </div>`;
            });
            outputDiv.innerHTML = html;
        } else {
            // Replace content of specific card
            const newCombo = data.numbers[0]; // Should only be one new combo
            const redBallsStr = newCombo.red_balls;
            const blueBallsStr = newCombo.blue_balls;
            const fullNumberStr = `红球: ${redBallsStr} 蓝球: ${blueBallsStr}`;

            const card = outputDiv.querySelector(`.prediction-result-card:nth-child(${indexToRegenerate + 1})`);
            if (card) {
                const redBallsList = redBallsStr.split(',').map(Number);
                const blueBallsList = blueBallsStr.split(',').map(Number);

                card.querySelector('.card-title').innerHTML = `随机号码 ${indexToRegenerate + 1}:`;
                card.querySelector('p:nth-of-type(2)').innerHTML = `红球: ${renderBalls(redBallsList, 'red', getConsecutiveGroupsJS(redBallsList))}`;
                card.querySelector('p:nth-of-type(3)').innerHTML = `蓝球: ${renderBalls(blueBallsList, 'blue', getConsecutiveGroupsJS(blueBallsList))}`;
                
                // Update statistics
                let statsDiv = card.querySelector('.number-stats');
                if (!statsDiv) {
                    statsDiv = document.createElement('div');
                    statsDiv.classList.add('number-stats', 'mt-2');
                    card.insertBefore(statsDiv, card.querySelector('.regenerate-random-btn')); // Insert before buttons
                }
                statsDiv.innerHTML = `
                    <small>红球: 奇偶比 ${newCombo.stats.red_odd_even_ratio}, 和值 ${newCombo.stats.red_sum}, 跨度 ${newCombo.stats.red_span}, 大小比 ${newCombo.stats.red_size_ratio}</small><br>
                    <small>蓝球: 奇偶比 ${newCombo.stats.blue_odd_even_ratio}, 和值 ${newCombo.stats.blue_sum}, 跨度 ${newCombo.stats.blue_span}, 大小比 ${newCombo.stats.blue_size_ratio}</small>
                `;

                card.querySelector('.check-generated-rules-btn').dataset.redBalls = redBallsStr;
                card.querySelector('.check-generated-rules-btn').dataset.blueBalls = blueBallsStr;
                card.querySelector('.copy-to-clipboard-btn').dataset.copyText = fullNumberStr;
                // card.querySelector('.share-to-social-btn').dataset.shareText = fullNumberStr; // Removed as per user request
                // Clear previous rule check results if any
                card.querySelector('.rule-check-results').innerHTML = '';
            }
        }
        console.log(`Frontend: Successfully rendered random numbers for ${lotteryType}.`);

    } catch (error) {
        console.error(`Frontend: Error generating random numbers for ${lotteryType}:`, error);
        if (indexToRegenerate === null) {
            outputDiv.innerHTML = '<p class="text-danger">生成失败。</p>';
        } else {
            const card = outputDiv.querySelector(`.prediction-result-card:nth-child(${indexToRegenerate + 1})`);
            if (card) {
                card.querySelector('.card-title').innerHTML = `随机号码 ${indexToRegenerate + 1}: <span class="text-danger">生成失败</span>`;
                // Clear stats on error
                const statsDiv = card.querySelector('.number-stats');
                if (statsDiv) statsDiv.innerHTML = '';
            }
        }
    }
}

// Generate Predicted Numbers (now "规则号码")
async function generatePredictedNumbers(lotteryType, indexToRegenerate = null) {
    const numGenerate = indexToRegenerate === null ? document.getElementById(`${lotteryType}_num_generate`).value : 1;
    const outputDiv = document.getElementById(`${lotteryType}_predicted_numbers_output`);

    if (indexToRegenerate === null) { // Only clear if generating all
        outputDiv.innerHTML = '<p class="text-muted">生成中... <span class="loading-spinner"></span></p>';
    } else {
        // Show loading spinner on the specific card
        const card = outputDiv.querySelector(`.prediction-result-card:nth-child(${indexToRegenerate + 1})`);
        if (card) {
            card.querySelector('.card-title').innerHTML = `规则预测号码 ${indexToRegenerate + 1}: <span class="loading-spinner"></span>`;
        }
    }

    console.log(`Frontend: Generating predicted (rule-based) numbers for ${lotteryType}, count=${numGenerate}, index=${indexToRegenerate}...`);
    try {
        const response = await fetch('/api/prediction/generate_predicted', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                lottery_type: lotteryType, 
                count: parseInt(numGenerate)
            })
        });
        const data = await response.json();

        console.log(`Frontend: Received response for ${lotteryType} predicted numbers:`, data);

        if (data.error) {
            if (indexToRegenerate === null) {
                outputDiv.innerHTML = `<p class="text-danger">生成失败: ${data.error}</p>`;
            } else {
                const card = outputDiv.querySelector(`.prediction-result-card:nth-child(${indexToRegenerate + 1})`);
                if (card) {
                    card.querySelector('.card-title').innerHTML = `规则预测号码 ${indexToRegenerate + 1}: <span class="text-danger">生成失败</span>`;
                }
            }
            return;
        }

        if (indexToRegenerate === null) {
            let html = '';
            data.numbers.forEach((combo, index) => {
                const redBallsStr = combo.red_balls;
                const blueBallsStr = combo.blue_balls;
                const fullNumberStr = `红球: ${redBallsStr} 蓝球: ${blueBallsStr}`;

                html += `<div class="prediction-result-card rule-based">
                            <p class="card-title">规则预测号码 ${index + 1}:</p>
                            <p>红球: ${renderBalls(combo.red_balls.split(',').map(Number), 'red', getConsecutiveGroupsJS(combo.red_balls.split(',').map(Number)))}</p>
                            <p>蓝球: ${renderBalls(combo.blue_balls.split(',').map(Number), 'blue', getConsecutiveGroupsJS(combo.blue_balls.split(',').map(Number)))}</p>
                            <div class="number-stats mt-2">
                                <small>红球: 奇偶比 ${combo.stats.red_odd_even_ratio}, 和值 ${combo.stats.red_sum}, 跨度 ${combo.stats.red_span}, 大小比 ${combo.stats.red_size_ratio}</small><br>
                                <small>蓝球: 奇偶比 ${combo.stats.blue_odd_even_ratio}, 和值 ${combo.stats.blue_sum}, 跨度 ${combo.stats.blue_span}, 大小比 ${combo.stats.blue_size_ratio}</small>
                            </div>
                            <button class="btn btn-sm btn-outline-info me-2 regenerate-predicted-btn" data-lottery-type="${lotteryType}" data-index="${index}">重新生成</button>
                            <button class="btn btn-sm btn-outline-primary me-2 check-generated-rules-btn" data-lottery-type="${lotteryType}" data-red-balls="${redBallsStr}" data-blue-balls="${blueBallsStr}">检查规则</button>
                            <button class="btn btn-sm btn-outline-secondary me-2 copy-to-clipboard-btn" data-copy-text="${fullNumberStr}">复制结果</button>
                            <div class="rule-check-results mt-2" id="${lotteryType}_predicted_rule_check_${index}"></div>
                        </div>`;
            });
            outputDiv.innerHTML = html;
        } else {
            // Replace content of specific card
            const newCombo = data.numbers[0]; // Should only be one new combo
            const redBallsStr = newCombo.red_balls;
            const blueBallsStr = newCombo.blue_balls;
            const fullNumberStr = `红球: ${redBallsStr} 蓝球: ${blueBallsStr}`;

            const card = outputDiv.querySelector(`.prediction-result-card:nth-child(${indexToRegenerate + 1})`);
            if (card) {
                const redBallsList = redBallsStr.split(',').map(Number);
                const blueBallsList = blueBallsStr.split(',').map(Number);

                card.querySelector('.card-title').innerHTML = `规则预测号码 ${indexToRegenerate + 1}:`;
                card.querySelector('p:nth-of-type(2)').innerHTML = `红球: ${renderBalls(redBallsList, 'red', getConsecutiveGroupsJS(redBallsList))}`;
                card.querySelector('p:nth-of-type(3)').innerHTML = `蓝球: ${renderBalls(blueBallsList, 'blue', getConsecutiveGroupsJS(blueBallsList))}`;
                
                // Update statistics
                let statsDiv = card.querySelector('.number-stats');
                if (!statsDiv) {
                    statsDiv = document.createElement('div');
                    statsDiv.classList.add('number-stats', 'mt-2');
                    card.insertBefore(statsDiv, card.querySelector('.regenerate-predicted-btn')); // Insert before buttons
                }
                statsDiv.innerHTML = `
                    <small>红球: 奇偶比 ${newCombo.stats.red_odd_even_ratio}, 和值 ${newCombo.stats.red_sum}, 跨度 ${newCombo.stats.red_span}, 大小比 ${newCombo.stats.red_size_ratio}</small><br>
                    <small>蓝球: 奇偶比 ${newCombo.stats.blue_odd_even_ratio}, 和值 ${newCombo.stats.blue_sum}, 跨度 ${newCombo.stats.blue_span}, 大小比 ${newCombo.stats.blue_size_ratio}</small>
                `;

                card.querySelector('.check-generated-rules-btn').dataset.redBalls = redBallsStr;
                card.querySelector('.check-generated-rules-btn').dataset.blueBalls = blueBallsStr;
                card.querySelector('.copy-to-clipboard-btn').dataset.copyText = fullNumberStr;
                // card.querySelector('.share-to-social-btn').dataset.shareText = fullNumberStr; // Removed as per user request
                // Clear previous rule check results if any
                card.querySelector('.rule-check-results').innerHTML = '';
            }
        }

        // Update filter stats display
        updateFilterStatsDisplay(lotteryType, data);
        document.getElementById(`${lotteryType}_filter_overview_card`).style.display = 'block'; // Show the overview card

        console.log(`Frontend: Successfully rendered predicted numbers for ${lotteryType}.`);

    } catch (error) {
        console.error(`Frontend: Error generating predicted numbers for ${lotteryType}:`, error);
        if (indexToRegenerate === null) {
            outputDiv.innerHTML = '<p class="text-danger">生成失败。</p>';
        } else {
            const card = outputDiv.querySelector(`.prediction-result-card:nth-child(${indexToRegenerate + 1})`);
            if (card) {
                card.querySelector('.card-title').innerHTML = `规则预测号码 ${indexToRegenerate + 1}: <span class="text-danger">生成失败</span>`;
                // Clear stats on error
                const statsDiv = card.querySelector('.number-stats');
                if (statsDiv) statsDiv.innerHTML = '';
            }
        }
        updateFilterStatsDisplay(lotteryType, null); // Clear stats on error
    }
}

// Check Rules for Generated Numbers (using new API)
async function checkGeneratedRules(lotteryType, redBallsStr, blueBallsStr) {
    const modalBody = document.querySelector('#ruleCheckModal .modal-body'); // Output to modal body
    modalBody.innerHTML = '<p class="text-muted">检查中... <span class="loading-spinner"></span></p>';
    const ruleCheckModal = new bootstrap.Modal(document.getElementById('ruleCheckModal'));
    ruleCheckModal.show(); // Show modal immediately

    console.log(`Frontend: Checking rules for generated numbers for ${lotteryType}: Red=${redBallsStr}, Blue=${blueBallsStr}`);
    try {
        const response = await fetch('/api/prediction/check_generated_rules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                lottery_type: lotteryType, 
                red_balls: redBallsStr, 
                blue_balls: blueBallsStr 
            })
        });
        const data = await response.json();

        console.log(`Frontend: Received rule check response for ${lotteryType}:`, data);

        if (data.error) {
            modalBody.innerHTML = `<p class="text-danger">规则检查失败: ${data.error}</p>`;
            return;
        }

        let html = '';
        for (const ruleKey in data) {
            const ruleResult = data[ruleKey];
            const statusClass = ruleResult.passed ? 'passed' : 'failed';
            // Remove all leading English text, numbers, underscores, colons, and whitespace
            const displayRuleKey = ruleKey.replace(/^[a-zA-Z0-9_:\s]+/, '').trim();
            html += `<div class="rule-item ${statusClass}">
                        <strong>${displayRuleKey}</strong> ${ruleResult.message}
                    </div>`;
        }
        modalBody.innerHTML = html;

    } catch (error) {
        console.error(`Frontend: Error checking rules for generated numbers for ${lotteryType}:`, error);
        modalBody.innerHTML = '<p class="text-danger">规则检查失败。</p>';
    }
}

// Copy to Clipboard function
async function copyToClipboard(text) {
    try {
        // 尝试使用现代 Clipboard API
        await navigator.clipboard.writeText(text);
        alert('号码已复制到剪贴板！');
    } catch (err) {
        console.error('Clipboard API 复制失败，尝试回退方案:', err);
        // 回退方案：使用 textarea 元素进行复制
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed'; // 避免滚动
        textarea.style.opacity = 0; // 隐藏元素
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        try {
            const successful = document.execCommand('copy');
            if (successful) {
                alert('号码已复制到剪贴板！');
            } else {
                alert('复制失败，请手动复制。');
            }
        } catch (copyErr) {
            console.error('手动复制失败:', copyErr);
            alert('复制失败，请手动复制。');
        } finally {
            document.body.removeChild(textarea);
        }
    }
}

// Clear Predicted Numbers (规则筛选)
function clearPredictedNumbers(lotteryType) {
    document.getElementById(`${lotteryType}_predicted_numbers_output`).innerHTML = '<p class="text-muted">点击"生成规则号码"按钮。</p>';
    updateFilterStatsDisplay(lotteryType, null);
    document.getElementById(`${lotteryType}_filter_overview_card`).style.display = 'none';
    console.log(`Frontend: Cleared predicted numbers for ${lotteryType}.`);
}

// Clear Random Numbers (真随机)
function clearRandomNumbers(lotteryType) {
    document.getElementById(`${lotteryType}_random_numbers_output`).innerHTML = '<p class="text-muted">点击"生成真随机号码"按钮。</p>';
    console.log(`Frontend: Cleared random numbers for ${lotteryType}.`);
}

// Copy All Random Numbers (真随机)
function copyAllRandomNumbers(lotteryType) {
    let allNumbersText = `--- ${lotteryType.toUpperCase()} 真随机号码 ---\n`;
    const randomCards = document.querySelectorAll(`#${lotteryType}_random_numbers_output .prediction-result-card`);
    if (randomCards.length === 0) {
        allNumbersText += "无\n";
    } else {
        randomCards.forEach(card => {
            const redBalls = card.querySelector('p:nth-of-type(2)').innerText.replace('红球: ', '');
            const blueBalls = card.querySelector('p:nth-of-type(3)').innerText.replace('蓝球: ', '');
            allNumbersText += `${redBalls} ${blueBalls}\n`;
        });
    }
    copyToClipboard(allNumbersText);
}

// Copy All Generated Numbers
function copyAllGeneratedNumbers(lotteryType) {
    let allNumbersText = `--- ${lotteryType.toUpperCase()} 规则预测号码 ---\n`;
    const predictedCards = document.querySelectorAll(`#${lotteryType}_predicted_numbers_output .prediction-result-card`);
    if (predictedCards.length === 0) {
        allNumbersText += "无\n";
    } else {
        predictedCards.forEach(card => {
            const redBalls = card.querySelector('p:nth-of-type(2)').innerText.replace('红球: ', '');
            const blueBalls = card.querySelector('p:nth-of-type(3)').innerText.replace('蓝球: ', '');
            allNumbersText += `${redBalls} ${blueBalls}\n`;
        });
    }

    allNumbersText += `\n--- ${lotteryType.toUpperCase()} 真随机号码 ---\n`;
    const randomCards = document.querySelectorAll(`#${lotteryType}_random_numbers_output .prediction-result-card`);
    if (randomCards.length === 0) {
        allNumbersText += "无\n";
    } else {
        randomCards.forEach(card => {
            const redBalls = card.querySelector('p:nth-of-type(2)').innerText.replace('红球: ', '');
            const blueBalls = card.querySelector('p:nth-of-type(3)').innerText.replace('蓝球: ', '');
            allNumbersText += `${redBalls} ${blueBalls}\n`;
        });
    }
    
    copyToClipboard(allNumbersText);
}


// Event Listeners
document.getElementById('generate_ssq_random').addEventListener('click', () => generateRandomNumbers('ssq'));
document.getElementById('generate_dlt_random').addEventListener('click', () => generateRandomNumbers('dlt'));

document.getElementById('generate_ssq_prediction').addEventListener('click', () => generatePredictedNumbers('ssq'));
document.getElementById('generate_dlt_prediction').addEventListener('click', () => generatePredictedNumbers('dlt'));

// Clear buttons
document.getElementById('clear_ssq_generated_numbers').addEventListener('click', () => clearPredictedNumbers('ssq'));
document.getElementById('clear_dlt_generated_numbers').addEventListener('click', () => clearPredictedNumbers('dlt'));
document.getElementById('clear_ssq_random_numbers').addEventListener('click', () => clearRandomNumbers('ssq'));
document.getElementById('clear_dlt_random_numbers').addEventListener('click', () => clearRandomNumbers('dlt'));

// Copy All buttons
document.getElementById('copy_all_ssq_numbers').addEventListener('click', () => copyAllGeneratedNumbers('ssq'));
document.getElementById('copy_all_dlt_numbers').addEventListener('click', () => copyAllGeneratedNumbers('dlt'));
document.getElementById('copy_all_ssq_random_numbers').addEventListener('click', () => copyAllRandomNumbers('ssq'));
document.getElementById('copy_all_dlt_random_numbers').addEventListener('click', () => copyAllRandomNumbers('dlt'));

// Generate Complex Prediction Numbers
async function generateComplexPrediction(lotteryType) {
    const redCount = document.getElementById(`${lotteryType}_complex_red_count`).value;
    const blueCount = document.getElementById(`${lotteryType}_complex_blue_count`).value;
    const numGenerate = document.getElementById(`${lotteryType}_complex_num_generate`).value;
    const outputDiv = document.getElementById(`${lotteryType}_complex_prediction_output`);

    outputDiv.innerHTML = '<p class="text-muted">生成中... <span class="loading-spinner"></span></p>';

    console.log(`Frontend: Generating complex prediction for ${lotteryType} with Red=${redCount}, Blue=${blueCount}, Count=${numGenerate}...`);
    try {
        const response = await fetch('/api/prediction/generate_complex', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                lottery_type: lotteryType, 
                red_count: parseInt(redCount), 
                blue_count: parseInt(blueCount),
                count: parseInt(numGenerate)
            })
        });
        const data = await response.json();

        console.log(`Frontend: Received response for ${lotteryType} complex prediction:`, data);

        if (data.error) {
            outputDiv.innerHTML = `<p class="text-danger">生成失败: ${data.error}</p>`;
            return;
        }

        let html = '';
        if (data.numbers && data.numbers.length > 0) {
            data.numbers.forEach((combo, index) => {
                const redBallsStr = combo.red_balls;
                const blueBallsStr = combo.blue_balls;
                const combinationText = `${combo.red_count}+${combo.blue_count}`;
                const priceText = `${combo.total_cost} 元`;
                const fullNumberStr = `红球: ${redBallsStr} 蓝球: ${blueBallsStr} (${combinationText}, ${priceText})`;

                html += `<div class="prediction-result-card complex-generated">
                            <p class="card-title">复式号码 ${index + 1}: (${combinationText}, ${priceText})</p>
                            <p>红球: ${renderBalls(combo.red_balls.split(',').map(Number), 'red', getConsecutiveGroupsJS(combo.red_balls.split(',').map(Number)))}</p>
                            <p>蓝球: ${renderBalls(combo.blue_balls.split(',').map(Number), 'blue', getConsecutiveGroupsJS(combo.blue_balls.split(',').map(Number)))}</p>
                            <div class="number-stats mt-2">
                                <small>红球: 奇偶比 ${combo.stats.red_odd_even_ratio}, 和值 ${combo.stats.red_sum}, 跨度 ${combo.stats.red_span}, 大小比 ${combo.stats.red_size_ratio}</small><br>
                                <small>蓝球: 奇偶比 ${combo.stats.blue_odd_even_ratio}, 和值 ${combo.stats.blue_sum}, 跨度 ${combo.stats.blue_span}, 大小比 ${combo.stats.blue_size_ratio}</small>
                            </div>
                            <button class="btn btn-sm btn-outline-primary me-2 check-generated-rules-btn" data-lottery-type="${lotteryType}" data-red-balls="${redBallsStr}" data-blue-balls="${blueBallsStr}">检查规则</button>
                            <button class="btn btn-sm btn-outline-secondary me-2 copy-to-clipboard-btn" data-copy-text="${fullNumberStr}">复制结果</button>
                        </div>`;
            });
        } else {
            html = '<p class="text-muted">未生成复式号码，请调整数量或检查规则。</p>';
        }
        outputDiv.innerHTML = html;
        console.log(`Frontend: Successfully rendered complex prediction for ${lotteryType}.`);

    } catch (error) {
        console.error(`Frontend: Error generating complex prediction for ${lotteryType}:`, error);
        outputDiv.innerHTML = '<p class="text-danger">生成失败。</p>';
    }
}

// Event Listeners for complex prediction buttons
document.getElementById('generate_ssq_complex_prediction').addEventListener('click', () => generateComplexPrediction('ssq'));
document.getElementById('generate_dlt_complex_prediction').addEventListener('click', () => generateComplexPrediction('dlt'));

// Event delegation for dynamically added buttons
document.getElementById('ssq_random_numbers_output').addEventListener('click', function(e) {
    if (e.target.classList.contains('regenerate-random-btn')) {
        const index = parseInt(e.target.dataset.index);
        generateRandomNumbers(e.target.dataset.lotteryType, index); 
    }
    if (e.target.classList.contains('check-generated-rules-btn')) {
        checkGeneratedRules(e.target.dataset.lotteryType, e.target.dataset.redBalls, e.target.dataset.blueBalls);
    }
    if (e.target.classList.contains('copy-to-clipboard-btn')) {
        copyToClipboard(e.target.dataset.copyText);
    }
    if (e.target.classList.contains('share-to-social-btn')) {
        // shareToSocialMedia(e.target.dataset.shareText); // Removed as per user request
    }
});

// Function to update filter statistics display and chart
function updateFilterStatsDisplay(lotteryType, statsData) {
    const totalCombinationsDisplay = document.getElementById(`${lotteryType}_total_combinations_display`);
    // const unfilteredWinningChanceDisplay = document.getElementById(`${lotteryType}_unfiltered_winning_chance_display`); // 移除
    const filteredByRulesCountDisplay = document.getElementById(`${lotteryType}_filtered_by_rules_count_display`);
    const filterRateDisplay = document.getElementById(`${lotteryType}_filter_rate_display`);
    const chartCanvas = document.getElementById(`${lotteryType}_filter_chart`);

    if (!statsData) {
        totalCombinationsDisplay.textContent = '计算中...';
        // unfilteredWinningChanceDisplay.textContent = '计算中...'; // 移除
        filteredByRulesCountDisplay.textContent = '计算中...';
        filterRateDisplay.textContent = '计算中...'; // Clear filter rate
        // Destroy existing chart if any
        if (lotteryType === 'ssq' && ssqFilterChart) {
            ssqFilterChart.destroy();
            ssqFilterChart = null;
        } else if (lotteryType === 'dlt' && dltFilterChart) {
            dltFilterChart.destroy();
            dltFilterChart = null;
        }
        return;
    }

    const totalCombinations = statsData.total_combinations;
    // const unfilteredWinningChance = statsData.unfiltered_winning_chance; // 移除
    const filteredByRulesCount = statsData.filtered_by_rules_count;
    const generatedCount = statsData.numbers.length; // Number of successfully generated sets

    totalCombinationsDisplay.textContent = totalCombinations.toLocaleString();
    // unfilteredWinningChanceDisplay.textContent = `1 / ${totalCombinations.toLocaleString()} (约 ${unfilteredWinningChance.toExponential(2)})`; // 移除
    filteredByRulesCountDisplay.textContent = filteredByRulesCount.toLocaleString();

    // Calculate and display filter rate
    let filterRate = 0;
    if (filteredByRulesCount + generatedCount > 0) {
        filterRate = (filteredByRulesCount / (filteredByRulesCount + generatedCount)) * 100;
    }
    filterRateDisplay.textContent = `${filterRate.toFixed(2)}%`;

    // Update Chart
    const ctx = chartCanvas.getContext('2d');
    let chartInstance;
    if (lotteryType === 'ssq') {
        if (ssqFilterChart) ssqFilterChart.destroy();
        chartInstance = ssqFilterChart;
    } else {
        if (dltFilterChart) dltFilterChart.destroy();
        chartInstance = dltFilterChart;
    }

    chartInstance = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['通过规则筛选', '成功生成'],
            datasets: [{
                data: [filteredByRulesCount, generatedCount],
                backgroundColor: ['#ff6384', '#36a2eb'],
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: '规则筛选概览'
                }
            }
        }
    });

    if (lotteryType === 'ssq') {
        ssqFilterChart = chartInstance;
    } else {
        dltFilterChart = chartInstance;
    }
}

// Initial load
document.addEventListener('DOMContentLoaded', function() {
    // Ensure the correct tab is active on load
    document.getElementById('ssq_prediction_tab').click(); // This will also trigger loadOmittedBalls('ssq') and loadActiveRules('ssq', 'ssq_active_rules_display')
    
    // Default to generating rule-based numbers for SSQ on page load
    generatePredictedNumbers('ssq');
});
document.getElementById('dlt_random_numbers_output').addEventListener('click', function(e) {
    if (e.target.classList.contains('regenerate-random-btn')) {
        const index = parseInt(e.target.dataset.index);
        generateRandomNumbers(e.target.dataset.lotteryType, index);
    }
    if (e.target.classList.contains('check-generated-rules-btn')) {
        checkGeneratedRules(e.target.dataset.lotteryType, e.target.dataset.redBalls, e.target.dataset.blueBalls);
    }
    if (e.target.classList.contains('copy-to-clipboard-btn')) {
        copyToClipboard(e.target.dataset.copyText);
    }
    if (e.target.classList.contains('share-to-social-btn')) {
        // shareToSocialMedia(e.target.dataset.shareText); // Removed as per user request
    }
});

document.getElementById('ssq_predicted_numbers_output').addEventListener('click', function(e) {
    if (e.target.classList.contains('regenerate-predicted-btn')) {
        const index = parseInt(e.target.dataset.index);
        generatePredictedNumbers(e.target.dataset.lotteryType, index);
    }
    if (e.target.classList.contains('check-generated-rules-btn')) {
        checkGeneratedRules(e.target.dataset.lotteryType, e.target.dataset.redBalls, e.target.dataset.blueBalls);
    }
    if (e.target.classList.contains('copy-to-clipboard-btn')) {
        copyToClipboard(e.target.dataset.copyText);
    }
    if (e.target.classList.contains('share-to-social-btn')) {
        // shareToSocialMedia(e.target.dataset.shareText); // Removed as per user request
    }
});
document.getElementById('dlt_predicted_numbers_output').addEventListener('click', function(e) {
    if (e.target.classList.contains('regenerate-predicted-btn')) {
        const index = parseInt(e.target.dataset.index);
        generatePredictedNumbers(e.target.dataset.lotteryType, index);
    }
    if (e.target.classList.contains('check-generated-rules-btn')) {
        checkGeneratedRules(e.target.dataset.lotteryType, e.target.dataset.redBalls, e.target.dataset.blueBalls);
    }
    if (e.target.classList.contains('copy-to-clipboard-btn')) {
        copyToClipboard(e.target.dataset.copyText);
    }
    if (e.target.classList.contains('share-to-social-btn')) {
        // shareToSocialMedia(e.target.dataset.shareText); // Removed as per user request
    }
});


// Clear Complex Generated Numbers
function clearComplexGeneratedNumbers(lotteryType) {
    document.getElementById(`${lotteryType}_complex_prediction_output`).innerHTML = '<p class="text-muted">复式号码将在此处生成。</p>';
    console.log(`Frontend: Cleared complex generated numbers for ${lotteryType}.`);
}

// Copy All Complex Generated Numbers
function copyAllComplexNumbers(lotteryType) {
    let allNumbersText = `--- ${lotteryType.toUpperCase()} 复式预测号码 ---\n`;
    const complexCards = document.querySelectorAll(`#${lotteryType}_complex_prediction_output .prediction-result-card`);
    if (complexCards.length === 0) {
        allNumbersText += "无\n";
    } else {
        complexCards.forEach(card => {
            const redBalls = card.querySelector('p:nth-of-type(2)').innerText.replace('红球: ', '');
            const blueBalls = card.querySelector('p:nth-of-type(3)').innerText.replace('蓝球: ', '');
            allNumbersText += `${redBalls} ${blueBalls}\n`;
        });
    }
    copyToClipboard(allNumbersText);
}

// Event Listeners for complex prediction clear/copy buttons
document.getElementById('clear_ssq_complex_generated_numbers').addEventListener('click', () => clearComplexGeneratedNumbers('ssq'));
document.getElementById('copy_all_ssq_complex_numbers').addEventListener('click', () => copyAllComplexNumbers('ssq'));

document.getElementById('clear_dlt_complex_generated_numbers').addEventListener('click', () => clearComplexGeneratedNumbers('dlt'));
document.getElementById('copy_all_dlt_complex_numbers').addEventListener('click', () => copyAllComplexNumbers('dlt'));

// Event delegation for dynamically added complex prediction buttons
document.getElementById('ssq_complex_prediction_output').addEventListener('click', function(e) {
    if (e.target.classList.contains('check-generated-rules-btn')) {
        checkGeneratedRules(e.target.dataset.lotteryType, e.target.dataset.redBalls, e.target.dataset.blueBalls);
    }
    if (e.target.classList.contains('copy-to-clipboard-btn')) {
        copyToClipboard(e.target.dataset.copyText);
    }
});
document.getElementById('dlt_complex_prediction_output').addEventListener('click', function(e) {
    if (e.target.classList.contains('check-generated-rules-btn')) {
        checkGeneratedRules(e.target.dataset.lotteryType, e.target.dataset.redBalls, e.target.dataset.blueBalls);
    }
    if (e.target.classList.contains('copy-to-clipboard-btn')) {
        copyToClipboard(e.target.dataset.copyText);
    }
});

// ==================== 智能筛选功能 ====================

// 收集智能筛选选项（从checkbox组中获取选中的值）
function getSmartFilterOptions(lotteryType) {
    const options = {};
    
    // 辅助函数：从checkbox组获取选中的值（排除"不限制"）
    function getCheckedValues(groupId) {
        const group = document.getElementById(groupId);
        if (!group) return [];
        const checked = group.querySelectorAll('.form-check-input:checked:not(.smart-filter-disabled)');
        const values = [];
        checked.forEach(function(cb) {
            values.push(cb.value);
        });
        return values;
    }
    
    // 辅助函数：检查"不限制"是否被选中
    function isDisabled(groupId) {
        const group = document.getElementById(groupId);
        if (!group) return true;
        const disabledChecked = group.querySelectorAll('.smart-filter-disabled:checked');
        return disabledChecked.length > 0;
    }
    
    // 分区原则
    const zoneValues = getCheckedValues(`${lotteryType}_smart_zone_ratio`);
    if (zoneValues.length > 0 && !isDisabled(`${lotteryType}_smart_zone_ratio`)) {
        options.zone_ratio = zoneValues;
    }
    
    // 连号原则
    const consValues = getCheckedValues(`${lotteryType}_smart_consecutive`);
    if (consValues.length > 0 && !isDisabled(`${lotteryType}_smart_consecutive`)) {
        options.consecutive = consValues;
    }
    
    // 与上期重号
    const repeatValues = getCheckedValues(`${lotteryType}_smart_repeat`);
    if (repeatValues.length > 0 && !isDisabled(`${lotteryType}_smart_repeat`)) {
        options.repeat = repeatValues;
    }
    
    // 遗漏号原则
    const omitValues = getCheckedValues(`${lotteryType}_smart_omission_pattern`);
    if (omitValues.length > 0 && !isDisabled(`${lotteryType}_smart_omission_pattern`)) {
        options.omission_pattern = omitValues;
    }
    
    // 奇偶比
    const oeValues = getCheckedValues(`${lotteryType}_smart_odd_even`);
    if (oeValues.length > 0 && !isDisabled(`${lotteryType}_smart_odd_even`)) {
        options.odd_even = oeValues;
    }
    
    // 最大跨度
    const spanValues = getCheckedValues(`${lotteryType}_smart_span`);
    if (spanValues.length > 0 && !isDisabled(`${lotteryType}_smart_span`)) {
        options.span = spanValues;
    }
    
    // 号码总和
    const sumValues = getCheckedValues(`${lotteryType}_smart_sum`);
    if (sumValues.length > 0 && !isDisabled(`${lotteryType}_smart_sum`)) {
        options.sum = sumValues;
    }
    
    // 同尾号
    const tailValues = getCheckedValues(`${lotteryType}_smart_same_tail`);
    if (tailValues.length > 0 && !isDisabled(`${lotteryType}_smart_same_tail`)) {
        options.same_tail = tailValues;
    }
    
    // 邻号(边号)
    const neighborValues = getCheckedValues(`${lotteryType}_smart_neighbor`);
    if (neighborValues.length > 0 && !isDisabled(`${lotteryType}_smart_neighbor`)) {
        options.neighbor = neighborValues;
    }
    
    // AC值
    const acValues = getCheckedValues(`${lotteryType}_smart_ac_value`);
    if (acValues.length > 0 && !isDisabled(`${lotteryType}_smart_ac_value`)) {
        options.ac_value = acValues;
    }
    
    // 蓝球相关（不同彩票类型不同）
    if (lotteryType === 'ssq') {
        const blueValues = getCheckedValues(`${lotteryType}_smart_blue_omission`);
        if (blueValues.length > 0 && !isDisabled(`${lotteryType}_smart_blue_omission`)) {
            options.blue_omission = blueValues;
        }
    } else if (lotteryType === 'dlt') {
        const blueOeValues = getCheckedValues(`${lotteryType}_smart_blue_odd_even`);
        if (blueOeValues.length > 0 && !isDisabled(`${lotteryType}_smart_blue_odd_even`)) {
            options.blue_odd_even = blueOeValues;
        }
        const blueSizeValues = getCheckedValues(`${lotteryType}_smart_blue_size`);
        if (blueSizeValues.length > 0 && !isDisabled(`${lotteryType}_smart_blue_size`)) {
            options.blue_size = blueSizeValues;
        }
    }
    
    return options;
}

// 生成智能筛选号码
async function generateSmartFilterNumbers(lotteryType) {
    const outputDiv = document.getElementById(`${lotteryType}_smart_filter_output`);
    const count = 5; // 默认生成5组
    
    outputDiv.innerHTML = '<p class="text-muted">智能筛选中... <span class="loading-spinner"></span></p>';
    
    const options = getSmartFilterOptions(lotteryType);
    console.log(`Frontend: Generating smart filter numbers for ${lotteryType} with options:`, options);
    
    try {
        const response = await fetch('/api/prediction/smart_filter', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lottery_type: lotteryType,
                count: count,
                options: options
            })
        });
        const data = await response.json();
        
        console.log(`Frontend: Received smart filter response for ${lotteryType}:`, data);
        
        if (data.error) {
            outputDiv.innerHTML = `<p class="text-danger">智能筛选失败: ${data.error}</p>`;
            return;
        }
        
        if (!data.numbers || data.numbers.length === 0) {
            outputDiv.innerHTML = '<p class="text-warning">未生成符合条件的号码，请放宽筛选条件后重试。</p>';
            return;
        }
        
        let html = '';
        data.numbers.forEach((combo, index) => {
            const redBallsStr = combo.red_balls;
            const blueBallsStr = combo.blue_balls;
            const fullNumberStr = `红球: ${redBallsStr} 蓝球: ${blueBallsStr}`;
            
            html += `<div class="prediction-result-card smart-filter-generated">
                        <p class="card-title">智能筛选号码 ${index + 1}:</p>
                        <p>红球: ${renderBalls(combo.red_balls.split(',').map(Number), 'red', getConsecutiveGroupsJS(combo.red_balls.split(',').map(Number)))}</p>
                        <p>蓝球: ${renderBalls(combo.blue_balls.split(',').map(Number), 'blue', getConsecutiveGroupsJS(combo.blue_balls.split(',').map(Number)))}</p>
                        <div class="number-stats mt-2">
                            <small>红球: 奇偶比 ${combo.stats.red_odd_even_ratio}, 和值 ${combo.stats.red_sum}, 跨度 ${combo.stats.red_span}, 大小比 ${combo.stats.red_size_ratio}</small><br>
                            <small>蓝球: 奇偶比 ${combo.stats.blue_odd_even_ratio}, 和值 ${combo.stats.blue_sum}, 跨度 ${combo.stats.blue_span}, 大小比 ${combo.stats.blue_size_ratio}</small>
                        </div>
                        <button class="btn btn-sm btn-outline-primary me-2 check-generated-rules-btn" data-lottery-type="${lotteryType}" data-red-balls="${redBallsStr}" data-blue-balls="${blueBallsStr}">检查规则</button>
                        <button class="btn btn-sm btn-outline-secondary me-2 copy-to-clipboard-btn" data-copy-text="${fullNumberStr}">复制结果</button>
                    </div>`;
        });
        outputDiv.innerHTML = html;
        console.log(`Frontend: Successfully rendered smart filter numbers for ${lotteryType}.`);
        
    } catch (error) {
        console.error(`Frontend: Error generating smart filter numbers for ${lotteryType}:`, error);
        outputDiv.innerHTML = '<p class="text-danger">智能筛选失败。</p>';
    }
}

// 清除智能筛选号码
function clearSmartFilterNumbers(lotteryType) {
    document.getElementById(`${lotteryType}_smart_filter_output`).innerHTML = '<p class="text-muted">智能筛选号码将在此处生成。</p>';
    console.log(`Frontend: Cleared smart filter numbers for ${lotteryType}.`);
}

// 复制所有智能筛选号码
function copyAllSmartFilterNumbers(lotteryType) {
    let allNumbersText = `--- ${lotteryType.toUpperCase()} 智能筛选号码 ---\n`;
    const smartCards = document.querySelectorAll(`#${lotteryType}_smart_filter_output .prediction-result-card`);
    if (smartCards.length === 0) {
        allNumbersText += "无\n";
    } else {
        smartCards.forEach(card => {
            const redBalls = card.querySelector('p:nth-of-type(2)').innerText.replace('红球: ', '');
            const blueBalls = card.querySelector('p:nth-of-type(3)').innerText.replace('蓝球: ', '');
            allNumbersText += `${redBalls} ${blueBalls}\n`;
        });
    }
    copyToClipboard(allNumbersText);
}

// 智能筛选按钮事件监听
document.getElementById('generate_ssq_smart_filter').addEventListener('click', () => generateSmartFilterNumbers('ssq'));
document.getElementById('generate_dlt_smart_filter').addEventListener('click', () => generateSmartFilterNumbers('dlt'));

document.getElementById('clear_ssq_smart_numbers').addEventListener('click', () => clearSmartFilterNumbers('ssq'));
document.getElementById('clear_dlt_smart_numbers').addEventListener('click', () => clearSmartFilterNumbers('dlt'));

document.getElementById('copy_all_ssq_smart_numbers').addEventListener('click', () => copyAllSmartFilterNumbers('ssq'));
document.getElementById('copy_all_dlt_smart_numbers').addEventListener('click', () => copyAllSmartFilterNumbers('dlt'));

// 智能筛选输出区域的事件委托（用于检查规则和复制按钮）
document.getElementById('ssq_smart_filter_output').addEventListener('click', function(e) {
    if (e.target.classList.contains('check-generated-rules-btn')) {
        checkGeneratedRules(e.target.dataset.lotteryType, e.target.dataset.redBalls, e.target.dataset.blueBalls);
    }
    if (e.target.classList.contains('copy-to-clipboard-btn')) {
        copyToClipboard(e.target.dataset.copyText);
    }
});

document.getElementById('dlt_smart_filter_output').addEventListener('click', function(e) {
    if (e.target.classList.contains('check-generated-rules-btn')) {
        checkGeneratedRules(e.target.dataset.lotteryType, e.target.dataset.redBalls, e.target.dataset.blueBalls);
    }
    if (e.target.classList.contains('copy-to-clipboard-btn')) {
        copyToClipboard(e.target.dataset.copyText);
    }
});
