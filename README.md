# Nonlinear NN Agent Harness

面向 Agent Harness / Runtime / Agent Coding 岗位的实验型项目。

本项目把一个非线性系统建模任务改造成 LLM-driven Agent Harness：LLM 负责规划实验，Harness 负责工具执行、schema guard、trace、session、history compression、reflection、benchmark 和结果落盘。

## Project Goal

目标不是单纯追求最低 NMSE，而是展示一个生产级 Agent Harness 需要的核心能力：

- Agentic loop
- Tool calling / ToolSpec / progressive disclosure
- Hook / session / trace
- SSE streaming
- LLM planner with DeepSeek-compatible client
- Schema guard and parameter budget guard
- Run artifacts and leaderboard
- Benchmark evaluation
- Context compression
- Reflection and recovery policy

## Architecture

```text
User Goal
  -> LLM Planner
  -> Structured Experiment Plan
  -> Schema / Budget Guard
  -> Harness Runtime
  -> Tool Registry
  -> Training / Verify / Report Tools
  -> Trace / Session / Metrics
  -> History Compression
  -> Reflection / Recovery
  -> Run Artifacts / Benchmark
```

LLM 只输出结构化计划，不直接执行 shell。执行边界由 Harness Runtime 和 ToolRegistry 控制。

## Results

### Best candidate in -41 dB target run

- Experiment: `exp016`
- Model: `complex_lstsq`
- Feature mode: `complex_mp`
- Memory depth: `220`
- MP order: `9`
- Params: `3980`
- NMSE: `-37.4875 dB`

![PSD for exp016](docs/assets/psd-exp016-best-41db-run.png)

### DeepSeek self-correction run

- Experiment: `exp_019`
- Model: `complex_lstsq`
- Feature mode: `complex_mp`
- Memory depth: `24`
- MP order: `4`
- Params: `202`
- NMSE: `-36.0275 dB`

![PSD for exp_019](docs/assets/psd-exp019-self-correction-run.png)

## Version Branches

Version branches are pushed to GitHub as stable checkpoints:

```text
version/v0.1
version/v0.2
version/v0.3
version/v0.4
version/v0.5
version/v0.6
version/v0.7
version/v0.8
version/v0.9
version/v1.0
version/v1.1
```

## Learning Docs

Latest main learning doc:

- `docs/learning/experiment-agent-harness-v1.1.md`

Historical version docs:

- `docs/learning/experiment-agent-harness-v0.1.md`
- `docs/learning/experiment-agent-harness-v0.2.md`
- `docs/learning/experiment-agent-harness-v0.3.md`
- `docs/learning/experiment-agent-harness-v0.4.md`
- `docs/learning/experiment-agent-harness-v0.5.md`
- `docs/learning/experiment-agent-harness-v0.6.md`
- `docs/learning/experiment-agent-harness-v0.7.md`
- `docs/learning/experiment-agent-harness-v0.8.md`
- `docs/learning/experiment-agent-harness-v0.9.md`
- `docs/learning/experiment-agent-harness-v1.0.md`
- `docs/learning/experiment-agent-harness-v1.1.md`

## Run

Fake planner loop:

```powershell
python examples\nonlinear_fit\run_planner_loop.py --provider fake --max-rounds 2 --max-experiments 1 --artifact-dir runs\fake-check --goal "smoke test"
```

DeepSeek planner loop:

```powershell
$env:DEEPSEEK_API_KEY="your-key"
python examples\nonlinear_fit\run_planner_loop.py --provider deepseek --max-rounds 10 --max-experiments 30 --timeout-seconds 10800 --nmse-threshold-db -41 --goal "Target NMSE <= -41 dB under 4000 trainable parameters."
```

Benchmark:

```powershell
python examples\nonlinear_fit\run_benchmark.py --output-dir benchmarks\fake-v08-check
```

Tests:

```powershell
python -m unittest discover tests
```

## Interview Positioning

Recommended summary:

```text
Designed and implemented an LLM-driven Agent Harness Runtime for nonlinear-system modeling experiments. The system decomposes experiment work into controlled tools, supports ToolSpec-based progressive disclosure, schema and parameter-budget guardrails, trace/session persistence, SSE event streaming, run artifact generation, benchmark evaluation, context compression, and reflection/recovery records for self-correction.
```

