"""Tests for DomainPlugin extraction (v1.8.0).

Verifies the DomainPlugin Protocol contract, the NonlinearModelingDomain,
the SyntheticRegressionDomain, and that Planner/Guard/Loop accept domain
parameters without hardcoded domain knowledge.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nonlinear_agent.domains.base import DomainPlugin
from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain
from nonlinear_agent.planner import ExperimentPlanner
from nonlinear_agent.planner_validation import validate_planned_overrides


class TestDomainPluginProtocol(unittest.TestCase):
    """Verify that domain implementations satisfy the DomainPlugin Protocol."""

    def test_nonlinear_domain_is_protocol_compatible(self):
        domain = NonlinearModelingDomain()
        self.assertIsInstance(domain, DomainPlugin)

    def test_synthetic_domain_is_protocol_compatible(self):
        domain = SyntheticRegressionDomain()
        self.assertIsInstance(domain, DomainPlugin)


class TestNonlinearModelingDomain(unittest.TestCase):
    """Verify the nonlinear modeling domain exposes correct design space,
    guard logic, and metric semantics."""

    def setUp(self):
        self.domain = NonlinearModelingDomain()

    def test_domain_name(self):
        self.assertEqual(self.domain.name, "nonlinear-modeling")

    def test_design_space_contains_model_types(self):
        ds = self.domain.design_space()
        self.assertIn("model_type", ds)
        self.assertIn("complex_lstsq", ds["model_type"])

    def test_primary_metric_is_nmse_db(self):
        self.assertEqual(self.domain.primary_metric(), "nmse_db")

    def test_is_better_lower_nmse_wins(self):
        self.assertTrue(
            self.domain.is_better({"nmse_db": -38.0}, {"nmse_db": -35.0})
        )

    def test_is_better_higher_nmse_loses(self):
        self.assertFalse(
            self.domain.is_better({"nmse_db": -30.0}, {"nmse_db": -35.0})
        )

    def test_validate_candidate_passes_valid_overrides(self):
        errors = self.domain.validate_candidate(
            {"memory_depth": 24, "mp_order_count": 3, "model_type": "complex_lstsq"}
        )
        self.assertEqual(errors, [])

    def test_validate_candidate_fails_invalid_spline_range(self):
        errors = self.domain.validate_candidate(
            {"model_type": "spline_mlp", "spline_range": None}
        )
        self.assertTrue(len(errors) > 0)

    def test_validate_candidate_fails_over_parameter_budget(self):
        errors = self.domain.validate_candidate(
            {"model_type": "complex_lstsq", "memory_depth": 99999, "mp_order_count": 999}
        )
        self.assertTrue(len(errors) > 0)

    def test_default_base_config_is_baseline_lstsq(self):
        cfg = self.domain.default_base_config()
        self.assertIn("baselines/lstsq-complexmp-o12-m150.yaml", cfg)

    def test_default_constraints(self):
        c = self.domain.default_constraints()
        self.assertEqual(c["metric"], "nmse_db")
        self.assertGreater(c["parameter_count_max"], 0)

    def test_planner_instructions_contains_domain_guidance(self):
        text = self.domain.planner_instructions()
        self.assertIn("complex_lstsq", text.lower())

    def test_planner_instructions_does_not_have_config_file_path(self):
        text = self.domain.planner_instructions()
        self.assertNotIn("configs/baselines/", text)

    def test_build_tool_registry_returns_expected_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = self.domain.build_tool_registry(Path(tmp))
            tool_names = list(registry._tools.keys())
            for name in ("generate_config", "run_training", "verify_artifacts", "write_report"):
                self.assertIn(name, tool_names)


class TestSyntheticRegressionDomain(unittest.TestCase):
    """Verify the lightweight second domain plugin for regression experiments."""

    def setUp(self):
        self.domain = SyntheticRegressionDomain()

    def test_domain_name(self):
        self.assertEqual(self.domain.name, "synthetic-regression")

    def test_primary_metric_is_val_mse(self):
        self.assertEqual(self.domain.primary_metric(), "val_mse")

    def test_design_space_has_degree_and_reg_strength(self):
        ds = self.domain.design_space()
        self.assertIn("degree", ds)
        self.assertIn("reg_strength", ds)

    def test_build_tool_registry_has_different_tools_than_nonlinear(self):
        nl = NonlinearModelingDomain()
        with tempfile.TemporaryDirectory() as tmp:
            nl_registry = nl.build_tool_registry(Path(tmp))
            sy_registry = self.domain.build_tool_registry(Path(tmp))
            nl_names = set(nl_registry._tools.keys())
            sy_names = set(sy_registry._tools.keys())
            self.assertNotEqual(nl_names, sy_names)
            self.assertIn("fit_candidate", sy_names)
            self.assertIn("evaluate_candidate", sy_names)


class TestPlannerWithDomain(unittest.TestCase):
    """Verify ExperimentPlanner accepts a domain and uses it for prompt generation."""

    def test_planner_accepts_domain_parameter(self):
        from nonlinear_agent.llm import FakeLLMClient

        llm = FakeLLMClient(
            responses=[
                '{"summary":"test","stop":true,"experiments":[]}',
            ]
        )
        domain = NonlinearModelingDomain()
        planner = ExperimentPlanner(llm_client=llm, domain=domain)
        self.assertEqual(planner.domain, domain)

    def test_planner_builds_prompt_with_domain_instructions(self):
        from nonlinear_agent.llm import FakeLLMClient

        llm = FakeLLMClient(
            responses=[
                '{"summary":"test","stop":true,"experiments":[]}',
            ]
        )
        domain = NonlinearModelingDomain()
        planner = ExperimentPlanner(llm_client=llm, domain=domain)
        prompt = planner._build_prompt(goal="test", history=[], constraints={})
        self.assertIn("complex_lstsq", prompt.lower())

    def test_planner_without_domain_still_works(self):
        from nonlinear_agent.llm import FakeLLMClient

        llm = FakeLLMClient(
            responses=[
                '{"summary":"test","stop":true,"experiments":[]}',
            ]
        )
        planner = ExperimentPlanner(llm_client=llm)
        self.assertIsNone(planner.domain)
        prompt = planner._build_prompt(goal="test", history=[], constraints={})
        self.assertIn("nonlinear", prompt.lower())


class TestGuardWithDomain(unittest.TestCase):
    """Verify the schema guard delegates domain-specific checks."""

    def test_guard_delegates_to_domain_validate_candidate(self):
        domain = NonlinearModelingDomain()
        normalized = validate_planned_overrides(
            {"model_type": "complex_lstsq", "memory_depth": 8, "mp_order_count": 2, "epochs": 0},
            parameter_count_max=4000,
            domain=domain,
        )
        self.assertEqual(normalized["model_type"], "complex_lstsq")

    def test_guard_rejects_invalid_candidate_with_domain_errors(self):
        domain = NonlinearModelingDomain()
        with self.assertRaises(ValueError):
            validate_planned_overrides(
                {"model_type": "spline_mlp", "spline_range": None, "epochs": 200},
                parameter_count_max=4000,
                domain=domain,
            )

    def test_guard_without_domain_uses_builtin_checks(self):
        normalized = validate_planned_overrides(
            {"model_type": "complex_lstsq", "memory_depth": 8, "mp_order_count": 2, "epochs": 0},
            parameter_count_max=4000,
        )
        self.assertEqual(normalized["model_type"], "complex_lstsq")
