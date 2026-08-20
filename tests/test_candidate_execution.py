from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path


PLUGIN_SOURCE = '''
import base64
import json
from pathlib import Path

from nonlinear_agent.model_plugins.contracts import (
    ArchitectureEdge, ArchitectureNode, ModelDescriptor,
    TrainingResult, descriptor_hash,
)

class NovelPlugin:
    descriptor = ModelDescriptor(
        name="novel_dynamic_model",
        version="1.0.0",
        training_mode="custom",
        config_schema={
            "type": "object",
            "properties": {
                "width": {"type": "integer", "minimum": 1},
                "train_ratio": {"type": "number"},
                "seed": {"type": "integer"},
            },
            "required": ["width"],
            "additionalProperties": False,
        },
        nodes=(
            ArchitectureNode("input", "Input", "input"),
            ArchitectureNode("novel", "Novel transform", "learned_transform"),
            ArchitectureNode("output", "Output", "linear"),
        ),
        edges=(
            ArchitectureEdge("input", "novel"),
            ArchitectureEdge("novel", "output"),
        ),
    )

    def estimate_parameters(self, config):
        return int(config["width"]) * 10

    def train(self, request):
        out = Path(request.workspace) / request.output_dir
        out.mkdir(parents=True, exist_ok=True)
        metrics = {
            "nmse_db": -36.5,
            "parameter_count": self.estimate_parameters(request.config),
            "observed_train_ratio": request.train_ratio,
            "observed_seed": request.seed,
        }
        metrics_path = out / "metrics.json"
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
        png_path = out / "psd.png"
        png_path.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        ))
        return TrainingResult(
            status="completed",
            metrics=metrics,
            artifacts=(
                metrics_path.relative_to(request.workspace).as_posix(),
                png_path.relative_to(request.workspace).as_posix(),
            ),
            descriptor_hash=descriptor_hash(self.descriptor),
        )
'''


