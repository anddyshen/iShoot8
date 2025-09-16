# iShoot8 - 智能彩票数据分析与预测系统

✨ **版本:** 1.0.4

## 🚀 项目简介

`iShoot8` 是一个基于 Flask 框架开发的智能彩票数据分析与预测系统。它旨在为用户提供双色球 (SSQ) 和大乐透 (DLT) 的历史开奖数据查询、多维度统计分析、基于自定义规则的号码预测以及规则符合度检查功能。通过直观的图表和详细的数据展示，帮助用户更好地理解彩票趋势，辅助决策。
这项目是利用个人爱好练手，仅供大家批评和娱乐。

## ✨ 主要功能

*   **历史开奖数据查询：**
    *   按彩种（双色球/大乐透）切换查看历史开奖数据。
    *   支持按日期范围筛选开奖记录。
    *   支持自定义每页显示数量。
    *   显示每期开奖的红球、蓝球、销售额、奖池、一等奖信息、奇偶比、和值等。
*   **号码统计与可视化：**
    *   **统计范围筛选：** 可选择统计最近 N 期或所有历史数据。
    *   **红球/蓝球出现频率：** 统计每个号码在指定范围内的出现次数和频率百分比。
    *   **红球/蓝球遗漏期数：** 统计每个号码当前的遗漏期数和历史最大遗漏期数。
    *   **图表展示：** 使用 Chart.js 绘制柱状图，直观展示号码的出现频率和遗漏趋势。
    *   **详细表格：** 提供可折叠的详细表格，展示所有号码的精确统计数据，并对热号/冷号进行高亮显示。
*   **预测规则检查：**
    *   在历史开奖页面，可点击“检查规则”按钮，验证该期开奖号码是否符合预设的预测规则。
    *   弹窗显示该期号码符合和不符合的具体规则及说明。
*   **智能号码预测 (TODO)：**
    *   基于后台配置的预测规则，生成符合条件的预测号码组合。
    *   支持单式和复式投注的号码生成。
*   **后台管理系统：**
    *   **网站设置：** 管理员可在线配置网站名称、URL、投注价格、分页大小、以及所有预测规则的参数（包括新添加的蓝球出现频率规则等）。
    *   **数据更新：** 支持手动触发最新开奖数据更新，或手动添加单期开奖数据。
    *   **新闻管理：** 发布、编辑、删除新闻公告，控制是否在首页显示和是否公开。
    *   **设置备份与恢复：** 支持下载当前设置备份，或恢复为默认设置。
*   **定时任务：** 后台自动定时更新最新开奖数据。
*   **响应式设计：** 基于 Bootstrap 框架，适配不同设备屏幕。

## ⚙️ 技术栈

*   **后端：** Python, Flask, Flask-SQLAlchemy, APScheduler
*   **数据库：** SQLite (默认，可配置为其他关系型数据库)
*   **前端：** HTML5, CSS3 (Bootstrap 5), JavaScript (Chart.js)
*   **数据源：** 外部彩票数据接口 (通过 `data_manager.py` 实现)

## 📦 安装与运行

### 前提条件

*   Python 3.8+
*   pip (Python 包管理器)

### 步骤

1.  **克隆仓库：**
    ```bash
    git clone https://github.com/your-username/iShoot8.git
    cd iShoot8
    ```

2.  **创建并激活虚拟环境：**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **安装依赖：**
    ```bash
    pip install -r requirements.txt
    ```
    **`requirements.txt` 内容示例：**
    ```
    Flask==2.3.3
    Flask-SQLAlchemy==3.1.1
    APScheduler==3.10.4
    python-dotenv==1.0.0
    requests==2.31.0
    pytz==2023.3.post1
    Werkzeug==2.3.7 # 确保与Flask版本兼容
    ```

