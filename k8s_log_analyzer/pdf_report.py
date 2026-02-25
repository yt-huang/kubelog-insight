"""
Generate PDF report for analysis result or project documentation.
Uses ReportLab for layout.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from .analysis_engine import AnalysisResult
from .history_store import HistoryEntry


def _get_reportlab():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, PageBreak
        return colors, A4, getSampleStyleSheet, ParagraphStyle, cm, SimpleDocTemplate, Paragraph, Spacer, Preformatted, PageBreak
    except ImportError:
        return None


def generate_analysis_pdf(result: AnalysisResult, output_path: str | Path) -> Optional[str]:
    """
    Generate a PDF report from an AnalysisResult.
    Returns None on success, or error message on failure.
    """
    lib = _get_reportlab()
    if lib is None:
        return "ReportLab not installed (pip install reportlab)"

    colors, A4, getSampleStyleSheet, ParagraphStyle, cm, SimpleDocTemplate, Paragraph, Spacer, Preformatted, PageBreak = lib
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name="CustomTitle",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=12,
        )
        heading_style = styles["Heading2"]
        body_style = styles["Normal"]

        story = []
        story.append(Paragraph("Kubernetes Log Analysis Report", title_style))
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("Component", heading_style))
        story.append(Paragraph(
            f"Type: {result.component_type} | Name: {result.component_name} | Namespace: {result.namespace}",
            body_style,
        ))
        if result.time_range:
            story.append(Paragraph(f"Time range: {result.time_range}", body_style))
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("Status", heading_style))
        status = "Success" if result.success else "Failed"
        story.append(Paragraph(status, body_style))
        if result.error_message:
            story.append(Paragraph(f"Error: {result.error_message}", body_style))
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("Analysis Result", heading_style))
        analysis = result.analysis_text or "(No analysis text)"
        story.append(Preformatted(analysis, body_style))
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("Preprocessed Log Preview", heading_style))
        preview = result.preprocessed_log_preview or "(empty)"
        story.append(Preformatted(preview[:3000], body_style))

        doc.build(story)
        return None
    except Exception as e:
        return str(e)


def generate_project_doc_pdf(output_path: str | Path) -> Optional[str]:
    """
    Generate project documentation PDF (background, solution, architecture, usage, highlights).
    Returns None on success, or error message on failure.
    """
    lib = _get_reportlab()
    if lib is None:
        return "ReportLab not installed (pip install reportlab)"

    colors, A4, getSampleStyleSheet, ParagraphStyle, cm, SimpleDocTemplate, Paragraph, Spacer, Preformatted, PageBreak = lib
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name="DocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            spaceAfter=14,
        )
        h2 = styles["Heading2"]
        body = styles["Normal"]

        story = []
        story.append(Paragraph("Kubernetes 日志分析工具 - 项目文档", title_style))
        story.append(Spacer(1, 0.8 * cm))

        story.append(Paragraph("1. 项目背景与痛点", h2))
        story.append(Paragraph(
            "在 Kubernetes 环境中，管理和分析大量日志是确保系统健康的关键。然而，这些日志量巨大，"
            "手动分析耗时且易错，特别是在识别特定异常（如空指针异常）时。需要一个自动化工具以便快速准确地分析日志，发现问题。",
            body,
        ))
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("2. 解决方案", h2))
        story.append(Paragraph(
            "开发一个工具，通过 kubectl-ai 自动分析 Kubernetes 中 Deployment 和 StatefulSet 的日志。"
            "用户可指定组件类型、组件名称和时间范围。工具将自动过滤、分析日志并高亮显示高危异常。",
            body,
        ))
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("3. 架构设计", h2))
        story.append(Paragraph("前端：使用 Python 的 Tkinter 开发用户界面。", body))
        story.append(Paragraph(
            "后端：使用 Python 和 Shell 脚本提取日志；通过 kubectl-ai 分析并识别异常；加入日志预处理，解决数据量过大问题。",
            body,
        ))
        story.append(Paragraph(
            "日志预处理：关键字过滤（正则）、按时间或事件类型采样与分片、可选 gzip 压缩。",
            body,
        ))
        story.append(Paragraph(
            "API 封装：封装 kubectl-ai 调用，支持扩展其他 API（如 DeepSeek）。",
            body,
        ))
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("4. 使用说明", h2))
        story.append(Paragraph(
            "输入组件类型（Deployment 或 StatefulSet）、组件名称、命名空间、时间范围。通过界面启动分析后，"
            "工具自动处理并分析日志，在结果区域高亮显示异常并展示分析结果。支持在历史记录中浏览和查询过去的分析。",
            body,
        ))
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("5. 项目亮点", h2))
        story.append(Paragraph("自动化与智能化：自动化日志分析，利用 AI 识别关键问题。", body))
        story.append(Paragraph("用户友好：简单的 UI 设计，易于操作。", body))
        story.append(Paragraph("高效处理：过滤与采样策略减少数据量，提升处理速度。", body))
        story.append(Paragraph("灵活扩展：API 封装增强系统的可扩展性。", body))

        doc.build(story)
        return None
    except Exception as e:
        return str(e)
