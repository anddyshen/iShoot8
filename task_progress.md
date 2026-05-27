# 智选规则核查修复 - 任务清单

- [ ] 1. 修改 `check_repeat_with_previous` 函数 - 支持传入上期开奖数据参数
- [ ] 2. 修改 `check_neighbor_numbers` 函数 - 支持传入上期开奖数据参数
- [ ] 3. 修改 `calculate_smart_filter_stats_for_draw` 函数 - 支持基于指定期之前的数据计算遗漏
- [ ] 4. 新增 `check_user_numbers_against_smart_filter_rankings` 函数 - 检查用户号码符合规则排名
- [ ] 5. 新增 `/api/prize_check/smart_filter_check` API 端点 - 接受用户号码和彩票类型
- [ ] 6. 修改前端 `checkSmartFilterRules` 函数 - 获取用户选中的号码调用新 API
- [ ] 7. 修复蓝球遗漏排名逻辑 - 在 `check_draw_against_smart_filter_rankings` 中获取正确的排名数据
- [ ] 8. 测试修复效果
