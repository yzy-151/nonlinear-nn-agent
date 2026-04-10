# Experiment Agent Harness v0.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an SSE streaming service layer so harness runtime events can be consumed online by clients.

**Architecture:** Keep the runtime and experiment tools unchanged. Add `server.py` as an adapter that converts `TraceEvent` objects into Server-Sent Events and exposes an optional FastAPI app. Keep FastAPI imports lazy so core tests do not require web dependencies.

**Tech Stack:** Python standard library, optional FastAPI/uvicorn, unittest.

---

### Task 1: SSE Encoding and Stream Adapter

**Files:**
- Create: `src/nonlinear_agent/server.py`
- Test: `tests/test_server_streaming.py`

- [x] Add `encode_sse_event`.
- [x] Add `stream_sse_events`.
- [x] Test event type and JSON payload format.

### Task 2: Harness Request Builder

**Files:**
- Create: `src/nonlinear_agent/server.py`
- Test: `tests/test_server_streaming.py`

- [x] Add `HarnessRunSpec`.
- [x] Add `build_harness_request` for generate_config -> run_training -> verify_artifacts -> write_report.

### Task 3: Optional FastAPI App

**Files:**
- Create: `src/nonlinear_agent/server.py`
- Create: `examples/nonlinear_fit/serve_harness.py`
- Modify: `requirements.txt`

- [x] Add `create_app(workspace)` with `/health` and `/runs/{session_id}/events`.
- [x] Add CLI service launcher.
- [x] Add `fastapi` and `uvicorn` to requirements.

### Task 4: Docs and Resume Evidence

**Files:**
- Create: `docs/learning/experiment-agent-harness-v0.3.md`
- Create: `docs/superpowers/plans/2026-07-22-experiment-agent-harness-v0.3.md`
- Modify: `README.md`
- Modify: `docs/resume/experiment-agent-harness-resume.md`
- Modify: `docs/handoff/deepseek-continuation-plan.md`

- [x] Document SSE usage.
- [x] Explain learning value and resume mapping.
- [x] Set v0.4 direction to cancel/interrupt, then MCP.

### Task 5: Verification

- [ ] Run full test suite.
- [ ] Check git diff.
- [ ] Commit and push.

## Self-Review

- This phase does not require network installs to pass tests.
- FastAPI is optional at import time but documented as a runtime dependency.
- The service layer preserves existing runtime/tool boundaries.
