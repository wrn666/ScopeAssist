import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Optional
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    UndetectedAdapter,
    CacheMode
)
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher, RateLimiter
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


@dataclass
class CrawlProgress:
    """爬取进度数据类"""
    total_urls: int = 0
    completed_urls: int = 0
    failed_urls: int = 0
    discovered_urls: int = 0
    start_time: Optional[datetime] = None
    
    def get_progress_rate(self) -> float:
        return (self.completed_urls / self.total_urls * 100) if self.total_urls > 0 else 0.0


class OSRedmCrawler:
    """红山网络全站爬虫系统"""
    
    def __init__(self, base_url: str = "https://www.osredm.com/", output_dir: str = None):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.output_dir = Path(output_dir or r"D:\HuaweiMoveData\Users\21438\Desktop\红山网络怕爬虫")
        
        # 加载配置文件
        self.load_config()
        
        # 创建必要的目录结构
        self.setup_directories()
        
        # 初始化日志系统
        self.setup_logging()
        
        # URL管理
        self.discovered_urls: Set[str] = set()
        self.completed_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.url_queue: List[str] = []
        
        # 进度追踪
        self.progress = CrawlProgress()
        
        # 文件路径
        self.urls_file = self.output_dir / "urls_discovered.json"
        self.progress_file = self.output_dir / "crawl_progress.json"
        self.failed_urls_file = self.output_dir / "failed_urls.json"
        
        # 加载已有的进度数据
        self.load_progress()
        
        self.logger.info(f"OSRedmCrawler 初始化完成 - 目标: {self.base_url}")
    
    def load_config(self):
        """加载配置文件"""
        try:
            # 导入配置
            from config import CRAWL_CONFIG
            self.config = CRAWL_CONFIG
        except ImportError:
            # 如果配置文件不存在，使用默认配置
            self.config = {
                "max_pages": 6000,
                "batch_size": 5,
                "max_rounds": 25,
                "delay_between_batches": 2,
                "delay_between_requests": 1,
                "delay_between_rounds": 10,
                "timeout": 35,  # 增加基础超时从20秒到35秒
                "explore_timeout": 60,  # 专门为探索页面设置60秒超时
                "max_retries": 3,
                "retry_delay": 2,  # 增加重试延迟
            }
        
    def setup_directories(self):
        """设置目录结构"""
        self.output_dir.mkdir(exist_ok=True)
        (self.output_dir / "markdown").mkdir(exist_ok=True)
        (self.output_dir / "logs").mkdir(exist_ok=True)
        (self.output_dir / "assets").mkdir(exist_ok=True)
        
    def setup_logging(self):
        """设置日志系统"""
        log_file = self.output_dir / "logs" / f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_progress(self):
        """加载爬取进度"""
        try:
            if self.urls_file.exists():
                with open(self.urls_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.discovered_urls = set(data.get('discovered', []))
                    self.completed_urls = set(data.get('completed', []))
                    self.failed_urls = set(data.get('failed', []))
                    
            if self.progress_file.exists():
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.progress.total_urls = data.get('total_urls', 0)
                    self.progress.completed_urls = data.get('completed_urls', 0)
                    self.progress.failed_urls = data.get('failed_urls', 0)
                    self.progress.discovered_urls = data.get('discovered_urls', 0)
                    
            self.logger.info(f"加载进度: 已发现{len(self.discovered_urls)}个URL, 已完成{len(self.completed_urls)}个")
            
        except Exception as e:
            self.logger.warning(f"加载进度失败: {e}")
            
    def save_progress(self):
        """保存爬取进度"""
        try:
            # 保存URL数据
            url_data = {
                'discovered': list(self.discovered_urls),
                'completed': list(self.completed_urls),
                'failed': list(self.failed_urls),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.urls_file, 'w', encoding='utf-8') as f:
                json.dump(url_data, f, ensure_ascii=False, indent=2)
                
            # 保存进度数据
            progress_data = {
                'total_urls': self.progress.total_urls,
                'completed_urls': self.progress.completed_urls,
                'failed_urls': self.progress.failed_urls,
                'discovered_urls': self.progress.discovered_urls,
                'progress_rate': self.progress.get_progress_rate(),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"保存进度失败: {e}")
    
    def _is_loop_url(self, url: str) -> bool:
        """检测是否为循环URL - 防止死循环爬取"""
        path = urlparse(url).path.lower()
        
        # 更严格的检测：超过1个explore就认为是循环
        explore_count = path.count('/explore/')
        if explore_count > 1:
            return True
        
        # 检查重复的page模式
        page_count = path.count('/page/')
        if page_count > 1:
            return True
            
        # 检查路径片段
        path_parts = [p for p in path.split('/') if p]
        
        # 检查连续重复的路径片段
        for i in range(len(path_parts) - 1):
            if path_parts[i] == path_parts[i + 1] and path_parts[i] in ['explore', 'help', 'page', 'all']:
                return True
        
        # 检查重复片段计数
        if path_parts.count('explore') > 1:
            return True
        if path_parts.count('all') > 1:
            return True
        if path_parts.count('page') > 1:
            return True
                
        # 检查路径长度是否异常（降低阈值）
        if len(path) > 60:
            return True
            
        # 检查路径层级是否过深（降低阈值）
        if len(path_parts) > 6:
            return True
            
        return False
    
    def get_dynamic_timeout(self, url: str, retry_count: int = 0) -> int:
        """根据URL类型动态获取超时时间"""
        # 基础超时时间
        base_timeout = self.config["timeout"]
        
        # 探索页面需要更长时间
        if '/explore/' in url or '/repos?' in url:
            explore_timeout = self.config.get("explore_timeout", 60)
            timeout = explore_timeout
        else:
            timeout = base_timeout
        
        # 重试时逐步增加超时
        if retry_count > 0:
            timeout = min(timeout + retry_count * 15, 120)  # 每次重试增加15秒，最大120秒
        
        return timeout
    
    def _normalize_url(self, url: str) -> str:
        """URL规范化，移除重复参数和清理路径"""
        parsed = urlparse(url)
        path = parsed.path
        
        # 清理重复的page路径 - 核心修复
        if '/page/' in path and path.count('/page/') > 1:
            # 保留最后一个有效的page参数
            parts = path.split('/page/')
            if len(parts) > 1:
                base_part = parts[0]
                # 找到最后一个有效的数字页码
                last_valid_page = None
                for part in reversed(parts[1:]):
                    page_match = re.match(r'^(\d+)', part)
                    if page_match:
                        last_valid_page = page_match.group(1)
                        break
                
                if last_valid_page:
                    path = f"{base_part}/page/{last_valid_page}"
                else:
                    path = base_part
        
        # 移除跟踪参数和重复参数
        query_params = []
        seen_params = set()
        if parsed.query:
            for param in parsed.query.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    if (key.lower() not in ['utm_source', 'utm_medium', 'utm_campaign', 
                                          'utm_content', 'utm_term', 'fbclid', 'gclid',
                                          '_ga', '_gid', 'ref', 'referrer'] and
                        key not in seen_params):
                        query_params.append(param)
                        seen_params.add(key)
        
        clean_query = '&'.join(query_params)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{path}"
        if clean_query:
            clean_url += f"?{clean_query}"
        if parsed.fragment and parsed.fragment not in ['', 'top']:
            clean_url += f"#{parsed.fragment}"
        
        return clean_url
            
    def extract_urls_from_content(self, html_content: str, current_url: str) -> Set[str]:
        """从HTML内容中提取URL - 重点关注开源项目"""
        urls = set()
        
        # 扩展的URL匹配模式
        url_patterns = [
            r'href=["\']([^"\']+)["\']',          # href属性
            r'src=["\']([^"\']+)["\']',           # src属性
            r'action=["\']([^"\']+)["\']',        # action属性
            r'url\(["\']?([^"\')\s]+)["\']?\)',   # CSS url()
            r'data-url=["\']([^"\']+)["\']',      # data-url属性
            r'data-href=["\']([^"\']+)["\']',     # data-href属性
            r'data-link=["\']([^"\']+)["\']',     # data-link属性
            r'window\.location\.href\s*=\s*["\']([^"\']+)["\']',  # JavaScript跳转
            r'location\.href\s*=\s*["\']([^"\']+)["\']',          # JavaScript跳转
            r'"url"\s*:\s*"([^"]+)"',             # JSON中的URL
            r"'url'\s*:\s*'([^']+)'",             # JSON中的URL (单引号)
        ]
        
        # 针对开源项目页面的特殊模式
        project_patterns = [
            r'/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+(?:["\'\s>])',  # 项目路径 /user/project
            r'explore/repos[^"\']*',                         # 探索页面
            r'explore/all[^"\']*',                           # 探索页面
        ]
        
        all_patterns = url_patterns + project_patterns
        
        for pattern in all_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                url = match.strip()
                
                # 跳过明显无效的URL
                if any(skip in url.lower() for skip in [
                    'javascript:', 'mailto:', 'tel:', 'ftp:', 'file:',
                    '#', 'data:', 'blob:', 'about:', 'chrome:', 'edge:'
                ]):
                    continue
                
                # 标准化URL
                if url.startswith('//'):
                    url = 'https:' + url
                elif url.startswith('/'):
                    url = urljoin(self.base_url, url)
                elif not url.startswith('http'):
                    url = urljoin(current_url, url)
                    
                # 清理URL参数（保留重要参数）
                parsed = urlparse(url)
                if parsed.netloc == self.domain:
                    # 死循环检测 - 关键修复
                    if self._is_loop_url(url):
                        continue
                    
                    # 初步过滤明显的文件URL
                    path_lower = parsed.path.lower()
                    if any(ext in path_lower for ext in ['.jpg', '.png', '.gif', '.css', '.js', '.pdf']):
                        continue
                    
                    # URL规范化处理
                    clean_url = self._normalize_url(url)
                    if clean_url and clean_url != url:  # 只添加规范化后的URL
                        urls.add(clean_url)
                    elif not self._is_loop_url(clean_url or url):  # 双重检查
                        urls.add(clean_url or url)
                    
        # 额外的深度搜索：查找隐藏的链接模式（带循环检测）
        # 搜索可能的分页链接 - 修复版本，严格限制
        pagination_patterns = [
            r'page[=/_](\d+)',
            r'p[=/_](\d+)',
        ]
        
        # 仅对主要页面进行分页发现，严格限制条件
        current_parsed = urlparse(current_url)
        base_path = current_parsed.path.lower()
        
        # 只对简单路径进行分页发现，特别优化探索页面
        should_discover_pagination = (
            # 路径深度不超过2层
            base_path.count('/') <= 2 and
            # 不包含已有的page路径
            '/page/' not in base_path and
            # 不是用户个人信息页面
            not any(keyword in base_path for keyword in ['/following', '/followers', '/organizes', '/commits', '/stargazers']) and
            # 不是项目开发细节页面
            not any(dev_keyword in base_path for dev_keyword in ['/commits/', '/commit/', '/tree/', '/blob/', '/diff/', '/compare/']) and
            # 不是特定项目的过深页面
            not ('cpm-9g-8b' in base_path and any(deep in base_path for deep in ['/commits/', '/tree/', '/blob/']))
        )
        
        # 特殊处理：为explore页面生成更多分页
        is_explore_page = '/explore' in base_path
        
        if should_discover_pagination or is_explore_page:
            for pattern in pagination_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    try:
                        page_num = int(match)
                        # 根据页面类型调整发现范围
                        max_pages = 50 if is_explore_page else 10  # explore页面允许更多分页
                        
                        if 1 <= page_num <= max_pages:
                            base_url = f"{current_parsed.scheme}://{current_parsed.netloc}{current_parsed.path}"
                            
                            # 生成下一页和多个后续页面URL
                            possible_urls = [
                                f"{base_url}?page={page_num + 1}",
                            ]
                            
                            # 对于explore页面，额外生成更多分页
                            if is_explore_page and page_num < 20:
                                for i in range(2, 6):  # 额外生成后续4页
                                    if page_num + i <= max_pages:
                                        possible_urls.append(f"{base_url}?page={page_num + i}")
                            
                            for purl in possible_urls:
                                if (urlparse(purl).netloc == self.domain and 
                                    not self._is_loop_url(purl)):
                                    normalized_url = self._normalize_url(purl)
                                    if normalized_url:
                                        urls.add(normalized_url)
                    except ValueError:
                        continue
                    
        return urls
        
    def get_safe_filename(self, url: str) -> str:
        """生成安全的文件名"""
        # 移除协议和域名
        path = urlparse(url).path
        if not path or path == '/':
            filename = 'index'
        else:
            filename = path.strip('/').replace('/', '_')
            
        # 移除或替换不安全的字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename[:100]  # 限制文件名长度
        
        if not filename:
            filename = 'page'
            
        return f"{filename}.md"
        
    def clean_anti_crawler_content(self, markdown_content: str) -> str:
        """清理反爬虫警告和无价值信息"""
        lines = markdown_content.split('\n')
        cleaned_lines = []
        skip_next_lines = 0
        
        # 定义需要过滤的内容模式
        filter_patterns = [
            r'不支持当前浏览器',
            r'请更换浏览器',
            r'推荐使用谷歌浏览器',
            r'360浏览器极速模式',
            r'火狐浏览器',
            r'Edge浏览器',
            r'红山开源社区-黑色',
            r'登录\[注册\]',
            r'!\[\]\(https://www\.osredm\.com/images/avatars/',
            r'!\[红山开源社区',
        ]
        
        # 定义导航菜单模式（通常是链接列表）
        nav_patterns = [
            r'\* \[首页\]',
            r'\* \[开源项目\]',
            r'\* \[创客空间\]',
            r'\* \[开放竞赛\]',
            r'\* \[社区动态\]',
            r'\* \[成果库\]',
            r'\* \[资源库\]',
            r'\* \[公告\]',
            r'\* \[Bot市场\]',
        ]
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 跳过已标记要跳过的行
            if skip_next_lines > 0:
                skip_next_lines -= 1
                i += 1
                continue
            
            # 检查是否是反爬虫警告行
            is_filter_line = any(re.search(pattern, line, re.IGNORECASE) for pattern in filter_patterns)
            
            # 检查是否是导航菜单行
            is_nav_line = any(re.search(pattern, line, re.IGNORECASE) for pattern in nav_patterns)
            
            if is_filter_line:
                # 找到反爬虫警告，跳过后续相关行
                if '不支持当前浏览器' in line:
                    skip_next_lines = 2  # 跳过后续的推荐浏览器行
                i += 1
                continue
            elif is_nav_line:
                # 检测到导航菜单开始，跳过整个导航块
                nav_count = 0
                j = i
                while j < len(lines) and nav_count < 20:  # 最多跳过20行导航
                    if any(re.search(pattern, lines[j].strip(), re.IGNORECASE) for pattern in nav_patterns):
                        nav_count += 1
                        j += 1
                    elif lines[j].strip().startswith('* [') and 'osredm.com' in lines[j]:
                        # 其他包含osredm.com的导航链接
                        j += 1
                    else:
                        break
                i = j
                continue
            elif line.startswith('![') and 'osredm.com/images' in line:
                # 跳过网站Logo和头像图片
                i += 1
                continue
            elif not line or line in ['---', '']:
                # 保留空行和分隔符，但避免连续空行
                if cleaned_lines and cleaned_lines[-1].strip():
                    cleaned_lines.append(line)
                i += 1
                continue
            else:
                # 保留有价值的内容行
                cleaned_lines.append(lines[i])
                i += 1
        
        # 移除开头和结尾的空行
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        
        return '\n'.join(cleaned_lines)
    
    def save_markdown_content(self, url: str, markdown_content: str):
        """保存Markdown内容到文件（已清理反爬虫信息，带内容去重）"""
        try:
            # 清理反爬虫警告和无价值信息
            cleaned_content = self.clean_anti_crawler_content(markdown_content)
            
            # 计算内容哈希，用于去重
            import hashlib
            content_hash = hashlib.md5(cleaned_content.encode('utf-8')).hexdigest()
            
            # 检查是否已经保存过相同内容
            if not hasattr(self, 'content_hashes'):
                self.content_hashes = set()
            
            if content_hash in self.content_hashes:
                self.logger.info(f"跳过重复内容: {url} (内容哈希: {content_hash[:8]}...)")
                return
            
            # 检查内容是否过短（可能是无效页面）
            content_length = len(cleaned_content.strip())
            if content_length < 50:  # 降低阈值从100到50
                # 对于explore页面，添加特殊处理
                if '/explore/' in url:
                    self.logger.warning(f"EXPLORE页面内容过短: {url} (仅{content_length}字符) - 原始内容前200字符:")
                    # 输出原始内容的前200字符用于调试
                    raw_preview = (markdown_content[:200] + '...') if len(markdown_content) > 200 else markdown_content
                    self.logger.warning(f"原始内容预览: {raw_preview}")
                    # 对于explore页面，即使内容短也尝试保存
                    if content_length > 10:  # 至少要有10个字符
                        self.logger.info(f"强制保存EXPLORE页面: {url} (内容长度: {content_length})")
                    else:
                        self.logger.warning(f"EXPLORE页面内容过短，跳过: {url}")
                        return
                else:
                    self.logger.info(f"跳过内容过短的页面: {url} (仅{content_length}字符)")
                    return
                
            self.content_hashes.add(content_hash)
            
            filename = self.get_safe_filename(url)
            filepath = self.output_dir / "markdown" / filename
            
            # 添加元数据头部
            metadata = f"""---
url: {url}
crawled_at: {datetime.now().isoformat()}
filename: {filename}
content_hash: {content_hash}
---

"""
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(metadata + cleaned_content)
                
            # 显示清理效果
            original_lines = len(markdown_content.split('\n'))
            cleaned_lines = len(cleaned_content.split('\n'))
            reduction = original_lines - cleaned_lines
            
            self.logger.info(f"保存成功: {filename} ({len(cleaned_content)} 字符, 清理了{reduction}行无效内容)")
            
        except Exception as e:
            self.logger.error(f"保存失败 {url}: {e}")
            
    def get_browser_config(self) -> BrowserConfig:
        """获取增强的浏览器配置"""
        return BrowserConfig(
            browser_type="chromium",
            headless=False,  # 显示浏览器界面便于观察
            enable_stealth=True,  # 启用隐身模式
            verbose=True,  # 保持详细日志输出
            viewport_width=1920,
            viewport_height=1080,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Cache-Control": "max-age=0"
            },
            extra_args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-extensions",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--lang=zh-CN",
                "--accept-lang=zh-CN,zh;q=0.9,en;q=0.8"
            ]
        )
        
    def get_enhanced_js_bypass(self) -> str:
        """获取增强的JavaScript绕过代码"""
        return """
        // 综合反检测JavaScript代码 - 专门对抗OSRedm的浏览器检测
        (async () => {
            // 1. 覆盖webdriver检测
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // 2. 伪造浏览器特征
            Object.defineProperty(navigator, 'userAgent', {
                get: () => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                configurable: true
            });
            
            Object.defineProperty(navigator, 'appVersion', {
                get: () => '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                configurable: true
            });
            
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32',
                configurable: true
            });
            
            // 3. 伪造插件信息
            Object.defineProperty(navigator, 'processors', {
                get: () => [
                    {name: 'Chrome PDF Plugin', length: 1},
                    {name: 'Chrome PDF Viewer', length: 1},
                    {name: 'Native Client', length: 2}
                ],
                configurable: true
            });
            
            // 4. 伪造语言设置
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en'],
                configurable: true
            });
            
            Object.defineProperty(navigator, 'language', {
                get: () => 'zh-CN',
                configurable: true
            });
            
            // 5. 伪造硬件信息
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,
                configurable: true
            });
            
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8,
                configurable: true
            });
            
            // 6. 伪造屏幕信息
            Object.defineProperty(screen, 'width', {
                get: () => 1920,
                configurable: true
            });
            
            Object.defineProperty(screen, 'height', {
                get: () => 1080,
                configurable: true
            });
            
            // 7. 移除自动化痕迹
            delete navigator.__proto__.webdriver;
            delete window.navigator.__proto__.webdriver;
            delete Object.getPrototypeOf(navigator).webdriver;
            
            // 8. 伪造chrome对象（很多网站检测这个）
            if (!window.chrome) {
                window.chrome = {
                    runtime: {
                        onConnect: undefined,
                        onMessage: undefined
                    },
                    loadTimes: function() {
                        return {
                            commitLoadTime: Date.now() / 1000 - Math.random(),
                            finishDocumentLoadTime: Date.now() / 1000 - Math.random(),
                            finishLoadTime: Date.now() / 1000 - Math.random(),
                            firstPaintAfterLoadTime: Date.now() / 1000 - Math.random(),
                            firstPaintTime: Date.now() / 1000 - Math.random(),
                            navigationType: "Other",
                            requestTime: Date.now() / 1000 - Math.random(),
                            startLoadTime: Date.now() / 1000 - Math.random()
                        };
                    },
                    csi: function() {
                        return {
                            pageT: Date.now(),
                            startE: Date.now(),
                            tran: 15
                        };
                    }
                };
            }
            
            // 9. 伪造权限API
            if (navigator.permissions) {
                const originalQuery = navigator.permissions.query;
                navigator.permissions.query = function(parameters) {
                    return originalQuery.call(navigator.permissions, parameters).then(result => {
                        if (parameters.name === 'notifications') {
                            Object.defineProperty(result, 'state', {get: () => 'denied'});
                        }
                        return result;
                    });
                };
            }
            
            // 10. 模拟人类行为 - 添加随机鼠标移动
            const randomMouseMove = () => {
                const event = new MouseEvent('mousemove', {
                    clientX: Math.random() * window.innerWidth,
                    clientY: Math.random() * window.innerHeight,
                    bubbles: true
                });
                document.dispatchEvent(event);
            };
            
            // 随机触发鼠标移动
            setTimeout(randomMouseMove, Math.random() * 1000);
            setTimeout(randomMouseMove, 1000 + Math.random() * 1000);
            
            console.log('✅ 反检测脚本已执行完成');
        })();
        """
        
    def get_crawler_config(self) -> CrawlerRunConfig:
        """获取爬虫运行配置"""
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,  # 绕过缓存获取最新内容
            js_code=[self.get_enhanced_js_bypass()],
            simulate_user=True,
            magic=True,
            delay_before_return_html=3.0,  # 适中的延迟时间
            capture_console_messages=True,
            wait_for_images=False,  # 不等待图片加载以提高速度
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=PruningContentFilter(threshold=0.3)
            ),
            page_timeout=self.config["timeout"] * 1000,  # 使用配置中的超时时间(转换为毫秒)
            wait_until="networkidle",  # 等待网络空闲
        )
        
    def get_crawler_config_for_url(self, url: str, retry_count: int = 0) -> CrawlerRunConfig:
        """为特定URL获取爬虫运行配置"""
        dynamic_timeout = self.get_dynamic_timeout(url, retry_count)
        
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            js_code=[self.get_enhanced_js_bypass()],
            simulate_user=True,
            magic=True,
            delay_before_return_html=5.0 + retry_count * 2.0,  # 增加延迟时间
            capture_console_messages=True,
            wait_for_images=False,  # 不等待图片加载以提高速度
            markdown_generator=DefaultMarkdownGenerator(
                content_filter=PruningContentFilter(threshold=0.3)
            ),
            page_timeout=dynamic_timeout * 1000,  # 使用动态超时时间(转换为毫秒)
            wait_until="networkidle",  # 等待网络空闲
            session_id="osredm_session",  # 使用固定会话ID
        )
        
    async def crawl_single_url(self, url: str, crawler: AsyncWebCrawler, retry_count: int = 0) -> bool:
        """爬取单个URL - 增强版带重试机制和错误分类"""
        max_retries = 3
        
        # 首先检查URL是否适合爬取
        if not self.is_valid_crawl_url(url):
            self.logger.info(f"跳过非网页URL: {url}")
            self.failed_urls.add(url)
            return False
        
        try:
            self.logger.info(f"开始爬取: {url}" + (f" (重试 {retry_count})" if retry_count > 0 else ""))
            
            # 使用动态配置
            config = self.get_crawler_config_for_url(url, retry_count)
            
            result = await crawler.arun(url, config=config)
            
            if result.success and result.markdown:
                # 保存Markdown内容
                self.save_markdown_content(url, result.markdown.raw_markdown)
                
                # 提取新的URL
                if result.html:
                    new_urls = self.extract_urls_from_content(result.html, url)
                    before_count = len(self.discovered_urls)
                    self.discovered_urls.update(new_urls)
                    after_count = len(self.discovered_urls)
                    new_count = after_count - before_count
                    if new_count > 0:
                        self.logger.info(f"发现 {new_count} 个新URL (总计: {after_count})")
                
                self.completed_urls.add(url)
                self.progress.completed_urls += 1
                
                # 从失败列表中移除（如果之前失败过）
                self.failed_urls.discard(url)
                
                return True
                
            else:
                error_msg = result.error_message or "未知错误"
                
                # 特殊处理：下载文件错误
                if "Download is starting" in error_msg:
                    self.logger.info(f"跳过文件下载URL: {url}")
                    self.failed_urls.add(url)
                    return False
                
                # 特殊处理：403/404等不可恢复错误
                if result.status_code in [403, 404, 410]:
                    self.logger.info(f"跳过不可访问URL [{result.status_code}]: {url}")
                    self.failed_urls.add(url)
                    return False
                
                self.logger.warning(f"爬取失败: {url} - {error_msg}")
                
                # 如果还有重试机会，进行重试
                if retry_count < max_retries:
                    retry_delay = self.config["retry_delay"] * (retry_count + 1)  # 线性递增而不是指数
                    await asyncio.sleep(retry_delay)
                    return await self.crawl_single_url(url, crawler, retry_count + 1)
                else:
                    self.failed_urls.add(url)
                    self.progress.failed_urls += 1
                    return False
                
        except Exception as e:
            error_str = str(e)
            
            # 特殊处理：下载相关错误
            if "Download is starting" in error_str or "download" in error_str.lower():
                self.logger.info(f"跳过文件下载URL: {url}")
                self.failed_urls.add(url)
                return False
            
            # 特殊处理：网络相关错误
            if any(keyword in error_str.lower() for keyword in ['timeout', 'connection', 'network']):
                # 超时错误特殊处理
                if 'timeout' in error_str.lower():
                    current_timeout = self.get_dynamic_timeout(url, retry_count)
                    self.logger.warning(f"超时错误 {url} (当前超时: {current_timeout}s): {e}")
                    
                    # 对于探索页面，如果超时了且还有重试机会，再给一次长超时的机会
                    if '/explore/' in url and retry_count < max_retries:
                        self.logger.info(f"探索页面超时，将使用更长超时重试: {url}")
                else:
                    self.logger.warning(f"网络错误 {url}: {e}")
            else:
                self.logger.error(f"爬取异常 {url}: {e}")
            
            # 如果还有重试机会，进行重试
            if retry_count < max_retries:
                # 对于超时错误，增加更长的重试延迟
                if 'timeout' in error_str.lower():
                    retry_delay = self.config["retry_delay"] * (retry_count + 1) * 2  # 超时错误延迟更长
                else:
                    retry_delay = self.config["retry_delay"] * (retry_count + 1)  # 线性递增
                    
                await asyncio.sleep(retry_delay)
                return await self.crawl_single_url(url, crawler, retry_count + 1)
            else:
                self.failed_urls.add(url)
                self.progress.failed_urls += 1
                return False
            
    async def crawl_batch(self, urls: List[str], batch_size: int = 3):
        """分批爬取URLs"""
        adapter = UndetectedAdapter()
        browser_config = self.get_browser_config()
        
        # 创建爬虫策略
        strategy = AsyncPlaywrightCrawlerStrategy(
            browser_config=browser_config,
            browser_adapter=adapter
        )
        
        # 配置调度器 - 优化速度
        dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=80.0,
            check_interval=2.0,
            max_session_permit=batch_size,
            rate_limiter=RateLimiter(
                base_delay=(self.config["delay_between_requests"], self.config["delay_between_requests"] + 1),  # 使用配置的延迟
                max_delay=10.0,  # 减少最大延迟从30秒到10秒
                max_retries=3
            )
        )
        
        async with AsyncWebCrawler(
            crawler_strategy=strategy,
            config=browser_config
        ) as crawler:
            
            # 分批处理URLs
            for i in range(0, len(urls), batch_size):
                batch = urls[i:i+batch_size]
                self.logger.info(f"处理批次 {i//batch_size + 1}: {len(batch)} 个URL")
                
                # 串行处理以避免被检测
                for url in batch:
                    if url not in self.completed_urls and url not in self.failed_urls:
                        await self.crawl_single_url(url, crawler, retry_count=0)
                        
                        # 保存进度
                        self.save_progress()
                        
                        # 优化后的批次间延迟 - 减少等待时间
                        delay = self.config["delay_between_batches"]  # 使用配置文件中的固定延迟
                        self.logger.info(f"批次完成，等待 {delay} 秒...")
                        await asyncio.sleep(delay)
                        
    def is_valid_crawl_url(self, url: str) -> bool:
        """检查URL是否适合爬取（过滤文件下载、用户个人信息页面等）"""
        # 文件扩展名黑名单
        file_extensions = {
            # 图片文件
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico',
            # 文档文件  
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            # 压缩文件
            '.zip', '.rar', '.7z', '.tar', '.gz',
            # 音视频文件
            '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv',
            # 其他文件
            '.exe', '.msi', '.dmg', '.apk', '.css', '.js', '.xml', '.json'
        }
        
        # URL路径关键词黑名单
        path_blacklist = {
            '/images/', '/img/', '/assets/', '/static/', '/media/',
            '/download/', '/file/', '/attachment/', '/avatar/',
            '/thumbnail/', '/thumb/', '/cache/', '/temp/',
            '/api/', '/ajax/', '/json/', '/xml/', '/rss/'
        }
        
        # 用户个人信息页面关键词黑名单
        personal_page_keywords = {
            '/following', '/followers', '/organizes', '/statistics', 
            '/stargazers', '/watchers', '/projects', '/settings',
            '/profile', '/activity', '/contributions', '/stars'
        }
        
        # 项目开发细节页面关键词黑名单（避免爬取过度详细的开发信息）
        development_detail_keywords = {
            '/commits/', '/commit/', '/compare/', '/diff/', '/patch/',
            '/blame/', '/history/', '/tree/', '/blob/', '/raw/',
            '/archive/', '/releases/download/', '/zipball/', '/tarball/'
        }
        
        # 解析URL
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # 检查文件扩展名
        for ext in file_extensions:
            if path.endswith(ext):
                return False
                
        # 检查路径关键词
        for keyword in path_blacklist:
            if keyword in path:
                return False
        
        # 检查用户个人信息页面
        for keyword in personal_page_keywords:
            if keyword in path:
                return False
        
        # 检查项目开发细节页面（过滤具体的commit、diff、代码浏览等页面）
        for keyword in development_detail_keywords:
            if keyword in path:
                return False
        
        # 首先进行死循环检测
        if self._is_loop_url(url):
            return False
        
        # 过滤过度嵌套的page参数（防止死循环）
        if parsed.query:
            query_lower = parsed.query.lower()
            # 检查文件下载参数
            if any(param in query_lower for param in ['download', 'file', 'attachment']):
                return False
            
            # 检查page参数嵌套深度
            page_count = query_lower.count('page=')
            if page_count > 2:  # 超过2层page嵌套就过滤
                return False
        
        # 检查路径中的page嵌套（如 /page/5/page/53）
        page_segments = path.count('/page/')
        if page_segments > 2:  # 超过2层page路径就过滤
            return False
            
        # 过滤特定的重复项目模式（CPM-9G-8B相关）
        if 'cpm-9g-8b' in path.lower():
            # 如果是commits页面且有过多嵌套，则过滤
            if '/commits/' in path and ('/page/' in path and page_segments > 1):
                return False
                
        # 特殊处理：头像和图标URL模式
        if re.search(r'/(avatar|icon|logo|banner|thumb)', path):
            return False
            
        return True
        
    def get_next_batch_urls(self, batch_size: int = 10) -> List[str]:
        """获取下一批待爬取的URLs - 优先处理开源项目页面"""
        pending_urls = []
        high_priority_urls = []
        normal_priority_urls = []
        
        # 分类URL优先级
        for url in list(self.discovered_urls):
            if url not in self.completed_urls and url not in self.failed_urls:
                # 检查URL是否适合爬取
                if self.is_valid_crawl_url(url):
                    # 判断是否是高优先级URL（开源项目相关）
                    if self.is_high_priority_url(url):
                        high_priority_urls.append(url)
                    else:
                        normal_priority_urls.append(url)
                else:
                    # 将不适合爬取的URL标记为已完成，避免重复尝试
                    self.failed_urls.add(url)
                    self.logger.debug(f"跳过非网页URL: {url}")
        
        # 优先处理高优先级URL（开源项目）
        pending_urls.extend(high_priority_urls[:batch_size])
        
        # 如果高优先级URL不足，补充普通URL
        if len(pending_urls) < batch_size:
            remaining_slots = batch_size - len(pending_urls)
            pending_urls.extend(normal_priority_urls[:remaining_slots])
            
        return pending_urls
    
    def is_high_priority_url(self, url: str) -> bool:
        """判断是否是高优先级URL（开源项目相关）"""
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # 高优先级：探索页面
        if '/explore' in path:
            return True
            
        # 高优先级：项目主页模式 (如 /owner/project)
        path_parts = [p for p in path.split('/') if p]
        if len(path_parts) == 2:  # /user/project 格式
            # 排除个人信息页面
            if not any(personal in path for personal in ['/following', '/followers', '/organizes', '/statistics']):
                return True
        
        # 高优先级：项目相关页面
        if any(keyword in path for keyword in ['/issues', '/pulls', '/wiki', '/docs', '/readme']):
            return True
            
        return False
        
    async def start_crawling(self, max_pages: int = 500, batch_size: int = 3, max_rounds: int = 5):
        """开始全站爬取 - 增强版支持多轮深度爬取"""
        self.progress.start_time = datetime.now()
        self.logger.info(f"开始全站深度爬取 - 最大页面数: {max_pages}, 批次大小: {batch_size}, 最大轮次: {max_rounds}")
        
        # 如果没有发现的URL，从首页开始
        if not self.discovered_urls:
            self.discovered_urls.add(self.base_url)
            
        current_round = 1
        
        try:
            while current_round <= max_rounds:
                self.logger.info(f"\n🔄 === 第 {current_round} 轮爬取开始 ===")
                
                # 记录本轮开始前的状态
                round_start_completed = len(self.completed_urls)
                round_start_discovered = len(self.discovered_urls)
                
                while True:
                    # 获取下一批URL
                    batch_urls = self.get_next_batch_urls(batch_size)
                    
                    if not batch_urls:
                        self.logger.info(f"第 {current_round} 轮没有更多URL需要爬取")
                        break
                        
                    if len(self.completed_urls) >= max_pages:
                        self.logger.info(f"达到最大页面数限制: {max_pages}")
                        return
                        
                    self.progress.total_urls = len(self.discovered_urls)
                    self.logger.info(f"第 {current_round} 轮进度: {self.progress.get_progress_rate():.1f}% "
                                   f"({self.progress.completed_urls}/{self.progress.total_urls})")
                    
                    # 爬取当前批次
                    await self.crawl_batch(batch_urls, batch_size)
                    
                    # 每批次后保存进度
                    self.save_progress()
                
                # 统计本轮成果
                round_completed = len(self.completed_urls) - round_start_completed
                round_discovered = len(self.discovered_urls) - round_start_discovered
                
                self.logger.info(f"第 {current_round} 轮完成: 爬取了 {round_completed} 页面, 发现了 {round_discovered} 个新URL")
                
                # 如果本轮没有新发现，可能已经爬完
                if round_discovered == 0 and round_completed == 0:
                    self.logger.info("连续轮次无新发现，可能已完成全站爬取")
                    break
                
                # 轮次间休息 - 使用配置文件中的固定延迟
                if current_round < max_rounds:
                    rest_time = self.config["delay_between_rounds"]  # 使用配置中的固定延迟
                    self.logger.info(f"轮次间休息 {rest_time} 秒...")
                    await asyncio.sleep(rest_time)
                
                current_round += 1
                
        except KeyboardInterrupt:
            self.logger.info("用户中断爬取")
        except Exception as e:
            self.logger.error(f"爬取过程出错: {e}")
        finally:
            self.save_progress()
            self.print_final_stats()
            
    def print_final_stats(self):
        """打印最终统计信息"""
        elapsed = datetime.now() - self.progress.start_time if self.progress.start_time else None
        
        print(f"\n{'='*80}")
        print("爬取完成统计")
        print(f"{'='*80}")
        print(f"总发现URL数: {len(self.discovered_urls)}")
        print(f"成功爬取数: {len(self.completed_urls)}")
        print(f"失败URL数: {len(self.failed_urls)}")
        print(f"完成率: {self.progress.get_progress_rate():.1f}%")
        if elapsed:
            print(f"总耗时: {elapsed}")
        print(f"输出目录: {self.output_dir}")
        print(f"{'='*80}")


