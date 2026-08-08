"""TDD tests for the PIM-cancellation and register-config domains."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.domains.base import DomainPlugin
from nonlinear_agent.domains.pim_cancellation import PIMCancellationDomain
from nonlinear_agent.domains.register_config import RegisterConfigDomain


class TestPIMCancellationDomain(unittest.TestCase):
    def setUp(self):
        self.domain = PIMCancellationDomain()

    def test_implements_domain_plugin_protocol(self):
        self.assertIsInstance(self.domain, DomainPlugin)

    def test_design_space_is_optimizable(self):
        ds = self.domain.design_space()
        self.assertIn("model_type", ds)
        self.assertIn("poly3", ds["model_type"])
        self.assertIn("memory_depth", ds)
        self.assertEqual(self.domain.primary_metric(), "res_db")

    def test_runs_candidate_and_reports_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = self.domain.build_tool_registry(Path(tmp))
            spec = self.domain.build_harness_spec(
                session_id="p1",
                base_config="",
                overrides={"model_type": "poly3", "memory_depth": 1, "reg": 1e-3},
                constraints={"parameter_count_max": 100000},
                timeout_seconds=60,
            )
            steps = self.domain.build_harness_steps(spec, Path(tmp))
            result = asyncio.run(registry.run(steps[0]))

        self.assertEqual(result.status, "succeeded")
        self.assertIn("res_db", result.output)
        self.assertIsInstance(result.output["res_db"], float)
        self.assertGreater(result.output["params"], 0)
        self.assertIn("max_power_db", result.output)
        self.assertIn("param_spread", result.output)

    def test_validate_candidate(self):
        self.assertEqual(self.domain.validate_candidate({"model_type": "poly3"}), [])
        self.assertGreater(len(self.domain.validate_candidate({"model_type": "lstm"})), 0)


class TestRegisterConfigDomain(unittest.TestCase):
    def setUp(self):
        self.domain = RegisterConfigDomain()

    def test_implements_domain_plugin_protocol(self):
        self.assertIsInstance(self.domain, DomainPlugin)

    def test_design_space_has_mu_optimizer_data_lut(self):
        ds = self.domain.design_space()
        self.assertIn("mu", ds)
        self.assertIn("optimizer", ds)
        self.assertIn("data_choice", ds)
        self.assertIn("lut_choice", ds)
        self.assertEqual(self.domain.primary_metric(), "final_mse_db")

    def test_runs_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = self.domain.build_tool_registry(Path(tmp))
            spec = self.domain.build_harness_spec(
                session_id="r1",
                base_config="",
                overrides={"mu": 0.01, "optimizer": "adam", "lut_choice": "lut16"},
                constraints={"parameter_count_max": 1},
                timeout_seconds=60,
            )
            steps = self.domain.build_harness_steps(spec, Path(tmp))
            result = asyncio.run(registry.run(steps[0]))

        self.assertEqual(result.status, "succeeded")
        self.assertIn("final_mse_db", result.output)
        self.assertIsInstance(result.output["final_mse_db"], float)

    def test_validate_candidate(self):
        self.assertEqual(
            self.domain.validate_candidate(
                {"mu": 0.01, "optimizer": "adam", "lut_choice": "lut16"}
            ),
            [],
        )
        self.assertGreater(
            len(self.domain.validate_candidate({"optimizer": "rmsprop"})), 0
        )


if __name__ == "__main__":
    unittest.main()
