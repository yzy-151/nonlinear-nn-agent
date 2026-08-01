"""TDD tests for the minimal SimpleDomain adapter."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.domains.base import DomainPlugin
from nonlinear_agent.domains.simple import SimpleDomain


def _run_candidate(degree: int = 2, reg: float = 0.01) -> dict:
    """Fake candidate executor: returns a metric dict."""
    return {"val_mse": float(reg) + degree * 0.01, "degree": degree}


class TestSimpleDomain(unittest.TestCase):
    def test_implements_domain_plugin_protocol(self):
        domain = SimpleDomain(
            name="grid-scan",
            design_space={"degree": [1, 2, 3], "reg": [0.001, 0.01, 0.1]},
            run_candidate=_run_candidate,
            primary_metric="val_mse",
        )
        self.assertIsInstance(domain, DomainPlugin)

    def test_design_space_and_validation(self):
        domain = SimpleDomain(
            name="grid-scan",
            design_space={"degree": [1, 2, 3]},
            run_candidate=_run_candidate,
            primary_metric="val_mse",
        )
        self.assertEqual(domain.design_space(), {"degree": [1, 2, 3]})
        self.assertEqual(domain.validate_candidate({"degree": 2}), [])
        self.assertGreater(len(domain.validate_candidate({"degree": 99})), 0)
        self.assertIn("degree", domain.allowed_override_fields())

    def test_executes_candidate_through_harness_tools(self):
        domain = SimpleDomain(
            name="grid-scan",
            design_space={"degree": [1, 2, 3]},
            run_candidate=_run_candidate,
            primary_metric="val_mse",
        )
        with tempfile.TemporaryDirectory() as tmp:
            registry = domain.build_tool_registry(Path(tmp))
            spec = domain.build_harness_spec(
                session_id="s1",
                base_config="",
                overrides={"degree": 2},
                constraints={"parameter_count_max": 100},
                timeout_seconds=60,
            )
            steps = domain.build_harness_steps(spec, Path(tmp))
            result = asyncio.run(registry.run(steps[0]))
            self.assertEqual(result.status, "succeeded")
            self.assertIn("val_mse", result.output)

    def test_is_better_respects_lower_is_better(self):
        low = SimpleDomain(
            name="a", design_space={"x": [1]}, run_candidate=_run_candidate,
            primary_metric="val_mse", lower_is_better=True,
        )
        high = SimpleDomain(
            name="b", design_space={"x": [1]}, run_candidate=_run_candidate,
            primary_metric="acc", lower_is_better=False,
        )
        self.assertTrue(low.is_better({"val_mse": 0.1}, {"val_mse": 0.5}))
        self.assertTrue(high.is_better({"acc": 0.9}, {"acc": 0.5}))

    def test_planner_accepts_simple_domain(self):
        from nonlinear_agent.llm import FakeLLMClient
        from nonlinear_agent.planner import ExperimentPlanner

        domain = SimpleDomain(
            name="grid-scan",
            design_space={"degree": [1, 2, 3], "reg": [0.001, 0.01]},
            run_candidate=_run_candidate,
            primary_metric="val_mse",
        )
        llm = FakeLLMClient(responses=['{"summary":"s","stop":true,"experiments":[]}'])
        planner = ExperimentPlanner(llm_client=llm, domain=domain)
        prompt = planner._build_prompt(goal="g", history=[], constraints={})
        self.assertIn("degree", prompt)
        self.assertIn("allowed override fields", prompt)


if __name__ == "__main__":
    unittest.main()
