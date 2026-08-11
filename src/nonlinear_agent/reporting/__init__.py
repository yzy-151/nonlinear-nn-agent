"""v3.9.0 Reporting: ReportSpec, fidelity checker, Markdown/PDF renderers."""

from nonlinear_agent.reporting.fidelity import FidelityChecker, TaskFidelityChecker
from nonlinear_agent.reporting.markdown_renderer import render_markdown, render_task_markdown
from nonlinear_agent.reporting.pdf_renderer import RenderError, render_pdf, render_task_pdf
from nonlinear_agent.reporting.report_spec import ReportSpec, ReportSpecBuilder
from nonlinear_agent.reporting.task_report_spec import RunResult, TaskReportBuilder, TaskReportSpec

__all__ = [
    "FidelityChecker",
    "RenderError",
    "ReportSpec",
    "ReportSpecBuilder",
    "RunResult",
    "TaskFidelityChecker",
    "TaskReportBuilder",
    "TaskReportSpec",
    "render_markdown",
    "render_pdf",
    "render_task_markdown",
    "render_task_pdf",
]
