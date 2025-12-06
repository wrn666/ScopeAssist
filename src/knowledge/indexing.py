import asyncio
import os
import tempfile
import time
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    CSVLoader,
    Docx2txtLoader,
    JSONLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
)

from src import config
from src.utils import logger


def chunk_with_parser(file_path, params=None):
    """
    使用文件解析器将文件切分成固定大小的块

    Args:
        file_path: 文件路径
        params: 参数
    """
    params = params or {}
    chunk_size = int(params.get("chunk_size", 500))
    chunk_overlap = int(params.get("chunk_overlap", 100))

    file_type = Path(file_path).suffix.lower()

    # 选择合适的加载器
    if file_type in [".txt"]:
        loader = TextLoader(file_path)

    elif file_type in [".md"]:
        loader = UnstructuredMarkdownLoader(file_path)

    elif file_type in [".docx", ".doc"]:
        loader = Docx2txtLoader(file_path)

    elif file_type in [".html", ".htm"]:
        loader = UnstructuredHTMLLoader(file_path)

    elif file_type in [".json"]:
        loader = JSONLoader(file_path, jq_schema=".")

    elif file_type in [".csv"]:
        loader = CSVLoader(file_path)

    else:
        raise ValueError(f"不支持的文件类型: {file_type}")

    # 加载文档
    docs = loader.load()

    # 创建文本分割器
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    # 分割文档
    nodes = text_splitter.split_documents(docs)

    # 添加序号信息到metadata
    for i, node in enumerate(nodes):
        if node.metadata is None:
            node.metadata = {}
        node.metadata["chunk_idx"] = i

    return nodes


def chunk_text(text, params=None):
    """
    将文本切分成固定大小的块
    """
    params = params or {}
    chunk_size = int(params.get("chunk_size", 500))
    chunk_overlap = int(params.get("chunk_overlap", 100))

    # 创建文本分割器
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, separators=["\n\n", "\n", ".", " ", ""]
    )

    # 分割文档
    nodes = text_splitter.split_text(text)

    # 添加序号信息到metadata
    nodes = [{"text": node, "metadata": {"chunk_idx": i}} for i, node in enumerate(nodes)]
    return nodes


def chunk(text_or_path, params=None):
    raise NotImplementedError("chunk is deprecated, use chunk_with_parser or chunk_text instead")


def pdfreader(file_path, params=None):
    """读取PDF文件并返回text文本"""
    if isinstance(file_path, str):
        file_path = Path(file_path)

    assert file_path.exists(), "File not found"
    assert file_path.suffix.lower() == ".pdf", "File format not supported"

    # 使用LangChain的PDF加载器
    loader = PyPDFLoader(str(file_path))
    docs = loader.load()

    # 简单的拼接起来之后返回纯文本
    text = "\n\n".join([d.page_content for d in docs])
    return text


def plainreader(file_path):
    """读取普通文本文件并返回text文本"""
    assert os.path.exists(file_path), "File not found"

    # 使用LangChain的文本加载器
    loader = TextLoader(str(file_path))
    docs = loader.load()
    text = "\n\n".join([d.page_content for d in docs])
    return text


