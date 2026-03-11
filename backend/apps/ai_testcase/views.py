# -*- coding: utf-8 -*-
"""
AI 用例生成 API 视图
"""
import copy
import json
import os
import logging
from django.http import HttpResponse, StreamingHttpResponse
from django.conf import settings
# 注意：Django 4.2 的 @csrf_exempt 装饰器会把 async 视图包裹成 sync 函数，
# 导致 "unawaited coroutine" 错误。改用直接设置 .csrf_exempt = True 属性的方式。
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AiTestcaseGeneration
from .serializers import (
    AiTestcaseGenerationSerializer,
    GenerateRequestSerializer,
    RegenerateModuleRequestSerializer,
)
from .services.kimi_client import KimiClient
from .services.xmind_builder import XMindBuilder
from .services.file_processor import FileProcessor, FileProcessError
from .services.prompts import REVIEW_DIMENSIONS

logger = logging.getLogger(__name__)

# XMind 输出目录
XMIND_OUTPUT_DIR = os.path.join(settings.BASE_DIR, 'apps', 'ai_testcase', 'output')
os.makedirs(XMIND_OUTPUT_DIR, exist_ok=True)

# 上传文件持久化目录
UPLOADS_DIR = os.path.join(settings.BASE_DIR, 'apps', 'ai_testcase', 'uploads')
os.makedirs(UPLOADS_DIR, exist_ok=True)


def _save_uploaded_files(uploaded_files, record_id: int) -> list:
    """
    将上传文件持久化保存到 uploads/{record_id}/ 目录

    Returns:
        保存后的文件路径列表
    """
    record_dir = os.path.join(UPLOADS_DIR, str(record_id))
    os.makedirs(record_dir, exist_ok=True)

    saved_paths = []
    for f in uploaded_files:
        filename = f.name if hasattr(f, 'name') else f'file_{len(saved_paths)}'
        filepath = os.path.join(record_dir, filename)

        with open(filepath, 'wb') as dest:
            f.seek(0)
            for chunk in f.chunks() if hasattr(f, 'chunks') else [f.read()]:
                dest.write(chunk)
            f.seek(0)

        saved_paths.append(filepath)
        logger.info(f"[AI用例] 持久化保存文件: {filepath}")

    return saved_paths


def _merge_module(result_json: dict, module_name: str, new_module_data: dict) -> dict:
    """
    将新生成的模块数据替换到 result_json 中

    Args:
        result_json: DB 中已有的完整 JSON
        module_name: 要替换的模块名
        new_module_data: AI 新生成的单模块 JSON (含 name, functions)

    Returns:
        合并后的完整 JSON（新 dict，不修改原始数据）
    """
    merged = copy.deepcopy(result_json)

    for i, mod in enumerate(merged["modules"]):
        if mod["name"] == module_name:
            merged["modules"][i] = new_module_data
            return merged

    raise ValueError(f"模块 '{module_name}' 不存在于当前用例中")


