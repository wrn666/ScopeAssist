#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理重复的markdown文件，基于内容哈希去重
"""

import os
import hashlib
import json
from pathlib import Path

def get_file_hash(filepath):
    """计算文件内容的MD5哈希"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # 只对实际内容计算哈希，跳过元数据头
            if '---\n' in content:
                parts = content.split('---\n', 2)
                if len(parts) >= 3:
                    content = parts[2]  # 跳过前两个---之间的元数据
            return hashlib.md5(content.encode('utf-8')).hexdigest()
    except Exception as e:
        print(f"读取文件失败 {filepath}: {e}")
        return None

def clean_duplicate_markdowns():
    """清理重复的markdown文件"""
    
    markdown_dir = Path('markdown')
    if not markdown_dir.exists():
        print("markdown目录不存在")
        return
    
    print("正在扫描markdown文件...")
    
    # 扫描所有markdown文件
    md_files = list(markdown_dir.glob('*.md'))
    print(f"找到 {len(md_files)} 个markdown文件")
    
    # 计算文件哈希
    file_hashes = {}
    hash_to_files = {}
    
    for md_file in md_files:
        file_hash = get_file_hash(md_file)
        if file_hash:
            file_hashes[md_file] = file_hash
            if file_hash not in hash_to_files:
                hash_to_files[file_hash] = []
            hash_to_files[file_hash].append(md_file)
    
    # 找出重复文件
    duplicates = {h: files for h, files in hash_to_files.items() if len(files) > 1}
    
    print(f"发现 {len(duplicates)} 组重复内容")
    
    # 删除重复文件，保留第一个
    deleted_count = 0
    saved_space = 0
    
    for file_hash, files in duplicates.items():
        # 按文件名排序，保留第一个
        files.sort(key=lambda x: x.name)
        keep_file = files[0]
        
        print(f"\n内容哈希 {file_hash[:8]}... 有 {len(files)} 个重复文件:")
        print(f"  保留: {keep_file.name}")
        
        for duplicate_file in files[1:]:
            try:
                file_size = duplicate_file.stat().st_size
                duplicate_file.unlink()
                print(f"  删除: {duplicate_file.name} ({file_size} bytes)")
                deleted_count += 1
                saved_space += file_size
            except Exception as e:
                print(f"  删除失败 {duplicate_file.name}: {e}")
    
    print(f"\n清理完成:")
    print(f"删除了 {deleted_count} 个重复文件")
    print(f"节省空间: {saved_space / 1024 / 1024:.2f} MB")
    print(f"剩余文件: {len(md_files) - deleted_count}")

if __name__ == "__main__":
    os.chdir(r"d:\HuaweiMoveData\Users\21438\Desktop\红山网络怕爬虫")
    clean_duplicate_markdowns()