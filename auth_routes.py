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

# ===== AI 配置 API =====

@bp.route('/api/ai_config', methods=['GET'])
@login_required
def api_get_ai_config():
    """获取当前用户的 AI 接口配置（屏蔽 API Key 敏感信息）"""
    config = current_user.ai_api_config or {}
    # 返回配置时屏蔽 API Key 中间部分
    safe_config = dict(config)
    if 'api_key' in safe_config and safe_config['api_key']:
        key = safe_config['api_key']
        if len(key) > 8:
            safe_config['api_key'] = key[:4] + '****' + key[-4:]
        elif len(key) > 4:
            safe_config['api_key'] = key[:2] + '****'
    return jsonify(safe_config)

@bp.route('/api/ai_config', methods=['POST'])
@login_required
def api_save_ai_config():
    """保存当前用户的 AI 接口配置"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效的请求数据'}), 400
    
    # 验证配置
    provider = data.get('provider', '').strip()
    if provider and provider not in ['openai', 'gemini', 'baidu', 'custom']:
        return jsonify({'error': '无效的接口提供商'}), 400
    
    # 如果新的 api_key 被屏蔽了（****），保留旧值
    if 'api_key' in data:
        new_key = data['api_key']
        if '****' in new_key:
            old_config = current_user.ai_api_config or {}
            data['api_key'] = old_config.get('api_key', new_key)
    
    current_user.ai_api_config = {
        'provider': data.get('provider', 'openai'),
        'api_key': data.get('api_key', ''),
        'api_url': data.get('api_url', ''),
        'model': data.get('model', 'gpt-4o'),
    }
    db.session.commit()
    return jsonify({'message': 'AI 接口配置保存成功'}), 200


# ===== 图片识别 API =====

@bp.route('/api/ai_recognize_ticket', methods=['POST'])
@login_required
def api_ai_recognize_ticket():
    """上传彩票图片，调用 AI 接口识别号码
    支持 test_mode=1 参数进行纯文本测试连接（无需上传真实图片）"""
    is_test = request.args.get('test_mode') == '1'
    
    if not is_test:
        if 'image' not in request.files:
            return jsonify({'error': '请上传图片文件'}), 400
        
        file = request.files['image']
        if not file.filename:
            return jsonify({'error': '请选择图片文件'}), 400
        
        # 检查文件大小（限制 10MB）
        file.seek(0, 2)  # 移到文件末尾
        file_size = file.tell()
        file.seek(0)  # 回到文件开头
        if file_size > 10 * 1024 * 1024:
            return jsonify({'error': '图片大小不能超过 10MB'}), 400
        
        # 检查文件类型
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in allowed_extensions:
            return jsonify({'error': '不支持的图片格式，请上传 PNG、JPG、GIF、BMP 或 WebP 格式'}), 400
    else:
        # 测试模式：创建一个空的文本文件对象
        import io
        file = io.BytesIO(b'test')
        file.filename = 'test.txt'
        ext = 'txt'
    
    # 获取用户 AI 配置
    ai_config = current_user.ai_api_config or {}
    provider = ai_config.get('provider', 'openai')
    api_key = ai_config.get('api_key', '')
    api_url = ai_config.get('api_url', '')
    model = ai_config.get('model', 'gpt-4o')
    
    if not api_key:
        return jsonify({'error': '请先在个人中心配置 AI 接口信息'}), 400
    
    # 读取图片内容并转为 Base64
    import base64
    img_data = base64.b64encode(file.read()).decode('utf-8')
    mime_type = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
    data_url = f'data:{mime_type};base64,{img_data}'
    
    try:
        if provider == 'openai' or provider == 'custom':
            result = _call_openai_api(api_key, api_url, model, data_url, is_test)
        elif provider == 'gemini':
            result = _call_gemini_api(api_key, api_url, model, data_url, is_test)
        elif provider == 'baidu':
            result = _call_baidu_api(api_key, api_url, data_url, is_test)
        else:
            return jsonify({'error': '不支持的接口提供商'}), 400
        
        # 如果是测试模式，只验证连接成功即可
        if is_test:
            return jsonify({'success': True, 'message': 'API 连接测试成功！'})
        
        # 验证识别结果 - 支持多注格式
        if not result:
            return jsonify({'error': 'AI 识别结果为空'}), 500
        
        tickets = result.get('tickets', [])
        lottery_type = result.get('lottery_type', 'ssq')
        
        # 如果没有 tickets 数组，尝试旧的单注格式
        if not tickets and 'red_balls' in result and 'blue_balls' in result:
            reds = result.get('red_balls', [])
            blues = result.get('blue_balls', [])
            reds = [int(b) for b in reds if str(b).isdigit()]
            blues = [int(b) for b in blues if str(b).isdigit()]
            tickets = [{'red_balls': reds, 'blue_balls': blues, 'multiplier': 1}]
        
        if not tickets:
            return jsonify({'error': 'AI 识别结果格式不正确，未能提取号码'}), 500
        
        # 验证每注号码
        validated_tickets = []
        for i, ticket in enumerate(tickets):
            reds = ticket.get('red_balls', [])
            blues = ticket.get('blue_balls', [])
            multi = int(ticket.get('multiplier', 1))
            is_additional = ticket.get('is_additional', False)
            
            reds = [int(b) for b in reds if str(b).isdigit()]
            blues = [int(b) for b in blues if str(b).isdigit()]
            
            if not reds or not blues:
                continue  # 跳过无效的注
            
            # 根据彩票类型验证号码范围和追加
            if lottery_type == 'ssq':
                if not all(1 <= b <= 33 for b in reds) or not all(1 <= b <= 16 for b in blues):
                    continue
                is_additional = False  # 双色球没有追加
            else:
                if not all(1 <= b <= 35 for b in reds) or not all(1 <= b <= 12 for b in blues):
                    continue
            
            validated_tickets.append({
                'red_balls': sorted(set(reds)),
                'blue_balls': sorted(set(blues)),
                'multiplier': max(1, multi),
                'is_additional': is_additional,
            })
        
        if not validated_tickets:
            return jsonify({'error': '未能从图片中识别出有效的彩票号码'}), 400
        
        # 计算总倍数和总费用（追加按3元/注，普通2元/注）
        total_multiplier = sum(t['multiplier'] for t in validated_tickets)
        total_cost = sum(t['multiplier'] * (3 if t.get('is_additional') else 2) for t in validated_tickets)
        
        # 从识别结果中提取期号
        ai_issue = result.get('issue', '')
        
        return jsonify({
            'success': True,
            'tickets': validated_tickets,
            'lottery_type': lottery_type,
            'issue': ai_issue,
            'total_multiplier': total_multiplier,
            'total_cost': total_cost,
        })
    
    except Exception as e:
        return jsonify({'error': f'AI 识别失败: {str(e)}'}), 500


def _call_openai_api(api_key, api_url, model, data_url, is_test=False):
    """调用 OpenAI 兼容接口进行图片识别
    支持标准 OpenAI 接口、gemini-balance 等轮询代理、以及各类 OpenAI 兼容网关。
    自动尝试多种认证方式以兼容不同代理实现。"""
    import requests
    import json
    import re
    
    url = api_url or 'https://api.openai.com/v1/chat/completions'
    
    effective_model = model or 'gpt-4o'
    
    if is_test:
        # 测试模式：只发文字请求验证 API Key
        payload = {
            'model': effective_model,
            'messages': [
                {'role': 'user', 'content': '请回复"连接测试成功"这几个字'}
            ],
            'temperature': 0.1,
            'max_tokens': 50,
        }
    else:
        prompt = """你是一个彩票号码识别专家。请仔细分析这张图片中的彩票号码，严格按照以下 JSON 格式返回结果：

