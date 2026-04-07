# Experiment Agent Harness v0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the v0.1 Agent Harness runtime to real nonlinear experiment tools and add trace replay reporting.

**Architecture:** Keep model training logic in `experiment.py`. Add `experiment_tools.py` as the boundary between runtime and training commands, add `replay.py` for observability reports, and add `run_harness.py` as the v0.2 CLI demo.

**Tech Stack:** Python standard library, PyYAML, existing training script, unittest.

---

### Task 1: Real Experiment Tools

**Files:**
- Create: `src/nonlinear_agent/experiment_tools.py`
- Test: `tests/test_experiment_tools.py`

- [x] Add `generate_config_tool` to write overridden YAML configs.
- [x] Add `run_training_tool` to execute training commands and capture stdout/stderr/returncode/elapsed time.
- [x] Add `verify_artifacts_tool` to enforce metrics/PSD/NMSE checks.
- [x] Add `write_report_tool` to generate hiring-facing reports from session state.
- [x] Add `build_experiment_tool_registry` to register all tools.

### Task 2: Trace Replay

**Files:**
- Create: `src/nonlinear_agent/replay.py`
- Test: `tests/test_replay.py`

- [x] Load JSONL trace events.
- [x] Summarize tool calls, latency, retries, metrics, and errors.
- [x] Generate Markdown replay report.

### Task 3: CLI Demo

**Files:**
- Create: `examples/nonlinear_fit/run_harness.py`
- Modify: `src/nonlinear_agent/runtime.py`
- Modify: `src/nonlinear_agent/tools.py`

- [x] Execute generate config -> train -> verify -> report through runtime.
- [x] Save session after each successful tool so later tools can read accumulated state.
- [x] Add `tool_names()` for registry introspection.

### Task 4: Docs

**Files:**
- Create: `docs/learning/experiment-agent-harness-v0.2.md`
- Create: `docs/superpowers/plans/2026-07-22-experiment-agent-harness-v0.2.md`
- Modify: `README.md`
- Modify: `docs/resume/experiment-agent-harness-resume.md`
- Modify: `docs/handoff/deepseek-continuation-plan.md`

- [x] Document what changed in v0.2.
- [x] Explain what the user should learn.
- [x] Update resume bullets and next-stage handoff.

### Task 5: Verification

- [x] Run v0.2 tests.
- [x] Run CLI demo with `harness-demo-v02`.
- [ ] Run full test suite.
- [ ] Commit and push.

## Self-Review

- v0.2 avoids heavy platform scope and does not add FastAPI/MCP yet.
- The implementation is testable without running long neural training.
- The CLI demo validates the real training path using the existing lightweight LSTSQ configuration.
