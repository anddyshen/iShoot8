# iShoot 多用户模式 - Phase 3：购买记录与ROI统计

> 预估工时：2-3 天
> 前置依赖：Phase 2（心仪号码功能已就绪）
> 当前阶段目标：实现购买记录管理、剪贴板导入、自动对奖、ROI统计图表

## 需要修改的文件

### 1. models.py - 新增 PurchasedNumbers 模型

在 models.py 文件末尾（已有 FavoriteNumbers 模型之后）新增：

```python
class PurchasedNumbers(db.Model):
    """已购买号码表"""
    __tablename__ = 'purchased_numbers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    lottery_type = db.Column(db.String(10), nullable=False)  # 'ssq' 或 'dlt'
    issue = db.Column(db.String(10), default='')              # 购买的期号，为空表示长期守号
    red_balls = db.Column(db.String(50), nullable=False)      # 逗号分隔
    blue_balls = db.Column(db.String(20), nullable=False)     # 逗号分隔
    bet_count = db.Column(db.Integer, default=1)              # 注数（复式时自动计算）
    cost = db.Column(db.Float, default=2.0)                   # 花费金额
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)           # 是否仍在守号
    source = db.Column(db.String(50), default='manual')       # 来源: manual, favorite_import, clipboard
    note = db.Column(db.String(200), default='')              # 备注
    
    # 中奖统计（自动计算）
    total_winning_amount = db.Column(db.Float, default=0.0)   # 总中奖金额
    total_checked_periods = db.Column(db.Integer, default=0)  # 已检查期数
    roi = db.Column(db.Float, default=0.0)                    # 投资回报率 (%)
    last_check_issue = db.Column(db.String(10), default='')   # 最后检查的期号
    last_checked_at = db.Column(db.DateTime)                   # 最后检查时间
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'lottery_type': self.lottery_type,
            'issue': self.issue,
            'red_balls': self.red_balls,
            'blue_balls': self.blue_balls,
            'red_balls_list': [int(x) for x in self.red_balls.split(',')],
            'blue_balls_list': [int(x) for x in self.blue_balls.split(',')],
            'bet_count': self.bet_count,
            'cost': self.cost,
            'purchase_date': self.purchase_date.isoformat() if self.purchase_date else None,
            'is_active': self.is_active,
            'source': self.source,
            'note': self.note,
            'total_winning_amount': self.total_winning_amount,
            'total_checked_periods': self.total_checked_periods,
            'roi': self.roi,
            'last_check_issue': self.last_check_issue,
        }
    
    def __repr__(self):
        return f'<PurchasedNumbers {self.user_id} - {self.lottery_type}: {self.red_balls}|{self.blue_balls}>'
```

### 2. 在 user_routes.py 中添加购买记录 API

在 `user_routes.py` 中新增以下路由（追加到现有代码后）：