def _apply_review_changes(result_json: dict, changes: list) -> tuple:
    """
    程序化地将 AI 返回的增量变更指令应用到用例 JSON 上

    Args:
        result_json: 当前完整的用例 JSON
        changes: AI 返回的变更指令列表

    Returns:
        (修改后的完整 JSON, 应用统计字符串)
    """
    data = copy.deepcopy(result_json)
    modules = data.get('modules', [])

    stats = {'deleted': 0, 'modified': 0, 'added_cases': 0, 'added_functions': 0, 'skipped': 0}

    # 建立模块索引: name -> module dict
    mod_index = {m['name']: m for m in modules}

    for change in changes:
        action = change.get('action', '')
        mod_name = change.get('module', '')

        if action == 'delete_case':
            func_name = change.get('function', '')
            case_name = change.get('case_name', '')
            mod = mod_index.get(mod_name)
            if not mod:
                stats['skipped'] += 1
                continue
            found = False
            for func in mod.get('functions', []):
                if func['name'] == func_name:
                    original_len = len(func.get('cases', []))
                    func['cases'] = [c for c in func.get('cases', []) if c.get('name') != case_name]
                    if len(func['cases']) < original_len:
                        stats['deleted'] += 1
                        found = True
                    break
            if not found:
                stats['skipped'] += 1

        elif action == 'modify_case':
            func_name = change.get('function', '')
            case_name = change.get('case_name', '')
            updates = change.get('updates', {})
            mod = mod_index.get(mod_name)
            if not mod or not updates:
                stats['skipped'] += 1
                continue
            found = False
            for func in mod.get('functions', []):
                if func['name'] == func_name:
                    for case in func.get('cases', []):
                        if case.get('name') == case_name:
                            for key, val in updates.items():
                                if key in ('name', 'steps', 'expected', 'priority', 'precondition') and val:
                                    case[key] = val
                            stats['modified'] += 1
                            found = True
                            break
                    break
            if not found:
                stats['skipped'] += 1

        elif action == 'add_case':
            func_name = change.get('function', '')
            new_case = change.get('case', {})
            mod = mod_index.get(mod_name)
            if not mod or not new_case.get('name'):
                stats['skipped'] += 1
                continue
            found = False
            for func in mod.get('functions', []):
                if func['name'] == func_name:
                    if 'cases' not in func:
                        func['cases'] = []
                    func['cases'].append(new_case)
                    stats['added_cases'] += 1
                    found = True
                    break
            if not found:
                # 功能点不存在，自动创建
                mod.setdefault('functions', []).append({
                    'name': func_name,
                    'cases': [new_case]
                })
                stats['added_cases'] += 1

        elif action == 'add_function':
            new_func = change.get('function', {})
            mod = mod_index.get(mod_name)
            if not mod or not new_func.get('name'):
                stats['skipped'] += 1
                continue
            mod.setdefault('functions', []).append(new_func)
            stats['added_functions'] += 1

        elif action == 'move_function':
            from_mod_name = change.get('from_module', '')
            func_name = change.get('function_name', '')
            to_mod_name = change.get('to_module', '')
            from_mod = mod_index.get(from_mod_name)
            to_mod = mod_index.get(to_mod_name)
            if not from_mod or not to_mod or not func_name:
                stats['skipped'] += 1
                continue
            # 从源模块摘出功能点
            moved_func = None
            new_funcs = []
            for func in from_mod.get('functions', []):
                if func['name'] == func_name:
                    moved_func = func
                else:
                    new_funcs.append(func)
            if moved_func:
                from_mod['functions'] = new_funcs
                to_mod.setdefault('functions', []).append(moved_func)
                stats['modified'] += 1
            else:
                stats['skipped'] += 1

        elif action == 'delete_function':
            func_name = change.get('function_name', '')
            mod = mod_index.get(mod_name)
            if not mod or not func_name:
                stats['skipped'] += 1
                continue
            original_len = len(mod.get('functions', []))
            mod['functions'] = [f for f in mod.get('functions', []) if f['name'] != func_name]
            if len(mod['functions']) < original_len:
                stats['deleted'] += 1
            else:
                stats['skipped'] += 1

        elif action == 'delete_module':
            if mod_name in mod_index:
                data['modules'] = [m for m in data['modules'] if m['name'] != mod_name]
                del mod_index[mod_name]
                stats['deleted'] += 1
            else:
                stats['skipped'] += 1

        else:
            stats['skipped'] += 1

    # 清理空节点：删光用例的功能点、删光功能点的模块
    for mod in data.get('modules', []):
        mod['functions'] = [
            f for f in mod.get('functions', [])
            if f.get('cases')  # 只保留有用例的功能点
        ]
    data['modules'] = [
        m for m in data['modules']
        if m.get('functions')  # 只保留有功能点的模块
    ]

    summary = (
        f"删除 {stats['deleted']} 条, "
        f"修改 {stats['modified']} 条, "
        f"新增 {stats['added_cases']} 条用例 + {stats['added_functions']} 个功能点"
    )
    if stats['skipped']:
        summary += f", 跳过 {stats['skipped']} 条（未匹配到）"

    return data, summary


def _add_cors_headers(response):
    """给响应加上 CORS 头（SSE 直连时浏览器需要）"""
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


