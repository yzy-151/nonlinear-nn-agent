import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.replay import build_replay_markdown, load_trace_events, summarize_trace, write_replay_report


class ReplayTest(unittest.TestCase):
    def test_summarize_trace_counts_tools_latency_metrics_and_errors(self):
        events = [
            {"event_type": "start", "session_id": "s1", "payload": {}},
            {"event_type": "tool_end", "session_id": "s1", "tool": "generate_config", "latency_ms": 10.0, "payload": {"attempts": 1}},
            {"event_type": "tool_end", "session_id": "s1", "tool": "run_training", "latency_ms": 25.0, "payload": {"attempts": 2}},
            {"event_type": "metric", "session_id": "s1", "payload": {"name": "nmse_db", "value": -38.2}},
            {"event_type": "error", "session_id": "s1", "tool": "verify_artifacts", "error": "missing psd", "payload": {"attempts": 1}},
        ]

        summary = summarize_trace(events)

        self.assertEqual(summary.session_id, "s1")
        self.assertEqual(summary.tool_calls, 2)
        self.assertEqual(summary.total_latency_ms, 35.0)
        self.assertEqual(summary.retry_count, 1)
        self.assertEqual(summary.metrics["nmse_db"], -38.2)
        self.assertEqual(summary.errors, ["verify_artifacts: missing psd"])

    def test_write_replay_report_reads_jsonl_and_writes_markdown(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            trace_path = workspace / "traces" / "s1.jsonl"
            trace_path.parent.mkdir(parents=True)
            rows = [
                {"event_type": "tool_end", "session_id": "s1", "tool": "run_training", "latency_ms": 20.0, "payload": {"attempts": 1}},
                {"event_type": "metric", "session_id": "s1", "payload": {"name": "nmse_db", "value": -40.1}},
            ]
            trace_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            loaded = load_trace_events(trace_path)
            markdown = build_replay_markdown(summarize_trace(loaded))
            report_path = write_replay_report(trace_path, workspace / "reports" / "s1" / "replay.md")

            self.assertEqual(len(loaded), 2)
            self.assertIn("Trace Replay Report", markdown)
            self.assertTrue(report_path.exists())
            self.assertIn("run_training", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