{
    "lottery_type": "ssq 或 dlt",
    "issue": "期号字符串，如 2026050",
    "tickets": [
        {"red_balls": [红球号码数组], "blue_balls": [蓝球号码数组], "multiplier": 倍数数字},
        {"red_balls": [红球号码数组], "blue_balls": [蓝球号码数组], "multiplier": 倍数数字}
    ]
}

判断规则：
- 双色球（SSQ）：红球6个（范围1-33），蓝球1个（范围1-16）
- 大乐透（DLT）：前区5个（范围1-35），后区2个（范围1-12）
- 识别彩票期号（如 2026050），放入 issue 字段
- 仔细查看图片中所有号码，识别每一注号码（彩票可能有多个号码组合）
- 识别每注号码的倍数（如2倍、3倍等），如果看不清倍数默认为1
- 识别彩票总费用（金额），放入 total_cost 字段
- 只返回 JSON，不要包含其他文字说明"""
        
        payload = {
            'model': effective_model,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': prompt},
                        {'type': 'image_url', 'image_url': {'url': data_url}}
                    ]
                }
            ],
            'temperature': 0.1,
            'max_tokens': 500,
        }
    
    # ===== 先检查 URL 路径：如果 URL 不含 /chat/completions，自动尝试常见路径 =====
    
    errors = []
    urls_to_try = [url]  # 先试原始 URL
    
    # 如果原始 URL 不含 /chat/completions 或 /generateContent，加常见路径
    if '/chat/completions' not in url and '/generateContent' not in url:
        base = url.rstrip('/')
        urls_to_try = [
            url,                              # 原始地址
            f'{base}/chat/completions',       # 常见路径
            f'{base}/v1/chat/completions',    # OpenAI 标准路径
            f'{base}/v1beta/chat/completions', # Gemini 兼容路径
        ]
        # 去重
        urls_to_try = list(dict.fromkeys(urls_to_try))
    
    # ===== 遍历所有 URL，对每个 URL 尝试所有认证方式 =====
    
    auth_methods = [
        ('方式1(Bearer)', {'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'}),
        ('方式2(x-goog-api-key)', {'x-goog-api-key': api_key, 'Content-Type': 'application/json'}),
        ('方式4(直接Auth)', {'Authorization': api_key, 'Content-Type': 'application/json'}),
    ]
    
    for try_url in urls_to_try:
        for method_name, headers in auth_methods:
            try:
                response = requests.post(try_url, headers=headers, json=payload, timeout=30)
                if response.status_code == 200:
                    if is_test:
                        return {'success': True}
                    return _parse_openai_response(response)
                errors.append(f'{method_name} @ {try_url} -> HTTP {response.status_code}')
            except Exception as e:
                errors.append(f'{method_name} @ {try_url} -> {str(e)[:50]}')
        
        # 特殊：方式3 (?key=) 需要修改 URL
        try:
            connector = '&' if '?' in try_url else '?'
            url_with_key = f'{try_url}{connector}key={api_key}'
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url_with_key, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                if is_test:
                    return {'success': True}
                return _parse_openai_response(response)
            errors.append(f'方式3(?key=) @ {try_url} -> HTTP {response.status_code}')
        except Exception as e:
            errors.append(f'方式3(?key=) @ {try_url} -> {str(e)[:50]}')
    
    # 所有方式都失败
    error_detail = ' | '.join(errors)
    
    # 分析错误模式，给出针对性建议
    suggestions = []
    error_types = set()
    for e in errors:
        if 'HTTP 405' in e:
            error_types.add('405')
        elif 'HTTP 401' in e:
            error_types.add('401')
        elif 'HTTP 404' in e:
            error_types.add('404')
    
    if '401' in error_types:
        suggestions.append('🔑 API Key 可能不正确，请检查')
    if '404' in error_types:
        suggestions.append('🌐 API URL 路径可能不正确，已自动尝试了 /v1/chat/completions 等常见路径仍未成功')
    if '405' in error_types:
        suggestions.append('🌐 API URL 可能只是根地址（如 http://127.0.0.1:8787），已自动尝试了 /v1/chat/completions 等常见路径，请检查代理的完整地址')
    if 'Connection' in str(errors) or 'timeout' in str(errors):
        suggestions.append('🔌 无法连接到服务器，请检查网络/代理设置')
    
    suggestion_text = '\n'.join(suggestions) if suggestions else '💡 建议：在 API URL 字段填写完整的接口地址，包括路径部分'
    
    raise Exception(f'AI 接口调用失败（已尝试 {len(urls_to_try)} 个URL路径 × 多种认证方式）:\n{error_detail}\n\n{suggestion_text}')


def _parse_openai_response(response):
    """解析 OpenAI 兼容接口的返回结果"""
    import json
    import re
    
    result = response.json()
    
    # 检查是否有 choices 字段（标准 OpenAI 格式）
    if 'choices' in result and len(result['choices']) > 0:
        content = result['choices'][0]['message']['content']
        
        # 尝试从返回内容中提取 JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json ... ``` 块
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试提取 {...} 对象
        obj_match = re.search(r'\{[\s\S]*\}', content)
        if obj_match:
            try:
                return json.loads(obj_match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise Exception(f'无法解析 AI 返回结果: {content[:200]}')
    
    # 检查是否有 candidates 字段（Gemini 原生格式转发的响应）
    if 'candidates' in result:
        try:
            content = result['candidates'][0]['content']['parts'][0]['text']
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
            obj_match = re.search(r'\{[\s\S]*\}', content)
            if obj_match:
                try:
                    return json.loads(obj_match.group(0))
                except json.JSONDecodeError:
                    pass
            raise Exception(f'无法解析 AI 返回结果: {content[:200]}')
        except (KeyError, IndexError):
            pass
    
    raise Exception(f'无法识别的 AI 返回格式: {json.dumps(result, ensure_ascii=False)[:200]}')


def _repair_truncated_json(text):
    """尝试修复被截断的 JSON 字符串"""
    import json
    # 移除 ```json ... ``` 标记
    import re
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()
    
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 尝试提取最外层的 {...} 对象
    brace_depth = 0
    bracket_depth = 0
    start = -1
    end = -1
    
    for i, ch in enumerate(text):
        if ch == '{':
            if start == -1:
                start = i
            brace_depth += 1
        elif ch == '}':
            brace_depth -= 1
            if brace_depth == 0 and start >= 0:
                end = i + 1
                break
        elif ch == '[':
            bracket_depth += 1
        elif ch == ']':
            bracket_depth -= 1
    
    if start >= 0 and end > start:
        candidate = text[start:end]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    
    # 如果 JSON 不完整，尝试补全
    # 找到最外层 { 和 } 的平衡
    if start >= 0:
        # 从 start 开始提取，并补全缺失的 }
        partial = text[start:]
        # 计算未闭合的 { 数量
        open_braces = 0
        for ch in partial:
            if ch == '{': open_braces += 1
            elif ch == '}': open_braces -= 1
        # 补全缺失的 }
        if open_braces > 0:
            partial += '}' * open_braces
        
        # 补全缺失的 ]
        open_brackets = 0
        for ch in partial:
            if ch == '[': open_brackets += 1
            elif ch == ']': open_brackets -= 1
        if open_brackets > 0:
            partial += ']' * open_brackets
        
        # 补全末尾的引号
        # 检查最后是否为不完整的字符串
        in_string = False
        escape = False
        for ch in partial:
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
        if in_string:
            partial += '"'
        
        try:
            return json.loads(partial)
        except json.JSONDecodeError:
            pass
    
    return None


def _call_gemini_api(api_key, api_url, model, data_url, is_test=False):
    """调用 Gemini（Google）API 进行图片识别"""
    import requests
    import json
    import re
    
    # Gemini API 原生端点
    if api_url:
        url = api_url
    else:
        # 官方 Gemini API 需要 API Key 在 URL 中
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model or "gemini-2.0-flash-exp"}:generateContent?key={api_key}'
    
    if is_test:
        # 测试模式：只发文字请求验证 API Key
        payload = {
            'contents': [
                {
                    'parts': [
                        {'text': '请回复"连接测试成功"这几个字'}
                    ]
                }
            ],
            'generationConfig': {
                'temperature': 0.1,
                'maxOutputTokens': 50,
            }
        }
    else:
        # 从 data_url 提取纯 base64 和 mime type
        if ',' in data_url:
            mime_type = data_url.split(';')[0].split(':')[1]
            img_b64 = data_url.split(',', 1)[1]
        else:
            mime_type = 'image/png'
            img_b64 = data_url
        
        prompt = """你是一个彩票号码识别专家。请仔细分析这张图片中的彩票号码，严格按照以下 JSON 格式返回结果（只返回 JSON，不要包含其他文字说明）：

