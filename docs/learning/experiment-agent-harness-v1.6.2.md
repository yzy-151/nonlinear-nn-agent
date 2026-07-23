# Experiment Agent Harness v1.6.2 学习文档

更新时间：2026-07-26

## 1. 版本主题

v1.6.2 是维护定版，不再扩张新概念，重点补齐 Agent Harness 的工程闭环：

- 实验产物路径不污染项目根目录。
- Reflection 不只落盘，而是进入下一轮 planner history。
- Benchmark 从 3 个 smoke case 扩展为 5 个关键场景。
- Web UI 和 Dashboard 统一为深色展示界面。
- 文档收敛为新人上手、交接维护、简历表达和版本学习四条主线。

## 2. 你应该从这个版本学会什么

### Artifact Guard

LLM planner 和手工配置都可能写出 `output_dir: exp001` 这类裸路径。如果不处理，训练脚本会在项目根目录生成大量实验文件。v1.6.2 增加 `artifact_paths.normalize_experiment_output_dir()`，把裸实验目录统一归入 `reports/`。

面试要点：

> Agent 系统要防止 LLM 生成的路径污染工作区。我的做法是在 planner validation 和 config generation 两层都归一化 output_dir，属于 runtime guardrail 的一部分。

### Reflection Context

旧问题是 reflection 只生成 `reflections/round-XXX.json`，但下一轮 planner 看不到这些恢复建议。v1.6.2 把 reflection 以 `run_status: reflection` 的记录写入 history，并在 benchmark/leaderboard 统计时过滤这种非实验记录。

面试要点：

> Reflection 要进入决策上下文才有意义。否则它只是日志，不是 agentic loop 的一部分。

### Benchmark Coverage

3 个 case 只能证明 smoke test。v1.6.2 使用 5 个 case 覆盖：

- target hit under budget
- invalid planner output rejection
- runtime failure handling
- reflection-based recovery
- experiment budget stop

指标口径：

- `target_hit_rate` = 达标 case 数 / 总 case 数。
- `rejected_rate` = rejected 记录数 / 全部实验记录。
- `runtime_failure_rate` = failed 记录数 / 全部实验记录。
- `average_experiments_used` = 消耗实验数 / case 数。
- `best_nmse_db` = 全部 case 最优 NMSE，越小越好。

### 文档收敛

本版本删除旧的零散 case/interview/plan 文档，把内容合并到：

- `docs/onboarding/newcomer-guide.md`
- `docs/handoff/llm-continuation-plan.md`
- `docs/resume/experiment-agent-harness-resume.md`
- `docs/learning/experiment-agent-harness-v*.md`

这能避免后续维护时同一件事散落在多处，面试前也更容易复习。

## 3. 主要改动文件

```text
src/nonlinear_agent/artifact_paths.py
src/nonlinear_agent/planner_validation.py
src/nonlinear_agent/experiment_tools.py
src/nonlinear_agent/loop.py
src/nonlinear_agent/benchmark.py
src/nonlinear_agent/run_artifacts.py
src/nonlinear_agent/server.py
src/nonlinear_agent/web_ui.py
src/nonlinear_agent/dashboard.py
examples/nonlinear_fit/run_benchmark.py
tests/test_planner_validation.py
tests/test_experiment_tools.py
tests/test_reflection.py
tests/test_benchmark.py
tests/test_server_benchmark.py
tests/test_web_ui.py
```

## 4. 验证命令

```powershell
python -m unittest discover tests
python examples\nonlinear_fit\run_benchmark.py --output-dir benchmarks\fake-v16-doc-ui-check
python agent.py dashboard
python agent.py serve --host 127.0.0.1 --port 8000
```

预期：

- 单元测试全部通过。
- Benchmark 输出 5 个 case 的 summary。
- Dashboard 生成 `docs/diagnostics/agent-runtime-dashboard.html`。
- 浏览器打开 `http://127.0.0.1:8000/` 后能看到深色 Web UI，并可运行 Workflow / Agent Planner / Benchmark。

## 5. 简历写法

- 维护并定版面向算法实验的 Agent Harness Runtime，补齐 artifact path guard、reflection-to-history 决策闭环、5-case benchmark evaluation 和 Web/Dashboard 展示界面，使 LLM 实验 Agent 具备可复现、可审计、可交接的工程化能力。

## 6. 后续边界

本项目到 v1.6.2 已经适合作为 Agent Harness 岗位项目展示。后续优先做维护：

- 保证测试通过。
- 更新 README 和面试表达。
- 保持 Web UI 能演示。
- 不再无目标堆新模块。

RAG、长期语义记忆、多 Agent 协作等内容交给 Storm 或新的独立项目覆盖。
