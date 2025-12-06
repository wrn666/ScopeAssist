#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试URL过滤逻辑，确保个人信息页面被正确过滤
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from urllib.parse import urlparse
import re

def is_valid_crawl_url(url: str) -> bool:
    """测试版本的URL过滤函数"""
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
    
    # 用户个人信息页面关键词黑名单
    personal_page_keywords = {
        '/following', '/followers', '/organizes', '/statistics', 
        '/stargazers', '/watchers', '/projects', '/settings',
        '/profile', '/activity', '/contributions', '/stars'
    }
    
    # 项目开发细节页面关键词黑名单
    development_detail_keywords = {
        '/commits/', '/commit/', '/compare/', '/diff/', '/patch/',
        '/blame/', '/history/', '/tree/', '/blob/', '/raw/',
        '/archive/', '/releases/download/', '/zipball/', '/tarball/'
    }
    
    # 解析URL
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    # 检查文件扩展名
    for ext in file_extensions:
        if path.endswith(ext):
            return False
            
    # 检查路径关键词
    for keyword in path_blacklist:
        if keyword in path:
            return False
    
    # 检查用户个人信息页面
    for keyword in personal_page_keywords:
        if keyword in path:
            return False
    
    # 检查项目开发细节页面
    for keyword in development_detail_keywords:
        if keyword in path:
            return False
    
    # 过滤过度嵌套的page参数
    if parsed.query:
        query_lower = parsed.query.lower()
        if any(param in query_lower for param in ['download', 'file', 'attachment']):
            return False
        
        page_count = query_lower.count('page=')
        if page_count > 2:
            return False
    
    # 检查路径中的page嵌套
    page_segments = path.count('/page/')
    if page_segments > 2:
        return False
        
    # 特殊处理：头像和图标URL模式
    if re.search(r'/(avatar|icon|logo|banner|thumb)', path):
        return False
        
    return True

def test_url_filtering():
    """测试URL过滤功能"""
    
    # 应该被过滤的URL样例
    should_be_filtered = [
        # 个人信息页面
        "https://www.osredm.com/p73921604/organizes/page=8",
        "https://www.osredm.com/p24698351/following",
        "https://www.osredm.com/user123/followers/page/5",
        "https://www.osredm.com/p12345/statistics",
        "https://www.osredm.com/user456/stargazers",
        "https://www.osredm.com/profile/user789",
        
        # 开发详细页面
        "https://www.osredm.com/p81745296/idrlnet/commits/3a19a3301d",
        "https://www.osredm.com/project/repo/commit/abc123",
        "https://www.osredm.com/repo/tree/master/src",
        "https://www.osredm.com/project/blob/main/readme.md",
        "https://www.osredm.com/compare/v1.0...v2.0",
        
        # 文件下载
        "https://www.osredm.com/files/document.pdf",
        "https://www.osredm.com/downloads/archive.zip",
        "https://www.osredm.com/images/logo.png"
    ]
    
    # 应该被保留的URL样例
    should_be_kept = [
        # 项目主页
        "https://www.osredm.com/jiuyuan/CPM-9G-8B",
        "https://www.osredm.com/project/awesome-ai",
        
        # Issues和讨论
        "https://www.osredm.com/project/repo/issues",
        "https://www.osredm.com/project/repo/issues/123",
        
        # 文档和说明
        "https://www.osredm.com/docs/tutorial",
        "https://www.osredm.com/project/wiki",
        
        # 竞赛和活动
        "https://www.osredm.com/competition/2025nlts",
        "https://www.osredm.com/task/taskDetail/394",
        
        # 简单分页
        "https://www.osredm.com/projects?page=2",
        "https://www.osredm.com/search?q=ai&page=3"
    ]
    
    print("=== URL过滤测试 ===\n")
    
    # 测试应该被过滤的URL
    print("测试应该被过滤的URL:")
    filtered_correctly = 0
    for url in should_be_filtered:
        result = is_valid_crawl_url(url)
        status = "✅ 正确过滤" if not result else "❌ 错误保留"
        print(f"  {status}: {url}")
        if not result:
            filtered_correctly += 1
    
    print(f"\n过滤准确率: {filtered_correctly}/{len(should_be_filtered)} ({filtered_correctly/len(should_be_filtered)*100:.1f}%)")
    
    # 测试应该被保留的URL
    print(f"\n测试应该被保留的URL:")
    kept_correctly = 0
    for url in should_be_kept:
        result = is_valid_crawl_url(url)
        status = "✅ 正确保留" if result else "❌ 错误过滤"
        print(f"  {status}: {url}")
        if result:
            kept_correctly += 1
    
    print(f"\n保留准确率: {kept_correctly}/{len(should_be_kept)} ({kept_correctly/len(should_be_kept)*100:.1f}%)")
    
    # 总体评估
    total_correct = filtered_correctly + kept_correctly
    total_tests = len(should_be_filtered) + len(should_be_kept)
    overall_accuracy = total_correct / total_tests * 100
    
    print(f"\n=== 测试总结 ===")
    print(f"总体准确率: {total_correct}/{total_tests} ({overall_accuracy:.1f}%)")
    
    if overall_accuracy >= 95:
        print("✅ 过滤逻辑工作良好，可以有效阻止个人信息页面爬取")
    elif overall_accuracy >= 80:
        print("⚠️ 过滤逻辑基本可用，但可能需要微调")
    else:
        print("❌ 过滤逻辑需要重大改进")
    
    return overall_accuracy

if __name__ == "__main__":
    test_url_filtering()