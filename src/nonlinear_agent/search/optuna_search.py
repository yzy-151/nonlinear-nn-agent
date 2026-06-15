"""Optuna TPE search strategy adapter.

Uses Optuna's Tree-structured Parzen Estimator (TPESampler) for
Bayesian hyperparameter optimization. The sampler only sees metric
values and candidate parameters — it NEVER bypasses the ToolRegistry
to execute training directly.
"""

from __future__ import annotations

from typing import Any

try:
    import optuna
except ImportError:
    optuna = None  # type: ignore

from nonlinear_agent.search.base import SearchContext


class OptunaTPESearch:
    """Optuna TPE-backed search using the same trial budget as other strategies."""

    name = "optuna_tpe"

    def __init__(self, context: SearchContext):
        if optuna is None:
            raise ImportError(
                "optuna is required for OptunaTPESearch. "
                "Install it with: pip install optuna"
            )
        self._ctx = context
        self._sampler = optuna.samplers.TPESampler(seed=context.seed)
        self._study = optuna.create_study(
            sampler=self._sampler,
            direction="minimize",
        )
        self._trial_counter = 0

    def suggest(
        self, history: list[dict], trial_index: int
    ) -> dict[str, Any]:
        design_space = self._ctx.domain.design_space()
        trial = self._study.ask()

        candidate: dict[str, Any] = {}
        for field, choices in design_space.items():
            if not choices:
                continue
            sample = choices[0]
            if isinstance(sample, int):
                ints = [c for c in choices if isinstance(c, int)]
                lo, hi = min(ints), max(ints)
                candidate[field] = trial.suggest_int(field, lo, hi)
            elif isinstance(sample, float):
                floats = [c for c in choices if isinstance(c, (int, float))]
                lo, hi = min(floats), max(floats)
                candidate[field] = trial.suggest_float(field, lo, hi)
            elif isinstance(sample, str):
                strs = [str(c) for c in choices]
                candidate[field] = trial.suggest_categorical(field, strs)

        self._trial_counter += 1
        return candidate

    def observe(self, candidate: dict, result: dict) -> None:
        metric_name = self._ctx.domain.primary_metric()
        value = result.get(metric_name, result.get("metrics", {}).get(metric_name))
        if value is not None:
            try:
                trial = self._study.trials[self._trial_counter - 1]
                self._study.tell(trial, float(value))
            except Exception:
                pass  # optuna sometimes fails on tell; non-critical for search