class CandidateExecutionTest(unittest.TestCase):
    def test_training_request_exposes_one_fixed_dataset_contract(self):
        from nonlinear_agent.model_plugins.contracts import TrainingRequest

        request = TrainingRequest.from_dict(
            {
                "run_id": "candidate-001",
                "workspace": str(self.root),
                "config": {},
                "output_dir": "reports/candidate-001",
                "data_file": "examples/nonlinear_fit/data/Simulation_MPDPD_Data.mat",
                "train_ratio": 0.8,
                "seed": 7,
            }
        )

        self.assertEqual(request.data_file, "examples/nonlinear_fit/data/Simulation_MPDPD_Data.mat")
        self.assertEqual(request.train_ratio, 0.8)
        self.assertEqual(request.seed, 7)

    def test_training_result_normalizes_common_success_status(self):
        from nonlinear_agent.model_plugins.contracts import TrainingResult

        for status in ("success", "succeeded", "ok", "completed"):
            result = TrainingResult.from_dict(
                {
                    "status": status,
                    "metrics": {"nmse_db": -30.0, "parameter_count": 10},
                    "artifacts": [],
                    "descriptor_hash": "hash",
                }
            )
            self.assertEqual(result.status, "completed")

    def test_training_result_accepts_named_artifact_mapping_values(self):
        from nonlinear_agent.model_plugins.contracts import TrainingResult

        result = TrainingResult.from_dict(
            {
                "status": "success",
                "metrics": {"nmse_db": -30.0, "parameter_count": 10},
                "artifacts": {
                    "metrics.json": "reports/run/metrics.json",
                    "psd.png": "reports/run/psd.png",
                },
                "descriptor_hash": "hash",
            }
        )

        self.assertEqual(
            result.artifacts,
            ("reports/run/metrics.json", "reports/run/psd.png"),
        )

    def test_training_result_ignores_non_numeric_metric_metadata(self):
        from nonlinear_agent.model_plugins.contracts import TrainingResult

        result = TrainingResult.from_dict(
            {
                "status": "completed",
                "metrics": {
                    "status": "completed",
                    "nmse_db": -30.0,
                    "parameter_count": 10,
                },
                "artifacts": [],
                "descriptor_hash": "hash",
            }
        )

        self.assertEqual(
            result.metrics,
            {"nmse_db": -30.0, "parameter_count": 10.0},
        )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        candidate_dir = self.root / "models" / "candidates"
        candidate_dir.mkdir(parents=True)
        (candidate_dir / "novel.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
        self.manifest = candidate_dir / "novel.json"
        self.manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "name": "novel_dynamic_model",
                    "entrypoint": "models/candidates/novel.py:NovelPlugin",
                }
            ),
            encoding="utf-8",
        )

    def _run(self):
        from nonlinear_agent.model_plugins.execution import run_candidate_model_tool

        return run_candidate_model_tool(
            workspace=self.root,
            manifest_path="models/candidates/novel.json",
            run_id="candidate-001",
            config={"width": 8},
            output_dir="reports/candidate-001",
            parameter_count_max=100,
            timeout_seconds=30,
        )

    def _replace(self, old: str, new: str) -> None:
        path = self.root / "models" / "candidates" / "novel.py"
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    def test_fixed_runner_returns_verified_metrics_and_artifacts(self):
        result = self._run()
        self.assertEqual(result["metrics"]["nmse_db"], -36.5)
        self.assertEqual(result["metrics"]["parameter_count"], 80.0)
        self.assertEqual(len(result["descriptor_hash"]), 64)
        self.assertEqual(len(result["artifacts"]), 2)
        for artifact in result["artifacts"]:
            self.assertTrue((self.root / artifact).is_file())
        self.assertNotIn("command", result)

    def test_runner_uses_candidate_split_and_seed_in_fixed_request(self):
        from nonlinear_agent.model_plugins.execution import run_candidate_model_tool

        result = run_candidate_model_tool(
            workspace=self.root,
            manifest_path="models/candidates/novel.json",
            run_id="candidate-config-contract",
            config={"width": 8, "train_ratio": 0.9, "seed": 7},
            output_dir="reports/candidate-config-contract",
            parameter_count_max=100,
            timeout_seconds=30,
        )

        self.assertEqual(result["metrics"]["observed_train_ratio"], 0.9)
        self.assertEqual(result["metrics"]["observed_seed"], 7.0)

    def test_rejects_nan_metric(self):
        self._replace('"nmse_db": -36.5', '"nmse_db": float("nan")')
        with self.assertRaisesRegex(ValueError, "finite"):
            self._run()

    def test_rejects_descriptor_hash_mismatch(self):
        self._replace(
            "descriptor_hash=descriptor_hash(self.descriptor)",
            'descriptor_hash="0" * 64',
        )
        with self.assertRaisesRegex(ValueError, "descriptor hash"):
            self._run()

    def test_rejects_missing_artifact(self):
        self._replace(
            "png_path.relative_to(request.workspace).as_posix(),",
            '"reports/candidate-001/missing.png",',
        )
        with self.assertRaisesRegex(FileNotFoundError, "artifact"):
            self._run()

    def test_rejects_artifact_outside_workspace(self):
        outside = self.root.parent / "outside-candidate-artifact.txt"
        outside.write_text("not evidence", encoding="utf-8")
        self.addCleanup(outside.unlink, missing_ok=True)
        self._replace(
            "png_path.relative_to(request.workspace).as_posix(),",
            '"../outside-candidate-artifact.txt",',
        )
        with self.assertRaisesRegex(ValueError, "workspace"):
            self._run()

    def test_rejects_failed_terminal_status(self):
        self._replace('status="completed"', 'status="failed"')
        with self.assertRaisesRegex(RuntimeError, "terminal status"):
            self._run()

    def test_candidate_import_cannot_mutate_parent_environment(self):
        os.environ.pop("CANDIDATE_IMPORT_LEAK", None)
        self.addCleanup(os.environ.pop, "CANDIDATE_IMPORT_LEAK", None)
        self._replace(
            "import base64",
            'import base64\nimport os\nos.environ["CANDIDATE_IMPORT_LEAK"] = "1"',
        )
        self._run()
        self.assertNotIn("CANDIDATE_IMPORT_LEAK", os.environ)

    def test_rejects_metrics_artifact_that_disagrees_with_result(self):
        self._replace(
            "return TrainingResult(",
            'metrics["nmse_db"] = -12.0\n        return TrainingResult(',
        )
        with self.assertRaisesRegex(ValueError, "metrics artifact"):
            self._run()


if __name__ == "__main__":
    unittest.main()
