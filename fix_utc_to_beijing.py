"""将数据库中已有的UTC时间转为北京时间（+8小时）"""
from app import app
from models import db, UserFavorite, UserPurchasedTicket, User, News
from datetime import timedelta

def main():
    with app.app_context():
        now_bj_str = __import__('models').beijing_now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"当前北京时间: {now_bj_str}")
        
        # 修复 UserFavorite
        favs = UserFavorite.query.all()
        fixed_fav = 0
        for f in favs:
            if f.created_at:
                # 如果时间看起来是UTC（接近服务器时间0点而现在是8点），就加8小时
                # 统一对所有记录加8小时，因为之前全是utcnow
                f.created_at = f.created_at + timedelta(hours=8)
                fixed_fav += 1
        db.session.commit()
        print(f"已修复 UserFavorite: {fixed_fav} 条")
        
        # 修复 UserPurchasedTicket
        tickets = UserPurchasedTicket.query.all()
        fixed_ticket = 0
        fixed_checked = 0
        for t in tickets:
            if t.created_at:
                t.created_at = t.created_at + timedelta(hours=8)
                fixed_ticket += 1
            if t.checked_at:
                t.checked_at = t.checked_at + timedelta(hours=8)
                fixed_checked += 1
        db.session.commit()
        print(f"已修复 UserPurchasedTicket: created_at={fixed_ticket}, checked_at={fixed_checked}")
        
        # 修复 User
        users = User.query.all()
        fixed_user = 0
        fixed_login = 0
        for u in users:
            if u.created_at:
                u.created_at = u.created_at + timedelta(hours=8)
                fixed_user += 1
            if u.last_login_at:
                u.last_login_at = u.last_login_at + timedelta(hours=8)
                fixed_login += 1
        db.session.commit()
        print(f"已修复 User: created_at={fixed_user}, last_login_at={fixed_login}")
        
        # 修复 News
        news_list = News.query.all()
        fixed_news = 0
        for n in news_list:
            if n.created_at:
                n.created_at = n.created_at + timedelta(hours=8)
                fixed_news += 1
            if n.updated_at:
                n.updated_at = n.updated_at + timedelta(hours=8)
                fixed_news += 1
        db.session.commit()
        print(f"已修复 News: {fixed_news} 条")
        
        # 验证
        print("\n--- 验证结果 ---")
        if UserFavorite.query.first():
            print(f"UserFavorite 最新记录: {UserFavorite.query.first().created_at}")
        if UserPurchasedTicket.query.first():
            print(f"UserPurchasedTicket 最新记录: {UserPurchasedTicket.query.first().created_at}")
        if User.query.first():
            print(f"User 最新记录: {User.query.first().created_at}")
        
        print("\n✅ UTC→北京时间迁移完成！")

if __name__ == '__main__':
    main()
