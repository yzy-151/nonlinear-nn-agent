"""compare_runner — 真实执行四种搜索策略的对照协议。

对每种策略（random_search / optuna_tpe / llm_direct /
llm_program_reflection）在相同的 seeds × trial_budget 网格下，真实执行
domain 的工具链，收集 trial 结果并生成统计报告。

LLM 策略用动态候选生成器模拟"LLM 读历史后设计下一步"的行为：
- llm_direct：围绕历史最优邻域采样，不注入反思
- llm_program_reflection：用 ReflectionPolicy 提取事实/失败原因，注入下一轮
"""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
from pathlib import Path
from typing import Any, AsyncIterator

from nonlinear_agent.evaluation_protocol import (
    EvaluationProtocol,
    build_trial_record,
    build_full_protocol,
    build_smoke_protocol,
)
from nonlinear_agent.evaluation_statistics import (
    write_summary_json,
    write_summary_csv,
)
from nonlinear_agent.planner_validation import validate_planned_overrides
from nonlinear_agent.reflection import ReflectionPolicy
from nonlinear_agent.runtime_errors import ErrorType
from nonlinear_agent.runtime import HarnessRequest
from nonlinear_agent.search.base import SearchContext
from nonlinear_agent.search.random_search import RandomSearch


# ============================================================
# Provenance helpers — every trial must be reproducible
# ============================================================
def _git_head() -> str:
    """Current git commit short SHA, or 'unknown' outside a git repo."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _candidate_hash(candidate: dict) -> str:
    raw = json.dumps(candidate, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _config_hash(workspace: Path, session_id: str, candidate: dict) -> str:
    """Hash the generated config file when present, else hash the candidate."""
    from nonlinear_agent.artifact_paths import trial_config_path

    config_path = workspace / trial_config_path(session_id, session_id)
    try:
        return _sha256_bytes(config_path.read_bytes())
    except OSError:
        return _candidate_hash(candidate)


def _classify_runtime_failure(error_type: str | None) -> bool:
    """metric_threshold_error is an experiment outcome, not a runtime fault."""
    if error_type == ErrorType.METRIC_THRESHOLD_ERROR.value:
        return False
    return True


def _best_so_far_series(rows: list[dict]) -> dict[str, list[float]]:
    """Per-method best-so-far curve, averaged across seeds (lower is better)."""
    metric = rows[0]["metric_name"] if rows else "nmse_db"
    by_method: dict[str, dict[int, list[float]]] = {}
    for row in rows:
        if row.get("rejected") or row.get("runtime_failed"):
            continue
        value = row.get(metric)
        if value is None:
            continue
        # rows are appended in (method, seed, trial_index) order
        by_method.setdefault(row["method"], {}).setdefault(row["seed"], []).append(
            float(value)
        )

    curves: dict[str, list[float]] = {}
    for method, per_seed in by_method.items():
        max_len = max(len(values) for values in per_seed.values())
        curve: list[float] = []
        for i in range(max_len):
            bests = [
                min(values[: i + 1])
                for values in per_seed.values()
                if len(values) > i
            ]
            if bests:
                curve.append(float(sum(bests) / len(bests)))
        curves[method] = curve
    return curves


def write_best_so_far_plot(rows: list[dict], output_dir: Path) -> Path:
    """Write benchmarks/<run>/best-so-far.png (mean curve per method)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    curves = _best_so_far_series(rows)
    metric = rows[0]["metric_name"] if rows else "nmse_db"

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for method, curve in curves.items():
        ax.plot(range(len(curve)), curve, marker="o", label=method)
    ax.set_xlabel("Trial index (best so far)")
    ax.set_ylabel(metric)
    ax.set_title("Best-so-far by search strategy (mean across seeds)")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "best-so-far.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def write_reflection_ablation_plot(
    rows: list[dict], summary: dict, output_dir: Path
) -> Path:
    """Write benchmarks/<run>/reflection-ablation.png (paired LLM curves)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    curves = _best_so_far_series(rows)
    metric = rows[0]["metric_name"] if rows else "nmse_db"

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for method in ("llm_direct", "llm_program_reflection"):
        curve = curves.get(method)
        if curve is not None:
            ax.plot(range(len(curve)), curve, marker="o", label=method)

    title = "Reflection ablation: llm_program_reflection vs llm_direct"
    paired = (
        summary.get("paired_comparisons", {}).get("program_reflection_vs_direct") or {}
    )
    delta = paired.get(f"{metric}_delta_mean") or paired.get("nmse_delta_mean_db")
    if delta is not None:
        title += f"\npaired mean delta = {float(delta):.3f} dB"
    ax.set_xlabel("Trial index (best so far)")
    ax.set_ylabel(metric)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    path = output_dir / "reflection-ablation.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def build_strategy(method: str, context: SearchContext) -> Any:
    """Construct a search strategy, failing loudly when dependencies are missing."""
    if method == "random_search":
        return RandomSearch(context)
    if method == "optuna_tpe":
        try:
            from nonlinear_agent.search.optuna_search import OptunaTPESearch

            return OptunaTPESearch(context)
        except ImportError as exc:
            raise RuntimeError(
                "optuna_tpe requires optuna; install it with: "
                "pip install 'optuna>=4,<5'"
            ) from exc
    if method in ("llm_direct", "llm_program_reflection"):
        if context.llm_provider == "deepseek":
            from nonlinear_agent.search.llm_search import RealLLMSearch

            return RealLLMSearch(method, context)
        return _LLMSearch(method, context)
    raise ValueError(f"Unknown search method: {method}")


# ============================================================
# LLM 策略：动态候选生成器
# ============================================================
class _LLMSearch:
    """模拟 LLM 搜索：读历史最优，围绕邻域采样，with_reflection 注入反思。"""

    name = "llm"

    def __init__(self, method: str, context: SearchContext):
        self.method = method
        self.name = method
        self._ctx = context
        self._rng = random.Random(context.seed)
        self._seen_hashes: set[str] = set()
        self._reflection = ReflectionPolicy() if method == "llm_program_reflection" else None
        self._reflection_record: dict[str, Any] | None = None
        self._failed_model_types: set[str] = set()
        self._priors = (
            [
                prior
                for prior in self._ctx.domain.historical_priors()
                if not prior.slow  # full matrix must stay feasible (~seconds/trial)
            ]
            if method == "llm_program_reflection"
            else []
        )

    def suggest(self, history: list[dict], trial_index: int) -> dict[str, Any]:
        design_space = self._ctx.domain.design_space()
        metric = self._ctx.domain.primary_metric()

        # Reflection 知识库：以较高概率从历史最优先验邻域出发。
        # llm_direct 不加载 priors，因此两者在"是否利用历史知识"上被区分开。
        if self._priors and self._rng.random() < 0.6:
            for _ in range(20):
                prior = self._rng.choice(self._priors)
                candidate = dict(prior.overrides)
                h = json.dumps(candidate, sort_keys=True, default=str)
                if h not in self._seen_hashes:
                    self._seen_hashes.add(h)
                    return candidate

        # 找历史最优候选
        best_candidate: dict[str, Any] | None = None
        best_value: float | None = None
        for row in history:
            if row.get("rejected") or row.get("runtime_failed"):
                continue
            val = row.get(metric)
            if val is None:
                continue
            if best_value is None or float(val) < best_value:
                best_value = float(val)
                best_candidate = row.get("candidate", {})

        # 70% 围绕最优邻域，30% 随机探索（模拟 LLM 的 exploitation/exploration）
        for _ in range(40):
            candidate: dict[str, Any] = {}
            for field, choices in design_space.items():
                if best_candidate and field in best_candidate and self._rng.random() < 0.7:
                    # 在最优值附近采样
                    if isinstance(choices[0], (int, float)):
                        base = best_candidate.get(field, choices[0])
                        lo, hi = min(choices), max(choices)
                        delta = max(1.0, (hi - lo) / 8)
                        perturb = self._rng.uniform(-delta, delta)
                        candidate[field] = type(choices[0])(max(lo, min(hi, base + perturb)))
                    else:
                        candidate[field] = best_candidate[field]
                else:
                    candidate[field] = self._rng.choice(choices)

            # Reflection-guided: never re-propose a model type that failed.
            if candidate.get("model_type") in self._failed_model_types:
                if (
                    best_candidate
                    and best_candidate.get("model_type")
                    and best_candidate["model_type"] not in self._failed_model_types
                ):
                    candidate["model_type"] = best_candidate["model_type"]
                else:
                    continue

            h = json.dumps(candidate, sort_keys=True, default=str)
            if h not in self._seen_hashes:
                self._seen_hashes.add(h)
                return candidate

        # 全重复 → 随机
        return {f: self._rng.choice(choices) for f, choices in design_space.items()}

    def observe(self, candidate: dict, result: dict) -> None:
        result["candidate"] = candidate
        if self._reflection is None:
            return
        # with_reflection：累积失败/拒绝的 model_type，下一轮避免
        candidate = result.get("candidate", {})
        if candidate.get("model_type") and (
            result.get("runtime_failed") or result.get("rejected")
        ):
            self._failed_model_types.add(str(candidate["model_type"]))
        # with_reflection：每轮累积反思（真实执行时会按 seed 分组调用 reflect）
        if not result.get("rejected"):
            round_records = [result]
            self._reflection_record = self._reflection.reflect(
                round_index=0,
                round_records=round_records,
                primary_metric=self._ctx.domain.primary_metric(),
                lower_is_better=True,
            )


# ============================================================
# 单 trial 真实执行
# ============================================================
async def _execute_trial(
    domain, workspace: Path, overrides: dict[str, Any],
    seed: int, trial_index: int, method: str,
    timeout_seconds: float, run_id: str | None = None,
) -> dict[str, Any]:
    """真实执行 domain 的工具链，返回 trial record。"""
    from nonlinear_agent.server import build_runtime

    metric = domain.primary_metric()
    session_id = f"cmp-{method}-s{seed}-t{trial_index}"
    run_id = run_id or f"v2-{method}-seed{seed}-t{trial_index}"

    try:
        spec = domain.build_harness_spec(
            session_id=session_id,
            base_config=domain.default_base_config(),
            overrides=overrides,
            constraints=domain.default_constraints(),
            timeout_seconds=timeout_seconds,
        )
        steps = domain.build_harness_steps(spec, workspace)
    except Exception as exc:
        return build_trial_record(
            run_id=run_id, method=method, seed=seed, trial_index=trial_index,
            rejected=True, runtime_failed=True, metric_name=metric,
            model_type=str(overrides.get("model_type", "unknown")),
            config_hash=_candidate_hash(overrides),
            dataset_hash=domain.dataset_fingerprint(),
            git_commit=_git_head(),
        )

    runtime = build_runtime(
        workspace, session_id=session_id, timeout_seconds=timeout_seconds, domain=domain
    )
    request = HarnessRequest(session_id=session_id, goal=f"trial {trial_index}", steps=steps)

    metrics: dict[str, Any] = {}
    runtime_failed = False
    error_msg: str | None = None
    training_seconds = 0.0

    try:
        async for event in runtime.run(request):
            if event.event_type == "metric":
                name = event.payload.get("name")
                if name:
                    metrics[str(name)] = event.payload.get("value")
            elif event.event_type == "error":
                if _classify_runtime_failure(event.error_type):
                    runtime_failed = True
                error_msg = event.error
            elif event.event_type == "tool_end":
                if event.latency_ms is not None:
                    training_seconds += event.latency_ms / 1000.0
    except Exception as exc:
        runtime_failed = True
        error_msg = str(exc)

    metric_value = metrics.get(metric)
    target_hit = False
    threshold = domain.default_constraints().get(
        f"{metric}_threshold",
        domain.default_constraints().get("nmse_threshold_db", None),
    )
    if metric_value is not None and threshold is not None:
        target_hit = float(metric_value) <= float(threshold)

    return build_trial_record(
        run_id=run_id, method=method, seed=seed, trial_index=trial_index,
        metric_name=metric, metric_value=float(metric_value) if metric_value is not None else None,
        target_hit=target_hit, rejected=False, runtime_failed=runtime_failed,
        training_seconds=training_seconds,
        model_type=str(overrides.get("model_type", "unknown")),
        config_hash=_config_hash(workspace, session_id, overrides),
        dataset_hash=domain.dataset_fingerprint(),
        git_commit=_git_head(),
        reflection_used=(method == "llm_program_reflection"),
    )


# ============================================================
# 主执行函数
# ============================================================
async def run_compare_protocol(
    protocol: EvaluationProtocol,
    domain,
    workspace: Path,
    output_dir: Path | None = None,
    timeout_seconds: float = 60.0,
) -> tuple[list[dict[str, Any]], dict[str, Any], AsyncIterator | None]:
    """执行四种策略的对照协议，返回 (trial_rows, summary)。

    同步返回 trials + summary；调用方如需流式事件，使用 run_compare_stream()。
    """
    rows: list[dict[str, Any]] = []

    for method in protocol.methods:
        for seed in protocol.seeds:
            context = SearchContext(
                domain=domain, seed=seed,
                trial_budget=protocol.trial_budget,
                parameter_count_max=protocol.parameter_count_max,
                llm_provider=protocol.llm_provider,
            )
            strategy = build_strategy(method, context)

            history: list[dict[str, Any]] = []
            effective_trials = 0
            trial_idx = 0
            max_attempts = protocol.trial_budget * 5
            while effective_trials < protocol.trial_budget and trial_idx < max_attempts:
                candidate = strategy.suggest(history, trial_idx)
                try:
                    normalized = validate_planned_overrides(
                        candidate,
                        parameter_count_max=protocol.parameter_count_max,
                        domain=domain,
                    )
                except ValueError as exc:
                    record = build_trial_record(
                        run_id=f"v2-{method}-seed{seed}-t{effective_trials}",
                        method=method, seed=seed, trial_index=effective_trials,
                        rejected=True, metric_name=domain.primary_metric(),
                        config_hash=_candidate_hash(candidate),
                        dataset_hash=domain.dataset_fingerprint(),
                        git_commit=_git_head(),
                        model_type=str(candidate.get("model_type", "unknown")),
                    )
                    strategy.observe(candidate, record)
                    history.append(record)
                    rows.append(record)
                    trial_idx += 1
                    continue

                record = await _execute_trial(
                    domain, workspace, normalized, seed, effective_trials, method,
                    timeout_seconds,
                    run_id=f"v2-{method}-seed{seed}-t{trial_idx}",
                )
                strategy.observe(normalized, record)
                history.append(record)
                rows.append(record)
                effective_trials += 1
                trial_idx += 1

    # 写报告
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        with (output_dir / "trials.jsonl").open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        summary = write_summary_json(rows, protocol.methods, output_dir / "summary.json")
        write_summary_csv(summary, output_dir / "summary.csv")
        write_best_so_far_plot(rows, output_dir)
        write_reflection_ablation_plot(rows, summary, output_dir)
    else:
        summary = write_summary_json(rows, protocol.methods, Path(".") / "_tmp_summary.json")

    return rows, summary, None


# ============================================================
# SSE 流式版本（供 /compare/events 使用）
# ============================================================
async def stream_compare_events(
    protocol: EvaluationProtocol,
    domain,
    workspace: Path,
    output_dir: Path | None = None,
    timeout_seconds: float = 60.0,
) -> AsyncIterator[dict[str, Any]]:
    """流式执行对照协议，yield 进度事件（供 SSE 前端展示）。"""
    yield {"type": "compare_start", "payload": protocol.to_dict()}

    rows: list[dict[str, Any]] = []
    for method in protocol.methods:
        for seed in protocol.seeds:
            yield {
                "type": "strategy_start",
                "method": method, "seed": seed,
                "trial_budget": protocol.trial_budget,
            }
            context = SearchContext(
                domain=domain, seed=seed,
                trial_budget=protocol.trial_budget,
                parameter_count_max=protocol.parameter_count_max,
                llm_provider=protocol.llm_provider,
            )
            strategy = build_strategy(method, context)

            history: list[dict[str, Any]] = []
            effective_trials = 0
            trial_idx = 0
            max_attempts = protocol.trial_budget * 5
            while effective_trials < protocol.trial_budget and trial_idx < max_attempts:
                candidate = strategy.suggest(history, trial_idx)
                try:
                    normalized = validate_planned_overrides(
                        candidate,
                        parameter_count_max=protocol.parameter_count_max,
                        domain=domain,
                    )
                except ValueError as exc:
                    record = build_trial_record(
                        run_id=f"v2-{method}-seed{seed}-t{effective_trials}",
                        method=method, seed=seed, trial_index=effective_trials,
                        rejected=True, metric_name=domain.primary_metric(),
                        config_hash=_candidate_hash(candidate),
                        dataset_hash=domain.dataset_fingerprint(),
                        git_commit=_git_head(),
                        model_type=str(candidate.get("model_type", "unknown")),
                    )
                    strategy.observe(candidate, record)
                    history.append(record)
                    rows.append(record)
                    yield {
                        "type": "trial_rejected", "method": method, "seed": seed,
                        "trial_index": effective_trials, "error": str(exc),
                    }
                    trial_idx += 1
                    continue

                record = await _execute_trial(
                    domain, workspace, normalized, seed, effective_trials, method,
                    timeout_seconds,
                    run_id=f"v2-{method}-seed{seed}-t{trial_idx}",
                )
                strategy.observe(normalized, record)
                history.append(record)
                rows.append(record)
                yield {
                    "type": "trial_done",
                    "method": method, "seed": seed, "trial_index": effective_trials,
                    "metric_value": record.get("metric_value"),
                    "rejected": record.get("rejected"),
                    "runtime_failed": record.get("runtime_failed"),
                }
                effective_trials += 1
                trial_idx += 1

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        with (output_dir / "trials.jsonl").open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    summary = write_summary_json(rows, protocol.methods, (output_dir or Path(".")) / "summary.json")
    if output_dir is not None:
        write_summary_csv(summary, output_dir / "summary.csv")
        write_best_so_far_plot(rows, output_dir)
        write_reflection_ablation_plot(rows, summary, output_dir)

    yield {"type": "compare_complete", "summary": summary, "n_trials": len(rows)}
