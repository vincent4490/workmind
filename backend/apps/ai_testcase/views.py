# -*- coding: utf-8 -*-
"""
AI 用例生成 API 视图
"""
import copy
import asyncio
import json
import os
import logging
import hashlib
from datetime import timedelta
from django.http import HttpResponse, StreamingHttpResponse
from django.conf import settings
from django.utils import timezone
# 注意：Django 4.2 的 @csrf_exempt 装饰器会把 async 视图包裹成 sync 函数，
# 导致 "unawaited coroutine" 错误。改用直接设置 .csrf_exempt = True 属性的方式。
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken

from .models import AiTestcaseEvent, AiTestcaseGeneration
from .serializers import (
    AiTestcaseGenerationSerializer,
    GenerateRequestSerializer,
    RegenerateModuleRequestSerializer,
    UpdateCaseRequestSerializer,
)
from .services.kimi_client import KimiClient
from .services.xmind_builder import XMindBuilder
from .services.file_processor import FileProcessor, FileProcessError
from .services.prompts import REVIEW_DIMENSIONS
from .services.schemas import validate_testcase_result, validate_changes, validate_review_items
from .utils import normalize_case_strategy_mode

logger = logging.getLogger(__name__)


def _log_event(event: str, **fields):
    """
    统一结构化日志（便于按 record/user/prompt_version 聚合统计）
    """
    try:
        logger.info(f"[ai_testcase] {event} | {json.dumps(fields, ensure_ascii=False, sort_keys=True)}")
    except Exception:
        logger.info(f"[ai_testcase] {event}")


def _normalize_review_items(items: list) -> tuple[list[dict], list[str]]:
    """
    对最终 review items 做强制规范化：
    - 尝试用 schema 校验
    - 校验失败则逐条过滤保留可解析项
    """
    warnings: list[str] = []
    try:
        validated = validate_review_items(items)
        normalized = [i.model_dump(exclude_none=True) for i in validated]
        return normalized, warnings
    except Exception as e:
        warnings.append(f"review_items_validation_failed: {str(e)[:200]}")
        normalized: list[dict] = []
        for raw in items:
            try:
                v = validate_review_items([raw])[0]
                normalized.append(v.model_dump(exclude_none=True))
            except Exception:
                continue
        if len(normalized) < len(items):
            warnings.append(f"review_items_filtered: {len(items) - len(normalized)}")
        return normalized, warnings

# XMind 输出目录
XMIND_OUTPUT_DIR = os.path.join(settings.BASE_DIR, 'apps', 'ai_testcase', 'output')
os.makedirs(XMIND_OUTPUT_DIR, exist_ok=True)

# 上传文件持久化目录
UPLOADS_DIR = os.path.join(settings.BASE_DIR, 'apps', 'ai_testcase', 'uploads')
os.makedirs(UPLOADS_DIR, exist_ok=True)

async def _authenticate_or_401(request):
    """
    本模块大量使用纯 Django async function views（SSE），不会自动走 DRF 的认证链路，
    这里显式复用全局 JWT 认证（MyJWTAuthentication）。
    """
    from backend.utils.auth import MyJWTAuthentication
    from asgiref.sync import sync_to_async

    auth = MyJWTAuthentication()
    try:
        auth_header = request.META.get('HTTP_AUTHORIZATION') or request.headers.get('Authorization')
        if auth_header:
            logger.info(f"[ai_testcase] auth.header_present | prefix={str(auth_header)[:20]}")

        # simplejwt 的 authenticate() 内部会同步访问 ORM 获取 user，
        # 在 async view 中会触发 SynchronousOnlyOperation。这里拆分认证步骤：
        # 1) 解析并校验 token（纯计算）
        # 2) 在线程中执行 get_user（ORM）
        raw = auth.get_raw_token(auth.get_header(request))
        # 兼容：支持从 URL query 中读取 token（如 ?token=xxx 或 ?access_token=xxx）
        if raw is None:
            q = request.GET.get('token') or request.GET.get('access_token')
            if q:
                token = q.strip()
                if not token.lower().startswith('bearer '):
                    token = f"Bearer {token}"
                request.META['HTTP_AUTHORIZATION'] = token
                logger.info(f"[ai_testcase] auth.query_token_used | prefix={token[:20]}")
                raw = auth.get_raw_token(auth.get_header(request))

        if raw is None:
            raise AuthenticationFailed('未登录或缺少 Authorization 头')

        validated_token = auth.get_validated_token(raw)
        user = await sync_to_async(auth.get_user)(validated_token)
        request.user = user
        return user, None
    except (AuthenticationFailed, InvalidToken) as e:
        logger.info(f"[ai_testcase] auth.failed | reason={str(e)[:200]}")
        return None, HttpResponse(str(e), status=401)
    except Exception:
        logger.exception("[ai_testcase] auth.failed_unexpected")
        return None, HttpResponse('认证失败', status=401)


def _authenticate_or_401_sync(request):
    """
    同步视图专用：全程同步 JWT + ORM，不经过 async_to_sync。

    ASGI（Daphne）下 DRF 同步视图会经 sync_to_async 在线程池执行；若此处再
    async_to_sync(async 认证)，会与嵌套的 async/sync 边界冲突，触发
    “You cannot call this from an async context”（SynchronousOnlyOperation）。
    逻辑与 _authenticate_or_401 一致，仅去掉 await/sync_to_async。
    """
    from backend.utils.auth import MyJWTAuthentication
    from rest_framework_simplejwt.exceptions import InvalidToken as JWTInvalidToken
    from rest_framework_simplejwt.exceptions import AuthenticationFailed as JWTAuthenticationFailed

    auth = MyJWTAuthentication()
    try:
        auth_header = request.META.get('HTTP_AUTHORIZATION') or request.headers.get('Authorization')
        if auth_header:
            logger.info(f"[ai_testcase] auth.header_present | prefix={str(auth_header)[:20]}")

        raw = auth.get_raw_token(auth.get_header(request))
        if raw is None:
            q = request.GET.get('token') or request.GET.get('access_token')
            if q:
                token = q.strip()
                if not token.lower().startswith('bearer '):
                    token = f"Bearer {token}"
                request.META['HTTP_AUTHORIZATION'] = token
                logger.info(f"[ai_testcase] auth.query_token_used | prefix={token[:20]}")
                raw = auth.get_raw_token(auth.get_header(request))

        if raw is None:
            raise JWTAuthenticationFailed('未登录或缺少 Authorization 头')

        validated_token = auth.get_validated_token(raw)
        user = auth.get_user(validated_token)
        request.user = user
        return user, None
    except (JWTAuthenticationFailed, JWTInvalidToken) as e:
        logger.info(f"[ai_testcase] auth.failed | reason={str(e)[:200]}")
        return None, HttpResponse(str(e), status=401)
    except Exception:
        logger.exception("[ai_testcase] auth.failed_unexpected")
        return None, HttpResponse('认证失败', status=401)


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


