"""RegisterConfigDomain — 寄存器表单配置实验领域。

可寻优参数：MU 值、优化器（adam / sgd）、数据选择（.mat 文件）、LUT 选择。
通过配置寄存器参数（收敛步长 / 优化器 / 数据 / 查找表）评估对消/拟合性能，
主指标为收敛后的误差 final_mse_db（越低越好）。
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

import numpy as np

from nonlinear_agent.tools import ToolRegistry, ToolSpec


def _list_mat_files(workspace: Path) -> list[str]:
    """扫描 data/ 与 examples/*/data/ 下的 .mat 文件（相对路径）。"""
    root = Path(workspace)
    found: list[str] = []
    for base in (root / "data", root / "examples"):
        if base.is_dir():
            for p in sorted(base.rglob("*.mat")):
                found.append(str(p.relative_to(root)).replace("\\", "/"))
    return found


def _load_signal(workspace: Path, data_file: str):
    """从 .mat 加载信号；失败则返回确定性模拟信号。"""
    path = Path(workspace) / data_file
    if path.is_file():
        try:
            import scipy.io as sio

            mat = sio.loadmat(path)
            x = mat.get("x")
            if x is not None:
                return np.asarray(x, dtype=float).ravel()
            tx = mat.get("tx")
            if tx is not None:
                return np.asarray(tx, dtype=float).ravel()
        except Exception:
            pass
    rng = np.random.default_rng(0)
    return rng.standard_normal(8192)


def _run_register_candidate(
    workspace: Path,
    mu: float = 0.01,
    optimizer: str = "adam",
    data_choice: str = "auto",
    lut_choice: str = "lut16",
    data_file: str | None = None,
    **_kw: Any,
) -> dict[str, Any]:
    """按寄存器配置做简单迭代拟合：收敛误差作为主指标。"""
    signal = _load_signal(workspace, data_file or data_choice)
    # 归一化目标：用非线性系统输出作为拟合目标
    target = signal + 0.1 * signal**3

    # LUT 决定量化位阶（越深越准）
    lut_bits = {"lut8": 3, "lut16": 4, "lut32": 5, "lut64": 6}.get(
        lut_choice, 4
    )
    # MU 决定收敛步长；optimizer 影响收敛曲线
    steps = 200
    est = np.zeros_like(target)
    grad = target  # 简化：直接用目标做梯度方向
    for _ in range(steps):
        step = mu * np.sign(grad) if optimizer == "sgd" else mu * grad
        est = est + step
        # 量化（模拟 LUT 精度损失）
        scale = 2**lut_bits
        est_q = np.round(est * scale) / scale
        est = est - 0.1 * (est - est_q)  # 轻微误差反馈
    mse = float(np.mean((est - target) ** 2))
    final_mse_db = float(10 * np.log10(mse + 1e-12))
    return {
        "final_mse_db": final_mse_db,
        "mu": float(mu),
        "optimizer": optimizer,
        "lut_choice": lut_choice,
        "data_choice": str(data_choice),
        "converged_steps": steps,
        "metrics": {"final_mse_db": final_mse_db},
    }


class RegisterConfigDomain:
    """寄存器表单配置领域：MU / 优化器 / 数据 / LUT 可寻优。"""

    name = "register-config"

    def planner_instructions(self) -> str:
        return (
            "Design register-config experiments: choose mu (step size), "
            "optimizer (adam/sgd), data_choice (.mat dataset), and lut_choice "
            "(LUT bit depth). Metric final_mse_db (lower is better).\n"
        )

    def design_space(self) -> dict[str, list[object]]:
        return {
            "mu": [0.001, 0.005, 0.01, 0.05, 0.1],
            "optimizer": ["adam", "sgd"],
            "data_choice": ["auto", "Simulation_MPDPD_Data.mat"],
            "lut_choice": ["lut8", "lut16", "lut32", "lut64"],
        }

    def planner_allowed_tools(self) -> list[str]:
        return ["run_register_candidate"]

    def validate_candidate(
        self, overrides: dict[str, object], parameter_count_max: int | None = None
    ) -> list[str]:
        errors: list[str] = []
        if "mu" in overrides:
            mu = overrides["mu"]
            if not isinstance(mu, (int, float)) or isinstance(mu, bool) or mu <= 0:
                errors.append("mu must be a positive number.")
        if "optimizer" in overrides and overrides["optimizer"] not in ("adam", "sgd"):
            errors.append("optimizer must be adam or sgd.")
        if "lut_choice" in overrides and overrides["lut_choice"] not in (
            "lut8", "lut16", "lut32", "lut64",
        ):
            errors.append("lut_choice must be lut8/lut16/lut32/lut64.")
        return errors

    def allowed_override_fields(self) -> set[str]:
        return {
            "mu", "optimizer", "data_choice", "lut_choice",
            "data_file", "output_dir",
        }

    def build_tool_registry(
        self, workspace: Path, default_timeout_seconds: float = 300.0
    ) -> ToolRegistry:
        registry = ToolRegistry(default_timeout_seconds=default_timeout_seconds)
        registry.register(
            "run_register_candidate",
            partial(_run_register_candidate, Path(workspace)),
            spec=ToolSpec(
                name="run_register_candidate",
                description="Run one register-config candidate and return final_mse_db.",
                input_schema={"type": "object", "required": ["mu", "optimizer"]},
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

        return [ToolCall(name="run_register_candidate", args=dict(spec.overrides))]

    def primary_metric(self) -> str:
        return "final_mse_db"

    def is_better(self, candidate: dict, incumbent: dict) -> bool:
        c = float(candidate.get("final_mse_db", float("inf")))
        i = float(incumbent.get("final_mse_db", float("inf")))
        return c < i

    def display_metric_names(self) -> set[str]:
        return {
            "final_mse_db", "mu", "optimizer", "lut_choice",
            "data_choice", "converged_steps",
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
        return {"parameter_count_max": 1, "metric": "final_mse_db"}

    def dataset_fingerprint(self) -> str:
        return "unknown"

    def historical_priors(self) -> list[Any]:
        return []
