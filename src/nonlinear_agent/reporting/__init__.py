"""v3.9.0 Reporting: ReportSpec, fidelity checker, Markdown/PDF renderers."""

from nonlinear_agent.reporting.fidelity import FidelityChecker
from nonlinear_agent.reporting.markdown_renderer import render_markdown
from nonlinear_agent.reporting.pdf_renderer import RenderError, render_pdf
from nonlinear_agent.reporting.report_spec import ReportSpec, ReportSpecBuilder

__all__ = [
    "FidelityChecker",
    "RenderError",
    "ReportSpec",
    "ReportSpecBuilder",
    "render_markdown",
    "render_pdf",
]