```python
# ==============================
# 页面路由
# ==============================

@bp.route('/purchased')
@login_required
def purchased():
    """购买记录管理页面"""
    return render_template('user/purchased.html')

@bp.route('/roi_stats')
@login_required
def roi_stats():
    """ROI统计页面"""
    return render_template('user/roi_stats.html')

# ==============================
# 购买记录 API
# ==============================

def calculate_auto_cost(red_balls_count, blue_balls_count, lottery_type):
    """
    根据号码数量和彩种自动计算注数和花费
    复式计算：C(red_count, base_red) * C(blue_count, base_blue)
    """
    import math
    if lottery_type == 'ssq':
        base_red, base_blue = 6, 1
    else:
        base_red, base_blue = 5, 2
    
    if red_balls_count < base_red or blue_balls_count < base_blue:
        return 1, 2.0  # 单注
    
    red_comb = math.comb(red_balls_count, base_red)
    blue_comb = math.comb(blue_balls_count, base_blue)
    total_bets = red_comb * blue_comb
    total_cost = total_bets * 2  # 每注2元
    
    return total_bets, total_cost


def auto_check_prizes(purchased, model_class):
    """
    对指定购买记录执行自动对奖
    返回中奖详情列表
    """
    from config import PRIZE_RULES, PER_BET_PRICE
    from utils import calculate_prize_details, format_lottery_numbers
    
    user_red = [int(x) for x in purchased.red_balls.split(',')]
    user_blue = [int(x) for x in purchased.blue_balls.split(',')]
    
    # 获取所有开奖数据（从购买日期之后或所有历史）
    query = model_class.query.order_by(model_class.issue.desc())
    
    # 如果有最后检查期号，只检查更新的
    if purchased.last_check_issue:
        query = query.filter(model_class.issue > purchased.last_check_issue)
    
    draws = query.all()
    
    total_win = 0.0
    checked_count = 0
    matches = []
    last_issue = purchased.last_check_issue
    
    for draw in draws:
        draw_red = draw.get_red_balls_list()
        draw_blue = draw.get_blue_balls_list()
        
        prize_details = calculate_prize_details(
            user_red, user_blue,
            draw_red, draw_blue,
            purchased.lottery_type
        )
        
        if prize_details:
            for prize_level, prize_count in prize_details.items():
                if prize_count > 0:
                    # 查找奖金金额
                    prize_rule = next(
                        (p for p in PRIZE_RULES[purchased.lottery_type]['prizes'] 
                         if p['level'] == prize_level), 
                        None
                    )
                    if prize_rule:
                        amount = prize_rule['amount']
                        if amount == '浮动':
                            # 浮动奖金从开奖记录中获取
                            if prize_level == '一等奖':
                                amount = draw.first_prize_amount or 5000000
                            elif prize_level == '二等奖':
                                amount = draw.second_prize_amount or 200000
                            else:
                                amount = 0
                        
                        win_amount = prize_count * amount
                        total_win += win_amount
                        
                        matches.append({
                            'issue': draw.issue,
                            'draw_date': draw.draw_date.strftime('%Y-%m-%d'),
                            'prize_level': prize_level,
                            'prize_count': prize_count,
                            'prize_amount': amount,
                            'win_amount': win_amount,
                        })
        
        checked_count += 1
        last_issue = draw.issue
    
    # 更新统计数据
    purchased.total_winning_amount += total_win
    purchased.total_checked_periods += checked_count
    purchased.last_check_issue = last_issue
    purchased.last_checked_at = datetime.utcnow()
    
    # 计算 ROI
    total_cost = purchased.cost * purchased.total_checked_periods
    if total_cost > 0:
        purchased.roi = (purchased.total_winning_amount / total_cost) * 100
    else:
        purchased.roi = 0.0
    
    return matches


@bp.route('/api/purchased', methods=['GET'])
@login_required
def api_get_purchased():
    """获取用户的购买记录"""
    lottery_type = request.args.get('lottery_type')
    is_active = request.args.get('is_active')  # 'true', 'false', 或 None
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = PurchasedNumbers.query.filter_by(user_id=current_user.id)
    
    if lottery_type and lottery_type in ('ssq', 'dlt'):
        query = query.filter_by(lottery_type=lottery_type)
    
    if is_active == 'true':
        query = query.filter_by(is_active=True)
    elif is_active == 'false':
        query = query.filter_by(is_active=False)
    
    query = query.order_by(PurchasedNumbers.purchase_date.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'records': [item.to_dict() for item in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
        'per_page': per_page,
    })


@bp.route('/api/purchased/add', methods=['POST'])
@login_required
def api_add_purchased():
    """添加单条购买记录"""
    data = request.get_json()
    
    lottery_type = data.get('lottery_type')
    red_balls = data.get('red_balls')
    blue_balls = data.get('blue_balls')
    issue = data.get('issue', '')
    note = data.get('note', '')
    source = data.get('source', 'manual')
    purchase_date_str = data.get('purchase_date')
    
    # 验证
    if not lottery_type or lottery_type not in ('ssq', 'dlt'):
        return jsonify({'error': '无效的彩票类型'}), 400
    if not red_balls or not blue_balls:
        return jsonify({'error': '请提供号码'}), 400
    
    from utils import format_lottery_numbers
    try:
        red_list = format_lottery_numbers(red_balls)
        blue_list = format_lottery_numbers(blue_balls)
    except Exception as e:
        return jsonify({'error': f'号码格式错误: {str(e)}'}), 400
    
    normalized_red = ','.join(map(str, red_list))
    normalized_blue = ','.join(map(str, blue_list))
    
    # 自动计算注数和花费
    bet_count, cost = calculate_auto_cost(len(red_list), len(blue_list), lottery_type)
    
    # 解析购买日期
    pdate = None
    if purchase_date_str:
        try:
            pdate = datetime.strptime(purchase_date_str, '%Y-%m-%d')
        except ValueError:
            pdate = datetime.utcnow()
    
    record = PurchasedNumbers(
        user_id=current_user.id,
        lottery_type=lottery_type,
        issue=issue,
        red_balls=normalized_red,
        blue_balls=normalized_blue,
        bet_count=bet_count,
        cost=cost,
        source=source,
        note=note,
        purchase_date=pdate or datetime.utcnow(),
    )
    
    db.session.add(record)
    db.session.commit()
    
    # 自动对奖
    model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
    matches = auto_check_prizes(record, model_class)
    db.session.commit()
    
    return jsonify({
        'message': '添加成功',
        'record': record.to_dict(),
        'matches': matches,
        'match_count': len(matches),
    })


@bp.route('/api/purchased/batch_add', methods=['POST'])
@login_required
def api_batch_add_purchased():
    """批量添加购买记录（支持剪贴板导入）"""
    data = request.get_json()
    text = data.get('text', '')
    lottery_type = data.get('lottery_type', 'ssq')
    
    if not text.strip():
        return jsonify({'error': '请粘贴号码内容'}), 400
    
    from utils import format_lottery_numbers
    
    lines = text.strip().split('\n')
    results = []
    errors = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 解析格式
        issue = ''
        balls_part = line
        
        # 格式3: 期号:号码 (如 "2026050:01,02,03,04,05,06|07")
        if ':' in line:
            parts = line.split(':', 1)
            issue = parts[0].strip()
            balls_part = parts[1].strip()
        
        # 格式1/2: 红球|蓝球 (如 "01,02,03,04,05,06|07")
        if '|' in balls_part:
            ball_parts = balls_part.split('|', 1)
            red_str = ball_parts[0].strip()
            blue_str = ball_parts[1].strip()
        else:
            errors.append(f'格式错误，缺少 | 分隔符: {line}')
            continue
        
        try:
            red_list = format_lottery_numbers(red_str)
            blue_list = format_lottery_numbers(blue_str)
            
            normalized_red = ','.join(map(str, red_list))
            normalized_blue = ','.join(map(str, blue_list))
            bet_count, cost = calculate_auto_cost(len(red_list), len(blue_list), lottery_type)
            
            record = PurchasedNumbers(
                user_id=current_user.id,
                lottery_type=lottery_type,
                issue=issue,
                red_balls=normalized_red,
                blue_balls=normalized_blue,
                bet_count=bet_count,
                cost=cost,
                source='clipboard',
            )
            db.session.add(record)
            
            # 自动对奖
            model_class = SSQDraw if lottery_type == 'ssq' else DLTDraw
            matches = auto_check_prizes(record, model_class)
            
            results.append({
                'red_balls': normalized_red,
                'blue_balls': normalized_blue,
                'issue': issue,
                'match_count': len(matches),
                'winning_amount': record.total_winning_amount,
            })
            
        except Exception as e:
            errors.append(f'解析失败: {line} - {str(e)}')
    
    db.session.commit()
    
    return jsonify({
        'message': f'成功导入 {len(results)} 条记录',
        'success_count': len(results),
        'error_count': len(errors),
        'results': results,
        'errors': errors,
    })


@bp.route('/api/purchased/import_favorite/<int:fav_id>', methods=['POST'])
@login_required
def api_import_from_favorite(fav_id):
    """从心仪号码导入到购买记录"""
    from models import FavoriteNumbers
    
    favorite = FavoriteNumbers.query.filter_by(id=fav_id, user_id=current_user.id).first()
    if not favorite:
        return jsonify({'error': '未找到该心仪号码'}), 404
    
    data = request.get_json() or {}
    issue = data.get('issue', '')
    note = data.get('note', favorite.note)
    
    red_list = [int(x) for x in favorite.red_balls.split(',')]
    blue_list = [int(x) for x in favorite.blue_balls.split(',')]
    bet_count, cost = calculate_auto_cost(len(red_list), len(blue_list), favorite.lottery_type)
    
    record = PurchasedNumbers(
        user_id=current_user.id,
        lottery_type=favorite.lottery_type,
        issue=issue,
        red_balls=favorite.red_balls,
        blue_balls=favorite.blue_balls,
        bet_count=bet_count,
        cost=cost,
        source='favorite_import',
        note=note or f'来自心仪号码',
    )
    
    db.session.add(record)
    db.session.commit()
    
    # 自动对奖
    model_class = SSQDraw if record.lottery_type == 'ssq' else DLTDraw
    matches = auto_check_prizes(record, model_class)
    db.session.commit()
    
    return jsonify({
        'message': '已从心仪号码导入到购买记录',
        'record': record.to_dict(),
        'matches': matches,
    })


@bp.route('/api/purchased/<int:record_id>', methods=['PUT'])
@login_required
def api_update_purchased(record_id):
    """更新购买记录"""
    record = PurchasedNumbers.query.filter_by(id=record_id, user_id=current_user.id).first()
    if not record:
        return jsonify({'error': '未找到该记录'}), 404
    
    data = request.get_json()
    
    if 'note' in data:
        record.note = data['note']
    if 'issue' in data:
        record.issue = data['issue']
    if 'is_active' in data:
        record.is_active = data['is_active']
    
    db.session.commit()
    return jsonify({'message': '更新成功', 'record': record.to_dict()})


@bp.route('/api/purchased/<int:record_id>', methods=['DELETE'])
@login_required
def api_delete_purchased(record_id):
    """删除购买记录"""
    record = PurchasedNumbers.query.filter_by(id=record_id, user_id=current_user.id).first()
    if not record:
        return jsonify({'error': '未找到该记录'}), 404
    
    db.session.delete(record)
    db.session.commit()
    return jsonify({'message': '已删除'})


@bp.route('/api/purchased/recheck', methods=['POST'])
@login_required
def api_recheck_all():
    """重新对奖所有活跃号码"""
    lottery_type = request.args.get('lottery_type')
    
    query = PurchasedNumbers.query.filter_by(
        user_id=current_user.id,
        is_active=True
    )
    
    if lottery_type and lottery_type in ('ssq', 'dlt'):
        query = query.filter_by(lottery_type=lottery_type)
    
    records = query.all()
    total_matches = 0
    
    for record in records:
        model_class = SSQDraw if record.lottery_type == 'ssq' else DLTDraw
        matches = auto_check_prizes(record, model_class)
        total_matches += len(matches)
    
    db.session.commit()
    
    return jsonify({
        'message': f'已重新对奖 {len(records)} 条记录，发现 {total_matches} 条中奖',
        'checked_count': len(records),
        'match_count': total_matches,
    })


@bp.route('/api/purchased/stats', methods=['GET'])
@login_required
def api_purchased_stats():
    """获取购买记录的统计数据"""
    lottery_type = request.args.get('lottery_type')
    
    query = PurchasedNumbers.query.filter_by(user_id=current_user.id)
    if lottery_type and lottery_type in ('ssq', 'dlt'):
        query = query.filter_by(lottery_type=lottery_type)
    
    records = query.all()
    
    total_investment = sum(r.cost * max(r.total_checked_periods, 1) for r in records)
    total_winnings = sum(r.total_winning_amount for r in records)
    active_count = sum(1 for r in records if r.is_active)
    
    overall_roi = 0.0
    if total_investment > 0:
        overall_roi = (total_winnings / total_investment) * 100
    
    # 按彩种统计
    type_stats = {}
    for lt in ['ssq', 'dlt']:
        lt_records = [r for r in records if r.lottery_type == lt]
        if lt_records:
            lt_invest = sum(r.cost * max(r.total_checked_periods, 1) for r in lt_records)
            lt_win = sum(r.total_winning_amount for r in lt_records)
            lt_roi = (lt_win / lt_invest * 100) if lt_invest > 0 else 0
            type_stats[lt] = {
                'count': len(lt_records),
                'active_count': sum(1 for r in lt_records if r.is_active),
                'total_investment': lt_invest,
                'total_winnings': lt_win,
                'roi': round(lt_roi, 2),
            }
    
    # 按月份统计（用于图表）
    from collections import defaultdict
    monthly_stats = defaultdict(lambda: {'investment': 0, 'winnings': 0})
    
    for r in records:
        month_key = r.purchase_date.strftime('%Y-%m')
        monthly_stats[month_key]['investment'] += r.cost * max(r.total_checked_periods, 1)
        monthly_stats[month_key]['winnings'] += r.total_winning_amount
    
    monthly_data = [
        {
            'month': month,
            'investment': round(data['investment'], 2),
            'winnings': round(data['winnings'], 2),
            'profit': round(data['winnings'] - data['investment'], 2),
        }
        for month, data in sorted(monthly_stats.items())
    ]
    
    # ROI排行榜（按ROI降序）
    roi_rankings = sorted(
        [
            {
                'id': r.id,
                'red_balls': r.red_balls,
                'blue_balls': r.blue_balls,
                'lottery_type': r.lottery_type,
                'total_investment': round(r.cost * max(r.total_checked_periods, 1), 2),
                'total_winnings': round(r.total_winning_amount, 2),
                'roi': round(r.roi, 2),
                'is_active': r.is_active,
            }
            for r in records
        ],
        key=lambda x: x['roi'],
        reverse=True
    )
    
    return jsonify({
        'total_records': len(records),
        'active_count': active_count,
        'total_investment': round(total_investment, 2),
        'total_winnings': round(total_winnings, 2),
        'net_profit': round(total_winnings - total_investment, 2),
        'overall_roi': round(overall_roi, 2),
        'type_stats': type_stats,
        'monthly_data': monthly_data,
        'roi_rankings': roi_rankings[:50],  # 前50名
    })
```

