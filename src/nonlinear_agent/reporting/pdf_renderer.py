"""PDF renderer for ReportSpec using reportlab (pure Python, v3.9.0)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nonlinear_agent.reporting.fidelity import FidelityChecker
from nonlinear_agent.reporting.fidelity import TaskFidelityChecker
from nonlinear_agent.reporting.report_spec import ReportSpec
from nonlinear_agent.reporting.task_report_spec import TaskReportSpec


class RenderError(RuntimeError):
    """Structured render failure with a retryable error list."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def render_pdf(spec: ReportSpec, output_dir: Path | str, source: dict[str, Any] | None = None) -> Path:
    """Render ReportSpec to PDF. Raises RenderError with structured errors."""
    errors: list[str] = []
    if spec.psd_path is None or not Path(spec.psd_path).exists():
        errors.append("missing psd artifact")
    if source is not None:
        errors.extend(FidelityChecker().check(spec, source))
    if errors:
        raise RenderError(errors)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"report-{spec.run_id}.pdf"

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleX", parent=styles["Title"], fontSize=16, spaceAfter=10
    )
    heading = ParagraphStyle(
        "HeadingX", parent=styles["Heading2"], fontSize=12, spaceBefore=10
    )
    body = styles["BodyText"]

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
    )
    story: list[Any] = [
        Paragraph(f"Agent Harness Report — {spec.run_id}", title_style),
        Paragraph(f"Goal: {spec.goal}", body),
        Spacer(1, 6),
        Paragraph("Baseline / Current", heading),
        Table(
            [
                ["Metric", "Value"],
                ["baseline_nmse_db", _fmt(spec.baseline_nmse_db)],
                ["nmse_db", _fmt(spec.current_nmse_db)],
                ["parameter_count", str(spec.parameter_count)],
            ],
            style=TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ]
            ),
        ),
        Spacer(1, 8),
        Paragraph("Best Candidates", heading),
    ]
    if spec.best_table:
        story.append(
            Table(
                [["model_type", "nmse_db", "parameter_count"]]
                + [
                    [
                        str(c.get("model_type", "")),
                        _fmt(c.get("nmse_db")),
                        str(c.get("parameter_count", "")),
                    ]
                    for c in spec.best_table
                ],
                style=TableStyle(
                    [("GRID", (0, 0), (-1, -1), 0.4, colors.grey)]
                ),
            )
        )
    story += [
        Spacer(1, 8),
        Paragraph("Failure Cases", heading),
    ]
    for case in spec.failure_cases:
        story.append(
            Paragraph(
                f"- {case.get('id', '')}: {case.get('status', '')} "
                f"({case.get('error', '')})",
                body,
            )
        )
    story += [
        Spacer(1, 8),
        Paragraph(f"Cost: ${_fmt(spec.cost_usd)}", body),
        Paragraph("Trace", heading),
    ]
    for ref in spec.trace_refs:
        story.append(Paragraph(ref, body))
    story += [
        Spacer(1, 8),
        Paragraph("PSD", heading),
        Image(str(spec.psd_path), width=4.5 * inch, height=2.2 * inch),
        Spacer(1, 8),
        Paragraph("Reproduce", heading),
        Paragraph(spec.reproduce_command, body),
    ]
    doc.build(story)
    return pdf_path


def _fmt(value: float | None, digits: int = 4) -> str:
    return f"{value:.{digits}f}" if value is not None else "unknown"


_CN_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
)