async def generate_stream_view(request):
    """
    SSE 流式生成测试用例（异步视图，Daphne 下真正流式推送）

    支持两种提交方式：
    1. JSON:      {"requirement": "...", "use_thinking": false}
    2. FormData:  requirement(文字) + use_thinking(布尔) + files(文件列表)

    POST /api/ai_testcase/generate-stream/

    Response: text/event-stream
        data: {"type": "chunk", "content": "..."}
        data: {"type": "done", "record_id": 1, "data": {...}, ...}
        data: {"type": "error", "error": "..."}
    """
    # 处理 CORS 预检请求（前端直连后端时浏览器会先发 OPTIONS）
    if request.method == 'OPTIONS':
        resp = HttpResponse(status=200)
        return _add_cors_headers(resp)

    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    # ---------- 解析请求参数（兼容 JSON 和 FormData） ----------
    extracted_texts = []
    images = []
    file_warnings = []

    content_type = request.content_type or ''

    uploaded_files = []  # 用于后续持久化

    if 'multipart' in content_type:
        # FormData 模式（带文件上传）
        from django.http.multipartparser import MultiPartParser
        from asgiref.sync import sync_to_async

        # Daphne 下 request.POST / request.FILES 需要同步访问
        _post = await sync_to_async(lambda: request.POST)()
        _files = await sync_to_async(lambda: request.FILES)()

        requirement = _post.get('requirement', '').strip()
        use_thinking = _post.get('use_thinking', 'false').lower() in ('true', '1', 'yes')
        mode = _post.get('mode', 'comprehensive')  # 新增模式参数
        uploaded_files = _files.getlist('files')

        # 处理上传的文件
        if uploaded_files:
            try:
                processor = FileProcessor()
                file_result = await sync_to_async(processor.process_files)(uploaded_files)
                extracted_texts = file_result['texts']
                images = file_result['images']
                file_warnings = file_result['warnings']
            except FileProcessError as e:
                return _add_cors_headers(HttpResponse(str(e), status=400))
            except Exception as e:
                logger.exception(f"[AI用例] 文件处理异常: {e}")
                return _add_cors_headers(HttpResponse(f'文件处理失败: {str(e)}', status=400))
    else:
        # JSON 模式（纯文本，兼容原有接口）
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

        requirement = body.get('requirement', '').strip()
        use_thinking = body.get('use_thinking', False)
        mode = body.get('mode', 'comprehensive')  # 新增模式参数

    # 校验：至少要有文字输入或上传文件
    if not requirement and not extracted_texts and not images:
        return _add_cors_headers(HttpResponse('请输入需求描述或上传文件', status=400))

    # 用于 DB 记录的需求摘要
    requirement_summary = requirement
    if not requirement_summary and extracted_texts:
        requirement_summary = f"[附件] {', '.join(t['source'] for t in extracted_texts[:3])}"
    if images and not requirement_summary:
        requirement_summary = f"[图片] {', '.join(img['source'] for img in images[:3])}"

    has_attachments = bool(extracted_texts or images)

    async def event_stream():
        from asgiref.sync import sync_to_async
        record = await sync_to_async(AiTestcaseGeneration.objects.create)(
            requirement=requirement_summary,
            use_thinking=use_thinking,
            status='generating'
        )

        # 持久化上传文件（供后续模块重新生成使用）
        if uploaded_files:
            saved_paths = await sync_to_async(_save_uploaded_files)(uploaded_files, record.id)
            record.source_files = saved_paths
            await sync_to_async(record.save)(update_fields=['source_files'])

        start_data = {'type': 'start', 'record_id': record.id}
        if file_warnings:
            start_data['warnings'] = file_warnings
        if has_attachments:
            start_data['attachment_info'] = {
                'text_count': len(extracted_texts),
                'image_count': len(images),
                'sources': [t['source'] for t in extracted_texts] + [img['source'] for img in images]
            }
        yield f"data: {json.dumps(start_data, ensure_ascii=False)}\n\n"

        try:
            client = KimiClient()

            # 根据是否有附件选择不同的生成方法
            if has_attachments:
                gen = client.generate_testcases_multimodal_stream_async(
                    requirement, extracted_texts, images, use_thinking=use_thinking, mode=mode
                )
            else:
                gen = client.generate_testcases_stream_async(
                    requirement, use_thinking=use_thinking, mode=mode
                )

            async for event in gen:
                if event['type'] == 'chunk':
                    yield f"data: {json.dumps({'type': 'chunk', 'content': event['content']}, ensure_ascii=False)}\n\n"

                elif event['type'] == 'done':
                    full_content = event['content']
                    usage = event['usage']

                    # 解析 JSON
                    data = KimiClient._parse_json(full_content)

                    if data is None:
                        record.status = 'failed'
                        record.error_message = 'AI 返回的内容无法解析为 JSON'
                        record.raw_content = full_content
                        await sync_to_async(record.save)()
                        yield f"data: {json.dumps({'type': 'error', 'error': 'AI 返回的内容无法解析为 JSON', 'record_id': record.id}, ensure_ascii=False)}\n\n"
                        return

                    # 更新记录
                    record.raw_content = full_content
                    record.prompt_tokens = usage['prompt_tokens']
                    record.completion_tokens = usage['completion_tokens']
                    record.total_tokens = usage['total_tokens']
                    record.result_json = data
                    record.count_stats()

                    # 生成 XMind
                    title = data.get('title', f'testcase_{record.id}')
                    xmind_filename = f"{title}.xmind"
                    xmind_path = os.path.join(XMIND_OUTPUT_DIR, xmind_filename)
                    await sync_to_async(XMindBuilder.build_and_save)(data, xmind_path)
                    record.xmind_file = xmind_path

                    record.status = 'success'
                    await sync_to_async(record.save)()

                    yield f"data: {json.dumps({'type': 'done', 'record_id': record.id, 'title': title, 'module_count': record.module_count, 'case_count': record.case_count, 'usage': usage, 'data': data}, ensure_ascii=False)}\n\n"

                elif event['type'] == 'error':
                    record.status = 'failed'
                    record.error_message = event['error']
                    await sync_to_async(record.save)()
                    yield f"data: {json.dumps({'type': 'error', 'error': event['error'], 'record_id': record.id}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception(f"[AI用例] 流式生成异常: {e}")
            record.status = 'failed'
            record.error_message = str(e)
            await sync_to_async(record.save)()
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'record_id': record.id}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    # 防止 GZipMiddleware 压缩 SSE 流（压缩会导致缓冲）
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response)

# Django 4.2 兼容：直接设置属性而非使用 @csrf_exempt 装饰器
generate_stream_view.csrf_exempt = True


