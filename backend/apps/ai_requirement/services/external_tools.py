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
    根据需求任务在 Jira 中创建工单。当前版本不支持，返回 501 提示。
    返回 {"success": bool, "created": [{"key": "PROJ-1", ...}], "error": str?}
    """
    return {"success": False, "created": [], "error": "当前不支持从需求任务创建 Jira 工单"}


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
