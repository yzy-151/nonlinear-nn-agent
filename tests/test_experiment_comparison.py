import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.comparison import (
    ExperimentRecord,
    build_comparison_markdown,
    load_experiment_record,
    rank_experiments,
    write_comparison_report,
)


class ExperimentComparisonTest(unittest.TestCase):
    def test_load_experiment_record_reads_metrics_and_config(self):
        with TemporaryDirectory() as tmpdir:
            experiment_dir = Path(tmpdir) / "reports" / "exp-a"
            experiment_dir.mkdir(parents=True)
            (experiment_dir / "metrics.json").write_text(
                json.dumps({"nmse_db": -41.8, "epochs": 240, "status": "succeeded"}),
                encoding="utf-8",
            )
            (experiment_dir / "resolved_config.yaml").write_text(
                yaml.safe_dump({"optimizer": "adam", "learning_rate": 0.0008}),
                encoding="utf-8",
            )
            (experiment_dir / "psd.png").write_bytes(b"fake image")

            record = load_experiment_record(experiment_dir)

            self.assertEqual(record.name, "exp-a")
            self.assertEqual(record.nmse_db, -41.8)
            self.assertEqual(record.optimizer, "adam")
            self.assertEqual(record.learning_rate, 0.0008)
            self.assertTrue(record.has_psd)

    def test_rank_experiments_sorts_lower_nmse_first(self):
        records = [
            ExperimentRecord("weak", -26.0, 2, "adam", 0.001, True, Path("a")),
            ExperimentRecord("best", -41.8, 240, "adam", 0.0008, True, Path("b")),
        ]

        ranked = rank_experiments(records)

        self.assertEqual([record.name for record in ranked], ["best", "weak"])

    def test_build_comparison_markdown_contains_resume_summary(self):
        records = [
            ExperimentRecord("best", -41.8, 240, "adam", 0.0008, True, Path("reports/best")),
            ExperimentRecord("dry-run", -26.9, 2, "adam", 0.001, True, Path("reports/dry-run")),
        ]

        markdown = build_comparison_markdown(records)

        self.assertIn("| best | -41.8000 | 240 | adam | 0.0008 | yes |", markdown)
        self.assertIn("Best NMSE: -41.80 dB", markdown)
        self.assertIn("resume", markdown.lower())

    def test_write_comparison_report_creates_report_file(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            report_path = write_comparison_report(
                records=[
                    ExperimentRecord("best", -41.8, 240, "adam", 0.0008, True, Path("reports/best"))
                ],
                output_path=workspace / "docs" / "experiment-comparison.md",
            )

            self.assertTrue(report_path.exists())
            self.assertIn("Experiment Comparison", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