def _merge_function(result_json: dict, module_name: str, function_name: str, new_function_data: dict) -> dict:
    """
    将新生成的功能点数据替换到 result_json 的指定模块中。

    Args:
        result_json: DB 中已有的完整 JSON
        module_name: 所属模块名
        function_name: 要替换的功能点名
        new_function_data: AI 新生成的单功能点 JSON (含 name, cases)

    Returns:
        合并后的完整 JSON（新 dict，不修改原始数据）
    """
    merged = copy.deepcopy(result_json)
    for mod in merged["modules"]:
        if mod["name"] != module_name:
            continue
        for j, func in enumerate(mod["functions"]):
            if func["name"] == function_name:
                mod["functions"][j] = new_function_data
                return merged
        raise ValueError(f"功能 '{function_name}' 在模块 '{module_name}' 中不存在")
    raise ValueError(f"模块 '{module_name}' 不存在于当前用例中")


def _merge_case(
    result_json: dict,
    module_name: str,
    function_name: str,
    case_index: int,
    new_case_data: dict,
) -> dict:
    """
    将指定功能下的某条用例替换为编辑后的数据。

    Args:
        result_json: DB 中已有的完整 JSON
        module_name: 所属模块名
        function_name: 所属功能点名
        case_index: 用例在 functions[].cases 中的下标
        new_case_data: 单条用例 JSON (含 name, priority, precondition, steps, expected)

    Returns:
        合并后的完整 JSON（新 dict）
    """
    merged = copy.deepcopy(result_json)
    for mod in merged["modules"]:
        if mod["name"] != module_name:
            continue
        for func in mod["functions"]:
            if func["name"] != function_name:
                continue
            cases = func.get("cases") or []
            if case_index < 0 or case_index >= len(cases):
                raise ValueError(f"用例下标 {case_index} 越界（共 {len(cases)} 条）")
            cases[case_index] = {**cases[case_index], **new_case_data}
            return merged
        raise ValueError(f"功能 '{function_name}' 在模块 '{module_name}' 中不存在")
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
        # 确保 change 是字典类型
        if not isinstance(change, dict):
            logger.warning(f"[AI用例] 跳过非字典类型的变更指令: {change}")
            stats['skipped'] += 1
            continue
            
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


def _add_cors_headers(response, request=None):
    """
    给响应加上 CORS 头（SSE 直连时浏览器需要）。
    从 settings.AI_TESTCASE_CORS_ALLOW_ORIGINS 读取白名单；若为空则不放行跨域。
    """
    allow_origins = getattr(settings, 'AI_TESTCASE_CORS_ALLOW_ORIGINS', []) or []
    origin = None
    if request is not None:
        origin = request.META.get('HTTP_ORIGIN')

    # 若配置了白名单，则仅对白名单 Origin 放行；未配置则不放行跨域（同域不受影响）
    if origin and origin in allow_origins:
        response['Access-Control-Allow-Origin'] = origin
        response['Vary'] = 'Origin'
    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


def _throttle_or_429(request, scope: str = 'ai_testcase'):
    """
    对纯 Django function view 手动应用 DRF 的 ScopedRateThrottle。
    """
    from backend.utils.throttles import AiTestcaseScopedRateThrottle

    throttle = AiTestcaseScopedRateThrottle()
    throttle.scope = scope
    ok = throttle.allow_request(request, view=None)
    if ok:
        return None
    wait = throttle.wait()
    resp = HttpResponse('请求过于频繁，请稍后再试', status=429)
    if wait is not None:
        resp['Retry-After'] = str(int(wait))
    return resp


async def _throttle_or_429_async(request, scope: str = 'ai_testcase'):
    """
    在 async view 中调用限流：DRF ScopedRateThrottle 会同步访问 cache，必须经 sync_to_async。
    """
    from asgiref.sync import sync_to_async

    return await sync_to_async(_throttle_or_429)(request, scope=scope)


