import os
import time
import traceback
from pathlib import Path

from src import config
from src.utils import logger


async def convert_url_to_pdf_with_ilovepdf(url: str) -> str | None:
    """
    使用 iLovePDF API 将 URL 转换为 PDF

    Args:
        url: 要转换的URL地址

    Returns:
        PDF文件路径，如果失败返回None
    """
    import requests
    import jwt
    import hashlib

    # 从环境变量获取 iLovePDF API 密钥
    public_key = os.getenv("ILOVEPDF_PUBLIC_KEY")
    secret_key = os.getenv("ILOVEPDF_SECRET_KEY")

    if not public_key or not secret_key:
        logger.warning("iLovePDF API credentials not configured. Falling back to simple HTML parsing.")
        return None

    try:
        api_base = "https://api.ilovepdf.com/v1"
        
        # 1. 获取认证token（优先使用/auth端点，更可靠）
        # 根据iLovePDF API文档，推荐使用/auth端点获取token
        try:
            auth_response = requests.post(
                f"{api_base}/auth",
                json={"public_key": public_key},
                timeout=30,
            )
            if auth_response.status_code == 200:
                auth_data = auth_response.json()
                token = auth_data["token"]
                logger.debug("Successfully obtained token from /auth endpoint")
                # 检查是否有剩余额度信息
                if "remaining_credits" in auth_data:
                    logger.debug(f"Remaining credits: {auth_data['remaining_credits']}")
            else:
                # 如果/auth失败，尝试自签名方式
                logger.warning(f"/auth endpoint failed ({auth_response.status_code}): {auth_response.text}")
                raise ValueError("Auth endpoint failed")
        except Exception as e:
            # 回退到自签名方式
            logger.debug(f"Using self-signed token: {e}")
            now = int(time.time())
            payload = {
                "iss": public_key,  # issuer必须是public_key
                "exp": now + 7200,  # 2小时过期
                "nbf": now,  # not before
                "iat": now,  # issued at
            }
            token = jwt.encode(payload, secret_key, algorithm="HS256")
        
        headers = {"Authorization": f"Bearer {token}"}

        # 2. 开始任务
        # 根据Postman collection，Start端点使用GET方法，且可能不需要region参数
        # URL格式：https://api.ilovepdf.com/v1/start/{tool}
        # 如果需要region，格式为：https://api.ilovepdf.com/v1/start/{tool}/{region}
        region = os.getenv("ILOVEPDF_REGION", "eu")
        
        # 先尝试不带region（根据Postman collection的标准格式）
        start_url = f"{api_base}/start/htmlpdf"
        
        logger.debug(f"Starting iLovePDF task: {start_url} (public_key: {public_key[:8]}...)")
        start_response = requests.get(  # 使用GET方法，不是POST！
            start_url,
            headers=headers,
            timeout=30,
        )
        
        # 记录响应状态和内容用于调试
        logger.debug(f"Start response status: {start_response.status_code}, body: {start_response.text[:200]}")
        
        # 如果返回404且指定了region，尝试不带region
        if start_response.status_code == 404 and region != "eu":
            logger.debug(f"Trying without region parameter")
            start_response = requests.get(
                start_url,
                headers=headers,
                timeout=30,
            )
        
        # 如果仍然404，尝试带region参数
        if start_response.status_code == 404:
            start_url_with_region = f"{api_base}/start/htmlpdf/{region}"
            logger.debug(f"Trying with region parameter: {start_url_with_region}")
            start_response = requests.get(
                start_url_with_region,
                headers=headers,
                timeout=30,
            )
        
        # 如果返回401，说明认证失败
        if start_response.status_code == 401:
            error_detail = start_response.text
            logger.error(f"iLovePDF API authentication failed (401): {error_detail}")
            raise ValueError(
                f"iLovePDF API authentication failed. "
                f"Please check your ILOVEPDF_PUBLIC_KEY and ILOVEPDF_SECRET_KEY are correct. "
                f"Response: {error_detail}"
            )
        
        # 如果返回404，可能是端点不存在或工具不可用
        if start_response.status_code == 404:
            error_detail = start_response.text
            logger.error(f"Failed to start htmlpdf task (404): {error_detail}")
            
            # 先尝试一个简单的工具（如compress）来验证API是否正常工作
            test_url = f"{api_base}/start/compress"
            test_response = requests.get(test_url, headers=headers, timeout=10)
            logger.debug(f"Test compress tool response: {test_response.status_code}, body: {test_response.text[:200]}")
            if test_response.status_code != 404:
                logger.warning(f"Other tools work (compress returned {test_response.status_code}), htmlpdf may not be available in your plan")
            else:
                logger.warning(
                    f"All tools return 404. This suggests: "
                    f"1) API credentials may not have access to PDF tools, "
                    f"2) Account may need activation, "
                    f"3) API keys may be from Image API only (not PDF API). "
                    f"Please check your iLovePDF developer dashboard."
                )
            
            # 返回None而不是抛出异常，让代码回退到简单HTML解析
            logger.error(
                f"iLovePDF API endpoint not found (404). "
                f"This may mean: "
                f"1) htmlpdf tool is not available in your plan, "
                f"2) API credentials are incorrect, "
                f"3) The tool name or endpoint format has changed. "
                f"Falling back to simple HTML parsing."
            )
            return None  # 返回None，让调用者使用回退方案
        
        start_response.raise_for_status()
        start_data = start_response.json()
        server = start_data["server"]
        task = start_data["task"]

        # 3. 上传URL（htmlpdf工具支持通过cloud_file参数直接传入URL，由服务器端处理）
        # 根据iLovePDF API文档，Upload步骤支持cloud_file参数传入公共URL
        upload_url = f"https://{server}/v1/upload"
        upload_data = {
            "task": task,
            "cloud_file": url,  # 直接传入URL，服务器端会处理
        }
        upload_response = requests.post(
            upload_url,
            headers=headers,
            json=upload_data,  # 使用JSON格式，因为cloud_file是JSON参数
            timeout=60,
        )
        upload_response.raise_for_status()
        upload_result = upload_response.json()
        server_filename = upload_result["server_filename"]

        # 4. 处理URL转PDF
        # 根据Postman collection，files数组需要包含server_filename和filename
        process_url = f"https://{server}/v1/process"
        process_payload = {
            "task": task,
            "tool": "htmlpdf",
            "files": [
                {
                    "server_filename": server_filename,
                    "filename": "server.pdf"  # 原始文件名，必需字段
                }
            ],
            # 可选参数
            "page_orientation": "portrait",  # 或 "landscape"
            "page_size": "A4",  # 或 "A3", "Letter", "Fit", "Auto"
            "page_margin": 0,  # 页面边距（像素）
            "view_width": 1980,  # 视口宽度（像素）
            "single_page": False,  # 是否单页输出
        }
        
        logger.debug(f"Processing task: {process_url}, payload: {process_payload}")
        process_response = requests.post(
            process_url,
            headers=headers,
            json=process_payload,
            timeout=300,  # 5分钟超时
        )
        
        # 如果返回错误，记录详细信息
        if process_response.status_code != 200:
            error_detail = process_response.text
            logger.error(f"Process failed ({process_response.status_code}): {error_detail}")
            logger.debug(f"Request payload was: {process_payload}")
        
        process_response.raise_for_status()

        # 5. 下载PDF
        download_url = f"https://{server}/v1/download/{task}"
        download_response = requests.get(download_url, headers=headers, timeout=60)
        download_response.raise_for_status()

        # 6. 保存PDF到临时文件
        pdf_content = download_response.content
        temp_dir = Path(config.save_dir) / "temp" / "url_pdfs"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # 使用URL的hash作为文件名的一部分
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        pdf_path = temp_dir / f"webpage_{url_hash}_{int(time.time())}.pdf"

        with open(pdf_path, "wb") as f:
            f.write(pdf_content)

        logger.info(f"Successfully converted URL to PDF using iLovePDF: {url} -> {pdf_path}")
        return str(pdf_path)

    except Exception as e:
        logger.error(f"Failed to convert URL to PDF using iLovePDF API: {e}")
        logger.debug(traceback.format_exc())
        return None


