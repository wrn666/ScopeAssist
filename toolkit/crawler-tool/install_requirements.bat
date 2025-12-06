@echo off
chcp 65001 >nul
echo ========================================
echo OSRedm 全站爬虫系统 - 依赖安装
echo ========================================

echo 📦 正在升级pip...
python -m pip install --upgrade pip

echo 📦 正在安装 crawl4ai...
pip install crawl4ai

echo 📦 正在安装 playwright...
pip install playwright

echo 🌐 正在安装 Playwright 浏览器 (这可能需要几分钟)...
playwright install

echo 🛠️  正在运行 crawl4ai 设置...
crawl4ai-setup

echo ========================================
echo ✅ 安装完成！
echo 现在可以运行 python main.py 开始爬取
echo ========================================
pause