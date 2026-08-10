"""PDF renderer for ReportSpec using reportlab (pure Python, v3.9.0)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nonlinear_agent.reporting.fidelity import FidelityChecker
from nonlinear_agent.reporting.report_spec import ReportSpec


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


def _fmt(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "unknown"
