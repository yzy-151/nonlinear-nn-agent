"""v3.8.0 E2E: 3 model families from IdeaPlanSpec to training + verification.

Real nonlinear-modeling training with tiny budgets (epochs<=2). Verifies the
full chain: PlanGate -> PlanHandoff -> ExecutionAgent(tool registry only) ->
metrics + artifact verification.
"""

from __future__ import annotations

import asyncio
import math
import shutil
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODEL_FAMILIES = [
    {"model_type": "complex_lstsq", "memory_depth": 8, "epochs": 0},
    {"model_type": "tiny_mlp", "memory_depth": 8, "epochs": 1, "hidden_units": 16},
    {"model_type": "spline_mlp", "memory_depth": 8, "epochs": 1, "hidden_units": 16},
]


def _plan_for(family: dict, experiment_id: str) -> dict:
    return {
        "plan_id": f"plan-{family['model_type']}",
        "hypotheses": [
            {
                "hypothesis": f"{family['model_type']} reaches valid NMSE",
                "rationale": "model family E2E check",
                "citation": "docs/experiments/nonlinear-search-ablation-v1.md",
            }
        ],
        "candidate_experiments": [
            {
                "model_type": family["model_type"],
                "memory_depth": family["memory_depth"],
                "epochs": family["epochs"],
                "hidden_units": family.get("hidden_units", 64),
                "params_estimate": 500,
                "budget": {"parameter_count_max": 20000, "epochs_max": 2},
                "stop_condition": "nmse finite and artifacts exist",
                "rationale": "E2E family verification",
                "citation": "docs/experiments/nonlinear-search-ablation-v1.md",
                "output_dir": experiment_id,
            }
        ],
        "experiment_dag": {"nodes": ["exp_001"], "edges": []},
        "expected_information_gain": 0.5,
        "risk": "low",
        "fallback": [],
        "required_code_changes": [],
        "no_code_change_candidates": [family["model_type"]],
    }


class TestE2EModelFamily(unittest.TestCase):
    def _run_family(self, family: dict) -> dict:
        from nonlinear_agent.coding_agent import GateResult  # noqa: F401
        from nonlinear_agent.execution_agent import ExecutionAgent
        from nonlinear_agent.plan_gate import PlanGate
        from nonlinear_agent.plan_handoff import PlanHandoff
        from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain

        experiment_id = f"e2e-{family['model_type']}-001"
        plan = _plan_for(family, experiment_id)
        gate_errors = PlanGate().validate(plan, parameter_count_max=20000)
        self.assertEqual(gate_errors, [])
        step = PlanHandoff().to_execution(plan)[0]

        domain = NonlinearModelingDomain()
        registry = domain.build_tool_registry(PROJECT_ROOT, default_timeout_seconds=180.0)
        agent = ExecutionAgent(registry)

        config_result = asyncio.run(
            agent.execute(
                "generate_config",
                {
                    "base_config_path": domain.default_base_config(),
                    "experiment_id": experiment_id,
                    "overrides": dict(step.overrides),
                },
            )
        )
        self.assertEqual(config_result.status, "completed", config_result.error)
        config_path = config_result.output.get("config_path")
        self.assertTrue(config_path, "generate_config must return config_path")

        training_result = asyncio.run(
            agent.execute(
                "run_training",
                {"config_path": config_path, "timeout_seconds": 180.0},
            )
        )
        self.assertEqual(training_result.status, "completed", training_result.error)
        nmse = training_result.metrics.get("nmse_db")
        self.assertIsNotNone(nmse, "training must return nmse_db")
        self.assertTrue(math.isfinite(float(nmse)), f"nmse must be finite: {nmse}")

        verify_result = asyncio.run(
            agent.execute(
                "verify_artifacts",
                {
                    # 训练产物实际目录（output_dir 未被 normalize 为 reports/）
                    "output_dir": str(
                        Path(training_result.artifacts[0]).parent
                    ),
                    # E2E 验证链路与产物，不要求 1-epoch 训练达标
                    "nmse_threshold_db": 100.0,
                },
            )
        )
        self.assertEqual(verify_result.status, "completed", verify_result.error)
        self.assertEqual(agent.audit_shell_calls(), 0)
        return {"family": family["model_type"], "nmse": float(nmse)}

    def test_three_model_families_e2e(self):
        results = []
        self._cleanup()
        self.addCleanup(self._cleanup)
        for family in MODEL_FAMILIES:
            results.append(self._run_family(family))
        self.assertEqual(len(results), 3)
        families = {r["family"] for r in results}
        self.assertEqual(
            families, {"complex_lstsq", "tiny_mlp", "spline_mlp"}
        )
        # 1-epoch 训练可能欠拟合（NMSE 为正），E2E 只要求链路完整 + 指标有限
        for r in results:
            self.assertTrue(math.isfinite(r["nmse"]), r)

    def _cleanup(self) -> None:
        """Remove E2E-generated run artifacts (explicit e2e-* prefixes only)."""
        for base in (PROJECT_ROOT / "runs", PROJECT_ROOT, PROJECT_ROOT / "reports"):
            if not base.is_dir():
                continue
            for child in base.iterdir():
                if child.name.startswith("e2e-") and child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
