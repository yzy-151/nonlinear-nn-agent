import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import scipy.io as scio
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.experiment import (
    build_model,
    count_trainable_parameters,
    ExperimentConfig,
    generate_complex_mp_features,
    generate_mp_features,
    generate_targets,
    load_config,
    load_scaled_signals,
    nmse_db,
)


class ExperimentCoreTest(unittest.TestCase):
    def test_nmse_db_uses_target_power_normalization(self):
        target = np.array([1.0 + 0.0j, -1.0 + 0.0j])
        prediction = np.array([0.9 + 0.0j, -0.9 + 0.0j])

        self.assertAlmostEqual(nmse_db(target, prediction), -20.0, places=6)

    def test_generate_mp_features_keeps_complex_memory_terms(self):
        signal = np.array([1 + 1j, 2 + 0j, 3 - 1j, 4 + 2j])

        features = generate_mp_features(signal, memory_depth=1)

        self.assertEqual(features.shape, (3, 8))
        self.assertEqual(features[0, 0], signal[1])
        self.assertEqual(features[0, 1], signal[0])
        self.assertEqual(features[0, 2], abs(signal[1]) ** 1)
        self.assertEqual(features[0, 7], abs(signal[0]) ** 3)

    def test_generate_complex_mp_features_preserves_phase_in_nonlinear_terms(self):
        signal = np.array([1 + 1j, 2 + 0j, 3 - 1j])

        features = generate_complex_mp_features(signal, memory_depth=1, order_count=4)

        self.assertEqual(features.shape, (2, 8))
        self.assertEqual(features[0, 0], signal[1])
        self.assertEqual(features[0, 1], signal[0])
        self.assertEqual(features[0, 2], signal[1] * abs(signal[1]) ** 2)
        self.assertEqual(features[0, 7], signal[0] * abs(signal[0]) ** 6)

    def test_generate_complex_mp_features_supports_custom_order_count(self):
        signal = np.array([1 + 1j, 2 + 0j, 3 - 1j])

        features = generate_complex_mp_features(signal, memory_depth=1, order_count=3)

        self.assertEqual(features.shape, (2, 6))
        self.assertEqual(features[0, 4], signal[1] * abs(signal[1]) ** 4)

    def test_load_config_merges_yaml_with_defaults(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(
                yaml.safe_dump({"epochs": 3, "learning_rate": 0.02}),
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertIsInstance(config, ExperimentConfig)
            self.assertEqual(config.epochs, 3)
            self.assertEqual(config.learning_rate, 0.02)
            self.assertEqual(config.memory_depth, 5)

    def test_load_scaled_signals_preserves_full_x_and_d_length(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "signals.mat"
            x = np.array([[1 + 1j, 2 + 0j, 3 - 1j, 4 + 2j]])
            d = np.array([[2 + 0j, 4 + 0j, 6 + 0j, 8 + 0j]])
            scio.savemat(path, {"x": x, "d": d})

            loaded_x, loaded_d = load_scaled_signals(path)

            self.assertEqual(loaded_x.shape, (4,))
            self.assertEqual(loaded_d.shape, (4,))
            self.assertAlmostEqual(
                np.mean(np.abs(loaded_x) ** 2),
                np.mean(np.abs(loaded_d) ** 2),
            )

    def test_tiny_mlp_stays_under_parameter_budget(self):
        config = ExperimentConfig(model_type="tiny_mlp", hidden_units=64)

        model = build_model(config)

        self.assertLessEqual(count_trainable_parameters(model), 4000)

    def test_linear_model_has_fewer_than_100_parameters(self):
        config = ExperimentConfig(model_type="linear")

        model = build_model(config)

        self.assertLessEqual(count_trainable_parameters(model), 100)

    def test_complex_cnn_exceeds_tiny_parameter_budget(self):
        config = ExperimentConfig(model_type="complex_cnn")

        model = build_model(config)

        self.assertGreater(count_trainable_parameters(model), 4000)

    def test_generate_targets_can_use_residual_mode(self):
        x = np.array([1 + 1j, 2 + 0j, 3 - 1j])
        d = np.array([1.5 + 1j, 1.0 + 0.5j, 2.5 - 2j])

        targets = generate_targets(x, d, memory_depth=1, target_mode="residual")

        self.assertEqual(targets.shape, (2, 2))
        self.assertAlmostEqual(targets[0, 0], (d[1] - x[1]).real)
        self.assertAlmostEqual(targets[0, 1], (d[1] - x[1]).imag)

    def test_spline_mlp_uses_learnable_lut_activation_under_budget(self):
        config = ExperimentConfig(
            model_type="spline_mlp",
            feature_mode="complex_mp",
            memory_depth=48,
            mp_order_count=1,
            hidden_units=32,
            spline_knots=16,
        )

        model = build_model(config)

        self.assertLessEqual(count_trainable_parameters(model), 4000)
        self.assertTrue(hasattr(model, "activation"))

    def test_spline_mlp_forward_preserves_batch_and_complex_output_shape(self):
        config = ExperimentConfig(
            model_type="spline_mlp",
            feature_mode="complex_mp",
            memory_depth=2,
            mp_order_count=1,
            hidden_units=4,
            spline_knots=16,
        )
        model = build_model(config)
        width = 2 * (config.memory_depth + 1)
        real = np.ones((3, width // 2), dtype=np.float32)
        imag = np.zeros((3, width // 2), dtype=np.float32)

        import torch
        output = model(torch.from_numpy(real), torch.from_numpy(imag))

        self.assertEqual(tuple(output.shape), (3, 2))

if __name__ == "__main__":
    unittest.main()