def parse_pdf(file, params=None):
    """
    解析PDF文件，支持多种OCR方式

    Args:
        file: PDF文件路径
        params: 参数字典，包含enable_ocr设置

    Returns:
        str: 解析得到的文本

    Raises:
        OCRServiceException: OCR服务不可用时抛出
    """
    from src.processors._ocr import OCRServiceException

    params = params or {}
    opt_ocr = params.get("enable_ocr", "disable")
    logger.debug(f"开始解析 PDF 文件: {file}, OCR 模式: {opt_ocr}")

    if opt_ocr == "disable":
        logger.debug(f"OCR 已禁用，使用标准 PDF 读取器: {file}")
        result = pdfreader(file, params=params)
        logger.debug(f"PDF 读取完成，文本长度: {len(result)} 字符")
        return result

    try:
        if opt_ocr == "mineru_ocr":
            logger.debug(f"使用 mineru_ocr 处理 PDF: {file}")
            from src.processors import ocr

            result = ocr.process_file_mineru(file, params=params)
            logger.debug(f"mineru_ocr 处理完成，文本长度: {len(result)} 字符")
            return result

        elif opt_ocr == "mineru_cloud":
            logger.debug(f"使用 mineru_cloud 处理 PDF: {file}")
            from src.processors import ocr

            result = ocr.process_file_mineru_cloud(file, params=params)
            logger.debug(f"mineru_cloud 处理完成，文本长度: {len(result)} 字符")
            return result

        elif opt_ocr == "paddlex_ocr":
            logger.debug(f"使用 paddlex_ocr 处理 PDF: {file}")
            from src.processors import ocr

            result = ocr.process_file_paddlex(file, params=params)
            logger.debug(f"paddlex_ocr 处理完成，文本长度: {len(result)} 字符")
            return result

        elif opt_ocr == "unstructured":
            logger.debug(f"使用 unstructured 处理 PDF: {file}")
            from src.processors import ocr
            
            # Unstructured 自动启用元数据保存以生成可视化
            unstructured_params = params.copy() if params else {}
            unstructured_params["save_metadata"] = True

            result = ocr.process_file_unstructured(file, params=unstructured_params)
            logger.debug(f"unstructured 处理完成，文本长度: {len(result)} 字符")
            return result

        else:
            raise ValueError(f"不支持的OCR方式: {opt_ocr}")

    except OCRServiceException as e:
        logger.error(f"OCR service failed: {e.service_name} - {str(e)}")
        raise
    except Exception as e:
        logger.error(f"PDF parsing failed: {str(e)}")
        raise OCRServiceException(f"PDF解析失败: {str(e)}", opt_ocr, "parsing_failed")


def parse_image(file, params=None):
    """
    解析图像文件，支持多种OCR方式
    """
    from src.processors._ocr import OCRServiceException

    params = params or {}
    opt_ocr = params.get("enable_ocr", "disable")
    logger.debug(f"开始解析图片文件: {file}, OCR 模式: {opt_ocr}")

    if opt_ocr == "disable":
        raise ValueError(f"图片文件必须启用OCR处理: {file}。请选择 mineru_ocr、mineru_cloud、paddlex_ocr 或 unstructured 之一")

    try:
        if opt_ocr == "mineru_ocr":
            logger.debug(f"使用 mineru_ocr 处理图片: {file}")
            from src.processors import ocr

            result = ocr.process_file_mineru(file, params=params)
            logger.debug(f"mineru_ocr 处理完成，文本长度: {len(result)} 字符")
            return result

        elif opt_ocr == "mineru_cloud":
            logger.debug(f"使用 mineru_cloud 处理图片: {file}")
            from src.processors import ocr

            result = ocr.process_file_mineru_cloud(file, params=params)
            logger.debug(f"mineru_cloud 处理完成，文本长度: {len(result)} 字符")
            return result

        elif opt_ocr == "paddlex_ocr":
            logger.debug(f"使用 paddlex_ocr 处理图片: {file}")
            from src.processors import ocr

            result = ocr.process_file_paddlex(file, params=params)
            logger.debug(f"paddlex_ocr 处理完成，文本长度: {len(result)} 字符")
            return result

        elif opt_ocr == "unstructured":
            logger.debug(f"使用 unstructured 处理图片: {file}")
            from src.processors import ocr
            
            # Unstructured 自动启用元数据保存以生成可视化
            unstructured_params = params.copy() if params else {}
            unstructured_params["save_metadata"] = True

            result = ocr.process_file_unstructured(file, params=unstructured_params)
            logger.debug(f"unstructured 处理完成，文本长度: {len(result)} 字符")
            return result

        else:
            raise ValueError(f"不支持的OCR方式: {opt_ocr}")

    except OCRServiceException as e:
        logger.error(f"OCR service failed: {e.service_name} - {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Image parsing failed: {str(e)}")
        raise OCRServiceException(f"Image解析失败: {str(e)}", opt_ocr, "parsing_failed")


async def parse_pdf_async(file, params=None):
    return await asyncio.to_thread(parse_pdf, file, params=params)


async def parse_image_async(file, params=None):
    return await asyncio.to_thread(parse_image, file, params=params)


