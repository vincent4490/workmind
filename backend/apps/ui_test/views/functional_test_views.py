# -*- coding: utf-8 -*-
"""
功能测试管理视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction, models
from django.http import HttpResponse
import logging
import io
import zipfile
import json
from datetime import datetime
import uuid

from backend.utils import pagination
from ..models import (
    FunctionalRequirement, FunctionalTestCase, Task,
    TestPlan, TestPlanCase, TestPlanCaseOperationLog
)
from ..serializers import (
    FunctionalRequirementSerializer, FunctionalTestCaseSerializer, TaskSerializer,
    TestPlanSerializer, TestPlanCaseSerializer, TestPlanCaseOperationLogSerializer
)
from ..utils.case_importers import get_importer

logger = logging.getLogger(__name__)


class FunctionalRequirementViewSet(viewsets.ModelViewSet):
    """功能测试需求视图集"""
    queryset = FunctionalRequirement.objects.all()  # type: ignore[attr-defined]
    serializer_class = FunctionalRequirementSerializer
    pagination_class = pagination.MyPageNumberPagination
    
    def get_queryset(self):
        """根据需求名称、测试团队、测试人员、状态、标签、创建时间过滤"""
        name = self.request.query_params.get('name', '').strip()
        requirement_name = self.request.query_params.get('requirement_name', '').strip()
        keyword = name or requirement_name
        test_team = self.request.query_params.get('test_team', '').strip()
        testers = self.request.query_params.get('testers', '').strip()
        status_val = self.request.query_params.get('status', '').strip()
        tags_val = self.request.query_params.get('tags', '').strip()
        created_at_after = self.request.query_params.get('created_at_after', '').strip()
        created_at_before = self.request.query_params.get('created_at_before', '').strip()

        queryset = FunctionalRequirement.objects.all().select_related('created_by')  # type: ignore[attr-defined]
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        if test_team:
            queryset = queryset.filter(test_team=test_team)
        if testers:
            queryset = queryset.filter(testers__icontains=testers)
        if status_val:
            queryset = queryset.filter(status=status_val)
        if tags_val:
            queryset = queryset.filter(tags__icontains=tags_val)
        if created_at_after:
            queryset = queryset.filter(created_at__date__gte=created_at_after)
        if created_at_before:
            queryset = queryset.filter(created_at__date__lte=created_at_before)
        return queryset.order_by('-updated_at')

    @action(detail=False, methods=['get'], url_path='test-team-options')
    def test_team_options(self, request):
        """返回所有出现过的测试团队（用于筛选下拉），去空格后去重，避免重复项"""
        values = (
            FunctionalRequirement.objects.all()
            .values_list('test_team', flat=True)
            .distinct()
        )
        seen = set()
        options = []
        for v in values:
            v_clean = (v or '').strip()
            if not v_clean or v_clean in seen:
                continue
            seen.add(v_clean)
            options.append(v_clean)
        options = sorted(options)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': options
        })

    @action(detail=False, methods=['get'], url_path='status-options')
    def status_options(self, request):
        """返回所有出现过的状态（用于筛选下拉），strip 后去重避免多个「未开始」"""
        values = (
            FunctionalRequirement.objects.all()
            .values_list('status', flat=True)
            .distinct()
        )
        options = sorted(set((v or '').strip() for v in values if (v or '').strip()))
        return Response({'code': 0, 'msg': 'success', 'data': options})

    @action(detail=False, methods=['get'], url_path='tag-options')
    def tag_options(self, request):
        """返回所有出现过的标签（tags 为逗号分隔，拆分去重）"""
        values = (
            FunctionalRequirement.objects.all()
            .values_list('tags', flat=True)
            .distinct()
        )
        seen = set()
        for v in values:
            if not v:
                continue
            for part in str(v).replace('，', ',').split(','):
                p = part.strip()
                if p and p not in seen:
                    seen.add(p)
        options = sorted(seen)
        return Response({'code': 0, 'msg': 'success', 'data': options})

    @action(detail=False, methods=['get'], url_path='tester-options')
    def tester_options(self, request):
        """返回所有出现过的测试人员（用于筛选下拉），testers 为逗号分隔，拆分去重"""
        values = (
            FunctionalRequirement.objects.all()
            .values_list('testers', flat=True)
            .distinct()
        )
        seen = set()
        for v in values:
            if not v:
                continue
            for part in str(v).replace('，', ',').split(','):
                p = part.strip()
                if p and p not in seen:
                    seen.add(p)
        options = sorted(seen)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': options
        })
    
    def list(self, request, *args, **kwargs):
        """获取需求列表"""
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            return Response({
                'code': 0,
                'msg': 'success',
                'data': paginated_response.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        """创建需求"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        return Response({
            'code': 0,
            'msg': '创建成功',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """更新需求"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'code': 0,
            'msg': '更新成功',
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """删除需求"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'code': 0,
            'msg': '删除成功'
        }, status=status.HTTP_200_OK)


