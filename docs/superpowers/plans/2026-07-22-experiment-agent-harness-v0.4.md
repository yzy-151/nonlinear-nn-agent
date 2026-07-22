# Experiment Agent Harness v0.4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add DeepSeek-compatible LLM planning and a real plan-run-observe experiment loop.

**Architecture:** Keep deterministic harness execution in the runtime/tools layer. Add a planner layer that turns goals, constraints, and history into JSON experiment candidates. The LLM never runs shell commands; it only proposes config overrides. Runtime remains responsible for execution, validation, trace, and session persistence.

**Tech Stack:** Python standard library `urllib`, DeepSeek OpenAI-compatible API, unittest, existing harness runtime.

---

### Task 1: LLM Client

**Files:**
- Create: `src/nonlinear_agent/llm.py`
- Test: `tests/test_llm_planner.py`

- [x] Add `LLMClient` protocol.
- [x] Add `FakeLLMClient` for deterministic tests.
- [x] Add `OpenAICompatibleClient.deepseek()` using `DEEPSEEK_API_KEY`, `https://api.deepseek.com`, and `deepseek-v4-flash`.

### Task 2: Planner

**Files:**
- Create: `src/nonlinear_agent/planner.py`
- Test: `tests/test_llm_planner.py`

- [x] Add `ExperimentPlanner`.
- [x] Prompt on goal, constraints, history, and allowed tools.
- [x] Parse JSON into `ExperimentPlan` and `PlannedExperiment`.

### Task 3: Plan-Run-Observe Loop

**Files:**
- Create: `src/nonlinear_agent/loop.py`
- Modify: `src/nonlinear_agent/server.py`
- Test: `tests/test_llm_planner.py`

- [x] Add `ExperimentPlannerLoop`.
- [x] Run planner, execute planned experiments through harness runtime, collect metric events, append history, and repeat until stop or max rounds.
- [x] Add `HarnessRunSpec.overrides` so planner outputs can modify YAML fields.

### Task 4: CLI Demo

**Files:**
- Create: `examples/nonlinear_fit/run_planner_loop.py`

- [x] Add `--provider fake` offline demo.
- [x] Add `--provider deepseek` mode that reads `DEEPSEEK_API_KEY`.

### Task 5: Docs and Verification

**Files:**
- Create: `docs/learning/experiment-agent-harness-v0.4.md`
- Create: `docs/superpowers/plans/2026-07-22-experiment-agent-harness-v0.4.md`
- Modify: README/resume/handoff.

- [x] Correct workflow vs agent wording.
- [x] Document DeepSeek usage without storing keys.
- [ ] Run tests, commit, and push.

## Self-Review

- No API key is stored in code or docs.
- Tests use `FakeLLMClient`; real DeepSeek calls are opt-in through env vars.
- LLM output is constrained to JSON config overrides, not arbitrary commands.
