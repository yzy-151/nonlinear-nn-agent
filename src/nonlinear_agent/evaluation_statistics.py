"""Statistical evaluation of search strategy comparison results.

Provides:
- Bootstrap confidence intervals (fixed seed 20260802, n=2000)
- Paired method delta (per-seed pairing)
- Per-method aggregate statistics
- Summary report generation (JSON, CSV)

All conclusions must be recomputable from the raw trials.jsonl file.
No hardcoded numbers — every claim must derive from the data.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np


BOOTSTRAP_SEED = 20260802
BOOTSTRAP_SAMPLES = 2000
CONFIDENCE_LEVEL = 0.95


def bootstrap_confidence_interval(
    samples: list[float],
    confidence: float = CONFIDENCE_LEVEL,
    n_bootstrap: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """Compute percentile bootstrap CI for the mean.

    Returns (mean, lower_bound, upper_bound).
    """
    if not samples:
        return (0.0, 0.0, 0.0)
    rng = np.random.default_rng(seed)
    arr = np.array(samples, dtype=np.float64)
    n = len(arr)
    means = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        means.append(float(np.mean(arr[idx])))
    means_arr = np.array(means)
    alpha = (1.0 - confidence) / 2.0
    low = float(np.percentile(means_arr, 100.0 * alpha))
    high = float(np.percentile(means_arr, 100.0 * (1.0 - alpha)))
    mean_val = float(np.mean(arr))
    return (mean_val, low, high)


def paired_method_delta(
    trial_rows: list[dict[str, Any]],
    method_a: str,
    method_b: str,
    metric: str = "nmse_db",
    lower_is_better: bool = True,
) -> dict[str, Any]:
    """Compute paired per-seed delta between two methods.

    For each seed that has both methods, compute delta = best_A - best_B.
    Then bootstrap the paired deltas across seeds.

    Returns a dict with mean, median, std, 95% CI, and per-seed deltas.
    Keys use the dynamic metric name (e.g. nmse_delta_* or val_mse_delta_*).
    """
    prefix = f"{metric}_delta"
    seed_best: dict[int, dict[str, float]] = {}
    for row in trial_rows:
        seed = row.get("seed")
        method = row.get("method")
        if seed is None or method is None:
            continue
        val = row.get(metric)
        if val is None or row.get("rejected") or row.get("runtime_failed"):
            continue
        val = float(val)
        if seed not in seed_best:
            seed_best[seed] = {}
        if method not in seed_best[seed]:
            seed_best[seed][method] = val
        else:
            if lower_is_better:
                seed_best[seed][method] = min(seed_best[seed][method], val)
            else:
                seed_best[seed][method] = max(seed_best[seed][method], val)

    deltas: list[float] = []
    per_seed: dict[int, float] = {}
    for seed in sorted(seed_best):
        if method_a in seed_best[seed] and method_b in seed_best[seed]:
            delta = seed_best[seed][method_a] - seed_best[seed][method_b]
            deltas.append(delta)
            per_seed[seed] = delta

    if not deltas:
        return {
            "paired_seed_count": 0,
            f"{prefix}_mean": None,
            "message": "No seeds with both methods found.",
        }

    mean_val, ci_low, ci_high = bootstrap_confidence_interval(deltas)
    arr = np.array(deltas)

    result = {
        "paired_seed_count": len(deltas),
        f"{prefix}_mean": float(np.mean(arr)),
        f"{prefix}_median": float(np.median(arr)),
        f"{prefix}_std": float(np.std(arr, ddof=1)) if len(deltas) > 1 else 0.0,
        f"{prefix}_ci_95_low": ci_low,
        f"{prefix}_ci_95_high": ci_high,
        "per_seed_deltas": per_seed,
        "significant": ci_low > 0 or ci_high < 0,  # CI does not cross zero
    }
    # Backward-compat aliases for the historical nmse_delta_mean_db key
    if metric == "nmse_db":
        result["nmse_delta_mean_db"] = result["nmse_db_delta_mean"]
        result["nmse_delta_median_db"] = result["nmse_db_delta_median"]
        result["nmse_delta_std_db"] = result["nmse_db_delta_std"]
        result["nmse_delta_ci_95_low"] = result["nmse_db_delta_ci_95_low"]
        result["nmse_delta_ci_95_high"] = result["nmse_db_delta_ci_95_high"]
    return result


def compute_method_statistics(
    trial_rows: list[dict[str, Any]],
    method: str,
    metric: str = "nmse_db",
    lower_is_better: bool = True,
) -> dict[str, Any]:
    """Compute per-method aggregate statistics across all seeds.

    Returns: best metric stats (dynamic key), target hit rate, rejected rate,
    failure rate. All stats are reported as mean +/- 95% CI computed across seeds.
    """
    method_rows = [r for r in trial_rows if r.get("method") == method]
    if not method_rows:
        return {"method": method, "n_trials": 0}

    seeds = sorted(set(r["seed"] for r in method_rows))

    per_seed_best: list[float] = []
    per_seed_hit_rate: list[float] = []
    per_seed_rejected_rate: list[float] = []
    per_seed_failure_rate: list[float] = []

    for seed in seeds:
        seed_rows = [r for r in method_rows if r["seed"] == seed]
        effective = [r for r in seed_rows if not r.get("rejected")]
        failed = [r for r in seed_rows if r.get("runtime_failed")]

        metric_vals = [float(r[metric]) for r in effective if metric in r and not r.get("runtime_failed")]
        if metric_vals:
            if lower_is_better:
                per_seed_best.append(min(metric_vals))
            else:
                per_seed_best.append(max(metric_vals))

        if effective:
            hit_count = sum(1 for r in effective if r.get("target_hit"))
            per_seed_hit_rate.append(hit_count / len(effective))

        if seed_rows:
            rejected_count = sum(1 for r in seed_rows if r.get("rejected"))
            per_seed_rejected_rate.append(rejected_count / len(seed_rows))

        if effective:
            per_seed_failure_rate.append(len(failed) / len(effective))

    stats: dict[str, Any] = {
        "method": method,
        "metric_name": metric,
        "n_seeds": len(seeds),
        "n_total_trials": len(method_rows),
        "n_effective_trials": sum(1 for r in method_rows if not r.get("rejected")),
    }

    best_prefix = f"best_{metric}"
    if per_seed_best:
        m, lo, hi = bootstrap_confidence_interval(per_seed_best)
        stats[f"{best_prefix}_mean"] = m
        stats[f"{best_prefix}_ci_95_low"] = lo
        stats[f"{best_prefix}_ci_95_high"] = hi
        stats[f"{best_prefix}_median"] = float(np.median(per_seed_best))
        stats[f"{best_prefix}_std"] = float(np.std(per_seed_best, ddof=1)) if len(per_seed_best) > 1 else 0.0

    if per_seed_hit_rate:
        m, lo, hi = bootstrap_confidence_interval(per_seed_hit_rate)
        stats["target_hit_rate_mean"] = m
        stats["target_hit_rate_ci_95_low"] = lo
        stats["target_hit_rate_ci_95_high"] = hi

    if per_seed_rejected_rate:
        m, lo, hi = bootstrap_confidence_interval(per_seed_rejected_rate)
        stats["rejected_rate_mean"] = m
        stats["rejected_rate_ci_95_low"] = lo
        stats["rejected_rate_ci_95_high"] = hi

    if per_seed_failure_rate:
        m, lo, hi = bootstrap_confidence_interval(per_seed_failure_rate)
        stats["runtime_failure_rate_mean"] = m
        stats["runtime_failure_rate_ci_95_low"] = lo
        stats["runtime_failure_rate_ci_95_high"] = hi

    return stats


def write_summary_json(
    trial_rows: list[dict[str, Any]],
    methods: list[str],
    output_path: Path,
) -> dict[str, Any]:
    """Write full summary.json with per-method stats and paired comparisons."""
    # Detect primary metric from first non-rejected row
    metric = "nmse_db"
    lower_is_better = True
    for row in trial_rows:
        if row.get("metric_name"):
            metric = row["metric_name"]
            break

    per_method = {}
    for method in methods:
        per_method[method] = compute_method_statistics(
            trial_rows, method, metric=metric, lower_is_better=lower_is_better
        )

    paired: dict[str, Any] = {}
    if "llm_program_reflection" in methods and "llm_direct" in methods:
        paired["program_reflection_vs_direct"] = paired_method_delta(
            trial_rows, "llm_program_reflection", "llm_direct",
            metric=metric, lower_is_better=lower_is_better,
        )

    summary = {
        "protocol_version": "1.9.0",
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "confidence_level": CONFIDENCE_LEVEL,
        "per_method": per_method,
        "paired_comparisons": paired,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def write_summary_csv(
    summary: dict[str, Any],
    output_path: Path,
) -> None:
    """Write a machine-readable CSV summary."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Determine metric name from first method stats
    metric = "nmse_db"
    for stats in summary.get("per_method", {}).values():
        if stats.get("metric_name"):
            metric = stats["metric_name"]
            break
    best_key = f"best_{metric}_mean"
    best_median_key = f"best_{metric}_median"

    lines = [
        "method,n_seeds,n_total_trials,n_effective_trials,"
        f"best_{metric}_mean,best_{metric}_median,"
        "target_hit_rate_mean,rejected_rate_mean,runtime_failure_rate_mean"
    ]
    for method_name, stats in summary.get("per_method", {}).items():
        lines.append(
            f"{method_name},"
            f"{stats.get('n_seeds', '')},"
            f"{stats.get('n_total_trials', '')},"
            f"{stats.get('n_effective_trials', '')},"
            f"{stats.get(best_key, '')},"
            f"{stats.get(best_median_key, '')},"
            f"{stats.get('target_hit_rate_mean', '')},"
            f"{stats.get('rejected_rate_mean', '')},"
            f"{stats.get('runtime_failure_rate_mean', '')}"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
