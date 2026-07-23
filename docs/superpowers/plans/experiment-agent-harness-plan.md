# Experiment Agent Harness 维护计划

更新时间：2026-07-22

本文件是唯一维护中的实施计划。旧的按日期拆分 plan 暂时保留为历史，后续确认删除。

## 当前目标

把 `nonlinear-nn-agent` 打造成面向 Agent Harness / Runtime / Agent Coding 岗位的项目证据。

当前已完成到 v1.5：

- v0.1：Harness Runtime
- v0.2：真实实验工具
- v0.3：SSE 服务层
- v0.4：LLM Planner Loop
- v0.5：Planner Schema Guard
- v0.6：Run Artifacts
- v0.7：Validation Guard 强化
- v0.8：Benchmark Evaluation
- v0.9：Context / Memory Compression
- v1.0：Tool Registry / Skill 化
- v1.1：Reflection / Recovery Policy
- v1.2：MCP Server / Tool Protocol
- v1.3：Async Runtime Hardening
- v1.4：Evaluation Dashboard / Runtime Diagnostics
- v1.5：Unified CLI / Local Dashboard Client

## 开发原则

- 新功能先写测试，再实现。
- LLM 只能输出结构化 plan，不直接执行命令。
- Runtime 负责工具执行、trace、session、错误和指标。
- Validation 负责 preflight 拒绝非法计划。
- 每个版本更新：
  - 最新学习文档
  - 对应版本文档
  - handoff 文档
  - resume 表达
  - 测试命令和结果

## v0.8 已完成：Agent Evaluation Benchmark

目标：回答面试高频问题“怎么证明这个 Agent 变强了”。

### Task 1：Benchmark Case 数据结构

已新增：

- `src/nonlinear_agent/benchmark.py`
- `tests/test_benchmark.py`
- `examples/nonlinear_fit/run_benchmark.py`

已支持：

- case id
- goal
- constraints
- max_rounds
- max_experiments
- expected behavior

### Task 2：Benchmark Runner

已完成：

- 使用 fake planner 跑固定 case。
- 后续可选 deepseek planner。
- 汇总每个 case 的 status、rounds、history_count、best_nmse、invalid/rejected/failed/succeeded 数量。

### Task 3：Benchmark Metrics

已输出指标：

- target_hit_rate
- invalid_plan_rate
- rejected_rate
- runtime_failure_rate
- best_nmse_db
- average_experiments_used

### Task 4：Artifact

已输出：

```text
benchmarks/<timestamp>/
  results.json
  leaderboard.csv
  summary.md
```

### Task 5：文档

已更新：

- `docs/learning/experiment-agent-harness-v0.8.md`
- `docs/handoff/deepseek-continuation-plan.md`
- `docs/resume/experiment-agent-harness-resume.md`

## v0.9 已完成：Context / Memory Compression

目标：回答上下文管理高频问题。

已新增：

- `src/nonlinear_agent/context_memory.py`
- `tests/test_context_memory.py`

已支持：

- short-term history window
- compressed run summary
- rejected/failed/succeeded 状态统计
- best_nmse / best_experiment 摘要
- notable error 摘要
- 完整 history 保留在 result/artifacts，planner prompt 只注入 summary + recent window

## v1.0 已完成：Tool Registry / Skill 化

目标：回答工具系统和 Skill 封装问题。

已新增/支持：

- ToolSpec
- ToolRegistry schema / describe_tools
- allowed tools 渐进式披露
- tool error policy
- unknown tool structured failure

## v1.1 已完成：Reflection + Recovery Policy

目标：回答 Self-refine / 自我修正策略问题。

已新增：

- `src/nonlinear_agent/reflection.py`
- `tests/test_reflection.py`

已支持：

- 每轮结束生成 reflection record
- 总结失败原因
- 明确下一轮修正策略
- rejected/failed history 触发 recovery policy
- `runs/<run-id>/reflections/round-XXX.json`
- `result.json` 保存完整 `reflections`
- `summary.md` 展示 recovery / avoid_next 摘要

## v1.2 已完成：MCP Server / Tool Protocol

目标：回答 MCP / Tool Protocol / Agent 工具协议问题。

已新增：

- `src/nonlinear_agent/mcp_server.py`
- `examples/nonlinear_fit/serve_mcp_tools.py`
- `tests/test_mcp_server.py`
- `docs/learning/experiment-agent-harness-v1.2.md`

已支持：

- `ToolSpec -> MCP tool schema`
- `tools/list`
- `tools/call`
- JSON-RPC 2.0 success/error response
- stdio JSON-lines mock server
- MCP bridge 复用现有 `ToolRegistry`

## v1.3 已完成：Async Runtime Hardening

目标：回答 Agent runtime 稳定性、取消、中断、重试和恢复问题。

已新增：

- `src/nonlinear_agent/runtime_errors.py`
- `src/nonlinear_agent/run_control.py`
- `tests/test_runtime_hardening.py`
- `docs/learning/experiment-agent-harness-v1.3.md`

已支持：

- structured error taxonomy
- cancellation / interrupt
- timeout error classification
- `RetryPolicy.ALWAYS / NEVER / RETRY_TIMEOUT`
- `HarnessRequest.resume_from_step`
- session `completed_steps`
- trace/session/reflection 贯通 `error_type`

## v1.4 已完成：Evaluation Dashboard / Runtime Diagnostics

目标：回答 Agent 评估结果如何展示、如何诊断 runtime/prompt/guardrail 改动收益。

已新增：

- `src/nonlinear_agent/diagnostics.py`
- `examples/nonlinear_fit/write_diagnostics.py`
- `tests/test_diagnostics.py`
- `docs/learning/experiment-agent-harness-v1.4.md`
- `docs/diagnostics/agent-runtime-dashboard.md`

已支持：

- benchmark 多次运行聚合
- planner loop run artifacts 聚合
- `target_hit_rate`
- `rejected_rate`
- `runtime_failure_rate`
- `best_nmse_db`
- `error_type_counts`
- Markdown diagnostics dashboard

## v1.5 已完成：Unified CLI / Local Dashboard Client

目标：降低项目操作门槛，把分散脚本收敛为可展示、可复现的命令入口。

已新增：

- `src/nonlinear_agent/cli.py`
- `src/nonlinear_agent/dashboard.py`
- `tests/test_cli.py`
- `tests/test_dashboard.py`
- `pyproject.toml`
- `agent.py`
- `docs/learning/experiment-agent-harness-v1.5.md`
- `docs/diagnostics/agent-runtime-dashboard.html`

已支持：

- `python -m nonlinear_agent.cli run`
- `python -m nonlinear_agent.cli benchmark`
- `python -m nonlinear_agent.cli diagnostics`
- `python -m nonlinear_agent.cli dashboard`
- `python -m nonlinear_agent.cli serve`
- `nonlinear-agent` console script
- `python agent.py ...` 本地免安装入口
- standalone HTML diagnostics dashboard

## v1.6 计划：Real DeepSeek Demo Replay / Case Study

目标：把真实 DeepSeek planner run 写成一个能直接面试讲述的 case study。

建议能力：

- 选择一轮真实 DeepSeek run。
- 提取 planner plan、history、reflection、leaderboard、PSD 图。
- 写 `docs/case-studies/deepseek-planner-self-correction.md`。
- 说明问题、失败、修正、结果和工程价值。

## 验证命令

```powershell
python -m unittest discover tests
python examples\nonlinear_fit\run_planner_loop.py --provider fake --max-rounds 2 --max-experiments 1 --artifact-dir runs\fake-check --goal "smoke test"
```
