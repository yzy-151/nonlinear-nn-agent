import asyncio
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.llm import FakeLLMClient
from nonlinear_agent.loop import ExperimentPlannerLoop
from nonlinear_agent.planner import ExperimentPlanner
from nonlinear_agent.planner_validation import (
    estimate_parameter_count,
    normalize_planner_overrides,
    validate_planned_overrides,
)


class PlannerValidationTest(unittest.TestCase):
    def test_normalize_maps_train_samples_to_max_train_samples(self):
        normalized = normalize_planner_overrides({"train_samples": 2048, "epochs": 8})

        self.assertEqual(normalized["max_train_samples"], 2048)
        self.assertNotIn("train_samples", normalized)
        self.assertEqual(normalized["epochs"], 8)

    def test_validate_rejects_unsupported_rank_field(self):
        with self.assertRaisesRegex(ValueError, "Unsupported planner override fields: rank"):
            validate_planned_overrides({"model_type": "complex_lstsq", "rank": 100})

    def test_estimate_parameter_count_for_lstsq_and_spline_mlp(self):
        lstsq = estimate_parameter_count({
            "model_type": "complex_lstsq",
            "feature_mode": "complex_mp",
            "memory_depth": 120,
            "mp_order_count": 10,
        })
        spline = estimate_parameter_count({
            "model_type": "spline_mlp",
            "feature_mode": "complex_mp",
            "memory_depth": 48,
            "mp_order_count": 1,
            "hidden_units": 32,
            "spline_knots": 16,
        })

        self.assertEqual(lstsq, 2422)
        self.assertEqual(spline, 3746)

    def test_validate_rejects_over_parameter_budget_candidate(self):
        with self.assertRaisesRegex(ValueError, "exceeds parameter budget"):
            validate_planned_overrides(
                {
                    "model_type": "spline_mlp",
                    "feature_mode": "complex_mp",
                    "memory_depth": 72,
                    "mp_order_count": 2,
                    "hidden_units": 64,
                    "spline_knots": 16,
                },
                parameter_count_max=4000,
            )

    def test_validate_rejects_invalid_spline_range_before_training(self):
        for invalid_value in (None, [1.0, 3.0]):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaisesRegex(ValueError, "spline_range must be a number"):
                    validate_planned_overrides(
                        {
                            "model_type": "spline_mlp",
                            "feature_mode": "complex_mp",
                            "memory_depth": 24,
                            "mp_order_count": 1,
                            "hidden_units": 16,
                            "spline_knots": 16,
                            "spline_range": invalid_value,
                        },
                        parameter_count_max=4000,
                    )

    def test_validate_rejects_zero_epoch_neural_models_but_allows_lstsq(self):
        with self.assertRaisesRegex(ValueError, "epochs must be >= 1 for neural model"):
            validate_planned_overrides({"model_type": "tiny_mlp", "epochs": 0})

        validated = validate_planned_overrides({"model_type": "complex_lstsq", "epochs": 0})

        self.assertEqual(validated["epochs"], 0)

    def test_planner_applies_mapping_before_returning_experiment(self):
        llm = FakeLLMClient(responses=[
            '{"summary":"map aliases", "stop": false, "experiments": ['
            '{"id":"alias-demo", "reason":"test", "overrides":{"train_samples":2048,"epochs":8}}]}'
        ])
        planner = ExperimentPlanner(llm_client=llm)

        plan = planner.plan("test alias", constraints={"parameter_count_max": 4000})

        self.assertEqual(plan.experiments[0].overrides["max_train_samples"], 2048)
        self.assertNotIn("train_samples", plan.experiments[0].overrides)

    def test_loop_records_rejected_plan_without_running_runtime(self):
        llm = FakeLLMClient(responses=[
            '{"summary":"bad plan", "stop": false, "experiments": ['
            '{"id":"bad-rank", "reason":"bad", "overrides":{"rank":100}}]}'
        ])
        planner = ExperimentPlanner(llm_client=llm)
        called = {"runtime": False}

        class FakeRuntime:
            async def run(self, request):
                called["runtime"] = True
                yield None

        with TemporaryDirectory() as tmpdir:
            loop = ExperimentPlannerLoop(
                planner=planner,
                workspace=Path(tmpdir),
                runtime_factory=lambda session_id: FakeRuntime(),
            )
            result = asyncio.run(loop.run(goal="reject invalid", max_rounds=1))

        self.assertFalse(called["runtime"])
        self.assertEqual(result.history[0]["run_status"], "rejected")
        self.assertIn("rank", result.history[0]["error"])

    def test_loop_records_invalid_spline_range_as_rejected_without_runtime(self):
        llm = FakeLLMClient(responses=[
            '{"summary":"bad spline", "stop": false, "experiments": ['
            '{"id":"bad-spline", "reason":"bad", '
            '"overrides":{"model_type":"spline_mlp","feature_mode":"complex_mp",'
            '"memory_depth":24,"mp_order_count":1,"hidden_units":16,'
            '"spline_knots":16,"spline_range":null,"epochs":50}}]}'
        ])
        planner = ExperimentPlanner(llm_client=llm)
        called = {"runtime": False}

        class FakeRuntime:
            async def run(self, request):
                called["runtime"] = True
                yield None

        with TemporaryDirectory() as tmpdir:
            loop = ExperimentPlannerLoop(
                planner=planner,
                workspace=Path(tmpdir),
                runtime_factory=lambda session_id: FakeRuntime(),
            )
            result = asyncio.run(loop.run(goal="reject invalid spline", max_rounds=1))

        self.assertFalse(called["runtime"])
        self.assertEqual(result.history[0]["run_status"], "rejected")
        self.assertIn("spline_range must be a number", result.history[0]["error"])


if __name__ == "__main__":
    unittest.main()
