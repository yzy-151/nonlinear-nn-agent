"""LLM-based search strategy adapters.

Wraps the ExperimentPlannerLoop into the SearchStrategy interface.
Two variants:
  - LLMDirectSearch: planner without reflection injection into next round
  - LLMProgramReflectionSearch: planner with full reflection feedback loop

Real-LLM search (used when SearchContext.llm_provider == "deepseek"):
  RealLLMSearch calls the DeepSeek chat API on every suggest() with a
  compact prompt (design space + history + schema template), parses the
  JSON reply, and retries with the guard's rejection message when the
  proposed candidate fails schema validation. llm_program_reflection
  additionally injects ReflectionPolicy facts from the previous trial.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nonlinear_agent.domains.base import DomainPlugin
from nonlinear_agent.llm import FakeLLMClient
from nonlinear_agent.loop import ExperimentPlannerLoop
from nonlinear_agent.planner import ExperimentPlanner
from nonlinear_agent.planner import _parse_json_object
from nonlinear_agent.planner_validation import validate_planned_overrides
from nonlinear_agent.reflection import ReflectionPolicy
from nonlinear_agent.search.base import SearchContext


# DeepSeek chat pricing (USD per 1M tokens) — same constants as benchmark.py
PROMPT_TOKEN_PRICE_USD = 0.27 / 1_000_000
COMPLETION_TOKEN_PRICE_USD = 1.10 / 1_000_000


_SHARED_DEEPSEEK_CLIENT: Any = None


def _load_env_local(path: Path | None = None) -> None:
    """Load .env.local into os.environ without overriding existing vars."""
    import os

    env_path = path or Path(".env.local")
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _get_shared_deepseek_client() -> Any:
    """Lazy singleton DeepSeek client shared by all RealLLMSearch instances."""
    global _SHARED_DEEPSEEK_CLIENT
    if _SHARED_DEEPSEEK_CLIENT is None:
        _load_env_local()
        from nonlinear_agent.llm import OpenAICompatibleClient

        _SHARED_DEEPSEEK_CLIENT = OpenAICompatibleClient.deepseek()
    return _SHARED_DEEPSEEK_CLIENT


class RealLLMSearch:
    """Real-API LLM search strategy (DeepSeek chat completions).

    suggest() builds a compact prompt from the domain design space and the
    recent trial history, asks the model for the next overrides object, and
    feeds schema-guard rejection messages back to the model for retry.
    Usage (prompt/completion tokens, latency, estimated cost) is written
    into the trial record in observe().
    """

    def __init__(self, method: str, context: SearchContext):
        if method not in ("llm_direct", "llm_program_reflection"):
            raise ValueError(f"Unknown real-LLM method: {method}")
        self.method = method
        self.name = method
        self._ctx = context
        self._client = _get_shared_deepseek_client()
        if getattr(self._client, "max_tokens", None) is None:
            self._client.max_tokens = 512  # 200 太小：flash 思考常超 200 导致空输出
        if getattr(self._client, "json_mode", True):
            self._client.json_mode = False  # json_object 让 flash 把 token 耗在隐藏推理上
        if getattr(self._client, "temperature", 0.2) < 0.5:
            self._client.temperature = 0.7  # 0.2 下 flash 过度思考；0.7 稳定且快
        self._reflection = (
            ReflectionPolicy() if method == "llm_program_reflection" else None
        )
        self._facts: list[dict[str, Any]] = []
        self._last_prompt_tokens = 0
        self._last_completion_tokens = 0
        self._last_latency_ms = 0.0
        self._max_retries = 3

    # ── SearchStrategy interface ────────────────────────────
    def suggest(self, history: list[dict], trial_index: int) -> dict[str, Any]:
        last_error: str | None = None
        fallback: dict[str, Any] = {}
        for attempt in range(self._max_retries + 1):
            try:
                prompt = self._build_prompt(history, retry_error=last_error)
                raw = self._call(prompt)
            except Exception as exc:  # 网络/API 错误：不中断整个协议
                last_error = f"LLM request failed: {exc}"
                if attempt == self._max_retries:
                    break
                continue
            try:
                payload = _parse_json_object(raw)
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = f"Planner response was not valid JSON: {exc}"
                if attempt == self._max_retries:
                    break
                continue

            overrides = payload.get("overrides", {})
            if not isinstance(overrides, dict):
                last_error = "overrides must be a JSON object."
                if attempt == self._max_retries:
                    break
                continue
            fallback = overrides

            try:
                return validate_planned_overrides(
                    overrides,
                    parameter_count_max=self._ctx.parameter_count_max,
                    domain=self._ctx.domain,
                )
            except ValueError as exc:
                last_error = str(exc)
                if attempt == self._max_retries:
                    break
        # 重试耗尽：返回最后一次候选，主循环会记 rejected
        return fallback

    def observe(self, candidate: dict, result: dict) -> None:
        result["candidate"] = candidate
        result["prompt_tokens"] = self._last_prompt_tokens
        result["completion_tokens"] = self._last_completion_tokens
        result["planner_latency_ms"] = self._last_latency_ms
        result["estimated_cost_usd"] = (
            self._last_prompt_tokens * PROMPT_TOKEN_PRICE_USD
            + self._last_completion_tokens * COMPLETION_TOKEN_PRICE_USD
        )
        if self._reflection is None or result.get("rejected"):
            return
        reflection = self._reflection.reflect(
            round_index=0,
            round_records=[result],
            primary_metric=self._ctx.domain.primary_metric(),
            lower_is_better=True,
        )
        self._facts = reflection.get("facts", [])

    # ── 内部：prompt 构造 ───────────────────────────────────
    def _build_prompt(
        self, history: list[dict], retry_error: str | None = None
    ) -> str:
        domain = self._ctx.domain
        metric = domain.primary_metric()
        design = domain.design_space()

        design_lines = []
        for field, choices in design.items():
            if isinstance(choices[0], int):
                lo, hi = min(choices), max(choices)
                design_lines.append(f"- {field}: integer in [{lo}, {hi}]")
            else:
                lo, hi = min(choices), max(choices)
                design_lines.append(f"- {field}: float in [{lo}, {hi}]")

        # 最近历史（含 candidate 的条目），倒序最近在前，最多 10 条
        recent = [
            {
                "candidate": row.get("candidate", {}),
                metric: row.get(metric),
                "rejected": bool(row.get("rejected")),
                "runtime_failed": bool(row.get("runtime_failed")),
            }
            for row in reversed(history[-20:])
            if isinstance(row.get("candidate"), dict)
        ][:10]

        parts = [
            (
                f"Design the next experiment to minimize {metric} on the "
                f"'{domain.name}' task (lower is better)."
            ),
            "Design space (use exactly these field names and value ranges):",
            "\n".join(design_lines),
            f"Constraints: parameter_count_max={self._ctx.parameter_count_max}",
        ]

        if self._facts:
            parts.append(
                "Reflection facts from previous trials:\n"
                + json.dumps(self._facts, ensure_ascii=False)
            )
        if recent:
            parts.append(
                "Recent trials (most recent first):\n"
                + json.dumps(recent, ensure_ascii=False)
            )

        parts.append(
            "Return JSON only with schema: "
            '{"overrides": object, "reason": str (max 20 words)}'
        )
        parts.append(
            "Fill in exactly this template (keys of 'overrides' must stay "
            "within the design space): "
            '{"overrides": {"degree": 5, "reg_strength": 0.001}, "reason": "try"}'
        )
        parts.append(
            "Only these override fields may be used: "
            f"{sorted(domain.allowed_override_fields())}. "
            "Values must match the design space types; nested objects are rejected."
        )
        if retry_error:
            parts.append(
                "Your previous candidate was rejected by the guard. "
                f"Fix it and return valid JSON only. Rejection reason: {retry_error}"
            )

        return "\n\n".join(parts)

    def _call(self, prompt: str) -> str:
        p0 = getattr(self._client, "total_prompt_tokens", 0)
        c0 = getattr(self._client, "total_completion_tokens", 0)
        t0 = time.perf_counter()
        raw = self._client.complete(prompt)
        self._last_latency_ms = (time.perf_counter() - t0) * 1000.0
        self._last_prompt_tokens = max(
            0, getattr(self._client, "total_prompt_tokens", 0) - p0
        )
        self._last_completion_tokens = max(
            0, getattr(self._client, "total_completion_tokens", 0) - c0
        )
        return raw


class LLMDirectSearch:
    """LLM planner without reflection context injected into subsequent rounds.

    The ReflectionPolicy still computes facts (for observability) but they
    are NOT passed back to the planner as context for the next round.
    """

    name = "llm_direct"

    def __init__(self, context: SearchContext, workspace: Path | str):
        self._ctx = context
        self._workspace = Path(workspace)
        self._history: list[dict] = []
        self._trial_index = 0
        self._pending_candidate: dict[str, Any] | None = None

    def suggest(
        self, history: list[dict], trial_index: int
    ) -> dict[str, Any]:
        # In the actual evaluation protocol, LLM search runs as a full
        # ExperimentPlannerLoop per seed. The suggest/observe interface is
        # used for the other strategies; for LLM we use run_llm_strategy()
        # directly. This suggest returns a placeholder.
        return {}

    def observe(self, candidate: dict, result: dict) -> None:
        pass


class LLMProgramReflectionSearch:
    """LLM planner with full reflection feedback injected into each round."""

    name = "llm_program_reflection"

    def __init__(self, context: SearchContext, workspace: Path | str):
        self._ctx = context
        self._workspace = Path(workspace)

    def suggest(
        self, history: list[dict], trial_index: int
    ) -> dict[str, Any]:
        return {}

    def observe(self, candidate: dict, result: dict) -> None:
        pass
