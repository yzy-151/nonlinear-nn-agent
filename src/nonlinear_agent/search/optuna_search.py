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


def _is_consecutive_ints(values: list[int]) -> bool:
    """True when values are exactly a contiguous integer range."""
    return len(values) > 1 and values == list(range(values[0], values[-1] + 1))


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
            # design_space 的列表语义是"允许的离散值"，必须按离散枚举采样：
            # 把 float/int 列表当连续区间（suggest_float/suggest_int）会采样到
            # 合法集合之外的值，导致 Optuna 永远无法命中真实最优离散点。
            if isinstance(sample, bool):
                candidate[field] = trial.suggest_categorical(field, list(choices))
            elif isinstance(sample, str):
                candidate[field] = trial.suggest_categorical(
                    field, [str(c) for c in choices]
                )
            elif isinstance(sample, int):
                ints = sorted(
                    {int(c) for c in choices if isinstance(c, int) and not isinstance(c, bool)}
                )
                if _is_consecutive_ints(ints):
                    # 连续整数区间（如 degree 1..5）保留有序数值建模
                    candidate[field] = trial.suggest_int(field, ints[0], ints[-1])
                else:
                    candidate[field] = trial.suggest_categorical(field, ints)
            elif isinstance(sample, (int, float)):
                nums = [
                    float(c)
                    for c in choices
                    if isinstance(c, (int, float)) and not isinstance(c, bool)
                ]
                candidate[field] = trial.suggest_categorical(field, nums)
            else:
                candidate[field] = trial.suggest_categorical(
                    field, [str(c) for c in choices]
                )

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
