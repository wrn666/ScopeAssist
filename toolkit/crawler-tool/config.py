# OSRedm 全站爬虫配置文件

# 目标网站配置
TARGET_URL = "https://www.osredm.com/"
OUTPUT_DIR = r"D:\HuaweiMoveData\Users\21438\Desktop\红山网络怕爬虫"

# 爬取参数配置
CRAWL_CONFIG = {
    # 基础配置
    "max_pages": 8000,          # 适中的页面限制，可根据需要调整
    "batch_size": 5,            # 批次大小 (增加到5提高效率)
    "max_rounds": 30,           # 最大轮次数 (增加到30)
    
    # 深度爬取配置
    "deep_max_pages": 1000,     # 深度模式最大页面数
    "deep_max_rounds": 20,      # 深度模式最大轮次
    "monitor_interval": 3600,   # 监控模式间隔(秒) - 1小时
    
    # 优化后的延迟配置 - 提高爬取速度
    "delay_between_batches": 2, # 批次间延迟(秒) - 从5减少到2
    "delay_between_requests": 1, # 请求间延迟(秒) - 从3减少到1
    "delay_between_rounds": 10, # 轮次间延迟(秒) - 从30减少到10
    
    # 超时和重试
    "timeout": 35,              # 基础页面超时时间(秒) - 从20增加到35
    "explore_timeout": 60,      # 探索页面专用超时时间(秒) - 新增
    "max_retries": 3,           # 最大重试次数
    "retry_delay": 2,           # 重试延迟基数(秒) - 从1增加到2
}

# 反检测配置
ANTI_DETECTION = {
    "use_stealth_mode": True,     # 启用隐身模式
    "use_undetected_adapter": True, # 使用不可检测适配器
    "headless": False,            # 是否无头模式
    "viewport_width": 1920,       # 视口宽度
    "viewport_height": 1080,      # 视口高度
    "memory_threshold": 80.0,     # 内存阈值百分比
}

# 内容过滤配置
CONTENT_FILTER = {
    "enable_pruning": True,       # 启用内容修剪
    "pruning_threshold": 0.3,     # 修剪阈值
    "save_images": False,         # 是否保存图片
    "save_raw_html": False,       # 是否保存原始HTML
}

# 日志配置
LOGGING = {
    "log_level": "INFO",          # 日志级别
    "max_log_files": 10,          # 最大日志文件数
    "log_file_size_mb": 10,       # 单个日志文件最大大小(MB)
}