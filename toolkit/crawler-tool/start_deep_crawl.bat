@echo off
chcp 65001 >nul
cls
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                🚀 OSRedm 深度爬取启动器                     ║
echo ║                    持续多轮深度爬取                          ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: 检查环境
echo 🔍 检查运行环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 未安装
    pause
    exit /b 1
)

python -c "import crawl4ai" >nul 2>&1
if errorlevel 1 (
    echo ❌ crawl4ai 未安装，正在修复...
    call fix_all_issues.bat
)

echo ✅ 环境检查完成
echo.
echo 🎯 准备启动深度爬取模式
echo ⚠️  注意：此模式将进行长时间深度爬取
echo 📁 结果保存至：markdown 文件夹
echo 🔄 支持中断后继续爬取
echo.

echo 启动中...
python deep_crawl.py

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    🏁 深度爬取完成                           ║
echo ║              检查 markdown 文件夹查看结果                    ║
echo ╚══════════════════════════════════════════════════════════════╝
pause