{
    "lottery_type": "ssq 或 dlt",
    "issue": "期号字符串，如 2026050",
    "tickets": [
        {"red_balls": [红球号码数组], "blue_balls": [蓝球号码数组], "multiplier": 倍数数字, "is_additional": true或false},
        {"red_balls": [红球号码数组], "blue_balls": [蓝球号码数组], "multiplier": 倍数数字, "is_additional": true或false}
    ]
}

判断规则：
- 双色球（SSQ）：红球6个（范围1-33），蓝球1个（范围1-16）。双色球没有追加投注，is_additional 始终为 false
- 大乐透（DLT）：前区5个（范围1-35），后区2个（范围1-12）。大乐透可能有追加投注，请识别彩票上是否有"追加"字样
- 识别彩票期号（如 2026050），放入 issue 字段
- 仔细查看图片中所有号码，识别每一注号码（彩票可能有多个号码组合）
- 识别每注号码的倍数（如2倍、3倍等），如果看不清倍数默认为1
- 识别每注是否为追加投注（大乐透才有），如果图片上有"追加"字样则 is_additional 为 true，没有则为 false
- 识别彩票总费用（金额），放入 total_cost 字段"""
        
        payload = {
            'contents': [
                {
                    'parts': [
                        {'text': prompt},
                        {
                            'inline_data': {
                                'mime_type': mime_type,
                                'data': img_b64
                            }
                        }
                    ]
                }
            ],
            'generationConfig': {
                'temperature': 0.1,
                'maxOutputTokens': 8192,
            }
        }
    
    # 请求头：官方 API 不需要额外 headers（key 在 URL 中），转接接口需要 Bearer token
    headers = {'Content-Type': 'application/json'}
    if api_url:
        headers['Authorization'] = f'Bearer {api_key}'
    
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    
    if response.status_code != 200:
        # 对于官方 API，key 已在 URL 中，不需要重试
        if not api_url:
            raise Exception(f'AI 接口调用失败 (HTTP {response.status_code}): {response.text}')
        
        # 对于转接接口，尝试把 key 放到 URL 参数重试
        if '?' in url:
            retry_url = url + '&key=' + api_key
        else:
            retry_url = url + '?key=' + api_key
        
        headers2 = {'Content-Type': 'application/json'}
        response = requests.post(retry_url, headers=headers2, json=payload, timeout=60)
        
        if response.status_code != 200:
            raise Exception(f'AI 接口调用失败 (HTTP {response.status_code}): {response.text}')
    
    if is_test:
        return {'success': True}
    
    result = response.json()
    
    # Gemini 响应格式：candidates[0].content.parts[0].text
    try:
        content = result['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError):
        raise Exception(f'无法解析 Gemini 返回结果: {json.dumps(result, ensure_ascii=False)[:200]}')
    
    # 尝试从返回内容中提取 JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # 尝试提取 ```json ... ``` 块
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 尝试提取 {...} 对象
    obj_match = re.search(r'\{[\s\S]*\}', content)
    if obj_match:
        try:
            return json.loads(obj_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # 尝试修复被截断的 JSON
    try:
        repaired = _repair_truncated_json(content)
        if repaired:
            return repaired
    except Exception:
        pass
    
    raise Exception(f'无法解析 Gemini 返回结果: {content[:200]}')


def _call_baidu_api(api_key, api_url, data_url, is_test=False):
    """调用百度 OCR API 进行文字识别，然后提取号码"""
    import requests
    import base64
    import json
    import re
    
    # 从 data_url 中提取纯 base64
    img_b64 = data_url.split(',', 1)[1] if ',' in data_url else data_url
    
    # 百度 OCR API
    ocr_url = api_url or 'https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic'
    
    # 获取 access_token
    token_url = 'https://aip.baidubce.com/oauth/2.0/token'
    token_data = {
        'grant_type': 'client_credentials',
        'client_id': api_key,  # API Key
        'client_secret': api_url,  # Secret Key（百度需要两个key，这里用api_url字段存Secret Key）
    }
    
    token_resp = requests.post(token_url, data=token_data, timeout=10)
    if token_resp.status_code != 200:
        raise Exception(f'百度 API 认证失败: {token_resp.text}')
    
    access_token = token_resp.json().get('access_token')
    if not access_token:
        raise Exception('获取百度 access_token 失败')
    
    if is_test:
        # 测试模式：能获取到 access_token 就算成功
        return {'success': True}
    
    # 调用 OCR
    ocr_resp = requests.post(
        f'{ocr_url}?access_token={access_token}',
        data={'image': img_b64},
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=30
    )
    
    if ocr_resp.status_code != 200:
        raise Exception(f'百度 OCR 调用失败: {ocr_resp.text}')
    
    ocr_result = ocr_resp.json()
    words_result = ocr_result.get('words_result', [])
    
    # 提取所有文字
    all_text = ' '.join([item['words'] for item in words_result])
    
    # 从文字中提取号码
    numbers = re.findall(r'(\d{1,2})', all_text)
    numbers = [int(n) for n in numbers if 1 <= int(n) <= 35]
    numbers = list(set(numbers))
    
    if len(numbers) < 6:
        raise Exception(f'未能从图片中识别出足够多的号码（仅识别到 {len(numbers)} 个有效号码）')
    
    # 自动判断并分配红蓝球
    numbers.sort()
    if len(numbers) >= 8:
        red_balls = numbers[:6]
        blue_balls = numbers[6:8]
        lottery_type = 'dlt' if len(blue_balls) >= 2 else 'ssq'
    elif len(numbers) >= 7:
        red_balls = numbers[:6]
        blue_balls = numbers[6:7]
        lottery_type = 'ssq'
    else:
        red_balls = numbers[:5]
        blue_balls = numbers[5:7]
        lottery_type = 'dlt'
    
    return {
        'red_balls': red_balls,
        'blue_balls': blue_balls,
        'lottery_type': lottery_type,
    }


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

@bp.route('/manual-entry')
@login_required
def manual_entry():
    """手工添加号码页面"""
    return render_template('user/manual_entry.html')


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
    
    # 计算统计信息（基于全部数据）- cost已包含倍数，直接求和
    total_cost = sum(t.cost for t in all_tickets)
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
    is_additional = data.get('is_additional', False)
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
    
    # 双色球不能追加
    if lottery_type == 'ssq':
        is_additional = False
    
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
        is_additional=is_additional,
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
    """更新已购号码记录（期号、倍数、金额）- 更新后重新对奖"""
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
    
    if 'multiplier' in data:
        multiplier = int(data['multiplier'])
        if multiplier < 1:
            return jsonify({'error': '倍数至少为1'}), 400
        ticket.multiplier = multiplier
    
    if 'cost' in data:
        cost = float(data['cost'])
        if cost < 2:
            return jsonify({'error': '金额至少2元'}), 400
        ticket.cost = cost
    
    if 'is_additional' in data:
        is_additional = bool(data['is_additional'])
        # 双色球不能追加
        if ticket.lottery_type == 'ssq' and is_additional:
            return jsonify({'error': '双色球不支持追加投注'}), 400
        ticket.is_additional = is_additional
        # 当 is_additional 变更时，自动重新计算金额
        red_count = len(ticket.red_balls.split(',')) if ticket.red_balls else 0
        blue_count = len(ticket.blue_balls.split(',')) if ticket.blue_balls else 0
        # 计算复式注数
        from math import comb
        if ticket.lottery_type == 'ssq':
            units = comb(red_count, 6) * comb(blue_count, 1)
        else:
            units = comb(red_count, 5) * comb(blue_count, 2)
        unit_price = 3 if (ticket.lottery_type == 'dlt' and is_additional) else 2
        ticket.cost = units * unit_price * ticket.multiplier
    
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
