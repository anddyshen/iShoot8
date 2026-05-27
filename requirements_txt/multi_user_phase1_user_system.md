# iShoot 多用户模式 - Phase 1：用户系统基础设施

> 预估工时：2-3 天
> 前置依赖：无
> 当前阶段目标：实现用户注册/登录/退出、Flask-Login 集成、后台用户管理、注册开关

## 需要安装的依赖

在命令行执行：
```bash
pip install flask-login flask-mail
```

## 需要修改的文件

### 1. models.py - 新增 User 模型

在 models.py 文件末尾新增 User 模型：

```python
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    nickname = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)
    notification_config = db.Column(db.JSON, default=dict)
    preferences = db.Column(db.JSON, default=dict)
    
    # 关联
    favorites = db.relationship('FavoriteNumbers', backref='user', lazy='dynamic')
    purchased_numbers = db.relationship('PurchasedNumbers', backref='user', lazy='dynamic')
    notifications = db.relationship('NotificationLog', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'nickname': self.nickname,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
        }
    
    def __repr__(self):
        return f'<User {self.username}>'
```

### 2. app.py - 集成 Flask-Login

在 app.py 中进行以下修改：

**上方导入区域添加**：
```python
from flask_login import LoginManager, current_user
from models import User, db, SSQDraw, DLTDraw, News, AdminSettings, initialize_admin_route_prefix
```

**在 db.init_app(app) 之后添加 LoginManager 初始化**：
```python
# 初始化 Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_routes.login'
login_manager.login_message = '请先登录。'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
```

**在上下文处理器 inject_global_data 中注入 current_user**（确保 current_user 在所有模板中可用）：
```python
@app.context_processor
def inject_global_data():
    return {
        'site_name': SITE_NAME,
        'site_url': SITE_URL,
        'current_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'app_version': __version__,
        'per_bet_price': PER_BET_PRICE,
        'settings': CURRENT_SETTINGS,
        'format_lottery_numbers': format_lottery_numbers,
        'current_user': current_user,  # 注入 current_user
    }
```

**路由注册区域添加认证路由蓝图**：
```python
# 导入路由
import routes
import admin_routes
import auth_routes  # 新增

# 注册蓝图
app.register_blueprint(routes.bp)
app.register_blueprint(admin_routes.bp, url_prefix=f'/{ADMIN_ROUTE_PREFIX}')
app.register_blueprint(auth_routes.bp)  # 新增
```

**在数据库初始化区域，创建所有表**（db.create_all() 会自动创建新添加的 User 表）。

### 3. 新建 auth_routes.py - 认证路由

创建 auth_routes.py 文件，内容如下：

```python
# auth_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from models import db, User
from config import CURRENT_SETTINGS

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
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        
        login_user(user, remember=remember)
        
        # 重定向到登录前页面
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
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

@bp.route('/api/change_password', methods=['POST'])
@login_required
def api_change_password():
    """修改密码"""
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    if not current_user.check_password(old_password):
        return jsonify({'error': '当前密码错误'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': '新密码至少6个字符'}), 400
    
    current_user.set_password(new_password)
    db.session.commit()
    return jsonify({'message': '密码修改成功'})
```

### 4. config.py - 新增设置项

在 DEFAULT_SETTINGS 字典中添加以下键值对：

```python
# 用户系统设置
"allow_registration": False,  # 是否允许用户注册，默认关闭
```

在 GENERAL_SETTINGS_KEYS 列表中添加：
```python
'allow_registration',
```

在 SETTING_LABELS_CHINESE 字典中添加：
```python
'allow_registration': '允许用户注册',
```

### 5. admin_routes.py - 新增用户管理

在 admin_routes.py 中新增以下路由：

```python
@bp.route('/users')
@admin_required
def admin_users():
    """用户列表管理"""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/user_manage.html', users=users)

@bp.route('/users/<int:user_id>/toggle_active', methods=['POST'])
@admin_required
def admin_toggle_user_active(user_id):
    """启用/禁用用户"""
    user = db.session.get(User, user_id)
    if not user:
        flash('用户不存在。', 'danger')
        return redirect(url_for('admin_routes.admin_users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    status = '启用' if user.is_active else '禁用'
    flash(f'用户 {user.username} 已{status}。', 'success')
    return redirect(url_for('admin_routes.admin_users'))

@bp.route('/users/<int:user_id>/reset_password', methods=['POST'])
@admin_required
def admin_reset_user_password(user_id):
    """管理员重置用户密码"""
    user = db.session.get(User, user_id)
    if not user:
        flash('用户不存在。', 'danger')
        return redirect(url_for('admin_routes.admin_users'))
    
    new_password = request.form.get('new_password', '')
    if len(new_password) < 6:
        flash('密码至少6个字符。', 'danger')
        return redirect(url_for('admin_routes.admin_users'))
    
    user.set_password(new_password)
    db.session.commit()
    flash(f'用户 {user.username} 的密码已重置。', 'success')
    return redirect(url_for('admin_routes.admin_users'))
```

