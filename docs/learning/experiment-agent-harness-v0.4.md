# Experiment Agent Harness v0.4 学习文档

更新时间：2026-07-22

## 这一版为什么必须做

前面 v0.1-v0.3 主要是 Agent Harness 底座：工具注册、session、trace、真实训练工具、SSE 流式接口。严格讲，它们更像可观测 workflow，不是完整 Agent。

v0.4 补上两个关键能力：

1. LLM Planner：由模型根据目标、约束和历史结果设计下一组实验。
2. Plan-Run-Observe Loop：执行实验后把 NMSE、参数量等 observation 回传给 planner，再决定继续还是停止。

这才形成更完整的 Agent 结构：

```text
User Goal
  -> LLM Planner
  -> Experiment Plan JSON
  -> Harness Runtime
  -> Tool Execution
  -> Metrics / Artifacts / Trace
  -> Observation History
  -> LLM Planner decides next round or stop
```

## 新增文件

- `src/nonlinear_agent/llm.py`
  - `LLMClient` 协议。
  - `FakeLLMClient`：测试和离线 demo 用。
  - `OpenAICompatibleClient`：OpenAI-compatible HTTP client，默认 DeepSeek。

- `src/nonlinear_agent/planner.py`
  - `ExperimentPlanner`：构造 prompt，解析 LLM JSON。
  - `ExperimentPlan` / `PlannedExperiment`：结构化实验计划。

- `src/nonlinear_agent/loop.py`
  - `ExperimentPlannerLoop`：真正的 plan-run-observe 多轮循环。
  - `PlannerLoopResult`：记录 rounds、history、summaries。

- `examples/nonlinear_fit/run_planner_loop.py`
  - CLI demo。
  - 默认 `--provider fake`，稳定离线运行。
  - `--provider deepseek` 时读取 `DEEPSEEK_API_KEY`。

- `tests/test_llm_planner.py`
  - 验证 DeepSeek client 默认 endpoint/model。
  - 验证 LLM JSON plan 解析。
  - 验证 planner loop 能执行一轮实验并在第二轮停止。

## DeepSeek API 怎么用

本项目没有调用 Codex API。DeepSeek client 使用 OpenAI-compatible Chat Completions 风格：

```text
base_url: https://api.deepseek.com
path: /chat/completions
default model: deepseek-v4-flash
api key env: DEEPSEEK_API_KEY
```

代码不会保存 API key。运行前在当前 shell 设置环境变量：

```powershell
$env:DEEPSEEK_API_KEY="你的 key"
python examples\nonlinear_fit\run_planner_loop.py --provider deepseek --max-rounds 2 --timeout-seconds 120
```

注意：不要把 key 写入 README、配置文件、trace、session 或 Git commit。

## 离线 demo 结果

命令：

```powershell
python examples\nonlinear_fit\run_planner_loop.py --provider fake --max-rounds 2 --timeout-seconds 120
```

结果：

```text
status: stopped
rounds: 2
experiment: planner-demo-001
NMSE: -37.4249 dB
parameter_count: 3626
model_type: complex_lstsq
feature_mode: complex_mp
mp_order_count: 12
```

第一轮 fake planner 设计实验，runtime 执行真实训练工具；第二轮 fake planner 根据 history 停止。这证明 loop 结构成立。

## 你应该学会什么

### 1. Agent 和 Workflow 的区别

Workflow 是固定步骤：

```text
generate_config -> run_training -> verify_artifacts -> write_report
```

Agent loop 是动态决策：

```text
observe -> plan -> act -> observe -> decide continue/stop
```

v0.4 之前项目主要是 workflow harness。v0.4 开始具备 Agent loop。

### 2. LLM 不能直接执行命令

Planner 只输出实验 JSON：

```json
{
  "summary": "try longer memory",
  "stop": false,
  "experiments": [
    {
      "id": "exp-o10-m180",
      "reason": "test deeper memory under parameter budget",
      "overrides": {
        "model_type": "complex_lstsq",
        "memory_depth": 180,
        "mp_order_count": 10
      }
    }
  ]
}
```

LLM 不输出 shell command。执行仍由 harness runtime 和 tool registry 控制。这是安全边界。

### 3. 仿真实验如何由 LLM 设计

Planner 的输入包括：

- 目标：例如参数量小于 4000，NMSE 尽量低。
- 约束：`parameter_count_max`、主指标 `nmse_db`。
- 历史结果：上一轮实验的 NMSE、参数量、模型类型。

Planner 的输出是下一组候选实验配置 overrides。runtime 执行后，将结果写回 history。

### 4. 面试时怎么讲

不要说 v0.1-v0.3 就已经是完整 Agent。准确说：

> 我先实现了可观测实验 harness：工具注册、session、trace、SSE 和真实训练工具链；随后接入 LLM Planner，把自然语言目标、约束和历史结果转成结构化实验计划，并通过 plan-run-observe loop 多轮执行和停止。

这个说法更稳，也更经得起追问。

## 当前不足

- DeepSeek 真实 API 调用尚未在仓库测试中执行，测试默认 fake，避免 key 泄露和网络不稳定。
- Planner 目前只校验 JSON 基本结构，还没做严格 schema 和参数预算预估。
- Loop 还没有 cancel/interrupt。
- 还没有 MCP server。

v0.5 建议做：

1. 参数预算预估器：LLM 输出计划前后都检查 `parameter_count <= 4000`。
2. Planner 输出 schema 校验。
3. cancel/interrupt。
4. MCP server。
