# Unstructured 图片 VLM 分析功能指南

## 概述

在使用 `Unstructured` 进行文档解析时，系统现在会自动使用 VLM（视觉语言模型）对提取的图片进行智能分析，判断图片是否包含有价值的信息内容。只有包含实质性内容的图片才会被保留并添加到最终的 Markdown 文档中。

## 功能特点

### 1. 智能图片筛选

使用 VLM 自动判断图片内容，过滤掉无实质性内容的图片，包括：
- 纯装饰性元素（边框、背景、分隔线等）
- 空白或几乎空白的图片
- 模糊不清无法识别的内容
- Logo、图标（除非是关键说明的一部分）
- 重复的水印或页眉页脚

### 2. 自动添加图片描述

对于保留的图片，VLM 会生成简要描述（50-100字），描述内容包括：
- 图表类型和主要数据趋势
- 流程图或架构图的核心结构
- 照片或插图的主题内容
- 表格数据的关键信息
- 公式或代码片段的概要

### 3. Markdown 格式输出

图片及其描述会以清晰的格式嵌入到 Markdown 文档中：

```markdown
**图片描述:** 这是一个折线图，展示了2020-2023年的销售额增长趋势，呈现持续上升态势。

![Image](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgA...)
```

## 技术实现

### 1. VLM 模型配置

系统使用在 `saves/config/base.yaml` 中配置的 VL 模型：

```yaml
vl_model: "siliconflow/OpenGVLab/InternVL2-26B"
```

支持的 VL 模型包括：
- `siliconflow/OpenGVLab/InternVL2-26B`（默认，中文友好）
- `openai/gpt-4o`
- `anthropic/claude-3-sonnet-20240229`
- `siliconflow/Qwen/Qwen-VL-Plus`

可以在**设置页面**的"视觉语言模型（VL Model）"选项中修改。

### 2. 处理流程

```
1. Unstructured 解析文档
   ↓
2. 提取图片并转换为 Base64
   ↓
3. VLM 分析每张图片内容
   ↓
4. 判断是否有实质性内容
   ↓
5. 保留有价值的图片并生成描述
   ↓
6. 嵌入到 Markdown 文档
```

### 3. 核心代码位置

- **主要实现**: `src/processors/_ocr.py`
  - `_analyze_image_with_vlm()`: VLM 图片分析方法
  - `process_file_unstructured()`: Unstructured 处理方法

## 使用方法

### 1. API 调用

在调用 OCR 服务时，使用 `unstructured` 方法：

```python
from src.processors._ocr import OCRPlugin

ocr_plugin = OCRPlugin()
result = ocr_plugin.process_file_unstructured(
    file_path="/path/to/document.pdf",
    params={"save_metadata": True}  # 可选，保存元数据用于可视化
)

# result 包含 Markdown 格式的文本，其中有价值的图片已被保留并附带描述
print(result)
```

### 2. 通过知识库上传

1. 在知识库管理页面上传 PDF 文档
2. 系统会自动使用 Unstructured 处理
3. VLM 会自动分析所有图片
4. 只有有价值的图片会被保留在最终的知识库中

## 性能与成本

### 1. 处理速度

- 图片分析是异步进行的，每张图片大约需要 2-5 秒
- 对于包含大量图片的文档，处理时间会相应增加
- 建议：对于图片较多的文档，可以在后台批量处理

### 2. API 成本

使用 VLM 分析图片会产生额外的 API 调用成本：

| VL 模型 | 每张图片成本（估算） |
|---------|-------------------|
| InternVL2-26B (SiliconFlow) | ~¥0.001 |
| GPT-4o | ~$0.003 |
| Claude 3 Sonnet | ~$0.005 |

**成本优化建议：**
- 使用开源模型（如 InternVL2）可大幅降低成本
- 考虑缓存相似图片的分析结果
- 对于大批量文档，可以设置图片分析的开关

### 3. 准确性

- **精确度**: VLM 能够准确识别大部分有价值的图片
- **误判**: 少数情况下可能会误判装饰性图片为有价值内容，或反之
- **建议**: 对于关键文档，建议人工复核处理结果

## 配置选项

### 1. 启用/禁用 VLM 分析

可以通过参数控制是否使用 VLM 分析：

```python
# 禁用 VLM 分析（保留所有图片，不添加描述）
result = ocr_plugin.process_file_unstructured(
    file_path="/path/to/document.pdf",
    params={"enable_vlm_analysis": False}  # 计划中的功能
)
```

### 2. 自定义分析提示词

如果需要针对特定领域的文档调整分析标准，可以修改 `_analyze_image_with_vlm` 方法中的 `prompt`。

## 日志与调试

### 1. 查看处理日志

系统会记录详细的图片分析日志：

```
[DEBUG] 图片分析成功 (page 1, img 1): 这是一个柱状图，展示了不同产品的销量对比...
[DEBUG] VLM 判断：图片无实质性内容
[WARNING] VLM 调用失败: Connection timeout
```

### 2. 日志位置

日志文件位于：`saves/logs/stacksolve-{date}.log`

## 故障排查

### 1. VLM 模型加载失败

**症状**: 日志显示 "加载 VL 模型失败"

**解决方法**:
- 检查 VL 模型配置是否正确
- 确认对应的 API Key 已配置在 `.env` 文件中
- 验证网络连接是否正常

### 2. 图片分析超时

**症状**: 日志显示 "VLM 调用失败: Connection timeout"

**解决方法**:
- 检查网络连接
- 尝试切换到其他 VL 模型提供商
- 增加超时时间（需要修改代码）

### 3. 所有图片都被过滤

**症状**: 生成的 Markdown 中没有任何图片

**可能原因**:
- VLM 判断标准过于严格
- 文档中的图片确实都是装饰性的
- VLM 模型出现问题

**解决方法**:
- 检查日志中的 VLM 分析结果
- 尝试使用不同的 VL 模型
- 调整 `_analyze_image_with_vlm` 中的判断逻辑

## 未来改进计划

- [ ] 添加图片分析缓存机制
- [ ] 支持批量并行处理图片
- [ ] 提供更细粒度的配置选项
- [ ] 支持自定义图片筛选规则
- [ ] 添加图片相似度检测，避免重复分析
- [ ] 生成图片内容的向量表示，用于语义搜索

## 相关文档

- [VL 模型配置指南](VL模型配置指南.md)
- [Unstructured 文档解析指南](Unstructured文档解析指南.md)
- [多模态消息功能指南](多模态消息功能指南.md)

---

**更新时间**: 2025-10-12  
**版本**: v0.4.0  
**作者**: Stack-Solve Team

