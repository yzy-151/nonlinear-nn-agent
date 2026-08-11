"""TDD tests for v3.8.0 Coding Agent: isolated worktree + patch/test gate."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
    (root / "module.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_module.py").write_text(
        "import sys\nimport unittest\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
        "from module import answer\n\n"
        "class ModuleTest(unittest.TestCase):\n"
        "    def test_answer(self):\n"
        "        self.assertEqual(answer(), 41)\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    (root / ".env.local").write_text("DEEPSEEK_API_KEY=sk-secret\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)


class TestCodingAgent(unittest.TestCase):
    def _repo(self):
        tmp = TemporaryDirectory()
        root = Path(tmp.name)
        _init_repo(root)
        self.addCleanup(tmp.cleanup)
        return root

    def test_worktree_is_isolated_from_main(self):
        from nonlinear_agent.coding_agent import CodingAgent

        root = self._repo()
        agent = CodingAgent(repo_root=root)
        worktree = agent.create_worktree()
        self.addCleanup(agent.cleanup_worktree)
        self.assertNotEqual(worktree.resolve(), root.resolve())
        # main 工作区不受 worktree 修改影响
        (worktree / "module.py").write_text(
            "def answer():\n    return 42\n", encoding="utf-8"
        )
        self.assertIn("return 41", (root / "module.py").read_text(encoding="utf-8"))

    def test_unauthorized_file_write_count_zero(self):
        from nonlinear_agent.coding_agent import CodingAgent

        root = self._repo()
        agent = CodingAgent(
            repo_root=root,
            allowed_files={root / "module.py"},
        )
        worktree = agent.create_worktree()
        self.addCleanup(agent.cleanup_worktree)
        result = agent.apply_patch(
            worktree,
            {
                "module.py": "def answer():\n    return 42\n",
                "evil.py": "import os\nos.system('rm -rf /')\n",
            },
        )
        self.assertEqual(result.unauthorized_writes, 1)
        self.assertFalse((worktree / "evil.py").exists())
        self.assertEqual(result.applied_files, ("module.py",))

    def test_patch_path_cannot_escape_worktree(self):
        from nonlinear_agent.coding_agent import CodingAgent

        root = self._repo()
        agent = CodingAgent(repo_root=root)
        worktree = agent.create_worktree()
        self.addCleanup(agent.cleanup_worktree)
        outside = worktree.parent / "coding-agent-escape.py"
        self.addCleanup(outside.unlink, missing_ok=True)

        result = agent.apply_patch(worktree, {"../coding-agent-escape.py": "x = 1\n"})

        self.assertEqual(result.unauthorized_writes, 1)
        self.assertFalse(outside.exists())

    def test_env_local_never_readable_by_coding_agent(self):
        from nonlinear_agent.coding_agent import CodingAgent

        root = self._repo()
        agent = CodingAgent(repo_root=root)
        worktree = agent.create_worktree()
        self.addCleanup(agent.cleanup_worktree)
        result = agent.apply_patch(
            worktree, {".env.local": "DEEPSEEK_API_KEY=stolen"}
        )
        self.assertTrue(result.env_local_accessed)
        self.assertFalse((worktree / ".env.local").read_text(encoding="utf-8").startswith("DEEPSEEK_API_KEY=stolen"))

    def test_patch_cannot_escape_worktree(self):
        from nonlinear_agent.coding_agent import CodingAgent

        root = self._repo()
        agent = CodingAgent(repo_root=root)
        worktree = agent.create_worktree()
        self.addCleanup(agent.cleanup_worktree)
        escaped = worktree.parent / "escaped.py"
        escaped.unlink(missing_ok=True)
        self.addCleanup(escaped.unlink, missing_ok=True)

        result = agent.apply_patch(worktree, {"../escaped.py": "secret = True\n"})

        self.assertEqual(result.unauthorized_writes, 1)
        self.assertFalse(escaped.exists())
        self.assertEqual(result.applied_files, ())

    def test_patch_rejects_a_root_other_than_the_owned_worktree(self):
        from nonlinear_agent.coding_agent import CodingAgent

        root = self._repo()
        agent = CodingAgent(repo_root=root)
        agent.create_worktree()
        self.addCleanup(agent.cleanup_worktree)

        with self.assertRaisesRegex(ValueError, "owned worktree"):
            agent.apply_patch(root, {"module.py": "def answer():\n    return 99\n"})

    def test_test_gate_rejects_failing_patch(self):
        from nonlinear_agent.coding_agent import CodingAgent

        root = self._repo()
        agent = CodingAgent(
            repo_root=root,
            allowed_files={root / "module.py"},
        )
        worktree = agent.create_worktree()
        self.addCleanup(agent.cleanup_worktree)
        agent.apply_patch(
            worktree, {"module.py": "def answer():\n    return 99\n"}
        )
        gate = agent.run_test_gate(
            worktree, [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
        )
        self.assertFalse(gate.passed)
        self.assertIn("FAILED", gate.output)

    def test_test_gate_accepts_fixed_patch(self):
        from nonlinear_agent.coding_agent import CodingAgent

        root = self._repo()
        agent = CodingAgent(
            repo_root=root,
            allowed_files={root / "module.py"},
        )
        worktree = agent.create_worktree()
        self.addCleanup(agent.cleanup_worktree)
        agent.apply_patch(
            worktree, {"module.py": "def answer():\n    return 40 + 1\n"}
        )
        gate = agent.run_test_gate(
            worktree, [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
        )
        self.assertTrue(gate.passed)


class TestCodingFixtures(unittest.TestCase):
    """v3.8.0 acceptance: >=9 of 10 coding fixtures pass the gate."""

    FIXTURES = [
        ("equivalent-add", {"module.py": "def answer():\n    return 40 + 1\n"}, True, ()),
        ("equivalent-sub", {"module.py": "def answer():\n    return 42 - 1\n"}, True, ()),
        ("equivalent-mul", {"module.py": "def answer():\n    return 20 * 2 + 1\n"}, True, ()),
        ("equivalent-sum", {"module.py": "def answer():\n    return sum([40, 1])\n"}, True, ()),
        ("equivalent-float", {"module.py": "def answer():\n    return 41.0\n"}, True, ()),
        ("equivalent-int", {"module.py": "def answer():\n    return int(41)\n"}, True, ()),
        ("equivalent-str", {"module.py": "def answer():\n    return len('a' * 41)\n"}, True, ()),
        ("equivalent-lambda", {"module.py": "f = lambda: 41\ndef answer():\n    return f()\n"}, True, ()),
        ("new-helper", {
            "module.py": "from helper import forty_one\ndef answer():\n    return forty_one()\n",
            "helper.py": "def forty_one():\n    return 41\n",
        }, True, ("helper.py",)),
        ("wrong-value", {"module.py": "def answer():\n    return 99\n"}, False, ()),
    ]

    def test_at_least_nine_of_ten_fixtures_pass_gate(self):
        from nonlinear_agent.coding_agent import CodingAgent

        passed = 0
        results = []
        for name, patch, expected_pass, extra_allowed in self.FIXTURES:
            with TemporaryDirectory() as td:
                root = Path(td)
                _init_repo(root)
                allowed = {root / "module.py"}
                allowed.update(root / extra for extra in extra_allowed)
                agent = CodingAgent(
                    repo_root=root,
                    allowed_files=allowed,
                )
                worktree = agent.create_worktree()
                agent.apply_patch(worktree, patch)
                gate = agent.run_test_gate(
                    worktree,
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                )
                agent.cleanup_worktree()
            self.assertEqual(
                gate.passed,
                expected_pass,
                f"fixture {name} expected pass={expected_pass}",
            )
            if gate.passed:
                passed += 1
            results.append((name, gate.passed))
        self.assertGreaterEqual(
            passed, 9, f"coding fixtures passed {passed}/9, {results}"
        )


if __name__ == "__main__":
    unittest.main()