4.  **配置环境变量：**
    在项目根目录下创建 `.env` 文件，并添加以下内容：
    ```
    FLASK_SECRET_KEY="your_super_secret_key_here" # 替换为随机生成的强密钥
    ADMIN_PASSWORD="your_admin_password"          # 替换为您的管理员密码
    # SQLALCHEMY_DATABASE_URI="sqlite:///instance/lottery.db" # 默认使用SQLite，可根据需要修改
    ```
    *提示：您可以使用 `python -c 'import os; print(os.urandom(24).hex())'` 生成一个随机密钥。*

5.  **初始化数据库：**
    ```bash
    flask shell
    >>> from app import db
    >>> db.create_all()
    >>> exit()
    ```
    这将创建 `instance/lottery.db` 文件和所有必要的数据库表。

6.  **运行应用：**
    ```bash
    python app.py
    ```
    应用将在 `http://127.0.0.1:5000/` 运行。

## 🌐 使用指南

### 访问前端页面

打开浏览器访问 `http://127.0.0.1:5000/`。

*   **首页 (`/`)：** 显示最新开奖信息和新闻。
*   **历史开奖 (`/history`)：**
    *   选择彩种（双色球/大乐透）。
    *   使用日期范围和统计范围筛选数据。
    *   查看号码统计图表和详细表格。
    *   点击每期旁边的“检查规则”按钮，查看该期号码是否符合预测规则。
*   **号码预测 (`/prediction`)：** (TODO) 未来将在此页面生成预测号码。
*   **兑奖中心 (`/prize_check`)：** (TODO) 未来将在此页面进行号码兑奖和趣味游戏。
*   **新闻详情 (`/news/<id>`)：** 查看具体新闻内容。

### 访问后台管理

打开浏览器访问 `http://127.0.0.1:5000/admin` (或您在 `config.py` 中设置的 `ADMIN_ROUTE_PREFIX`)。

*   **登录：** 使用 `.env` 文件中配置的 `ADMIN_PASSWORD` 进行登录。
*   **仪表盘 (`/admin`)：** 后台管理首页。
*   **网站设置 (`/admin/settings`)：**
    *   修改网站基本信息。
    *   调整预测规则的各项参数，例如：
        *   `ssq_red_omit_1_weight` (双色球红球遗漏权重)
        *   `ssq_blue_recent_occurrence_draws` (双色球蓝球最新出现频率检查期数)
        *   `ssq_blue_recent_occurrence_threshold` (双色球蓝球出现次数阈值)
        *   `ssq_blue_recent_occurrence_weight` (双色球蓝球提升概率)
        *   以及对应的大乐透参数 `dlt_...`
        *   `history_stats_range_default` 和 `history_stats_range_options` (历史统计范围)
    *   下载设置备份或恢复默认设置。
*   **数据更新 (`/admin/data_update`)：**
    *   手动触发最新开奖数据抓取。
    *   手动添加单期开奖数据。
*   **新闻管理 (`/admin/news_manage`)：** 发布、编辑、删除新闻。

## 📁 项目结构
好的，恭喜您！这是一个重要的里程碑。现在，我将为您编写一份详细且专业的 README.md 文件，供您的 GitHub 项目使用。这份 README.md 将涵盖项目介绍、功能、安装、使用、配置、项目结构以及未来的扩展方向。

MARKDOWN
# iShoot8 - 智能彩票数据分析与预测系统

✨ **版本:** 1.0.4

## 🚀 项目简介

`iShoot8` 是一个基于 Flask 框架开发的智能彩票数据分析与预测系统。它旨在为用户提供双色球 (SSQ) 和大乐透 (DLT) 的历史开奖数据查询、多维度统计分析、基于自定义规则的号码预测以及规则符合度检查功能。通过直观的图表和详细的数据展示，帮助用户更好地理解彩票趋势，辅助决策。

## ✨ 主要功能

*   **历史开奖数据查询：**
    *   按彩种（双色球/大乐透）切换查看历史开奖数据。
    *   支持按日期范围筛选开奖记录。
    *   支持自定义每页显示数量。
    *   显示每期开奖的红球、蓝球、销售额、奖池、一等奖信息、奇偶比、和值等。