async def generate_from_structure_stream_view(request):
    """
    SSE 流式：基于功能点结构生成测试用例（需求智能体结构直传，方案 A）。

    POST /api/ai_testcase/generate-from-structure/
    Body: {
        "structure": { "title": "...", "modules": [{ "name": "...", "functions": [{ "name", "description", "acceptance_points", "priority", "test_hint" }] }] },
        "requirement": "可选需求摘要",
        "use_thinking": false,
        "source_requirement_task_id": 123
    }

    Response: text/event-stream
        data: {"type": "start", "record_id": 1, "source_requirement_task_id": 123}
        data: {"type": "chunk", "content": "..."}
        data: {"type": "done", "record_id": 1, "data": {...}, ...}
        data: {"type": "error", "error": "..."}
    """
    if request.method == 'OPTIONS':
        resp = HttpResponse(status=200)
        return _add_cors_headers(resp)

    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    structure = body.get('structure')
    if not structure or not isinstance(structure, dict):
        return _add_cors_headers(HttpResponse('缺少或无效的 structure（功能点 JSON）', status=400))
    if not structure.get('modules'):
        return _add_cors_headers(HttpResponse('structure 需包含 modules 数组', status=400))

    requirement = (body.get('requirement') or '').strip()
    use_thinking = body.get('use_thinking', False)
    source_requirement_task_id = body.get('source_requirement_task_id')

    requirement_summary = requirement or f"[来自功能点结构] {structure.get('title', '')}"

    async def event_stream():
        from asgiref.sync import sync_to_async
        record = await sync_to_async(AiTestcaseGeneration.objects.create)(
            requirement=requirement_summary,
            use_thinking=use_thinking,
            status='generating'
        )
        start_data = {'type': 'start', 'record_id': record.id}
        if source_requirement_task_id is not None:
            start_data['source_requirement_task_id'] = source_requirement_task_id
        yield f"data: {json.dumps(start_data, ensure_ascii=False)}\n\n"

        try:
            client = KimiClient()
            gen = client.generate_testcases_from_structure_stream_async(
                structure, requirement_summary=requirement or None, use_thinking=use_thinking
            )

            async for event in gen:
                if event['type'] == 'chunk':
                    yield f"data: {json.dumps({'type': 'chunk', 'content': event['content']}, ensure_ascii=False)}\n\n"
                elif event['type'] == 'done':
                    full_content = event['content']
                    usage = event['usage']
                    data = KimiClient._parse_json(full_content)
                    if data is None:
                        record.status = 'failed'
                        record.error_message = 'AI 返回的内容无法解析为 JSON'
                        record.raw_content = full_content
                        await sync_to_async(record.save)()
                        yield f"data: {json.dumps({'type': 'error', 'error': 'AI 返回的内容无法解析为 JSON', 'record_id': record.id}, ensure_ascii=False)}\n\n"
                        return
                    record.raw_content = full_content
                    record.prompt_tokens = usage['prompt_tokens']
                    record.completion_tokens = usage['completion_tokens']
                    record.total_tokens = usage['total_tokens']
                    record.result_json = data
                    record.count_stats()
                    title = data.get('title', f'testcase_{record.id}')
                    xmind_filename = f"{title}.xmind"
                    xmind_path = os.path.join(XMIND_OUTPUT_DIR, xmind_filename)
                    await sync_to_async(XMindBuilder.build_and_save)(data, xmind_path)
                    record.xmind_file = xmind_path
                    record.status = 'success'
                    await sync_to_async(record.save)()

                    # 回写血缘：将本次用例记录 ID 追加到需求任务的 downstream_testcases
                    if source_requirement_task_id is not None:
                        def _append_downstream():
                            from apps.ai_requirement.models import AiRequirementTask
                            try:
                                task = AiRequirementTask.objects.get(id=source_requirement_task_id)
                                downstream = list(task.downstream_testcases or [])
                                if record.id not in downstream:
                                    downstream.append(record.id)
                                    task.downstream_testcases = downstream
                                    task.save(update_fields=['downstream_testcases', 'updated_at'])
                                    logger.info(f"[AI用例] 已回写 downstream_testcases: task_id={source_requirement_task_id}, record_id={record.id}")
                            except AiRequirementTask.DoesNotExist:
                                logger.warning(f"[AI用例] 回写时需求任务不存在: task_id={source_requirement_task_id}")

                        await sync_to_async(_append_downstream)()

                    yield f"data: {json.dumps({'type': 'done', 'record_id': record.id, 'title': title, 'module_count': record.module_count, 'case_count': record.case_count, 'usage': usage, 'data': data}, ensure_ascii=False)}\n\n"
                elif event['type'] == 'error':
                    record.status = 'failed'
                    record.error_message = event['error']
                    await sync_to_async(record.save)()
                    yield f"data: {json.dumps({'type': 'error', 'error': event['error'], 'record_id': record.id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception(f"[AI用例] 基于结构流式生成异常: {e}")
            record.status = 'failed'
            record.error_message = str(e)
            await sync_to_async(record.save)()
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'record_id': record.id}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response)


