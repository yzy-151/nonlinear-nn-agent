# Experiment Agent Harness v1.1 总学习文档

更新时间：2026-07-22

这是 v1.1 历史学习文档。当前最新主学习入口是 `experiment-agent-harness-v1.2.md`。

## 1. 本版主题

v1.1 补上 Agent 面试高频问题：Self-refine / 自我修正 / 工具失败恢复策略。

之前项目已经能把错误写入 history。v1.1 进一步把错误分析显式结构化：

- 每轮执行后生成 reflection record。
- 总结 rejected / failed / succeeded 状态。
- 识别失败原因。
- 给出 recovery actions。
- 给出下一轮 avoid list。
- 将 reflection 写入 `runs/<run-id>/reflections/round-XXX.json`。
- 最终 `result.json` 也包含 `reflections`。

## 2. 新增文件

- `src/nonlinear_agent/reflection.py`
- `tests/test_reflection.py`

更新：

- `src/nonlinear_agent/loop.py`
- `src/nonlinear_agent/run_artifacts.py`

## 3. 当前完整架构

```text
User Goal
  -> LLM Planner
  -> ToolSpec-aware plan
  -> Schema / Budget Guard
  -> Harness Runtime
  -> Tool Registry
  -> Metrics / Errors / Artifacts
  -> History Compression
  -> Reflection / Recovery Policy
  -> Run Artifacts
  -> Next planner round
```

## 4. Reflection Record

每个 reflection 包含：

```text
round
record_count
status_counts
best_experiment_id
best_nmse_db
failure_causes
recovery_actions
avoid_next
```

示例：

```json
{
  "round": 1,
  "status_counts": {"rejected": 1, "failed": 1},
  "failure_causes": [
    "Schema/preflight rejection in bad-rank: Unsupported planner override fields: rank",
    "Runtime/tool failure in weak: NMSE threshold failed"
  ],
  "recovery_actions": [
    "Remove unsupported fields and keep planner overrides within the declared tool/config schema.",
    "Prefer stronger baseline variants or revise the target/feature family after repeated NMSE threshold failures."
  ],
  "avoid_next": [
    "Avoid planner fields not listed in ExperimentConfig or ToolSpec input_schema.",
    "Avoid repeating weak model families without changing feature design or training budget."
  ]
}
```

## 5. 面试回答模板

### Agent 调工具失败怎么办？

我把失败分成三层：

1. preflight validation 失败：不进入 runtime，记录为 `rejected`。
2. runtime/tool 失败：记录为 `failed`，写入 trace、history 和 artifact。
3. 成功但指标弱：记录 metric，由 reflection 判断是否继续探索或调整方向。

每轮结束后会生成 reflection，明确失败原因、修正策略和下一轮避免项。

### Self-refine 做过什么？

做过两类：

- 隐式 self-correction：错误进入 history，下一轮 planner 读取后修正。
- 显式 reflection：系统生成结构化 `failure_causes / recovery_actions / avoid_next`，用于审计和后续 planner prompt 优化。

### 如何避免模型反复犯同样错误？

通过两层机制：

- Schema guard 阻止非法计划实际执行。
- Reflection 的 `avoid_next` 把失败模式显式记录下来，后续可以注入 planner prompt 或 benchmark 分析。

## 6. 结果图

### -41 dB target run best candidate

![PSD for exp016](../assets/psd-exp016-best-41db-run.png)

### DeepSeek self-correction candidate

![PSD for exp_019](../assets/psd-exp019-self-correction-run.png)

## 7. 验证

```powershell
python -m unittest tests.test_reflection
python -m unittest discover tests
```

## 8. 简历表达

```text
为 LLM Planner Loop 增加 Reflection / Recovery Policy，在每轮实验后结构化生成失败原因、修正策略和下一轮避免项，并将 rejected/failed/succeeded 状态、最佳指标和 recovery actions 写入 run artifacts，提升 Agent 自我修正、错误复盘和面试可解释性。
```

## 9. 下一步

v1.2：MCP Server / Tool Protocol。

目标是把当前 `ToolSpec` 映射为标准 MCP tool schema，让项目能回答“MCP 是什么、写过哪些 MCP 工具、Skill 和 MCP 有什么区别”。
