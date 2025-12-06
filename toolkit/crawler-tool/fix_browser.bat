@echo off
chcp 65001 >nul
echo ========================================
echo 🔧 Playwright 浏览器修复工具
echo ========================================

echo 🌐 正在安装 Playwright 浏览器...
echo 💡 这可能需要几分钟时间，请耐心等待...
echo.

:: 安装 Playwright
pip install playwright

:: 安装浏览器
playwright install

:: 安装系统依赖
playwright install-deps

echo.
echo ========================================
echo ✅ 浏览器安装完成！
echo 现在可以重新运行爬虫程序
echo ========================================
pause