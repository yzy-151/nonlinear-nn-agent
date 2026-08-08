"""PIMCancellationDomain — 三阶 PIM 对消实验领域。

输入：tx (32, datalen) 与 rx (32, datalen)，让模型从 tx 拟合/对消 rx。
主指标：残余 res_db（越低越好）。
中间变量：参数量、每通道最大功率、参数分布、激活参数量。

可寻优参数与非线性建模 domain 一致（design_space 白名单驱动）。
数据来源：选中的 .mat 文件（优先 tx/rx 字段，其次 x/d 字段），无则生成模拟数据。
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

import numpy as np

from nonlinear_agent.tools import ToolRegistry, ToolSpec


# ── 数据加载 ────────────────────────────────────────────────
def _load_tx_rx(workspace: Path, data_file: str | None = None):
    """从 .mat 加载 tx/rx；无匹配字段则生成模拟 32 通道三阶 PIM 数据。"""
    if data_file:
        path = Path(workspace) / data_file
        if path.is_file():
            try:
                import scipy.io as sio

                mat = sio.loadmat(path)
                tx = mat.get("tx")
                rx = mat.get("rx")
                if tx is not None and rx is not None:
                    return (
                        np.asarray(tx, dtype=float),
                        np.asarray(rx, dtype=float),
                    )
                x = mat.get("x")
                d = mat.get("d")
                if x is not None and d is not None:
                    x = np.asarray(x, dtype=float).ravel()
                    d = np.asarray(d, dtype=float).ravel()
                    n = len(x)
                    datalen = n // 32
                    x = x[: 32 * datalen].reshape(32, datalen)
                    d = d[: 32 * datalen].reshape(32, datalen)
                    return x, d
            except Exception:
                pass
    return _synthetic_pim()


def _synthetic_pim(n_ch: int = 32, datalen: int = 4096):
    """确定性模拟：三阶 PIM（tx + 立方非线性 + 通道串扰）→ rx。"""
    rng = np.random.default_rng(42)
    tx = rng.standard_normal((n_ch, datalen)) * 0.5
    rx = 0.8 * tx + 0.15 * tx**3 + 0.05 * np.roll(tx, 1, axis=0)
    return tx, rx


def _fit_and_cancel(
    tx: np.ndarray,
    rx: np.ndarray,
    model_type: str = "poly3",
    memory_depth: int = 0,
    reg: float = 1e-3,
    normalize_power: bool = True,
    **_kw: Any,
) -> dict[str, Any]:
    """最小二乘拟合 tx→rx（含立方项与延迟项），返回残余与诊断。"""
    n_ch, _ = tx.shape
    if normalize_power:
        power = np.mean(tx**2, axis=1, keepdims=True)
        tx_n = tx / np.sqrt(power + 1e-12)
    else:
        tx_n = tx

    features = [tx_n, tx_n**3]
    if model_type in ("poly5",):
        features.append(tx_n**5)
    if model_type == "linear":
        features = [tx_n]
    for m in range(1, memory_depth + 1):
        features.append(np.roll(tx_n, m, axis=1))
        features.append(np.roll(tx_n**3, m, axis=1))
    X = np.stack(features, axis=1)  # (n_ch, n_feat, datalen)

    coeffs = []
    for c in range(n_ch):
        xc = X[c].T  # (datalen, n_feat)
        a = xc.T @ xc + reg * np.eye(xc.shape[1])
        coeffs.append(np.linalg.solve(a, xc.T @ rx[c]))
    coeffs = np.array(coeffs)  # (n_ch, n_feat)
    pred = np.sum(coeffs[:, :, None] * X, axis=1)

    res = rx - pred
    res_db = float(10 * np.log10(np.mean(res**2) / (np.mean(rx**2) + 1e-12)))
    per_ch_power_db = 10 * np.log10(np.mean(rx**2, axis=1) + 1e-12)
    return {
        "res_db": res_db,
        "params": int(coeffs.size),
        "max_power_db": float(np.max(per_ch_power_db)),
        "param_spread": float(np.std(coeffs)),
        "activation_params": 0,
    }


def _run_pim_candidate(workspace: Path, **overrides: Any) -> dict[str, Any]:
    """注册到 ToolRegistry 的候选执行函数。"""
    tx, rx = _load_tx_rx(workspace, overrides.pop("data_file", None))
    metrics = _fit_and_cancel(tx, rx, **overrides)
    metrics["metrics"] = dict(metrics)
    return metrics


# ── DomainPlugin ─────────────────────────────────────────────
class PIMCancellationDomain:
    """三阶 PIM 对消领域：tx(32×L) 拟合 rx(32×L)，残余 res_db 为主指标。"""

    name = "pim-cancellation"

    def planner_instructions(self) -> str:
        return (
            "Design 3rd-order PIM cancellation experiments: fit tx (32 channels) "
            "to rx across the data. Model types: linear / poly3 / poly5. "
            "memory_depth adds delayed tx/tx^3 features. reg is ridge strength, "
            "normalize_power per-channel power normalization. Metric res_db "
            "(lower is better); also monitor params / max_power_db / "
            "param_spread.\n"
        )

    def design_space(self) -> dict[str, list[object]]:
        return {
            "model_type": ["linear", "poly3", "poly5"],
            "memory_depth": [0, 1, 2, 4],
            "reg": [1e-5, 1e-4, 1e-3, 1e-2, 0.1],
            "normalize_power": [True, False],
        }

    def planner_allowed_tools(self) -> list[str]:
        return ["run_pim_candidate"]

    def validate_candidate(
        self, overrides: dict[str, object], parameter_count_max: int | None = None
    ) -> list[str]:
        errors: list[str] = []
        model_type = str(overrides.get("model_type", "poly3"))
        allowed_models = {str(m) for m in self.design_space()["model_type"]}
        if model_type not in allowed_models:
            errors.append(f"model_type must be one of {sorted(allowed_models)}.")
        if "memory_depth" in overrides:
            md = overrides["memory_depth"]
            if not isinstance(md, int) or isinstance(md, bool) or md < 0 or md > 8:
                errors.append("memory_depth must be an integer in [0, 8].")
        if "reg" in overrides:
            reg = overrides["reg"]
            if not isinstance(reg, (int, float)) or isinstance(reg, bool) or reg < 0:
                errors.append("reg must be a non-negative number.")
        if "normalize_power" in overrides and not isinstance(
            overrides["normalize_power"], bool
        ):
            errors.append("normalize_power must be a boolean.")
        return errors

    def allowed_override_fields(self) -> set[str]:
        return {
            "model_type", "memory_depth", "reg", "normalize_power",
            "data_file", "output_dir",
        }

    def build_tool_registry(
        self, workspace: Path, default_timeout_seconds: float = 300.0
    ) -> ToolRegistry:
        registry = ToolRegistry(default_timeout_seconds=default_timeout_seconds)
        registry.register(
            "run_pim_candidate",
            partial(_run_pim_candidate, Path(workspace)),
            spec=ToolSpec(
                name="run_pim_candidate",
                description="Run one PIM cancellation candidate and return res_db and diagnostics.",
                input_schema={"type": "object", "required": ["model_type"]},
                category="experiment",
                error_policy="return_error",
            ),
        )
        return registry

    def build_harness_spec(
        self, session_id: str, base_config: str, overrides: dict[str, Any],
        constraints: dict[str, Any], timeout_seconds: float,
    ) -> Any:
        from nonlinear_agent.domains.simple import _SimpleSpec

        overrides = dict(overrides)
        if constraints.get("data_file"):
            overrides.setdefault("data_file", constraints["data_file"])
        return _SimpleSpec(
            session_id=session_id,
            overrides=overrides,
            timeout_seconds=timeout_seconds,
        )

    def build_harness_steps(self, spec: Any, workspace: Path) -> list[Any]:
        from nonlinear_agent.tools import ToolCall

        return [ToolCall(name="run_pim_candidate", args=dict(spec.overrides))]

    def primary_metric(self) -> str:
        return "res_db"

    def is_better(self, candidate: dict, incumbent: dict) -> bool:
        c = float(candidate.get("res_db", float("inf")))
        i = float(incumbent.get("res_db", float("inf")))
        return c < i

    def display_metric_names(self) -> set[str]:
        return {
            "res_db", "params", "max_power_db", "param_spread",
            "activation_params",
        }

    def display_metric_unit(self) -> str:
        return "dB"

    def display_metric_lower_is_better(self) -> bool:
        return True

    def artifact_preview_patterns(self) -> list[str]:
        return []

    def default_base_config(self) -> str:
        return ""

    def default_constraints(self) -> dict:
        return {"parameter_count_max": 100000, "metric": "res_db"}

    def dataset_fingerprint(self) -> str:
        return "unknown"

    def historical_priors(self) -> list[Any]:
        return []
