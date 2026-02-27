# -*- coding: utf-8 -*-
"""
报告相关视图
"""
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import logging
import os

from ..models import UiTestExecution

logger = logging.getLogger(__name__)


@csrf_exempt  # 允许跨域访问
@require_http_methods(["GET"])  # 只允许 GET 请求
def serve_report_file(request, execution_id, file_path=''):
    """提供报告文件访问（用于 Allure 报告）
    
    支持访问报告目录下的所有文件，包括：
    - index.html（主页面）
    - 静态资源（CSS、JS、图片等）
    - JSON 数据文件
    
    使用方式：
    - 访问主页面: /api/ui_test/executions/{id}/report/
    - 访问资源文件: /api/ui_test/executions/{id}/report/data/test-cases.json
    
    注意：此视图允许匿名访问，不需要认证。
    """
    try:
        execution = get_object_or_404(UiTestExecution, id=execution_id)
        
        if not execution.report_path:
            logger.error(f"执行记录 {execution_id} 的报告路径为空")
            raise Http404("报告路径不存在")
        
        # 如果 file_path 为空，返回 index.html
        if not file_path or file_path == '':
            file_path = 'index.html'
        
        # 报告路径是绝对路径
        report_dir = execution.report_path
        
        # 构建完整文件路径
        full_path = os.path.join(report_dir, file_path)
        
        # 安全检查：确保文件在报告目录内（防止路径遍历攻击）
        report_dir_abs = os.path.abspath(report_dir)
        full_path_abs = os.path.abspath(full_path)
        
        logger.debug(f"报告文件访问: execution_id={execution_id}, file_path={file_path}, full_path={full_path_abs}")
        
        if not full_path_abs.startswith(report_dir_abs):
            logger.error(f"路径安全检查失败: {full_path_abs} 不在 {report_dir_abs} 内")
            raise Http404("无效的文件路径")
        
        # 检查文件是否存在
        if not os.path.exists(full_path_abs):
            logger.error(f"文件不存在: {full_path_abs}")
            raise Http404(f"文件不存在: {file_path}")
        
        if not os.path.isfile(full_path_abs):
            logger.error(f"路径不是文件: {full_path_abs}")
            raise Http404(f"路径不是文件: {file_path}")
        
        # 返回文件
        try:
            file_handle = open(full_path_abs, 'rb')
            content_type = _get_content_type(file_path)
            response = FileResponse(file_handle, content_type=content_type)
            # 设置文件名，方便浏览器下载（如果需要）
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
            logger.info(f"成功返回报告文件: {file_path}, content_type={content_type}")
            return response
        except Exception as e:
            logger.error(f"读取报告文件失败: {full_path_abs}, error: {e}", exc_info=True)
            raise Http404(f"读取文件失败: {file_path}")
    except Http404:
        raise
    except Exception as e:
        logger.error(f"处理报告文件请求失败: execution_id={execution_id}, file_path={file_path}, error: {e}", exc_info=True)
        raise Http404(f"处理请求失败: {str(e)}")


def _get_content_type(file_path):
    """根据文件扩展名返回 Content-Type"""
    ext = os.path.splitext(file_path)[1].lower()
    content_types = {
        '.html': 'text/html',
        '.js': 'application/javascript',
        '.css': 'text/css',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
        '.ttf': 'font/ttf',
        '.eot': 'application/vnd.ms-fontobject',
        '.txt': 'text/plain',
    }
    return content_types.get(ext, 'application/octet-stream')
