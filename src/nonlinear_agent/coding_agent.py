"""Coding Agent — isolated worktree + patch/test gate (v3.8.0).

The coding agent only edits a temporary git worktree (never main), only
files on an explicit whitelist, and never touches .env.local. A patch only
passes the gate when its target tests succeed.
"""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GateResult:
    passed: bool
    output: str


@dataclass(frozen=True)
class CodingResult:
    applied_files: tuple[str, ...]
    unauthorized_writes: int
    env_local_accessed: bool
    gate: GateResult | None = None


class CodingAgent:
    """Applies patches in an isolated worktree under a file whitelist."""

    def __init__(
        self,
        repo_root: Path | str,
        allowed_files: set[Path] | None = None,
    ):
        self._repo = Path(repo_root).resolve()
        self._allowed = {
            Path(path).resolve() for path in (allowed_files or set())
        }
        self._worktree: Path | None = None
        self._branch: str | None = None

    def create_worktree(self) -> Path:
        """Create a temporary worktree on its own branch (main untouched)."""
        tmp = tempfile.mkdtemp(prefix="coding-wt-")
        branch = f"coding-{uuid.uuid4().hex[:8]}"
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, tmp],
            cwd=self._repo,
            check=True,
            capture_output=True,
            text=True,
        )
        self._worktree = Path(tmp)
        self._branch = branch
        return self._worktree

    def apply_patch(
        self, worktree: Path | str, patch: dict[str, str]
    ) -> CodingResult:
        root = Path(worktree).resolve()
        if self._worktree is None or root != self._worktree.resolve():
            raise ValueError("Patches may only target this agent's owned worktree.")
        applied: list[str] = []
        unauthorized = 0
        env_accessed = False
        allowed_rel = {
            path.relative_to(self._repo).as_posix() for path in self._allowed
        }
        for rel, content in patch.items():
            rel_path = Path(rel)
            target = (root / rel).resolve()
            if any(part.lower() == ".env.local" for part in rel_path.parts):
                env_accessed = True
                continue
            try:
                target.relative_to(root)
            except ValueError:
                unauthorized += 1
                continue
            normalized_rel = target.relative_to(root).as_posix()
            if rel_path.is_absolute() or (self._allowed and normalized_rel not in allowed_rel):
                unauthorized += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            applied.append(normalized_rel)
        return CodingResult(
            applied_files=tuple(applied),
            unauthorized_writes=unauthorized,
            env_local_accessed=env_accessed,
        )

    def run_test_gate(
        self, worktree: Path | str, command: list[str], timeout_seconds: float = 120.0
    ) -> GateResult:
        try:
            proc = subprocess.run(
                command,
                cwd=str(worktree),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return GateResult(passed=False, output=f"gate timeout: {exc}")
        output = (proc.stdout or "") + (proc.stderr or "")
        return GateResult(passed=proc.returncode == 0, output=output)

    def cleanup_worktree(self) -> None:
        if self._worktree is not None:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(self._worktree)],
                cwd=self._repo,
                capture_output=True,
                text=True,
            )
        if self._branch is not None:
            subprocess.run(
                ["git", "branch", "-D", self._branch],
                cwd=self._repo,
                capture_output=True,
                text=True,
            )
        self._worktree = None
        self._branch = None
