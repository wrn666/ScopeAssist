"""
网页爬取模块

使用 crawl4ai 进行高级网页内容抓取，支持 JavaScript 渲染和反爬虫绕过
"""

import asyncio
import os
import subprocess
from typing import Optional

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, UndetectedAdapter
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy

from src.utils import logger

# 全局标志，确保只检查一次
_playwright_checked = False


def ensure_playwright_browser():
    """
    确保 Playwright 浏览器已安装
    如果未安装，尝试自动安装
    """
    global _playwright_checked
    
    if _playwright_checked:
        return
    
    try:
        # 尝试导入 playwright
        from playwright.sync_api import sync_playwright
        
        # 尝试启动浏览器来检查是否已安装
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        
        logger.debug("[WebCrawler] Playwright 浏览器已安装")
        _playwright_checked = True
        return
        
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"[WebCrawler] Playwright 浏览器检查失败: {error_msg}")
        
        # 检查是否是浏览器未安装的错误
        if "Executable doesn't exist" in error_msg or "playwright install" in error_msg.lower():
            logger.info("[WebCrawler] 检测到 Playwright 浏览器未安装，尝试自动安装...")
            
            try:
                # 尝试使用 subprocess 安装浏览器
                # 优先使用 uv run（如果在 Docker 环境中）
                if os.path.exists("/bin/uv") or os.path.exists("/usr/bin/uv"):
                    logger.info("[WebCrawler] 使用 uv run python -m playwright install chromium")
                    result = subprocess.run(
                        ["uv", "run", "--no-dev", "python", "-m", "playwright", "install", "chromium"],
                        capture_output=True,
                        text=True,
                        timeout=300  # 5分钟超时
                    )
                else:
                    # 使用 python -m playwright 安装（更可靠的方式）
                    import sys
                    logger.info("[WebCrawler] 使用 python -m playwright install chromium")
                    result = subprocess.run(
                        [sys.executable, "-m", "playwright", "install", "chromium"],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                
                if result.returncode == 0:
                    logger.info("[WebCrawler] Playwright 浏览器安装成功")
                    _playwright_checked = True
                else:
                    logger.error(f"[WebCrawler] Playwright 浏览器安装失败: {result.stderr}")
                    logger.warning("[WebCrawler] 请手动运行 'playwright install chromium' 或检查网络连接")
                    
            except subprocess.TimeoutExpired:
                logger.error("[WebCrawler] Playwright 浏览器安装超时")
            except FileNotFoundError:
                logger.error("[WebCrawler] 未找到 playwright 命令，请确保 playwright 已正确安装")
            except Exception as install_error:
                logger.error(f"[WebCrawler] 安装 Playwright 浏览器时出错: {install_error}")
        
        _playwright_checked = True  # 即使失败也标记为已检查，避免重复尝试


async def crawl_url(url: str, timeout: int = 60) -> Optional[str]:
    """
    使用 crawl4ai 爬取网页内容，支持 JavaScript 渲染和反爬虫绕过
    
    Args:
        url: 要爬取的网页 URL
        timeout: 超时时间（秒）
    
    Returns:
        str: 提取的 Markdown 格式文本，如果失败返回 None
    """
    # 确保 Playwright 浏览器已安装
    ensure_playwright_browser()
    
    try:
        logger.debug(f"[WebCrawler] 开始爬取网页: {url}")
        
        # 浏览器配置 - 模拟真实的 Chrome 浏览器
        browser_config = BrowserConfig(
            headless=True,  # 无头模式（Docker环境必需），配合UndetectedAdapter仍可避免被检测
            verbose=True,  # 详细输出
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

        # JavaScript 代码用于绕过浏览器检测
        js_bypass = """
        // 覆盖常见的检测方法
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });

        // 覆盖 Chrome 检测
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
            js_code=[js_bypass],  # 执行 JavaScript 绕过代码
            simulate_user=True,  # 模拟用户行为
            magic=True,  # 启用魔法模式
            delay_before_return_html=5.0,  # 返回 HTML 前的延迟时间
            capture_console_messages=True,  # 捕获控制台消息
            wait_for_images=True  # 等待图片加载
        )

        # 创建爬虫并执行抓取
        async with AsyncWebCrawler(
            crawler_strategy=strategy,
            config=browser_config
        ) as crawler:
            result = await crawler.arun(url, config=crawler_config)

            if not result.success:
                logger.warning(f"[WebCrawler] 爬取失败: {url}, 状态码: {result.status_code}")
                return None

            # 检查是否仍有浏览器错误
            if result.html and "不支持当前浏览器" in result.html:
                logger.warning(f"[WebCrawler] 检测到浏览器检测错误: {url}")

            # 获取 Markdown 内容
            if result.markdown and result.markdown.raw_markdown:
                markdown_content = result.markdown.raw_markdown.strip()
                logger.debug(f"[WebCrawler] 爬取成功: {url}, 内容长度: {len(markdown_content)} 字符")
                return markdown_content
            else:
                logger.warning(f"[WebCrawler] 未获取到 Markdown 内容: {url}")
                return None

    except Exception as e:
        logger.error(f"[WebCrawler] 爬取网页失败: {url}, 错误: {str(e)}")
        import traceback
        logger.debug(f"[WebCrawler] 异常详情: {traceback.format_exc()}")
        return None


async def crawl_url_sync(url: str, timeout: int = 60) -> Optional[str]:
    """
    同步版本的爬取函数，用于在非异步上下文中调用
    
    Args:
        url: 要爬取的网页 URL
        timeout: 超时时间（秒）
    
    Returns:
        str: 提取的 Markdown 格式文本，如果失败返回 None
    """
    try:
        # 尝试获取当前事件循环
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果事件循环正在运行，创建一个新任务
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, crawl_url(url, timeout))
                return future.result(timeout=timeout + 10)
        else:
            return await crawl_url(url, timeout)
    except RuntimeError:
        # 如果没有事件循环，创建一个新的
        return asyncio.run(crawl_url(url, timeout))
    except Exception as e:
        logger.error(f"[WebCrawler] 同步爬取失败: {url}, 错误: {str(e)}")
        return None

