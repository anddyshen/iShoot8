# iShoot - 智能彩票数据分析与预测系统

<p align="center">
  <img src="static/img/favicon.ico" alt="iShoot Logo" width="64" height="64">
  <br>
  <b>iShoot · 科学数据分析 · 多维智能缩水 · 投资回报核算</b>
  <br>
  <span>✨ 当前版本：<b>v2.0.0</b></span>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.13-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.1.3-green?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/Bootstrap-5.3.2-purple?logo=bootstrap" alt="Bootstrap">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/Synology-Supported-0080FF" alt="Synology NAS">
  <img src="https://img.shields.io/badge/License-MIT-brightgreen" alt="License">
</p>

---

## 🚀 项目简介

`iShoot` 是一个基于 **Flask 3 + SQLite/MySQL + Bootstrap 5.3** 构建的专业级彩票数据智能分析、走势可视化、号码科学缩水筛选与投资收益（ROI）核算系统。

系统针对国内主流彩种——**双色球（SSQ）**与**超级大乐透（DLT）**，完整适配了 **2026年最新开奖规则与奖金计算机制**（双色球“福运奖”、大乐透新7级奖金结构及追加投注浮动奖机制）。系统集成了现代轻科技风格 UI，原生支持白天/暗黑模式自适应切换与立体 3D 晶莹彩票球展示，兼具极佳的可视化表现与严谨的概率算法。

---

## ✨ 核心功能特性

### 1. 📊 开奖数据全量管理与自动采集
* **实时/历史开奖同步**：内置定时任务引擎（APScheduler），每天自动自外部权威接口同步最新双色球与大乐透开奖结果；支持手动补全与单期更新。
* **数据维度完备**：覆盖期号、开奖日期、前/后区出球顺序、销售总额、奖池滚存金额、各级奖项中奖注数及单注奖金。
* **多维条件检索**：支持按彩种、开奖年份、日期区间及自定义分页大小灵活筛选。

### 2. 📈 高阶号码统计与走势可视化
* **冷热号与出现频率分析**：多周期（最近 N 期 / 全历史）统计红蓝球出现频次、占比百分比。
* **遗漏期数追踪**：精准计算每个号码的当前连续遗漏期数与历史最大遗漏极值。
* **动态图表呈现**：结合 Chart.js 绘制直观的出现频率柱状图与遗漏走势图，支持热冷号智能视觉高亮。

### 3. 🎯 科学智能号码缩水与过滤引擎
* **核心过滤算法**：支持数十项自定义概率与结构过滤规则（连号形态、奇偶比、区间比、和值跨度、冷热权重、高遗漏降权阈值等）。
* **历史回测与规则检验**：支持将任意一期真实开奖号码与预设规则进行反向交叉比对，验证规则有效性。
* **批量模拟选号**：支持按“规则严格筛选”或“概率加权随机”快速生成投注建议，降低大复式投注成本。

### 4. 🏆 对奖中心与投资回报率 (ROI) 精算
* **全投注形态核验**：完美支持单式投注、复式投注以及大乐透 1 元追加投注的批量中奖核验。
* **收益财务看板**：自动精算总投入金额、各级中奖总金额、净盈亏损益与 ROI 百分比，提供直观的盈亏视觉反馈。
* **2026 新规专享支持**：双色球奖池 ≥15 亿元自动触发福运奖核对；大乐透奖池 >8 亿元自动联动浮动奖金测算。

### 5. 👥 多用户体系与追号中心
* **分级权限与用户隔离**：支持普通会员与系统管理员，各用户独立维护个人资产。
* **心仪号码收藏**：随时收藏看好的号码组合，一键送入筛选或对奖中心。
* **已购彩票追号管理**：登记实际购买的彩票注单，系统开奖后自动触发中奖核算。
* **注册与安全机制**：内置 PIL 图形验证码防刷、密码强度检测、支持开启管理员邀请码注册模式。

### 6. 🔔 多渠道主动消息通知系统
* **站内信 (In-App)**：顶部导航栏带未读消息小铃铛徽章与即时预览下拉。
* **SMTP 邮件推送**：支持开奖提醒、中奖战报、密码重置验证等邮件通知。
* **群晖 Synology Chat**：支持通过 Webhook 将开奖和中奖提醒直接推送到群晖 NAS 个人或团队聊天频道。

### 7. 🎨 现代设计系统 (Modern Tech Dashboard)
* **原生暗黑模式**：顶栏一键切换白天/暗黑模式，零白闪平滑过渡，夜间护眼。
* **3D 晶莹立体号码球**：高光径向渐变、立体投影、悬停放大与连号彩色高光圈。
* **分级设置菜单**：右上角用户头像下拉菜单清晰分离“普通用户个人偏好设置”与“管理员系统设置”。

