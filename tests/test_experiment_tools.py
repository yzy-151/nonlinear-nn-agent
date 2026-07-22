import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.experiment_tools import (
    build_experiment_tool_registry,
    generate_config_tool,
    run_training_tool,
    verify_artifacts_tool,
    write_report_tool,
)


class ExperimentToolsTest(unittest.TestCase):
    def test_generate_config_tool_writes_overridden_yaml(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            base_config = workspace / "base.yaml"
            base_config.write_text(
                yaml.safe_dump({"epochs": 10, "learning_rate": 0.001, "output_dir": "reports/base"}),
                encoding="utf-8",
            )

            result = generate_config_tool(
                workspace=workspace,
                base_config_path="base.yaml",
                experiment_id="harness-demo",
                overrides={"epochs": 0, "output_dir": "reports/harness-demo"},
            )

            config_path = workspace / result["config_path"]
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["epochs"], 0)
            self.assertEqual(config["learning_rate"], 0.001)
            self.assertEqual(config["output_dir"], "reports/harness-demo")
            self.assertEqual(result["artifacts"], ["configs/harness-demo.yaml"])

    def test_run_training_tool_captures_metrics_and_process_output(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            script = workspace / "train_stub.py"
            script.write_text(
                "import json, pathlib\n"
                "pathlib.Path('reports/demo').mkdir(parents=True, exist_ok=True)\n"
                "pathlib.Path('reports/demo/metrics.json').write_text(json.dumps({'nmse_db': -39.5, 'status': 'succeeded'}))\n"
                "pathlib.Path('reports/demo/psd.png').write_bytes(b'png')\n"
                "print(json.dumps({'status': 'succeeded', 'nmse_db': -39.5, 'output_dir': 'reports/demo'}))\n",
                encoding="utf-8",
            )
            config = workspace / "config.yaml"
            config.write_text("output_dir: reports/demo\n", encoding="utf-8")

            result = run_training_tool(
                workspace=workspace,
                config_path="config.yaml",
                command=[sys.executable, "train_stub.py"],
            )

            self.assertEqual(result["metrics"]["nmse_db"], -39.5)
            self.assertEqual(result["returncode"], 0)
            self.assertEqual(result["artifacts"], ["reports/demo/metrics.json", "reports/demo/psd.png"])
            self.assertGreaterEqual(result["elapsed_seconds"], 0.0)

    def test_verify_artifacts_tool_enforces_nmse_threshold_and_psd(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            output_dir = workspace / "reports" / "demo"
            output_dir.mkdir(parents=True)
            (output_dir / "metrics.json").write_text(json.dumps({"nmse_db": -37.0}), encoding="utf-8")
            (output_dir / "psd.png").write_bytes(b"png")

            result = verify_artifacts_tool(
                workspace=workspace,
                output_dir="reports/demo",
                nmse_threshold_db=-35.0,
            )

            self.assertEqual(result["metrics"]["nmse_db"], -37.0)
            self.assertEqual(result["artifacts"], ["reports/demo/metrics.json", "reports/demo/psd.png"])
            self.assertIn("NMSE", result["context_summary"])

    def test_write_report_tool_creates_hiring_facing_summary(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            result = write_report_tool(
                workspace=workspace,
                session_id="harness-demo",
                metrics={"nmse_db": -37.0},
                artifacts=["reports/demo/psd.png"],
            )

            report_path = workspace / result["artifacts"][0]
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("Agent Harness Report", text)
            self.assertIn("-37.0000 dB", text)
            self.assertIn("trace", text.lower())

    def test_build_experiment_tool_registry_registers_expected_tools(self):
        registry = build_experiment_tool_registry(workspace=Path("."))

        self.assertIn("generate_config", registry.tool_names())
        self.assertIn("run_training", registry.tool_names())
        self.assertIn("verify_artifacts", registry.tool_names())
        self.assertIn("write_report", registry.tool_names())


if __name__ == "__main__":
    unittest.main()
