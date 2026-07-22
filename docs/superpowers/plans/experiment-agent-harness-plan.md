# Experiment Agent Harness 维护计划

更新时间：2026-07-22

本文件是唯一维护中的实施计划。旧的按日期拆分 plan 暂时保留为历史，后续确认删除。

## 当前目标

把 `nonlinear-nn-agent` 打造成面向 Agent Harness / Runtime / Agent Coding 岗位的项目证据。

当前已完成到 v0.8：

- v0.1：Harness Runtime
- v0.2：真实实验工具
- v0.3：SSE 服务层
- v0.4：LLM Planner Loop
- v0.5：Planner Schema Guard
- v0.6：Run Artifacts
- v0.7：Validation Guard 强化
- v0.8：Benchmark Evaluation

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

## v0.9 计划：Context / Memory Compression

目标：回答上下文管理高频问题。

能力：

- short-term history window
- compressed run summary
- rejected/failed/succeeded experience memory
- prompt history budget

## v1.0 计划：Tool Registry / Skill 化

目标：回答工具系统和 Skill 封装问题。

能力：

- ToolSpec
- ToolRegistry schema
- allowed tools 渐进式披露
- tool error policy

## 验证命令

```powershell
python -m unittest discover tests
python examples\nonlinear_fit\run_planner_loop.py --provider fake --max-rounds 2 --max-experiments 1 --artifact-dir runs\fake-check --goal "smoke test"
```
