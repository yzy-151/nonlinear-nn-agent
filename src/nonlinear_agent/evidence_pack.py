"""Build one auditable evidence bundle from behavior, search, and reliability evals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


COLORS = {
    "navy": "#1B365D",
    "blue": "#3478B8",
    "teal": "#2A9D8F",
    "amber": "#E9A23B",
    "red": "#C94C4C",
    "gray": "#6B7280",
}


def merge_agent_benchmark_reports(
    original: dict[str, Any], correction: dict[str, Any]
) -> dict[str, Any]:
    """Replace corrected case rows and recompute task-level pass@k."""
    corrected_ids = {
        str(row.get("case_id")) for row in correction.get("results", [])
    }
    rows = [
        row for row in original.get("results", [])
        if str(row.get("case_id")) not in corrected_ids
    ] + list(correction.get("results", []))
    case_ids = sorted({str(row.get("case_id")) for row in rows})
    max_attempts = max((int(row.get("attempt", 1)) for row in rows), default=1)
    first_passes = 0
    any_passes = 0
    for case_id in case_ids:
        case_rows = sorted(
            (row for row in rows if str(row.get("case_id")) == case_id),
            key=lambda row: int(row.get("attempt", 1)),
        )
        first_passes += int(bool(case_rows and case_rows[0].get("passed")))
        any_passes += int(any(bool(row.get("passed")) for row in case_rows))
    task_count = len(case_ids)
    merged = dict(original)
    merged.update({
        "task_count": task_count,
        "attempt_count": len(rows),
        "pass_at_1": first_passes / task_count if task_count else 0.0,
        f"pass_at_{max_attempts}": any_passes / task_count if task_count else 0.0,
        "results": rows,
        "correction_provenance": {
            "replaced_cases": sorted(corrected_ids),
            "reason": "scoring protocol correction",
        },
    })
    return merged


def build_evidence_summary(
    scripted: dict[str, Any],
    online: dict[str, Any] | None,
    search_summary: dict[str, Any] | None,
    stress: dict[str, Any] | None,
    online_before: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def behavior(report: dict[str, Any] | None, scope: str) -> dict[str, Any] | None:
        if not report:
            return None
        rows = report.get("results", [])
        return {
            "evaluation_mode": report.get("evaluation_mode"),
            "task_count": report.get("task_count", 0),
            "attempt_count": report.get("attempt_count", 0),
            "pass_at_1": report.get("pass_at_1", 0.0),
            "pass_at_3": report.get("pass_at_3"),
            "prompt_tokens": sum(int(row.get("total_prompt_tokens", 0)) for row in rows),
            "completion_tokens": sum(int(row.get("total_completion_tokens", 0)) for row in rows),
            "claim_scope": scope,
        }

    return {
        "protocol": "evidence-pack-v1",
        "agent_behavior": {
            "scripted": behavior(
                scripted, "Harness contract regression; no LLM reasoning claim."
            ),
            "online": behavior(
                online, "Real LLM action selection and recovery on deterministic faults."
            ),
            "online_before": behavior(
                online_before, "Pre-improvement real LLM baseline on the same protocol."
            ),
        },
        "search_quality": search_summary or {},
        "runtime_reliability": stress or {},
    }


def write_evidence_pack(
    output_dir: Path | str,
    scripted: dict[str, Any],
    online: dict[str, Any] | None,
    search_summary: dict[str, Any] | None,
    search_trials: list[dict[str, Any]],
    stress: dict[str, Any] | None,
    online_before: dict[str, Any] | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> list[Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    summary = build_evidence_summary(
        scripted, online, search_summary, stress, online_before=online_before
    )
    json_path = root / "evidence-summary.json"
    md_path = root / "evidence-report.md"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(_render_markdown(summary), encoding="utf-8")
    pass_plot = _write_agent_pass_plot(root, scripted, online, online_before)
    convergence_plot = _write_search_convergence_plot(root, search_trials)
    paths = [json_path, md_path, pass_plot, convergence_plot]
    if before and after:
        paths.append(_write_engineering_improvement_plot(root, before, after))
    return paths


def _render_markdown(summary: dict[str, Any]) -> str:
    scripted = summary["agent_behavior"]["scripted"] or {}
    online = summary["agent_behavior"]["online"] or {}
    reliability = summary.get("runtime_reliability", {})
    search = summary.get("search_quality", {})
    lines = [
        "# Evidence Benchmark v1", "",
        "## Agent behavior", "",
        "| Mode | Tasks | Attempts | pass@1 | pass@3 | Claim boundary |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
        f"| Scripted | {scripted.get('task_count', 0)} | {scripted.get('attempt_count', 0)} | {scripted.get('pass_at_1', 0):.3f} | - | {scripted.get('claim_scope', '')} |",
    ]
    if online:
        pass_at_3 = online.get("pass_at_3")
        pass_at_3_text = f"{float(pass_at_3):.3f}" if pass_at_3 is not None else "-"
        lines.append(
            f"| DeepSeek | {online.get('task_count', 0)} | {online.get('attempt_count', 0)} | {online.get('pass_at_1', 0):.3f} | {pass_at_3_text} | {online.get('claim_scope', '')} |"
        )
    lines.extend([
        "", "## Search quality", "",
        "| Method | Seeds | Effective trials | Target hit | Best metric mean |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    for method, stats in search.get("per_method", {}).items():
        metric = str(stats.get("metric_name", "metric"))
        best = stats.get(f"best_{metric}_mean")
        best_text = f"{float(best):.6g}" if best is not None else "-"
        lines.append(
            f"| `{method}` | {stats.get('n_seeds', 0)} | "
            f"{stats.get('n_effective_trials', 0)} | "
            f"{float(stats.get('target_hit_rate_mean', 0.0)):.3f} | "
            f"{best_text} |"
        )
    lines.extend(["", "### Paired increments", ""])
    for label, result in search.get("paired_comparisons", {}).items():
        delta = next(
            (
                value for key, value in result.items()
                if key.endswith("_delta_mean") and value is not None
            ),
            result.get("nmse_delta_mean_db"),
        )
        delta_text = f"{float(delta):.6g}" if delta is not None else "N/A"
        lines.append(
            f"- `{label}`: delta `{delta_text}`, paired seeds "
            f"`{result.get('paired_seed_count', 0)}`, significant "
            f"`{bool(result.get('significant', False))}`."
        )
    lines.extend([
        "", "## Runtime reliability", "",
        f"- duplicate execution rate: `{reliability.get('duplicate_execution_rate', 'N/A')}`",
        f"- event loss rate: `{reliability.get('event_loss_rate', 'N/A')}`",
        f"- terminal consistency: `{reliability.get('terminal_consistency', 'N/A')}`",
        f"- recovery rate: `{reliability.get('recovery_rate', 'N/A')}`",
        "", "## Claim policy", "",
        "Scripted results validate deterministic harness contracts only. Online results validate LLM decisions on fixed faults. Search results alone support model-quality claims.", "",
    ])
    return "\n".join(lines)


def _plot_setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.size": 10, "axes.titlesize": 13, "axes.labelsize": 11,
        "legend.fontsize": 9, "figure.dpi": 140,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.22, "grid.linestyle": "--",
    })
    return plt


def _write_agent_pass_plot(
    root: Path,
    scripted: dict,
    online: dict | None,
    online_before: dict | None = None,
) -> Path:
    plt = _plot_setup()
    labels = ["Harness\ncontract"]
    values = [float(scripted.get("pass_at_1", 0.0)) * 100]
    colors = [COLORS["navy"]]
    if online_before:
        labels.append("DeepSeek\nbefore")
        values.append(float(online_before.get("pass_at_1", 0.0)) * 100)
        colors.append("#AAB2BD")
    if online:
        labels.append("DeepSeek\nafter pass@1")
        values.append(float(online.get("pass_at_1", 0.0)) * 100)
        colors.append(COLORS["teal"])
        if online.get("pass_at_3") is not None:
            labels.append("DeepSeek\nafter pass@3")
            values.append(float(online.get("pass_at_3", 0.0)) * 100)
            colors.append(COLORS["blue"])
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    bars = ax.bar(labels, values, color=colors, width=0.56, edgecolor="white")
    ax.bar_label(bars, fmt="%.1f%%", padding=4, fontweight="bold")
    ax.set_ylim(0, 108)
    ax.set_ylabel("Task pass@1 (%)  ↑")
    fig.suptitle("Agent behavior benchmark", x=0.13, y=0.98, ha="left", fontweight="bold", fontsize=14)
    ax.text(0, 1.01, "18 independent tasks; production ToolSpec; deterministic fault observations", transform=ax.transAxes, color=COLORS["gray"], fontsize=9)
    fig.subplots_adjust(top=0.84, bottom=0.2)
    path = root / "agent-pass-rate.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def _write_search_convergence_plot(root: Path, rows: list[dict[str, Any]]) -> Path:
    import numpy as np
    plt = _plot_setup()
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    methods = sorted({str(row.get("method")) for row in rows if row.get("method")})
    palette = [COLORS["gray"], COLORS["amber"], COLORS["blue"], COLORS["teal"], COLORS["navy"]]
    metric = next((str(row.get("metric_name")) for row in rows if row.get("metric_name")), "nmse_db")
    for method, color in zip(methods, palette):
        method_rows = [row for row in rows if row.get("method") == method and row.get(metric) is not None and not row.get("rejected") and not row.get("runtime_failed")]
        curves = []
        for seed in sorted({row.get("seed") for row in method_rows}):
            seed_rows = sorted((row for row in method_rows if row.get("seed") == seed), key=lambda row: int(row.get("trial_index", 0)))
            values = np.array([float(row[metric]) for row in seed_rows])
            if len(values):
                curves.append(np.minimum.accumulate(values))
        if not curves:
            continue
        width = min(len(curve) for curve in curves)
        matrix = np.array([curve[:width] for curve in curves])
        mean = matrix.mean(axis=0)
        x = np.arange(1, width + 1)
        ax.plot(x, mean, marker="o", linewidth=2.1, markersize=4, label=method, color=color)
        if len(matrix) > 1:
            sem = matrix.std(axis=0, ddof=1) / np.sqrt(len(matrix))
            ax.fill_between(x, mean - 1.96 * sem, mean + 1.96 * sem, color=color, alpha=0.14)
    ax.set_xlabel("Effective trial")
    ax.set_ylabel(f"Best-so-far {metric}  ↓")
    ax.set_title("Search efficiency under a fixed budget", loc="left", fontweight="bold")
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    path = root / "search-convergence.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def _write_engineering_improvement_plot(
    root: Path, before: dict[str, Any], after: dict[str, Any]
) -> Path:
    """Show recomputed before/after engineering outcomes with honest directions."""
    import numpy as np
    plt = _plot_setup()
    labels = ["Task hit", "Valid plan", "Rejected plan"]
    before_pct = np.array([
        float(before.get("target_hit_rate", 0.0)),
        float(before.get("planner_success_rate", 0.0)),
        float(before.get("rejected_rate", 0.0)),
    ]) * 100
    after_pct = np.array([
        float(after.get("target_hit_rate", 0.0)),
        float(after.get("planner_success_rate", 0.0)),
        float(after.get("rejected_rate", 0.0)),
    ]) * 100
    x = np.arange(len(labels))
    width = 0.34
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.6), gridspec_kw={"width_ratios": [2.2, 1]})
    ax = axes[0]
    old_bars = ax.bar(x - width / 2, before_pct, width, label="Before", color="#AAB2BD")
    new_bars = ax.bar(x + width / 2, after_pct, width, label="After", color=COLORS["teal"])
    ax.bar_label(old_bars, fmt="%.1f%%", padding=3, fontsize=9)
    ax.bar_label(new_bars, fmt="%.1f%%", padding=3, fontsize=9, fontweight="bold")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Rate (%)")
    ax.set_title("Agent contract and task outcomes", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    ax.text(0.97, 0.02, "Rejected plan: lower is better", transform=ax.transAxes, ha="right", color=COLORS["gray"], fontsize=8.5)

    old_nmse = float(before.get("best_nmse_db", 0.0))
    new_nmse = float(after.get("best_nmse_db", 0.0))
    nmse_bars = axes[1].bar(["Before", "After"], [old_nmse, new_nmse], color=["#AAB2BD", COLORS["blue"]], width=0.58)
    for bar, value in zip(nmse_bars, [old_nmse, new_nmse]):
        axes[1].text(
            bar.get_x() + bar.get_width() / 2,
            value + 1.6,
            f"{value:.2f} dB",
            ha="center", va="top", fontweight="bold",
        )
    axes[1].set_ylabel("Best NMSE (dB)  ↓")
    axes[1].set_title(
        f"Best verified result\n{old_nmse - new_nmse:.2f} dB improvement",
        loc="left", fontweight="bold",
    )
    axes[1].set_ylim(min(old_nmse, new_nmse) - 4, 0)
    fig.suptitle("Engineering contribution backed by archived benchmark JSON", x=0.02, ha="left", fontsize=14, fontweight="bold")
    fig.tight_layout()
    path = root / "engineering-improvement.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path
