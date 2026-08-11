import sys
import unittest
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.cli import build_parser, main


class CliTest(unittest.TestCase):
    def test_multi_agent_parser_exposes_three_by_three_final_evaluation_defaults(self):
        args = build_parser().parse_args(["multi-agent", "--provider", "deepseek"])

        self.assertEqual(args.command, "multi-agent")
        self.assertEqual(args.rounds, 3)
        self.assertEqual(args.experiments_per_round, 3)
        self.assertTrue(args.final_evaluation)
        self.assertEqual(args.nmse_threshold_db, -35.0)

    def test_parser_exposes_operational_subcommands(self):
        parser = build_parser()

        commands = parser.parse_args(["run", "--provider", "fake", "--max-rounds", "0"])
        benchmark = parser.parse_args(["benchmark", "--output-dir", "benchmarks/check"])
        diagnostics = parser.parse_args(["diagnostics", "--output", "docs/diagnostics/check.md"])
        dashboard = parser.parse_args(["dashboard", "--output", "docs/diagnostics/check.html"])
        serve = parser.parse_args(["serve", "--host", "127.0.0.1", "--port", "8011"])

        self.assertEqual(commands.command, "run")
        self.assertEqual(benchmark.command, "benchmark")
        self.assertEqual(diagnostics.command, "diagnostics")
        self.assertEqual(dashboard.command, "dashboard")
        self.assertEqual(serve.command, "serve")

    def test_run_parser_exposes_action_mode_and_action_budget(self):
        args = build_parser().parse_args([
            "run", "--mode", "action", "--provider", "fake", "--max-actions", "7",
        ])

        self.assertEqual(args.mode, "action")
        self.assertEqual(args.max_actions, 7)

    def test_parser_exposes_independent_agent_task_benchmark(self):
        args = build_parser().parse_args([
            "agent-benchmark",
            "--provider", "scripted",
            "--attempts", "3",
            "--output-dir", "benchmarks/agent-tasks-v1",
        ])

        self.assertEqual(args.command, "agent-benchmark")
        self.assertEqual(args.provider, "scripted")
        self.assertEqual(args.attempts, 3)

    def test_fake_action_mode_can_stop_without_starting_training(self):
        stop_action = (
            '{"type":"stop","action_id":"safe-stop",'
            '"reason":"test complete","caused_by_event_ids":[]}'
        )
        with TemporaryDirectory() as tmpdir:
            exit_code = main([
                "run",
                "--mode", "action",
                "--provider", "fake",
                "--workspace", tmpdir,
                "--fake-action", stop_action,
                "--max-actions", "2",
            ])

        self.assertEqual(exit_code, 0)

    def test_diagnostics_command_writes_markdown(self):
        with TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "diagnostics.md"

            exit_code = main(["diagnostics", "--workspace", tmpdir, "--output", str(output)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(output.exists())
            self.assertIn("Agent Runtime Diagnostics Dashboard", output.read_text(encoding="utf-8"))

    def test_dashboard_command_writes_html(self):
        with TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "dashboard.html"

            exit_code = main(["dashboard", "--workspace", tmpdir, "--output", str(output)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(output.exists())
            html = output.read_text(encoding="utf-8")
            self.assertIn("<!doctype html>", html.lower())
            self.assertIn("Agent Runtime Dashboard", html)

    def test_root_agent_script_exposes_cli_help(self):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "agent.py"), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Unified CLI", result.stdout)


if __name__ == "__main__":
    unittest.main()
