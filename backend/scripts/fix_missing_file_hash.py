#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
为缺失 file_hash 的元素补充 Hash
"""

import os
import sys
import hashlib
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from apps.ui_test.models import UiElement

def calculate_file_hash(file_path):
    """计算文件 Hash"""
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            return hashlib.md5(content).hexdigest()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def fix_missing_file_hash():
    """为缺失 file_hash 的元素补充 Hash"""
    elements = UiElement.objects.filter(element_type='image', is_active=True)
    template_base = Path(__file__).resolve().parent.parent / 'apps' / 'ui_test' / 'Template'
    
    fixed_count = 0
    error_count = 0
    skipped_count = 0
    
    for elem in elements:
        file_hash = elem.config.get('file_hash')
        
        # 如果已经有 Hash，跳过
        if file_hash:
            skipped_count += 1
            continue
        
        image_path = elem.config.get('image_path')
        if not image_path:
            print(f"[跳过] 元素 {elem.id} ({elem.name}): 没有 image_path")
            continue
        
        # 计算 Hash
        full_path = template_base / image_path
        if not full_path.exists():
            print(f"[错误] 元素 {elem.id} ({elem.name}): 文件不存在 {full_path}")
            error_count += 1
            continue
        
        new_hash = calculate_file_hash(full_path)
        if not new_hash:
            error_count += 1
            continue
        
        # 更新 Hash
        elem.config['file_hash'] = new_hash
        elem.save()
        
        print(f"[修复] 元素 {elem.id} ({elem.name}): Hash = {new_hash}")
        fixed_count += 1
    
    print("\n" + "=" * 80)
    print(f"✅ 修复了 {fixed_count} 个元素")
    print(f"⏭️  跳过了 {skipped_count} 个已有 Hash 的元素")
    print(f"❌ {error_count} 个错误")
    print("=" * 80)

if __name__ == '__main__':
    print("开始修复缺失的 file_hash...\n")
    print("⚠️  警告：执行前请确保已备份数据库！\n")
    
    response = input("确定要继续吗？(yes/no): ")
    if response.lower() != 'yes':
        print("已取消")
        sys.exit(0)
    
    fix_missing_file_hash()