### 3. 购买记录管理页面

**templates/user/purchased.html** 主要内容：
- **添加记录区域**：
  - 手动输入表单（彩种、期号、红球、蓝球、备注）
  - 剪贴板批量导入区域（textarea + 格式说明 + 导入按钮）
  - "从心仪号码导入"按钮（弹出选择心仪号码的模态框）
- **记录列表**：
  - 分彩种 Tab（全部/SSQ/DLT）
  - 筛选：活跃/全部
  - 表格/卡片显示：号码球、期号、注数、花费、中奖金额、ROI、状态
  - 操作：编辑备注、切换守号、删除
- **导入格式说明**（可折叠）：
  ```
  支持以下格式：
  格式1: 01,02,03,04,05,06|07
  格式2: 每行一个号码
  格式3: 2026050:01,02,03,04,05,06|07
  ```

### 4. ROI 统计页面

**templates/user/roi_stats.html** 主要内容：
- **总览卡片**（4个）：
  - 总投入金额
  - 总中奖金额
  - 净收益（红色/绿色）
  - 总回报率 ROI%
- **按彩种统计**表格：SSQ / DLT 分别的投入、中奖、ROI
- **月度趋势图表**（使用 Chart.js）：
  - 柱状图：每月投入 vs 中奖
  - 折线图：累计 ROI 趋势
