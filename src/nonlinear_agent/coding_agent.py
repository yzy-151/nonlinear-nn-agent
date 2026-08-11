"""Coding Agent — isolated worktree + patch/test gate (v3.8.0).

The coding agent only edits a temporary git worktree (never main), only
files on an explicit whitelist, and never touches .env.local. A patch only
passes the gate when its target tests succeed.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_FORBIDDEN_IMPORTS = {
    "ctypes",
    "http",
    "importlib",
    "multiprocessing",
    "os",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "urllib",
}
_FORBIDDEN_CALLS = {"compile", "eval", "exec", "input", "__import__"}
_FORBIDDEN_ATTRIBUTES = {
    "connect",
    "popen",
    "remove",
    "rmtree",
    "spawn",
    "system",
}
_SECRET_VALUE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")


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


@dataclass(frozen=True)
class CodingTaskSpec:
    """Bounded request for one LLM-generated candidate model plugin."""

    task_id: str
    objective: str
    candidate_name: str
    config: dict[str, Any]
    parameter_count_max: int
    smoke_timeout_seconds: float = 120.0
    constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.task_id):
            raise ValueError("task_id contains unsupported characters")
        if not _IDENTIFIER.fullmatch(self.candidate_name):
            raise ValueError("candidate_name contains unsupported characters")
        if not self.objective.strip():
            raise ValueError("objective must not be empty")
        if self.parameter_count_max <= 0:
            raise ValueError("parameter_count_max must be positive")
        if self.smoke_timeout_seconds <= 0:
            raise ValueError("smoke_timeout_seconds must be positive")


@dataclass(frozen=True)
class CodeFile:
    path: str
    content: str


@dataclass(frozen=True)
class CodeChangePlan:
    """Full replacement file set returned by the coding model."""

    task_id: str
    candidate_name: str
    rationale: str
    manifest_path: str
    files: tuple[CodeFile, ...]

    @classmethod
    def from_json(cls, response: str, task: CodingTaskSpec) -> "CodeChangePlan":
        stripped = response.strip()
        if not stripped.startswith("{") or not stripped.endswith("}"):
            raise ValueError("coding response must be one JSON object without Markdown")
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"coding response is invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("coding response must be a JSON object")
        required = {
            "schema_version",
            "task_id",
            "candidate_name",
            "rationale",
            "manifest_path",
            "files",
        }
        missing = sorted(required - set(payload))
        unknown = sorted(set(payload) - required)
        if missing:
            raise ValueError(f"coding response missing fields: {', '.join(missing)}")
        if unknown:
            raise ValueError(f"coding response has unknown fields: {', '.join(unknown)}")
        if payload["schema_version"] != 1:
            raise ValueError("coding response schema_version must be 1")
        if payload["task_id"] != task.task_id:
            raise ValueError("coding response task_id does not match request")
        if payload["candidate_name"] != task.candidate_name:
            raise ValueError("coding response candidate_name does not match request")
        raw_files = payload["files"]
        if not isinstance(raw_files, dict) or not raw_files:
            raise ValueError("coding response files must be a non-empty object")
        if len(raw_files) > 12:
            raise ValueError("coding response contains too many files")

        base = PurePosixPath("models") / "candidates" / task.candidate_name
        files: list[CodeFile] = []
        for raw_path, content in raw_files.items():
            path = _candidate_relative_path(raw_path, base)
            if path.suffix not in {".py", ".json"}:
                raise ValueError("candidate files must be Python or JSON")
            if not isinstance(content, str):
                raise ValueError(f"candidate file content must be text: {path}")
            if len(content.encode("utf-8")) > 250_000:
                raise ValueError(f"candidate file is too large: {path}")
            files.append(CodeFile(path.as_posix(), content))

        manifest_path = _candidate_relative_path(payload["manifest_path"], base)
        file_map = {item.path: item.content for item in files}
        if manifest_path.as_posix() not in file_map:
            raise ValueError("manifest_path must identify one returned file")
        try:
            manifest = json.loads(file_map[manifest_path.as_posix()])
        except json.JSONDecodeError as exc:
            raise ValueError(f"candidate manifest is invalid JSON: {exc}") from exc
        if not isinstance(manifest, dict):
            raise ValueError("candidate manifest must be an object")
        manifest["schema_version"] = 1
        manifest["name"] = task.candidate_name
        entrypoint = str(manifest.get("entrypoint", ""))
        if ":" in entrypoint:
            source_path, class_name = entrypoint.rsplit(":", 1)
        else:
            class_hint = entrypoint if entrypoint.isidentifier() else ""
            inferred: list[tuple[str, str]] = []
            for path, content in file_map.items():
                if not path.endswith(".py"):
                    continue
                try:
                    tree = ast.parse(content)
                except SyntaxError:
                    continue
                for node in tree.body:
                    if not isinstance(node, ast.ClassDef):
                        continue
                    methods = {
                        item.name
                        for item in node.body
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    }
                    if node.name == class_hint or {"train", "estimate_parameters"}.issubset(methods):
                        inferred.append((path, node.name))
            inferred = list(dict.fromkeys(inferred))
            if len(inferred) != 1:
                raise ValueError("candidate manifest entrypoint is invalid")
            source_path, class_name = inferred[0]
        if source_path not in file_map:
            source_matches = [
                path
                for path in file_map
                if path.endswith(".py")
                and PurePosixPath(path).name == PurePosixPath(source_path).name
            ]
            if len(source_matches) == 1:
                source_path = source_matches[0]
            else:
                raise ValueError("candidate entrypoint source must be returned in files")
        if not source_path.endswith(".py"):
            raise ValueError("candidate entrypoint source must be returned in files")
        if not class_name.isidentifier():
            raise ValueError("candidate entrypoint class name is invalid")
        manifest["entrypoint"] = f"{source_path}:{class_name}"
        normalized_manifest = json.dumps(
            manifest, ensure_ascii=False, sort_keys=True
        )
        files = [
            CodeFile(
                item.path,
                normalized_manifest
                if item.path == manifest_path.as_posix()
                else item.content,
            )
            for item in files
        ]
        if not any(item.path.endswith(".py") for item in files):
            raise ValueError("candidate response must include Python source")
        return cls(
            task_id=task.task_id,
            candidate_name=task.candidate_name,
            rationale=str(payload["rationale"]),
            manifest_path=manifest_path.as_posix(),
            files=tuple(files),
        )


@dataclass(frozen=True)
class CodingWorkflowResult:
    passed: bool
    task_id: str
    candidate_name: str
    worktree: str
    manifest_path: str
    applied_files: tuple[str, ...]
    attempt_count: int
    failure_facts: tuple[str, ...]
    validation: dict[str, Any]
    metrics: dict[str, float]
    artifacts: tuple[str, ...]
    trace_path: str


class CandidateGateError(ValueError):
    def __init__(self, stage: str, facts: list[str]):
        self.stage = stage
        self.facts = tuple(facts)
        super().__init__(f"{stage} gate: {'; '.join(facts)}")


def _candidate_relative_path(value: Any, base: PurePosixPath) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("candidate path must use workspace-relative POSIX syntax")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path == PurePosixPath("."):
        raise ValueError("candidate path must remain in its candidate directory")
    candidate_root = ("models", "candidates")
    if path.parts[:2] == candidate_root and len(path.parts) >= 4:
        path = base.joinpath(*path.parts[3:])
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise ValueError(
            "candidate path must remain in its candidate directory"
        ) from exc
    return path


def inspect_candidate_source(source: str) -> list[str]:
    """Extract deterministic syntax and capability violations from Python source."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"SyntaxError line {exc.lineno}: {exc.msg}"]

    errors: list[str] = []
    for statement in tree.body:
        if isinstance(statement, ast.Expr) and not (
            isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ) and not _is_safe_backend_selection(statement.value):
            errors.append(
                f"top-level executable statement is not allowed at line {statement.lineno}"
            )
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            try:
                ast.literal_eval(value)
            except (ValueError, TypeError):
                errors.append(
                    f"top-level assignment must be a literal at line {statement.lineno}"
                )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in _FORBIDDEN_IMPORTS:
                    errors.append(f"forbidden import: {root}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root in _FORBIDDEN_IMPORTS:
                errors.append(f"forbidden import: {root}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALLS:
                errors.append(f"forbidden call: {node.func.id}")
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in _FORBIDDEN_ATTRIBUTES
            ):
                errors.append(f"forbidden capability call: {node.func.attr}")
    return list(dict.fromkeys(errors))


def _is_safe_backend_selection(value: ast.expr) -> bool:
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and isinstance(value.func.value, ast.Name)
        and value.func.value.id == "matplotlib"
        and value.func.attr == "use"
        and len(value.args) == 1
        and isinstance(value.args[0], ast.Constant)
        and value.args[0].value == "Agg"
        and not value.keywords
    )


