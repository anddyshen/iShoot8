"""修复第二阶段问题数据：
问题：auth_routes.py 的 beijing_now() 返回 aware datetime（如 00:45:04+08:00），
SQLAlchemy 存储时自动转 UTC（减8小时变为 16:45:04），
fix_utc_to_beijing.py 又加了8小时（变为 00:45:04），
但如果有双重转换或重新读取保存，就会变成 08:45:04。

识别方法：
- 正确数据：created_at 时间在 checked_at 之前（先创建，后对奖）
- 错数据：created_at 比 checked_at 还晚，或比当前时间还晚
"""
from app import app
from models import db, UserFavorite, UserPurchasedTicket
from datetime import datetime, timedelta

def main():
    with app.app_context():
        now = datetime.now()
        print(f"当前服务器时间: {now}")
        
        # ===== 修复 UserPurchasedTicket =====
        tickets = UserPurchasedTicket.query.all()
        fixed_count = 0
        for t in tickets:
            if t.created_at:
                # 场景1：created_at 比当前时间还晚（将来），说明多了8小时
                if t.created_at > now:
                    hours_ahead = (t.created_at - now).total_seconds() / 3600
                    if 6 < hours_ahead < 10:  # 大约8小时
                        old = t.created_at
                        t.created_at = t.created_at - timedelta(hours=8)
                        print(f"  Ticket ID={t.id} (期号={t.issue}): {old} -> {t.created_at} (-8h, 比当前早{hours_ahead:.1f}h)")
                        fixed_count += 1
                        continue
                
                # 场景2：created_at 比 checked_at 还晚（先对奖后创建不可能）
                if t.checked_at and t.created_at > t.checked_at:
                    hours_ahead = (t.created_at - t.checked_at).total_seconds() / 3600
                    if 6 < hours_ahead < 10:
                        old = t.created_at
                        t.created_at = t.created_at - timedelta(hours=8)
                        print(f"  Ticket ID={t.id} (期号={t.issue}): {old} -> {t.created_at} (-8h, 比checked_at早{hours_ahead:.1f}h)")
                        fixed_count += 1
                        continue
            
            # 同样检查 checked_at
            if t.checked_at and t.checked_at > now:
                hours_ahead = (t.checked_at - now).total_seconds() / 3600
                if 6 < hours_ahead < 10:
                    old = t.checked_at
                    t.checked_at = t.checked_at - timedelta(hours=8)
                    print(f"  Ticket ID={t.id} checked_at: {old} -> {t.checked_at} (-8h)")
                    fixed_count += 1
        
        db.session.commit()
        print(f"\n已修复 UserPurchasedTicket: {fixed_count} 处")
        
        # ===== 修复 UserFavorite =====
        favs = UserFavorite.query.all()
        fixed_fav = 0
        for f in favs:
            if f.created_at and f.created_at > now:
                hours_ahead = (f.created_at - now).total_seconds() / 3600
                if 6 < hours_ahead < 10:
                    old = f.created_at
                    f.created_at = f.created_at - timedelta(hours=8)
                    print(f"  Favorite ID={f.id}: {old} -> {f.created_at} (-8h)")
                    fixed_fav += 1
        
        db.session.commit()
        print(f"已修复 UserFavorite: {fixed_fav} 条")
        
        # ===== 验证 =====
        print("\n--- 验证结果 ---")
        for t in UserPurchasedTicket.query.order_by(UserPurchasedTicket.id.desc()).limit(10).all():
            check = f", checked_at={t.checked_at}" if t.checked_at else ""
            print(f"  ID={t.id}: issue={t.issue}, created_at={t.created_at}{check}")
        
        print("\n✅ 修复完成！")

if __name__ == '__main__':
    main()
