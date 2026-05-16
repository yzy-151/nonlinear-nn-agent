# Experiment Agent Harness v0.9 总学习文档

更新时间：2026-07-22

这是当前最新主学习文档。你优先读这一份；旧版 `v0.1-v0.8` 保留为版本历史。

## 1. 本版主题

v0.9 补上 Agent 面试最高频问题：上下文管理。

本项目现在支持 deterministic history compression：

- 原始完整 history 仍保留在 loop result 和 run artifacts 中。
- 发送给 planner 的 history 只保留：
  - 一个 `history-summary` 压缩摘要。
  - 最近 N 条原始记录。
- 摘要中包含状态统计、最佳 NMSE、最佳实验、参数量和代表性错误。

这对应面试里的核心回答：

> 原始上下文不丢，但不会每轮都完整注入模型。系统保留完整日志用于审计和复盘；模型侧只注入压缩摘要和最近窗口，控制 token 成本并降低无关历史干扰。

## 2. 新增文件

- `src/nonlinear_agent/context_memory.py`
- `tests/test_context_memory.py`

更新：

- `src/nonlinear_agent/loop.py`

## 3. 当前架构

```text
Full history
  -> HistoryCompressor
  -> history-summary + recent window
  -> LLM Planner prompt
  -> new plan
  -> Runtime execution
  -> full history append
  -> artifacts preserve full result
```

## 4. 压缩策略

默认 `recent_window=3`。

如果 history 长度不超过窗口：

```text
planner receives full history copy
```

如果 history 超过窗口：

```text
planner receives:
  1. history-summary for older records
  2. last N raw records
```

`history-summary` 字段：

- `covered_records`
- `status_counts`
- `best_experiment_id`
- `best_nmse_db`
- `best_parameter_count`
- `notable_errors`
- `context_summary`

## 5. 面试回答模板

### 上下文过长怎么办？

我不会把完整历史无限塞进 prompt。完整 history 保存在 result/artifacts 中用于审计；发给 planner 的是压缩摘要加最近窗口。摘要保留状态统计、最佳实验和代表性错误，最近窗口保留细节，兼顾 token 成本和决策质量。

### 什么时候触发总结？

当前版本按 history 条数触发：超过 `recent_window` 后压缩旧记录。后续可以扩展为 token budget 触发，比如估算 prompt 字符数或模型上下文比例。

### 总结会不会丢关键信息？

会有风险，所以我保留两层防线：第一，完整原始 history 不删除，只是不全部注入模型；第二，摘要保留对下一轮规划最关键的信息：成功/失败/rejected 统计、最佳 NMSE、参数量和典型错误。

### 长期记忆和短期记忆怎么区分？

当前做的是短期实验 history 压缩，不是用户长期记忆。短期记忆服务当前 run 的决策；长期记忆应沉淀跨 run 的经验，例如“某类字段经常非法”“某类模型在当前数据集弱”。这是 v1.0 之后可扩展方向。

## 6. 验证

```powershell
python -m unittest tests.test_context_memory
python -m unittest discover tests
python examples\nonlinear_fit\run_planner_loop.py --provider fake --max-rounds 2 --max-experiments 1 --artifact-dir runs\fake-v09-check --goal "context memory smoke test"
```

## 7. 简历表达

```text
为 LLM Planner Loop 增加上下文压缩机制，将完整实验历史保留在 run artifacts 中用于审计，同时只向模型注入 history-summary 与最近窗口，摘要保留状态统计、最佳指标和代表性错误，降低 token 成本并提升多轮实验规划的可控性。
```

## 8. 下一步

v1.0：Tool Registry / Skill 化。

目标是回答面试高频问题：工具怎么定义、注册、发现、调用、失败恢复，以及 Skill 和 MCP 如何区分。

