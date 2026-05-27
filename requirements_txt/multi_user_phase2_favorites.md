# iShoot 多用户模式 - Phase 2：心仪号码功能

> 预估工时：1-2 天
> 前置依赖：Phase 1（用户系统已就绪）
> 当前阶段目标：实现心仪号码的收藏、管理、跨页面嵌入

## 需要修改的文件

### 1. models.py - 新增 FavoriteNumbers 模型

在 models.py 文件末尾（已有 User 模型之后）新增：

```python
class FavoriteNumbers(db.Model):
    """心仪号码表"""
    __tablename__ = 'favorite_numbers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    lottery_type = db.Column(db.String(10), nullable=False)  # 'ssq' 或 'dlt'
    red_balls = db.Column(db.String(50), nullable=False)      # 逗号分隔，如 "01,05,12,18,22,30"
    blue_balls = db.Column(db.String(20), nullable=False)     # 逗号分隔，如 "07"
    note = db.Column(db.String(200), default='')              # 备注
    tags = db.Column(db.String(200), default='')              # 标签，逗号分隔
    source_page = db.Column(db.String(50), default='')        # 来源页面: prediction, prize_check, history
    is_active = db.Column(db.Boolean, default=True)           # 是否有效
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 唯一约束：同一用户不能收藏完全相同的号码组合
    __table_args__ = (
        db.UniqueConstraint('user_id', 'lottery_type', 'red_balls', 'blue_balls', name='uq_user_favorite'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'lottery_type': self.lottery_type,
            'red_balls': self.red_balls,
            'blue_balls': self.blue_balls,
            'red_balls_list': [int(x) for x in self.red_balls.split(',')],
            'blue_balls_list': [int(x) for x in self.blue_balls.split(',')],
            'note': self.note,
            'tags': self.tags,
            'source_page': self.source_page,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f'<FavoriteNumbers {self.user_id} - {self.lottery_type}: {self.red_balls}|{self.blue_balls}>'
```

### 2. 在 User 模型中添加关联（如果 Phase 1 中已添加则跳过）

确保 User 模型中已有：
```python
favorites = db.relationship('FavoriteNumbers', backref='user', lazy='dynamic')
```

### 3. 在 user_routes.py 中添加心仪号码 API

创建或编辑 `user_routes.py`（如果不存在则新建）：

