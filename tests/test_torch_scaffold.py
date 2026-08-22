from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import scipy.io as scio
from torch import nn


class TorchScaffoldTest(unittest.TestCase):
    def test_architecture_only_plugin_uses_fixed_training_and_evidence_pipeline(self):
        from nonlinear_agent.model_plugins.contracts import (
            ArchitectureEdge,
            ArchitectureNode,
            ModelDescriptor,
            TrainingRequest,
        )
        from nonlinear_agent.model_plugins.torch_scaffold import TorchArchitecturePlugin

        class CompactPlugin(TorchArchitecturePlugin):
            descriptor = ModelDescriptor(
                name="compact_scaffold",
                version="1.0.0",
                training_mode="gradient",
                config_schema={"type": "object", "properties": {}},
                nodes=(
                    ArchitectureNode("input", "Complex MP", "complex_mp"),
                    ArchitectureNode("hidden", "Dense + Tanh", "dense_activation"),
                    ArchitectureNode("output", "Complex output", "linear"),
                ),
                edges=(
                    ArchitectureEdge("input", "hidden"),
                    ArchitectureEdge("hidden", "output"),
                ),
            )

            def build_model(self, input_dim, config):
                return nn.Sequential(
                    nn.Linear(input_dim, 8), nn.Tanh(), nn.Linear(8, 2)
                )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = root / "data.mat"
            rng = np.random.default_rng(7)
            x = rng.normal(size=256) + 1j * rng.normal(size=256)
            d = 0.8 * x + 0.1 * x * np.abs(x) ** 2
            scio.savemat(data, {"x": x.reshape(1, -1), "d": d.reshape(1, -1)})
            request = TrainingRequest(
                run_id="scaffold-test",
                workspace=str(root),
                config={
                    "feature_mode": "complex_mp",
                    "target_mode": "direct",
                    "memory_depth": 2,
                    "mp_order_count": 2,
                    "epochs": 2,
                    "batch_size": 32,
                    "learning_rate": 1e-3,
                    "optimizer": "adam",
                    "scheduler_step_size": 10,
                    "scheduler_gamma": 1.0,
                },
                output_dir="reports/scaffold-test",
                data_file="data.mat",
                train_ratio=0.8,
                seed=7,
            )

            result = CompactPlugin().train(request)

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.metrics["parameter_count"], 122)
            self.assertTrue(np.isfinite(result.metrics["nmse_db"]))
            self.assertEqual({Path(item).name for item in result.artifacts}, {"metrics.json", "psd.png"})
            for artifact in result.artifacts:
                self.assertTrue((root / artifact).is_file())
