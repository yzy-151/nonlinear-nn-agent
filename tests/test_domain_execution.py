"""Tests for domain-driven execution — verifying synthetic domain works end-to-end."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain
from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
from nonlinear_agent.planner_validation import validate_planned_overrides
from nonlinear_agent.server import build_runtime, HarnessRunSpec, build_harness_request


class TestSyntheticDomainExecution(unittest.TestCase):
    def setUp(self):
        self.domain = SyntheticRegressionDomain()

    def test_guard_allows_synthetic_fields(self):
        result = validate_planned_overrides(
            {"degree": 3, "reg_strength": 0.01}, domain=self.domain,
        )
        self.assertEqual(result["degree"], 3)

    def test_guard_rejects_synthetic_fields_without_domain(self):
        with self.assertRaises(ValueError):
            validate_planned_overrides({"degree": 3, "reg_strength": 0.01}, domain=None)

    def test_guard_rejects_invalid_degree(self):
        with self.assertRaises(ValueError):
            validate_planned_overrides({"degree": 10}, domain=self.domain)

    def test_build_harness_spec(self):
        spec = self.domain.build_harness_spec(
            session_id="test-001",
            base_config="configs/examples/synthetic-regression.yaml",
            overrides={"degree": 3, "reg_strength": 0.01},
            constraints={"parameter_count_max": 100},
            timeout_seconds=60.0,
        )
        self.assertIsInstance(spec, HarnessRunSpec)
        self.assertEqual(spec.session_id, "test-001")

    def test_build_harness_steps_two_steps(self):
        spec = self.domain.build_harness_spec(
            session_id="test-001",
            base_config="configs/examples/synthetic-regression.yaml",
            overrides={"degree": 2, "reg_strength": 0.001},
            constraints={}, timeout_seconds=60.0,
        )
        steps = self.domain.build_harness_steps(spec, Path("."))
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].name, "fit_candidate")
        self.assertEqual(steps[1].name, "evaluate_candidate")

    def test_synthetic_tools_execute(self):
        import asyncio
        from nonlinear_agent.tools import ToolCall
        with tempfile.TemporaryDirectory() as tmp:
            registry = self.domain.build_tool_registry(Path(tmp))
            fit_result = asyncio.run(registry.run(
                ToolCall(name="fit_candidate", args={"degree": 3, "reg_strength": 0.001})
            ))
            self.assertEqual(fit_result.status, "succeeded")
            self.assertIn("train_mse", fit_result.output)
            eval_result = asyncio.run(registry.run(
                ToolCall(name="evaluate_candidate", args={})
            ))
            self.assertEqual(eval_result.status, "succeeded")
            self.assertIn("val_mse", eval_result.output)

    def test_build_runtime_with_domain(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = build_runtime(Path(tmp), session_id="test", timeout_seconds=60.0, domain=self.domain)
            self.assertIn("fit_candidate", runtime.tool_registry._tools)
            self.assertIn("evaluate_candidate", runtime.tool_registry._tools)

    def test_display_config(self):
        self.assertIn("val_mse", self.domain.display_metric_names())
        self.assertEqual(self.domain.display_metric_unit(), "")
        self.assertEqual(self.domain.artifact_preview_patterns(), [])

    def test_allowed_override_fields(self):
        fields = self.domain.allowed_override_fields()
        self.assertIn("degree", fields)
        self.assertIn("reg_strength", fields)

    def test_planner_allowed_tools(self):
        tools = self.domain.planner_allowed_tools()
        self.assertIn("fit_candidate", tools)
        self.assertIn("evaluate_candidate", tools)


class TestBackwardCompatibility(unittest.TestCase):
    def test_nonlinear_harness_steps_match_original(self):
        domain = NonlinearModelingDomain()
        spec = HarnessRunSpec(
            session_id="test", base_config="configs/baselines/lstsq-complexmp-o12-m150.yaml",
            output_dir="reports/test", epochs=0, learning_rate=0.0008, optimizer="adam",
            nmse_threshold_db=-35.0, timeout_seconds=300.0,
            overrides={"model_type": "complex_lstsq"},
        )
        original = build_harness_request(spec)
        domain_steps = domain.build_harness_steps(spec, Path("."))
        self.assertEqual(len(original.steps), len(domain_steps))
        for orig_step, dom_step in zip(original.steps, domain_steps):
            self.assertEqual(orig_step.name, dom_step.name)

    def test_guard_without_domain_still_works(self):
        result = validate_planned_overrides(
            {"model_type": "complex_lstsq", "memory_depth": 8, "epochs": 0}, domain=None,
        )
        self.assertEqual(result["model_type"], "complex_lstsq")

    def test_guard_with_nonlinear_domain_still_works(self):
        domain = NonlinearModelingDomain()
        result = validate_planned_overrides(
            {"model_type": "complex_lstsq", "memory_depth": 8, "epochs": 0}, domain=domain,
        )
        self.assertEqual(result["model_type"], "complex_lstsq")
