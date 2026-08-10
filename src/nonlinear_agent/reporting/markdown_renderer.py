"""Markdown renderer for ReportSpec (v3.9.0)."""

from __future__ import annotations

from nonlinear_agent.reporting.report_spec import ReportSpec


def render_markdown(spec: ReportSpec) -> str:
    lines = [
        f"# Agent Harness Report — {spec.run_id}",
        "",
        f"## Goal\n{spec.goal}",
        "",
        "## Baseline",
        f"- baseline_nmse_db: {_fmt(spec.baseline_nmse_db)}",
        "",
        "## Current",
        f"- nmse_db: {_fmt(spec.current_nmse_db)}",
        f"- parameter_count: {spec.parameter_count}",
        "",
        "## Best Candidates",
    ]
    if spec.best_table:
        lines.append(
            "| model_type | nmse_db | parameter_count |\n"
            "| --- | ---: | ---: |"
        )
        for candidate in spec.best_table:
            lines.append(
                f"| {candidate.get('model_type', '')} | "
                f"{_fmt(candidate.get('nmse_db'))} | "
                f"{candidate.get('parameter_count', '')} |"
            )
    else:
        lines.append("- none")
    lines += [
        "",
        "## Failure Cases",
    ]
    if spec.failure_cases:
        for case in spec.failure_cases:
            lines.append(
                f"- {case.get('id', '')}: {case.get('status', '')} "
                f"({case.get('error', '')})"
            )
    else:
        lines.append("- none")
    lines += [
        "",
        "## Cost",
        f"- cost_usd: {_fmt(spec.cost_usd)}",
        "",
        "## Trace",
    ]
    lines += [f"- `{ref}`" for ref in spec.trace_refs] or ["- none"]
    lines += [
        "",
        "## Reproduce",
        f"```\n{spec.reproduce_command}\n```",
        "",
    ]
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "unknown"
