#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理已存在的markdown文件，删除反爬虫警告和无价值信息
"""

import os
import re
from pathlib import Path

def clean_anti_crawler_content(markdown_content: str) -> str:
    """清理反爬虫警告和无价值信息"""
    lines = markdown_content.split('\n')
    cleaned_lines = []
    skip_next_lines = 0
    in_metadata = False
    
    # 定义需要过滤的内容模式
    filter_patterns = [
        r'不支持当前浏览器',
        r'请更换浏览器',
        r'推荐使用谷歌浏览器',
        r'360浏览器极速模式',
        r'火狐浏览器',
        r'Edge浏览器',
        r'红山开源社区-黑色',
        r'登录\[注册\]',
        r'!\[\]\(https://www\.osredm\.com/images/avatars/',
        r'!\[红山开源社区',
    ]
    
    # 定义导航菜单模式
    nav_patterns = [
        r'\* \[首页\]',
        r'\* \[开源项目\]', 
        r'\* \[创客空间\]',
        r'\* \[开放竞赛\]',
        r'\* \[社区动态\]',
        r'\* \[成果库\]',
        r'\* \[资源库\]',
        r'\* \[公告\]',
        r'\* \[Bot市场\]',
    ]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 保留元数据部分
        if line.strip() == '---':
            if not in_metadata:
                in_metadata = True
                cleaned_lines.append(line)
                i += 1
                continue
            else:
                in_metadata = False
                cleaned_lines.append(line)
                i += 1
                continue
        
        if in_metadata:
            cleaned_lines.append(line)
            i += 1
            continue
        
        # 跳过已标记要跳过的行
        if skip_next_lines > 0:
            skip_next_lines -= 1
            i += 1
            continue
        
        line_strip = line.strip()
        
        # 检查是否是反爬虫警告行
        is_filter_line = any(re.search(pattern, line_strip, re.IGNORECASE) for pattern in filter_patterns)
        
        # 检查是否是导航菜单行
        is_nav_line = any(re.search(pattern, line_strip, re.IGNORECASE) for pattern in nav_patterns)
        
        if is_filter_line:
            # 找到反爬虫警告，跳过后续相关行
            if '不支持当前浏览器' in line_strip:
                skip_next_lines = 2  # 跳过后续的推荐浏览器行
            i += 1
            continue
        elif is_nav_line:
            # 检测到导航菜单开始，跳过整个导航块
            nav_count = 0
            j = i
            while j < len(lines) and nav_count < 15:  # 最多跳过15行导航
                curr_line = lines[j].strip()
                if any(re.search(pattern, curr_line, re.IGNORECASE) for pattern in nav_patterns):
                    nav_count += 1
                    j += 1
                elif curr_line.startswith('* [') and 'osredm.com' in curr_line:
                    # 其他包含osredm.com的导航链接
                    j += 1
                else:
                    break
            i = j
            continue
        elif line_strip.startswith('![') and 'osredm.com/images' in line_strip:
            # 跳过网站Logo和头像图片
            i += 1
            continue
        elif not line_strip:
            # 保留空行，但避免连续空行
            if cleaned_lines and cleaned_lines[-1].strip():
                cleaned_lines.append(line)
            i += 1
            continue
        else:
            # 保留有价值的内容行
            cleaned_lines.append(line)
            i += 1
    
    # 移除开头和结尾的空行
    while cleaned_lines and not cleaned_lines[0].strip():
        cleaned_lines.pop(0)
    while cleaned_lines and not cleaned_lines[-1].strip():
        cleaned_lines.pop()
    
    return '\n'.join(cleaned_lines)

def clean_existing_markdown_files():
    """清理已存在的markdown文件"""
    markdown_dir = Path("markdown")
    
    if not markdown_dir.exists():
        print("❌ markdown目录不存在")
        return
    
    md_files = list(markdown_dir.glob("*.md"))
    total_files = len(md_files)
    
    if total_files == 0:
        print("📁 markdown目录中没有找到.md文件")
        return
    
    print(f"🔍 找到 {total_files} 个markdown文件，开始清理...")
    
    processed = 0
    total_lines_removed = 0
    
    for md_file in md_files:
        try:
            # 读取原文件
            with open(md_file, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # 清理内容
            cleaned_content = clean_anti_crawler_content(original_content)
            
            # 计算清理效果
            original_lines = len(original_content.split('\n'))
            cleaned_lines = len(cleaned_content.split('\n'))
            lines_removed = original_lines - cleaned_lines
            
            # 只有内容发生变化才重新写入
            if lines_removed > 0:
                with open(md_file, 'w', encoding='utf-8') as f:
                    f.write(cleaned_content)
                
                total_lines_removed += lines_removed
                print(f"✅ {md_file.name}: 清理了 {lines_removed} 行无效内容")
            else:
                print(f"⏭️  {md_file.name}: 无需清理")
            
            processed += 1
            
            # 显示进度
            if processed % 100 == 0:
                print(f"📊 进度: {processed}/{total_files} ({processed/total_files*100:.1f}%)")
                
        except Exception as e:
            print(f"❌ 处理文件 {md_file.name} 时出错: {e}")
    
    print(f"\n🎉 清理完成!")
    print(f"📊 处理文件: {processed}/{total_files}")
    print(f"🗑️  总共清理: {total_lines_removed} 行无效内容")
    print(f"💾 所有文件已更新，反爬虫警告信息已删除")

if __name__ == "__main__":
    clean_existing_markdown_files()