generate_from_structure_stream_view.csrf_exempt = True


async def regenerate_module_stream_view(request):
    """
    SSE 流式模块级重新生成测试用例

    POST /api/ai_testcase/regenerate-module-stream/
    {
        "record_id": 1,
        "module_name": "用户管理",
        "adjustment": "补充更多异常场景和边界值用例",
        "use_thinking": false
    }

    Response: text/event-stream
        data: {"type": "start", "record_id": 1, "module_name": "..."}
        data: {"type": "chunk", "content": "..."}
        data: {"type": "done", "record_id": 1, "data": {...}, ...}
        data: {"type": "error", "error": "..."}
    """
    # CORS 预检
    if request.method == 'OPTIONS':
        resp = HttpResponse(status=200)
        return _add_cors_headers(resp)

    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    # ---------- 解析请求参数 ----------
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    record_id = body.get('record_id')
    module_name = body.get('module_name', '').strip()
    module_requirement = body.get('module_requirement', '').strip()
    adjustment = body.get('adjustment', '').strip()
    use_thinking = body.get('use_thinking', False)

    # ---------- 参数校验 ----------
    if not record_id:
        return _add_cors_headers(HttpResponse('缺少 record_id', status=400))
    if not module_name:
        return _add_cors_headers(HttpResponse('缺少 module_name', status=400))
    if not module_requirement and not adjustment:
        return _add_cors_headers(HttpResponse('请至少填写「补充需求」或「调整意见」中的一项', status=400))

    # ---------- 查询记录 ----------
    from asgiref.sync import sync_to_async

    try:
        record = await sync_to_async(AiTestcaseGeneration.objects.get)(id=record_id)
    except AiTestcaseGeneration.DoesNotExist:
        return _add_cors_headers(HttpResponse(f'记录不存在: id={record_id}', status=404))

    if record.status != 'success':
        return _add_cors_headers(HttpResponse(
            f'该记录状态为 {record.status}，只有 success 状态的记录才能进行模块重新生成', status=400
        ))

    if not record.result_json:
        return _add_cors_headers(HttpResponse('该记录没有用例数据', status=400))

    # ---------- 校验模块名是否存在 ----------
    existing_modules = record.result_json.get('modules', [])
    module_names = [m['name'] for m in existing_modules]

    if module_name not in module_names:
        return _add_cors_headers(HttpResponse(
            json.dumps({
                'error': f"模块 '{module_name}' 不存在",
                'available_modules': module_names
            }, ensure_ascii=False),
            status=400,
            content_type='application/json'
        ))

    # 提取该模块的已有用例
    existing_module_json = next(m for m in existing_modules if m['name'] == module_name)

    async def event_stream():
        from asgiref.sync import sync_to_async

        # 标记为生成中（防止并发）
        record.status = 'generating'
        await sync_to_async(record.save)(update_fields=['status'])

        yield f"data: {json.dumps({'type': 'start', 'record_id': record.id, 'module_name': module_name}, ensure_ascii=False)}\n\n"

        try:
            # 从持久化的源文件重新提取文本和图片
            extracted_texts = []
            images = []
            source_warnings = []

            if record.source_files:
                processor = FileProcessor()
                file_result = await sync_to_async(processor.process_local_files)(record.source_files)
                extracted_texts = file_result['texts']
                images = file_result['images']
                source_warnings = file_result['warnings']

                if source_warnings:
                    yield f"data: {json.dumps({'type': 'warning', 'warnings': source_warnings}, ensure_ascii=False)}\n\n"

            # 调用 Kimi AI 进行模块级重新生成
            client = KimiClient()
            gen = client.regenerate_module_stream_async(
                module_name=module_name,
                existing_module_json=existing_module_json,
                module_requirement=module_requirement,
                adjustment=adjustment,
                extracted_texts=extracted_texts,
                images=images,
                requirement=record.requirement,
                use_thinking=use_thinking,
            )

            async for event in gen:
                if event['type'] == 'chunk':
                    yield f"data: {json.dumps({'type': 'chunk', 'content': event['content']}, ensure_ascii=False)}\n\n"

                elif event['type'] == 'done':
                    full_content = event['content']
                    usage = event['usage']

                    # 解析 AI 返回的单模块 JSON
                    module_data = KimiClient._parse_json(full_content)

                    if module_data is None:
                        record.status = 'success'  # 恢复原状态，旧数据不受影响
                        await sync_to_async(record.save)(update_fields=['status'])
                        yield f"data: {json.dumps({'type': 'error', 'error': 'AI 返回的内容无法解析为 JSON，原用例数据不受影响', 'record_id': record.id}, ensure_ascii=False)}\n\n"
                        return

                    # 校验返回格式
                    if 'functions' not in module_data:
                        record.status = 'success'
                        await sync_to_async(record.save)(update_fields=['status'])
                        yield f"data: {json.dumps({'type': 'error', 'error': 'AI 返回的 JSON 缺少 functions 字段，原用例数据不受影响', 'record_id': record.id}, ensure_ascii=False)}\n\n"
                        return

                    # 强制保证模块名一致
                    module_data['name'] = module_name

                    # JSON 合并：替换目标模块，保留其他模块
                    try:
                        merged_json = _merge_module(record.result_json, module_name, module_data)
                    except ValueError as e:
                        record.status = 'success'
                        await sync_to_async(record.save)(update_fields=['status'])
                        yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'record_id': record.id}, ensure_ascii=False)}\n\n"
                        return

                    # 更新 DB 记录
                    record.result_json = merged_json
                    record.count_stats()

                    # 累计 Token 消耗
                    record.prompt_tokens += usage['prompt_tokens']
                    record.completion_tokens += usage['completion_tokens']
                    record.total_tokens += usage['total_tokens']

                    # 重新生成 XMind 文件
                    title = merged_json.get('title', f'testcase_{record.id}')
                    xmind_filename = f"{title}.xmind"
                    xmind_path = os.path.join(XMIND_OUTPUT_DIR, xmind_filename)
                    await sync_to_async(XMindBuilder.build_and_save)(merged_json, xmind_path)
                    record.xmind_file = xmind_path

                    record.status = 'success'
                    await sync_to_async(record.save)()

                    yield f"data: {json.dumps({'type': 'done', 'record_id': record.id, 'module_name': module_name, 'module_count': record.module_count, 'case_count': record.case_count, 'usage': usage, 'data': merged_json}, ensure_ascii=False)}\n\n"

                elif event['type'] == 'error':
                    record.status = 'success'  # 恢复原状态
                    await sync_to_async(record.save)(update_fields=['status'])
                    yield f"data: {json.dumps({'type': 'error', 'error': event['error'], 'record_id': record.id}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception(f"[AI用例] 模块重新生成异常: {e}")
            record.status = 'success'  # 恢复原状态，旧数据不受影响
            await sync_to_async(record.save)(update_fields=['status'])
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'record_id': record.id}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response)

