# Experiment Agent Harness v1.3 总学习文档

更新时间：2026-07-23

这是 v1.3 历史学习文档。当前最新主学习入口是 `experiment-agent-harness-v1.4.md`。

## 1. 本版主题

v1.3 补上 Agent Runtime 面试高频问题：长链路工具调用的稳定性、取消、中断、超时、重试和恢复。

本版新增五个能力：

- structured error taxonomy
- cancellation / interrupt
- timeout classification
- retry policy 分类
- resume from step

核心思想：不要让 runtime 只记录一段错误字符串，而要把失败变成可观测、可统计、可恢复的结构化状态。

## 2. 新增文件

- `src/nonlinear_agent/runtime_errors.py`
- `src/nonlinear_agent/run_control.py`
- `tests/test_runtime_hardening.py`

更新：

- `src/nonlinear_agent/tools.py`
- `src/nonlinear_agent/runtime.py`
- `src/nonlinear_agent/session.py`
- `src/nonlinear_agent/trace.py`
- `src/nonlinear_agent/reflection.py`
- `src/nonlinear_agent/__init__.py`

## 3. 当前完整架构

```text
ToolCall
  -> ToolRegistry.run()
  -> retry policy / timeout handling
  -> ToolResult(error_type, retryable)
  -> ExperimentHarnessRuntime
  -> TraceEvent(error_type)
  -> ExperimentSession(error_types, completed_steps)
  -> ReflectionPolicy(error_type_counts)
```

取消/恢复路径：

```text
RunController.cancel()
  -> Runtime checks before next tool
  -> cancelled TraceEvent
  -> session.status = cancelled

HarnessRequest.resume_from_step
  -> Runtime skips completed earlier steps
  -> continues from selected step
```

## 4. Error Taxonomy

新增 `ErrorType`：

```text
validation_error
timeout_error
tool_error
metric_threshold_error
cancelled
```

分类逻辑：

- `asyncio.TimeoutError` -> `timeout_error`
- `ValueError` -> `validation_error`
- message 同时包含 `nmse` 和 `threshold` -> `metric_threshold_error`
- cancellation -> `cancelled`
- 其他异常 -> `tool_error`

## 5. Retry Policy

新增 `RetryPolicy`：

```text
always
never
retry_timeout
```

行为：

- `always`：兼容旧行为，按 `retries` 重试所有工具异常。
- `never`：失败一次立刻返回。
- `retry_timeout`：只重试 timeout 类错误。

示例：

```python
ToolCall(
    name="run_training",
    args={"config_path": "configs/demo.yaml"},
    timeout_seconds=120,
    retries=1,
    retry_policy=RetryPolicy.RETRY_TIMEOUT,
)
```

## 6. Cancellation / Interrupt

新增 `RunController`：

```python
controller = RunController()
controller.cancel("user interrupt")
```

Runtime 每个 tool 执行前检查：

- 若未取消，继续执行工具。
- 若已取消，产出 `cancelled` event。
- session 状态写为 `cancelled`。
- `error_type` 写为 `cancelled`。

这对应长任务 Agent 的 human interrupt / stop generation / stop tool run 场景。

## 7. Resume Failed Run

`HarnessRequest` 新增：

```python
resume_from_step: int = 1
```

当 `resume_from_step=2` 时，runtime 会跳过第 1 步，从第 2 个工具继续执行。

当前 v1.3 做的是 step-level resume，不是训练进程内部 checkpoint resume。它适合回答：

- 工具链中第 3 步失败，如何不重复第 1-2 步？
- session 中如何记录已完成 step？
- 长链路 Agent 怎么做可恢复执行？

## 8. Reflection 增强

`ReflectionPolicy` 新增：

```text
error_type_counts
```

示例：

```json
{
  "error_type_counts": {
    "timeout_error": 1,
    "validation_error": 1
  }
}
```

这样 benchmark 和面试复盘可以回答“不只是失败了，而是哪类失败最多”。

## 9. 面试回答模板

### 工具调用卡住怎么办？

我不会只靠全局超时，而是把 timeout 作为结构化错误类型记录。`ToolRegistry` 会把 `asyncio.TimeoutError` 归类为 `timeout_error`，Runtime 把它写进 trace/session/history。是否 retry 由 `RetryPolicy` 决定，例如训练工具可以只 retry timeout，schema 错误不 retry。

### Agent 怎么取消？

Runtime 接收 `RunController`，每个工具调用前检查是否取消。取消后产出 `cancelled` event，session 状态变成 `cancelled`，并写入 `error_type=cancelled`。这样用户中断不是进程崩溃，而是可观测状态。

### 失败后怎么恢复？

session 记录 `completed_steps`。`HarnessRequest.resume_from_step` 可以让 Runtime 跳过已完成步骤，从指定 step 继续。这是 step-level resume，后续可扩展到训练 checkpoint。

### 怎么判断哪些错误要 retry？

不能把所有错误都 retry。v1.3 分成：

- validation / schema 错误：不 retry，交给 planner 修正。
- metric threshold 错误：不 retry，交给 planner/reflection 改实验方案。
- timeout / temporary tool error：按策略 retry。
- cancelled：不 retry，尊重用户中断。

## 10. 验证

```powershell
python -m unittest tests.test_runtime_hardening
python -m unittest discover tests
```

## 11. 简历表达

```text
为 Agent Harness Runtime 增加结构化错误分类、取消/中断、超时与重试策略、step-level resume 能力，使长链路工具调用具备可观测、可恢复和可控失败处理能力；错误类型贯通 ToolResult、TraceEvent、Session 和 Reflection，支持后续 benchmark 分析。
```

## 12. 下一步

v1.4：Evaluation Dashboard / Runtime Diagnostics。

目标：

- benchmark 多次运行对比
- error_type 分布统计
- prompt / guard / runtime 版本对比
- HTML 或 Markdown dashboard
