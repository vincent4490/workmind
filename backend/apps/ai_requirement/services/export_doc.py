# -*- coding: utf-8 -*-
"""
需求智能体：导出为 Word（.docx）/ XMind（.xmind）
- 产品、开发角色任务 → Word
- 测试角色任务 → XMind
"""
import re
import logging
import os
import shutil
import subprocess
import tempfile
from .requirement_xmind import build_to_bytes as xmind_build_to_bytes

logger = logging.getLogger(__name__)

# 任务类型 -> 中文名（用于文件名）
TASK_TYPE_LABELS = {
    'competitive_analysis': '竞品分析',
    'prd_draft': 'PRD撰写',
    'prd_refine': '需求完善',
    'requirement_analysis': '需求分析',
    'tech_design': '技术方案',
    'test_requirement_analysis': '测试需求分析',
}


def _safe_filename(title: str, task_type: str, ext: str) -> str:
    """生成安全文件名：标题前30字_任务类型.扩展名"""
    label = TASK_TYPE_LABELS.get(task_type, task_type)
    clean = re.sub(r'[<>:"/\\|?*]', '_', (title or '')[:30].strip()) or '需求'
    return f"{clean}_{label}.{ext}"


def export_docx(task) -> tuple[bytes, str]:
    """
    将任务导出为 Word (.docx)，适用于产品/开发角色任务。
    :return: (文件二进制, 建议文件名)
    """
    content = (task.result_md or getattr(task, 'raw_content', '') or '').strip()
    if not content:
        raise ValueError("该任务无文本内容可导出为 Word")

    # 方案A：使用 pandoc 将 Markdown 直接转换为真正结构化 docx
    pandoc_path = shutil.which('pandoc') or shutil.which('pandoc.exe')
    if not pandoc_path:
        # 即使你在当前终端里能跑 pandoc，也可能后端进程 PATH 没刷新。
        # 这里做常见路径兜底，避免导出失败。
        candidates: list[str] = []
        env_path = os.environ.get('PANDOC_PATH')
        if isinstance(env_path, str) and env_path.strip():
            candidates.append(env_path.strip())

        candidates.extend([
            r"C:\Program Files\Pandoc\pandoc.exe",
            r"C:\Program Files (x86)\Pandoc\pandoc.exe",
            r"C:\Users\admin\AppData\Local\Pandoc\pandoc.exe",
            r"C:\Users\Public\Pandoc\pandoc.exe",
        ])

        for c in candidates:
            if c and os.path.isfile(c):
                pandoc_path = c
                break

    if not pandoc_path:
        raise ValueError(
            "方案A导出 Word 需要 `pandoc.exe`。"
            "我在当前后端进程里找不到 pandoc（可能是 PATH 未刷新或安装目录不在 PATH）。"
            "请确认 pandoc 已安装，并确保后端进程能访问到它。"
            "（你可以把 pandoc.exe 路径设为环境变量 `PANDOC_PATH` 后再重试）"
        )

    title = (task.requirement_input or '')[:80].strip() or '需求智能体输出'
    task_label = TASK_TYPE_LABELS.get(task.task_type, task.task_type)

    # 用普通段落承载标题，避免与正文的 H1 重复
    md = f"{title}\n[{task_label}]\n\n{content}"

    with tempfile.TemporaryDirectory(prefix='ai_req_docx_') as tmpdir:
        md_path = f"{tmpdir}/input.md"
        docx_path = f"{tmpdir}/output.docx"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md)

        # --wrap=none：减少因为换行重排导致的视觉差异
        # pandoc 会正确处理列表/表格/代码块等
        proc = subprocess.run(
            [
                pandoc_path,
                '--from', 'markdown',
                '--to', 'docx',
                '--wrap=none',
                md_path,
                '-o',
                docx_path,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            err_snip = (proc.stderr or proc.stdout or '').strip()[:500]
            raise ValueError(f"pandoc 转换失败: {err_snip}")

        with open(docx_path, 'rb') as f:
            out_bytes = f.read()

    filename = _safe_filename(task.requirement_input, task.task_type, 'docx')
    return out_bytes, filename


def export_xmind(task) -> tuple[bytes, str]:
    """
    将任务 result_json 导出为 XMind，适用于测试角色任务。
    :return: (文件二进制, 建议文件名)
    """
    if not getattr(task, "result_json", None):
        raise ValueError("该任务无结构化结果可导出为 XMind")
    data = xmind_build_to_bytes(task)
    filename = _safe_filename(task.requirement_input, task.task_type, 'xmind')
    return data, filename