- **ROI 排行榜**：按回报率降序排列的所有号码组合
  - 显示号码、投入、中奖、ROI%、状态

### 5. 前端 JavaScript 补充

在 **static/js/user.js** 中追加购买记录相关逻辑：

```javascript
// ===== 购买记录功能 =====

// 剪贴板导入
function parseClipboardText(text) {
    const lines = text.trim().split('\n');
    const results = [];
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        
        let issue = '';
        let ballsPart = trimmed;
        
        if (trimmed.includes(':')) {
            const parts = trimmed.split(':', 1);
            issue = parts[0].trim();
            ballsPart = trimmed.substring(trimmed.indexOf(':') + 1).trim();
        }
        
        if (ballsPart.includes('|')) {
            const ballParts = ballsPart.split('|');
            results.push({
                issue: issue,
                red_balls: ballParts[0].trim(),
                blue_balls: ballParts[1].trim(),
            });
        }
    }
    return results;
}

// 批量导入
$('#btn-import-clipboard').click(function() {
    const text = $('#clipboard-text').val();
    const lotteryType = $('#import-lottery-type').val();
    
    if (!text.trim()) {
        alert('请先粘贴号码内容');
        return;
    }
    
    $.ajax({
        url: '/user/api/purchased/batch_add',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            text: text,
            lottery_type: lotteryType,
        }),
        success: function(resp) {
            const msg = resp.message + 
                (resp.error_count > 0 ? `，${resp.error_count} 条失败` : '');
            showToast(msg, resp.error_count > 0 ? 'warning' : 'success');
            
            if (resp.errors && resp.errors.length > 0) {
                $('#import-errors').html(resp.errors.join('<br>')).show();
            }
            
            // 刷新列表
            loadPurchasedRecords();
            $('#clipboard-text').val('');
        },
        error: function(xhr) {
            showToast('导入失败: ' + (xhr.responseJSON?.error || '未知错误'), 'danger');
        }
    });
});

// 加载购买记录列表
function loadPurchasedRecords() {
    // 实现列表加载逻辑
}

// 初始化 ROI 图表
function initRoiChart(monthlyData) {
    // 使用 Chart.js 渲染图表
}

// 导出为文本
function exportPurchased() {
    // 导出购买记录为文本格式
}
```

### 6. 补充需要导入的模块

确保在 user_routes.py 顶部有正确的导入：
```python
from models import db, User, FavoriteNumbers, PurchasedNumbers, SSQDraw, DLTDraw
from datetime import datetime
```

## 测试清单

- [ ] 手动添加单条购买记录，自动计算注数和花费
- [ ] 添加后自动对奖，正确显示中奖结果
- [ ] 剪贴板批量导入多种格式的号码
- [ ] 从心仪号码导入到购买记录
- [ ] 编辑记录的备注和状态
- [ ] 删除购买记录
- [ ] 重新对奖所有活跃号码
- [ ] ROI统计页面显示正确的总投入/中奖/ROI
- [ ] 月度趋势图表正确渲染
- [ ] ROI排行榜按回报率排序
- [ ] 不同用户的购买记录相互隔离
