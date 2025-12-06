# 使用轻量级Python基础镜像
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.7.2 /uv /uvx /bin/

# 设置工作目录
WORKDIR /app

# 环境变量设置
ENV TZ=Asia/Shanghai \
    UV_LINK_MODE=copy \
    DEBIAN_FRONTEND=noninteractive

# 设置时区、修复tmp权限、更换镜像源
# 使用清华大学镜像源（更快更稳定），如需切换可修改下面的sed命令
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    mkdir -p /tmp /var/tmp && \
    chmod 1777 /tmp /var/tmp && \
    cp /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list.d/debian.sources.bak && \
    sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources

# 备用方案：如需使用阿里云镜像源，将上面两行sed替换为：
# sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources && \
# sed -i 's|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖（镜像源已更新，直接安装）
# 包括 Playwright 浏览器所需的依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-dev \
        ffmpeg \
        libsm6 \
        libxext6 \
        curl \
        git \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-eng \
        # Playwright 浏览器依赖
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libdbus-1-3 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libcairo2 \
        && apt-get autoremove -y && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# 复制项目配置文件
COPY ../pyproject.toml /app/pyproject.toml
COPY ../.python-version /app/.python-version

# 接收构建参数
ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""

# 设置环境变量（这些值可能是空的）
ENV HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY \
    http_proxy=$HTTP_PROXY \
    https_proxy=$HTTPS_PROXY \
    HF_ENDPOINT=https://hf-mirror.com \
    GIT_HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 如果网络还是不好，可以在后面添加 --index-url https://pypi.tuna.tsinghua.edu.cn/simple
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 安装 Playwright 浏览器（Chromium）
# 使用 uv run 来运行 playwright install，确保使用正确的 Python 环境
# 注意：playwright install 需要在 Python 包安装完成后运行
RUN uv run --no-dev python -m playwright install chromium && \
    uv run --no-dev python -m playwright install-deps chromium || true
    
# 复制代码到容器中
COPY ../src /app/src
COPY ../server /app/server
