@echo off
chcp 65001 >nul
cls
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                   🔧 一键问题解决工具                        ║
echo ║              OSRedm 全站爬虫系统                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo 🚀 正在检测和修复所有可能的问题...
echo.

echo [1/5] 📦 升级 pip...
python -m pip install --upgrade pip >nul 2>&1

echo [2/5] 📦 安装 crawl4ai...
pip install crawl4ai >nul 2>&1

echo [3/5] 📦 安装 playwright...
pip install playwright >nul 2>&1

echo [4/5] 🌐 安装浏览器 (这可能需要几分钟)...
playwright install >nul 2>&1

echo [5/5] 🛠️  运行 crawl4ai 设置...
crawl4ai-setup >nul 2>&1

echo.
echo ✅ 完成环境修复！
echo.
echo 🧪 正在进行环境测试...

:: 测试 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 未安装或不可用
    goto :error
) else (
    echo ✅ Python 正常
)

:: 测试 crawl4ai
python -c "import crawl4ai" >nul 2>&1
if errorlevel 1 (
    echo ❌ crawl4ai 库导入失败
    goto :error
) else (
    echo ✅ crawl4ai 库正常
)

:: 测试 playwright
python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo ❌ playwright 库导入失败
    goto :error
) else (
    echo ✅ playwright 库正常
)

:: 测试浏览器
python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); b.close(); p.stop()" >nul 2>&1
if errorlevel 1 (
    echo ❌ 浏览器不可用
    goto :error
) else (
    echo ✅ 浏览器正常
)

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                     🎉 环境完全正常！                        ║
echo ║                 现在可以开始爬取了                            ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo 💡 下一步操作：
echo    1. 运行 start_crawler.bat 开始爬取
echo    2. 或运行 quick_test.py 进行快速测试
echo.
goto :end

:error
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    ⚠️  仍有问题存在                          ║
echo ║              请检查网络连接后重新运行此脚本                   ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:end
pause