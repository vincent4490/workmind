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
    FunctionalRequirement, FunctionalTestCase, TestPlan, TestPlanCase, TestPlanCaseOperationLog
)
from ..serializers import (
    FunctionalRequirementSerializer, FunctionalTestCaseSerializer, TestPlanSerializer,
    TestPlanCaseSerializer, TestPlanCaseOperationLogSerializer
)
from ..utils.case_importers import get_importer

logger = logging.getLogger(__name__)


class FunctionalRequirementViewSet(viewsets.ModelViewSet):
    """功能测试需求视图集"""
    queryset = FunctionalRequirement.objects.all()  # type: ignore[attr-defined]
    serializer_class = FunctionalRequirementSerializer
    pagination_class = pagination.MyPageNumberPagination
    
    def get_queryset(self):
        """根据需求名称过滤"""
        name = self.request.query_params.get('name', '').strip()
        requirement_name = self.request.query_params.get('requirement_name', '').strip()
        keyword = name or requirement_name
        
        queryset = FunctionalRequirement.objects.all().select_related('created_by')  # type: ignore[attr-defined]
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        return queryset.order_by('-updated_at')
    
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


class FunctionalTestCaseViewSet(viewsets.ModelViewSet):
    """功能测试用例视图集"""
    queryset = FunctionalTestCase.objects.all()  # type: ignore[attr-defined]
    serializer_class = FunctionalTestCaseSerializer
    pagination_class = pagination.MyPageNumberPagination
    
    def get_queryset(self):
        """根据其他搜索条件过滤用例"""
        requirement_name = self.request.query_params.get('requirement_name', '').strip()
        priority = self.request.query_params.get('priority', '').strip()
        tag = self.request.query_params.get('tag', '').strip()
        
        queryset = FunctionalTestCase.objects.all().select_related('created_by')  # type: ignore[attr-defined]
        
        # 需求名称过滤（支持模糊匹配）
        if requirement_name:
            queryset = queryset.filter(requirement_name__icontains=requirement_name)
        
        # 优先级过滤（精确匹配）
        if priority:
            queryset = queryset.filter(priority=priority)
        
        if tag:
            tag_list = [t.strip() for t in tag.replace('，', ',').split(',') if t.strip()]
            tag_query = models.Q()
            for t in tag_list:
                tag_query |= models.Q(tags__contains=[t]) | models.Q(tags__icontains=t)
            queryset = queryset.filter(tag_query)
        
        return queryset.order_by('-updated_at')
    
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
        """导入测试用例（支持 xmind, xls, xlsx, csv）"""
        if 'file' not in request.FILES:
            return Response({
                'code': 1,
                'msg': '请选择要导入的文件'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        try:
            # 获取导入器
            importer = get_importer(file.name)
            
            # 解析文件
            cases_data = importer.parse(file)
            
            if not cases_data:
                return Response({
                    'code': 1,
                    'msg': '文件中没有找到有效的测试用例'
                }, status=status.HTTP_400_BAD_REQUEST)

            logger.info(
                "导入解析结果预览: cases_count=%s, first_requirement=%s, first_feature=%s, first_case=%s",
                len(cases_data),
                cases_data[0].get('requirement_name') if cases_data else None,
                cases_data[0].get('feature_name') if cases_data else None,
                cases_data[0].get('name') if cases_data else None,
            )
            
            # 校验需求名称必须存在于需求管理
            def _normalize_requirement_name(value: str) -> str:
                if not value:
                    return ''
                return str(value).strip()

            requirement_names_in_file = {
                _normalize_requirement_name(case.get('requirement_name'))
                for case in cases_data
            }
            requirement_names_in_file.discard('')
            existing_requirements = {
                _normalize_requirement_name(name)
                for name in FunctionalRequirement.objects.values_list('name', flat=True)  # type: ignore[attr-defined]
                if name
            }
            logger.info(
                "导入需求名称调试: file_requirements=%s, existing_requirements=%s",
                sorted(requirement_names_in_file),
                sorted(existing_requirements),
            )
            missing_requirements = sorted(requirement_names_in_file - existing_requirements)
            if missing_requirements:
                return Response({
                    'code': 1,
                    'msg': '导入失败：需求名称不存在，请先在需求管理页面创建需求'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 批量创建用例
            created_count = 0
            failed_count = 0
            errors = []
            
            with transaction.atomic():
                for case_data in cases_data:
                    try:
                        FunctionalTestCase.objects.create(  # type: ignore[attr-defined]
                            created_by=request.user,
                            **case_data
                        )
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
                    'errors': errors[:10]  # 只返回前10个错误
                }
            })
        except ValueError as e:
            return Response({
                'code': 1,
                'msg': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"导入测试用例失败: {e}", exc_info=True)
            return Response({
                'code': 1,
                'msg': f'导入失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """导出测试用例（支持 Excel 和 XMind 格式）"""
        logger.info(f"ViewSet export 方法被调用: {request.path}, 参数: {request.query_params}")
        try:
            # 获取查询参数
            requirement_name = request.query_params.get('requirement_name', '').strip()
            priority = request.query_params.get('priority', '').strip()
            tag = request.query_params.get('tag', '').strip()
            export_format = request.query_params.get(
                'file_format',
                request.query_params.get('export_format', 'xlsx')
            ).lower()  # 默认 xlsx
            
            # 构建查询集
            queryset = FunctionalTestCase.objects.all().select_related('created_by')  # type: ignore[attr-defined]
            
            if requirement_name:
                queryset = queryset.filter(requirement_name__icontains=requirement_name)
            
            if priority:
                queryset = queryset.filter(priority=priority)
            
            if tag:
                tag_list = [t.strip() for t in tag.replace('，', ',').split(',') if t.strip()]
                tag_query = models.Q()
                for t in tag_list:
                    tag_query |= models.Q(tags__contains=[t]) | models.Q(tags__icontains=t)
                queryset = queryset.filter(tag_query)
            
            # 获取所有用例
            cases = queryset.order_by('-updated_at')
            
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
        """导出为 Excel 格式"""
        try:
            import pandas as pd
        except ImportError:
            logger.error("pandas 未安装，请运行: pip install pandas openpyxl")
            return Response({
                'code': 1,
                'msg': '导出功能需要安装 pandas 和 openpyxl 库'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # 准备导出数据
        export_data = []
        for case in cases:
            # 格式化操作步骤和预期结果（每条一行）
            steps_text = ''
            expected_results_text = ''
            if case.test_steps:
                steps_list = []
                expected_list = []
                for idx, step in enumerate(case.test_steps, 1):
                    step_text = (step.get('step') or '').strip()
                    expected_text = (step.get('expected_result') or '').strip()
                    if step_text:
                        steps_list.append(f'步骤{idx}：{step_text}')
                    if expected_text:
                        expected_list.append(f'预期结果{idx}：{expected_text}')
                steps_text = '\n'.join(steps_list)
                expected_results_text = '\n'.join(expected_list)
            
            export_data.append({
                '需求名称': case.requirement_name,
                '功能模块': case.feature_name,
                '用例名称': case.name,
                '优先级': case.priority,
                '前置条件': case.preconditions or '',
                '操作步骤': steps_text,
                '预期结果': expected_results_text,
                '创建人': case.created_by.username if case.created_by else '',
                '创建时间': case.created_at.strftime('%Y-%m-%d %H:%M:%S') if case.created_at else '',
                '更新时间': case.updated_at.strftime('%Y-%m-%d %H:%M:%S') if case.updated_at else ''
            })
        
        # 创建 DataFrame
        df = pd.DataFrame(export_data)
        
        # 创建 Excel 文件
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='功能测试用例')
            
            # 调整列宽
            worksheet = writer.sheets['功能测试用例']
            column_widths = {
                'A': 20,  # 需求名称
                'B': 20,  # 功能模块
                'C': 30,  # 用例名称
                'D': 10,  # 优先级
                'E': 30,  # 前置条件
                'F': 50,  # 操作步骤
                'G': 50,  # 预期结果
                'H': 15,  # 创建人
                'I': 20,  # 创建时间
                'J': 20   # 更新时间
            }
            for col, width in column_widths.items():
                worksheet.column_dimensions[col].width = width

            # 操作步骤/预期结果换行显示
            from openpyxl.styles import Alignment
            wrap_alignment = Alignment(wrap_text=True, vertical='top')
            for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row, min_col=5, max_col=7):
                for cell in row:
                    cell.alignment = wrap_alignment
        
        output.seek(0)
        
        # 生成文件名：需求名称 + 测试用例
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        requirement_names = []
        for case in cases:
            if case.requirement_name and case.requirement_name not in requirement_names:
                requirement_names.append(case.requirement_name)
        if len(requirement_names) == 1:
            base_name = requirement_names[0]
        elif requirement_names:
            base_name = '多需求'
        else:
            base_name = '需求'
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
        """导出为 XMind 格式"""
        try:
            # 创建 XMind 文件结构
            output = io.BytesIO()
            
            # 创建 ZIP 文件（XMind 文件实际上是 ZIP 压缩包）
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # 创建 content.json（新格式）
                content_json, first_sheet_id = self._create_xmind_json(cases)
                zip_file.writestr('content.json', content_json.encode('utf-8'))

                # 创建 metadata.json（新格式）
                now_ms = int(datetime.utcnow().timestamp() * 1000)
                metadata = {
                    "creator": {
                        "name": "workmind",
                        "version": "1.0"
                    },
                    "generator": "workmind",
                    "created": now_ms,
                    "modified": now_ms,
                    "activeSheetId": first_sheet_id
                }
                zip_file.writestr('metadata.json', json.dumps(metadata, ensure_ascii=False).encode('utf-8'))

                # 创建 manifest.json（新格式）
                manifest = {
                    "file-entries": {
                        "content.json": {
                            "media-type": "application/json"
                        },
                        "metadata.json": {
                            "media-type": "application/json"
                        }
                    }
                }
                zip_file.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False).encode('utf-8'))
            
            output.seek(0)
            
            # 生成文件名：需求名称 + 测试用例
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            requirement_names = []
            for case in cases:
                if case.requirement_name and case.requirement_name not in requirement_names:
                    requirement_names.append(case.requirement_name)
            if len(requirement_names) == 1:
                base_name = requirement_names[0]
            elif requirement_names:
                base_name = '多需求'
            else:
                base_name = '需求'
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
        """创建 XMind content.json 内容（新格式）"""
        def new_id(prefix: str) -> str:
            return f"{prefix}-{uuid.uuid4().hex}"

        # 按需求名称分组
        requirement_groups = {}
        for case in cases:
            req_name = case.requirement_name or '未分类'
            if req_name not in requirement_groups:
                requirement_groups[req_name] = {}

            feature_name = case.feature_name or '未分类'
            if feature_name not in requirement_groups[req_name]:
                requirement_groups[req_name][feature_name] = []

            requirement_groups[req_name][feature_name].append(case)

        sheets = []
        for req_name, modules in requirement_groups.items():
            root_topic = {
                'id': new_id('topic'),
                'title': req_name,
                'structureClass': 'org.xmind.ui.logic.right',
                'children': {
                    'attached': []
                }
            }

            for feature_name, case_list in modules.items():
                module_topic = {
                    'id': new_id('module'),
                    'title': feature_name,
                    'children': {
                        'attached': []
                    }
                }

                for case in case_list:
                    case_topic = {
                        'id': new_id('case'),
                        'title': case.name,
                        'children': {
                            'attached': []
                        }
                    }
                    if case.priority:
                        case_topic['labels'] = [str(case.priority)]

                    if case.preconditions:
                        case_topic['children']['attached'].append({
                            'id': new_id('pre'),
                            'title': f'前置条件：{case.preconditions}'
                        })

                    if case.test_steps:
                        steps_topic = {
                            'id': new_id('steps'),
                            'title': '操作步骤',
                            'children': {
                                'attached': []
                            }
                        }
                        for idx, step in enumerate(case.test_steps, 1):
                            step_text = step.get('step', '')
                            expected_text = step.get('expected_result', '')
                            if step_text:
                                step_topic = {
                                    'id': new_id('step'),
                                    'title': f'步骤{idx}：{step_text}'
                                }
                                if expected_text:
                                    step_topic['children'] = {
                                        'attached': [{
                                            'id': new_id('exp'),
                                            'title': f'预期结果{idx}：{expected_text}'
                                        }]
                                    }
                                steps_topic['children']['attached'].append(step_topic)
                            elif expected_text:
                                steps_topic['children']['attached'].append({
                                    'id': new_id('exp'),
                                    'title': f'预期结果{idx}：{expected_text}'
                                })
                        case_topic['children']['attached'].append(steps_topic)

                    module_topic['children']['attached'].append(case_topic)

                root_topic['children']['attached'].append(module_topic)

            sheets.append({
                'id': new_id('sheet'),
                'title': req_name,
                'rootTopic': root_topic
            })

        first_sheet_id = sheets[0]['id'] if sheets else ''
        return json.dumps(sheets, ensure_ascii=False), first_sheet_id



# 独立的导出视图函数
@api_view(['GET'])
@permission_classes([AllowAny])
def functional_case_export(request):
    """功能测试用例导出视图函数"""
    logger.info(f"functional_case_export 被调用: {request.path}, 参数: {request.query_params}")
    try:
        # 获取查询参数
        requirement_name = request.query_params.get('requirement_name', '').strip()
        priority = request.query_params.get('priority', '').strip()
        tag = request.query_params.get('tag', '').strip()
        export_format = request.query_params.get(
            'file_format',
            request.query_params.get('export_format', 'xlsx')
        ).lower()  # 默认 xlsx
        
        # 构建查询集
        queryset = FunctionalTestCase.objects.all().select_related('created_by')  # type: ignore[attr-defined]
        
        if requirement_name:
            queryset = queryset.filter(requirement_name__icontains=requirement_name)
        
        if priority:
            queryset = queryset.filter(priority=priority)
        
        if tag:
            tag_list = [t.strip() for t in tag.replace('，', ',').split(',') if t.strip()]
            tag_query = models.Q()
            for t in tag_list:
                tag_query |= models.Q(tags__contains=[t]) | models.Q(tags__icontains=t)
            queryset = queryset.filter(tag_query)
        
        # 获取所有用例
        cases = queryset.order_by('-updated_at')
        
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