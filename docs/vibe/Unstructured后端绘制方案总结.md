# Unstructured 后端绘制方案实现总结

## 概述

本方案将 PDF 文档的结构化解析和可视化标注完全放在后端实现。在文件处理阶段自动生成可视化数据并保存到磁盘，需要时直接读取展示。

## 核心设计思想

**"处理时可视化，需要时读取"**

- ✅ 在文件处理（`process_file_unstructured`）时自动生成可视化
- ✅ 将可视化数据保存为 JSON 文件（`{file_path}.visualization.json`）
- ✅ 需要展示时直接读取已保存的数据
- ✅ 路由层只负责读取和返回数据，不做业务处理

## 架构设计

### 数据流程

```
用户上传 PDF → Unstructured 解析
    ↓
提取元素和坐标
    ↓
使用 matplotlib 绘制标注框
    ↓
生成 Base64 图片
    ↓
保存为 .visualization.json
    ↓
（稍后需要时）
    ↓
前端请求 → 路由读取 JSON → 前端显示
```

### 文件存储结构

```
saves/knowledge_base_data/milvus_data/kb_xxx/uploads/
├── document.pdf                      # 原始PDF文件
├── document.pdf.unstructured_metadata.json   # 元数据（可选）
└── document.pdf.visualization.json   # 可视化数据（自动生成）
```

## 技术实现

### 1. OCR 插件层（`src/processors/_ocr.py`）

#### `process_file_unstructured` 方法

在处理文件时自动调用可视化生成：

```python
def process_file_unstructured(self, file_path, params=None):
    """处理文件并自动生成可视化"""
    # ... Unstructured 解析逻辑 ...
    
    # 如果是 PDF 文件且需要保存元数据，自动生成可视化
    if save_metadata and file_path.lower().endswith('.pdf'):
        try:
            visualization_data = self._generate_visualization(file_path, documents)
            visualization_path = file_path + ".visualization.json"
            with open(visualization_path, "w", encoding="utf-8") as f:
                json.dump(visualization_data, f, ensure_ascii=False, indent=2)
            logger.info(f"可视化数据已保存到: {visualization_path}")
        except Exception as e:
            logger.warning(f"生成可视化数据失败: {str(e)}")
    
    return result_text
```

#### `_generate_visualization` 方法

生成可视化标注数据：

```python
def _generate_visualization(self, file_path, documents):
    """
    生成 PDF 文档的可视化标注数据
    
    处理流程：
    1. 提取元数据
    2. 遍历每一页
    3. 使用 PyMuPDF 渲染 PDF 页面
    4. 使用 matplotlib 绘制标注框
    5. 添加图例
    6. 保存为 Base64 图片
    
    返回：包含所有页面标注图片的 JSON 数据
    """
    # 提取元数据
    metadata = []
    for doc in documents:
        meta = doc.metadata.copy()
        meta["text"] = doc.page_content
        meta["category"] = meta.get("category", "Text")
        metadata.append(meta)
    
    # 打开 PDF 并处理每一页
    pdf_doc = fitz.open(file_path)
    annotated_pages = []
    
    for page_num in range(1, total_pages + 1):
        # 获取该页元素
        page_elements = [el for el in metadata if el.get("page_number") == page_num]
        
        # 渲染页面
        pdf_page = pdf_doc.load_page(page_num - 1)
        pix = pdf_page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2倍分辨率
        
        # 使用 matplotlib 绘制标注框
        fig, ax = plt.subplots(...)
        ax.imshow(pil_image)
        
        # 绘制每个元素的标注框
        for element in page_elements:
            rect = patches.Polygon(scaled_points, ...)
            ax.add_patch(rect)
        
        # 添加图例
        ax.legend(handles=legend_handles, ...)
        
        # 保存为 Base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', ...)
        plt.close(fig)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        
        annotated_pages.append({
            "page_number": page_num,
            "image": img_base64,
            "elements": page_elements
        })
    
    return {
        "filename": os.path.basename(file_path),
        "total_pages": total_pages,
        "annotated_pages": annotated_pages,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
```

### 2. 路由层（`server/routers/chat_router.py`）

路由层极度简化，只负责读取和返回数据：

```python
@chat.post("/visualize-unstructured-by-path")
async def visualize_unstructured_by_path(
    request_body: dict = Body(...),
    current_user: User = Depends(get_required_user)
):
    """
    读取文件的 Unstructured 可视化数据
    注意：可视化数据在文件处理时自动生成并保存
    """
    file_path = request_body.get("file_path")
    
    # 读取已保存的可视化数据
    visualization_path = file_path + ".visualization.json"
    
    if not os.path.exists(visualization_path):
        raise HTTPException(
            status_code=404,
            detail="可视化数据未找到，请确保文件使用 Unstructured 方法处理过"
        )
    
    with open(visualization_path, "r", encoding="utf-8") as f:
        visualization_data = json.load(f)
    
    return {
        "success": True,
        "filename": visualization_data.get("filename"),
        "total_pages": visualization_data.get("total_pages"),
        "annotated_pages": visualization_data.get("annotated_pages"),
        "created_at": visualization_data.get("created_at"),
        "message": "可视化数据加载成功"
    }
```

**路由层职责：**
- ✅ 验证参数
- ✅ 读取 JSON 文件
- ✅ 返回数据
- ❌ 不做任何业务处理
- ❌ 不调用 matplotlib 绘制
- ❌ 不调用 OCR 处理