async def main():
    """主函数 - 启动OSRedm全站爬虫"""
    print("🚀 OSRedm 全站爬虫系统启动")
    print("=" * 60)
    
    try:
        # 检查浏览器环境
        await check_browser_environment()
        
        # 创建爬虫实例
        crawler = OSRedmCrawler(
            base_url="https://www.osredm.com/",
            output_dir=r"D:\HuaweiMoveData\Users\21438\Desktop\红山网络怕爬虫"
        )
        
        # 开始爬取 (从配置文件读取参数)
        from config import CRAWL_CONFIG
        await crawler.start_crawling(
            max_pages=CRAWL_CONFIG['max_pages'],     # 从配置读取最大页面数
            batch_size=CRAWL_CONFIG['batch_size'],   # 从配置读取批次大小
            max_rounds=CRAWL_CONFIG['max_rounds']    # 从配置读取最大轮次
        )
        
    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
        print("\n💡 常见解决方案:")
        print("1. 运行 fix_browser.bat 修复浏览器")
        print("2. 运行 install_requirements.bat 重新安装依赖")
        print("3. 检查网络连接是否正常")
        input("\n按回车键退出...")


async def check_browser_environment():
    """检查浏览器环境（异步版本）"""
    try:
        import playwright
        print("✅ Playwright 库已安装")
        
        # 检查浏览器是否可用（使用异步API）
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            # 尝试启动浏览器
            browser = await p.chromium.launch(headless=True)
            await browser.close()
            print("✅ Chromium 浏览器可用")
            
    except ImportError:
        raise Exception("Playwright 库未安装，请运行 install_requirements.bat")
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            raise Exception("Playwright 浏览器未安装，请运行 fix_browser.bat")
        else:
            raise Exception(f"浏览器环境检查失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