async def process_url_to_markdown(url: str, params: dict | None = None, target_pdf_path: str | None = None) -> tuple[str, str | None]:
    """
    将URL转换为markdown格式
    优先使用 iLovePDF API 将 HTML 转为 PDF，然后使用现有的 PDF 处理流程

    Args:
        url: URL地址
        params: 处理参数（包含 enable_ocr 等OCR配置）
        target_pdf_path: 如果提供，PDF文件将被保存到此路径（用于知识库存储）

    Returns:
        tuple: (markdown格式内容, PDF文件路径或None)
    """
    # 延迟导入以避免循环导入
    from .indexing import process_file_to_markdown
    
    # 尝试使用 iLovePDF API 将 URL 转为 PDF
    pdf_path = await convert_url_to_pdf_with_ilovepdf(url)

    if pdf_path:
        try:
            # 如果指定了目标路径，将PDF移动到目标位置（用于知识库存储）
            final_pdf_path = pdf_path
            if target_pdf_path:
                import shutil
                target_dir = os.path.dirname(target_pdf_path)
                os.makedirs(target_dir, exist_ok=True)
                shutil.move(pdf_path, target_pdf_path)
                final_pdf_path = target_pdf_path
                logger.debug(f"Moved PDF from {pdf_path} to {target_pdf_path}")
                
                # 可视化文件也会跟随PDF文件移动（如果有的话）
                visualization_path = pdf_path + ".visualization.json"
                if os.path.exists(visualization_path):
                    target_visualization_path = target_pdf_path + ".visualization.json"
                    shutil.move(visualization_path, target_visualization_path)
                    logger.debug(f"Moved visualization file to {target_visualization_path}")
            
            # 使用现有的 PDF 处理流程（支持OCR等模式）
            markdown_content = await process_file_to_markdown(final_pdf_path, params=params)
            # 在标题中添加URL信息
            return (f"# {url}\n\n{markdown_content}", final_pdf_path if target_pdf_path else None)
        except Exception as e:
            logger.error(f"Failed to process PDF from URL {url}: {e}")
            # 如果PDF处理失败，尝试回退到简单HTML解析
            # 清理PDF文件（如果还在临时目录）
            if not target_pdf_path and pdf_path and os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                    # 也清理可视化文件
                    vis_path = pdf_path + ".visualization.json"
                    if os.path.exists(vis_path):
                        os.remove(vis_path)
                except Exception:
                    pass

    # 回退方案：使用 crawl4ai 进行高级网页爬取
    from .web_crawler import crawl_url

    try:
        logger.debug(f"使用 crawl4ai 爬取网页: {url}")
        markdown_content = await crawl_url(url, timeout=60)
        
        if markdown_content:
            # 在标题中添加 URL 信息
            return (f"# {url}\n\n{markdown_content}", None)
        else:
            logger.warning(f"crawl4ai 爬取失败，返回错误信息: {url}")
            return (f"# {url}\n\nFailed to process URL: 网页爬取失败，可能网站需要 JavaScript 渲染或存在反爬虫保护", None)
    except Exception as e:
        logger.error(f"Failed to process URL {url}: {e}")
        return (f"# {url}\n\nFailed to process URL: {e}", None)