class TaskViewSet(viewsets.ModelViewSet):
    """任务管理视图集"""
    queryset = Task.objects.all()  # type: ignore[attr-defined]
    serializer_class = TaskSerializer
    pagination_class = pagination.MyPageNumberPagination

    def get_queryset(self):
        """按任务名称、所属需求、任务负责人、状态、创建时间过滤"""
        name = self.request.query_params.get('name', '').strip()
        requirement_name = self.request.query_params.get('requirement_name', '').strip()
        owner = self.request.query_params.get('owner', '').strip()
        status_val = self.request.query_params.get('status', '').strip()
        created_at_after = self.request.query_params.get('created_at_after', '').strip()
        created_at_before = self.request.query_params.get('created_at_before', '').strip()

        queryset = Task.objects.all().select_related('created_by')  # type: ignore[attr-defined]
        if name:
            queryset = queryset.filter(name__icontains=name)
        if requirement_name:
            queryset = queryset.filter(requirement_name__icontains=requirement_name)
        if owner:
            queryset = queryset.filter(owner__icontains=owner)
        if status_val:
            queryset = queryset.filter(status=status_val)
        if created_at_after:
            queryset = queryset.filter(created_at__date__gte=created_at_after)
        if created_at_before:
            queryset = queryset.filter(created_at__date__lte=created_at_before)
        return queryset.order_by('-updated_at')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            return Response({'code': 0, 'msg': 'success', 'data': paginated_response.data})
        serializer = self.get_serializer(queryset, many=True)
        return Response({'code': 0, 'msg': 'success', 'data': serializer.data})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        return Response({
            'code': 0, 'msg': '创建成功', 'data': serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({'code': 0, 'msg': '更新成功', 'data': serializer.data})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'code': 0, 'msg': '删除成功'}, status=status.HTTP_200_OK)