class CodingAgent:
    """Applies patches in an isolated worktree under a file whitelist."""

    def __init__(
        self,
        repo_root: Path | str,
        allowed_files: set[Path] | None = None,
        llm_client: Any | None = None,
        model_router: Any | None = None,
        model_role: str = "coding",
        temp_root: Path | str | None = None,
    ):
        self._repo = Path(repo_root).resolve()
        self._allowed = {
            Path(path).resolve() for path in (allowed_files or set())
        }
        self._llm = llm_client
        self._model_router = model_router
        self._model_role = model_role
        self._temp_root = Path(temp_root).resolve() if temp_root is not None else None
        self._worktree: Path | None = None
        self._branch: str | None = None

    def create_worktree(self) -> Path:
        """Create a temporary worktree on its own branch (main untouched)."""
        if self._temp_root is not None:
            self._temp_root.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.mkdtemp(
            prefix="coding-wt-",
            dir=str(self._temp_root) if self._temp_root is not None else None,
        )
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

    def generate_candidate(
        self,
        task: CodingTaskSpec,
        max_repairs: int = 2,
    ) -> CodingWorkflowResult:
        """Ask the coding model for a complete plugin and pass fixed gates."""
        if max_repairs < 0 or max_repairs > 5:
            raise ValueError("max_repairs must be between 0 and 5")
        if self._llm is None and self._model_router is None:
            raise RuntimeError("CodingAgent requires an LLM client or ModelRouter")
        worktree = self._worktree or self.create_worktree()
        trace_relative = (
            Path("runs") / "coding-agent" / task.task_id / "coding-trace.json"
        )
        attempts: list[dict[str, Any]] = []
        failure_facts: tuple[str, ...] = ()
        all_failure_facts: list[str] = []
        last_manifest = ""
        last_applied: tuple[str, ...] = ()

        for attempt_index in range(max_repairs + 1):
            prompt = _build_coding_prompt(task, attempt_index, failure_facts)
            response = ""
            attempt_files: tuple[CodeFile, ...] = ()
            try:
                response = self._complete(prompt)
                plan = CodeChangePlan.from_json(response, task)
                attempt_files = plan.files
                static_errors: list[str] = []
                for code_file in plan.files:
                    if code_file.path.endswith(".py"):
                        static_errors.extend(
                            f"{code_file.path}: {error}"
                            for error in inspect_candidate_source(code_file.content)
                        )
                if static_errors:
                    raise CandidateGateError("static", static_errors)

                self._clear_candidate_directory(worktree, task.candidate_name)
                patch_result = self.apply_patch(
                    worktree,
                    {item.path: item.content for item in plan.files},
                )
                if patch_result.unauthorized_writes or patch_result.env_local_accessed:
                    raise CandidateGateError(
                        "write",
                        [
                            "candidate attempted a write outside its authorized file set"
                        ],
                    )
                last_manifest = plan.manifest_path
                last_applied = patch_result.applied_files

                from nonlinear_agent.model_plugins.execution import (
                    run_candidate_model_tool,
                    validate_candidate_model_tool,
                )

                validation = validate_candidate_model_tool(
                    workspace=worktree,
                    manifest_path=plan.manifest_path,
                    config=task.config,
                    parameter_count_max=task.parameter_count_max,
                )
                smoke = run_candidate_model_tool(
                    workspace=worktree,
                    manifest_path=plan.manifest_path,
                    run_id=f"{task.task_id}-attempt-{attempt_index + 1}",
                    config=task.config,
                    output_dir=(
                        Path("runs")
                        / "coding-agent"
                        / task.task_id
                        / f"smoke-{attempt_index + 1}"
                    ),
                    parameter_count_max=task.parameter_count_max,
                    timeout_seconds=task.smoke_timeout_seconds,
                )
                attempts.append(
                    _trace_attempt(
                        attempt_index,
                        prompt,
                        response,
                        "passed",
                        (),
                        plan.files,
                    )
                )
                _write_trace(worktree / trace_relative, task, attempts, "passed")
                return CodingWorkflowResult(
                    passed=True,
                    task_id=task.task_id,
                    candidate_name=task.candidate_name,
                    worktree=str(worktree),
                    manifest_path=plan.manifest_path,
                    applied_files=patch_result.applied_files,
                    attempt_count=attempt_index + 1,
                    failure_facts=tuple(all_failure_facts),
                    validation=validation,
                    metrics={
                        str(name): float(value)
                        for name, value in smoke["metrics"].items()
                    },
                    artifacts=tuple(str(item) for item in smoke["artifacts"]),
                    trace_path=trace_relative.as_posix(),
                )
            except Exception as exc:
                failure_facts = _facts_from_exception(exc)
                all_failure_facts.extend(failure_facts)
                attempts.append(
                    _trace_attempt(
                        attempt_index,
                        prompt,
                        response,
                        "failed",
                        failure_facts,
                        attempt_files,
                    )
                )

        _write_trace(worktree / trace_relative, task, attempts, "failed")
        return CodingWorkflowResult(
            passed=False,
            task_id=task.task_id,
            candidate_name=task.candidate_name,
            worktree=str(worktree),
            manifest_path=last_manifest,
            applied_files=last_applied,
            attempt_count=len(attempts),
            failure_facts=tuple(all_failure_facts),
            validation={},
            metrics={},
            artifacts=(),
            trace_path=trace_relative.as_posix(),
        )

    def _complete(self, prompt: str) -> str:
        if self._model_router is not None:
            return str(self._model_router.complete(self._model_role, prompt))
        return str(self._llm.complete(prompt))

    @staticmethod
    def _clear_candidate_directory(worktree: Path, candidate_name: str) -> None:
        candidate_dir = (
            worktree / "models" / "candidates" / candidate_name
        ).resolve()
        allowed_root = (worktree / "models" / "candidates").resolve()
        candidate_dir.relative_to(allowed_root)
        if candidate_dir.is_dir():
            shutil.rmtree(candidate_dir)

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


