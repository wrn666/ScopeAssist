"""
URL清理工具 - 清理已发现的无效URL
"""
import json
import re
from urllib.parse import urlparse
from pathlib import Path

def is_valid_crawl_url(url: str, domain: str) -> bool:
    """检查URL是否适合爬取"""
    # 文件扩展名黑名单
    file_extensions = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.zip', '.rar', '.7z', '.tar', '.gz',
        '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv',
        '.exe', '.msi', '.dmg', '.apk', '.css', '.js', '.xml', '.json'
    }
    
    # URL路径关键词黑名单
    path_blacklist = {
        '/images/', '/img/', '/assets/', '/static/', '/media/',
        '/download/', '/file/', '/attachment/', '/avatar/',
        '/thumbnail/', '/thumb/', '/cache/', '/temp/',
        '/api/', '/ajax/', '/json/', '/xml/', '/rss/'
    }
    
    # 解析URL
    parsed = urlparse(url)
    
    # 检查域名
    if parsed.netloc != domain:
        return False
        
    path = parsed.path.lower()
    
    # 检查文件扩展名
    for ext in file_extensions:
        if path.endswith(ext):
            return False
            
    # 检查路径关键词
    for keyword in path_blacklist:
        if keyword in path:
            return False
            
    # 检查查询参数中的文件标识
    if parsed.query:
        query_lower = parsed.query.lower()
        if any(param in query_lower for param in ['download', 'file', 'attachment']):
            return False
            
    # 特殊处理：头像和图标URL模式
    if re.search(r'/(avatar|icon|logo|banner|thumb)', path):
        return False
        
    return True

def clean_urls():
    """清理URL文件"""
    urls_file = Path("urls_discovered.json")
    
    if not urls_file.exists():
        print("未找到 urls_discovered.json 文件")
        return
    
    print("正在清理无效URL...")
    
    # 读取现有数据
    with open(urls_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    discovered = set(data.get('discovered', []))
    completed = set(data.get('completed', []))
    failed = set(data.get('failed', []))
    
    print(f"清理前: 发现 {len(discovered)} 个URL")
    
    # 过滤URL
    domain = "www.osredm.com"
    valid_discovered = set()
    invalid_count = 0
    
    for url in discovered:
        if is_valid_crawl_url(url, domain):
            valid_discovered.add(url)
        else:
            invalid_count += 1
            failed.add(url)  # 将无效URL标记为失败
    
    print(f"清理后: 有效 {len(valid_discovered)} 个URL")
    print(f"移除了 {invalid_count} 个无效URL")
    
    # 更新数据
    cleaned_data = {
        'discovered': list(valid_discovered),
        'completed': list(completed),
        'failed': list(failed),
        'last_updated': data.get('last_updated', ''),
        'cleaned': True,
        'cleaned_count': invalid_count
    }
    
    # 保存清理后的数据
    with open(urls_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
    
    print("✅ URL清理完成")
    print(f"📁 清理结果已保存到 {urls_file}")

if __name__ == "__main__":
    clean_urls()