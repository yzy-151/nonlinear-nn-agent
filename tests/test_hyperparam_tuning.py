"""TDD tests for tunable hyperparameters and the optimizable-field whitelist."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class TestTunableConfigFields(unittest.TestCase):
    def test_config_exposes_kernel_and_layers_in_whitelist(self):
        from nonlinear_agent.experiment import ExperimentConfig

        cfg = ExperimentConfig()
        self.assertEqual(cfg.kernel_size, 3)
        self.assertEqual(cfg.num_layers, 3)
        # The guard whitelist is derived from ExperimentConfig fields
        from nonlinear_agent.planner_validation import allowed_override_fields

        self.assertIn("kernel_size", allowed_override_fields())
        self.assertIn("num_layers", allowed_override_fields())


class TestComplexCNNTunable(unittest.TestCase):
    def test_kernel_size_is_respected_with_adaptive_padding(self):
        from nonlinear_agent.experiment import ComplexCNN

        cnn = ComplexCNN(memory_depth=5, kernel_size=5, num_layers=2)
        conv = cnn.convs[0]
        self.assertEqual(tuple(conv.conv_real.kernel_size), (5, 5))
        self.assertEqual(tuple(conv.conv_real.padding), (2, 2))

    def test_num_layers_controls_conv_depth(self):
        from nonlinear_agent.experiment import ComplexCNN

        self.assertEqual(len(ComplexCNN(5, num_layers=2).convs), 2)
        self.assertEqual(len(ComplexCNN(5, num_layers=4).convs), 4)

    def test_forward_shape_is_stable(self):
        import torch
        from nonlinear_agent.experiment import ComplexCNN

        cnn = ComplexCNN(memory_depth=5, kernel_size=5, num_layers=3)
        x = torch.randn(4, 24)  # 4 * (memory_depth+1)
        out = cnn(x, x)
        self.assertEqual(tuple(out.shape), (4, 2))


class TestFilteredDomain(unittest.TestCase):
    def test_filtered_domain_limits_design_space_and_whitelist(self):
        from nonlinear_agent.domains.filtered import FilteredDomain
        from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain

        domain = FilteredDomain(
            NonlinearModelingDomain(),
            enabled_fields=["model_type", "learning_rate", "kernel_size"],
        )
        self.assertEqual(
            set(domain.design_space().keys()),
            {"model_type", "learning_rate", "kernel_size"},
        )
        self.assertEqual(
            domain.allowed_override_fields(),
            {"model_type", "learning_rate", "kernel_size"},
        )
        # A disabled field is rejected by the guard
        errors = domain.validate_candidate({"memory_depth": 999})
        self.assertTrue(
            any("memory_depth" in error for error in errors),
            f"expected memory_depth rejection, got {errors}",
        )

    def test_filtered_domain_delegates_other_methods(self):
        from nonlinear_agent.domains.filtered import FilteredDomain
        from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain

        domain = FilteredDomain(NonlinearModelingDomain(), enabled_fields=["model_type"])
        self.assertEqual(domain.name, "nonlinear-modeling")
        self.assertEqual(domain.primary_metric(), "nmse_db")
        self.assertIsInstance(domain.historical_priors(), list)


if __name__ == "__main__":
    unittest.main()
