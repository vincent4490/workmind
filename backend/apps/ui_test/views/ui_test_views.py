# -*- coding: utf-8 -*-
"""
UI测试核心功能视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
import logging
import os
import re
import base64
import subprocess
from pathlib import Path
import json
import yaml
from django.db import transaction
from datetime import datetime

from ..models import (
    Device, UiTestConfig, UiTestCase,
    UiComponentDefinition, UiCustomComponentDefinition, UiComponentPackage
)
from ..serializers import (
    UiTestConfigSerializer,
    UiTestCaseSerializer,
    UiComponentDefinitionSerializer, UiCustomComponentDefinitionSerializer, UiComponentPackageSerializer
)
from ..utils.config_manager import ConfigManager
from backend.utils import pagination
from ..utils.ui_flow_validator import validate_ui_flow

logger = logging.getLogger(__name__)


class UiTestConfigViewSet(viewsets.ModelViewSet):
    """UI测试配置视图集"""
    queryset = UiTestConfig.objects.all()  # type: ignore[attr-defined]
    serializer_class = UiTestConfigSerializer

    @action(detail=False, methods=['post'], url_path='ui-flow-template')
    def ui_flow_template(self, request):
        """上传UI Flow模板图片"""
        if 'file' not in request.FILES:
            return Response({
                'code': 1,
                'msg': '请上传图片文件',
            }, status=status.HTTP_400_BAD_REQUEST)

        # 开源版本：固定使用 common 目录
        game_name = "common"

        filename = str(request.data.get('filename', '')).strip()
        upload_file = request.FILES['file']
        if not filename:
            filename = upload_file.name

        safe_name = re.sub(r'[^A-Za-z0-9_.-]', '_', filename)
        if not safe_name:
            safe_name = f"template_{int(timezone.now().timestamp())}.png"
        if not os.path.splitext(safe_name)[1]:
            safe_name = f"{safe_name}.png"

        base_dir = Path(__file__).resolve().parents[1] / "Template" / game_name
        base_dir.mkdir(parents=True, exist_ok=True)
        target_path = base_dir / safe_name

        try:
            with open(target_path, 'wb') as f:
                for chunk in upload_file.chunks():
                    f.write(chunk)
        except Exception as e:
            logger.error(f"保存模板失败: {e}", exc_info=True)
            return Response({
                'code': 1,
                'msg': f'保存失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='ui-flow-templates')
    def ui_flow_templates(self, request):
        """获取UI Flow模板列表"""
        # 开源版本：支持指定目录名，默认 common
        game_name = str(request.query_params.get('game_name', 'common')).strip()
        if not game_name:
            game_name = 'common'

        base_dir = Path(__file__).resolve().parents[1] / "Template" / game_name
        if not base_dir.exists():
            return Response({
                'code': 0,
                'msg': 'success',
                'data': []
            })

        files = []
        for item in base_dir.iterdir():
            if item.is_file() and item.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
                files.append({
                    'name': item.name,
                    'size': item.stat().st_size,
                    'updated_at': item.stat().st_mtime
                })

        files.sort(key=lambda x: x['updated_at'], reverse=True)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': files
        })

    @action(detail=False, methods=['post'], url_path='ui-flow-template-delete')
    def ui_flow_template_delete(self, request):
        """删除UI Flow模板"""
        # 开源版本：支持指定目录名，默认 common
        game_name = str(request.data.get('game_name', 'common')).strip()
        if not game_name:
            game_name = 'common'
        filename = str(request.data.get('filename', '')).strip()
        if not filename:
            return Response({
                'code': 1,
                'msg': '请提供文件名称',
            }, status=status.HTTP_400_BAD_REQUEST)

        safe_name = re.sub(r'[^A-Za-z0-9_.-]', '_', filename)
        target_path = Path(__file__).resolve().parents[1] / "Template" / game_name / safe_name
        if not target_path.exists():
            return Response({
                'code': 1,
                'msg': '文件不存在',
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            target_path.unlink()
        except Exception as e:
            logger.error(f"删除模板失败: {e}", exc_info=True)
            return Response({
                'code': 1,
                'msg': f'删除失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'code': 0,
            'msg': '删除成功'
        })

    @action(detail=False, methods=['get'], url_path='ui-flow-screenshot')
    def ui_flow_screenshot(self, request):
        """从设备获取截图"""
        raw_device_id = str(request.query_params.get('device_id', '')).strip()
        if not raw_device_id:
            return Response({
                'code': 1,
                'msg': '请指定设备ID'
            }, status=status.HTTP_400_BAD_REQUEST)

        device_id = raw_device_id
        if raw_device_id.isdigit():
            try:
                device = Device.objects.get(id=int(raw_device_id))  # type: ignore[attr-defined]
                device_id = device.device_id
            except Device.DoesNotExist:  # type: ignore[attr-defined]
                return Response({
                    'code': 1,
                    'msg': '设备不存在',
                }, status=status.HTTP_404_NOT_FOUND)

        adb_path = 'adb'
        try:
            config = UiTestConfig.objects.first()  # type: ignore[attr-defined]
            if config and config.adb_path:
                adb_path = config.adb_path
        except Exception:
            pass

        try:
            result = subprocess.run(
                [adb_path, "-s", device_id, "exec-out", "screencap", "-p"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=20,
            )
        except FileNotFoundError:
            # adb 未安装/未配置属于可预期环境问题，不应作为 5xx 报错刷屏
            return Response(
                {
                    "code": 1,
                    "msg": "adb 不存在或不可执行，请检查 UiTestConfig.adb_path 配置或系统 PATH",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except subprocess.TimeoutExpired:
            return Response(
                {
                    "code": 1,
                    "msg": "设备截图超时（adb screencap 无响应），请检查设备连接状态",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except subprocess.CalledProcessError as e:
            stderr = ""
            try:
                stderr = (e.stderr or b"").decode("utf-8", errors="ignore").strip()
            except Exception:
                stderr = ""
            msg = "设备截图失败"
            if stderr:
                msg = f"{msg}: {stderr}"
            # 常见：device offline / unauthorized / not found / no permissions
            return Response({"code": 1, "msg": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"设备截图失败: {e}", exc_info=True)
            return Response(
                {"code": 1, "msg": f"设备截图失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not result.stdout:
            return Response({
                'code': 1,
                'msg': '设备截图失败：无返回数据'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        image_base64 = base64.b64encode(result.stdout).decode('utf-8')
        return Response({
            'code': 0,
            'msg': 'success',
            'data': {
                'filename': f"device_{device_id}_{int(timezone.now().timestamp())}.png",
                'content': f"data:image/png;base64,{image_base64}"
            }
        })


class UiTestCaseViewSet(viewsets.ModelViewSet):
    """UI测试用例视图"""
    queryset = UiTestCase.objects.all()  # type: ignore[attr-defined]
    serializer_class = UiTestCaseSerializer

    def _parse_case_data(self, raw_data):
        if raw_data is None:
            return {}
        if isinstance(raw_data, dict):
            return raw_data
        try:
            import json
            return json.loads(raw_data)
        except Exception:
            return {}

    def _validate_ui_case_data(self, case_data):
        ui_flow = case_data.get('ui_flow')
        if not ui_flow:
            return None

        component_defs = UiComponentDefinition.objects.filter(enabled=True)  # type: ignore[attr-defined]
        component_map = {c.type: c for c in component_defs}
        custom_defs = UiCustomComponentDefinition.objects.filter(enabled=True)  # type: ignore[attr-defined]
        custom_map = {c.type: c for c in custom_defs}
        is_valid, errors = validate_ui_flow(ui_flow, component_map, custom_map)
        if not is_valid:
            return Response({
                'code': 1,
                'msg': 'UI场景校验失败',
                'data': errors
            }, status=status.HTTP_400_BAD_REQUEST)
        return None
    
    def get_queryset(self):
        """获取用例列表"""
        ui_flow_only = self.request.query_params.get('ui_flow_only')
        queryset = UiTestCase.objects.all()  # type: ignore[attr-defined]
        if ui_flow_only in ('1', 'true', 'True'):
            queryset = queryset.filter(case_data__has_key='ui_flow')
        return queryset
    
    def list(self, request, *args, **kwargs):
        """获取UI测试用例列表"""
        queryset = self.get_queryset()
        if 'page' in request.query_params or 'size' in request.query_params:
            paginator = pagination.MyPageNumberPagination()
            page = paginator.paginate_queryset(queryset, request, view=self)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return Response({
                    'code': 0,
                    'msg': 'success',
                    'data': paginator.get_paginated_response(serializer.data).data
                })
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'code': 0,
            'msg': 'success',
            'data': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        """创建UI测试用例"""
        data = request.data.copy()
        case_data = self._parse_case_data(data.get('case_data'))
        
        # 验证UI测试用例数据
        validation_response = self._validate_ui_case_data(case_data)
        if validation_response:
            return validation_response
        data['case_data'] = case_data

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({
            'code': 0,
            'msg': '创建成功',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """更新UI测试用例"""
        data = request.data.copy()
        case_data = self._parse_case_data(data.get('case_data'))
        
        # 验证UI测试用例数据
        validation_response = self._validate_ui_case_data(case_data)
        if validation_response:
            return validation_response
        data['case_data'] = case_data

        serializer = self.get_serializer(self.get_object(), data=data, partial=kwargs.pop('partial', False))
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'code': 0,
            'msg': '更新成功',
            'data': serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """删除UI测试用例"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'code': 0,
            'msg': '删除成功'
        }, status=status.HTTP_200_OK)


