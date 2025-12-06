# Unstructured 功能实现总结

## 📋 功能概述

成功为 StackSolve - 栈问速解 知识库系统添加了 **Unstructured** 文档解析功能，这是一种智能文档解析方法，特别适合处理包含复杂表格和结构的 PDF 文档。

## ✅ 完成的工作

### 1. 后端实现

#### 1.1 OCR 插件扩展 (`src/processors/_ocr.py`)

添加了 `process_file_unstructured` 方法：

```python
def process_file_unstructured(self, file_path, params=None):
    """
    使用 Unstructured 处理文件（支持 PDF、图片等）
    高级文档解析，支持表格结构检测和图片提取
    
    特性：
    - 使用 langchain_unstructured.UnstructuredLoader
    - 智能文档结构识别（标题、段落、表格、图片）
    - 高分辨率 OCR 模式（strategy="hi_res"）
    - 自动表格结构检测（infer_table_structure=True）
    - 中英文混合识别（ocr_languages="chi_sim+eng"）
    - 使用 PaddleOCR 引擎
    - 图片自动提取并转换为 Base64 嵌入
    """
```

**核心特性：**
- ✅ 保留完整元数据用于可视化
- ✅ 智能识别文档元素（Title, Header, Table, Image, Text）
- ✅ 表格自动转换为 Markdown 格式
- ✅ 图片提取并编码为 Base64 嵌入 Markdown
- ✅ 错误处理和日志记录

#### 1.2 文件索引集成 (`src/knowledge/indexing.py`)

在 `parse_pdf` 和 `parse_image` 函数中添加了 unstructured 选项：

```python
elif opt_ocr == "unstructured":
    from src.processors import ocr
    return ocr.process_file_unstructured(file, params=params)
```

#### 1.3 聊天 API 扩展 (`server/routers/chat_router.py`)

文件提取 API 支持 `unstructured` 方法：
- 端点：`POST /api/chat/extract-file`
- 支持 `ocr_method` 参数
- 默认使用 `unstructured` 方法

### 2. 前端实现

#### 2.1 知识库文件上传界面 (`web/src/components/FileUploadModal.vue`)

添加了 Unstructured 选项到 OCR 下拉菜单：

```javascript
{
  value: 'unstructured',
  label: '✅ Unstructured (智能解析)',
  title: 'Unstructured (智能文档解析)',
  disabled: false
}
```

**特点：**
- 默认状态为 `healthy`（✅）
- 不需要健康检查
- 总是可用
- 健康检查结果合并策略（保留 unstructured 状态）

#### 2.2 Agent API (`web/src/apis/agent_api.js`)

更新了 `extractFileContent` 方法支持 OCR 方法参数：

```javascript
extractFileContent: async (file, ocrMethod = 'unstructured') => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('ocr_method', ocrMethod);
  // ...
}
```

### 3. 依赖管理

#### 3.1 Python 依赖 (`pyproject.toml`)

添加的依赖：
```toml
"unstructured[pdf]>=0.17.2",
"langchain-unstructured>=0.1.4",
"html2text>=2024.2.26",
"matplotlib>=3.9.0",
```

#### 3.2 系统依赖 (`docker/api.Dockerfile`)

添加的系统包：
```dockerfile
poppler-utils           # PDF 工具（pdfinfo, pdftoppm 等）
tesseract-ocr           # Tesseract OCR 引擎
tesseract-ocr-chi-sim   # 中文简体语言包
tesseract-ocr-eng       # 英文语言包
```

**Dockerfile 优化：**
- 修复了 `/tmp` 目录权限问题
- 分离了镜像源配置和软件安装步骤
- 在安装前确保 `/tmp` 权限为 `1777`

## 🎯 技术亮点

### 1. 智能文档结构识别

```python
# 文档元素类型识别
- Title       → # 标题
- Header      → ## 标题
- Table       → Markdown 表格
- Image       → ![Image](data:image/png;base64,...)
- Text        → 普通文本
```

### 2. Base64 图片嵌入

**优势：**
- ✅ 无需额外的文件存储路径
- ✅ 图片直接嵌入 Markdown
- ✅ 支持跨平台显示
- ✅ 简化文件管理

**实现：**
```python
# 提取图片 → 转换为 PNG 字节流 → Base64 编码 → data URI
pix = fitz.Pixmap(doc, xref)
img_bytes = pix.tobytes("png")
img_base64 = base64.b64encode(img_bytes).decode('utf-8')
data_uri = f"data:image/png;base64,{img_base64}"
```

### 3. 高级表格处理

```python
# HTML 表格转 Markdown
if text_as_html:
    from html2text import html2text
    table_md = html2text(text_as_html)
    md_lines.append(table_md)
```

## 📊 OCR 方法对比

