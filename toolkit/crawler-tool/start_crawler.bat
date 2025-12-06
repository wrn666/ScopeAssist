@echo off
chcp 65001 >nul
echo ========================================
echo 🚀 OSRedm 全站爬虫系统启动
echo ========================================

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

:: 检查crawl4ai是否安装
python -c "import crawl4ai" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  警告: 未检测到crawl4ai库
    echo 是否现在安装依赖? (Y/N)
    set /p install=
    if /i "%install%"=="Y" (
        call install_requirements.bat
    ) else (
        echo 请先运行 install_requirements.bat 安装依赖
        pause
        exit /b 1
    )
)

:: 检查Playwright浏览器是否安装
python -c "from playwright.sync_api import sync_playwright; sync_playwright().start().chromium.launch()" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  警告: Playwright 浏览器未正确安装
    echo 这是导致错误的常见原因
    echo 是否现在修复浏览器安装? (Y/N)
    set /p fix=
    if /i "%fix%"=="Y" (
        call fix_browser.bat
    ) else (
        echo 请先运行 fix_browser.bat 修复浏览器
        pause
        exit /b 1
    )
)

echo ✅ 环境检查完成
echo 📁 输出目录: %cd%
echo ⚙️  配置文件: config.py
echo 📝 详细说明: README.md
echo.
echo 🎯 准备开始爬取 https://www.osredm.com/
echo.

:: 启动爬虫
python main.py

echo.
echo ========================================
echo 🏁 爬虫运行完成
echo ========================================
pause