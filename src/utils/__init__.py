import hashlib
import os
import time

from src.utils.logging_config import logger


def is_text_pdf(pdf_path):
    import fitz

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    if total_pages == 0:
        return False

    text_pages = 0
    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        text = page.get_text()
        if text.strip():  # 检查是否有文本内容
            text_pages += 1

    # 计算有文本内容的页面比例
    text_ratio = text_pages / total_pages
    # 如果超过50%的页面有文本内容，则认为是文本PDF
    return text_ratio > 0.5


def hashstr(input_string, length=None, with_salt=False):
    """生成字符串的哈希值
    Args:
        input_string: 输入字符串
        length: 截取长度，默认为None，表示不截取
        with_salt: 是否加盐，默认为False
    """
    try:
        # 尝试直接编码
        encoded_string = str(input_string).encode("utf-8")
    except UnicodeEncodeError:
        # 如果编码失败，替换无效字符
        encoded_string = str(input_string).encode("utf-8", errors="replace")

    if with_salt:
        salt = str(time.time())
        encoded_string = (encoded_string.decode("utf-8") + salt).encode("utf-8")

    hash = hashlib.md5(encoded_string).hexdigest()
    if length:
        return hash[:length]
    return hash


def get_docker_safe_url(base_url):
    if not base_url:
        return base_url

    if os.getenv("RUNNING_IN_DOCKER") == "true":
        # 替换所有可能的本地地址形式
        base_url = base_url.replace("http://localhost", "http://host.docker.internal")
        base_url = base_url.replace("http://127.0.0.1", "http://host.docker.internal")
        logger.info(f"Running in docker, using {base_url} as base url")
    return base_url


def url_to_filename(url: str, max_length: int = 200, extension: str = ".pdf") -> str:
    """
    将URL转换为安全的文件名
    
    Args:
        url: 要转换的URL
        max_length: 文件名最大长度（不包括扩展名）
        extension: 文件扩展名，默认为".pdf"
    
    Returns:
        str: 安全的文件名
    """
    import re
    from urllib.parse import urlparse
    
    # 移除协议前缀（http://, https://）
    url_without_protocol = re.sub(r'^https?://', '', url)
    
    # 替换文件系统不支持的字符
    # 替换 /, ?, &, =, #, %, +, :, *, ", ', <, >, |, \ 等特殊字符为下划线
    safe_name = re.sub(r'[<>:"/\\|?*&#%+=]', '_', url_without_protocol)
    
    # 移除连续的下划线
    safe_name = re.sub(r'_+', '_', safe_name)
    
    # 移除开头和结尾的下划线
    safe_name = safe_name.strip('_')
    
    # 如果文件名太长，截断并保留末尾部分（通常URL末尾包含更多信息）
    if len(safe_name) > max_length:
        safe_name = safe_name[-max_length:]
        # 如果截断后以_开头，移除它
        safe_name = safe_name.lstrip('_')
    
    # 如果文件名为空（不应该发生），使用默认名称
    if not safe_name:
        safe_name = "url"
    
    # 添加扩展名
    return safe_name + extension
