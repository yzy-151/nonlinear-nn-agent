# 5-Minute Demo Script — nonlinear-nn-agent v2.0.0

## Timeline

### 00:00-00:40: Harness vs. Auto-Train Script

- Show the architecture: Planner -> Guard -> Runtime -> ToolRegistry -> Reflection
- Point: This is NOT a fixed training script. The LLM plans experiments, the
  Guard validates them, the Runtime executes through registered tools, and
  Reflection feeds facts back into the next round.
- Demo: `python agent.py run --provider fake --max-rounds 2`
- Show the structured plan output: `{"summary": "...", "experiments": [...]}`

### 00:40-01:30: ToolSpec, Guard, and DomainPlugin

- Show `ToolSpec` definitions: name, description, input_schema, category,
  error_policy — the "manual" the LLM reads.
- Show Guard catching invalid overrides (fake plan with `spline_range: null`)
- Show `NonlinearModelingDomain` and `SyntheticRegressionDomain` — same
  Planner/Runtime, different tools, different metrics.
- Point: The harness is domain-agnostic. Add a new DomainPlugin, get a
  new experiment loop.

### 01:30-02:30: Fake Planner SSE, Trace, Cancel, Recover

- Start server: `python agent.py serve --port 8001`
- Open Web UI at http://127.0.0.1:8001
- Run Agent Planner tab with Fake provider
- Show live SSE event stream: plan_generated, tool_start/tool_end, metric, complete
- Show event IDs (v2.0): each SSE frame has `id: <sequence>`
- Show Cancel button: POST /cancel/{session_id} stops the run mid-training
- Show Trace: `traces/{session_id}.jsonl` with hierarchical span tracing

### 02:30-03:40: Random/TPE/LLM/Reflection Comparison

- Show the protocol: `python agent.py compare-search --dry-run`
  4 methods x 5 seeds x 10 trials = 200 effective training trials
- Show per-method statistics: best NMSE, target hit rate, rejected rate,
  runtime failure rate — all with 95% bootstrap CI
- Show Reflection paired delta: `llm_with_reflection` vs `llm_no_reflection`,
  delta computed per-seed, not pooled
- Point: If the CI crosses zero, we say "no observed stable advantage" —
  no cherry-picking the best seed.

### 03:40-04:30: Real DeepSeek Self-Correction Bad Case

- Show real DeepSeek run where the LLM output `spline_range: null`
- Show Guard rejection: "Unsupported planner override fields: rank"
- Show how Reflection captures the failure: `failure_causes: ["spline_range must be a number"]`
- Show next round: LLM avoids the mistake
- Point: The guard doesn't crash — it produces structured rejection records
  that feed back into the planner's context.

### 04:30-05:00: SQLite, Boundaries, and What's NOT Here

- Show `RuntimeControlPlane`: SQLite with WAL, atomic job claims, monotonic
  event sequencing, SSE replay via Last-Event-ID
- Stress test: `python agent.py stress-runtime --concurrency 8 --requests 100`
  (dup rate = 0, event loss = 0, consistency = 1.0)
- Boundaries: No RAG, no GraphRAG, no multi-agent teams — those belong to
  the PaperStorm project. This project demonstrates a single-agent harness
  with tool-level reliability.
- End with: "Questions about any layer of the stack?"