| 方法 | 速度 | 表格识别 | 结构保持 | 图片提取 | GPU 需求 | 适用场景 |
|------|------|----------|----------|----------|---------|----------|
| **disable** | ⚡⚡⚡⚡⚡ | ❌ | ⭐⭐ | ❌ | 否 | 纯文本 PDF |
| **unstructured** ⭐ | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 可选 | **复杂文档、表格** |
| **mineru_ocr** | ⚡⚡ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 是 | 学术论文 |
| **paddlex_ocr** | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 是 | 企业文档 |

## 🔧 使用方法

### 方法 1：知识库文件上传

1. 创建或打开知识库
2. 点击"添加文件"
3. 在"使用OCR"下拉框中选择 **"✅ Unstructured (智能解析)"**
4. 上传文件

### 方法 2：Agent 聊天文件上传

```javascript
// 前端自动使用 unstructured 方法
const result = await agentApi.extractFileContent(file);
```

### 方法 3：程序化调用

```python
from src.processors import ocr

# 基础使用
text = ocr.process_file_unstructured("document.pdf")

# 保存元数据用于可视化
text = ocr.process_file_unstructured(
    "document.pdf", 
    params={"save_metadata": True}
)
```

## 📝 输出格式示例

```markdown
# 文档标题

## 第一章 概述

这是正常的段落文本内容...

### 数据统计表

| 项目 | 数量 | 占比 |
|------|------|------|
| A项目 | 100 | 50% |
| B项目 | 100 | 50% |

![Image](data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...)

图片说明文字...
```

## ⚙️ 配置选项

### UnstructuredLoader 参数

```python
UnstructuredLoader(
    file_path=file_path,
    strategy="hi_res",              # 高分辨率模式
    infer_table_structure=True,     # 表格结构检测
    ocr_languages="chi_sim+eng",    # 中英文识别
    ocr_engine="paddleocr"          # OCR 引擎
)
```

### strategy 选项

- `auto`: 自动选择（默认）
- `fast`: 快速模式（跳过 OCR）
- `hi_res`: 高分辨率模式（最准确）
- `ocr_only`: 仅 OCR

## 🚀 性能优化建议

1. **文档大小**：建议单个文件 < 50MB
2. **图片处理**：Base64 会增加约 33% 的数据大小
3. **处理时间**：复杂文档约 10-30 秒/页
4. **内存占用**：高分辨率模式需要较多内存

## 🐛 故障排查

### 问题 1：图片不显示

**原因**：图片已经作为 Base64 嵌入在 Markdown 中

**解决**：确保 Markdown 渲染器支持 data URI

### 问题 2：处理速度慢

**解决方案**：
1. 使用 `strategy="auto"` 自动选择
2. 对简单 PDF 使用其他方法
3. 考虑分页处理大文档

### 问题 3：中文识别率低

**解决方案**：
1. 确认 `tesseract-ocr-chi-sim` 已安装
2. 检查 `ocr_languages="chi_sim+eng"` 配置
3. 使用高分辨率源文档

### 问题 4：表格识别不准确

**解决方案**：
1. 确保 `infer_table_structure=True`
2. 使用 `strategy="hi_res"`
3. 检查原始 PDF 表格是否清晰

## 📦 部署清单

### ✅ 已完成

- [x] 添加 Python 依赖到 `pyproject.toml`
- [x] 修改 Dockerfile 添加系统依赖
- [x] 实现 `process_file_unstructured` 方法
- [x] 集成到文件索引流程
- [x] 前端添加 Unstructured 选项
- [x] API 支持 OCR 方法选择
- [x] 图片 Base64 编码实现
- [x] 错误处理和日志记录
- [x] 编写使用文档

### 🔄 后续优化（可选）

- [ ] 添加处理进度反馈
- [ ] 支持批量文件处理
- [ ] 缓存重复文档的处理结果
- [ ] 添加可视化工具（显示文档结构）
- [ ] 优化大文件处理性能

## 📚 相关文档

- [Unstructured文档解析指南.md](./Unstructured文档解析指南.md)
- [多模态消息功能指南.md](./多模态消息功能指南.md)
- [文件上传与提取功能指南.md](./文件上传与提取功能指南.md)

## 🎉 总结

Unstructured 功能为 StackSolve - 栈问速解 带来了强大的文档解析能力：

1. **智能化**：自动识别文档结构和元素类型
2. **高质量**：准确的表格识别和内容提取
3. **易用性**：前端一键选择，无需配置
4. **灵活性**：支持多种文档类型和格式
5. **可扩展**：保留元数据，便于后续处理

现在系统共支持 **5 种文件处理方式**，可根据不同文档类型和需求灵活选择！

---

**最后更新**: 2025-10-08
**版本**: v0.3.0