---

## 🛠️ 技术栈

* **后端服务**：Python 3.11 / 3.13、Flask 3.1.3、Flask-SQLAlchemy 3.1、Flask-Login、Flask-Mail、Flask-Migrate
* **后台任务**：APScheduler 3.11（支持 Cron 定时调度与动态参数更新）
* **生产服务器**：Gunicorn 26.2（支持单/多工作线程与健康检查）
* **数据库**：SQLite 3（默认轻量免配置，数据存储于 `instance/ishoot.db`）/ 可扩展 MySQL
* **前端框架**：HTML5, CSS3, Bootstrap 5.3.2, Bootstrap Icons 1.11, Chart.js

---

## 🐳 群晖 NAS (Synology Container Manager) 部署指南

群晖 Container Manager（原 Docker 套件）支持通过项目（docker-compose）一键构建运行，步骤如下：

### 步骤 1：上传项目代码到群晖
在群晖 File Station 中，打开 `docker` 共享文件夹，新建目录 `ishoot`（路径为 `/docker/ishoot`），将本项目所有代码解压上传至该文件夹中。

### 步骤 2：在群晖 Container Manager 中创建项目
1. 打开群晖 DSM 的 **Container Manager**；
2. 点击左侧导航栏的 **“项目 (Project)”** -> 点击 **“新增 (Create)”**；
3. 填写配置：
   - **项目名称**：`ishoot`
   - **路径**：选择刚才上传的文件夹 `/docker/ishoot`
   - **来源**：选择 **“创建 docker-compose.yaml”** 或 **“使用现有的 docker-compose.yaml”**；
4. 点击“下一步”并勾选“构建完成后立即启动”，系统将全自动编译镜像并拉起服务！

### 步骤 3：访问与注意事项
* 部署成功后，在浏览器中访问：`http://<群晖局域网IP>:6666/`
* **重要端口提示**：
  > ⚠️ 避开群晖默认的 5000 管理端口，本项目的 Docker 映射端口已设为 **`6666:6666`**。如需修改宿主机端口，只需调整 compose 中的 `6666` 即可。
* **数据安全持久化**：
  > 数据库保存在 `/docker/ishoot/instance/ishoot.db`，所有系统设置与追号历史在容器更新或重启后均永久保留。

---

## 📦 标准 Docker / Docker Compose 部署

适用于任何标准的 Linux 服务器、VPS、Unraid、极空间或绿联等 NAS 设备：

```bash
# 1. 克隆代码仓库
git clone https://github.com/anddyshen/iShoot8.git
cd iShoot8

# 2. 一键构建并启动后台容器
docker-compose up -d --build

# 3. 查看容器运行日志与状态
docker-compose logs -f
```
访问地址：`http://<服务器IP>:6666/`

---

## 💻 本地开发环境安装与启动

如果您需要在本地调试或开发：

### 1. 准备环境
* Python 3.11 或 3.12 / 3.13
* Git

### 2. 克隆与安装
```bash
git clone https://github.com/anddyshen/iShoot8.git
cd iShoot8

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# 或 (Linux / macOS)
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 运行项目
* **Windows 一键运行**：直接双击根目录下的 [`run.bat`](file:///d:/Projects/iShoot8/run.bat)；
* **命令行运行**：
  ```bash
  python app.py
  ```
* **VSCode 调试**：直接打开项目，按键盘 **F5** 即可进入断点调试模式（已预置 `.vscode/settings.json` 与 `.vscode/launch.json`）。

---

## 🔑 默认初始账号与后台入口

首次启动时，系统会自动完成数据库建表并初始化管理员账号：

| 账号类型 | 用户名 | 默认初始密码 | 权限说明 |
| :--- | :--- | :--- | :--- |
| **超级管理员** | `admin` | `admin123` | 拥有全部管理权限（请登录后在个人中心立即修改密码！） |

* **前台首页**：`http://127.0.0.1:5000/`
* **后台管理安全混淆入口**：`http://127.0.0.1:5000/admin_xyz12/`
  *(路由前缀可在 `.env` 或 `config.py` 中的 `ADMIN_ROUTE_PREFIX` 自行修改)*

---

## ⚠️ 免责声明 (Disclaimer)

1. 本项目所有代码及算法仅供 Python/Flask 编程学习、数据可视化研究与数学趣味探讨。
2. 彩票开奖结果属于完全随机事件，任何历史统计、遗漏分析及缩水过滤算法均**无法**改变概率学中奖期望。
3. 请广大用户理性娱乐，严禁利用本项目进行任何形式的非法博彩或商业兜售活动。

---

## 📄 授权协议

本项目基于 [MIT License](LICENSE) 开源。欢迎 Star、Fork 与提交 Pull Request！
