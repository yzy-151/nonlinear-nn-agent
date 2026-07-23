# Agent Harness 面试 Q&A

更新时间：2026-07-23

这份文档用于背诵和面试前快速复习。

## 1. Agent Harness 和直接调 LLM API 有什么区别？

直接调 LLM API 只解决“生成文本”。Agent Harness 解决“让模型安全、可观测、可恢复地调用工具完成长链路任务”。

本项目里：

- Planner 只输出结构化 JSON plan。
- Runtime 执行工具链。
- ToolRegistry 控制可调用工具。
- SessionStore 保存状态。
- TraceLogger 记录事件。
- ReflectionPolicy 复盘失败。
- Benchmark/Diagnostics 评估整体表现。

## 2. 工具怎么定义、注册、发现、调用？

工具定义在 `experiment_tools.py`，注册到 `ToolRegistry`：

```text
generate_config
run_training
verify_artifacts
write_report
```

每个工具有 `ToolSpec`：

- name
- description
- input_schema
- category
- error_policy

Planner 通过 `describe_tools()` 看到工具能力。Runtime 根据 `ToolCall(name, args)` 调 `ToolRegistry.run()`，得到 `ToolResult`，再转成 `TraceEvent`。

## 3. 工具调用失败怎么办？

分层处理：

1. schema/preflight 失败：记为 `rejected`，不执行工具。
2. timeout/tool error：记为 `failed`，写入 trace、session、history。
3. 指标不达标：记录 metric 和 error，由 reflection 判断下一步。

v1.3 之后错误有结构化 `error_type`，例如：

- `validation_error`
- `timeout_error`
- `tool_error`
- `metric_threshold_error`
- `cancelled`

## 4. 上下文压缩怎么做？

`HistoryCompressor` 保留最近 N 条原始记录，把更久远历史压成摘要。

摘要保留：

- covered_records
- status_counts
- best_experiment_id
- best_nmse_db
- best_parameter_count
- notable_errors

完整 history 仍保存在 `result.json`，只是不给 planner 全量注入。

## 5. Reflection 和普通日志有什么区别？

日志记录发生了什么。Reflection 生成下一步怎么修：

- failure_causes
- recovery_actions
- avoid_next
- best_experiment_id
- best_nmse_db
- error_type_counts

它可以直接进入下一轮 planner prompt，也可以用于面试复盘。

## 6. MCP 和 ToolSpec 什么关系？

`ToolSpec` 是项目内部工具描述。MCP 是跨进程工具协议。

本项目 v1.2 做了 MCP-compatible bridge：

- `ToolSpec -> MCP tool schema`
- `tools/list`
- `tools/call`
- JSON-RPC success/error response

底层仍复用 `ToolRegistry`，所以 LLM Planner 和 MCP client 共享同一套工具能力。

## 7. 怎么证明 Agent 变强？

不能只看一次 demo。v0.8 做 benchmark，v1.4 做 diagnostics。

指标：

- target_hit_rate
- rejected_rate
- runtime_failure_rate
- average_experiments_used
- best_nmse_db
- error_type_counts

这能比较 prompt、guardrail、runtime 改动前后的收益。

## 8. 这个项目如何对应面试高频点？

| 高频点 | 本项目版本 |
|---|---|
| Harness Runtime | v0.1-v0.3 |
| Tool Calling | v1.0 |
| Context Management | v0.9 |
| Self-Reflection | v1.1 |
| MCP | v1.2 |
| Runtime Hardening | v1.3 |
| Evaluation | v0.8 + v1.4 |
| Demo/UI | v1.5 + v1.6 |

## 9. 项目边界是什么？

这个项目不是 RAG 项目，不负责覆盖 BM25、Rerank、Ragas、GraphRAG。RAG 相关问题用 Storm 项目覆盖。

本项目主线是：

> Agent Harness / Runtime / Tool Calling / Context / Reflection / Evaluation / Delivery Surface

不要在面试里把它说成万能 Agent 平台。
