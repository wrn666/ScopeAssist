"""网络爬虫工具 - 提供网页内容抓取功能"""

from typing import Annotated, Any
from urllib.parse import urlparse

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.knowledge.web_crawler import crawl_url
from src.utils import logger


class WebCrawlerModel(BaseModel):
    """网络爬虫的参数模型"""

    url: str = Field(
        description="要爬取的网页URL，必须是有效的HTTP或HTTPS链接",
        example="https://www.example.com/article",
    )
    timeout: int = Field(
        default=60,
        description="超时时间（秒），默认60秒",
        ge=10,
        le=300,
    )


def _validate_url(url: str) -> tuple[bool, str]:
    """
    验证URL是否安全有效

    Returns:
        (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "URL不能为空"

    # 检查URL格式
    parsed = urlparse(url)
    if not parsed.scheme:
        return False, "URL格式不正确，必须包含协议（如 https:// 或 http://）"

    # 只允许HTTP和HTTPS协议
    allowed_schemes = ["http", "https"]
    if parsed.scheme not in allowed_schemes:
        return False, f"不支持的协议: {parsed.scheme}，仅支持: {', '.join(allowed_schemes)}"

    # 检查是否有危险的字符或路径遍历
    dangerous_patterns = [
        r"\.\./",  # 路径遍历
        r"\.\.\\",  # Windows路径遍历
        r"%2e%2e",  # URL编码的..
        r"%2E%2E",  # URL编码的..
    ]

    import re

    for pattern in dangerous_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return False, f"URL包含不安全的字符: {pattern}"

    return True, ""


async def web_crawler_wrapper(
    url: Annotated[str, "要爬取的网页URL，必须是有效的HTTP或HTTPS链接"],
    timeout: Annotated[int, "超时时间（秒），默认60秒"] = 60,
) -> str:
    """爬取网页内容并转换为Markdown格式

    这个工具可以爬取网页内容，支持JavaScript渲染和反爬虫绕过。
    返回的内容是Markdown格式的文本，便于阅读和处理。

    参数:
    - url: 要爬取的网页URL（必须是HTTP或HTTPS协议）
    - timeout: 超时时间（秒），默认60秒，范围10-300秒

    返回:
    - 成功时返回Markdown格式的网页内容
    - 失败时返回错误信息

    注意:
    - 工具会自动处理JavaScript渲染和反爬虫检测
    - 对于需要登录的页面可能无法访问
    - 爬取速度取决于网页的复杂度和网络状况
    """
    try:
        # 验证URL
        is_valid, error_msg = _validate_url(url)
        if not is_valid:
            logger.error(f"Invalid URL: {error_msg}")
            return f"❌ URL验证失败: {error_msg}"

        logger.info(f"开始爬取网页: {url}")

        # 调用爬虫函数
        result = await crawl_url(url, timeout=timeout)

        if result is None:
            error_msg = f"❌ 爬取网页失败: {url}\n可能的原因：\n- 网页无法访问或超时\n- 网页需要登录认证\n- 网络连接问题\n- 网页内容为空"
            logger.warning(error_msg)
            return error_msg

        # 限制返回内容长度，避免过长
        max_length = 50000  # 最大50000字符
        if len(result) > max_length:
            truncated_result = result[:max_length] + f"\n\n... (内容已截断，原始内容长度为 {len(result)} 字符)"
            logger.warning(f"网页内容过长，已截断: {len(result)} -> {max_length} 字符")
            return f"✅ 成功爬取网页内容（已截断）:\n\n{truncated_result}"
        else:
            logger.info(f"成功爬取网页: {url}, 内容长度: {len(result)} 字符")
            return f"✅ 成功爬取网页内容:\n\n{result}"

    except Exception as e:
        error_msg = f"❌ 爬取网页时发生错误: {str(e)}"
        logger.error(f"Web crawler error: {error_msg}")
        import traceback

        logger.debug(f"Web crawler traceback: {traceback.format_exc()}")
        return error_msg


def get_web_crawler_tools() -> list[Any]:
    """获取网络爬虫工具列表"""
    web_crawler_tool = StructuredTool.from_function(
        coroutine=web_crawler_wrapper,
        name="web_crawler",
        description="""爬取网页内容并转换为Markdown格式，支持JavaScript渲染和反爬虫绕过。

使用说明:
* URL必须是有效的HTTP或HTTPS链接
* 工具会自动处理JavaScript渲染，适合动态网页
* 支持绕过常见的反爬虫检测机制
* 返回的内容是Markdown格式，便于阅读和处理
* 对于需要登录的页面可能无法访问
* 爬取速度取决于网页的复杂度和网络状况

示例:
- https://www.example.com/article  # 爬取文章内容
- https://news.example.com/latest   # 爬取新闻页面
- https://docs.example.com/guide    # 爬取文档页面
""",
        args_schema=WebCrawlerModel,
        metadata={"tag": ["web", "crawler", "scraper"]},
    )

    return [web_crawler_tool]

