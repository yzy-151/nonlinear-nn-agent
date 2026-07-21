import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.agent_workflow import (
    AgentRequest,
    ExperimentAgent,
    build_resume_change_log,
    parse_metrics_stdout,
)


class AgentWorkflowTest(unittest.TestCase):
    def test_agent_generates_plan_config_summary_and_resume_log(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            base_config = workspace / "base.yaml"
            base_config.write_text(
                yaml.safe_dump(
                    {
                        "data_path": "examples/nonlinear_fit/data/Simulation_MPDPD_Data.mat",
                        "output_dir": "reports/baseline",
                        "epochs": 5,
                        "optimizer": "adam",
                        "learning_rate": 0.001,
                    }
                ),
                encoding="utf-8",
            )

            def fake_runner(config_path: Path):
                config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                output_dir = workspace / config["output_dir"]
                output_dir.mkdir(parents=True)
                (output_dir / "psd.png").write_bytes(b"fake image")
                metrics = {
                    "status": "succeeded",
                    "samples": 16379,
                    "train_samples": 16378,
                    "evaluation_samples": 16379,
                    "epochs": config["epochs"],
                    "final_train_loss": 1.2e-6,
                    "nmse_db": -42.5,
                }
                (output_dir / "metrics.json").write_text(
                    json.dumps(metrics),
                    encoding="utf-8",
                )
                return metrics

            agent = ExperimentAgent(workspace=workspace, runner=fake_runner)
            state = agent.run(
                AgentRequest(
                    experiment_id="job-demo-001",
                    goal="Improve nonlinear NN MPDPD fitting and produce resume-ready evidence.",
                    base_config_path=base_config,
                    epochs=12,
                    learning_rate=0.0008,
                    optimizer="adam",
                    output_dir="reports/job-demo-001",
                    nmse_threshold_db=-35.0,
                )
            )

            self.assertEqual(state.status, "succeeded")
            self.assertEqual(state.metrics["nmse_db"], -42.5)
            self.assertTrue(state.plan_path.exists())
            self.assertTrue(state.config_path.exists())
            self.assertTrue(state.summary_path.exists())
            self.assertTrue(state.resume_log_path.exists())
            self.assertIn("NMSE", state.summary_path.read_text(encoding="utf-8"))
            self.assertIn("resume", state.resume_log_path.read_text(encoding="utf-8").lower())

    def test_build_resume_change_log_mentions_agent_engineering_evidence(self):
        text = build_resume_change_log(
            experiment_id="job-demo-001",
            nmse_db=-42.5,
            plan_path=Path("plans/job-demo-001.md"),
            config_path=Path("configs/job-demo-001.yaml"),
            summary_path=Path("reports/job-demo-001/agent-summary.md"),
        )

        self.assertIn("Agentic Experiment Runner", text)
        self.assertIn("-42.50 dB", text)
        self.assertIn("plans/job-demo-001.md", text)
        self.assertIn("configs/job-demo-001.yaml", text)

    def test_parse_metrics_stdout_ignores_surrounding_warnings(self):
        stdout = (
            "warning before json\n"
            "{\n"
            '  "status": "succeeded",\n'
            '  "nmse_db": -41.8\n'
            "}\n"
            "warning after json\n"
        )

        self.assertEqual(parse_metrics_stdout(stdout)["nmse_db"], -41.8)


if __name__ == "__main__":
    unittest.main()
