"""Markdown renderer for ReportSpec (v3.9.0)."""

from __future__ import annotations

from nonlinear_agent.reporting.report_spec import ReportSpec
from nonlinear_agent.reporting.task_report_spec import TaskReportSpec


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


def render_task_markdown(spec: TaskReportSpec) -> str:
    """中文任务级报告：计划 → 代码变更 → 实验表格（达标/最优标注）→ 消融等。"""
    best = spec.best()
    lines = [
        f"# 任务报告 — {spec.task_id}",
        "",
        f"## 目标\n{spec.goal}",
        "",
        "## 约束",
    ]
    for key, value in spec.constraints.items():
        lines.append(f"- {key}: {value}")
    if spec.citations:
        lines += ["", "## 知识引用"]
        lines += [f"- {citation}" for citation in spec.citations]
    lines += ["", "## 计划"]
    hypotheses = spec.plan.get("hypotheses", [])
    if hypotheses:
        lines.append("### 假设")
        for h in hypotheses:
            lines.append(f"- {h.get('假设', h)}")
    candidates = spec.plan.get("candidate_experiments", [])
    if candidates:
        lines.append("### 候选实验")
        lines.append("| model_type | 参数估算 | 停止条件 |")
        lines.append("| --- | ---: | --- |")
        for c in candidates:
            lines.append(
                f"| {c.get('model_type', '')} | "
                f"{c.get('params_estimate', '')} | "
                f"{c.get('停止条件', c.get('stop_condition', ''))} |"
            )
    if spec.code_changes:
        lines += ["", "## 代码变更"]
        lines.append("| 文件 | 变更 |")
        lines.append("| --- | --- |")
        for change in spec.code_changes:
            lines.append(f"| {change.get('file', '')} | {change.get('change', '')} |")
    lines += ["", "## 实验结果"]
    if spec.executions:
        lines.append("| 实验 | 模型 | NMSE (dB) | 参数量 | 达标 | 标注 |")
        lines.append("| --- | --- | ---: | ---: | ---: | --- |")
        for run in spec.executions:
            mark = "⭐ 最优" if best is not None and run.run_id == best.run_id else ""
            hit = "✅ 达标" if run.target_hit else "❌ 未达标"
            lines.append(
                f"| {run.run_id} | {run.model_type} | "
                f"{_fmt(run.nmse_db)} | {run.parameter_count} | {hit} | {mark} |"
            )
    else:
        lines.append("- 无执行结果")
    if spec.ablations:
        lines += ["", "## 消融"]
        lines.append("| 策略 | best NMSE (dB) |")
        lines.append("| --- | ---: |")
        for ablation in spec.ablations:
            name = ablation.get("名称", ablation.get("name", ""))
            value = ablation.get("best_nmse_db")
            lines.append(f"| {name} | {_fmt(value)} |")
    lines += ["", "## 失败案例"]
    if spec.failure_cases:
        for case in spec.failure_cases:
            lines.append(
                f"- {case.get('id', '')}: {case.get('状态', case.get('status', ''))} "
                f"({case.get('错误', case.get('error', ''))})"
            )
    else:
        lines.append("- 无")
    lines += [
        "",
        "## 成本",
        f"- 总成本: ${_fmt(spec.cost_usd)}",
        "",
        "## Trace",
    ]
    lines += [f"- `{ref}`" for ref in spec.trace_refs] or ["- 无"]
    lines += [
        "",
        "## 复现",
        f"```\n{spec.reproduce_command}\n```",
        "",
        "## 限制",
        spec.limits,
        "",
    ]
    return "\n".join(lines)