def _compute_idempotency_key(
    *,
    generation_mode: str,
    requirement: str,
    mode: str,
    use_thinking: bool,
    extracted_texts: list,
    images: list,
    prompt_version: str,
) -> str:
    """
    生成幂等键：同一用户相同输入在短时间重复提交时复用已有成功结果，避免重复消耗。
    注意：这里只做“输入特征”哈希，不包含用户信息（用户隔离在查询条件中完成）。
    """

    def _image_fingerprint(img: dict) -> dict:
        data = img.get('data') or ''
        return {
            'source': img.get('source'),
            'mime': img.get('mime'),
            'len': len(data),
            'head': data[:128],  # 控制大小
        }

    payload = {
        'generation_mode': generation_mode,
        'prompt_version': prompt_version,
        'mode': mode,
        'use_thinking': bool(use_thinking),
        'requirement': requirement or '',
        'texts': [
            {
                'source': t.get('source'),
                'len': len(t.get('content') or ''),
                'head': (t.get('content') or '')[:256],
            }
            for t in (extracted_texts or [])
        ],
        'images': [_image_fingerprint(i) for i in (images or [])],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


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
        return _add_cors_headers(resp, request)

    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405), request)

    user, auth_resp = await _authenticate_or_401(request)
    if auth_resp:
        return _add_cors_headers(auth_resp, request)

    throttle_resp = await _throttle_or_429_async(request, scope='ai_testcase')
    if throttle_resp:
        return _add_cors_headers(throttle_resp, request)

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
                return _add_cors_headers(HttpResponse(str(e), status=400), request)
            except Exception as e:
                logger.exception(f"[AI用例] 文件处理异常: {e}")
                return _add_cors_headers(HttpResponse(f'文件处理失败: {str(e)}', status=400), request)
    else:
        # JSON 模式（纯文本，兼容原有接口）
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return _add_cors_headers(HttpResponse('Invalid JSON', status=400), request)

        requirement = body.get('requirement', '').strip()
        use_thinking = body.get('use_thinking', False)
        mode = body.get('mode', 'comprehensive')  # 新增模式参数

    mode = normalize_case_strategy_mode(mode)

    # 校验：至少要有文字输入或上传文件
    if not requirement and not extracted_texts and not images:
        return _add_cors_headers(HttpResponse('请输入需求描述或上传文件', status=400), request)

    # 用于 DB 记录的需求摘要
    requirement_summary = requirement
    if not requirement_summary and extracted_texts:
        requirement_summary = f"[附件] {', '.join(t['source'] for t in extracted_texts[:3])}"
    if images and not requirement_summary:
        requirement_summary = f"[图片] {', '.join(img['source'] for img in images[:3])}"

    has_attachments = bool(extracted_texts or images)

    prompt_version = getattr(settings, 'AI_TESTCASE_PROMPT_VERSION', 'v1')
    idempotency_key = _compute_idempotency_key(
        generation_mode='direct',
        requirement=requirement or requirement_summary,
        mode=mode,
        use_thinking=use_thinking,
        extracted_texts=extracted_texts,
        images=images,
        prompt_version=prompt_version,
    )

    async def event_stream():
        from asgiref.sync import sync_to_async
        reuse_window_s = int(getattr(settings, 'AI_TESTCASE_IDEMPOTENCY_REUSE_WINDOW_SECONDS', 60) or 0)
        reuse_after = timezone.now() - timedelta(seconds=reuse_window_s) if reuse_window_s > 0 else None

        def _find_existing():
            qs = AiTestcaseGeneration.objects.filter(
                created_by=user,
                generation_mode='direct',
                idempotency_key=idempotency_key,
                status='success',
            )
            if reuse_after is not None:
                qs = qs.filter(created_at__gte=reuse_after)
            return qs.order_by('-created_at').first()

        existing = await sync_to_async(_find_existing)()

        if existing and existing.result_json:
            _log_event(
                "generate.reuse",
                record_id=existing.id,
                user_id=getattr(user, "id", None),
                prompt_version=existing.prompt_version,
            )
            yield f"data: {json.dumps({'type': 'done', 'reused': True, 'record_id': existing.id, 'title': (existing.result_json or {}).get('title', ''), 'module_count': existing.module_count, 'case_count': existing.case_count, 'usage': {'prompt_tokens': existing.prompt_tokens, 'completion_tokens': existing.completion_tokens, 'total_tokens': existing.total_tokens}, 'data': existing.result_json}, ensure_ascii=False)}\n\n"
            return

        record = await sync_to_async(AiTestcaseGeneration.objects.create)(
            requirement=requirement_summary,
            created_by=user,
            use_thinking=use_thinking,
            status='generating',
            generation_mode='direct',
            idempotency_key=idempotency_key,
            prompt_version=prompt_version,
            case_strategy_mode=mode,
        )
        _log_event(
            "generate.start",
            record_id=record.id,
            user_id=getattr(user, "id", None),
            prompt_version=prompt_version,
            idempotency_key=idempotency_key,
            mode=mode,
            has_attachments=has_attachments,
        )

        # 持久化上传文件（供后续模块重新生成使用）
        if uploaded_files:
            saved_paths = await sync_to_async(_save_uploaded_files)(uploaded_files, record.id)
            record.source_files = saved_paths
            await sync_to_async(record.save)(update_fields=['source_files'])

        start_data = {'type': 'start', 'record_id': record.id, 'prompt_version': prompt_version}
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
                # 支持取消：用户触发 cancel 后停止生成（不再继续消耗）
                await sync_to_async(record.refresh_from_db)(fields=['status'])
                if record.status == 'cancelled':
                    yield f"data: {json.dumps({'type': 'cancelled', 'record_id': record.id}, ensure_ascii=False)}\n\n"
                    return

                if event['type'] == 'chunk':
                    yield f"data: {json.dumps({'type': 'chunk', 'content': event['content']}, ensure_ascii=False)}\n\n"

                elif event['type'] == 'done':
                    full_content = event['content']
                    usage = event['usage']

                    # 解析 JSON
                    data = KimiClient._parse_json(full_content)

                    if data is None:
                        record.status = 'failed'
                        record.error_message = 'parse_error: AI 返回的内容无法解析为 JSON'
                        record.raw_content = full_content
                        await sync_to_async(record.save)()
                        _log_event("generate.error", record_id=record.id, user_id=getattr(user, "id", None), error_type="parse")
                        yield f"data: {json.dumps({'type': 'error', 'error_type': 'parse', 'error': 'AI 返回的内容无法解析为 JSON', 'record_id': record.id}, ensure_ascii=False)}\n\n"
                        return

                    try:
                        validate_testcase_result(data)
                    except Exception as ve:
                        record.status = 'failed'
                        record.error_message = f'validation_error: {str(ve)[:500]}'
                        record.raw_content = full_content
                        await sync_to_async(record.save)()
                        _log_event("generate.error", record_id=record.id, user_id=getattr(user, "id", None), error_type="validation")
                        yield f"data: {json.dumps({'type': 'error', 'error_type': 'validation', 'error': 'AI 返回 JSON 结构不符合约定', 'validation_error': str(ve), 'record_id': record.id}, ensure_ascii=False)}\n\n"
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

                    _log_event(
                        "generate.done",
                        record_id=record.id,
                        user_id=getattr(user, "id", None),
                        prompt_version=prompt_version,
                        module_count=record.module_count,
                        case_count=record.case_count,
                        total_tokens=record.total_tokens,
                    )
                    yield f"data: {json.dumps({'type': 'done', 'record_id': record.id, 'title': title, 'module_count': record.module_count, 'case_count': record.case_count, 'usage': usage, 'data': data}, ensure_ascii=False)}\n\n"

                elif event['type'] == 'error':
                    record.status = 'failed'
                    record.error_message = f"llm_error: {event['error']}"
                    await sync_to_async(record.save)()
                    _log_event("generate.error", record_id=record.id, user_id=getattr(user, "id", None), error_type="llm")
                    yield f"data: {json.dumps({'type': 'error', 'error_type': 'llm', 'error': event['error'], 'record_id': record.id}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception(f"[AI用例] 流式生成异常: {e}")
            record.status = 'failed'
            record.error_message = f"server_error: {str(e)}"
            await sync_to_async(record.save)()
            yield f"data: {json.dumps({'type': 'error', 'error_type': 'server', 'error': str(e), 'record_id': record.id}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    # 防止 GZipMiddleware 压缩 SSE 流（压缩会导致缓冲）
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response, request)

# Django 4.2 兼容：直接设置属性而非使用 @csrf_exempt 装饰器
generate_stream_view.csrf_exempt = True


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
        return _add_cors_headers(resp, request)

    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405), request)

    user, auth_resp = await _authenticate_or_401(request)
    if auth_resp:
        return _add_cors_headers(auth_resp, request)

    throttle_resp = await _throttle_or_429_async(request, scope='ai_testcase')
    if throttle_resp:
        return _add_cors_headers(throttle_resp, request)

    # ---------- 解析请求参数 ----------
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400), request)

    record_id = body.get('record_id')
    module_name = body.get('module_name', '').strip()
    module_requirement = body.get('module_requirement', '').strip()
    adjustment = body.get('adjustment', '').strip()
    use_thinking = body.get('use_thinking', False)

    # ---------- 参数校验 ----------
    if not record_id:
        return _add_cors_headers(HttpResponse('缺少 record_id', status=400), request)
    if not module_name:
        return _add_cors_headers(HttpResponse('缺少 module_name', status=400), request)
    if not module_requirement and not adjustment:
        return _add_cors_headers(HttpResponse('请至少填写「补充需求」或「调整意见」中的一项', status=400), request)

    # ---------- 查询记录 ----------
    from asgiref.sync import sync_to_async

    try:
        record = await sync_to_async(AiTestcaseGeneration.objects.get)(id=record_id, created_by=user)
    except AiTestcaseGeneration.DoesNotExist:
        return _add_cors_headers(HttpResponse(f'记录不存在: id={record_id}', status=404), request)

    _log_event(
        "regenerate_module.start",
        record_id=record_id,
        user_id=getattr(user, "id", None),
        module_name=module_name,
    )

    if record.status != 'success':
        return _add_cors_headers(HttpResponse(
            f'该记录状态为 {record.status}，只有 success 状态的记录才能进行模块重新生成', status=400
        ), request)

    if not record.result_json:
        return _add_cors_headers(HttpResponse('该记录没有用例数据', status=400), request)

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
        ), request)

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
    return _add_cors_headers(response, request)


