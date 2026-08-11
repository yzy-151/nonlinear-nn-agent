"""ModelRouter — role-based model configuration and usage accounting (v3.7.0).

Role configs (provider/model/temperature/budget) come from configuration, not
from agent code. Every call records role/provider/model/latency/token/cost;
secrets never enter usage records or traces. Fallback triggers at most once,
only on retryable error classes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class ModelRoleConfig:
    provider: str
    model: str
    temperature: float = 0.0
    token_budget: int = 0
    cost_budget: float = 0.0
    prompt_price_per_million: float = 0.27
    completion_price_per_million: float = 1.10


@dataclass(frozen=True)
class UsageRecord:
    role: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: float
    timestamp: float


ClientFactory = Callable[[str, ModelRoleConfig], Any]


class ModelRouter:
    """Routes per-role LLM calls and tracks token/cost/latency usage."""

    def __init__(
        self,
        roles: dict[str, dict[str, Any]],
        client_factory: ClientFactory | None = None,
    ):
        self._roles = {
            name: ModelRoleConfig(**config) for name, config in roles.items()
        }
        self._client_factory = client_factory
        self._clients: dict[str, Any] = {}
        self._usage: list[UsageRecord] = []
        self._cost_budget = float("inf")
        self._token_budget = float("inf")

    # ── 配置 ─────────────────────────────────────────────
    def role_config(self, role: str) -> ModelRoleConfig:
        if role not in self._roles:
            raise KeyError(f"Unknown model role: {role}")
        return self._roles[role]

    def set_budgets(
        self,
        cost_budget_usd: float | None = None,
        token_budget: int | None = None,
    ) -> None:
        if cost_budget_usd is not None:
            self._cost_budget = float(cost_budget_usd)
        if token_budget is not None:
            self._token_budget = float(token_budget)

    # ── 调用 ─────────────────────────────────────────────
    def complete(self, role: str, prompt: str) -> str:
        config = self.role_config(role)
        client = self._clients.get(role)
        if client is None:
            if self._client_factory is None:
                raise RuntimeError(
                    f"No client factory for role '{role}' and no cached client."
                )
            client = self._client_factory(role, config)
            self._clients[role] = client

        prompt_before = int(getattr(client, "total_prompt_tokens", 0))
        completion_before = int(getattr(client, "total_completion_tokens", 0))
        started = time.perf_counter()
        try:
            reply = client.complete(prompt)
        except Exception as exc:
            # fallback：最多一次，仅对可重试错误类
            from nonlinear_agent.llm import _RetryableRequestError

            if isinstance(exc, _RetryableRequestError):
                started = time.perf_counter()
                prompt_before = int(getattr(client, "total_prompt_tokens", 0))
                completion_before = int(getattr(client, "total_completion_tokens", 0))
                reply = client.complete(prompt)
            else:
                raise
        latency_ms = (time.perf_counter() - started) * 1000.0
        prompt_tokens = int(getattr(client, "total_prompt_tokens", 0)) - prompt_before
        completion_tokens = (
            int(getattr(client, "total_completion_tokens", 0)) - completion_before
        )
        self._usage.append(
            UsageRecord(
                role=role,
                provider=str(getattr(client, "provider", config.provider)),
                model=str(getattr(client, "model", config.model)),
                prompt_tokens=max(0, prompt_tokens),
                completion_tokens=max(0, completion_tokens),
                cost_usd=(
                    max(0, prompt_tokens)
                    * config.prompt_price_per_million
                    / 1_000_000
                    + max(0, completion_tokens)
                    * config.completion_price_per_million
                    / 1_000_000
                ),
                latency_ms=latency_ms,
                timestamp=time.time(),
            )
        )
        return reply

    # ── 用量 ─────────────────────────────────────────────
    def usage(self) -> list[UsageRecord]:
        return list(self._usage)

    def total_cost(self) -> float:
        return sum(record.cost_usd for record in self._usage)

    def total_tokens(self) -> int:
        return sum(
            record.prompt_tokens + record.completion_tokens
            for record in self._usage
        )

    def budget_exceeded(self) -> bool:
        return self.total_cost() > self._cost_budget or self.total_tokens() > self._token_budget