def _build_coding_prompt(
    task: CodingTaskSpec,
    attempt_index: int,
    failure_facts: tuple[str, ...],
) -> str:
    task_payload = {
        "task_id": task.task_id,
        "objective": task.objective,
        "candidate_name": task.candidate_name,
        "config": task.config,
        "parameter_count_max": task.parameter_count_max,
        "constraints": list(task.constraints),
    }
    repair = (
        "No prior failure."
        if not failure_facts
        else "Previous gate facts to repair:\n- " + "\n- ".join(failure_facts)
    )
    return f"""You are the Coding Agent for a nonlinear-model experiment harness.
Return exactly one JSON object. Do not use Markdown or code fences.

Task:
{json.dumps(task_payload, ensure_ascii=False, sort_keys=True)}

Attempt: {attempt_index + 1}
{repair}

Return a complete replacement candidate package, not only a model class. The
Python entrypoint class must implement ModelPlugin with:
- descriptor: ModelDescriptor with generic architecture nodes and edges
- estimate_parameters(config) -> non-negative int
- train(TrainingRequest) -> TrainingResult
Import ArchitectureNode, ArchitectureEdge, ModelDescriptor, TrainingResult,
and descriptor_hash from nonlinear_agent.model_plugins.contracts. The class
attribute descriptor must be an actual ModelDescriptor instance whose nodes
and edges are tuples of ArchitectureNode and ArchitectureEdge instances; never
use a plain dict as descriptor. Return an actual TrainingResult instance.
Use the exact public constructor fields:
- ArchitectureNode(node_id, label, operation, details={{}}), never id=
- ArchitectureEdge(source, target, label="")
- ModelDescriptor(name, version, training_mode, config_schema, nodes, edges)
- TrainingResult(status, metrics, artifacts, descriptor_hash)
TrainingRequest exposes exactly request.run_id, request.workspace,
request.config, request.output_dir, request.data_file, request.train_ratio, and
request.seed. Load the shared MAT file from Path(request.workspace) /
request.data_file with scipy.io.loadmat; it contains MAT keys "x" and "d".
Scale d to x power as the existing nonlinear experiment does, and use the
fixed request.train_ratio split. x and d are complex one-dimensional signals:
never cast a complex array directly to float or discard its imaginary part.
Represent real/imaginary components explicitly, use causal memory features
when the hypothesis requires them, reconstruct a complex prediction, and
compute held-out NMSE as 10*log10(mean(abs(prediction-target)**2) /
mean(abs(target)**2)). Do not expect train_data, test_data, inputs, targets, or
another hidden request field. training_mode must be exactly one of
"gradient", "closed_form", or "custom". Keep the complete plugin.py concise
(prefer under 7000 characters) so the JSON response is not truncated.
The train method must execute the candidate's own fitting procedure and write
both metrics.json and a valid psd.png below request.workspace/request.output_dir.
It must return finite nmse_db and parameter_count metrics, artifact paths
relative to request.workspace, and descriptor_hash(descriptor).
TrainingResult status must be "completed". artifacts must be a tuple/list of
the workspace-relative metrics.json and psd.png paths, not a name-to-path map.

All files must stay below models/candidates/{task.candidate_name}/. The plugin
must be self-contained except for the public contract import from
nonlinear_agent.model_plugins.contracts. Do not import nonlinear_agent.contracts
or any other guessed internal module. Python may use standard numerical and
plotting libraries, but must not use os, subprocess, socket, network clients,
dynamic imports, eval, or exec. Top-level code may contain only imports, class
or function definitions, literal constants, and optionally exactly
matplotlib.use("Agg") for a noninteractive backend. Do not modify rcParams,
construct arrays, or perform plotting at module scope; put all other runtime
setup and computation inside train.
The candidate manifest "schema_version" must be the JSON number 1, not the string "1".

Required JSON schema:
{{
  "schema_version": 1,
  "task_id": "{task.task_id}",
  "candidate_name": "{task.candidate_name}",
  "rationale": "why this implementation matches the hypothesis",
  "manifest_path": "models/candidates/{task.candidate_name}/manifest.json",
  "files": {{
    "models/candidates/{task.candidate_name}/plugin.py": "complete Python source",
    "models/candidates/{task.candidate_name}/manifest.json": "JSON string"
  }}
}}
"""


