# -*- coding: utf-8 -*-
"""
Jira / Confluence 连接器（P2-3 MCP 工具链同能力）

根据 task_id 读取 AiRequirementTask 的 result_json/result_md，
调用 Jira/Confluence REST API 创建工单或写入文档。
未配置时返回 {"success": False, "error": "not_configured"}。
"""
import base64
import json
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings


def _jira_configured() -> bool:
    base = getattr(settings, "JIRA_BASE_URL", "") or ""
    token = getattr(settings, "JIRA_API_TOKEN", "") or ""
    return bool(base.strip() and token.strip())


def _confluence_configured() -> bool:
    base = getattr(settings, "CONFLUENCE_BASE_URL", "") or ""
    token = getattr(settings, "CONFLUENCE_API_TOKEN", "") or ""
    return bool(base.strip() and token.strip())


def _http_post(
    url: str,
    body: dict,
    *,
    basic_auth: str | None = None,
    content_type: str = "application/json",
) -> tuple[int, Any]:
    """POST JSON 并返回 (status_code, parsed_json or None)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": content_type, "Accept": "application/json"},
    )
    if basic_auth:
        req.add_header("Authorization", "Basic " + basic_auth)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8")
            body_out = json.loads(raw) if raw else None
        except Exception:
            body_out = None
        return e.code, body_out
    except (json.JSONDecodeError, urllib.error.URLError, OSError) as e:
        return -1, {"_raw_error": str(e)}


def create_jira_tickets_from_task(
    task_id: int,
    project_key: str | None = None,
    issue_type: str = "Task",
) -> dict:
    """
    根据 feature_breakdown 任务的 result_json 在 Jira 中创建多个 Issue。
    返回 {"success": bool, "created": [{"key": "PROJ-1", ...}], "error": str?}
    """
    from apps.ai_requirement.models import AiRequirementTask

    if not _jira_configured():
        return {"success": False, "created": [], "error": "Jira 未配置（JIRA_BASE_URL / JIRA_API_TOKEN）"}

    try:
        task = AiRequirementTask.objects.get(id=task_id)
    except AiRequirementTask.DoesNotExist:
        return {"success": False, "created": [], "error": "任务不存在"}

    if task.task_type != "feature_breakdown":
        return {"success": False, "created": [], "error": "仅支持 feature_breakdown 任务类型"}
    data = task.result_json
    if not data or not isinstance(data, dict):
        return {"success": False, "created": [], "error": "该任务无结构化结果"}

    modules = data.get("modules", [])
    if not modules:
        return {"success": False, "created": [], "error": "功能点数据为空"}

    base_url = (getattr(settings, "JIRA_BASE_URL", "") or "").rstrip("/")
    proj = (project_key or getattr(settings, "JIRA_PROJECT_KEY", "") or "").strip()
    if not proj:
        return {"success": False, "created": [], "error": "未指定 JIRA 项目（JIRA_PROJECT_KEY 或请求参数 project_key）"}

    email = (getattr(settings, "JIRA_EMAIL", "") or "").strip()
    token = (getattr(settings, "JIRA_API_TOKEN", "") or "").strip()
    basic_auth = base64.b64encode(f"{email}:{token}".encode()).decode() if email else None
    if not basic_auth and token:
        # 仅 API Token 时可用 Bearer（部分 Jira Cloud 支持）
        basic_auth = base64.b64encode(f"{token}:".encode()).decode()

    created = []
    title = data.get("title", "功能点梳理")

    for mod in modules:
        mod_name = mod.get("name", "未命名模块")
        for func in mod.get("functions", []):
            name = func.get("name", "未命名功能")
            desc_parts = [func.get("description") or "", f"\n\n验收要点:"]
            for ap in func.get("acceptance_points", []):
                desc_parts.append(f"\n- {ap}")
            if func.get("test_hint"):
                desc_parts.append(f"\n测试建议: {func['test_hint']}")
            description = "\n".join(desc_parts) if desc_parts else name
            payload = {
                "fields": {
                    "project": {"key": proj},
                    "summary": f"[{mod_name}] {name}",
                    "description": description,
                    "issuetype": {"name": issue_type},
                }
            }
            code, resp = _http_post(
                f"{base_url}/rest/api/3/issue",
                payload,
                basic_auth=basic_auth,
            )
            if code in (200, 201) and resp and isinstance(resp, dict):
                created.append({"key": resp.get("key"), "id": resp.get("id")})
            else:
                return {
                    "success": False,
                    "created": created,
                    "error": f"创建 Jira 工单失败: HTTP {code}",
                    "details": resp,
                }

    return {"success": True, "created": created, "error": None}


def write_prd_to_confluence(
    task_id: int,
    space_key: str | None = None,
    title: str | None = None,
) -> dict:
    """
    将任务的 PRD 内容（result_md 或 result_json.markdown_full）写入 Confluence 页面。
    返回 {"success": bool, "page_id": str?, "url": str?, "error": str?}
    """
    from apps.ai_requirement.models import AiRequirementTask

    if not _confluence_configured():
        return {"success": False, "page_id": None, "url": None, "error": "Confluence 未配置（CONFLUENCE_BASE_URL / CONFLUENCE_API_TOKEN）"}

    try:
        task = AiRequirementTask.objects.get(id=task_id)
    except AiRequirementTask.DoesNotExist:
        return {"success": False, "page_id": None, "url": None, "error": "任务不存在"}

    body_html = ""
    page_title = title or f"PRD-{task.task_type}-{task_id}"

    if task.result_md:
        # 简单将 Markdown 转为 Confluence 存储格式（用 <p> 与换行）
        import re
        md = task.result_md
        md = re.sub(r"<", "&lt;", md)
        md = re.sub(r">", "&gt;", md)
        lines = md.split("\n")
        out = []
        for line in lines:
            if line.startswith("# "):
                out.append(f"<h1>{line[2:].strip()}</h1>")
            elif line.startswith("## "):
                out.append(f"<h2>{line[3:].strip()}</h2>")
            elif line.startswith("### "):
                out.append(f"<h3>{line[4:].strip()}</h3>")
            elif line.strip():
                out.append(f"<p>{line}</p>")
            else:
                out.append("<p></p>")
        body_html = "".join(out)
    elif task.result_json and isinstance(task.result_json, dict):
        page_title = title or (task.result_json.get("prd_meta", {}) or {}).get("version") or page_title
        raw_md = (task.result_json.get("markdown_full") or "").strip()
        if raw_md:
            import re
            md = re.sub(r"<", "&lt;", raw_md)
            md = re.sub(r">", "&gt;", md)
            lines = md.split("\n")
            out = []
            for line in lines:
                if line.startswith("# "):
                    out.append(f"<h1>{line[2:].strip()}</h1>")
                elif line.startswith("## "):
                    out.append(f"<h2>{line[3:].strip()}</h2>")
                elif line.startswith("### "):
                    out.append(f"<h3>{line[4:].strip()}</h3>")
                elif line.strip():
                    out.append(f"<p>{line}</p>")
                else:
                    out.append("<p></p>")
            body_html = "".join(out)

    if not body_html:
        return {"success": False, "page_id": None, "url": None, "error": "该任务无 PRD 正文（result_md / result_json.markdown_full）"}

    space = (space_key or getattr(settings, "CONFLUENCE_SPACE_KEY", "") or "").strip()
    if not space:
        return {"success": False, "page_id": None, "url": None, "error": "未指定 Confluence 空间（CONFLUENCE_SPACE_KEY 或请求参数 space_key）"}

    base_url = (getattr(settings, "CONFLUENCE_BASE_URL", "") or "").rstrip("/")
    email = (getattr(settings, "CONFLUENCE_EMAIL", "") or "").strip()
    token = (getattr(settings, "CONFLUENCE_API_TOKEN", "") or "").strip()
    basic_auth = base64.b64encode(f"{email}:{token}".encode()).decode() if email else None
    if not basic_auth and token:
        basic_auth = base64.b64encode(f"{token}:".encode()).decode()

    payload = {
        "type": "page",
        "title": page_title,
        "space": {"key": space},
        "body": {
            "storage": {"value": body_html, "representation": "storage"},
        },
    }
    code, resp = _http_post(
        f"{base_url}/wiki/rest/api/content",
        payload,
        basic_auth=basic_auth,
    )
    if code in (200, 201) and resp and isinstance(resp, dict):
        pid = resp.get("id")
        links = (resp.get("_links") or {}) if isinstance(resp.get("_links"), dict) else {}
        webui = links.get("webui") or ""
        base = base_url.rstrip("/")
        if webui:
            url = base + "/wiki" + webui if not base.endswith("/wiki") else base + webui
        else:
            url = base + "/wiki/spaces/" + space + "/pages/" + str(pid)
        return {"success": True, "page_id": str(pid), "url": url, "error": None}
    return {
        "success": False,
        "page_id": None,
        "url": None,
        "error": f"创建 Confluence 页面失败: HTTP {code}",
        "details": resp,
    }