### 6. 新建模板文件

**templates/user/login.html** - 登录页面
- 简洁的登录表单（用户名、密码、记住我）
- 如果注册开启，显示"没有账号？去注册"链接
- 错误提示区域

**templates/user/register.html** - 注册页面
- 注册表单（用户名、密码、确认密码、邮箱（选填）、昵称（选填））
- 如果注册关闭，显示提示信息
- 错误提示区域

**templates/user/profile.html** - 个人中心
- 显示用户基本信息
- 编辑昵称、邮箱的表单
- 修改密码表单
- 链接到：心仪号码、购买记录、ROI统计、通知设置

**templates/admin/user_manage.html** - 后台用户管理
- 用户列表表格（用户名、邮箱、昵称、状态、注册时间、最后登录）
- 操作按钮：启用/禁用、重置密码
- 显示用户总数

### 7. 修改 base.html 导航栏

在导航栏（通常在 base.html 的 `<nav>` 或顶部区域）中：
- 未登录时显示"登录"和"注册"链接（注册链接受 allow_registration 控制）
- 已登录时显示用户名（或昵称）、"个人中心"、"退出"链接
- 使用 `{% if current_user.is_authenticated %}` 判断登录状态

示例代码片段（添加到导航栏合适位置）：
```html
<div class="navbar-nav ms-auto">
    {% if current_user.is_authenticated %}
        <li class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                👤 {{ current_user.nickname or current_user.username }}
            </a>
            <ul class="dropdown-menu dropdown-menu-end">
                <li><a class="dropdown-item" href="{{ url_for('user_routes.profile') }}">个人中心</a></li>
                <li><a class="dropdown-item" href="{{ url_for('user_routes.favorites') }}">❤️ 心仪号码</a></li>
                <li><a class="dropdown-item" href="{{ url_for('user_routes.purchased') }}">📋 购买记录</a></li>
                <li><a class="dropdown-item" href="{{ url_for('user_routes.notification_settings') }}">🔔 通知设置</a></li>
                {% if current_user.is_admin %}
                <li><hr class="dropdown-divider"></li>
                <li><a class="dropdown-item" href="{{ url_for('admin_routes.admin_dashboard') }}">⚙️ 后台管理</a></li>
                {% endif %}
                <li><hr class="dropdown-divider"></li>
                <li><a class="dropdown-item" href="{{ url_for('auth_routes.logout') }}">退出</a></li>
            </ul>
        </li>
    {% else %}
        <li class="nav-item">
            <a class="nav-link" href="{{ url_for('auth_routes.login') }}">登录</a>
        </li>
        {% if settings.allow_registration %}
        <li class="nav-item">
            <a class="nav-link" href="{{ url_for('auth_routes.register') }}">注册</a>
        </li>
        {% endif %}
    {% endif %}
</div>
```

### 8. 管理员初始化

在 app.py 的数据库初始化区域，添加管理员账号自动创建逻辑：

```python
with app.app_context():
    db.create_all()
    AdminSettings.initialize_default_settings()
    
    # 创建默认管理员（如果不存在）
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            nickname='管理员',
            is_active=True,
            is_admin=True
        )
        admin_user.set_password(CURRENT_SETTINGS.get('admin_password', 'admin123'))
        db.session.add(admin_user)
        db.session.commit()
        print('默认管理员账号已创建 (username: admin)')
    
    # ... 其余初始化代码
```

## 测试清单

- [ ] 访问 `/login` 显示登录页面
- [ ] 访问 `/register` 显示注册页面（默认注册关闭时仍可访问但提示）
- [ ] 使用管理员账号登录
- [ ] 注册新用户（后台开启注册开关后）
- [ ] 用户退出登录
- [ ] 未登录状态下访问需要登录的 API 被重定向
- [ ] 后台 `/admin/users` 显示用户列表
- [ ] 管理员可以禁用/启用用户
- [ ] 被禁用的用户无法登录
- [ ] 管理员可以重置用户密码
