"""
测试连号原则修复的验证脚本
"""
import sys
sys.path.insert(0, 'd:\\Projects\\iShoot8')

# 我们需要模拟 Flask 应用上下文，因为 smart_filter_engine 中有 current_app 引用
# 但 check_consecutive_balls 不依赖 Flask，可以直接测试
from smart_filter_engine import check_consecutive_balls

test_results = []

def run_test(name, balls, max_groups, max_length, expected_pass, expected_count, check_fn=None):
    """运行测试并记录结果"""
    p, count, groups = check_consecutive_balls(balls, max_groups, max_length)
    
    if check_fn:
        actual_pass = check_fn(p, count, groups)
    else:
        actual_pass = p
    
    status = "PASS" if actual_pass == expected_pass else "FAIL"
    detail = f"balls={balls}, max_groups={max_groups}, max_length={max_length}, count={count}, groups={[list(g) for g in groups]}"
    print(f"{status}: {name}")
    print(f"  {detail}")
    print(f"  期望 passed={expected_pass}, 实际 passed={actual_pass}")
    print()
    return actual_pass == expected_pass

print("=" * 60)
print("连号原则修复测试")
print("=" * 60)
print()

# 测试 1: 无连号 - [1,3,5,7,9,11] 没有连号，期望通过
run_test(
    "无连号测试 (应通过)",
    [1, 3, 5, 7, 9, 11], 0, 0,
    True, 0,
    lambda p, c, g: p and c == 0
)

# 测试 2: 1组2连号 - [5,6,10,15,20,25] 有1组2连号(5,6)，期望通过
run_test(
    "1组2连号测试 (应通过)",
    [5, 6, 10, 15, 20, 25], 1, 2,
    True, 1,
    lambda p, c, g: p and c == 1 and any(len(x) == 2 for x in g)
)

# 测试 3: 无连号不匹配1组2连号 - 期望不通过
run_test(
    "无连号不应通过1组2连号",
    [1, 3, 5, 7, 9, 11], 1, 2,
    False, 0,
    lambda p, c, g: p and c == 1 and any(len(x) == 2 for x in g)
)

# 测试 4: 2组2连号不匹配1组2连号 - 期望不通过
run_test(
    "2组2连号不应通过1组2连号",
    [5, 6, 10, 11, 20, 25], 1, 2,
    False, 2,
    lambda p, c, g: p and c == 1 and any(len(x) == 2 for x in g)
)

# 测试 5: 2组2连号 - [5,6,10,11,20,25] 有2组2连号，期望通过
run_test(
    "2组2连号测试 (应通过)",
    [5, 6, 10, 11, 20, 25], 2, 2,
    True, 2,
    lambda p, c, g: p and c == 2 and all(len(x) == 2 for x in g)
)

# 测试 6: 1组3连号 - [5,6,7,10,15,20] 有1组3连号(5,6,7)，期望通过
run_test(
    "1组3连号测试 (应通过)",
    [5, 6, 7, 10, 15, 20], 1, 3,
    True, 1,
    lambda p, c, g: p and c == 1 and any(len(x) == 3 for x in g)
)

# 测试 7: 1组2连号不匹配1组3连号 - 期望不通过
run_test(
    "1组2连号不应通过1组3连号",
    [5, 6, 10, 15, 20, 25], 1, 3,
    False, 1,
    lambda p, c, g: p and c == 1 and any(len(x) == 3 for x in g)
)

# 测试 8: 2组2连号不匹配2组2连号（但其中一组不是标准的2连号）
# [5,6,10,11,15,20] - 两组都是2连号，但max_groups=2时检查通过的
run_test(
    "2组2连号正确匹配测试",
    [5, 6, 10, 11, 15, 20], 2, 2,
    True, 2,
    lambda p, c, g: p and c == 2 and all(len(x) == 2 for x in g)
)

# 测试 9: 3连号 + 1个单独号码不应通过1组2连号
run_test(
    "1组3连号不应通过1组2连号",
    [5, 6, 7, 10, 15, 20], 1, 2,
    False, 1,
    lambda p, c, g: p and c == 1 and any(len(x) == 2 for x in g)
)

print("=" * 60)
print("测试完成")
