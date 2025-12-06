#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理死循环URL工具
修复已发现的循环URL，移除重复的page参数
"""

import json
import re
from urllib.parse import urlparse
from datetime import datetime

def is_loop_url(url: str) -> bool:
    """检测是否为循环URL"""
    path = urlparse(url).path
    
    # 检查重复的page模式
    page_count = path.count('/page/')
    if page_count > 2:
        return True
        
    # 检查路径长度
    if len(path) > 150:
        return True
        
    # 检查重复的数字序列
    page_numbers = re.findall(r'/page/(\d+)', path)
    if len(page_numbers) > 2:
        if len(set(page_numbers)) < len(page_numbers):
            return True
            
    return False

def normalize_url(url: str) -> str:
    """规范化URL，移除重复的page参数"""
    parsed = urlparse(url)
    path = parsed.path
    
    # 清理重复的page路径
    if '/page/' in path and path.count('/page/') > 1:
        parts = path.split('/page/')
        if len(parts) > 1:
            base_part = parts[0]
            # 找到最后一个有效的数字页码
            last_valid_page = None
            for part in reversed(parts[1:]):
                page_match = re.match(r'^(\d+)', part)
                if page_match:
                    last_valid_page = page_match.group(1)
                    break
            
            if last_valid_page:
                path = f"{base_part}/page/{last_valid_page}"
            else:
                path = base_part
    
    clean_url = f"{parsed.scheme}://{parsed.netloc}{path}"
    if parsed.query:
        clean_url += f"?{parsed.query}"
    if parsed.fragment:
        clean_url += f"#{parsed.fragment}"
    
    return clean_url

def clean_discovered_urls():
    """清理urls_discovered.json中的循环URL"""
    try:
        with open('urls_discovered.json', 'r', encoding='utf-8') as f:
            url_data = json.load(f)
    except FileNotFoundError:
        print("❌ 未找到urls_discovered.json文件")
        return
    
    print("🔍 开始检查和清理循环URL...")
    
    # 统计信息
    original_discovered = len(url_data['discovered'])
    original_completed = len(url_data['completed'])
    original_failed = len(url_data['failed'])
    
    # 清理discovered URLs
    clean_discovered = []
    loop_urls_found = []
    normalized_urls = {}
    
    for url in url_data['discovered']:
        if is_loop_url(url):
            loop_urls_found.append(url)
            # 尝试规范化
            normalized = normalize_url(url)
            if not is_loop_url(normalized):
                if normalized not in normalized_urls:
                    normalized_urls[normalized] = []
                normalized_urls[normalized].append(url)
                clean_discovered.append(normalized)
        else:
            clean_discovered.append(url)
    
    # 去重
    clean_discovered = list(set(clean_discovered))
    
    # 清理completed URLs
    clean_completed = []
    for url in url_data['completed']:
        if is_loop_url(url):
            normalized = normalize_url(url)
            if not is_loop_url(normalized):
                clean_completed.append(normalized)
        else:
            clean_completed.append(url)
    
    clean_completed = list(set(clean_completed))
    
    # 清理failed URLs
    clean_failed = []
    for url in url_data['failed']:
        if not is_loop_url(url):
            clean_failed.append(url)
    
    # 更新数据
    url_data['discovered'] = clean_discovered
    url_data['completed'] = clean_completed
    url_data['failed'] = clean_failed
    url_data['last_updated'] = datetime.now().isoformat()
    
    # 保存清理后的文件
    with open('urls_discovered.json', 'w', encoding='utf-8') as f:
        json.dump(url_data, f, ensure_ascii=False, indent=2)
    
    # 输出统计信息
    print(f"\n📊 清理结果:")
    print(f"原始discovered URLs: {original_discovered}")
    print(f"清理后discovered URLs: {len(clean_discovered)}")
    print(f"发现的循环URLs: {len(loop_urls_found)}")
    print(f"原始completed URLs: {original_completed}")
    print(f"清理后completed URLs: {len(clean_completed)}")
    print(f"原始failed URLs: {original_failed}")
    print(f"清理后failed URLs: {len(clean_failed)}")
    
    if loop_urls_found:
        print(f"\n🔄 循环URL示例（前5个）:")
        for url in loop_urls_found[:5]:
            print(f"  - {url}")
        
        if len(normalized_urls) > 0:
            print(f"\n✅ 规范化示例:")
            for normalized, originals in list(normalized_urls.items())[:3]:
                print(f"  {originals[0]} -> {normalized}")
    
    print(f"\n✅ 清理完成！已保存到 urls_discovered.json")
    
    remaining = len(clean_discovered) - len(clean_completed) - len(clean_failed)
    print(f"📈 当前进度: {len(clean_completed)}/{len(clean_discovered)} ({len(clean_completed)/len(clean_discovered)*100:.1f}%)")
    print(f"🔄 剩余待爬取: {remaining} 个URL")

if __name__ == "__main__":
    clean_discovered_urls()