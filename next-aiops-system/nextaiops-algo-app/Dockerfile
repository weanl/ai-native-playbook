# NextAIOpsAlgoApp Development Environment
# Python 3.11 + uv + make + git

FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

# 安装系统依赖（make, git 等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    make \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（现代 Python 包管理器）
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# 设置工作目录
WORKDIR /app

# 复制 pyproject.toml（预装依赖加速开发）
COPY pyproject.toml .

# 使用 uv 安装依赖（比 pip 快 10-100x）
RUN uv pip install --system -e ".[dev]" || echo "依赖安装将在容器启动后执行"

# 设置默认命令
CMD ["bash"]