# Experiment Agent Harness v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing nonlinear NN experiment runner into a lightweight Agent Harness that demonstrates runtime, tools, hooks, session persistence, trace logging, and hiring-facing documentation.

**Architecture:** Keep the existing training and comparison code unchanged. Add focused harness modules under `src/nonlinear_agent/` and cover them with unit tests that do not run heavy training. The runtime will execute named tools asynchronously, emit events, write trace JSONL, update a persisted session, and call hooks around each tool invocation.

**Tech Stack:** Python standard library (`asyncio`, `dataclasses`, `json`, `time`, `uuid`, `pathlib`), existing `yaml` dependency, `unittest`.

---

### Task 1: Harness Data Boundaries

**Files:**
- Create: `src/nonlinear_agent/trace.py`
- Create: `src/nonlinear_agent/session.py`
- Test: `tests/test_harness_runtime.py`

- [x] Define trace events as JSON-serializable records with `session_id`, `event_type`, `step`, `tool`, `status`, `timestamp`, `latency_ms`, `payload`, and `error`.
- [x] Define an experiment session that stores goal, status, current step, metrics, artifacts, errors, context summary, and event history.
- [x] Persist sessions to `sessions/<session_id>.json` and load them back without external services.

### Task 2: Tool System and Hooks

**Files:**
- Create: `src/nonlinear_agent/tools.py`
- Create: `src/nonlinear_agent/hooks.py`
- Test: `tests/test_harness_runtime.py`

- [x] Add `ToolRegistry` for registering named callables.
- [x] Add timeout and retry handling around tool execution.
- [x] Add `HookManager` with `before_tool`, `after_tool`, `on_error`, and `on_metric` events.

### Task 3: Async Runtime

**Files:**
- Create: `src/nonlinear_agent/runtime.py`
- Test: `tests/test_harness_runtime.py`

- [x] Add `ExperimentHarnessRuntime.run()` as an async event generator.
- [x] Execute a list of tool calls in order.
- [x] Emit start/tool_start/tool_end/metric/error/complete events.
- [x] Update session and trace after each step.

### Task 4: Docs and Hiring Evidence

**Files:**
- Create: `docs/learning/experiment-agent-harness-v0.1.md`
- Create: `docs/resume/experiment-agent-harness-resume.md`
- Create: `docs/handoff/deepseek-continuation-plan.md`
- Modify: `README.md`

- [x] Explain what the user should learn from this phase.
- [x] Provide resume bullets mapped to Agent Harness JD requirements.
- [x] Provide continuation steps clear enough for DeepSeek or another Codex workspace.

### Task 5: Verification and GitHub

**Files:**
- Modify as needed after tests.

- [x] Run `python -m unittest discover -s tests -p "test_*.py" -v`.
- [x] Check `git status -sb` and `git diff --stat`.
- [x] Commit intentional changes.
- [x] Push `main` to `origin`.

## Self-Review

- No placeholder sections are left in this plan.
- Scope is limited to a testable v0.1 harness layer; heavy model training and web server work are explicitly deferred.
- Each new module has one responsibility and tests can run without GPU or long experiments.
