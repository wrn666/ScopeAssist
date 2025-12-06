# OSRedm 全站爬虫系统

一个专为 https://www.osredm.com/ 设计的智能全站爬虫系统，具备强大的反检测能力和分批处理功能。

## ✨ 主要特性

- 🛡️ **强化反检测**: 结合 Stealth Mode 和 UndetectedAdapter 双重保护
- 🔄 **分批处理**: 智能分批爬取，避免触发网站防护机制
- 💾 **断点续爬**: 支持中断恢复，保存爬取进度
- 📁 **自动组织**: 自动创建目录结构，分类保存内容
- 📊 **实时监控**: 详细的爬取进度和统计信息
- 🎯 **智能URL发现**: 自动发现和分类网站内的所有链接

## 🚀 快速开始

### ⚠️ 重要：遇到浏览器错误？
如果看到 `Executable doesn't exist` 错误，请先运行：
```bash
fix_browser.bat
```

### 1. 安装依赖
```bash
# 运行完整安装脚本（推荐）
install_requirements.bat

# 如果遇到浏览器问题，单独运行
fix_browser.bat
```

### 2. 运行爬虫
```bash
# 方式一：智能启动脚本（推荐，会自动检查环境）
start_crawler.bat

# 方式二：直接运行
python main.py

# 方式三：快速测试模式
python quick_test.py
```

### 3. 监控进度
爬虫运行时会实时显示:
- 当前爬取进度
- 发现的URL数量
- 成功/失败统计
- 估计剩余时间

## 📁 输出结构

```
红山网络怕爬虫/
├── markdown/              # Markdown文件
├── logs/                  # 日志文件
├── assets/               # 资源文件
├── urls_discovered.json  # 发现的URL列表
├── crawl_progress.json   # 爬取进度
└── failed_urls.json     # 失败的URL
```

## ⚙️ 配置选项

在 `config.py` 中可以调整:

### 爬取参数
- `max_pages`: 最大爬取页面数 (默认: 100)
- `batch_size`: 批次大小 (默认: 2)
- `delay_between_batches`: 批次间延迟 (默认: 5秒)

### 反检测设置
- `use_stealth_mode`: 启用隐身模式
- `use_undetected_adapter`: 使用不可检测适配器
- `headless`: 是否使用无头模式

### 内容过滤
- `enable_pruning`: 启用内容修剪
- `pruning_threshold`: 修剪阈值
- `save_images`: 是否保存图片

## 🛠️ 高级功能

### 断点续爬
如果爬取过程中断，重新运行程序会自动:
- 加载已爬取的URL列表
- 跳过已完成的页面
- 从中断点继续爬取

### 智能延迟
系统会根据以下因素动态调整延迟:
- 批次大小
- 服务器响应时间
- 错误率

### 错误处理
- 自动重试失败的请求
- 记录详细的错误信息
- 智能识别反爬机制

## 📊 进度监控

### 实时统计
- 总发现URL数
- 成功爬取数
- 失败URL数
- 完成百分比

### 日志信息
详细的日志记录包括:
- 每个URL的爬取状态
- 发现的新URL数量
- 错误信息和重试次数
- 系统资源使用情况

## ⚠️ 注意事项

1. **合规使用**: 请遵守网站的 robots.txt 和使用条款
2. **合理延迟**: 不要设置过小的延迟，避免对服务器造成压力
3. **监控资源**: 注意系统内存和磁盘空间使用情况
4. **网络稳定**: 确保网络连接稳定，避免频繁重试

## 🔧 故障排除

### 常见问题

**Q: 出现 "Executable doesn't exist" 错误？**
```
错误: BrowserType.launch: Executable doesn't exist at C:\Users\...\chromium-1187\chrome-win\chrome.exe
```
**A: 浏览器未安装，解决方法：**
```bash
# 方法一：运行修复脚本
fix_browser.bat

# 方法二：手动安装
pip install playwright
playwright install
playwright install-deps
```

**Q: 爬虫被检测到怎么办？**
A: 尝试增加延迟时间，或启用更强的反检测模式

**Q: 内存使用过高？**
A: 减小 batch_size 或调低 memory_threshold

**Q: 某些页面爬取失败？**
A: 检查 failed_urls.json 文件，查看具体错误信息

**Q: 导入 crawl4ai 失败？**
```
错误: ModuleNotFoundError: No module named 'crawl4ai'
```
**A: 重新安装依赖：**
```bash
install_requirements.bat
```

### 参数调优建议

**保守模式** (推荐新手):
```python
max_pages = 50
batch_size = 1
delay_between_batches = 10
```

**平衡模式** (推荐):
```python
max_pages = 100
batch_size = 2
delay_between_batches = 5
```

**激进模式** (谨慎使用):
```python
max_pages = 500
batch_size = 3
delay_between_batches = 3
```

## 📞 支持

如遇到问题，请检查:
1. 日志文件中的错误信息
2. 网络连接状态
3. 系统资源使用情况
4. crawl4ai 库是否正确安装

---

🎯 **目标**: 高效、稳定、隐蔽地爬取 OSRedm 网站内容
⚡ **原则**: 尊重服务器、智能延迟、错误恢复