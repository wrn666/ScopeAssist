import asyncio
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    UndetectedAdapter
)
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy


async def main():
    # 目标网站URL
    url = "https://www.osredm.com/"

    # 使用不可检测浏览器和JavaScript绕过浏览器检测
    print("正在测试不可检测浏览器和JavaScript绕过...")

    # 浏览器配置 - 模拟真实的Chrome浏览器
    browser_config = BrowserConfig(
        headless=True,       # 无头模式（Docker环境必需），配合UndetectedAdapter仍可避免被检测
        verbose=True,        # 详细输出
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
    )

    # 创建不可检测适配器
    adapter = UndetectedAdapter()

    # 创建爬虫策略，使用不可检测适配器
    strategy = AsyncPlaywrightCrawlerStrategy(
        browser_config=browser_config,
        browser_adapter=adapter
    )

    # JavaScript代码用于绕过浏览器检测
    js_bypass = """
    // 覆盖常见的检测方法
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
    });

    // 覆盖Chrome检测
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
    });

    // 覆盖语言检测
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en'],
    });

    // 隐藏自动化指标
    delete navigator.__proto__.webdriver;

    // 等待页面加载
    await new Promise(resolve => setTimeout(resolve, 3000));

    console.log('浏览器检测绕过尝试完成');
    """

    # 爬虫运行配置
    crawler_config = CrawlerRunConfig(
        js_code=[js_bypass],                    # 执行JavaScript绕过代码
        simulate_user=True,                     # 模拟用户行为
        magic=True,                            # 启用魔法模式
        delay_before_return_html=5.0,          # 返回HTML前的延迟时间
        capture_console_messages=True,         # 捕获控制台消息
        wait_for_images=True                   # 等待图片加载
    )

    # 创建爬虫并执行抓取
    async with AsyncWebCrawler(
        crawler_strategy=strategy,
        config=browser_config
    ) as crawler:
        result = await crawler.arun(url, config=crawler_config)

        # 输出结果摘要
        print(f"\n结果:")
        print(f"状态码: {result.status_code}")
        print(f"成功: {result.success}")
        print(f"控制台消息数量: {len(result.console_messages or [])}")

        # 检查是否仍有浏览器错误
        has_browser_error = "不支持当前浏览器" in result.html
        print(f"存在浏览器检测错误: {has_browser_error}")

        # 输出完整的Markdown内容
        print(f"\n{'='*80}")
        print("完整的MARKDOWN内容:")
        print(f"{'='*80}")
        print(result.markdown.raw_markdown)

        # 输出所有控制台消息
        print(f"\n{'='*80}")
        print("控制台消息:")
        print(f"{'='*80}")
        if result.console_messages:
            for i, msg in enumerate(result.console_messages, 1):
                print(f"{i}. {msg}")
        else:
            print("未捕获到控制台消息")


if __name__ == "__main__":
    asyncio.run(main())
