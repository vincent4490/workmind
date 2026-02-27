#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
查找使用相同图片的重复元素
"""

import os
import sys
from pathlib import Path
from collections import defaultdict

# 添加项目路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from apps.ui_test.models import UiElement

def find_duplicate_elements():
    """查找使用相同图片的元素"""
    elements = UiElement.objects.filter(element_type='image', is_active=True)
    
    # 按 file_hash 分组
    hash_groups = defaultdict(list)
    no_hash_elements = []
    
    for elem in elements:
        file_hash = elem.config.get('file_hash')
        if file_hash:
            hash_groups[file_hash].append(elem)
        else:
            no_hash_elements.append(elem)
    
    # 打印重复的元素
    print("=" * 80)
    print("重复的图片元素：")
    print("=" * 80)
    
    duplicate_count = 0
    for file_hash, elems in hash_groups.items():
        if len(elems) > 1:
            duplicate_count += 1
            print(f"\nHash: {file_hash}")
            print(f"图片路径: {elems[0].config.get('image_path', 'N/A')}")
            print(f"使用该图片的元素：")
            for elem in elems:
                print(f"  - ID: {elem.id}, Name: {elem.name}, 使用次数: {elem.usage_count}")
    
    if duplicate_count == 0:
        print("✅ 没有发现重复的图片元素")
    else:
        print(f"\n⚠️ 发现 {duplicate_count} 组重复的图片")
    
    # 打印没有 Hash 的元素
    if no_hash_elements:
        print("\n" + "=" * 80)
        print("没有 file_hash 的元素（旧数据）：")
        print("=" * 80)
        for elem in no_hash_elements:
            print(f"  - ID: {elem.id}, Name: {elem.name}, Path: {elem.config.get('image_path', 'N/A')}")
        print(f"\n⚠️ 共 {len(no_hash_elements)} 个元素没有 Hash")
    
    return duplicate_count, len(no_hash_elements)

if __name__ == '__main__':
    print("开始检查重复的图片元素...\n")
    dup_count, no_hash_count = find_duplicate_elements()
    
    if dup_count > 0:
        print("\n建议：")
        print("1. 保留使用次数多的元素")
        print("2. 删除其他重复的元素")
        print("3. 或者如果图片确实不同，重新上传正确的图片")
    
    if no_hash_count > 0:
        print("\n建议：")
        print("运行 fix_missing_file_hash.py 脚本为旧数据补充 Hash")