```python
# user_routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, FavoriteNumbers
from utils import format_lottery_numbers

bp = Blueprint('user_routes', __name__, url_prefix='/user')

# ==============================
# 页面路由
# ==============================

@bp.route('/favorites')
@login_required
def favorites():
    """心仪号码管理页面"""
    return render_template('user/favorites.html')

@bp.route('/profile')
@login_required
def profile():
    """个人中心页面"""
    return render_template('user/profile.html')

# ==============================
# 心仪号码 API
# ==============================

@bp.route('/api/favorites', methods=['GET'])
@login_required
def api_get_favorites():
    """获取用户的心仪号码列表"""
    lottery_type = request.args.get('lottery_type')  # 可选筛选
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = FavoriteNumbers.query.filter_by(user_id=current_user.id, is_active=True)
    
    if lottery_type and lottery_type in ('ssq', 'dlt'):
        query = query.filter_by(lottery_type=lottery_type)
    
    # 按创建时间降序排列
    query = query.order_by(FavoriteNumbers.created_at.desc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'favorites': [item.to_dict() for item in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
        'per_page': per_page,
    })


@bp.route('/api/favorites/add', methods=['POST'])
@login_required
def api_add_favorite():
    """添加心仪号码"""
    data = request.get_json()
    
    lottery_type = data.get('lottery_type')
    red_balls = data.get('red_balls')
    blue_balls = data.get('blue_balls')
    note = data.get('note', '')
    tags = data.get('tags', '')
    source_page = data.get('source_page', '')
    
    # 验证参数
    if not lottery_type or lottery_type not in ('ssq', 'dlt'):
        return jsonify({'error': '无效的彩票类型'}), 400
    
    if not red_balls or not blue_balls:
        return jsonify({'error': '请提供完整的号码'}), 400
    
    try:
        # 标准化号码格式（去除多余空格、排序）
        red_list = format_lottery_numbers(red_balls)
        blue_list = format_lottery_numbers(blue_balls)
        normalized_red = ','.join(map(str, red_list))
        normalized_blue = ','.join(map(str, blue_list))
    except Exception as e:
        return jsonify({'error': f'号码格式错误: {str(e)}'}), 400
    
    # 检查是否已存在（同一用户的相同号码）
    existing = FavoriteNumbers.query.filter_by(
        user_id=current_user.id,
        lottery_type=lottery_type,
        red_balls=normalized_red,
        blue_balls=normalized_blue
    ).first()
    
    if existing:
        if existing.is_active:
            return jsonify({'error': '该号码已在心仪列表中', 'id': existing.id}), 409
        else:
            # 重新激活
            existing.is_active = True
            existing.note = note or existing.note
            existing.tags = tags or existing.tags
            existing.source_page = source_page or existing.source_page
            existing.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'message': '已重新添加到心仪列表', 'favorite': existing.to_dict()})
    
    # 创建新的收藏
    favorite = FavoriteNumbers(
        user_id=current_user.id,
        lottery_type=lottery_type,
        red_balls=normalized_red,
        blue_balls=normalized_blue,
        note=note,
        tags=tags,
        source_page=source_page,
    )
    
    db.session.add(favorite)
    db.session.commit()
    
    return jsonify({'message': '已添加到心仪列表', 'favorite': favorite.to_dict()})


@bp.route('/api/favorites/<int:fav_id>', methods=['DELETE'])
@login_required
def api_delete_favorite(fav_id):
    """删除心仪号码（软删除）"""
    favorite = FavoriteNumbers.query.filter_by(id=fav_id, user_id=current_user.id).first()
    if not favorite:
        return jsonify({'error': '未找到该心仪号码'}), 404
    
    favorite.is_active = False
    db.session.commit()
    
    return jsonify({'message': '已从心仪列表移除'})


@bp.route('/api/favorites/<int:fav_id>', methods=['PUT'])
@login_required
def api_update_favorite(fav_id):
    """更新心仪号码的备注和标签"""
    favorite = FavoriteNumbers.query.filter_by(id=fav_id, user_id=current_user.id).first()
    if not favorite:
        return jsonify({'error': '未找到该心仪号码'}), 404
    
    data = request.get_json()
    
    if 'note' in data:
        favorite.note = data['note']
    if 'tags' in data:
        favorite.tags = data['tags']
    
    db.session.commit()
    
    return jsonify({'message': '更新成功', 'favorite': favorite.to_dict()})


@bp.route('/api/favorites/batch_delete', methods=['POST'])
@login_required
def api_batch_delete_favorites():
    """批量删除心仪号码"""
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'error': '请选择要删除的号码'}), 400
    
    count = FavoriteNumbers.query.filter(
        FavoriteNumbers.id.in_(ids),
        FavoriteNumbers.user_id == current_user.id
    ).update({'is_active': False}, synchronize_session=False)
    
    db.session.commit()
    
    return jsonify({'message': f'已移除 {count} 个心仪号码', 'deleted_count': count})


@bp.route('/api/favorites/check', methods=['POST'])
@login_required
def api_check_favorite():
    """检查某个号码是否已在心仪列表中"""
    data = request.get_json()
    lottery_type = data.get('lottery_type')
    red_balls = data.get('red_balls')
    blue_balls = data.get('blue_balls')
    
    if not all([lottery_type, red_balls, blue_balls]):
        return jsonify({'error': '参数不完整'}), 400
    
    try:
        red_list = format_lottery_numbers(red_balls)
        blue_list = format_lottery_numbers(blue_balls)
        normalized_red = ','.join(map(str, red_list))
        normalized_blue = ','.join(map(str, blue_list))
    except Exception as e:
        return jsonify({'error': f'号码格式错误: {str(e)}'}), 400
    
    existing = FavoriteNumbers.query.filter_by(
        user_id=current_user.id,
        lottery_type=lottery_type,
        red_balls=normalized_red,
        blue_balls=normalized_blue,
        is_active=True
    ).first()
    
    return jsonify({
        'is_favorited': existing is not None,
        'favorite_id': existing.id if existing else None,
    })
```

### 4. 创建收藏按钮组件

**templates/components/favorite_btn.html**：
```html
{% macro favorite_btn(lottery_type, red_balls, blue_balls, source_page='', size='sm') %}
<button type="button" 
        class="btn btn-outline-danger btn-{{ size }} favorite-btn"
        data-lottery-type="{{ lottery_type }}"
        data-red-balls="{{ red_balls }}"
        data-blue-balls="{{ blue_balls }}"
        data-source-page="{{ source_page }}"
        title="添加到心仪列表">
    <span class="fav-icon">🤍</span>
    <span class="fav-text">收藏</span>
</button>
{% endmacro %}
```

### 5. 心仪号码管理页面

**templates/user/favorites.html** 主要内容：
- 分彩种 Tab 切换（SSQ / DLT / 全部）
- 号码卡片列表：显示号码球、备注、标签、来源、收藏时间
- 操作按钮：编辑备注、删除、批量选择
- "购买此号码"按钮（跳转到购买记录录入页，为 Phase 3 预留）
- 空状态提示
- 分页

### 6. 在以下页面嵌入收藏按钮

**templates/prediction.html** - 预测页面：
- 在生成的号码组合区域，每个号码组旁添加收藏按钮
- 调用 `favorite_btn` 宏，传入当前号码的 lottery_type、red_balls、blue_balls
- source_page 传 'prediction'

**templates/prize_check.html** - 对奖中心：
- 在用户输入的号码组合显示区域，每个号码旁添加收藏按钮
- 源页面传 'prize_check'

**templates/history.html** - 历史数据页面：
- 在每期开奖号码显示区域添加收藏按钮
- 源页面传 'history'

### 7. 前端 JavaScript