*   **号码统计与可视化：**
    *   **统计范围筛选：** 可选择统计最近 N 期或所有历史数据。
    *   **红球/蓝球出现频率：** 统计每个号码在指定范围内的出现次数和频率百分比。
    *   **红球/蓝球遗漏期数：** 统计每个号码当前的遗漏期数和历史最大遗漏期数。
    *   **图表展示：** 使用 Chart.js 绘制柱状图，直观展示号码的出现频率和遗漏趋势。
    *   **详细表格：** 提供可折叠的详细表格，展示所有号码的精确统计数据，并对热号/冷号进行高亮显示。
*   **预测规则检查：**
    *   在历史开奖页面，可点击“检查规则”按钮，验证该期开奖号码是否符合预设的预测规则。
    *   弹窗显示该期号码符合和不符合的具体规则及说明。
*   **智能号码预测 (TODO)：**
    *   基于后台配置的预测规则，生成符合条件的预测号码组合。
    *   支持单式和复式投注的号码生成。
*   **后台管理系统：**
    *   **网站设置：** 管理员可在线配置网站名称、URL、投注价格、分页大小、以及所有预测规则的参数（包括新添加的蓝球出现频率规则等）。
    *   **数据更新：** 支持手动触发最新开奖数据更新，或手动添加单期开奖数据。
    *   **新闻管理：** 发布、编辑、删除新闻公告，控制是否在首页显示和是否公开。
    *   **设置备份与恢复：** 支持下载当前设置备份，或恢复为默认设置。
*   **定时任务：** 后台自动定时更新最新开奖数据。
*   **响应式设计：** 基于 Bootstrap 框架，适配不同设备屏幕。

## ⚙️ 技术栈

*   **后端：** Python, Flask, Flask-SQLAlchemy, APScheduler
*   **数据库：** SQLite (默认，可配置为其他关系型数据库)
*   **前端：** HTML5, CSS3 (Bootstrap 5), JavaScript (Chart.js)
*   **数据源：** 外部彩票数据接口 (通过 `data_manager.py` 实现)

## 📦 安装与运行

### 前提条件

*   Python 3.8+
*   pip (Python 包管理器)

### 步骤

1.  **克隆仓库：**
    ```bash
    git clone https://github.com/your-username/iShoot8.git
    cd iShoot8
    ```

2.  **创建并激活虚拟环境：**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **安装依赖：**
    ```bash
    pip install -r requirements.txt
    ```
    **`requirements.txt` 内容示例：**
    ```
    Flask==2.3.3
    Flask-SQLAlchemy==3.1.1
    APScheduler==3.10.4
    python-dotenv==1.0.0
    requests==2.31.0
    pytz==2023.3.post1
    Werkzeug==2.3.7 # 确保与Flask版本兼容
    ```

4.  **配置环境变量：**
    在项目根目录下创建 `.env` 文件，并添加以下内容：
    ```
    FLASK_SECRET_KEY="your_super_secret_key_here" # 替换为随机生成的强密钥
    ADMIN_PASSWORD="your_admin_password"          # 替换为您的管理员密码
    # SQLALCHEMY_DATABASE_URI="sqlite:///instance/lottery.db" # 默认使用SQLite，可根据需要修改
    ```
    *提示：您可以使用 `python -c 'import os; print(os.urandom(24).hex())'` 生成一个随机密钥。*

5.  **初始化数据库：**
    ```bash
    flask shell
    >>> from app import db
    >>> db.create_all()
    >>> exit()
    ```
    这将创建 `instance/lottery.db` 文件和所有必要的数据库表。

6.  **运行应用：**
    ```bash
    python app.py
    ```
    应用将在 `http://127.0.0.1:5000/` 运行。

## 🌐 使用指南

### 访问前端页面

打开浏览器访问 `http://127.0.0.1:5000/`。

*   **首页 (`/`)：** 显示最新开奖信息和新闻。
*   **历史开奖 (`/history`)：**
    *   选择彩种（双色球/大乐透）。
    *   使用日期范围和统计范围筛选数据。
    *   查看号码统计图表和详细表格。
    *   点击每期旁边的“检查规则”按钮，查看该期号码是否符合预测规则。