async def regenerate_function_stream_view(request):
    """
    SSE 流式功能点级重新生成测试用例

    POST /api/ai_testcase/regenerate-function-stream/
    {
        "record_id": 1,
        "module_name": "落地页优化",
        "function_name": "落地页视觉重设计",
        "function_requirement": "",
        "adjustment": "补充更多边界值用例",
        "use_thinking": false
    }
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200), request)
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405), request)

    user, auth_resp = await _authenticate_or_401(request)
    if auth_resp:
        return _add_cors_headers(auth_resp, request)

    throttle_resp = await _throttle_or_429_async(request, scope='ai_testcase')
    if throttle_resp:
        return _add_cors_headers(throttle_resp, request)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400), request)

    record_id = body.get('record_id')
    module_name = (body.get('module_name') or '').strip()
    function_name = (body.get('function_name') or '').strip()
    function_requirement = (body.get('function_requirement') or '').strip()
    adjustment = (body.get('adjustment') or '').strip()
    use_thinking = body.get('use_thinking', False)

    if not record_id:
        return _add_cors_headers(HttpResponse('缺少 record_id', status=400), request)
    if not module_name:
        return _add_cors_headers(HttpResponse('缺少 module_name', status=400), request)
    if not function_name:
        return _add_cors_headers(HttpResponse('缺少 function_name', status=400), request)
    if not function_requirement and not adjustment:
        return _add_cors_headers(HttpResponse('请至少填写「补充需求」或「调整意见」中的一项', status=400), request)

    from asgiref.sync import sync_to_async

    try:
        record = await sync_to_async(AiTestcaseGeneration.objects.get)(id=record_id, created_by=user)
    except AiTestcaseGeneration.DoesNotExist:
        return _add_cors_headers(HttpResponse(f'记录不存在: id={record_id}', status=404), request)

    _log_event(
        "regenerate_function.start",
        record_id=record_id,
        user_id=getattr(user, "id", None),
        module_name=module_name,
        function_name=function_name,
    )

    if record.status != 'success':
        return _add_cors_headers(HttpResponse(
            f'该记录状态为 {record.status}，只有 success 状态的记录才能进行功能点重新生成', status=400
        ), request)
    if not record.result_json:
        return _add_cors_headers(HttpResponse('该记录没有用例数据', status=400), request)

    existing_modules = record.result_json.get('modules', [])
    mod = next((m for m in existing_modules if m.get('name') == module_name), None)
    if not mod:
        return _add_cors_headers(HttpResponse(
            json.dumps({'error': f"模块 '{module_name}' 不存在", 'available_modules': [m['name'] for m in existing_modules]},
                      ensure_ascii=False), status=400, content_type='application/json'
        ), request)
    existing_function = next((f for f in mod.get('functions', []) if f.get('name') == function_name), None)
    if not existing_function:
        return _add_cors_headers(HttpResponse(
            json.dumps({'error': f"功能 '{function_name}' 在模块 '{module_name}' 中不存在"},
                      ensure_ascii=False), status=400, content_type='application/json'
        ), request)

    async def event_stream():
        record.status = 'generating'
        await sync_to_async(record.save)(update_fields=['status'])

        yield f"data: {json.dumps({'type': 'start', 'record_id': record.id, 'module_name': module_name, 'function_name': function_name}, ensure_ascii=False)}\n\n"

        try:
            client = KimiClient()
            gen = client.regenerate_function_stream_async(
                module_name=module_name,
                function_name=function_name,
                existing_function_json=existing_function,
                function_requirement=function_requirement,
                adjustment=adjustment,
                requirement=record.requirement or '',
                use_thinking=use_thinking,
            )
            async for event in gen:
                if event['type'] == 'chunk':
                    yield f"data: {json.dumps({'type': 'chunk', 'content': event['content']}, ensure_ascii=False)}\n\n"
                elif event['type'] == 'done':
                    full_content = event['content']
                    usage = event['usage']
                    function_data = KimiClient._parse_json(full_content)
                    if function_data is None:
                        record.status = 'success'
                        await sync_to_async(record.save)(update_fields=['status'])
                        yield f"data: {json.dumps({'type': 'error', 'error': 'AI 返回的内容无法解析为 JSON', 'record_id': record.id}, ensure_ascii=False)}\n\n"
                        return
                    if 'cases' not in function_data:
                        record.status = 'success'
                        await sync_to_async(record.save)(update_fields=['status'])
                        yield f"data: {json.dumps({'type': 'error', 'error': 'AI 返回的 JSON 缺少 cases 字段', 'record_id': record.id}, ensure_ascii=False)}\n\n"
                        return
                    function_data['name'] = function_name
                    try:
                        merged_json = _merge_function(record.result_json, module_name, function_name, function_data)
                    except ValueError as e:
                        record.status = 'success'
                        await sync_to_async(record.save)(update_fields=['status'])
                        yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'record_id': record.id}, ensure_ascii=False)}\n\n"
                        return
                    record.result_json = merged_json
                    record.count_stats()
                    record.prompt_tokens += usage.get('prompt_tokens', 0)
                    record.completion_tokens += usage.get('completion_tokens', 0)
                    record.total_tokens += usage.get('total_tokens', 0)
                    title = merged_json.get('title', f'testcase_{record.id}')
                    xmind_path = os.path.join(XMIND_OUTPUT_DIR, f"{title}.xmind")
                    await sync_to_async(XMindBuilder.build_and_save)(merged_json, xmind_path)
                    record.xmind_file = xmind_path
                    record.status = 'success'
                    await sync_to_async(record.save)()
                    yield f"data: {json.dumps({'type': 'done', 'record_id': record.id, 'module_name': module_name, 'function_name': function_name, 'module_count': record.module_count, 'case_count': record.case_count, 'usage': usage, 'data': merged_json}, ensure_ascii=False)}\n\n"
                elif event['type'] == 'error':
                    record.status = 'success'
                    await sync_to_async(record.save)(update_fields=['status'])
                    yield f"data: {json.dumps({'type': 'error', 'error': event['error'], 'record_id': record.id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("[AI用例] 功能点重新生成异常: %s", e)
            record.status = 'success'
            await sync_to_async(record.save)(update_fields=['status'])
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'record_id': record.id}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response, request)


def update_case_view(request):
    """
    编辑单条用例（标题、前置条件、测试步骤、预期结果等），写回 result_json 并重建 XMind。

    POST /api/ai_testcase/update-case/
    Body: {
        "record_id": 1,
        "module_name": "模块名",
        "function_name": "功能点名",
        "case_index": 0,
        "name": "用例标题",
        "priority": "P0",
        "precondition": "前置条件",
        "steps": "测试步骤",
        "expected": "预期结果"
    }
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200), request)
    if request.method != 'POST':
        return _add_cors_headers(
            Response({'error': '仅支持 POST'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        )
    user, auth_resp = _authenticate_or_401_sync(request)
    if auth_resp:
        return _add_cors_headers(auth_resp, request)
    throttle_resp = _throttle_or_429(request, scope='ai_testcase')
    if throttle_resp:
        return _add_cors_headers(throttle_resp, request)
    try:
        body = json.loads(request.body) if request.body else {}
        ser = UpdateCaseRequestSerializer(data=body)
        if not ser.is_valid():
            return _add_cors_headers(Response(ser.errors, status=status.HTTP_400_BAD_REQUEST), request)
        data = ser.validated_data
        record_id = data['record_id']
        module_name = data['module_name']
        function_name = data['function_name']
        case_index = data['case_index']
        new_case = {
            'name': data['name'],
            'priority': data.get('priority') or 'P1',
            'precondition': data.get('precondition') or '',
            'steps': data.get('steps') or '',
            'expected': data.get('expected') or '',
        }
        record = AiTestcaseGeneration.objects.get(id=record_id, created_by=user)
        if not record.result_json or not record.result_json.get('modules'):
            return _add_cors_headers(Response(
                {'error': '该记录无有效用例数据'},
                status=status.HTTP_400_BAD_REQUEST
            ), request)
        merged_json = _merge_case(
            record.result_json,
            module_name,
            function_name,
            case_index,
            new_case,
        )
        record.result_json = merged_json
        record.count_stats()
        title = merged_json.get('title', f'testcase_{record.id}')
        xmind_path = os.path.join(XMIND_OUTPUT_DIR, f'{title}.xmind')
        XMindBuilder.build_and_save(merged_json, xmind_path)
        record.xmind_file = xmind_path
        record.save(update_fields=['result_json', 'module_count', 'case_count', 'xmind_file'])
        _log_event(
            "update_case.done",
            record_id=record.id,
            user_id=getattr(user, "id", None),
            module_name=module_name,
            function_name=function_name,
        )
        return _add_cors_headers(Response({
            'data': merged_json,
            'module_count': record.module_count,
            'case_count': record.case_count,
        }, status=status.HTTP_200_OK), request)
    except AiTestcaseGeneration.DoesNotExist:
        return _add_cors_headers(Response({'error': '记录不存在'}, status=status.HTTP_404_NOT_FOUND), request)
    except ValueError as e:
        return _add_cors_headers(Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST), request)
    except Exception as e:
        logger.exception("[AI用例] 更新用例异常: %s", e)
        return _add_cors_headers(Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), request)


