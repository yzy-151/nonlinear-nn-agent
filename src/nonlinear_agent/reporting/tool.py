"""write_task_report tool — the agent-facing reporting capability (v3.9.x).

Registered in the ToolRegistry so the Writing Agent can produce an
analysis-style Chinese HTML + PDF report through the normal tool chain:
architecture diagram, PSD figure, improvement chart, data-driven tables,
agent-supplied analysis, fidelity check, HTML -> PDF (headless Edge).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from nonlinear_agent.reporting.fidelity import TaskFidelityChecker
from nonlinear_agent.reporting.figures import (
    draw_architecture_diagram,
    draw_improvement_bars,
)
from nonlinear_agent.reporting.html_renderer import render_task_html
from nonlinear_agent.reporting.pdf_renderer import RenderError, render_task_pdf
from nonlinear_agent.reporting.task_report_spec import TaskReportBuilder
from nonlinear_agent.tools import ToolSpec


def write_task_report_tool(
    workspace: Path | str,
    task_source: dict[str, Any],
    output_dir: str | None = None,
    analysis: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Generate an analysis-style Chinese HTML + PDF task report."""
    root = Path(workspace)
    out = root / (output_dir or "reports/task-report")
    out.mkdir(parents=True, exist_ok=True)
    fig_dir = out / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    spec = TaskReportBuilder().build(task_source)
    if not spec.executions:
        raise RenderError(["task_source.executions is empty; nothing to report"])
    fidelity_errors = TaskFidelityChecker().check(spec, task_source)
    if fidelity_errors:
        raise RenderError(fidelity_errors)

    best = spec.best()
    best_config: dict[str, Any] = {}
    best_source: dict[str, Any] = {}
    if best is not None:
        best_source = next(
            (
                e
                for e in task_source.get("executions", [])
                if str(e.get("run_id")) == best.run_id
            ),
            {},
        )
        best_config = {
            "hidden_units": best_source.get("hidden_units"),
            "memory_depth": best_source.get("memory_depth"),
            "mp_order_count": best_source.get("mp_order_count"),
            "activation": best_source.get("activation"),
        }
    psd_value = best_source.get("psd_path")
    if not psd_value:
        raise RenderError(["best execution is missing a real PSD artifact"])
    source_psd = Path(str(psd_value))
    if not source_psd.is_absolute():
        source_psd = root / source_psd
    source_psd = source_psd.resolve()
    try:
        source_psd.relative_to(root.resolve())
    except ValueError as exc:
        raise RenderError(["real PSD artifact must be inside the workspace"]) from exc
    if not source_psd.is_file():
        raise RenderError([f"real PSD artifact does not exist: {source_psd}"])

    arch = draw_architecture_diagram(
        best.model_type if best else "unknown",
        fig_dir / "architecture.png",
        config=best_config,
    )
    psd = fig_dir / f"psd{source_psd.suffix.lower()}"
    if source_psd != psd.resolve():
        shutil.copy2(source_psd, psd)
    improvement = draw_improvement_bars(
        [
            (r.run_id, r.baseline_nmse_db or 0.0, r.nmse_db or 0.0)
            for r in spec.executions
            if r.nmse_db is not None
        ],
        fig_dir / "improvement.png",
    )
    html_doc = render_task_html(
        spec,
        figures={
            "architecture": str(arch),
            "psd": str(psd),
            "improvement": str(improvement),
            "psd_note": f"真实实验 PSD，来源：{best.run_id if best else 'unknown'} / {source_psd.name}",
        },
        analysis=analysis,
    )
    html_path = out / f"task-report-{spec.task_id}.html"
    html_path.write_text(html_doc, encoding="utf-8")
    pdf_path = render_task_pdf(
        spec,
        out,
        source=task_source,
        figures={
            "architecture": str(arch),
            "psd": str(psd),
            "improvement": str(improvement),
        },
        analysis=analysis,
    )

    def rel(path: Path) -> str:
        return str(Path(path).relative_to(root)).replace("\\", "/")

    return {
        "artifacts": [
            rel(html_path),
            rel(pdf_path),
            rel(arch),
            rel(psd),
            rel(improvement),
        ],
        "html_path": rel(html_path),
        "pdf_path": rel(pdf_path),
        "context_summary": f"任务报告已生成：{rel(pdf_path)}（HTML+PDF，含架构框图/PSD/改进分析/数据化总结）",
    }


def write_task_report_spec() -> ToolSpec:
    return ToolSpec(
        name="write_task_report",
        description=(
            "为一次实验任务生成分析型中文 HTML+PDF 报告：网络原理框图、PSD 功率谱、"
            "改进效果对比、实验结果表、数据化总结、消融与失败案例；"
            "analysis 字段提供改进过程/为什么有效/经验总结文本。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "task_source": {
                    "type": "object",
                    "description": "任务级数据：goal/constraints/executions/ablations/failure_cases/cost_usd 等",
                },
                "output_dir": {"type": "string"},
                "analysis": {
                    "type": "object",
                    "description": "可选：improvement/why_effective/experience 分析文本",
                },
            },
            "required": ["task_source"],
            "additionalProperties": False,
        },
        category="reporting",
        error_policy="return_error",
    )
