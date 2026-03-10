# -*- coding: utf-8 -*-
"""
需求智能体：导出为 PDF / Word（.docx）
"""
import io
import re
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

# 任务类型 -> 中文名（用于文件名）
TASK_TYPE_LABELS = {
    'competitive_analysis': '竞品分析',
    'prd_draft': 'PRD撰写',
    'prd_refine': '需求完善',
    'requirement_analysis': '需求分析',
    'tech_design': '技术方案',
    'test_requirement_analysis': '测试需求分析',
    'feature_breakdown': '功能点梳理',
}


def _safe_filename(title: str, task_type: str, ext: str) -> str:
    """生成安全文件名：标题前30字_任务类型.扩展名"""
    label = TASK_TYPE_LABELS.get(task_type, task_type)
    clean = re.sub(r'[<>:"/\\|?*]', '_', (title or '')[:30].strip()) or '需求'
    return f"{clean}_{label}.{ext}"


def export_docx(task) -> tuple[bytes, str]:
    """
    将任务导出为 Word (.docx)。
    :return: (文件二进制, 建议文件名)
    """
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

    content = (task.result_md or task.raw_content or '').strip()
    if not content:
        raise ValueError("该任务无文本内容可导出")

    doc = Document()
    # 标题行：需求摘要 + 任务类型
    title = (task.requirement_input or '')[:80].strip() or '需求智能体输出'
    task_label = TASK_TYPE_LABELS.get(task.task_type, task.task_type)
    doc.add_heading(f"{title}\n[{task_label}]", level=0)

    # 按行写入：## 作为标题，其余为正文
    for block in content.split('\n\n'):
        block = block.strip()
        if not block:
            continue
        lines = block.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('### '):
                doc.add_heading(line[4:].strip(), level=3)
            elif line.startswith('## '):
                doc.add_heading(line[3:].strip(), level=2)
            elif line.startswith('# '):
                doc.add_heading(line[2:].strip(), level=1)
            else:
                p = doc.add_paragraph()
                p.add_run(line)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    filename = _safe_filename(task.requirement_input, task.task_type, 'docx')
    return buf.getvalue(), filename


def _get_chinese_font_path():
    """尝试获取系统中文字体路径（TTF 优先，TTC 需子字体索引），用于 ReportLab PDF。"""
    import os
    # TTF 单字体文件优先；TTC 为集合，ReportLab 需 TTF 或 TTC+index
    candidates = [
        ('C:/Windows/Fonts/msyh.ttf', None),
        ('C:/Windows/Fonts/simhei.ttf', None),
        ('C:/Windows/Fonts/simsun.ttc', 0),
        ('C:/Windows/Fonts/msyh.ttc', 0),
        ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 0),
        ('/System/Library/Fonts/PingFang.ttc', 0),
    ]
    for path, subindex in candidates:
        if os.path.isfile(path):
            return path, subindex
    return None, None


def export_pdf(task) -> tuple[bytes, str]:
    """
    将任务导出为 PDF。
    :return: (文件二进制, 建议文件名)
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    content = (task.result_md or task.raw_content or '').strip()
    if not content:
        raise ValueError("该任务无文本内容可导出")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()
    font_path, font_subindex = _get_chinese_font_path()
    if font_path:
        try:
            kw = {"subfontIndex": font_subindex} if font_subindex is not None else {}
            pdfmetrics.registerFont(TTFont("ChineseFont", font_path, **kw))
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontName='ChineseFont',
                fontSize=10,
            )
            heading1_style = ParagraphStyle(
                'CustomHeading1',
                parent=styles['Heading1'],
                fontName='ChineseFont',
                fontSize=16,
            )
            heading2_style = ParagraphStyle(
                'CustomHeading2',
                parent=styles['Heading2'],
                fontName='ChineseFont',
                fontSize=14,
            )
        except Exception as e:
            logger.warning("[export_pdf] 注册中文字体失败，使用默认: %s", e)
            normal_style = styles['Normal']
            heading1_style = styles['Heading1']
            heading2_style = styles['Heading2']
    else:
        normal_style = styles['Normal']
        heading1_style = styles['Heading1']
        heading2_style = styles['Heading2']

    def escape(s):
        return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    story = []
    title = (task.requirement_input or '')[:80].strip() or '需求智能体输出'
    task_label = TASK_TYPE_LABELS.get(task.task_type, task.task_type)
    story.append(Paragraph(escape(f"{title} [{task_label}]"), heading1_style))
    story.append(Spacer(1, 0.5*cm))

    for block in content.split('\n\n'):
        block = block.strip()
        if not block:
            continue
        for line in block.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('### '):
                story.append(Paragraph(escape(line[4:].strip()), heading2_style))
            elif line.startswith('## '):
                story.append(Paragraph(escape(line[3:].strip()), heading2_style))
            elif line.startswith('# '):
                story.append(Paragraph(escape(line[2:].strip()), heading1_style))
            else:
                story.append(Paragraph(escape(line), normal_style))

    doc.build(story)
    buf.seek(0)
    filename = _safe_filename(task.requirement_input, task.task_type, 'pdf')
    return buf.getvalue(), filename
