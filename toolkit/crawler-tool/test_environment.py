import asyncio
import sys
from pathlib import Path

print("🧪 环境验证测试")
print("=" * 50)

try:
    # 测试导入
    print("📦 测试导入...")
    from crawl4ai import AsyncWebCrawler, BrowserConfig
    print("✅ crawl4ai 导入成功")
    
    from playwright.sync_api import sync_playwright
    print("✅ playwright 导入成功")
    
    # 测试浏览器
    print("🌐 测试浏览器...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://example.com")
        title = page.title()
        print(f"✅ 浏览器正常，测试页面标题: {title}")
        browser.close()
    
    # 测试简单爬取
    print("🕷️ 测试爬虫...")
    async def test_crawl():
        config = BrowserConfig(headless=True)
        async with AsyncWebCrawler(config=config) as crawler:
            result = await crawler.arun("https://example.com")
            if result.success:
                print(f"✅ 爬虫测试成功，内容长度: {len(result.markdown)}")
                return True
            else:
                print(f"❌ 爬虫测试失败: {result.error_message}")
                return False
    
    success = asyncio.run(test_crawl())
    
    if success:
        print("\n🎉 所有测试通过！环境完全正常！")
        print("💡 可以安全运行完整的爬虫程序了")
    else:
        print("\n⚠️ 爬虫测试失败")
        
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("💡 请运行 fix_all_issues.bat")
except Exception as e:
    print(f"❌ 测试失败: {e}")

print("\n按回车键继续...")
input()