*   **号码预测 (`/prediction`)：** (TODO) 未来将在此页面生成预测号码。
*   **兑奖中心 (`/prize_check`)：** (TODO) 未来将在此页面进行号码兑奖和趣味游戏。
*   **新闻详情 (`/news/<id>`)：** 查看具体新闻内容。

### 访问后台管理

打开浏览器访问 `http://127.0.0.1:5000/admin` (或您在 `config.py` 中设置的 `ADMIN_ROUTE_PREFIX`)。

*   **登录：** 使用 `.env` 文件中配置的 `ADMIN_PASSWORD` 进行登录。
*   **仪表盘 (`/admin`)：** 后台管理首页。
*   **网站设置 (`/admin/settings`)：**
    *   修改网站基本信息。
    *   调整预测规则的各项参数，例如：
        *   `ssq_red_omit_1_weight` (双色球红球遗漏权重)
        *   `ssq_blue_recent_occurrence_draws` (双色球蓝球最新出现频率检查期数)
        *   `ssq_blue_recent_occurrence_threshold` (双色球蓝球出现次数阈值)
        *   `ssq_blue_recent_occurrence_weight` (双色球蓝球提升概率)
        *   以及对应的大乐透参数 `dlt_...`
        *   `history_stats_range_default` 和 `history_stats_range_options` (历史统计范围)
    *   下载设置备份或恢复默认设置。
*   **数据更新 (`/admin/data_update`)：**
    *   手动触发最新开奖数据抓取。
    *   手动添加单期开奖数据。
*   **新闻管理 (`/admin/news_manage`)：** 发布、编辑、删除新闻。

## 📁 项目结构

iShoot8/
├── app.py # Flask 应用主入口

├── config.py # 全局配置，包括数据库URI、网站设置、管理员密码等

├── models.py # SQLAlchemy 数据库模型定义 (SSQDraw, DLTDraw, News等)

├── routes.py # 前端页面路由定义

├── admin_routes.py # 后台管理页面路由定义

├── data_manager.py # 负责从外部接口抓取和更新彩票数据

├── prediction_engine.py # 核心预测逻辑和规则实现

├── utils.py # 辅助函数，如号码格式化、奇偶和值计算、遗漏统计等

├── requirements.txt # 项目依赖包列表

├── .env # 环境变量配置 (敏感信息)

├── instance/

│ └── lottery.db # SQLite 数据库文件 (如果使用SQLite)

│ └── settings.json # 运行时网站设置的持久化文件

├── templates/ # HTML 模板文件

│ ├── base.html

│ ├── index.html

│ ├── history.html # 历史开奖数据及统计页面

│ ├── prediction.html

│ ├── prize_check.html

│ ├── news_detail.html
│ └── admin/ # 后台管理模板

│ ├── login.html

│ ├── dashboard.html
│ ├── settings.html # 网站设置页面

│ ├── data_update.html

│ └── news_manage.html

└── static/ # 静态资源 (CSS, JS, 图片等)

├── css/

├── js/

└── img/

## 💡 未来增强

*   完善大乐透的预测规则和检查逻辑。
*   实现号码预测页面，展示生成的预测号码。
*   实现兑奖中心页面，支持用户输入号码进行兑奖。
*   增加更多高级统计图表和分析维度（如大小比、质合比、012路等）。
*   优化数据库查询性能，尤其是在处理大量历史数据时。
*   实现用户管理和权限控制。
*   将网站设置从 `settings.json` 迁移到数据库中进行管理。
*   增加更多的用户互动及娱乐体验。

## 🤝 贡献

欢迎任何形式的贡献！如果您有任何建议、Bug 报告或功能请求，请随时提交 Issue 或 Pull Request。

## 📄 许可证

本项目采用 MIT 许可证。详情请参阅 `LICENSE` 文件。

## 📧 联系方式

如果您有任何问题，可以通过以下方式联系我：
*   GitHub Issue
*   Email: anddy.shen@outlook.com 