def _facts_from_exception(exc: Exception) -> tuple[str, ...]:
    if isinstance(exc, CandidateGateError):
        raw = [f"{exc.stage}: {fact}" for fact in exc.facts]
    else:
        raw = [f"{type(exc).__name__}: {exc}"]
    return tuple(_sanitize_fact(item) for item in raw)


def _sanitize_fact(value: str) -> str:
    redacted = _SECRET_VALUE.sub("[REDACTED]", value)
    return redacted.replace("\x00", "")[:1200]


def _trace_attempt(
    attempt_index: int,
    prompt: str,
    response: str,
    status: str,
    facts: tuple[str, ...],
    files: tuple[CodeFile, ...],
) -> dict[str, Any]:
    return {
        "attempt": attempt_index + 1,
        "status": status,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "response_sha256": hashlib.sha256(response.encode("utf-8")).hexdigest(),
        "failure_facts": list(facts),
        "files": {
            item.path: hashlib.sha256(item.content.encode("utf-8")).hexdigest()
            for item in files
        },
    }


def _write_trace(
    path: Path,
    task: CodingTaskSpec,
    attempts: list[dict[str, Any]],
    status: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "task_id": task.task_id,
        "candidate_name": task.candidate_name,
        "status": status,
        "attempts": attempts,
    }
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)
