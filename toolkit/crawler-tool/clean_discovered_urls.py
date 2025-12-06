#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理已发现的URL列表，去除重复、无效和用户个人信息页面
"""

import json
import re
from urllib.parse import urlparse, parse_qs
from typing import Set, List

def should_keep_url(url: str) -> bool:
    """判断URL是否应该保留"""
    
    # 用户个人信息页面关键词黑名单
    personal_page_keywords = [
        '/following', '/followers', '/organizes', '/statistics', 
        '/stargazers', '/watchers', '/projects', '/settings',
        '/profile', '/activity', '/contributions', '/stars'
    ]
    
    # 解析URL
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    # 检查用户个人信息页面
    for keyword in personal_page_keywords:
        if keyword in path:
            return False
    
    # 过滤过度嵌套的page参数（防止死循环）
    if parsed.query:
        query_lower = parsed.query.lower()
        # 检查page参数嵌套深度
        page_count = query_lower.count('page=')
        if page_count > 1:  # 超过1层page嵌套就过滤
            return False
    
    # 检查路径中的page嵌套（如 /page/5/page/53）
    page_segments = path.count('/page/')
    if page_segments > 1:  # 超过1层page路径就过滤
        return False
        
    # 过滤特定的重复项目模式（CPM-9G-8B相关的过深嵌套）
    if 'cpm-9g-8b' in path.lower():
        # 如果是commits页面且有嵌套，则过滤
        if '/commits/' in path and '/page/' in path:
            return False
        # 过滤过深的tree和blob路径
        if any(deep_path in path for deep_path in ['/tree/', '/blob/']) and '/page/' in path:
            return False
            
    # 过滤文件下载URL
    file_extensions = ['.zip', '.tar', '.gz', '.pdf', '.doc', '.xls', '.ppt']
    for ext in file_extensions:
        if path.endswith(ext):
            return False
    
    # 过滤API和静态资源
    if any(api_path in path for api_path in ['/api/', '/images/', '/assets/', '/static/']):
        return False
    
    return True

def normalize_url(url: str) -> str:
    """规范化URL，去除无意义的参数"""
    parsed = urlparse(url)
    
    # 保留重要的查询参数
    if parsed.query:
        params = parse_qs(parsed.query)
        important_params = {}
        
        # 只保留重要参数
        for key, values in params.items():
            if key.lower() in ['page', 'p', 'type', 'branch', 'tab']:
                important_params[key] = values[0]
        
        # 重新构建查询字符串
        if important_params:
            query_parts = [f"{k}={v}" for k, v in important_params.items()]
            new_query = "&".join(query_parts)
        else:
            new_query = ""
    else:
        new_query = ""
    
    # 重新构建URL
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if new_query:
        normalized += f"?{new_query}"
    
    return normalized

def clean_discovered_urls():
    """清理已发现的URL列表"""
    
    # 读取当前的URL列表
    try:
        with open('urls_discovered.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        discovered_urls = data.get('discovered', [])
        print(f"原始URL数量: {len(discovered_urls)}")
        
        # 过滤和去重
        valid_urls = set()
        filtered_out = {
            'personal_pages': 0,
            'deep_nesting': 0,
            'file_downloads': 0,
            'duplicates': 0
        }
        
        for url in discovered_urls:
            if should_keep_url(url):
                normalized = normalize_url(url)
                if normalized not in valid_urls:
                    valid_urls.add(normalized)
                else:
                    filtered_out['duplicates'] += 1
            else:
                # 统计过滤原因
                path = urlparse(url).path.lower()
                if any(kw in path for kw in ['/following', '/followers', '/organizes', '/statistics']):
                    filtered_out['personal_pages'] += 1
                elif '/page/' in path and path.count('/page/') > 1:
                    filtered_out['deep_nesting'] += 1
                elif any(ext in path for ext in ['.zip', '.pdf', '.doc']):
                    filtered_out['file_downloads'] += 1
        
        # 转换回列表并排序
        cleaned_urls = sorted(list(valid_urls))
        
        # 更新数据
        data['discovered'] = cleaned_urls
        
        # 保存清理后的URL列表
        with open('urls_discovered_cleaned.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 替换原文件
        with open('urls_discovered.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n清理完成:")
        print(f"清理后URL数量: {len(cleaned_urls)}")
        print(f"过滤掉的URL数量: {len(discovered_urls) - len(cleaned_urls)}")
        print(f"  - 用户个人信息页面: {filtered_out['personal_pages']}")
        print(f"  - 过度嵌套页面: {filtered_out['deep_nesting']}")
        print(f"  - 文件下载链接: {filtered_out['file_downloads']}")
        print(f"  - 重复URL: {filtered_out['duplicates']}")
        
        # 显示一些清理后的URL样例
        print(f"\n清理后的URL样例:")
        for i, url in enumerate(cleaned_urls[:10]):
            print(f"  {i+1}. {url}")
        
        return len(discovered_urls), len(cleaned_urls)
        
    except FileNotFoundError:
        print("未找到 urls_discovered.json 文件")
        return 0, 0
    except Exception as e:
        print(f"清理过程中出错: {e}")
        return 0, 0

if __name__ == "__main__":
    clean_discovered_urls()