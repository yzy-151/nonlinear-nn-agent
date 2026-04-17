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

## 2026-07-22 追加：如何让 Planner 想到 spline-LUT 和多模型实验

单纯告诉 LLM “优化 NMSE” 不够，它通常只会给普通 MLP/CNN 超参数。要让负责 plan 的 Agent 想到你说的物理启发方案，需要在 prompt 里明确给它四类信息：

1. 可执行设计空间
   - `model_type`: `complex_lstsq`, `linear`, `tiny_mlp`, `spline_mlp`。
   - `feature_mode`: 推荐 `complex_mp`，保留 `legacy_abs` baseline。
   - `activation`: `relu`, `tanh`, `silu`, `gelu`。
   - `spline_mlp`: 一层非线性，learnable 1D LUT activation，`spline_knots=16`，一阶线性插值。

2. 物理先验
   - 非线性来自物理链路，不一定需要深层 2D Conv。
   - 浅层非线性 + 记忆项可能比深网络更可解释。
   - 记忆深度和多项式阶数是关键变量。

3. 参数预算
   - `parameter_count_max <= 4000`。
   - 同 NMSE 下优先参数更少。
   - `spline_mlp` 推荐候选：`mp_order_count=1`, `memory_depth in [24, 48, 72]`, `hidden_units in [16, 32]`, `spline_knots=16`。

4. 历史结果
   - 已知强 baseline：`complex_lstsq + complex_mp + memory_depth=150 + mp_order_count=12`，3626 参数，NMSE 约 -37.42 dB。
   - planner 应该围绕这个 baseline 做变体，而不是随机试模型。

本轮已把这些信息写入 `ExperimentPlanner._build_prompt()`。这样 DeepSeek 不需要凭空发明实验空间，而是在“可执行、可验证、符合物理先验”的边界内设计实验。

## 多实验 fake planner demo 结果

本轮用 fake planner 模拟 DeepSeek 一次设计三类实验，并真实执行：

| Experiment | Model | Params | NMSE dB | Status | Interpretation |
|---|---|---:|---:|---|---|
| planner-lstsq-o10-m120 | complex_lstsq | 2422 | -37.3298 | passed | 参数更少，NMSE 接近当前最佳，是有价值候选 |
| planner-spline-m48-h32 | spline_mlp | 3746 | -3.5603 | failed threshold | 结构可执行，但 8 epoch/2048 样本远未训练好 |
| planner-tiny-silu-m48-h32 | tiny_mlp | 3234 | -1.4559 | failed threshold | 普通 MLP 在短训练下明显弱于闭式 MP |

结论：

- `complex_lstsq` 仍是当前最强、最稳路线。
- `spline_mlp` 是值得探索的物理启发结构，但不能用 8 epoch 小样本就否定，需要更合理训练策略、归一化或初始化。
- Planner 的价值不是保证每个实验成功，而是提出可解释候选、执行、记录失败，并把失败反馈给下一轮。
