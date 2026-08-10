import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_tests.py"
SPEC = importlib.util.spec_from_file_location("run_tests", SCRIPT_PATH)
run_tests = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_tests)


class TestProfilesTest(unittest.TestCase):
    def test_fast_profile_targets_agent_evidence_modules(self):
        command = run_tests.build_command("fast")

        self.assertIn("tests.test_action_loop", command)
        self.assertIn("tests.test_agent_benchmark_cases", command)
        self.assertNotIn("discover", command)

    def test_full_profile_discovers_complete_offline_suite(self):
        command = run_tests.build_command("full")

        self.assertEqual(command[-2:], ["discover", "tests"])

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            run_tests.build_command("network")


if __name__ == "__main__":
    unittest.main()