在 **static/js/user.js** 中添加（如果不存在则新建）：

```javascript
// user.js - 用户相关前端逻辑

$(document).ready(function() {
    // 心仪号码收藏按钮点击事件
    $(document).on('click', '.favorite-btn', function() {
        const btn = $(this);
        const lotteryType = btn.data('lottery-type');
        const redBalls = btn.data('red-balls');
        const blueBalls = btn.data('blue-balls');
        const sourcePage = btn.data('source-page');
        
        // 检查是否已收藏
        $.ajax({
            url: '/user/api/favorites/check',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                lottery_type: lotteryType,
                red_balls: redBalls,
                blue_balls: blueBalls
            }),
            success: function(checkResp) {
                if (checkResp.is_favorited) {
                    // 已收藏，执行取消收藏
                    $.ajax({
                        url: '/user/api/favorites/' + checkResp.favorite_id,
                        method: 'DELETE',
                        success: function() {
                            updateFavBtnState(btn, false);
                            showToast('已从心仪列表移除', 'info');
                        },
                        error: function(xhr) {
                            showToast('操作失败: ' + xhr.responseJSON?.error, 'danger');
                        }
                    });
                } else {
                    // 未收藏，执行收藏
                    $.ajax({
                        url: '/user/api/favorites/add',
                        method: 'POST',
                        contentType: 'application/json',
                        data: JSON.stringify({
                            lottery_type: lotteryType,
                            red_balls: redBalls,
                            blue_balls: blueBalls,
                            source_page: sourcePage
                        }),
                        success: function() {
                            updateFavBtnState(btn, true);
                            showToast('已添加到心仪列表 ❤️', 'success');
                        },
                        error: function(xhr) {
                            if (xhr.status === 401) {
                                showToast('请先登录', 'warning');
                                // 延迟跳转到登录页
                                setTimeout(function() {
                                    window.location.href = '/auth/login?next=' + encodeURIComponent(window.location.pathname);
                                }, 1500);
                            } else {
                                showToast('操作失败: ' + (xhr.responseJSON?.error || '未知错误'), 'danger');
                            }
                        }
                    });
                }
            },
            error: function(xhr) {
                if (xhr.status === 401) {
                    showToast('请先登录', 'warning');
                    setTimeout(function() {
                        window.location.href = '/auth/login?next=' + encodeURIComponent(window.location.pathname);
                    }, 1500);
                }
            }
        });
    });
    
    // 更新收藏按钮状态
    function updateFavBtnState(btn, isFavorited) {
        const icon = btn.find('.fav-icon');
        const text = btn.find('.fav-text');
        if (isFavorited) {
            icon.text('❤️');
            text.text('已收藏');
            btn.removeClass('btn-outline-danger').addClass('btn-danger');
        } else {
            icon.text('🤍');
            text.text('收藏');
            btn.removeClass('btn-danger').addClass('btn-outline-danger');
        }
    }
    
    // 初始化已收藏按钮状态（页面加载时检查所有收藏按钮）
    function initFavoriteButtons() {
        $('.favorite-btn').each(function() {
            const btn = $(this);
            const lotteryType = btn.data('lottery-type');
            const redBalls = btn.data('red-balls');
            const blueBalls = btn.data('blue-balls');
            
            $.ajax({
                url: '/user/api/favorites/check',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    lottery_type: lotteryType,
                    red_balls: redBalls,
                    blue_balls: blueBalls
                }),
                success: function(resp) {
                    if (resp.is_favorited) {
                        updateFavBtnState(btn, true);
                    }
                }
            });
        });
    }
    
    initFavoriteButtons();
    
    // Toast 消息提示
    function showToast(message, type) {
        // 如果已经有 toast 容器则复用，否则创建
        let container = $('#toast-container');
        if (container.length === 0) {
            container = $('<div id="toast-container" style="position:fixed;top:20px;right:20px;z-index:9999;"></div>');
            $('body').append(container);
        }
        
        const toast = $(`
            <div class="toast show" role="alert" style="min-width:200px;">
                <div class="toast-header text-${type}">
                    <strong class="me-auto">提示</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">${message}</div>
            </div>
        `);
        
        container.append(toast);
        setTimeout(function() {
            toast.remove();
        }, 3000);
    }
});
```

### 8. 确保 user_routes.py 蓝图在 app.py 中注册

在 app.py 中添加：
```python
import user_routes
app.register_blueprint(user_routes.bp)
```

## 测试清单

- [ ] 未登录点击收藏按钮，提示"请先登录"
- [ ] 已登录点击收藏按钮，成功添加到心仪列表
- [ ] 再次点击同一号码，取消收藏
- [ ] 预测页面生成的号码可以收藏
- [ ] 对奖中心输入的号码可以收藏
- [ ] 历史页面的开奖号码可以收藏
- [ ] 心仪号码管理页面正确显示所有收藏
- [ ] 可以编辑备注和标签
- [ ] 可以批量删除
- [ ] 不同用户的收藏相互隔离
- [ ] 重复收藏同一号码提示已存在
