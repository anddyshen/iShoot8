# auth_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timezone, timedelta
from models import db, User, UserFavorite, UserPurchasedTicket, SSQDraw, DLTDraw
from config import CURRENT_SETTINGS

# 北京时间（UTC+8）— 返回 naive datetime，与 models.py 保持一致
BEIJING_TZ = timezone(timedelta(hours=8))
def beijing_now():
    return datetime.now(BEIJING_TZ).replace(tzinfo=None)

bp = Blueprint('auth_routes', __name__, url_prefix='/auth')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    # 检查注册开关
    if not CURRENT_SETTINGS.get('allow_registration', False):
        flash('管理员已关闭注册功能。', 'warning')
        return redirect(url_for('auth_routes.login'))
    
    if current_user.is_authenticated:
        return redirect(url_for('routes.index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        email = request.form.get('email', '').strip()
        nickname = request.form.get('nickname', '').strip()
        
        # 验证
        if not username or len(username) < 3:
            flash('用户名至少3个字符。', 'danger')
            return render_template('user/register.html')
        
        if not password or len(password) < 6:
            flash('密码至少6个字符。', 'danger')
            return render_template('user/register.html')
        
        if password != confirm_password:
            flash('两次输入的密码不一致。', 'danger')
            return render_template('user/register.html')
        
        if User.query.filter_by(username=username).first():
            flash('用户名已被占用。', 'danger')
            return render_template('user/register.html')
        
        if email and User.query.filter_by(email=email).first():
            flash('邮箱已被占用。', 'danger')
            return render_template('user/register.html')
        
        # 创建用户
        user = User(
            username=username,
            email=email if email else None,
            nickname=nickname if nickname else username,
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功，请登录。', 'success')
        return redirect(url_for('auth_routes.login'))
    
    return render_template('user/register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if current_user.is_authenticated:
        return redirect(url_for('routes.index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('用户名或密码错误。', 'danger')
            return render_template('user/login.html')
        
        if not user.is_active:
            flash('账户已被禁用，请联系管理员。', 'danger')
            return render_template('user/login.html')
        
        # 更新最后登录时间
        user.last_login_at = beijing_now()
        db.session.commit()
        
        login_user(user, remember=remember)
        
        # 重定向到登录前页面
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        # 如果是管理员，登录后跳转到后台管理
        if user.is_admin:
            return redirect(url_for('admin_routes.admin_dashboard'))
        return redirect(url_for('routes.index'))
    
    return render_template('user/login.html')

@bp.route('/logout')
def logout():
    """退出登录"""
    logout_user()
    flash('已退出登录。', 'info')
    return redirect(url_for('routes.index'))

# ===== API 接口 =====

@bp.route('/api/me')
@login_required
def api_me():
    """获取当前用户信息"""
    return jsonify(current_user.to_dict())

@bp.route('/api/update_profile', methods=['POST'])
@login_required
def api_update_profile():
    """更新个人资料"""
    data = request.get_json()
    
    if 'nickname' in data:
        current_user.nickname = data['nickname']
    if 'email' in data:
        # 检查邮箱是否已被其他用户使用
        existing = User.query.filter(User.email == data['email'], User.id != current_user.id).first()
        if existing:
            return jsonify({'error': '邮箱已被占用'}), 400
        current_user.email = data['email']
    
    db.session.commit()
    return jsonify({'message': '更新成功', 'user': current_user.to_dict()})

# ===== 页面路由 =====

@bp.route('/profile')
@login_required
def profile():
    """个人中心页面"""
    return render_template('user/profile.html')

@bp.route('/favorites')
@login_required
def favorites():
    """心仪号码页面"""
    return render_template('user/favorites.html')

@bp.route('/purchased')
@login_required
def purchased():
    """已购号码页面"""
    return render_template('user/purchased.html')


@bp.route('/api/change_password', methods=['POST'])
@login_required
def api_change_password():
    """修改密码"""
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    
    if not current_user.check_password(old_password):
        return jsonify({'error': '当前密码错误'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': '新密码至少6个字符'}), 400
    
    if new_password != confirm_password:
        return jsonify({'error': '两次输入的新密码不一致'}), 400
    
    current_user.set_password(new_password)
    db.session.commit()
    return jsonify({'message': '密码修改成功'})


def _check_ticket_prize(ticket):
    """对单个已购号码进行对奖，更新 prize_amount 和 prize_level"""
    if ticket.lottery_type == 'ssq':
        draw = SSQDraw.query.filter_by(issue=ticket.issue).first()
    elif ticket.lottery_type == 'dlt':
        draw = DLTDraw.query.filter_by(issue=ticket.issue).first()
    else:
        return
    
    if not draw:
        # 未开奖，清空奖金
        ticket.prize_amount = 0.0
        ticket.prize_level = None
        ticket.checked_at = beijing_now()
        return
    
    user_reds = sorted([int(x.strip()) for x in ticket.red_balls.split(',')])
    user_blues = sorted([int(x.strip()) for x in ticket.blue_balls.split(',')])
    draw_reds = draw.get_red_balls_list()
    draw_blues = draw.get_blue_balls_list()
    
    red_match = len(set(user_reds) & set(draw_reds))
    blue_match = len(set(user_blues) & set(draw_blues))
    
    prize_amount = 0.0
    prize_level = None
    
    if ticket.lottery_type == 'ssq':
        if red_match == 6 and blue_match == 1:
            prize_level, prize_amount = '一等奖', '浮动'
        elif red_match == 6:
            prize_level, prize_amount = '二等奖', '浮动'
        elif red_match == 5 and blue_match == 1:
            prize_level, prize_amount = '三等奖', 3000
        elif red_match == 5 or (red_match == 4 and blue_match == 1):
            prize_level, prize_amount = '四等奖', 200
        elif red_match == 4 or (red_match == 3 and blue_match == 1):
            prize_level, prize_amount = '五等奖', 10
        elif blue_match == 1:
            prize_level, prize_amount = '六等奖', 5
    elif ticket.lottery_type == 'dlt':
        if red_match == 5 and blue_match == 2:
            prize_level, prize_amount = '一等奖', '浮动'
        elif red_match == 5 and blue_match == 1:
            prize_level, prize_amount = '二等奖', '浮动'
        elif red_match == 5 or (red_match == 4 and blue_match == 2):
            prize_level, prize_amount = '三等奖', 5000
        elif (red_match == 4 and blue_match == 1) or (red_match == 3 and blue_match == 2):
            prize_level, prize_amount = '四等奖', 300
        elif (red_match == 4) or (red_match == 3 and blue_match == 1) or (red_match == 2 and blue_match == 2):
            prize_level, prize_amount = '五等奖', 150
        elif (red_match == 3) or (red_match == 2 and blue_match == 1) or (red_match == 1 and blue_match == 2) or (red_match == 0 and blue_match == 2):
            prize_level, prize_amount = '六等奖', 15
        elif blue_match == 1:
            prize_level, prize_amount = '七等奖', 5
    
    if isinstance(prize_amount, str):
        prize_amount = 0.0  # 浮动奖暂时设为0
    
    ticket.prize_amount = prize_amount
    ticket.prize_level = prize_level
    ticket.checked_at = beijing_now()


# ===== 心仪号码 API =====

@bp.route('/api/favorites', methods=['GET'])
@login_required
def api_get_favorites():
    """获取用户的心仪号码列表（支持分页和彩种筛选）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    lottery_type = request.args.get('lottery_type', 'all').lower()
    
    query = UserFavorite.query.filter_by(user_id=current_user.id)
    
    if lottery_type in ['ssq', 'dlt']:
        query = query.filter_by(lottery_type=lottery_type)
    
    # 先获取全部数据以便计算统计
    all_favorites = query.order_by(UserFavorite.created_at.desc()).all()
    total = len(all_favorites)
    
    # 分页
    start = (page - 1) * per_page
    end = start + per_page
    page_favorites = all_favorites[start:end]
    
    return jsonify({
        'favorites': [f.to_dict() for f in page_favorites],
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': max(1, (total + per_page - 1) // per_page),
        'current_filter': lottery_type,
    })

@bp.route('/api/favorites', methods=['POST'])
@login_required
def api_add_favorite():
    """添加心仪号码"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    lottery_type = data.get('lottery_type', '').lower()
    red_balls = data.get('red_balls', '').strip()
    blue_balls = data.get('blue_balls', '').strip()
    note = data.get('note', '').strip()
    
    if lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': '无效的彩种'}), 400
    if not red_balls or not blue_balls:
        return jsonify({'error': '红球和蓝球号码不能为空'}), 400
    
    favorite = UserFavorite(
        user_id=current_user.id,
        lottery_type=lottery_type,
        red_balls=red_balls,
        blue_balls=blue_balls,
        combination=red_balls + '|' + blue_balls,
        note=note,
    )
    db.session.add(favorite)
    db.session.commit()
    
    return jsonify({'message': '添加成功', 'favorite': favorite.to_dict()})

@bp.route('/api/favorites/<int:favorite_id>', methods=['PUT'])
@login_required
def api_update_favorite(favorite_id):
    """更新心仪号码备注"""
    favorite = UserFavorite.query.filter_by(id=favorite_id, user_id=current_user.id).first()
    if not favorite:
        return jsonify({'error': '记录不存在'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    if 'note' in data:
        favorite.note = data['note'].strip()
    
    db.session.commit()
    return jsonify({'message': '更新成功', 'favorite': favorite.to_dict()})

@bp.route('/api/favorites/batch_delete', methods=['POST'])
@login_required
def api_batch_delete_favorites():
    """批量删除心仪号码"""
    data = request.get_json()
    if not data or 'ids' not in data or not isinstance(data['ids'], list):
        return jsonify({'error': '请提供要删除的ID列表'}), 400
    
    ids = data['ids']
    if not ids:
        return jsonify({'error': 'ID列表不能为空'}), 400
    
    deleted_count = 0
    for fav_id in ids:
        favorite = UserFavorite.query.filter_by(id=fav_id, user_id=current_user.id).first()
        if favorite:
            db.session.delete(favorite)
            deleted_count += 1
    
    db.session.commit()
    return jsonify({'message': f'成功删除 {deleted_count} 条记录'})

@bp.route('/api/favorites/<int:favorite_id>', methods=['DELETE'])
@login_required
def api_delete_favorite(favorite_id):
    """删除心仪号码"""
    favorite = UserFavorite.query.filter_by(id=favorite_id, user_id=current_user.id).first()
    if not favorite:
        return jsonify({'error': '记录不存在'}), 404
    
    db.session.delete(favorite)
    db.session.commit()
    return jsonify({'message': '删除成功'})


# ===== 已购号码 API =====

@bp.route('/api/purchased', methods=['GET'])
@login_required
def api_get_purchased():
    """获取用户的已购号码列表（支持分页和彩种筛选）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    lottery_type = request.args.get('lottery_type', 'all').lower()
    
    query = UserPurchasedTicket.query.filter_by(user_id=current_user.id)
    
    if lottery_type in ['ssq', 'dlt']:
        query = query.filter_by(lottery_type=lottery_type)
    
    # 先获取总数（总记录和总统计不分页）
    all_tickets = query.order_by(UserPurchasedTicket.created_at.desc()).all()
    total = len(all_tickets)
    
    # 计算统计信息（基于全部数据）
    total_cost = sum(t.cost * t.multiplier for t in all_tickets)
    total_prize = sum(t.prize_amount for t in all_tickets)
    
    # 分页
    start = (page - 1) * per_page
    end = start + per_page
    page_tickets = all_tickets[start:end]
    
    return jsonify({
        'tickets': [t.to_dict() for t in page_tickets],
        'stats': {
            'total_cost': total_cost,
            'total_prize': total_prize,
        },
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': max(1, (total + per_page - 1) // per_page),
        'current_filter': lottery_type,
    })

@bp.route('/api/purchased', methods=['POST'])
@login_required
def api_add_purchased():
    """添加已购号码"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    lottery_type = data.get('lottery_type', '').lower()
    issue = data.get('issue', '').strip()
    red_balls = data.get('red_balls', '').strip()
    blue_balls = data.get('blue_balls', '').strip()
    cost = float(data.get('cost', 2))
    multiplier = int(data.get('multiplier', 1))
    note = data.get('note', '').strip()
    
    if lottery_type not in ['ssq', 'dlt']:
        return jsonify({'error': '无效的彩种'}), 400
    if not issue or not red_balls or not blue_balls:
        return jsonify({'error': '期号、红球和蓝球号码不能为空'}), 400
    if cost < 2:
        return jsonify({'error': '投注金额至少2元'}), 400
    if multiplier < 1:
        return jsonify({'error': '倍数至少为1'}), 400
    
    # 自动对奖（如果存在开奖数据）
    prize_amount = 0.0
    prize_level = None
    draw = None
    
    if lottery_type == 'ssq':
        draw = SSQDraw.query.filter_by(issue=issue).first()
    elif lottery_type == 'dlt':
        draw = DLTDraw.query.filter_by(issue=issue).first()
    
    if draw:
        from prediction_engine import check_lottery_rules
        user_reds = sorted([int(x.strip()) for x in red_balls.split(',')])
        user_blues = sorted([int(x.strip()) for x in blue_balls.split(',')])
        draw_reds = draw.get_red_balls_list()
        draw_blues = draw.get_blue_balls_list()
        
        red_match = len(set(user_reds) & set(draw_reds))
        blue_match = len(set(user_blues) & set(draw_blues))
        
        # 简单对奖逻辑
        if lottery_type == 'ssq':
            if red_match == 6 and blue_match == 1:
                prize_level, prize_amount = '一等奖', '浮动'
            elif red_match == 6:
                prize_level, prize_amount = '二等奖', '浮动'
            elif red_match == 5 and blue_match == 1:
                prize_level, prize_amount = '三等奖', 3000
            elif red_match == 5 or (red_match == 4 and blue_match == 1):
                prize_level, prize_amount = '四等奖', 200
            elif red_match == 4 or (red_match == 3 and blue_match == 1):
                prize_level, prize_amount = '五等奖', 10
            elif blue_match == 1:
                prize_level, prize_amount = '六等奖', 5
        elif lottery_type == 'dlt':
            if red_match == 5 and blue_match == 2:
                prize_level, prize_amount = '一等奖', '浮动'
            elif red_match == 5 and blue_match == 1:
                prize_level, prize_amount = '二等奖', '浮动'
            elif red_match == 5 or (red_match == 4 and blue_match == 2):
                prize_level, prize_amount = '三等奖', 5000
            elif (red_match == 4 and blue_match == 1) or (red_match == 3 and blue_match == 2):
                prize_level, prize_amount = '四等奖', 300
            elif (red_match == 4) or (red_match == 3 and blue_match == 1) or (red_match == 2 and blue_match == 2):
                prize_level, prize_amount = '五等奖', 150
            elif (red_match == 3) or (red_match == 2 and blue_match == 1) or (red_match == 1 and blue_match == 2) or (red_match == 0 and blue_match == 2):
                prize_level, prize_amount = '六等奖', 15
            elif blue_match == 1:
                prize_level, prize_amount = '七等奖', 5
        
        if isinstance(prize_amount, str):
            prize_amount = 0.0  # 浮动奖暂时设为0
    
    ticket = UserPurchasedTicket(
        user_id=current_user.id,
        lottery_type=lottery_type,
        issue=issue,
        red_balls=red_balls,
        blue_balls=blue_balls,
        cost=cost,
        multiplier=multiplier,
        prize_amount=prize_amount,
        prize_level=prize_level,
        note=note,
        checked_at=beijing_now() if draw else None,
    )
    db.session.add(ticket)
    db.session.commit()
    
    return jsonify({'message': '添加成功', 'ticket': ticket.to_dict()})

@bp.route('/api/purchased/<int:ticket_id>', methods=['PUT'])
@login_required
def api_update_purchased(ticket_id):
    """更新已购号码记录（期号）- 更新后重新对奖"""
    ticket = UserPurchasedTicket.query.filter_by(id=ticket_id, user_id=current_user.id).first()
    if not ticket:
        return jsonify({'error': '记录不存在'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    if 'issue' in data:
        issue = data['issue'].strip()
        if not issue:
            return jsonify({'error': '期号不能为空'}), 400
        ticket.issue = issue
        
        # 期号变更后重新对奖
        _check_ticket_prize(ticket)
    
    db.session.commit()
    return jsonify({'message': '更新成功', 'ticket': ticket.to_dict()})

@bp.route('/api/purchased/check_all', methods=['POST'])
@login_required
def api_check_all_purchased():
    """对所有已购号码进行批量对奖"""
    tickets = UserPurchasedTicket.query.filter_by(user_id=current_user.id).all()
    
    checked_count = 0
    for ticket in tickets:
        _check_ticket_prize(ticket)
        checked_count += 1
    
    db.session.commit()
    
    return jsonify({'message': f'对奖完成，共处理 {checked_count} 条记录'})

@bp.route('/api/purchased/batch_delete', methods=['POST'])
@login_required
def api_batch_delete_purchased():
    """批量删除已购号码"""
    data = request.get_json()
    if not data or 'ids' not in data or not isinstance(data['ids'], list):
        return jsonify({'error': '请提供要删除的ID列表'}), 400
    
    ids = data['ids']
    if not ids:
        return jsonify({'error': 'ID列表不能为空'}), 400
    
    deleted_count = 0
    for tid in ids:
        ticket = UserPurchasedTicket.query.filter_by(id=tid, user_id=current_user.id).first()
        if ticket:
            db.session.delete(ticket)
            deleted_count += 1
    
    db.session.commit()
    return jsonify({'message': f'成功删除 {deleted_count} 条记录'})

@bp.route('/api/purchased/<int:ticket_id>', methods=['DELETE'])
@login_required
def api_delete_purchased(ticket_id):
    """删除已购号码记录"""
    ticket = UserPurchasedTicket.query.filter_by(id=ticket_id, user_id=current_user.id).first()
    if not ticket:
        return jsonify({'error': '记录不存在'}), 404
    
    db.session.delete(ticket)
    db.session.commit()
    return jsonify({'message': '删除成功'})