# Django 4.2 兼容：直接设置属性而非使用 @csrf_exempt 装饰器
regenerate_module_stream_view.csrf_exempt = True


async def review_stream_view(request):
    """
    SSE 流式用例评审（分维度逐项扫描）

    POST /api/ai_testcase/review-stream/
    {"record_id": 1}

    SSE 事件类型：
    - start: 评审开始，含 dimensions 列表
    - dimension_start: 某个维度开始，含 dimension_key, dimension_label, index, total
    - chunk: 当前维度的流式文本
    - dimension_done: 某个维度完成，含该维度的 items
    - done: 全部维度完成，含合并后的所有 items
    - error: 出错
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    record_id = body.get('record_id')

    if not record_id:
        return _add_cors_headers(HttpResponse('缺少 record_id', status=400))

    from asgiref.sync import sync_to_async

    try:
        record = await sync_to_async(AiTestcaseGeneration.objects.get)(id=record_id)
    except AiTestcaseGeneration.DoesNotExist:
        return _add_cors_headers(HttpResponse(f'记录不存在: id={record_id}', status=404))

    if record.status != 'success' or not record.result_json:
        return _add_cors_headers(HttpResponse('该记录没有可评审的用例数据', status=400))

    async def event_stream():
        from asgiref.sync import sync_to_async

        dimensions = REVIEW_DIMENSIONS
        dim_labels = [d['label'] for d in dimensions]
        total = len(dimensions)

        yield f"data: {json.dumps({'type': 'start', 'record_id': record.id, 'dimensions': dim_labels, 'total': total}, ensure_ascii=False)}\n\n"

        try:
            # 从源文件重新提取文本和图片
            extracted_texts = []
            images = []

            if record.source_files:
                processor = FileProcessor()
                file_result = await sync_to_async(processor.process_local_files)(record.source_files)
                extracted_texts = file_result['texts']
                images = file_result['images']

            client = KimiClient()
            all_items = []
            total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            global_id = 1

            for idx, dim in enumerate(dimensions):
                dim_key = dim['key']
                dim_label = dim['label']

                yield f"data: {json.dumps({'type': 'dimension_start', 'dimension_key': dim_key, 'dimension_label': dim_label, 'index': idx + 1, 'total': total}, ensure_ascii=False)}\n\n"

                gen = client.review_dimension_stream_async(
                    dimension_key=dim_key,
                    result_json=record.result_json,
                    extracted_texts=extracted_texts,
                    images=images,
                    requirement=record.requirement,
                )

                async for event in gen:
                    if event['type'] == 'chunk':
                        yield f"data: {json.dumps({'type': 'chunk', 'content': event['content'], 'dimension_key': dim_key}, ensure_ascii=False)}\n\n"
                    elif event['type'] == 'done':
                        full_content = event['content']
                        usage = event['usage']

                        total_usage['prompt_tokens'] += usage['prompt_tokens']
                        total_usage['completion_tokens'] += usage['completion_tokens']
                        total_usage['total_tokens'] += usage['total_tokens']

                        dim_data = KimiClient._parse_json(full_content)
                        dim_items = []
                        if dim_data and 'items' in dim_data:
                            for item in dim_data['items']:
                                item['id'] = global_id
                                global_id += 1
                                dim_items.append(item)
                            all_items.extend(dim_items)

                        yield f"data: {json.dumps({'type': 'dimension_done', 'dimension_key': dim_key, 'dimension_label': dim_label, 'items_count': len(dim_items), 'items': dim_items}, ensure_ascii=False)}\n\n"

                    elif event['type'] == 'error':
                        # 单维度失败不中断，继续下一个
                        err_msg = event.get('error', '未知错误')
                        warning_text = f'{dim_label}维度评审失败: {err_msg}'
                        dim_done_data = {'type': 'dimension_done', 'dimension_key': dim_key, 'dimension_label': dim_label, 'items_count': 0, 'items': [], 'warning': warning_text}
                        yield f"data: {json.dumps(dim_done_data, ensure_ascii=False)}\n\n"

            # 全部维度完成，按 severity 排序
            severity_order = {'high': 0, 'medium': 1, 'low': 2}
            all_items.sort(key=lambda x: severity_order.get(x.get('severity', 'low'), 3))

            # 重新编号
            for i, item in enumerate(all_items, 1):
                item['id'] = i

            review_data = {
                "summary": f"共扫描 {total} 个维度，发现 {len(all_items)} 个问题",
                "total_issues": len(all_items),
                "items": all_items,
            }

            yield f"data: {json.dumps({'type': 'done', 'record_id': record.id, 'data': review_data, 'usage': total_usage}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception(f"[AI用例] 分维度评审异常: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response)

review_stream_view.csrf_exempt = True


async def apply_review_stream_view(request):
    """
    SSE 流式采纳评审意见

    POST /api/ai_testcase/apply-review-stream/
    {"record_id": 1, "selected_items": [...], "use_thinking": false}
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200))
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405))

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400))

    record_id = body.get('record_id')
    selected_items = body.get('selected_items', [])
    use_thinking = body.get('use_thinking', False)

    if not record_id:
        return _add_cors_headers(HttpResponse('缺少 record_id', status=400))
    if not selected_items:
        return _add_cors_headers(HttpResponse('未选择任何评审项', status=400))

    from asgiref.sync import sync_to_async

    try:
        record = await sync_to_async(AiTestcaseGeneration.objects.get)(id=record_id)
    except AiTestcaseGeneration.DoesNotExist:
        return _add_cors_headers(HttpResponse(f'记录不存在: id={record_id}', status=404))

    if record.status != 'success' or not record.result_json:
        return _add_cors_headers(HttpResponse('该记录没有可修改的用例数据', status=400))

    async def event_stream():
        from asgiref.sync import sync_to_async

        record.status = 'generating'
        await sync_to_async(record.save)(update_fields=['status'])

        yield f"data: {json.dumps({'type': 'start', 'record_id': record.id, 'selected_count': len(selected_items)}, ensure_ascii=False)}\n\n"

        try:
            client = KimiClient()
            gen = client.apply_review_stream_async(
                result_json=record.result_json,
                selected_items=selected_items,
                use_thinking=use_thinking,
            )

            async for event in gen:
                if event['type'] == 'chunk':
                    yield f"data: {json.dumps({'type': 'chunk', 'content': event['content']}, ensure_ascii=False)}\n\n"
                elif event['type'] == 'done':
                    full_content = event['content']
                    usage = event['usage']

                    change_data = KimiClient._parse_json(full_content)

                    if change_data is None:
                        record.status = 'success'
                        await sync_to_async(record.save)(update_fields=['status'])
                        yield f"data: {json.dumps({'type': 'error', 'error': 'AI 返回内容无法解析为 JSON，原用例数据不受影响'}, ensure_ascii=False)}\n\n"
                        return

                    changes = change_data.get('changes', [])
                    if not changes:
                        record.status = 'success'
                        await sync_to_async(record.save)(update_fields=['status'])
                        yield f"data: {json.dumps({'type': 'error', 'error': 'AI 未返回任何变更指令，原用例数据不受影响'}, ensure_ascii=False)}\n\n"
                        return

                    # 程序化应用变更（不依赖 AI 输出完整 JSON）
                    try:
                        new_data, apply_summary = _apply_review_changes(record.result_json, changes)
                    except Exception as apply_err:
                        logger.exception(f"[AI用例] 应用变更失败: {apply_err}")
                        record.status = 'success'
                        await sync_to_async(record.save)(update_fields=['status'])
                        yield f"data: {json.dumps({'type': 'error', 'error': f'变更应用失败: {str(apply_err)}'}, ensure_ascii=False)}\n\n"
                        return

                    # 更新记录
                    record.result_json = new_data
                    record.count_stats()
                    record.prompt_tokens += usage['prompt_tokens']
                    record.completion_tokens += usage['completion_tokens']
                    record.total_tokens += usage['total_tokens']

                    # 重新生成 XMind
                    title = new_data.get('title', f'testcase_{record.id}')
                    xmind_filename = f"{title}.xmind"
                    xmind_path = os.path.join(XMIND_OUTPUT_DIR, xmind_filename)
                    await sync_to_async(XMindBuilder.build_and_save)(new_data, xmind_path)
                    record.xmind_file = xmind_path

                    record.status = 'success'
                    await sync_to_async(record.save)()

                    yield f"data: {json.dumps({'type': 'done', 'record_id': record.id, 'module_count': record.module_count, 'case_count': record.case_count, 'usage': usage, 'data': new_data, 'apply_summary': apply_summary}, ensure_ascii=False)}\n\n"

                elif event['type'] == 'error':
                    record.status = 'success'
                    await sync_to_async(record.save)(update_fields=['status'])
                    yield f"data: {json.dumps({'type': 'error', 'error': event['error']}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception(f"[AI用例] 采纳评审意见异常: {e}")
            record.status = 'success'
            await sync_to_async(record.save)(update_fields=['status'])
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response)