async def process_file_to_markdown(file_path: str, params: dict | None = None) -> str:
    """
    将不同类型的文件转换为markdown格式

    Args:
        file_path: 文件路径
        params: 处理参数

    Returns:
        markdown格式内容
    """
    file_path_obj = Path(file_path)
    file_ext = file_path_obj.suffix.lower()
    logger.debug(f"开始处理文件到 Markdown: {file_path}, 文件类型: {file_ext}")

    if file_ext == ".pdf":
        # 使用 OCR 处理 PDF
        logger.debug(f"检测到 PDF 文件，开始使用 OCR 处理: {file_path}")
        text = await parse_pdf_async(str(file_path_obj), params=params)
        logger.debug(f"PDF 处理完成，文本长度: {len(text)} 字符")
        return f"# {file_path_obj.name}\n\n{text}"

    elif file_ext in [".txt", ".md"]:
        # 直接读取文本文件
        logger.debug(f"检测到文本文件，开始读取: {file_path}")
        with open(file_path_obj, encoding="utf-8") as f:
            content = f.read()
        logger.debug(f"文本文件读取完成，内容长度: {len(content)} 字符")
        return f"# {file_path_obj.name}\n\n{content}"

    elif file_ext in [".doc", ".docx"]:
        # 处理 Word 文档
        logger.debug(f"检测到 Word 文档，开始处理: {file_path}")
        from docx import Document  # type: ignore

        doc = Document(file_path_obj)
        text = "\n".join([para.text for para in doc.paragraphs])
        logger.debug(f"Word 文档处理完成，文本长度: {len(text)} 字符")
        return f"# {file_path_obj.name}\n\n{text}"

    elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
        # 使用 OCR 处理图片
        logger.debug(f"检测到图片文件，开始使用 OCR 处理: {file_path}")
        text = await parse_image_async(str(file_path_obj), params=params)
        logger.debug(f"图片 OCR 处理完成，文本长度: {len(text)} 字符")
        return f"# {file_path_obj.name}\n\n{text}"

    elif file_ext in [".html", ".htm"]:
        # 使用 BeautifulSoup 处理 HTML 文件
        from markdownify import markdownify as md

        with open(file_path_obj, encoding="utf-8") as f:
            content = f.read()
        text = md(content, heading_style="ATX")
        return f"# {file_path_obj.name}\n\n{text}"

    elif file_ext == ".csv":
        # 处理 CSV 文件
        import pandas as pd

        df = pd.read_csv(file_path_obj)
        # 将每一行数据与表头组合成独立的表格
        markdown_content = f"# {file_path_obj.name}\n\n"

        for index, row in df.iterrows():
            # 创建包含表头和当前行的小表格
            row_df = pd.DataFrame([row], columns=df.columns)
            markdown_table = row_df.to_markdown(index=False)
            markdown_content += f"{markdown_table}\n\n"

        return markdown_content.strip()

    elif file_ext in [".xls", ".xlsx"]:
        # 处理 Excel 文件
        import pandas as pd

        # 读取所有工作表
        excel_file = pd.ExcelFile(file_path_obj)
        markdown_content = f"# {file_path_obj.name}\n\n"

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path_obj, sheet_name=sheet_name)
            markdown_content += f"## {sheet_name}\n\n"

            # 将每一行数据与表头组合成独立的表格
            for index, row in df.iterrows():
                # 创建包含表头和当前行的小表格
                row_df = pd.DataFrame([row], columns=df.columns)
                markdown_table = row_df.to_markdown(index=False)
                markdown_content += f"{markdown_table}\n\n"

        return markdown_content.strip()

    elif file_ext == ".json":
        # 处理 JSON 文件
        import json

        with open(file_path_obj, encoding="utf-8") as f:
            data = json.load(f)
        # 将 JSON 数据格式化为 markdown 代码块
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        return f"# {file_path_obj.name}\n\n```json\n{json_str}\n```"

    else:
        # 尝试作为文本文件读取
        raise ValueError(f"Unsupported file type: {file_ext}")


# 从 url_processor 模块导入 URL 处理函数（保持向后兼容）
from .url_processor import convert_url_to_pdf_with_ilovepdf, process_url_to_markdown