### 3. 前端组件（`web/src/components/UnstructuredVisualizerModal.vue`）

前端只负责显示后端返回的图片：

```vue
<template>
  <a-modal title="Unstructured 文档可视化">
    <!-- 工具栏：页面导航 -->
    <div class="toolbar">
      <a-button @click="prevPage">上一页</a-button>
      <span>第 {{ currentPage }} / {{ totalPages }} 页</span>
      <a-button @click="nextPage">下一页</a-button>
    </div>

    <!-- 显示标注图片 -->
    <div class="image-container">
      <img :src="`data:image/png;base64,${currentPageImage}`" />
    </div>

    <!-- 元素列表 -->
    <div class="content-list">
      <div v-for="element in currentPageElements">
        {{ element.category }}: {{ element.text }}
      </div>
    </div>
  </a-modal>
</template>
```

## 可视化数据格式

### `.visualization.json` 文件结构

```json
{
  "filename": "document.pdf",
  "total_pages": 10,
  "created_at": "2025-10-09 00:48:00",
  "annotated_pages": [
    {
      "page_number": 1,
      "image": "iVBORw0KGgoAAAANS...(Base64)",
      "elements": [
        {
          "category": "Title",
          "text": "文档标题",
          "page_number": 1,
          "coordinates": {
            "points": [[100, 50], [400, 50], [400, 100], [100, 100]],
            "layout_width": 595,
            "layout_height": 842
          }
        }
      ]
    }
  ]
}
```

## 颜色方案

| 元素类型 | 颜色代码 | 颜色名称 | 用途 |
|---------|---------|---------|------|
| Title | #da70d6 | orchid（兰花紫） | 标题 |
| Image | #228b22 | forestgreen（森林绿） | 图片 |
| Table | #ff6347 | tomato（番茄红） | 表格 |
| Text | #00bfff | deepskyblue（深天蓝） | 普通文本 |

## 使用流程

### 1. 上传文件到知识库

```javascript
// 在 FileUploadModal.vue 中选择 "Unstructured" OCR 方法
ocrMethod: 'unstructured'

// 后端自动调用
process_file_unstructured(file_path, params={"save_metadata": True})
    ↓
自动生成 .visualization.json
```

### 2. 查看可视化

```javascript
// 在 FileDetailModal.vue 中点击 "Unstructured 可视化" 按钮
const result = await agentApi.visualizeUnstructuredByPath(file.path);
    ↓
后端读取 .visualization.json
    ↓
前端显示标注图片
```

## 优势与特点

### ✅ 核心优势

1. **职责分离**：
   - OCR 插件：业务逻辑（解析 + 可视化）
   - 路由层：数据传输（读取 + 返回）
   - 前端：展示（显示图片）

2. **性能优化**：
   - 处理一次，多次使用
   - 避免重复计算
   - 快速响应（直接读取文件）

3. **可维护性**：
   - 逻辑集中在 OCR 插件
   - 路由层代码极简
   - 易于测试和调试

4. **可扩展性**：
   - 可以添加缓存策略
   - 可以异步生成可视化
   - 可以支持其他文件格式

### ⚠️ 注意事项

1. **存储空间**：
   - 每页图片约 100-500KB
   - 大文档会占用较多磁盘空间
   - 建议：定期清理或压缩

2. **处理时间**：
   - 可视化生成需要额外时间
   - 建议：异步处理或显示进度

3. **文件同步**：
   - 删除原文件时需要同步删除可视化文件
   - 建议：在文件删除逻辑中添加清理

## 与原方案对比

| 特性 | 原方案（前端绘制） | 当前方案（处理时生成） |
|-----|------------------|---------------------|
| 绘制时机 | 查看时实时绘制 | 处理时预先生成 |
| 响应速度 | 慢（需要绘制） | 快（直接读取） |
| 服务器压力 | 高（每次请求都绘制） | 低（一次性生成） |
| 存储需求 | 低 | 高 |
| 路由层复杂度 | 高（包含绘制逻辑） | 低（只读文件） |
| 可重用性 | 差 | 好 |

## 文件清单

### 后端文件

- `src/processors/_ocr.py`
  - `process_file_unstructured()` - 处理文件并自动生成可视化
  - `_generate_visualization()` - 生成可视化标注数据

- `server/routers/chat_router.py`
  - `/api/chat/visualize-unstructured-by-path` - 读取可视化数据

### 前端文件

- `web/src/components/UnstructuredVisualizerModal.vue` - 可视化弹窗
- `web/src/components/FileDetailModal.vue` - 文件详情页集成
- `web/src/apis/agent_api.js` - API 调用

## 依赖库

### Python 依赖

```python
unstructured[pdf]      # PDF 文档解析
langchain-unstructured # LangChain 集成
PyMuPDF (fitz)         # PDF 渲染
matplotlib             # 绘图和标注
Pillow                 # 图像处理
html2text              # HTML 表格转换
```

## 总结

通过将可视化生成集成到文件处理流程中，我们实现了：

1. **清晰的职责分离**：OCR 插件负责业务，路由负责传输
2. **高效的性能**：处理一次，多次使用
3. **简洁的代码**：路由层从 180 行减少到 30 行
4. **良好的扩展性**：易于添加新功能

这种设计符合"单一职责原则"和"关注点分离"的软件工程最佳实践。