class FunctionalTestCaseViewSet(viewsets.ModelViewSet):
    """功能测试用例视图集"""
    queryset = FunctionalTestCase.objects.all()  # type: ignore[attr-defined]
    serializer_class = FunctionalTestCaseSerializer
    pagination_class = pagination.MyPageNumberPagination
    
    def get_queryset(self):
        """按 title、module_name、function_name、priority、source 过滤"""
        title = self.request.query_params.get('title', '').strip()
        module_name = self.request.query_params.get('module_name', '').strip()
        function_name = self.request.query_params.get('function_name', '').strip()
        priority = self.request.query_params.get('priority', '').strip()
        source = self.request.query_params.get('source', '').strip()

        queryset = FunctionalTestCase.objects.all().select_related('created_by', 'ai_generation')  # type: ignore[attr-defined]
        if title:
            queryset = queryset.filter(title__icontains=title)
        if module_name:
            queryset = queryset.filter(module_name__icontains=module_name)
        if function_name:
            queryset = queryset.filter(function_name__icontains=function_name)
        if priority:
            queryset = queryset.filter(priority=priority)
        if source:
            queryset = queryset.filter(source=source)
        return queryset.order_by('created_at')  # 正序：与导入顺序一致
    
    def list(self, request, *args, **kwargs):
        """获取功能测试用例列表"""
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            # 将分页响应包装在统一的响应格式中
            return Response({
                'code': 0,
                'msg': 'success',
                'data': paginated_response.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        """创建功能测试用例"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # 设置创建人
        serializer.save(created_by=request.user)
        
        return Response({
            'code': 0,
            'msg': '创建成功',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """更新功能测试用例"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'code': 0,
            'msg': '更新成功',
            'data': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """删除功能测试用例"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'code': 0,
            'msg': '删除成功'
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='import')
    def import_cases(self, request):
        """导入测试用例（支持 xmind, xls, xlsx, csv），必须选择需求名称，用例归属该需求（覆盖文件内需求名称）"""
        requirement_id = request.POST.get('requirement_id') or request.data.get('requirement_id')
        if not requirement_id:
            return Response({'code': 1, 'msg': '请选择需求名称'}, status=status.HTTP_400_BAD_REQUEST)
        if 'file' not in request.FILES:
            return Response({
                'code': 1,
                'msg': '请选择要导入的文件'
            }, status=status.HTTP_400_BAD_REQUEST)

        requirement = get_object_or_404(FunctionalRequirement, pk=requirement_id)
        title_override = requirement.name

        file = request.FILES['file']
        try:
            importer = get_importer(file.name)
            cases_data = importer.parse(file)

            if not cases_data:
                return Response({
                    'code': 1,
                    'msg': '文件中没有找到有效的测试用例'
                }, status=status.HTTP_400_BAD_REQUEST)

            created_count = 0
            failed_count = 0
            errors = []

            with transaction.atomic():
                for case_data in cases_data:
                    try:
                        # 只保留新模型字段，title 使用所选需求名称覆盖文件内需求名称
                        create_kw = {
                            'title': title_override,
                            'module_name': case_data.get('module_name', ''),
                            'function_name': case_data.get('function_name', ''),
                            'name': case_data.get('name', '') or '未命名用例',
                            'priority': case_data.get('priority', 'P2'),
                            'precondition': case_data.get('precondition', ''),
                            'steps': case_data.get('steps', ''),
                            'expected': case_data.get('expected', ''),
                            'source': 'manual',
                            'created_by': request.user,
                        }
                        FunctionalTestCase.objects.create(**create_kw)  # type: ignore[attr-defined]
                        created_count += 1
                    except Exception as e:
                        failed_count += 1
                        errors.append(f"用例 '{case_data.get('name', '未知')}' 创建失败: {str(e)}")
                        logger.error(f"创建用例失败: {e}", exc_info=True)

            return Response({
                'code': 0,
                'msg': f'导入完成：成功 {created_count} 条，失败 {failed_count} 条',
                'data': {
                    'created_count': created_count,
                    'failed_count': failed_count,
                    'errors': errors[:10]
                }
            })
        except ValueError as e:
            return Response({'code': 1, 'msg': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"导入测试用例失败: {e}", exc_info=True)
            return Response({'code': 1, 'msg': f'导入失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='import-from-ai')
    def import_from_ai(self, request):
        """从 AI 生成记录导入用例到功能测试用例管理，必须选择需求名称，用例归属该需求"""
        ai_generation_id = request.data.get('ai_generation_id')
        requirement_id = request.data.get('requirement_id')
        if not ai_generation_id:
            return Response({'code': 1, 'msg': '请提供 ai_generation_id'}, status=status.HTTP_400_BAD_REQUEST)
        if not requirement_id:
            return Response({'code': 1, 'msg': '请选择需求名称'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from apps.ai_testcase.models import AiTestcaseGeneration
            record = get_object_or_404(AiTestcaseGeneration, pk=ai_generation_id)
        except Exception as e:
            return Response({'code': 1, 'msg': f'获取 AI 记录失败: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        requirement = get_object_or_404(FunctionalRequirement, pk=requirement_id)

        result_json = record.result_json
        if not result_json or not isinstance(result_json, dict):
            return Response({'code': 1, 'msg': '该记录没有可导入的用例数据'}, status=status.HTTP_400_BAD_REQUEST)

        title = requirement.name
        modules = result_json.get('modules', [])
        if not modules:
            return Response({'code': 1, 'msg': '用例数据中没有模块'}, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        with transaction.atomic():
            for mod in modules:
                module_name = mod.get('name', '')
                for func in mod.get('functions', []):
                    function_name = func.get('name', '')
                    for case in func.get('cases', []):
                        FunctionalTestCase.objects.create(  # type: ignore[attr-defined]
                            title=title,
                            module_name=module_name,
                            function_name=function_name,
                            name=case.get('name', '') or '未命名',
                            priority=case.get('priority', 'P2'),
                            precondition=case.get('precondition', ''),
                            steps=case.get('steps', ''),
                            expected=case.get('expected', ''),
                            source='ai',
                            ai_generation_id=record.id,
                            created_by=request.user,
                        )
                        created_count += 1

        return Response({
            'code': 0,
            'msg': f'导入成功，共 {created_count} 条用例',
            'data': {'created_count': created_count}
        })
    
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """导出测试用例（支持 Excel 和 XMind 格式）"""
        try:
            title = request.query_params.get('title', '').strip()
            module_name = request.query_params.get('module_name', '').strip()
            function_name = request.query_params.get('function_name', '').strip()
            priority = request.query_params.get('priority', '').strip()
            source = request.query_params.get('source', '').strip()
            export_format = request.query_params.get(
                'file_format',
                request.query_params.get('export_format', 'xlsx')
            ).lower()

            queryset = FunctionalTestCase.objects.all().select_related('created_by')  # type: ignore[attr-defined]
            if title:
                queryset = queryset.filter(title__icontains=title)
            if module_name:
                queryset = queryset.filter(module_name__icontains=module_name)
            if function_name:
                queryset = queryset.filter(function_name__icontains=function_name)
            if priority:
                queryset = queryset.filter(priority=priority)
            if source:
                queryset = queryset.filter(source=source)

            cases = queryset.order_by('created_at')
            
            if not cases.exists():
                return Response({
                    'code': 1,
                    'msg': '没有可导出的用例'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 根据格式选择导出方法
            if export_format == 'xmind':
                return self._export_to_xmind(cases)
            else:
                return self._export_to_excel(cases)
            
        except Exception as e:
            logger.error(f"导出测试用例失败: {e}", exc_info=True)
            return Response({
                'code': 1,
                'msg': f'导出失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _export_to_excel(self, cases):
        """导出为 Excel 格式（新字段：title, module_name, function_name, steps, expected）"""
        try:
            import pandas as pd
        except ImportError:
            logger.error("pandas 未安装，请运行: pip install pandas openpyxl")
            return Response({
                'code': 1,
                'msg': '导出功能需要安装 pandas 和 openpyxl 库'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        export_data = []
        for case in cases:
            export_data.append({
                '需求名称': case.title or '',
                '模块名称': case.module_name or '',
                '功能点名称': case.function_name or '',
                '用例名称': case.name,
                '优先级': case.priority,
                '前置条件': case.precondition or '',
                '测试步骤': case.steps or '',
                '预期结果': case.expected or '',
                '来源': case.source or 'manual',
                '创建人': (getattr(case.created_by, 'name', None) or case.created_by.username) if case.created_by else '',
                '创建时间': case.created_at.strftime('%Y-%m-%d %H:%M:%S') if case.created_at else '',
                '更新时间': case.updated_at.strftime('%Y-%m-%d %H:%M:%S') if case.updated_at else ''
            })

        df = pd.DataFrame(export_data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='功能测试用例')
            worksheet = writer.sheets['功能测试用例']
            column_widths = {
                'A': 20, 'B': 20, 'C': 20, 'D': 30, 'E': 10, 'F': 30, 'G': 50, 'H': 50, 'I': 10,
                'J': 15, 'K': 20, 'L': 20
            }
            for col, width in column_widths.items():
                worksheet.column_dimensions[col].width = width
            from openpyxl.styles import Alignment
            wrap_alignment = Alignment(wrap_text=True, vertical='top')
            for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row, min_col=6, max_col=8):
                for cell in row:
                    cell.alignment = wrap_alignment

        output.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        titles = list({c.title for c in cases if c.title})
        base_name = titles[0] if len(titles) == 1 else ('多需求' if titles else '需求')
        filename = f'{base_name}测试用例_{timestamp}.xlsx'
        
        # 返回文件响应
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        from urllib.parse import quote
        safe_name = filename.encode('ascii', 'ignore').decode('ascii') or 'export.xlsx'
        response['Content-Disposition'] = (
            f'attachment; filename="{safe_name}"; filename*=UTF-8\'\'{quote(filename)}'
        )
        response['Access-Control-Expose-Headers'] = 'Content-Disposition'
        return response
    
    def _export_to_xmind(self, cases):
        """导出为 XMind 格式（新字段）"""
        try:
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                content_json, first_sheet_id = self._create_xmind_json(cases)
                zip_file.writestr('content.json', content_json.encode('utf-8'))
                now_ms = int(datetime.utcnow().timestamp() * 1000)
                metadata = {
                    "creator": {"name": "workmind", "version": "1.0"},
                    "generator": "workmind",
                    "created": now_ms,
                    "modified": now_ms,
                    "activeSheetId": first_sheet_id
                }
                zip_file.writestr('metadata.json', json.dumps(metadata, ensure_ascii=False).encode('utf-8'))
                manifest = {
                    "file-entries": {
                        "content.json": {"media-type": "application/json"},
                        "metadata.json": {"media-type": "application/json"}
                    }
                }
                zip_file.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False).encode('utf-8'))

            output.seek(0)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            titles = list({c.title for c in cases if c.title})
            base_name = titles[0] if len(titles) == 1 else ('多需求' if titles else '需求')
            filename = f'{base_name}测试用例_{timestamp}.xmind'
            
            # 返回文件响应
            response = HttpResponse(
                output.getvalue(),
                content_type='application/x-xmind'
            )
            from urllib.parse import quote
            safe_name = filename.encode('ascii', 'ignore').decode('ascii') or 'export.xmind'
            response['Content-Disposition'] = (
                f'attachment; filename="{safe_name}"; filename*=UTF-8\'\'{quote(filename)}'
            )
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            return response
            
        except Exception as e:
            logger.error(f"导出 XMind 文件失败: {e}", exc_info=True)
            return Response({
                'code': 1,
                'msg': f'导出 XMind 文件失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _create_xmind_json(self, cases):
        """创建 XMind content.json（新字段：title, module_name, function_name, precondition, steps, expected）"""
        def new_id(prefix: str) -> str:
            return f"{prefix}-{uuid.uuid4().hex}"

        # 按 title -> module_name -> function_name 分组
        groups = {}
        for case in cases:
            t = case.title or '未分类'
            if t not in groups:
                groups[t] = {}
            m = case.module_name or '未分类'
            if m not in groups[t]:
                groups[t][m] = {}
            f = case.function_name or '未分类'
            if f not in groups[t][m]:
                groups[t][m][f] = []
            groups[t][m][f].append(case)

        sheets = []
        for req_name, modules in groups.items():
            root_topic = {
                'id': new_id('topic'),
                'title': req_name,
                'structureClass': 'org.xmind.ui.logic.right',
                'children': {'attached': []}
            }
            for mod_name, funcs in modules.items():
                mod_topic = {
                    'id': new_id('module'),
                    'title': mod_name,
                    'children': {'attached': []}
                }
                for func_name, case_list in funcs.items():
                    func_topic = {
                        'id': new_id('func'),
                        'title': func_name,
                        'children': {'attached': []}
                    }
                    for case in case_list:
                        case_topic = {
                            'id': new_id('case'),
                            'title': case.name,
                            'children': {'attached': []}
                        }
                        if case.priority:
                            case_topic['labels'] = [str(case.priority)]
                        if case.precondition:
                            case_topic['children']['attached'].append({
                                'id': new_id('pre'),
                                'title': f'前置条件：{case.precondition}'
                            })
                        if case.steps or case.expected:
                            steps_topic = {
                                'id': new_id('steps'),
                                'title': '测试步骤',
                                'children': {'attached': []}
                            }
                            if case.steps:
                                steps_topic['children']['attached'].append({
                                    'id': new_id('step'),
                                    'title': case.steps
                                })
                            if case.expected:
                                steps_topic['children']['attached'].append({
                                    'id': new_id('exp'),
                                    'title': f'预期结果：{case.expected}'
                                })
                            case_topic['children']['attached'].append(steps_topic)
                        func_topic['children']['attached'].append(case_topic)
                    mod_topic['children']['attached'].append(func_topic)
                root_topic['children']['attached'].append(mod_topic)
            sheets.append({'id': new_id('sheet'), 'title': req_name, 'rootTopic': root_topic})

        first_sheet_id = sheets[0]['id'] if sheets else ''
        return json.dumps(sheets, ensure_ascii=False), first_sheet_id



# 独立的导出视图函数
@api_view(['GET'])
@permission_classes([AllowAny])
def functional_case_export(request):
    """功能测试用例导出视图函数（新字段筛选）"""
    try:
        title = request.query_params.get('title', '').strip()
        module_name = request.query_params.get('module_name', '').strip()
        function_name = request.query_params.get('function_name', '').strip()
        priority = request.query_params.get('priority', '').strip()
        source = request.query_params.get('source', '').strip()
        export_format = request.query_params.get(
            'file_format',
            request.query_params.get('export_format', 'xlsx')
        ).lower()

        queryset = FunctionalTestCase.objects.all().select_related('created_by')  # type: ignore[attr-defined]
        if title:
            queryset = queryset.filter(title__icontains=title)
        if module_name:
            queryset = queryset.filter(module_name__icontains=module_name)
        if function_name:
            queryset = queryset.filter(function_name__icontains=function_name)
        if priority:
            queryset = queryset.filter(priority=priority)
        if source:
            queryset = queryset.filter(source=source)

        cases = queryset.order_by('created_at')
        
        if not cases.exists():
            return Response({
                'code': 1,
                'msg': '没有可导出的用例'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 创建视图集实例以调用导出方法
        viewset = FunctionalTestCaseViewSet()
        
        # 根据格式选择导出方法
        if export_format == 'xmind':
            return viewset._export_to_xmind(cases)
        else:
            return viewset._export_to_excel(cases)
            
    except Exception as e:
        logger.error(f"导出测试用例失败: {e}", exc_info=True)
        return Response({
            'code': 1,
            'msg': f'导出失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestPlanViewSet(viewsets.ModelViewSet):
    """测试计划视图集"""
    queryset = TestPlan.objects.all()  # type: ignore[attr-defined]
    serializer_class = TestPlanSerializer
    pagination_class = pagination.MyPageNumberPagination
    
    def get_queryset(self):
        """获取测试计划列表"""
        queryset = TestPlan.objects.all().select_related('created_by')  # type: ignore[attr-defined]
        return queryset.order_by('-updated_at')
    
    def list(self, request, *args, **kwargs):
        """获取测试计划列表"""
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            # 将分页响应包装在统一的响应格式中
            return Response({
                'code': 0,
                'msg': 'success',
                'data': paginated_response.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        """创建测试计划"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        
        return Response({
            'code': 0,
            'msg': '创建成功',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, *args, **kwargs):
        """删除测试计划"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'code': 0,
            'msg': '删除成功'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='add-cases')
    def add_cases(self, request, pk=None):
        """向测试计划添加用例"""
        test_plan = self.get_object()
        case_ids = request.data.get('case_ids', [])
        
        if not case_ids:
            return Response({
                'code': 1,
                'msg': '请选择要添加的用例'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            added_count = 0
            skipped_count = 0
            
            with transaction.atomic():
                for idx, case_id in enumerate(case_ids):
                    # 检查是否已存在
                    if TestPlanCase.objects.filter(  # type: ignore[attr-defined]
                        test_plan=test_plan,
                        test_case_id=case_id
                    ).exists():
                        skipped_count += 1
                        continue
                    
                    # 创建关联
                    TestPlanCase.objects.create(  # type: ignore[attr-defined]
                        test_plan=test_plan,
                        test_case_id=case_id
                    )
                    added_count += 1
            
            return Response({
                'code': 0,
                'msg': f'添加完成：成功 {added_count} 条，跳过 {skipped_count} 条（已存在）',
                'data': {
                    'added_count': added_count,
                    'skipped_count': skipped_count
                }
            })
        except Exception as e:
            logger.error(f"添加用例到测试计划失败: {e}", exc_info=True)
            return Response({
                'code': 1,
                'msg': f'添加失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['delete'], url_path='remove-case/(?P<case_id>[^/.]+)')
    def remove_case(self, request, pk=None, case_id=None):
        """从测试计划中移除用例"""
        test_plan = self.get_object()
        
        try:
            plan_case = get_object_or_404(
                TestPlanCase,
                test_plan=test_plan,
                test_case_id=case_id
            )
            plan_case.delete()
            
            return Response({
                'code': 0,
                'msg': '移除成功'
            })
        except Exception as e:
            logger.error(f"从测试计划移除用例失败: {e}", exc_info=True)
            return Response({
                'code': 1,
                'msg': f'移除失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'], url_path='cases')
    def get_cases(self, request, pk=None):
        """获取测试计划中的用例列表"""
        test_plan = self.get_object()
        plan_cases = TestPlanCase.objects.filter(  # type: ignore[attr-defined]
            test_plan=test_plan
        ).select_related('test_case')
        
        serializer = TestPlanCaseSerializer(plan_cases, many=True)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': serializer.data
        })

    @action(detail=True, methods=['post'], url_path='cases/mark')
    def mark_case(self, request, pk=None):
        """标记测试计划用例执行结果（不生成执行记录）"""
        test_plan = self.get_object()
        case_id = request.data.get('case_id')
        case_status = request.data.get('status')
        message = request.data.get('message', '')

        if not case_id or case_status not in ['passed', 'failed', 'skipped', 'pending']:
            return Response({
                'code': 1,
                'msg': '参数错误'
            }, status=status.HTTP_400_BAD_REQUEST)

        if case_status in ['failed', 'skipped'] and not str(message).strip():
            return Response({
                'code': 1,
                'msg': '失败或跳过必须填写备注'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan_case = get_object_or_404(
                TestPlanCase,
                test_plan=test_plan,
                test_case_id=case_id
            )
            plan_case.status = case_status
            plan_case.result_message = message or ''
            plan_case.marked_by = request.user
            plan_case.marked_at = timezone.now()
            with transaction.atomic():
                plan_case.save()
                TestPlanCaseOperationLog.objects.create(  # type: ignore[attr-defined]
                    plan_case=plan_case,
                    status=case_status,
                    message=message or '',
                    operator=request.user
                )

            return Response({
                'code': 0,
                'msg': '更新成功',
                'data': TestPlanCaseSerializer(plan_case).data
            })
        except Exception as e:
            logger.error(f"标记用例结果失败: {e}", exc_info=True)
            return Response({
                'code': 1,
                'msg': f'更新失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='cases/batch-mark')
    def batch_mark_cases(self, request, pk=None):
        """批量标记测试计划用例执行结果"""
        test_plan = self.get_object()
        case_ids = request.data.get('case_ids') or []
        case_status = request.data.get('status')
        message = request.data.get('message', '')

        if not isinstance(case_ids, list) or not case_ids:
            return Response({'code': 1, 'msg': '请选择要标记的用例'}, status=status.HTTP_400_BAD_REQUEST)
        if case_status not in ['passed', 'failed', 'skipped', 'pending']:
            return Response({'code': 1, 'msg': '参数错误：status 无效'}, status=status.HTTP_400_BAD_REQUEST)
        if case_status in ['failed', 'skipped'] and not str(message).strip():
            return Response({'code': 1, 'msg': '失败或跳过必须填写备注'}, status=status.HTTP_400_BAD_REQUEST)

        updated_count = 0
        try:
            with transaction.atomic():
                for case_id in case_ids:
                    plan_case = TestPlanCase.objects.filter(  # type: ignore[attr-defined]
                        test_plan=test_plan,
                        test_case_id=case_id
                    ).first()
                    if not plan_case:
                        continue
                    plan_case.status = case_status
                    plan_case.result_message = message or ''
                    plan_case.marked_by = request.user
                    plan_case.marked_at = timezone.now()
                    plan_case.save()
                    TestPlanCaseOperationLog.objects.create(  # type: ignore[attr-defined]
                        plan_case=plan_case,
                        status=case_status,
                        message=message or '',
                        operator=request.user
                    )
                    updated_count += 1
            return Response({
                'code': 0,
                'msg': f'批量标记成功，共 {updated_count} 条',
                'data': {'updated_count': updated_count}
            })
        except Exception as e:
            logger.error(f"批量标记用例失败: {e}", exc_info=True)
            return Response({'code': 1, 'msg': f'批量标记失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='cases/logs')
    def case_logs(self, request, pk=None):
        """获取测试计划用例操作记录"""
        test_plan = self.get_object()
        case_id = request.query_params.get('case_id')

        logs = TestPlanCaseOperationLog.objects.filter(  # type: ignore[attr-defined]
            plan_case__test_plan=test_plan
        ).select_related('plan_case', 'operator', 'plan_case__test_case')

        if case_id:
            logs = logs.filter(plan_case__test_case_id=case_id)

        serializer = TestPlanCaseOperationLogSerializer(logs.order_by('-created_at'), many=True)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': serializer.data
        })