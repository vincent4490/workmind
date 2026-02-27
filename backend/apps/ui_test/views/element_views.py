# -*- coding: utf-8 -*-
"""
UI元素管理视图
统一管理图片、坐标、区域元素
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.http import HttpResponse, FileResponse
from django.db.models import Q, Count
from pathlib import Path
import hashlib
import logging

from ..models import UiElement
from ..serializers import UiElementSerializer, UiElementListSerializer

logger = logging.getLogger(__name__)


class UiElementViewSet(viewsets.ModelViewSet):
    """UI元素管理视图集"""
    
    queryset = UiElement.objects.filter(is_active=True)
    serializer_class = UiElementSerializer
    
    def get_serializer_class(self):
        """列表页用简化版序列化器"""
        if self.action == 'list':
            return UiElementListSerializer
        return UiElementSerializer
    
    def get_queryset(self):
        """支持筛选和搜索"""
        queryset = super().get_queryset()
        
        # 按类型筛选
        element_type = self.request.query_params.get('element_type')
        if element_type and element_type != 'all' and element_type != '':
            queryset = queryset.filter(element_type=element_type)
        
        # 关键词搜索（名称、标签）
        keyword = self.request.query_params.get('keyword')
        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword)
            )
        
        # 按标签筛选
        tag = self.request.query_params.get('tag')
        if tag:
            queryset = queryset.filter(tags__contains=tag)
        
        return queryset.order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """列表接口（支持分页）"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # 分页处理
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            return Response({
                'code': 0,
                'msg': 'success',
                'data': {
                    'results': response.data.get('results', []),
                    'count': response.data.get('count', 0)
                }
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': {
                'results': serializer.data,
                'count': len(serializer.data)
            }
        })
    
    def create(self, request, *args, **kwargs):
        """创建元素"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # 设置创建人
        serializer.save(created_by=request.user)
        
        logger.info(f"用户 {request.user.username} 创建了元素: {serializer.data['name']}")
        
        return Response({
            'code': 0,
            'msg': '创建成功',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """更新元素"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        logger.info(f"用户 {request.user.username} 更新了元素: {instance.name}")
        
        return Response({
            'code': 0,
            'msg': '更新成功',
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """删除元素（硬删除 + 删除图片文件）"""
        instance = self.get_object()
        element_name = instance.name
        
        # 如果是图片类型，删除文件
        if instance.element_type == 'image':
            image_path = self.get_template_base_path() / instance.config.get('image_path', '')
            if image_path.exists():
                try:
                    image_path.unlink()
                    logger.info(f"删除图片文件: {image_path}")
                except Exception as e:
                    logger.error(f"删除图片文件失败: {e}")
                    return Response({
                        'code': 1,
                        'msg': f'删除图片文件失败: {str(e)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # 硬删除（真正删除数据库记录）
        instance.delete()
        
        logger.info(f"用户 {request.user.username} 删除了元素: {element_name}")
        
        return Response({
            'code': 0,
            'msg': '删除成功'
        }, status=status.HTTP_200_OK)
    
    # ========== 自定义接口 ==========
    
    @action(detail=False, methods=['post'])
    def upload_image(self, request):
        """上传图片文件"""
        file = request.FILES.get('file')
        image_category = request.data.get('image_category', 'common')
        element_id = request.data.get('element_id')  # 编辑模式下的元素ID
        
        if not file:
            return Response({'code': 1, 'msg': '未上传文件'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 验证文件类型
        if not file.name.lower().endswith(('.png', '.jpg', '.jpeg')):
            return Response({'code': 1, 'msg': '只支持 PNG/JPG 格式'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 计算文件hash（防止重复上传）
        file.seek(0)
        file_content = file.read()
        file_hash = hashlib.md5(file_content).hexdigest()
        file.seek(0)
        
        # 构建 image_path 用于检查
        image_path = f"{image_category}/{file.name}"
        
        # 双重检查：1. 文件名检查（防止重复截图）
        existing_path_query = UiElement.objects.filter(
            element_type='image',
            config__image_path=image_path,
            is_active=True
        )
        
        # 如果是编辑模式，排除当前元素
        if element_id:
            existing_path_query = existing_path_query.exclude(id=element_id)
        
        existing_by_path = existing_path_query.first()
        
        if existing_by_path:
            return Response({
                'code': 1,
                'msg': f'文件名冲突：元素 "{existing_by_path.name}" 已使用该文件名',
                'detail': f'已有元素使用文件：{image_path}',
                'suggestion': '请使用不同的文件名，或直接使用已有元素',
                'data': {
                    'existing_element': {
                        'id': existing_by_path.id,
                        'name': existing_by_path.name,
                        'reason': 'filename_conflict'
                    }
                }
            })
        
        # 双重检查：2. 内容Hash检查（防止改名绕过）
        existing_hash_query = UiElement.objects.filter(
            element_type='image',
            config__file_hash=file_hash,
            is_active=True
        )
        
        # 如果是编辑模式，排除当前元素
        if element_id:
            existing_hash_query = existing_hash_query.exclude(id=element_id)
        
        existing_by_hash = existing_hash_query.first()
        
        if existing_by_hash:
            return Response({
                'code': 1,
                'msg': f'内容重复：元素 "{existing_by_hash.name}" 已使用相同内容的图片',
                'detail': f'已有元素使用该图片内容（Hash: {file_hash[:8]}...）',
                'suggestion': '如需使用该图片，请直接使用已有元素；如确实是不同元素，请确保图片内容确实不同',
                'data': {
                    'existing_element': {
                        'id': existing_by_hash.id,
                        'name': existing_by_hash.name,
                        'image_path': existing_by_hash.config.get('image_path', ''),
                        'reason': 'content_duplicate'
                    }
                }
            })
        
        # 保存文件
        template_base = self.get_template_base_path() / image_category
        template_base.mkdir(parents=True, exist_ok=True)
        
        # 直接使用文件名，如果存在则覆盖
        file_path = template_base / file.name
        
        # 保存文件（覆盖模式）
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # 返回相对路径
        relative_path = f"{image_category}/{file_path.name}"
        
        logger.info(f"用户 {request.user.username} 上传图片: {relative_path}")
        
        return Response({
            'code': 0,
            'msg': '上传成功',
            'data': {
                'image_path': relative_path,
                'file_name': file_path.name,
                'file_hash': file_hash,
                'file_size': file_path.stat().st_size
            }
        })
    
    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def preview(self, request, pk=None):
        """预览图片（允许匿名访问）"""
        element = self.get_object()
        
        if element.element_type != 'image':
            return Response({'code': 1, 'msg': '非图片类型元素'}, status=status.HTTP_400_BAD_REQUEST)
        
        image_path = self.get_template_base_path() / element.config.get('image_path', '')
        
        if not image_path.exists():
            logger.warning(f"图片文件不存在: {image_path}")
            return Response({'code': 1, 'msg': '图片文件不存在'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            return FileResponse(open(image_path, 'rb'), content_type='image/png')
        except Exception as e:
            logger.error(f"读取图片失败: {e}")
            return Response({'code': 1, 'msg': f'读取图片失败: {str(e)}'}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def image_categories(self, request):
        """获取所有图片分类（扫描 Template 目录）"""
        template_base = self.get_template_base_path()
        categories = []
        
        try:
            if template_base.exists() and template_base.is_dir():
                for item in template_base.iterdir():
                    if item.is_dir() and not item.name.startswith('.'):
                        categories.append(item.name)
            
            # 排序，但确保 common 始终在第一位
            categories = sorted(categories)
            if 'common' in categories:
                categories.remove('common')
                categories.insert(0, 'common')
        except Exception as e:
            logger.warning(f"扫描 Template 目录失败: {e}")
            categories = ['common']  # 失败时至少返回 common
        
        return Response({
            'code': 0,
            'data': categories
        })
    
    @action(detail=False, methods=['post'])
    def create_image_category(self, request):
        """创建新的图片分类（创建目录）"""
        category_name = request.data.get('name', '').strip()
        
        if not category_name:
            return Response({'code': 1, 'msg': '分类名称不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 验证分类名称（只允许字母、数字、下划线、中划线）
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', category_name):
            return Response({'code': 1, 'msg': '分类名称只能包含字母、数字、下划线和中划线'}, status=status.HTTP_400_BAD_REQUEST)
        
        template_base = self.get_template_base_path()
        new_category_path = template_base / category_name
        
        # 检查是否已存在
        if new_category_path.exists():
            return Response({'code': 1, 'msg': f'分类 "{category_name}" 已存在'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 创建目录
        try:
            new_category_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"用户 {request.user.username} 创建了图片分类: {category_name}")
            
            return Response({
                'code': 0,
                'msg': '创建成功',
                'data': {
                    'name': category_name
                }
            })
        except Exception as e:
            logger.error(f"创建图片分类失败: {e}")
            return Response({'code': 1, 'msg': f'创建失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def delete_image_category(self, request):
        """删除图片分类（只能删除空目录）"""
        category_name = request.data.get('name', '').strip()
        
        if not category_name:
            return Response({'code': 1, 'msg': '分类名称不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 禁止删除 common
        if category_name == 'common':
            return Response({'code': 1, 'msg': '不能删除默认分类 common'}, status=status.HTTP_400_BAD_REQUEST)
        
        template_base = self.get_template_base_path()
        category_path = template_base / category_name
        
        # 检查是否存在
        if not category_path.exists():
            return Response({'code': 1, 'msg': '分类不存在'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查是否为空目录
        if list(category_path.glob('*')):
            return Response({
                'code': 1, 
                'msg': '该分类下还有文件，请先删除或移动所有文件后再删除分类'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 删除空目录
        try:
            category_path.rmdir()
            logger.info(f"用户 {request.user.username} 删除了空分类: {category_name}")
            
            return Response({
                'code': 0,
                'msg': '删除成功'
            })
        except Exception as e:
            logger.error(f"删除图片分类失败: {e}")
            return Response({'code': 1, 'msg': f'删除失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def tags(self, request):
        """获取所有标签"""
        elements = UiElement.objects.filter(is_active=True)
        all_tags = set()
        
        for element in elements:
            if element.tags:
                all_tags.update(element.tags)
        
        return Response({
            'code': 0,
            'data': sorted(list(all_tags))
        })
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """复制元素"""
        element = self.get_object()
        
        # 生成新名称（避免重复）
        new_name = f"{element.name}_副本"
        counter = 1
        while UiElement.objects.filter(name=new_name, is_active=True).exists():
            new_name = f"{element.name}_副本{counter}"
            counter += 1
        
        # 创建副本
        new_element = UiElement.objects.create(
            name=new_name,
            element_type=element.element_type,
            tags=element.tags.copy() if element.tags else [],
            config=element.config.copy() if element.config else {},
            resolution_configs=element.resolution_configs.copy() if element.resolution_configs else {},
            created_by=request.user
        )
        
        logger.info(f"用户 {request.user.username} 复制了元素: {element.name} -> {new_name}")
        
        serializer = self.get_serializer(new_element)
        return Response({
            'code': 0,
            'msg': '复制成功',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['post'])
    def batch_delete(self, request):
        """批量删除（硬删除）"""
        ids = request.data.get('ids', [])
        
        if not ids:
            return Response({'code': 1, 'msg': '请选择要删除的元素'}, status=status.HTTP_400_BAD_REQUEST)
        
        elements = UiElement.objects.filter(id__in=ids, is_active=True)
        count = elements.count()
        
        # 删除图片文件
        for element in elements:
            if element.element_type == 'image':
                image_path = self.get_template_base_path() / element.config.get('image_path', '')
                if image_path.exists():
                    try:
                        image_path.unlink()
                        logger.info(f"删除图片文件: {image_path}")
                    except Exception as e:
                        logger.error(f"删除图片文件失败: {e}")
        
        # 硬删除（真正删除数据库记录）
        elements.delete()
        
        logger.info(f"用户 {request.user.username} 批量删除了 {count} 个元素")
        
        return Response({
            'code': 0,
            'msg': f'成功删除 {count} 个元素'
        })
    
    @action(detail=True, methods=['post'])
    def record_usage(self, request, pk=None):
        """记录元素使用"""
        element = self.get_object()
        
        try:
            element.increment_usage()
            logger.info(f"记录元素使用: {element.name}, 使用次数: {element.usage_count}")
            
            return Response({
                'code': 0,
                'msg': '记录成功',
                'data': {
                    'usage_count': element.usage_count,
                    'last_used_at': element.last_used_at
                }
            })
        except Exception as e:
            logger.error(f"记录元素使用失败: {e}")
            return Response({
                'code': 1,
                'msg': f'记录失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # ========== 辅助方法 ==========
    
    def get_template_base_path(self):
        """获取模板基础路径"""
        # __file__ = .../views/element_views.py
        # .parent = .../views/
        # .parent.parent = .../ui_test/
        return Path(__file__).resolve().parent.parent / "Template"
