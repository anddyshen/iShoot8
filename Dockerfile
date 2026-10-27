# 使用官方轻量级 Python 3.11 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量：禁止生成 pyc，无缓冲输出，固定中国时区
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 替换为国内镜像源加速 apt 下载
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list 2>/dev/null || true

# 安装系统级基础依赖（处理时区、图片生成等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装 Python 依赖（使用清华镜像源加速）
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目代码
COPY . /app/

# 创建持久化与上传目录
RUN mkdir -p /app/instance /app/uploads /app/backups

# 暴露端口
EXPOSE 5000

# 声明持久化卷
VOLUME ["/app/instance", "/app/uploads", "/app/backups"]

# 使用 Gunicorn 启动
# 单 worker + 多线程：保障 SQLite 数据库安全，并避免 APScheduler 重复执行
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app:app"]