update_case_view.csrf_exempt = True


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
        return _add_cors_headers(HttpResponse(status=200), request)
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405), request)

    user, auth_resp = await _authenticate_or_401(request)
    if auth_resp:
        return _add_cors_headers(auth_resp, request)
    throttle_resp = await _throttle_or_429_async(request, scope='ai_testcase')
    if throttle_resp:
        return _add_cors_headers(throttle_resp, request)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400), request)

    record_id = body.get('record_id')

    if not record_id:
        return _add_cors_headers(HttpResponse('缺少 record_id', status=400), request)

    from asgiref.sync import sync_to_async

    try:
        record = await sync_to_async(AiTestcaseGeneration.objects.get)(id=record_id, created_by=user)
    except AiTestcaseGeneration.DoesNotExist:
        return _add_cors_headers(HttpResponse(f'记录不存在: id={record_id}', status=404), request)

    if record.status != 'success' or not record.result_json:
        return _add_cors_headers(HttpResponse('该记录没有可评审的用例数据', status=400), request)

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
                            try:
                                validated = validate_review_items(dim_data['items'])
                                for item in validated:
                                    d = item.model_dump(exclude_none=True)
                                    d['dimension_key'] = dim_key
                                    d['id'] = global_id
                                    global_id += 1
                                    dim_items.append(d)
                                all_items.extend(dim_items)
                            except Exception as ve:
                                warning_text = f'{dim_label}维度评审返回结构不合法，已忽略该维度结果: {str(ve)[:200]}'
                                dim_done_data = {
                                    'type': 'dimension_done',
                                    'dimension_key': dim_key,
                                    'dimension_label': dim_label,
                                    'items_count': 0,
                                    'items': [],
                                    'warning': warning_text,
                                }
                                yield f"data: {json.dumps(dim_done_data, ensure_ascii=False)}\n\n"
                                continue

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

            # 最终输出前做一次 schema 规范化/清洗，确保前端消费稳定
            normalized_items, normalize_warnings = _normalize_review_items(all_items)

            # 重新编号
            for i, item in enumerate(normalized_items, 1):
                item['id'] = i

            review_data = {
                "summary": f"共扫描 {total} 个维度，发现 {len(all_items)} 个问题",
                "total_issues": len(normalized_items),
                "items": normalized_items,
            }
            if normalize_warnings:
                review_data["warnings"] = normalize_warnings

            yield f"data: {json.dumps({'type': 'done', 'record_id': record.id, 'data': review_data, 'usage': total_usage}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception(f"[AI用例] 分维度评审异常: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response, request)

review_stream_view.csrf_exempt = True


async def apply_review_stream_view(request):
    """
    SSE 流式采纳评审意见

    POST /api/ai_testcase/apply-review-stream/
    {"record_id": 1, "selected_items": [...], "use_thinking": false}
    """
    if request.method == 'OPTIONS':
        return _add_cors_headers(HttpResponse(status=200), request)
    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405), request)

    user, auth_resp = await _authenticate_or_401(request)
    if auth_resp:
        return _add_cors_headers(auth_resp, request)
    throttle_resp = await _throttle_or_429_async(request, scope='ai_testcase')
    if throttle_resp:
        return _add_cors_headers(throttle_resp, request)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(HttpResponse('Invalid JSON', status=400), request)

    record_id = body.get('record_id')
    selected_items = body.get('selected_items', [])
    use_thinking = body.get('use_thinking', False)

    if not record_id:
        return _add_cors_headers(HttpResponse('缺少 record_id', status=400), request)
    if not selected_items:
        return _add_cors_headers(HttpResponse('未选择任何评审项', status=400), request)

    from asgiref.sync import sync_to_async

    try:
        record = await sync_to_async(AiTestcaseGeneration.objects.get)(id=record_id, created_by=user)
    except AiTestcaseGeneration.DoesNotExist:
        return _add_cors_headers(HttpResponse(f'记录不存在: id={record_id}', status=404), request)

    _log_event(
        "apply_review.start",
        record_id=record_id,
        user_id=getattr(user, "id", None),
        selected_count=len(selected_items),
    )

    if record.status != 'success' or not record.result_json:
        return _add_cors_headers(HttpResponse('该记录没有可修改的用例数据', status=400), request)

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
                        yield f"data: {json.dumps({'type': 'error', 'error_type': 'parse', 'error': 'AI 返回内容无法解析为 JSON，原用例数据不受影响'}, ensure_ascii=False)}\n\n"
                        return

                    # 处理 AI 返回的数据格式：可能是 {"changes": [...]} 或直接是 [...]
                    if isinstance(change_data, list):
                        changes = change_data
                    elif isinstance(change_data, dict):
                        changes = change_data.get('changes', [])
                    else:
                        changes = []
                    
                    if not changes:
                        record.status = 'success'
                        await sync_to_async(record.save)(update_fields=['status'])
                        yield f"data: {json.dumps({'type': 'error', 'error_type': 'validation', 'error': 'AI 未返回任何变更指令，原用例数据不受影响'}, ensure_ascii=False)}\n\n"
                        return

                    try:
                        validate_changes(changes)
                    except Exception as ve:
                        record.status = 'success'
                        await sync_to_async(record.save)(update_fields=['status'])
                        yield f"data: {json.dumps({'type': 'error', 'error_type': 'validation', 'error': 'AI 返回变更指令结构不符合约定，原用例数据不受影响', 'validation_error': str(ve)}, ensure_ascii=False)}\n\n"
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

                    _log_event(
                        "apply_review.done",
                        record_id=record.id,
                        user_id=getattr(user, "id", None),
                        module_count=record.module_count,
                        case_count=record.case_count,
                    )
                    yield f"data: {json.dumps({'type': 'done', 'record_id': record.id, 'module_count': record.module_count, 'case_count': record.case_count, 'usage': usage, 'data': new_data, 'apply_summary': apply_summary}, ensure_ascii=False)}\n\n"

                elif event['type'] == 'error':
                    record.status = 'success'
                    await sync_to_async(record.save)(update_fields=['status'])
                    yield f"data: {json.dumps({'type': 'error', 'error_type': 'llm', 'error': event['error']}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception(f"[AI用例] 采纳评审意见异常: {e}")
            record.status = 'success'
            await sync_to_async(record.save)(update_fields=['status'])
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response, request)