def _register_cn_font() -> str:
    """Register a Chinese font with reportlab; returns font family name."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for path in _CN_FONT_CANDIDATES:
        if Path(path).exists():
            name = f"CN-{Path(path).stem}"
            pdfmetrics.registerFont(TTFont(name, path))
            return name
    return "Helvetica"


def render_task_pdf(
    spec: TaskReportSpec,
    output_dir: Path | str,
    source: dict[str, Any] | None = None,
    figures: dict[str, str] | None = None,
    analysis: dict[str, str] | None = None,
) -> Path:
    """中文任务级 PDF：表格 + PSD 图 + 达标/最优标注。"""
    figures = figures or {}
    analysis = analysis or {}
    psds = [
        p
        for p in (
            figures.get("psd"),
            figures.get("architecture"),
            figures.get("improvement"),
        )
        if p and Path(p).exists()
    ]
    errors: list[str] = []
    if not psds:
        errors.append("missing psd artifact for all executions")
    if source is not None:
        errors.extend(TaskFidelityChecker().check(spec, source))
    if errors:
        raise RenderError(errors)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"task-report-{spec.task_id}.pdf"

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    cn_font = _register_cn_font()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CNTitle", parent=styles["Title"], fontName=cn_font, fontSize=16, spaceAfter=10
    )
    heading = ParagraphStyle(
        "CNHeading", parent=styles["Heading2"], fontName=cn_font, fontSize=12, spaceBefore=10
    )
    body = ParagraphStyle(
        "CNBody", parent=styles["BodyText"], fontName=cn_font, fontSize=9
    )

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )
    story: list[Any] = [
        Paragraph(f"任务报告 — {spec.task_id}", title_style),
        Paragraph(f"目标：{spec.goal}", body),
        Spacer(1, 6),
        Paragraph("约束", heading),
        Paragraph("；".join(f"{k}={v}" for k, v in spec.constraints.items()), body),
        Paragraph("计划", heading),
    ]
    for h in spec.plan.get("hypotheses", []):
        story.append(Paragraph(f"假设：{h.get('假设', h)}", body))
    if spec.code_changes:
        story.append(Paragraph("代码变更", heading))
        story.append(
            Table(
                [["文件", "变更"]]
                + [[c.get("file", ""), c.get("change", "")] for c in spec.code_changes],
                style=TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey)]),
            )
        )
    story.append(Paragraph("实验结果", heading))
    best = spec.best()
    rows = [["实验", "模型", "NMSE (dB)", "参数量", "达标", "标注"]]
    for run in spec.executions:
        # 纯文字标注：SimHei 无 emoji 字形，避免渲染成方框
        mark = "最优" if best is not None and run.run_id == best.run_id else ""
        hit = "达标" if run.target_hit else "未达标"
        rows.append(
            [
                run.run_id,
                run.model_type,
                _fmt(run.nmse_db),
                str(run.parameter_count),
                hit,
                mark,
            ]
        )
    story.append(
        Table(
            rows,
            style=TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ]
            ),
        )
    )
    story.append(Paragraph("数据化总结", heading))
    best = spec.best()
    hit_count = sum(1 for r in spec.executions if r.target_hit)
    hit_rate = hit_count / len(spec.executions) if spec.executions else 0.0
    story.append(
        Table(
            [
                ["指标", "数值"],
                ["实验总数", str(len(spec.executions))],
                ["达标率", f"{hit_rate * 100:.0f}%"],
                ["最优 NMSE", _fmt(best.nmse_db) if best else "—"],
                ["相对基线提升", _fmt(best.nmse_db - best.baseline_nmse_db, 2) if best and best.nmse_db is not None and best.baseline_nmse_db is not None else "—"],
                ["总成本", f"${_fmt(spec.cost_usd, 4)}"],
            ],
            style=TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey)]),
        )
    )
    story.append(Paragraph("改进过程与效果", heading))
    if figures.get("improvement") and Path(figures["improvement"]).exists():
        story.append(Image(str(figures["improvement"]), width=5.5 * inch, height=2.8 * inch))
    if analysis.get("improvement"):
        story.append(Paragraph(analysis["improvement"], body))
    story.append(Paragraph("为什么有效", heading))
    if figures.get("psd") and Path(figures["psd"]).exists():
        story.append(Image(str(figures["psd"]), width=5.5 * inch, height=2.8 * inch))
    if analysis.get("why_effective"):
        story.append(Paragraph(analysis["why_effective"], body))
    story.append(Paragraph("经验总结", heading))
    if analysis.get("experience"):
        story.append(Paragraph(analysis["experience"], body))
    story.append(Paragraph("消融", heading))
    if spec.ablations:
        story.append(
            Table(
                [["策略", "best NMSE (dB)"], *[
                    [a.get("名称", a.get("name", "")), _fmt(a.get("best_nmse_db"))]
                    for a in spec.ablations
                ]],
                style=TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey)]),
            )
        )
    story.append(Paragraph("失败案例", heading))
    for case in spec.failure_cases:
        story.append(
            Paragraph(
                f"- {case.get('id', '')}: {case.get('状态', case.get('status', ''))} "
                f"({case.get('错误', case.get('error', ''))})",
                body,
            )
        )
    story += [
        Paragraph(f"总成本：${_fmt(spec.cost_usd)}", body),
        Paragraph("网络原理框图", heading),
    ]
    if figures.get("architecture") and Path(figures["architecture"]).exists():
        story.append(Image(str(figures["architecture"]), width=6.0 * inch, height=2.4 * inch))
    story += [
        Paragraph("复现", heading),
        Paragraph(spec.reproduce_command, body),
        Paragraph("限制", heading),
        Paragraph(spec.limits, body),
    ]
    doc.build(story)
    return pdf_path
