import sys
import unittest
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.cli import build_parser, main


class CliTest(unittest.TestCase):
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