apply_review_stream_view.csrf_exempt = True


async def generation_events_stream_view(request, record_id: int):
    """
    P2：从事件表 SSE 推送（支持断线重连 after 游标）。

    GET /api/ai_testcase/generations/{id}/events-stream/?after=<event_id>
    """
    from asgiref.sync import sync_to_async

    if request.method == 'OPTIONS':
        resp = HttpResponse(status=200)
        return _add_cors_headers(resp, request)

    if request.method != 'GET':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405), request)

    user, auth_resp = await _authenticate_or_401(request)
    if auth_resp:
        return _add_cors_headers(auth_resp, request)

    throttle_resp = await _throttle_or_429_async(request, scope='ai_testcase')
    if throttle_resp:
        return _add_cors_headers(throttle_resp, request)

    try:
        after = int((request.GET.get('after') or '0').strip() or 0)
    except Exception:
        after = 0

    def _get_record():
        return AiTestcaseGeneration.objects.get(id=record_id, created_by=user)

    try:
        record = await sync_to_async(_get_record)()
    except AiTestcaseGeneration.DoesNotExist:
        return _add_cors_headers(HttpResponse('Not found', status=404), request)

    terminal_statuses = {'success', 'failed', 'cancelled'}

    async def event_stream():
        last_keepalive = timezone.now()
        last_sent_id = after
        idle_polls_after_terminal = 0

        # A 方案：订阅实时 chunk（不落库）
        pubsub = None
        try:
            import redis
            r = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', '127.0.0.1'),
                port=int(getattr(settings, 'REDIS_PORT', 6379)),
                db=int(getattr(settings, 'REDIS_DB', 0)),
                password=getattr(settings, 'REDIS_PASSWORD', None) or None,
                decode_responses=True,
            )
            pubsub = r.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(f"ai_testcase:chunks:{record.id}")
        except Exception:
            pubsub = None

        yield f"data: {json.dumps({'type': 'hello', 'record_id': record.id, 'after': after}, ensure_ascii=False)}\n\n"

        try:
            while True:
                # 先转发实时 chunk（不保证断线重放）
                if pubsub is not None:
                    try:
                        # 高频 drain：一次循环尽量多取几条，避免 1s 才吐一段导致“很慢”的体感
                        for _ in range(50):
                            msg = await sync_to_async(pubsub.get_message)()
                            if not msg or msg.get('type') != 'message':
                                break
                            chunk_text = msg.get('data') or ''
                            if chunk_text:
                                yield f"data: {json.dumps({'type': 'chunk', 'record_id': record.id, 'content': chunk_text}, ensure_ascii=False)}\n\n"
                    except Exception:
                        pass

                def _fetch_events():
                    return list(
                        AiTestcaseEvent.objects.filter(generation_id=record.id, id__gt=last_sent_id)
                        .order_by('id')[:200]
                    )

                events = await sync_to_async(_fetch_events)()
                if events:
                    idle_polls_after_terminal = 0
                    for ev in events:
                        last_sent_id = ev.id
                        payload = {
                            'type': ev.event_type,
                            'event_id': ev.id,
                            'record_id': record.id,
                            'created_at': ev.created_at.isoformat(),
                            'payload': ev.payload,
                        }
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                await sync_to_async(record.refresh_from_db)(fields=['status'])
                if record.status in terminal_statuses and not events:
                    idle_polls_after_terminal += 1
                    if idle_polls_after_terminal >= 2:
                        yield f"data: {json.dumps({'type': 'eof', 'record_id': record.id, 'status': record.status, 'last_event_id': last_sent_id}, ensure_ascii=False)}\n\n"
                        return

                now = timezone.now()
                if (now - last_keepalive).total_seconds() >= 10:
                    last_keepalive = now
                    yield f"data: {json.dumps({'type': 'keepalive', 'record_id': record.id, 'last_event_id': last_sent_id}, ensure_ascii=False)}\n\n"

                # 更快的 tick：提升 chunk 实时性；DB 事件仍按批拉取，成本可控
                await asyncio.sleep(0.1)
        finally:
            if pubsub is not None:
                try:
                    pubsub.close()
                except Exception:
                    pass

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response, request)

generation_events_stream_view.csrf_exempt = True


