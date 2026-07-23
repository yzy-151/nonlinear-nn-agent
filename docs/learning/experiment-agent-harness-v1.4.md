# Experiment Agent Harness v1.4 总学习文档

更新时间：2026-07-23

这是当前最新主学习文档。你优先读这一份；旧版 `v0.1-v1.3` 保留为版本历史。

## 1. 本版主题

v1.4 补上 Agent Evaluation / Runtime Diagnostics：不只展示某次 demo 成功，而是聚合 benchmark 和 planner loop artifacts，说明 Agent 在目标命中、失败率、错误类型和最佳指标上的表现。

新增能力：

- 读取多个 `benchmarks/<run>/results.json`。
- 读取多个 `runs/<run>/result.json`。
- 聚合 target hit rate、rejected rate、runtime failure rate、best NMSE。
- 统计 run status 分布。
- 统计 `error_type` 分布。
- 生成 Markdown diagnostics dashboard。

## 2. 新增文件

- `src/nonlinear_agent/diagnostics.py`
- `examples/nonlinear_fit/write_diagnostics.py`
- `tests/test_diagnostics.py`
- `docs/diagnostics/agent-runtime-dashboard.md`

更新：

- `src/nonlinear_agent/__init__.py`

## 3. 数据流

```text
benchmarks/*/results.json
  -> collect_diagnostics()

runs/*/result.json
  -> collect_diagnostics()

diagnostics dict
  -> render_diagnostics_markdown()
  -> docs/diagnostics/agent-runtime-dashboard.md
```

## 4. Dashboard 指标

核心指标：

- `case_count`
- `target_hit_rate`
- `rejected_rate`
- `runtime_failure_rate`
- `average_experiments_used`
- `best_nmse_db`
- `status_counts`
- `error_type_counts`
- `best_candidate`

这些指标对应的面试解释：

- `target_hit_rate`：Agent 是否能完成目标。
- `rejected_rate`：guardrail 拦截坏计划的比例。
- `runtime_failure_rate`：执行层稳定性。
- `error_type_counts`：失败是否被结构化诊断。
- `best_nmse_db`：算法任务结果质量。
- `average_experiments_used`：实验预算使用效率。

## 5. 为什么 v1.4 重要

v0.1-v1.3 证明系统能运行，v1.4 证明系统能被评估。

面试里“我做了一个 Agent”是不够的，关键问题是：

- 怎么证明它变强了？
- 怎么发现 runtime 问题？
- 怎么比较 prompt/guard/runtime 改动？
- 怎么知道失败是 validation、timeout、tool error 还是 cancelled？

v1.4 的 dashboard 就是回答这些问题的证据。

## 6. 运行方式

```powershell
python examples\nonlinear_fit\write_diagnostics.py
```

默认输出：

```text
docs/diagnostics/agent-runtime-dashboard.md
```

## 7. 验证

```powershell
python -m unittest tests.test_diagnostics
python -m unittest discover tests
```

## 8. 简历表达

```text
构建 Agent Runtime diagnostics dashboard，聚合 benchmark 与 planner-loop artifacts，统计 target_hit_rate、rejected_rate、runtime_failure_rate、error_type 分布、最佳 NMSE 和实验预算使用情况，用于评估 prompt、guardrail 与 runtime hardening 改动收益。
```

## 9. 下一步

v1.5：Unified CLI / Local Dashboard Client。

目标：

- 把 planner loop、benchmark、diagnostics、dashboard、serve 收敛到一个 CLI。
- 增加本地 HTML dashboard，降低展示和复现成本。
- 安装后支持 `nonlinear-agent` 命令。