class UiComponentDefinitionViewSet(viewsets.ModelViewSet):
    """UI组件定义视图"""
    queryset = UiComponentDefinition.objects.all()  # type: ignore[attr-defined]
    serializer_class = UiComponentDefinitionSerializer

    def get_queryset(self):
        queryset = UiComponentDefinition.objects.all()  # type: ignore[attr-defined]
        enabled = self.request.query_params.get('enabled')
        if enabled is not None:
            if enabled in ('1', 'true', 'True'):
                queryset = queryset.filter(enabled=True)
            elif enabled in ('0', 'false', 'False'):
                queryset = queryset.filter(enabled=False)
        return queryset.order_by('sort_order', '-updated_at')

    def destroy(self, request, *args, **kwargs):
        """删除UI组件定义"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'code': 0,
            'msg': '删除成功'
        }, status=status.HTTP_200_OK)


class UiComponentPackageViewSet(viewsets.ModelViewSet):
    """UI组件包视图集（用于导出/安装组件定义）"""
    queryset = UiComponentPackage.objects.all()  # type: ignore[attr-defined]
    serializer_class = UiComponentPackageSerializer

    def _parse_manifest(self, request) -> dict:
        if 'file' in request.FILES:
            upload = request.FILES['file']
            raw = upload.read()
            try:
                content = raw.decode('utf-8')
            except Exception:
                content = raw.decode('utf-8-sig')
            filename = upload.name.lower()
            if filename.endswith('.json'):
                return json.loads(content)
            return yaml.safe_load(content)

        manifest = request.data.get('manifest')
        if isinstance(manifest, dict):
            return manifest
        if isinstance(manifest, str) and manifest.strip():
            try:
                return json.loads(manifest)
            except Exception:
                return yaml.safe_load(manifest)
        raise ValueError("请上传组件包文件或提供manifest")

    def create(self, request, *args, **kwargs):
        try:
            manifest = self._parse_manifest(request)
        except Exception as error:
            return Response({'code': 1, 'msg': f'解析组件包失败: {error}'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(manifest, dict):
            return Response({'code': 1, 'msg': '组件包格式错误：manifest 必须为对象'}, status=status.HTTP_400_BAD_REQUEST)

        components = manifest.get('components') or []
        if not isinstance(components, list) or not components:
            return Response({'code': 1, 'msg': '组件包缺少components 列表'}, status=status.HTTP_400_BAD_REQUEST)

        overwrite = str(request.data.get('overwrite', '1')).lower() in ('1', 'true', 'yes')
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []

        with transaction.atomic():
            for item in components:
                if not isinstance(item, dict):
                    errors.append('组件定义格式错误')
                    continue
                component_type = item.get('type')
                if not component_type:
                    errors.append('组件缺少 type')
                    continue
                defaults = {
                    'name': item.get('name') or component_type,
                    'category': item.get('category', ''),
                    'description': item.get('description', ''),
                    'schema': item.get('schema') or {},
                    'default_config': item.get('default_config') or {},
                    'enabled': item.get('enabled', True),
                    'sort_order': item.get('sort_order', 0),
                }
                obj, created = UiComponentDefinition.objects.get_or_create(type=component_type, defaults=defaults)
                if created:
                    created_count += 1
                    continue
                if not overwrite:
                    skipped_count += 1
                    continue
                for key, value in defaults.items():
                    setattr(obj, key, value)
                obj.save()
                updated_count += 1

            if errors:
                return Response({'code': 1, 'msg': '组件包包含错误: ' + ', '.join(errors), 'data': errors}, status=status.HTTP_400_BAD_REQUEST)

            package = UiComponentPackage.objects.create(
                name=manifest.get('name') or request.data.get('name') or 'component-package',
                version=manifest.get('version') or request.data.get('version', ''),
                description=manifest.get('description') or request.data.get('description', ''),
                author=manifest.get('author') or request.data.get('author', ''),
                source=request.data.get('source', 'upload'),
                manifest=manifest,
                created_by=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
            )

        return Response({
            'code': 0,
            'msg': '组件包已安装',
            'data': {
                'package_id': package.id,
                'created': created_count,
                'updated': updated_count,
                'skipped': skipped_count
            }
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        export_format = request.query_params.get('file_format')
        if not export_format:
            export_format = request.query_params.get('format')
        export_format = str(export_format or 'yaml').lower()
        include_disabled = str(request.query_params.get('include_disabled', '0')).lower() in ('1', 'true', 'yes')
        name = request.query_params.get('name', 'ui-component-pack')
        version = request.query_params.get('version', '') or datetime.now().strftime('%Y.%m.%d')
        author = request.query_params.get('author', '')
        description = request.query_params.get('description', '导出的组件包')

        queryset = UiComponentDefinition.objects.all()
        if not include_disabled:
            queryset = queryset.filter(enabled=True)

        components = []
        for item in queryset.order_by('sort_order', 'type'):
            components.append({
                'type': item.type,
                'name': item.name,
                'category': item.category,
                'description': item.description,
                'schema': item.schema or {},
                'default_config': item.default_config or {},
                'enabled': item.enabled,
                'sort_order': item.sort_order,
            })

        manifest = {
            'name': name,
            'version': version,
            'description': description,
            'author': author,
            'components': components,
        }

        if export_format == 'json':
            content = json.dumps(manifest, ensure_ascii=False, indent=2)
            content_type = 'application/json'
            filename = f'{name}.json'
        else:
            content = yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False)
            content_type = 'application/x-yaml'
            filename = f'{name}.yaml'

        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class UiCustomComponentDefinitionViewSet(viewsets.ModelViewSet):
    """UI自定义组件定义视图集"""
    queryset = UiCustomComponentDefinition.objects.all()  # type: ignore[attr-defined]
    serializer_class = UiCustomComponentDefinitionSerializer

    def get_queryset(self):
        queryset = UiCustomComponentDefinition.objects.all()  # type: ignore[attr-defined]
        enabled = self.request.query_params.get('enabled')
        if enabled is not None:
            if enabled in ('1', 'true', 'True'):
                queryset = queryset.filter(enabled=True)
            elif enabled in ('0', 'false', 'False'):
                queryset = queryset.filter(enabled=False)
        return queryset.order_by('sort_order', '-updated_at')

    def destroy(self, request, *args, **kwargs):
        """删除UI自定义组件定义"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'code': 0,
            'msg': '删除成功'
        }, status=status.HTTP_200_OK)