class AiTestcaseViewSet(viewsets.ModelViewSet):
    """AI 用例生成 ViewSet"""
    queryset = AiTestcaseGeneration.objects.all()
    serializer_class = AiTestcaseGenerationSerializer
    throttle_scope = 'ai_testcase'

    def get_queryset(self):
        qs = super().get_queryset().select_related('created_by')
        user = getattr(self.request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return qs.none()
        if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
            cid = self.request.query_params.get('created_by')
            if cid not in (None, ''):
                try:
                    qs = qs.filter(created_by_id=int(cid))
                except (ValueError, TypeError):
                    pass
            return qs
        return qs.filter(created_by=user)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """
        取消生成任务（对 SSE/Agent 长任务生效）

        POST /api/ai_testcase/generations/{id}/cancel/
        """
        record = self.get_object()
        if record.status != 'generating':
            return Response({'error': f'当前状态为 {record.status}，无法取消'}, status=status.HTTP_400_BAD_REQUEST)
        record.mark_cancelled()
        record.save(update_fields=['status', 'cancelled_at'])
        _log_event(
            "cancel.done",
            record_id=record.id,
            user_id=getattr(request.user, "id", None),
        )
        return Response({'id': record.id, 'status': record.status, 'cancelled_at': record.cancelled_at}, status=status.HTTP_200_OK)

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
        prompt_version = getattr(settings, 'AI_TESTCASE_PROMPT_VERSION', 'v1')
        idempotency_key = _compute_idempotency_key(
            generation_mode='direct',
            requirement=requirement,
            mode=mode,
            use_thinking=use_thinking,
            extracted_texts=[],
            images=[],
            prompt_version=prompt_version,
        )

        reuse_window_s = int(getattr(settings, 'AI_TESTCASE_IDEMPOTENCY_REUSE_WINDOW_SECONDS', 60) or 0)
        reuse_after = timezone.now() - timedelta(seconds=reuse_window_s) if reuse_window_s > 0 else None
        existing_qs = AiTestcaseGeneration.objects.filter(
            created_by=request.user,
            generation_mode='direct',
            idempotency_key=idempotency_key,
            status='success',
        )
        if reuse_after is not None:
            existing_qs = existing_qs.filter(created_at__gte=reuse_after)
        existing = existing_qs.order_by('-created_at').first()
        if existing and existing.result_json:
            return Response({
                'id': existing.id,
                'status': 'success',
                'reused': True,
                'title': existing.result_json.get('title', ''),
                'module_count': existing.module_count,
                'case_count': existing.case_count,
                'usage': {
                    'prompt_tokens': existing.prompt_tokens,
                    'completion_tokens': existing.completion_tokens,
                    'total_tokens': existing.total_tokens,
                },
                'data': existing.result_json,
            }, status=status.HTTP_200_OK)

        # 创建记录
        record = AiTestcaseGeneration.objects.create(
            requirement=requirement,
            created_by=request.user,
            use_thinking=use_thinking,
            status='generating',
            generation_mode='direct',
            idempotency_key=idempotency_key,
            prompt_version=prompt_version,
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

    @action(detail=False, methods=['post'], url_path='start')
    def start(self, request):
        """
        P2：启动 direct 任务（同步返回 record_id，后台 Celery 执行）。

        POST /api/ai_testcase/generations/start/
        支持 JSON 或 multipart/form-data（可带 files）
        """
        user, auth_resp = _authenticate_or_401_sync(request)
        if auth_resp:
            return Response({'detail': auth_resp.content.decode('utf-8', errors='ignore')}, status=401)

        throttle_resp = _throttle_or_429(request, scope='ai_testcase')
        if throttle_resp:
            return Response({'detail': throttle_resp.content.decode('utf-8', errors='ignore')}, status=429)

        extracted_texts = []
        images = []
        uploaded_files = []
        requirement = ''
        use_thinking = False
        mode = 'comprehensive'

        content_type = request.content_type or ''
        if 'multipart' in content_type:
            requirement = (request.POST.get('requirement', '') or '').strip()
            use_thinking = (request.POST.get('use_thinking', 'false') or '').lower() in ('true', '1', 'yes')
            mode = (request.POST.get('mode', 'comprehensive') or 'comprehensive').strip()
            uploaded_files = request.FILES.getlist('files')
            if uploaded_files:
                try:
                    processor = FileProcessor()
                    file_result = processor.process_files(uploaded_files)
                    extracted_texts = file_result.get('texts', [])
                    images = file_result.get('images', [])
                except Exception as e:
                    return Response({'detail': f'文件处理失败: {str(e)}'}, status=400)
        else:
            serializer = GenerateRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            requirement = serializer.validated_data['requirement']
            use_thinking = serializer.validated_data.get('use_thinking', False)
            mode = serializer.validated_data.get('mode', 'comprehensive')

        mode = normalize_case_strategy_mode(mode)

        prompt_version = getattr(settings, 'AI_TESTCASE_PROMPT_VERSION', 'v1')
        idempotency_key = _compute_idempotency_key(
            generation_mode='direct',
            requirement=requirement,
            mode=mode,
            use_thinking=use_thinking,
            extracted_texts=extracted_texts,
            images=images,
            prompt_version=prompt_version,
        )

        reuse_window_s = int(getattr(settings, 'AI_TESTCASE_IDEMPOTENCY_REUSE_WINDOW_SECONDS', 60) or 0)
        reuse_after = timezone.now() - timedelta(seconds=reuse_window_s) if reuse_window_s > 0 else None
        existing_qs = AiTestcaseGeneration.objects.filter(
            created_by=user,
            generation_mode='direct',
            idempotency_key=idempotency_key,
            status='success',
        )
        if reuse_after is not None:
            existing_qs = existing_qs.filter(created_at__gte=reuse_after)
        existing = existing_qs.order_by('-created_at').first()
        if existing:
            return Response({'record_id': existing.id, 'reused': True, 'status': existing.status}, status=status.HTTP_200_OK)

        record = AiTestcaseGeneration.objects.create(
            created_by=user,
            requirement=requirement,
            use_thinking=use_thinking,
            generation_mode='direct',
            status='generating',
            idempotency_key=idempotency_key,
            prompt_version=prompt_version,
            case_strategy_mode=mode,
        )

        if uploaded_files:
            try:
                saved_paths = _save_uploaded_files(uploaded_files, record.id)
                record.source_files = saved_paths
                record.save(update_fields=['source_files'])
            except Exception as e:
                record.status = 'failed'
                record.error_message = f'file_save_error: {str(e)}'
                record.save(update_fields=['status', 'error_message'])
                return Response({'detail': f'文件保存失败: {str(e)}'}, status=500)

        from apps.ai_testcase.tasks import run_ai_testcase_direct
        run_ai_testcase_direct.delay(record.id)
        return Response({'record_id': record.id, 'reused': False, 'status': record.status}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='agent-start')
    def agent_start(self, request):
        """
        P2：启动 agent 任务（同步返回 record_id，后台 Celery 执行）。

        POST /api/ai_testcase/generations/agent-start/
        支持 JSON 或 multipart/form-data（可带 files）
        """
        user, auth_resp = _authenticate_or_401_sync(request)
        if auth_resp:
            return Response({'detail': auth_resp.content.decode('utf-8', errors='ignore')}, status=401)

        throttle_resp = _throttle_or_429(request, scope='ai_testcase')
        if throttle_resp:
            return Response({'detail': throttle_resp.content.decode('utf-8', errors='ignore')}, status=429)

        extracted_texts = []
        images = []
        uploaded_files = []
        requirement = ''
        use_thinking = False
        mode = 'comprehensive'

        content_type = request.content_type or ''
        if 'multipart' in content_type:
            requirement = (request.POST.get('requirement', '') or '').strip()
            use_thinking = (request.POST.get('use_thinking', 'false') or '').lower() in ('true', '1', 'yes')
            mode = (request.POST.get('mode', 'comprehensive') or 'comprehensive').strip()
            uploaded_files = request.FILES.getlist('files')
            if uploaded_files:
                try:
                    processor = FileProcessor()
                    file_result = processor.process_files(uploaded_files)
                    extracted_texts = file_result.get('texts', [])
                    images = file_result.get('images', [])
                except Exception as e:
                    return Response({'detail': f'文件处理失败: {str(e)}'}, status=400)
        else:
            serializer = GenerateRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            requirement = serializer.validated_data['requirement']
            use_thinking = serializer.validated_data.get('use_thinking', False)
            mode = serializer.validated_data.get('mode', 'comprehensive')

        mode = normalize_case_strategy_mode(mode)

        prompt_version = getattr(settings, 'AI_TESTCASE_PROMPT_VERSION', 'v1')
        idempotency_key = _compute_idempotency_key(
            generation_mode='agent',
            requirement=requirement,
            mode=mode,
            use_thinking=use_thinking,
            extracted_texts=extracted_texts,
            images=images,
            prompt_version=prompt_version,
        )

        reuse_window_s = int(getattr(settings, 'AI_TESTCASE_IDEMPOTENCY_REUSE_WINDOW_SECONDS', 60) or 0)
        reuse_after = timezone.now() - timedelta(seconds=reuse_window_s) if reuse_window_s > 0 else None
        existing_qs = AiTestcaseGeneration.objects.filter(
            created_by=user,
            generation_mode='agent',
            idempotency_key=idempotency_key,
            status='success',
        )
        if reuse_after is not None:
            existing_qs = existing_qs.filter(created_at__gte=reuse_after)
        existing = existing_qs.order_by('-created_at').first()
        if existing:
            return Response({'record_id': existing.id, 'reused': True, 'status': existing.status}, status=status.HTTP_200_OK)

        record = AiTestcaseGeneration.objects.create(
            created_by=user,
            requirement=requirement,
            use_thinking=use_thinking,
            generation_mode='agent',
            status='generating',
            idempotency_key=idempotency_key,
            prompt_version=prompt_version,
            case_strategy_mode=mode,
        )

        if uploaded_files:
            try:
                saved_paths = _save_uploaded_files(uploaded_files, record.id)
                record.source_files = saved_paths
                record.save(update_fields=['source_files'])
            except Exception as e:
                record.status = 'failed'
                record.error_message = f'file_save_error: {str(e)}'
                record.save(update_fields=['status', 'error_message'])
                return Response({'detail': f'文件保存失败: {str(e)}'}, status=500)

        from apps.ai_testcase.tasks import run_ai_testcase_agent
        run_ai_testcase_agent.delay(record.id)
        return Response({'record_id': record.id, 'reused': False, 'status': record.status}, status=status.HTTP_201_CREATED)

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
        user = getattr(request, 'user', None)
        can_filter = False
        if user and getattr(user, 'is_authenticated', False):
            can_filter = bool(
                getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)
            )
        return Response({
            'configured': bool(api_key),
            'model': getattr(settings, 'KIMI_MODEL', 'kimi-k2.5'),
            'base_url': getattr(settings, 'KIMI_BASE_URL', 'https://api.moonshot.cn/v1'),
            'api_key_prefix': api_key[:8] + '...' if api_key else '',
            'can_filter_by_creator': can_filter,
        })


# ============ Agent 智能体生成入口 ============

async def agent_generate_stream_view(request):
    """
    SSE 流式 Agent 智能体生成测试用例

    与 generate-stream 的区别：Agent 会自动进行需求分析、策略规划、
    分模块生成、自评审和自动修订，直到用例质量达标。

    POST /api/ai_testcase/agent-generate-stream/
    支持 JSON 和 FormData 两种提交方式（与 generate-stream 一致）

    Response: text/event-stream
        data: {"type": "agent_start", "record_id": 1, "nodes": [...]}
        data: {"type": "agent_node_done", "node": "analyze_requirement", ...}
        data: {"type": "agent_review", "score": 0.65, ...}
        data: {"type": "agent_refining", "iteration": 2}
        data: {"type": "agent_done", "record_id": 1, "data": {...}, ...}
        data: {"type": "error", "error": "..."}
    """
    if request.method == 'OPTIONS':
        resp = HttpResponse(status=200)
        return _add_cors_headers(resp, request)

    if request.method != 'POST':
        return _add_cors_headers(HttpResponse('Method not allowed', status=405), request)

    user, auth_resp = await _authenticate_or_401(request)
    if auth_resp:
        return _add_cors_headers(auth_resp, request)

    throttle_resp = await _throttle_or_429_async(request, scope='ai_testcase')
    if throttle_resp:
        return _add_cors_headers(throttle_resp, request)

    extracted_texts = []
    images = []
    file_warnings = []
    content_type = request.content_type or ''
    uploaded_files = []

    if 'multipart' in content_type:
        from asgiref.sync import sync_to_async

        _post = await sync_to_async(lambda: request.POST)()
        _files = await sync_to_async(lambda: request.FILES)()

        requirement = _post.get('requirement', '').strip()
        use_thinking = _post.get('use_thinking', 'false').lower() in ('true', '1', 'yes')
        mode = _post.get('mode', 'comprehensive')
        uploaded_files = _files.getlist('files')

        if uploaded_files:
            try:
                processor = FileProcessor()
                file_result = await sync_to_async(processor.process_files)(uploaded_files)
                extracted_texts = file_result['texts']
                images = file_result['images']
                file_warnings = file_result['warnings']
            except FileProcessError as e:
                return _add_cors_headers(HttpResponse(str(e), status=400), request)
            except Exception as e:
                logger.exception(f"[Agent] 文件处理异常: {e}")
                return _add_cors_headers(HttpResponse(f'文件处理失败: {str(e)}', status=400), request)
    else:
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return _add_cors_headers(HttpResponse('Invalid JSON', status=400), request)

        requirement = body.get('requirement', '').strip()
        use_thinking = body.get('use_thinking', False)
        mode = body.get('mode', 'comprehensive')

    mode = normalize_case_strategy_mode(mode)

    if not requirement and not extracted_texts and not images:
        return _add_cors_headers(HttpResponse('请输入需求描述或上传文件', status=400), request)

    requirement_summary = requirement
    if not requirement_summary and extracted_texts:
        requirement_summary = f"[附件] {', '.join(t['source'] for t in extracted_texts[:3])}"
    if images and not requirement_summary:
        requirement_summary = f"[图片] {', '.join(img['source'] for img in images[:3])}"

    prompt_version = getattr(settings, 'AI_TESTCASE_PROMPT_VERSION', 'v1')
    idempotency_key = _compute_idempotency_key(
        generation_mode='agent',
        requirement=requirement or requirement_summary,
        mode=mode,
        use_thinking=use_thinking,
        extracted_texts=extracted_texts,
        images=images,
        prompt_version=prompt_version,
    )

    async def event_stream():
        from asgiref.sync import sync_to_async
        from .workflows.executor import TestcaseAgentExecutor

        reuse_window_s = int(getattr(settings, 'AI_TESTCASE_IDEMPOTENCY_REUSE_WINDOW_SECONDS', 60) or 0)
        reuse_after = timezone.now() - timedelta(seconds=reuse_window_s) if reuse_window_s > 0 else None

        def _find_existing():
            qs = AiTestcaseGeneration.objects.filter(
                created_by=user,
                generation_mode='agent',
                idempotency_key=idempotency_key,
                status='success',
            )
            if reuse_after is not None:
                qs = qs.filter(created_at__gte=reuse_after)
            return qs.order_by('-created_at').first()

        existing = await sync_to_async(_find_existing)()
        if existing and existing.result_json:
            _log_event(
                "agent_generate.reuse",
                record_id=existing.id,
                user_id=getattr(user, "id", None),
                prompt_version=existing.prompt_version,
            )
            yield f"data: {json.dumps({'type': 'agent_done', 'reused': True, 'record_id': existing.id, 'data': existing.result_json, 'review_score': existing.review_score, 'iterations': existing.iteration_count, 'module_count': existing.module_count, 'case_count': existing.case_count, 'usage': {'prompt_tokens': existing.prompt_tokens, 'completion_tokens': existing.completion_tokens, 'total_tokens': existing.total_tokens}}, ensure_ascii=False)}\n\n"
            return

        record = await sync_to_async(AiTestcaseGeneration.objects.create)(
            requirement=requirement_summary,
            created_by=user,
            use_thinking=use_thinking,
            status='generating',
            generation_mode='agent',
            idempotency_key=idempotency_key,
            prompt_version=prompt_version,
            case_strategy_mode=mode,
        )
        _log_event(
            "agent_generate.start",
            record_id=record.id,
            user_id=getattr(user, "id", None),
            prompt_version=prompt_version,
            idempotency_key=idempotency_key,
            mode=mode,
        )

        if uploaded_files:
            saved_paths = await sync_to_async(_save_uploaded_files)(uploaded_files, record.id)
            record.source_files = saved_paths
            await sync_to_async(record.save)(update_fields=['source_files'])

        if file_warnings:
            yield f"data: {json.dumps({'type': 'warnings', 'warnings': file_warnings}, ensure_ascii=False)}\n\n"

        async for event in TestcaseAgentExecutor.run(
            record=record,
            requirement=requirement or requirement_summary,
            extracted_texts=extracted_texts,
            images=images,
            use_thinking=use_thinking,
            mode=mode,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Content-Encoding'] = 'identity'
    return _add_cors_headers(response, request)


agent_generate_stream_view.csrf_exempt = True
