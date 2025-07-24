# 使用官方 Python 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装诗歌依赖管理工具
# RUN pip install poetry

# 复制依赖文件并安装
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app.py .

# 暴露 Chainlit 端口
EXPOSE 8000

# 设置环境变量，让 Chainlit 监听所有网络接口
ENV CHAINLIT_HOST=0.0.0.0
ENV CHAINLIT_PORT=8000

# 启动应用的命令
# --headless 模式对于在容器中运行至关重要
CMD ["chainlit", "run", "app.py", "--headless"]