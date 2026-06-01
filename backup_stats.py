"""
智能筛选统计数据备份脚本
用途：在数据库迁移/更新前备份可再生的统计数据
备份内容：SmartFilterStats, SmartFilterStatsRanking 两张表

使用方法：
  python backup_stats.py           # 备份到默认路径 backups/
  python backup_stats.py restore    # 从最新备份恢复
  python backup_stats.py list       # 列出所有备份文件
"""
import json
import os
import glob
from datetime import datetime

BACKUP_DIR = os.path.join(os.path.dirname(__file__), 'backups')

def ensure_backup_dir():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

def serialize_value(val):
    """序列化日期等特殊类型"""
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return val

def backup():
    """备份统计数据"""
    from app import app
    from models import db, SmartFilterStats, SmartFilterStatsRanking
    
    ensure_backup_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(BACKUP_DIR, f'smart_filter_backup_{timestamp}.json')
    
    with app.app_context():
        # 备份 stats
        stats = SmartFilterStats.query.all()
        stats_data = [{
            'id': s.id,
            'lottery_type': s.lottery_type,
            'issue': s.issue,
            'draw_date': serialize_value(s.draw_date),
            'rule_name': s.rule_name,
            'rule_value': s.rule_value
        } for s in stats]
        
        # 备份 rankings
        rankings = SmartFilterStatsRanking.query.all()
        rankings_data = [{
            'id': r.id,
            'lottery_type': r.lottery_type,
            'lookback_period': r.lookback_period,
            'rule_name': r.rule_name,
            'rank': r.rank,
            'rule_value': r.rule_value,
            'frequency': r.frequency,
            'percentage': r.percentage
        } for r in rankings]
        
        data = {
            'backup_time': timestamp,
            'stats_count': len(stats_data),
            'rankings_count': len(rankings_data),
            'stats': stats_data,
            'rankings': rankings_data
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f'✅ 备份完成: {filename}')
        print(f'   SmartFilterStats: {len(stats_data)} 条')
        print(f'   SmartFilterStatsRanking: {len(rankings_data)} 条')

def restore():
    """从最新备份恢复"""
    from app import app
    from models import db, SmartFilterStats, SmartFilterStatsRanking
    
    ensure_backup_dir()
    files = sorted(glob.glob(os.path.join(BACKUP_DIR, 'smart_filter_backup_*.json')))
    
    if not files:
        print('❌ 没有找到备份文件')
        return
    
    latest = files[-1]
    print(f'从备份恢复: {latest}')
    
    with open(latest, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    with app.app_context():
        # 清空旧数据
        SmartFilterStats.query.filter_by(lottery_type='dlt').delete()
        SmartFilterStatsRanking.query.filter_by(lottery_type='dlt').delete()
        SmartFilterStats.query.filter_by(lottery_type='ssq').delete()
        SmartFilterStatsRanking.query.filter_by(lottery_type='ssq').delete()
        db.session.commit()
        
        # 恢复 stats
        for item in data['stats']:
            s = SmartFilterStats(
                lottery_type=item['lottery_type'],
                issue=item['issue'],
                rule_name=item['rule_name'],
                rule_value=item['rule_value']
            )
            # 恢复日期（如果有）
            if item.get('draw_date'):
                from datetime import date
                try:
                    s.draw_date = date.fromisoformat(item['draw_date'])
                except:
                    pass
            db.session.add(s)
        db.session.commit()
        
        # 恢复 rankings
        for item in data['rankings']:
            r = SmartFilterStatsRanking(
                lottery_type=item['lottery_type'],
                lookback_period=item['lookback_period'],
                rule_name=item['rule_name'],
                rank=item['rank'],
                rule_value=item['rule_value'],
                frequency=item['frequency'],
                percentage=item['percentage']
            )
            db.session.add(r)
        db.session.commit()
        
        # 验证
        s_count = SmartFilterStats.query.count()
        r_count = SmartFilterStatsRanking.query.count()
        print(f'✅ 恢复完成')
        print(f'   SmartFilterStats: {s_count} 条')
        print(f'   SmartFilterStatsRanking: {r_count} 条')

def list_backups():
    """列出所有备份"""
    ensure_backup_dir()
    files = sorted(glob.glob(os.path.join(BACKUP_DIR, 'smart_filter_backup_*.json')))
    
    if not files:
        print('没有找到备份文件')
        return
    
    print(f'找到 {len(files)} 个备份:')
    for f in files:
        size = os.path.getsize(f)
        name = os.path.basename(f)
        print(f'  {name} ({size/1024:.1f} KB)')

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == 'restore':
            restore()
        elif sys.argv[1] == 'list':
            list_backups()
        else:
            print(f'未知命令: {sys.argv[1]}')
            print('用法: python backup_stats.py [backup|restore|list]')
    else:
        backup()