apply_review_stream_view.csrf_exempt = True


class AiTestcaseViewSet(viewsets.ModelViewSet):
    """AI 用例生成 ViewSet"""
    queryset = AiTestcaseGeneration.objects.all()
    serializer_class = AiTestcaseGenerationSerializer

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        """
        生成测试用例

        POST /api/ai_testcase/generations/generate/
        {
            "requirement": "功能需求描述",
            "use_thinking": false
        }
        """
        serializer = GenerateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        requirement = serializer.validated_data['requirement']
        use_thinking = serializer.validated_data.get('use_thinking', False)
        mode = serializer.validated_data.get('mode', 'comprehensive')

        # 创建记录
        record = AiTestcaseGeneration.objects.create(
            requirement=requirement,
            use_thinking=use_thinking,
            status='generating'
        )

        try:
            # 调用 Kimi API
            client = KimiClient()
            result = client.generate_testcases(requirement, use_thinking=use_thinking, mode=mode)

            # 更新 Token 消耗
            record.prompt_tokens = result['usage']['prompt_tokens']
            record.completion_tokens = result['usage']['completion_tokens']
            record.total_tokens = result['usage']['total_tokens']
            record.raw_content = result['raw_content']

            if not result['success']:
                record.status = 'failed'
                record.error_message = result['error']
                record.save()
                return Response({
                    'id': record.id,
                    'status': 'failed',
                    'error': result['error'],
                    'usage': result['usage']
                }, status=status.HTTP_200_OK)

            # 保存结构化数据
            record.result_json = result['data']
            record.count_stats()

            # 生成 XMind 文件
            title = result['data'].get('title', f'testcase_{record.id}')
            xmind_filename = f"{title}.xmind"
            xmind_path = os.path.join(XMIND_OUTPUT_DIR, xmind_filename)
            XMindBuilder.build_and_save(result['data'], xmind_path)
            record.xmind_file = xmind_path

            record.status = 'success'
            record.save()

            return Response({
                'id': record.id,
                'status': 'success',
                'title': title,
                'module_count': record.module_count,
                'case_count': record.case_count,
                'usage': result['usage'],
                'data': result['data'],
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"[AI用例] 生成异常: {e}")
            record.status = 'failed'
            record.error_message = str(e)
            record.save()
            return Response({
                'id': record.id,
                'status': 'failed',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """
        下载 XMind 文件

        GET /api/ai_testcase/generations/{id}/download/
        """
        record = self.get_object()

        if not record.result_json:
            return Response(
                {"error": "该记录没有生成结果"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            file_bytes = XMindBuilder.build_to_bytes(record.result_json)
            title = record.result_json.get('title', f'testcase_{record.id}')
            filename = f"{title}.xmind"

            response = HttpResponse(
                file_bytes,
                content_type='application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:
            logger.error(f"[AI用例] 下载失败: {e}")
            return Response(
                {"error": f"文件生成失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='preview')
    def preview(self, request, pk=None):
        """
        预览用例结构化数据

        GET /api/ai_testcase/generations/{id}/preview/
        """
        record = self.get_object()

        if not record.result_json:
            return Response(
                {"error": "该记录没有生成结果"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'id': record.id,
            'title': record.result_json.get('title', ''),
            'data': record.result_json,
            'module_count': record.module_count,
            'case_count': record.case_count,
        })

    @action(detail=False, methods=['get'], url_path='config-status')
    def config_status(self, request):
        """
        检查 Kimi API 配置状态

        GET /api/ai_testcase/generations/config-status/
        """
        api_key = getattr(settings, 'KIMI_API_KEY', '')
        return Response({
            'configured': bool(api_key),
            'model': getattr(settings, 'KIMI_MODEL', 'kimi-k2.5'),
            'base_url': getattr(settings, 'KIMI_BASE_URL', 'https://api.moonshot.cn/v1'),
            'api_key_prefix': api_key[:8] + '...' if api_key else '',
        })
