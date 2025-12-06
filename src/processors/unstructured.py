import os
import time
import traceback
import base64
import json
import io

import fitz
import matplotlib.patches as patches
import matplotlib.pyplot as plt
from PIL import Image as PILImage

from src.utils import logger
from src.models.chat import select_model
from ._ocr import OCRServiceException, log_ocr_request


class UnstructuredProcessor:
    """Unstructured 文档处理器"""

    def __init__(self):
        pass

    def _format_markdown_with_llm(self, markdown_text: str, params: dict = None) -> str:
        """
        使用 LLM 整理和规范化 Markdown 格式
        
        :param markdown_text: 原始 Markdown 文本
        :param params: 参数（可包含 format_with_llm=False 禁用，llm_provider 和 llm_model 指定模型）
        :return: 整理后的 Markdown 文本
        """
        # 检查是否启用 LLM 格式化
        format_with_llm = params.get("format_with_llm", True) if params else True
        if not format_with_llm:
            logger.debug("[Unstructured] LLM 格式化已禁用，跳过格式整理")
            return markdown_text
        
        logger.debug(f"[Unstructured] 开始使用 LLM 整理 Markdown 格式，原始文本长度: {len(markdown_text)} 字符")
        
        # 检查文本长度，如果太长则跳过格式化（避免超出token限制）
        max_length = params.get("llm_format_max_length", 50000) if params else 50000
        if len(markdown_text) > max_length:
            logger.warning(f"[Unstructured] 文本长度 ({len(markdown_text)} 字符) 超过最大限制 ({max_length} 字符)，跳过 LLM 格式化")
            return markdown_text
        
        try:
            # 获取 LLM 配置
            llm_provider = params.get("llm_provider", "dashscope") if params else "dashscope"
            llm_model = params.get("llm_model", "deepseek-v3.2-exp") if params else "qwen-plus-latest"
            
            logger.debug(f"[Unstructured] 使用 LLM 模型: {llm_provider}/{llm_model}")
            
            # 加载模型
            try:
                model = select_model(llm_provider, llm_model)
                logger.debug(f"[Unstructured] LLM 模型加载成功")
            except Exception as e:
                logger.warning(f"[Unstructured] 加载 LLM 模型失败 ({llm_provider}/{llm_model}): {str(e)}，跳过格式整理")
                logger.debug(f"[Unstructured] LLM 模型加载异常详情: {traceback.format_exc()}")
                return markdown_text
            
            # 构建提示词
            system_prompt = """你是一个专业的文档格式整理专家。请将给定的 Markdown 文档整理成标准、规范的 Markdown 格式。

要求：
1. 保持文档的原始内容和结构不变
2. 规范化标题层级（确保标题层级合理，使用 #、##、### 等）
3. 规范化列表格式（统一使用 - 或 1. 格式）
4. 规范化表格格式（确保表格对齐正确）
5. 规范化代码块格式（确保代码块有正确的语言标识）
6. 规范化段落间距（段落之间使用适当的空行分隔）
7. 保持图片描述和链接格式不变
8. 确保所有 Markdown 语法正确

请直接返回整理后的 Markdown 文档，不要添加任何额外的说明或注释。"""

            user_prompt = f"""请整理以下 Markdown 文档：

```markdown
{markdown_text}
```"""

            # 调用 LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            logger.debug(f"[Unstructured] 开始调用 LLM 进行格式整理")
            start_time = time.time()
            
            response = model.call(messages, stream=False)
            formatted_text = response.content.strip()
            
            # 移除可能的代码块标记（如果 LLM 返回了代码块格式）
            if formatted_text.startswith("```markdown"):
                formatted_text = formatted_text.replace("```markdown", "").replace("```", "").strip()
            elif formatted_text.startswith("```"):
                formatted_text = formatted_text.replace("```", "").strip()
            
            format_time = time.time() - start_time
            logger.info(f"[Unstructured] LLM 格式整理完成，耗时: {format_time:.2f} 秒，整理后文本长度: {len(formatted_text)} 字符")
            logger.debug(f"[Unstructured] LLM 格式整理完成")
            
            return formatted_text
            
        except Exception as e:
            logger.warning(f"[Unstructured] LLM 格式整理失败: {str(e)}，返回原始文本")
            logger.debug(f"[Unstructured] LLM 格式整理异常详情: {traceback.format_exc()}")
            return markdown_text

    def _analyze_image_with_vlm(self, image_data_uri: str) -> str:
        """
        使用 VLM 模型分析图片内容，判断是否有实质性内容
        
        :param image_data_uri: 图片的 data URI (base64 编码)
        :return: 如果有实质性内容返回描述文本，否则返回空字符串
        """
        logger.debug(f"[VLM] 开始分析图片内容，data URI 长度: {len(image_data_uri)} 字符")
        try:
            from src.models.chat import select_model
            
            # 使用 dashscope 的 qwen-vl-max 视觉模型
            provider = "dashscope"
            model_name = "qwen-vl-max-2025-04-02"
            
            # 加载 VL 模型
            try:
                logger.debug(f"[VLM] 选择模型: {provider}/{model_name}")
                vlm = select_model(provider, model_name)
                logger.debug(f"[VLM] 模型加载成功")
            except Exception as e:
                logger.warning(f"加载 VL 模型失败 ({provider}/{model_name}): {str(e)}，跳过图片分析")
                logger.debug(f"[VLM] 模型加载异常详情: {traceback.format_exc()}")
                return ""
            
            # 构建多模态消息
            prompt = """请分析这张图片的内容。如果图片包含以下任何一种实质性内容，请回答"是"并简要描述图片内容：
                    - 有意义的文字、表格、图表
                    - 重要的照片、插图、示意图
                    - 具有参考价值的视觉信息

                    如果图片只是装饰性元素、背景、分隔线、空白区域或无实质内容，请只回答"否"。

                    请按以下格式回答：
                    判断: [是/否]
                    描述: [如果是"是"，请用一句话描述图片主要内容；如果是"否"，留空]"""
            
            # 构建多模态消息（OpenAI 格式）
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_uri}}
                    ]
                }
            ]
            
            # 调用 VLM 进行分析
            try:
                logger.debug(f"[VLM] 开始调用 VLM API")
                response = vlm.call(messages, stream=False)
                logger.debug(f"[VLM] VLM API 调用完成，开始解析响应")
                content = response.content.strip()
                logger.debug(f"[VLM] VLM 响应内容长度: {len(content)} 字符")
                
                # 解析 VLM 回复（格式：判断: 是/否\n描述: xxx）
                lines = content.split('\n')
                judgment = ""
                description = ""
                
                for line in lines:
                    if line.startswith("判断:") or line.startswith("判断："):
                        judgment = line.split(':', 1)[1].strip() if ':' in line else line.split('：', 1)[1].strip()
                    elif line.startswith("描述:") or line.startswith("描述："):
                        description = line.split(':', 1)[1].strip() if ':' in line else line.split('：', 1)[1].strip()
                
                logger.debug(f"[VLM] 解析结果 - 判断: {judgment}, 描述长度: {len(description)} 字符")
                
                # 判断是否为实质性内容
                if "否" in judgment or not description:
                    logger.debug(f"VLM 判断：图片无实质性内容（判断: {judgment}）")
                    return ""
                
                logger.debug(f"VLM 分析结果 (判断: {judgment}): {description[:100]}...")
                return description
                
            except Exception as e:
                logger.warning(f"VLM 调用失败: {str(e)}")
                logger.debug(f"[VLM] VLM 调用异常详情: {traceback.format_exc()}")
                return ""
                
        except Exception as e:
            logger.warning(f"图片分析异常: {str(e)}")
            return ""

    def process_file(self, file_path, params=None):
        """
        使用 Unstructured 处理文件（支持 PDF、图片等）
        高级文档解析，支持表格结构检测和图片提取

        :param file_path: 文件路径
        :param params: 参数（可包含 save_metadata=True 以保存元数据用于可视化）
        :return: 提取的 Markdown 格式文本
        """
        logger.debug(f"[Unstructured] 开始处理文件: {file_path}")
        try:
            from langchain_unstructured import UnstructuredLoader
            logger.debug(f"[Unstructured] 导入 UnstructuredLoader 成功")
        except ImportError:
            raise OCRServiceException(
                "Unstructured 库未安装。请运行: pip install unstructured[pdf] langchain-unstructured",
                "unstructured",
                "import_error"
            )

        start_time = time.time()
        save_metadata = params.get("save_metadata", False) if params else False
        logger.debug(f"[Unstructured] 参数: save_metadata={save_metadata}")

        try:
            # 使用 UnstructuredLoader 提取文本和结构化内容（保留元数据）
            logger.debug(f"[Unstructured] 创建 UnstructuredLoader，文件: {file_path}")
            loader = UnstructuredLoader(
                file_path=file_path,
                strategy="hi_res",              # 高分辨率模式，支持复杂文档
                infer_table_structure=True,     # 自动解析表格结构
                ocr_languages="chi_sim+eng",    # 支持中英文 OCR
                ocr_engine="paddleocr"          # 指定 PaddleOCR 作为 OCR 引擎
            )
            logger.debug(f"[Unstructured] UnstructuredLoader 创建完成，开始加载文档")
            
            # 获取文件大小用于日志
            try:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                logger.info(f"[Unstructured] 文件大小: {file_size_mb:.2f} MB，开始加载文档（这可能需要几分钟时间，请耐心等待...）")
            except Exception:
                logger.info(f"[Unstructured] 开始加载文档（这可能需要几分钟时间，请耐心等待...）")
            
            load_start_time = time.time()
            
            # 加载文档 - 这是一个可能耗时很长的操作
            logger.debug(f"[Unstructured] 进入 loader.load() 函数，开始实际加载（这可能需要几分钟）")
            try:
                docs = loader.load()
                logger.debug(f"[Unstructured] loader.load() 返回，类型: {type(docs)}")
                documents = list(docs)
                logger.debug(f"[Unstructured] 转换为列表完成，文档数量: {len(documents)}")
            except Exception as e:
                logger.error(f"[Unstructured] loader.load() 执行失败: {str(e)}")
                logger.debug(f"[Unstructured] loader.load() 异常详情: {traceback.format_exc()}")
                raise
            
            load_time = time.time() - load_start_time
            logger.info(f"[Unstructured] 文档加载完成，共 {len(documents)} 个文档块，耗时: {load_time:.2f} 秒")
            logger.debug(f"[Unstructured] 文档加载完成，共 {len(documents)} 个文档块")
            
            # 如果需要保存元数据用于可视化
            if save_metadata:
                logger.debug(f"[Unstructured] 开始保存元数据")
                metadata_path = file_path + ".unstructured_metadata.json"
                metadata_list = []
                for doc in documents:
                    metadata_list.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata
                    })
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata_list, f, ensure_ascii=False, indent=2)
                logger.info(f"元数据已保存到: {metadata_path}")
                logger.debug(f"[Unstructured] 元数据保存完成")
            
            # 提取图片并转换为 Base64 嵌入 Markdown
            logger.debug(f"[Unstructured] 开始提取图片")
            image_map = {}  # page_num -> list of {"data_uri": str, "description": str}
            try:
                logger.debug(f"[Unstructured] 打开 PDF 文件进行图片提取: {file_path}")
                doc = fitz.open(file_path)
                total_pages = doc.page_count
                logger.debug(f"[Unstructured] PDF 共 {total_pages} 页，开始逐页提取图片")
                for page_num, page in enumerate(doc, start=1):
                    logger.debug(f"[Unstructured] 处理第 {page_num}/{total_pages} 页")
                    image_map[page_num] = []
                    images_on_page = list(page.get_images(full=True))
                    logger.debug(f"[Unstructured] 第 {page_num} 页发现 {len(images_on_page)} 张图片")
                    for img_index, img in enumerate(images_on_page, start=1):
                        try:
                            logger.debug(f"[Unstructured] 处理第 {page_num} 页第 {img_index} 张图片")
                            xref = img[0]
                            pix = fitz.Pixmap(doc, xref)
                            logger.debug(f"[Unstructured] 图片提取成功，尺寸: {pix.width}x{pix.height}")
                            
                            # 转换为 RGB（如果需要）
                            if pix.n >= 5:  # CMYK
                                logger.debug(f"[Unstructured] 转换为 RGB 格式")
                                pix = fitz.Pixmap(fitz.csRGB, pix)
                            
                            # 转换为 PNG 字节流
                            logger.debug(f"[Unstructured] 转换为 PNG 字节流")
                            img_bytes = pix.tobytes("png")
                            logger.debug(f"[Unstructured] PNG 字节流大小: {len(img_bytes)} 字节")
                            
                            # 编码为 Base64
                            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                            logger.debug(f"[Unstructured] Base64 编码完成，长度: {len(img_base64)} 字符")
                            
                            # 构建 data URI
                            data_uri = f"data:image/png;base64,{img_base64}"
                            
                            # 使用 VLM 分析图片内容
                            logger.debug(f"[Unstructured] 开始使用 VLM 分析图片内容")
                            description = self._analyze_image_with_vlm(data_uri)
                            logger.debug(f"[Unstructured] VLM 分析完成，描述: {description[:50] if description else '无实质性内容'}...")
                            
                            # 只保存有实质性内容的图片
                            if description:
                                image_map[page_num].append({
                                    "data_uri": data_uri,
                                    "description": description
                                })
                                logger.debug(f"图片分析成功 (page {page_num}, img {img_index}): {description[:50]}...")
                            else:
                                logger.debug(f"图片无实质性内容，跳过 (page {page_num}, img {img_index})")
                            
                        except Exception as e:
                            logger.warning(f"处理图片失败 (page {page_num}, img {img_index}): {str(e)}")
                            logger.debug(f"[Unstructured] 图片处理异常详情: {traceback.format_exc()}")
                            continue
                            
                doc.close()
                logger.debug(f"[Unstructured] 图片提取完成，共处理 {sum(len(imgs) for imgs in image_map.values())} 张图片")
            except Exception as e:
                logger.warning(f"图片提取失败: {str(e)}")
                logger.debug(f"[Unstructured] 图片提取异常详情: {traceback.format_exc()}")

            # 转换为 Markdown
            logger.debug(f"[Unstructured] 开始转换为 Markdown")
            md_lines = []
            inserted_images = set()
            
            # 默认不嵌入base64图片到知识库，只保留图片描述
            include_base64 = params.get("include_base64_images", False) if params else False
            if not include_base64:
                logger.info("知识库模式：将使用图片描述替代 base64 图片，避免 chunk 过大")

            logger.debug(f"[Unstructured] 开始处理 {len(documents)} 个文档块")
            for idx, doc in enumerate(documents, 1):
                logger.debug(f"[Unstructured] 处理文档块 {idx}/{len(documents)}")
                metadata = doc.metadata
                text = doc.page_content
                cat = metadata.get("category", "Text")
                page_num = metadata.get("page_number")

                if cat == "Title" and text.strip().startswith("- "):
                    md_lines.append(text)
                elif cat == "Title":
                    md_lines.append(f"# {text}")
                elif cat in ["Header", "Subheader"]:
                    md_lines.append(f"## {text}")
                elif cat == "Table":
                    # 尝试获取 HTML 表格并转换
                    text_as_html = metadata.get("text_as_html")
                    if text_as_html:
                        try:
                            from html2text import html2text
                            table_md = html2text(text_as_html)
                            md_lines.append(table_md)
                        except ImportError:
                            md_lines.append(text)
                    else:
                        md_lines.append(text)
                elif cat == "Image":
                    # 插入 Base64 编码的图片及其描述
                    # 注意：知识库模式下不嵌入base64图片，避免chunk过大
                    if page_num and page_num in image_map:
                        for img_info in image_map[page_num]:
                            img_data_uri = img_info["data_uri"]
                            img_description = img_info["description"]
                            if img_data_uri not in inserted_images:
                                # 添加图片描述作为文本
                                md_lines.append(f"**图片描述:** {img_description}")
                                # 只在需要时添加图片（用于可视化展示，不用于知识库检索）
                                if include_base64:
                                    md_lines.append(f"![Image]({img_data_uri})")
                                inserted_images.add(img_data_uri)
                                break
                else:
                    md_lines.append(text)

            logger.debug(f"[Unstructured] Markdown 转换完成，共 {len(md_lines)} 行")
            result_text = "\n\n".join(md_lines)
            processing_time = time.time() - start_time
            logger.debug(f"[Unstructured] Markdown 文本生成完成，长度: {len(result_text)} 字符，耗时: {processing_time:.2f} 秒")
            
            # 使用 LLM 整理 Markdown 格式
            logger.debug(f"[Unstructured] 开始使用 LLM 整理 Markdown 格式")
            result_text = self._format_markdown_with_llm(result_text, params=params)
            logger.debug(f"[Unstructured] LLM 格式整理完成，最终文本长度: {len(result_text)} 字符")
            
            # 如果是 PDF 文件，自动生成可视化数据并保存
            if save_metadata and file_path.lower().endswith('.pdf'):
                logger.debug(f"[Unstructured] 开始生成可视化数据")
                try:
                    visualization_data = self._generate_visualization(file_path, documents)
                    visualization_path = file_path + ".visualization.json"
                    with open(visualization_path, "w", encoding="utf-8") as f:
                        json.dump(visualization_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"可视化数据已保存到: {visualization_path}")
                    logger.debug(f"[Unstructured] 可视化数据生成完成")
                except Exception as e:
                    logger.warning(f"生成可视化数据失败: {str(e)}")
                    logger.debug(f"[Unstructured] 可视化数据生成异常详情: {traceback.format_exc()}")
            
            log_ocr_request("unstructured", file_path, True, processing_time)
            logger.debug(f"Unstructured 处理完成: {result_text[:100]}... (共 {len(result_text)} 字符)")
            logger.debug(f"[Unstructured] 整个处理流程完成，总耗时: {processing_time:.2f} 秒")
            
            return result_text
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Unstructured 处理失败: {str(e)}"
            logger.error(f"[Unstructured] 处理失败: {error_msg}")
            logger.debug(f"[Unstructured] 异常详情: {traceback.format_exc()}")
            log_ocr_request("unstructured", file_path, False, processing_time, error_msg)
            raise OCRServiceException(error_msg, "unstructured", "processing_failed")

    def _generate_visualization(self, file_path, documents):
        """
        生成 PDF 文档的可视化标注数据
        
        :param file_path: PDF 文件路径
        :param documents: UnstructuredLoader 加载的文档列表
        :return: 包含标注图片的可视化数据
        """
        # 提取元数据
        metadata = []
        for doc in documents:
            meta = doc.metadata.copy()
            meta["text"] = doc.page_content
            meta["category"] = meta.get("category", "Text")
            metadata.append(meta)
        
        # 打开 PDF 文件
        pdf_doc = fitz.open(file_path)
        total_pages = pdf_doc.page_count
        
        # 为每一页生成标注图片
        annotated_pages = []
        category_to_color = {
            "Title": "orchid",
            "Image": "forestgreen",
            "Table": "tomato",
        }
        
        for page_num in range(1, total_pages + 1):
            # 获取该页的元素
            page_elements = [el for el in metadata if el.get("page_number") == page_num]
            
            # 渲染 PDF 页面
            pdf_page = pdf_doc.load_page(page_num - 1)
            pix = pdf_page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2倍分辨率
            
            if not page_elements:
                # 如果该页没有元素，直接返回原始PDF页面
                img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                annotated_pages.append({
                    "page_number": page_num,
                    "image": img_base64,
                    "elements": []
                })
                continue
            
            # 转换为 PIL 图像
            pil_image = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # 创建 matplotlib 图形
            fig, ax = plt.subplots(1, figsize=(pix.width/100, pix.height/100), dpi=100)
            ax.imshow(pil_image)
            
            categories = set()
            
            # 绘制标注框
            for element in page_elements:
                if "coordinates" not in element:
                    continue
                
                coords = element["coordinates"]
                if "points" not in coords:
                    continue
                
                points = coords["points"]
                layout_width = coords.get("layout_width", pix.width)
                layout_height = coords.get("layout_height", pix.height)
                
                # 坐标缩放
                scaled_points = [
                    (x * pix.width / layout_width, y * pix.height / layout_height)
                    for x, y in points
                ]
                
                category = element.get("category", "Text")
                box_color = category_to_color.get(category, "deepskyblue")
                categories.add(category)
                
                # 绘制多边形框
                rect = patches.Polygon(
                    scaled_points, 
                    linewidth=2, 
                    edgecolor=box_color, 
                    facecolor="none"
                )
                ax.add_patch(rect)
            
            # 添加图例
            legend_handles = [patches.Patch(color="deepskyblue", label="Text")]
            for category in ["Title", "Image", "Table"]:
                if category in categories:
                    legend_handles.append(
                        patches.Patch(color=category_to_color[category], label=category)
                    )
            ax.axis("off")
            ax.legend(handles=legend_handles, loc="upper right", fontsize=8)
            plt.tight_layout(pad=0)
            
            # 将图形保存为 Base64
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, dpi=100)
            plt.close(fig)
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            
            annotated_pages.append({
                "page_number": page_num,
                "image": img_base64,
                "elements": page_elements
            })
        
        pdf_doc.close()
        
        return {
            "filename": os.path.basename(file_path),
            "total_pages": total_pages,
            "annotated_pages": annotated_pages,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

