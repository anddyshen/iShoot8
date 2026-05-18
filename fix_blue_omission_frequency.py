"""
修复脚本：重建 blue_omission 排名 - 按出现频率排序而非遗漏期数
"""
from app import app
from smart_filter_engine import update_smart_filter_stats

with app.app_context():
    from models import SmartFilterStatsRanking, db
    
    # 清除所有 blue_omission 排名数据
    print("清除旧的 blue_omission 排名数据...")
    deleted = SmartFilterStatsRanking.query.filter_by(rule_name='blue_omission').delete()
    db.session.commit()
    print(f"  删除了 {deleted} 条 blue_omission 排名记录")
    
    # 重新触发统计更新（会按新逻辑重新计算排名）
    print("\n重新计算双色球智能筛选统计...")
    update_smart_filter_stats('ssq', app)
    
    print("\n重新计算大乐透智能筛选统计...")
    update_smart_filter_stats('dlt', app)
    
    # 验证结果
    print("\n验证修复结果（按出现频率排序的前5名）：")
    for lt in ['ssq', 'dlt']:
        rankings = SmartFilterStatsRanking.query.filter_by(
            lottery_type=lt, 
            rule_name='blue_omission',
            lookback_period=100
        ).order_by(SmartFilterStatsRanking.rank).all()
        print(f"\n{lt} 蓝球出现频率前5 (回溯100期):")
        for r in rankings[:5]:
            print(f"  第{r.rank}名: 号码{r.rule_value}, 出现{r.frequency}次, 占比{r.percentage}%")
    
    print("\n修复完成！")
