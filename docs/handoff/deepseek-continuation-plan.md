# DeepSeek / Other Codex Continuation Plan

更新时间：2026-07-21

## 项目路径

本地项目：

`D:\FILEEEEEEEEEEE\projects\nonlinear-nn-agent`

GitHub：

`https://github.com/yzy-151/nonlinear-nn-agent`

## 当前职业目标

目标岗位方向：Agent Harness / Runtime / Agent Coding / LLM 应用工程。

本项目不再只定位为“通信仿真实验”，而是定位为：

> 面向算法实验的 Agent Harness Runtime，用真实神经网络非线性拟合任务展示 Agentic Loop、工具系统、Hook、session 持久化、trace logging、失败重试、指标评估和报告生成。

## 当前 v0.1 已完成内容

新增模块：

- `src/nonlinear_agent/tools.py`
  - `ToolCall`
  - `ToolResult`
  - `ToolRegistry`
  - 支持同步/异步工具、timeout、retry、结构化失败结果。

- `src/nonlinear_agent/hooks.py`
  - `HookManager`
  - 支持 `before_tool`、`after_tool`、`on_error`、`on_metric`。

- `src/nonlinear_agent/session.py`
  - `ExperimentSession`
  - `SessionStore`
  - 支持 session 创建、保存、加载、load_or_create。

- `src/nonlinear_agent/trace.py`
  - `TraceEvent`
  - `TraceLogger`
  - 输出 JSONL event trace。

- `src/nonlinear_agent/runtime.py`
  - `HarnessRequest`
  - `ExperimentHarnessRuntime`
  - async generator 形式执行步骤，流式产出 start/tool_start/tool_end/metric/error/complete 事件。

新增测试：

- `tests/test_harness_runtime.py`
  - retry 成功路径。
  - session 保存/加载。
  - runtime 成功链路、hooks、trace。
  - runtime 失败链路、error hook、failed session。

新增文档：

- `docs/superpowers/plans/2026-07-21-experiment-agent-harness-v0.1.md`
- `docs/learning/experiment-agent-harness-v0.1.md`
- `docs/resume/experiment-agent-harness-resume.md`
- `docs/handoff/deepseek-continuation-plan.md`

## 接手前必须运行

```powershell
cd D:\FILEEEEEEEEEEE\projects\nonlinear-nn-agent
python -m unittest discover -s tests -p "test_*.py" -v
```

预期：所有测试通过。

## Git 操作规则

先检查：

```powershell
git status -sb
git diff --stat
```

不要覆盖用户未提交改动。提交前只 stage 本次相关文件。

如果网络需要代理：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7890'
$env:HTTPS_PROXY='http://127.0.0.1:7890'
```

推送：

```powershell
git push origin main
```

## v0.2 推荐目标

v0.2 不要继续只调 NMSE。优先把已有真实实验能力接入 harness。

### 任务 1：真实工具封装

新增文件：

`src/nonlinear_agent/experiment_tools.py`

建议工具：

- `generate_config_tool(base_config_path, experiment_id, overrides)`
- `run_training_tool(config_path)`
- `verify_artifacts_tool(output_dir, nmse_threshold_db)`
- `write_report_tool(session_id, metrics, artifacts)`

要求：

- 所有工具返回 dict。
- 返回中包含 `metrics` 或 `artifacts` 时 runtime 自动写入 session。
- 训练命令必须捕获 stdout/stderr、returncode、elapsed time。
- 失败时不要静默吞掉错误。

### 任务 2：命令行 Demo

新增文件：

`examples/nonlinear_fit/run_harness.py`

目标命令：

```powershell
python examples\nonlinear_fit\run_harness.py --experiment-id harness-demo-001 --base-config configs\model-search\lstsq-complexmp-o12-m150.yaml
```

输出：

- `sessions/harness-demo-001.json`
- `traces/harness-demo-001.jsonl`
- `reports/harness-demo-001/agent-summary.md`

### 任务 3：Trace Replay 报告

新增文件：

`src/nonlinear_agent/replay.py`

功能：

- 读取 JSONL trace。
- 统计 tool latency、失败步骤、重试次数、metric events。
- 生成 Markdown replay report。

输出示例：

`reports/harness-demo-001/replay.md`

### 任务 4：FastAPI SSE

新增文件：

`src/nonlinear_agent/server.py`

目标：

- 提供 `/runs/{session_id}/events` SSE。
- 把 runtime event 转成 Server-Sent Events。
- 不需要前端，curl 能看到事件即可。

### 任务 5：MCP Server

新增文件：

`src/nonlinear_agent/mcp_server.py`

目标：

- 暴露实验工具为 MCP tools。
- 工具至少包括 `generate_config`、`run_training`、`evaluate_nmse`、`write_report`。
- README 说明如何启动。

## v0.3 推荐目标

接 LangGraph，而不是替换现有 runtime：

- 用 LangGraph 实现同样的实验流程。
- 对比自研 runtime 与 LangGraph 的 checkpoint/resume/interrupt。
- 写文档说明为什么生产中通常选成熟框架，但自研原型帮助理解底层机制。

## 简历主线

不要写成“我做了一个自动训练脚本”。应该写：

> 设计并实现面向算法实验的轻量级 Agent Harness Runtime，将非线性神经网络拟合实验拆解为配置生成、训练执行、NMSE 评估、PSD 验证和报告生成等工具链，支持异步 Agentic Loop、工具注册、Hook、session 持久化、trace logging 和失败重试。

## DeepSeek 接手注意事项

- 不要删除已有 `reports/`，但默认 `.gitignore` 不上传 reports。
- 不要把大模型权重、`.pt`、`.pth`、Excel 文件提交到 GitHub。
- 不要重写 `experiment.py` 的训练逻辑，除非测试覆盖足够。
- 新功能先写 `tests/test_*.py`，再实现。
- 所有新增文档都要围绕求职证据：能力点、文件路径、测试命令、简历 bullet。

## 2026-07-22 v0.2 已完成内容

新增模块：

- `src/nonlinear_agent/experiment_tools.py`
  - `generate_config_tool`
  - `run_training_tool`
  - `verify_artifacts_tool`
  - `write_report_tool`
  - `build_experiment_tool_registry`

- `src/nonlinear_agent/replay.py`
  - `load_trace_events`
  - `summarize_trace`
  - `build_replay_markdown`
  - `write_replay_report`

- `examples/nonlinear_fit/run_harness.py`
  - 端到端执行 generate_config -> run_training -> verify_artifacts -> write_report。

新增测试：

- `tests/test_experiment_tools.py`
- `tests/test_replay.py`

真实 demo 命令：

```powershell
python examples\nonlinear_fit\run_harness.py --experiment-id harness-demo-v02 --base-config configs\model-search\lstsq-complexmp-o12-m150.yaml --output-dir reports\harness-demo-v02 --epochs 0 --nmse-threshold-db -35 --timeout-seconds 120
```

真实 demo 结果：

```text
NMSE: -37.4249 dB
parameter_count: 3626
model_type: complex_lstsq
feature_mode: complex_mp
mp_order_count: 12
```

v0.3 推荐目标调整：

1. 先做 FastAPI SSE，把 runtime event 变成在线流式接口。
2. 再做 cancellation/interrupt，模拟长训练中断。
3. 再做 MCP server，把 experiment tools 暴露成标准工具协议。
4. 最后做 LangGraph 对照版，展示 checkpoint/resume/human interrupt。

接手注意：

- `reports/`、`sessions/`、`traces/` 是运行产物，不要提交。
- `configs/harness-demo-v02.yaml` 是 demo 生成配置，除非要作为展示样例，否则不要提交。
- 下一步优先补 `server.py` 和 `tests/test_server.py`，不要继续调模型效果。

## 2026-07-22 v0.3 已完成内容

新增模块：

- `src/nonlinear_agent/server.py`
  - `HarnessRunSpec`
  - `build_harness_request`
  - `encode_sse_event`
  - `stream_sse_events`
  - `build_runtime`
  - `create_app`

- `examples/nonlinear_fit/serve_harness.py`
  - 启动 FastAPI/uvicorn 服务。

新增测试：

- `tests/test_server_streaming.py`

新增学习文档：

- `docs/learning/experiment-agent-harness-v0.3.md`
- `docs/superpowers/plans/2026-07-22-experiment-agent-harness-v0.3.md`

服务启动：

```powershell
python examples\nonlinear_fit\serve_harness.py --host 127.0.0.1 --port 8000
```

SSE 请求：

```powershell
curl -N -X POST http://127.0.0.1:8000/runs/server-demo/events -H "Content-Type: application/json" -d "{\"epochs\":0,\"nmse_threshold_db\":-35}"
```

v0.4 推荐目标：

1. 做 cancellation/interrupt，不要先做复杂前端。
2. 在 runtime 中加入 `CancellationToken` 或 `RunController`。
3. 让 SSE 流遇到 cancel 时产出 `cancelled` event 并保存 failed/cancelled session。
4. 再做 MCP server。
5. 最后做 LangGraph 对照版。

注意：FastAPI/uvicorn 已加入 `requirements.txt`，但 `server.py` 采用懒加载，未安装时核心测试仍可运行。

## 2026-07-22 v0.4 已完成内容

v0.4 修正项目定位：v0.1-v0.3 是可观测 workflow/harness 底座，v0.4 开始具备 LLM planner 和真正 plan-run-observe loop。

新增模块：

- `src/nonlinear_agent/llm.py`
  - `LLMClient`
  - `FakeLLMClient`
  - `OpenAICompatibleClient.deepseek()`

- `src/nonlinear_agent/planner.py`
  - `ExperimentPlanner`
  - `ExperimentPlan`
  - `PlannedExperiment`

- `src/nonlinear_agent/loop.py`
  - `ExperimentPlannerLoop`
  - `PlannerLoopResult`

- `examples/nonlinear_fit/run_planner_loop.py`
  - `--provider fake`
  - `--provider deepseek`

新增测试：

- `tests/test_llm_planner.py`

离线验证命令：

```powershell
python examples\nonlinear_fit\run_planner_loop.py --provider fake --max-rounds 2 --timeout-seconds 120
```

离线 demo 结果：

```text
status: stopped
rounds: 2
experiment: planner-demo-001
NMSE: -37.4249 dB
parameter_count: 3626
```

DeepSeek 使用方式：

```powershell
$env:DEEPSEEK_API_KEY="你的 key"
python examples\nonlinear_fit\run_planner_loop.py --provider deepseek --max-rounds 2 --timeout-seconds 120
```

注意：不要把 API key 写入代码、文档、session、trace 或 Git。

v0.5 推荐目标：

1. 做参数预算预估器，planner 输出后先检查 `parameter_count <= 4000`。
2. 做 Planner JSON schema 校验和自动修复。
3. 做 cancel/interrupt。
4. 做 MCP server。

## 2026-07-22 追加：Planner 设计空间增强

已新增：

- `model_type="spline_mlp"`
  - 一层 `Linear -> LearnableSplineActivation -> Linear`。
  - `LearnableSplineActivation` 是每通道 learnable 1D LUT，默认 `spline_knots=16`，一阶线性插值。
  - 适合表达用户提出的“1D LUT + 16 spline 激活函数，非线性层只用一层”的物理启发方案。

已增强 planner prompt：

- 明确可执行 `model_type`: `complex_lstsq`, `linear`, `tiny_mlp`, `spline_mlp`。
- 明确 `spline_mlp` 设计建议。
- 明确参数预算和历史 baseline。

已跑多实验 fake planner demo：

```text
planner-lstsq-o10-m120: 2422 params, NMSE -37.3298 dB
planner-spline-m48-h32: 3746 params, NMSE -3.5603 dB, failed threshold
planner-tiny-silu-m48-h32: 3234 params, NMSE -1.4559 dB, failed threshold
```

接手建议：

1. 对 `spline_mlp` 做更合理训练：更多 epoch、输入归一化、初始化、scheduler。
2. 增加参数预算预估器，planner 输出后先 reject 超预算方案。
3. 真实 DeepSeek 运行前先设置 `$env:DEEPSEEK_API_KEY`，不要把 key 写入命令历史或 Git。

## 2026-07-22 追加：v0.5 Planner Schema Guard

新增文件：

- `src/nonlinear_agent/planner_validation.py`
  - `normalize_planner_overrides`
  - `validate_planned_overrides`
  - `estimate_parameter_count`

新增测试：

- `tests/test_planner_validation.py`

行为：

- `train_samples` 自动映射为 `max_train_samples`。
- `rank` 等未支持字段会被拒绝。
- 超过 `parameter_count_max` 的候选不会运行。
- `ExperimentPlannerLoop` 会把拒绝项写入 history：`run_status: rejected`。

下一步建议真实 DeepSeek 再跑一轮，观察第二轮非法字段是否变成 rejected history，而不是训练脚本报错。

## 2026-07-22 追加：真实 DeepSeek 自我修正记录

真实 DeepSeek run 已验证初步 plan-run-observe 自我修正：

- 第一轮 spline_mlp 输出 `spline_range` 为 list，训练报错。
- 错误进入 loop history。
- 第二轮 DeepSeek 根据错误把 `spline_range` 修正为 scalar，并继续执行 spline_mlp。
- 第三轮发现 `exp_019` 达到 NMSE `-36.0275 dB`，主动停止。

最佳结果：

```text
exp_019
model_type: complex_lstsq
feature_mode: complex_mp
memory_depth: 24
mp_order_count: 4
parameter_count: 202
nmse_db: -36.0275 dB
```

这个记录可以作为面试中的“Agent loop 不是固定 workflow，而能根据错误和指标修正下一轮计划”的证据。

## 2026-07-22 追加：v0.6 Run Artifacts

本项目新增自动 run artifact 能力：

- `src/nonlinear_agent/run_artifacts.py`
- `ExperimentPlannerLoop(..., artifact_dir=...)`
- CLI 参数：`--artifact-dir`

每次 loop 会生成：

```text
runs/<timestamp-or-user-dir>/
  plans/
    round-001.json
    round-002.json
  result.json
  leaderboard.csv
  summary.md
```

验证命令：

```powershell
python examples\nonlinear_fit\run_planner_loop.py --provider fake --max-rounds 2 --max-experiments 1 --artifact-dir runs\fake-v06-check --goal "artifact smoke test"
python -m unittest discover tests
```

注意：

- `runs/` 已加入 `.gitignore`，默认不提交临时实验产物。
- planner 自动生成的 `configs/exp*.yaml`、`configs/planner-*.yaml` 也已忽略。
- 后续如果需要把某次重要实验放进 Git，建议手动整理成 `docs/experiments/*.md`，不要直接提交完整 `runs/`。

## 2026-07-22 追加：v0.7 Validation Guard

新增 planner 参数预检：

- `src/nonlinear_agent/planner_validation.py`
- 测试：`tests/test_planner_validation.py`

已覆盖：

- `spline_range=None` 或 list：reject，避免训练脚本 `float(None)` / `float(list)` 崩溃。
- 神经模型显式 `epochs=0`：reject。
- `complex_lstsq epochs=0`：allow。
- 正整数参数和值类型参数预检。
- loop 会把 validation error 写入 history：`run_status=rejected`，runtime 不会被调用。

验证命令：

```powershell
python -m unittest tests.test_planner_validation tests.test_llm_planner tests.test_experiment_core
python -m unittest discover tests
```

下一步建议：

1. 把 rejected/succeeded/failed 统计写进 `summary.md`。
2. 在 planner prompt 中明确“看到 rejected history 后必须解释修正策略”。
3. 增加自动保存 raw LLM response，便于审计 planner 输出和 parser 行为。

## 2026-07-22 追加：v0.8 Benchmark Evaluation

新增：

- `src/nonlinear_agent/benchmark.py`
- `examples/nonlinear_fit/run_benchmark.py`
- `tests/test_benchmark.py`
- 最新主学习文档：`docs/learning/experiment-agent-harness-v0.8.md`
- 唯一维护计划：`docs/superpowers/plans/experiment-agent-harness-plan.md`

能力：

- 固定 benchmark case。
- 统计 `target_hit_rate`、`rejected_rate`、`runtime_failure_rate`、`average_experiments_used`、`best_nmse_db`。
- 生成 `results.json`、`leaderboard.csv`、`summary.md`。

验证命令：

```powershell
python examples\nonlinear_fit\run_benchmark.py --output-dir benchmarks\fake-v08-check
python -m unittest tests.test_benchmark
python -m unittest discover tests
```

下一步 v0.9：

- 做 context/memory compression。
- 给 planner history 加窗口、压缩摘要和预算控制。

## 2026-07-22 追加：v0.9 Context / Memory Compression

新增：

- `src/nonlinear_agent/context_memory.py`
- `tests/test_context_memory.py`
- 最新主学习文档：`docs/learning/experiment-agent-harness-v0.9.md`

行为：

- `HistoryCompressor(recent_window=3)` 默认接入 `ExperimentPlannerLoop`。
- 完整 history 仍保留在 loop result 和 run artifacts。
- 发给 planner 的 history 会压缩为 `history-summary + 最近 N 条原始记录`。
- `history-summary` 包含状态统计、最佳实验、最佳 NMSE、参数量和代表性错误。

验证命令：

```powershell
python -m unittest tests.test_context_memory
python -m unittest discover tests
python examples\nonlinear_fit\run_planner_loop.py --provider fake --max-rounds 2 --max-experiments 1 --artifact-dir runs\fake-v09-check --goal "context memory smoke test"
```

下一步 v1.0：

- 做 Tool Registry / Skill 化。
- 明确工具 schema、allowed tools 渐进式披露和 tool error policy。

## 2026-07-22 追加：v1.0 Tool Registry / Skill 化

新增/更新：

- `src/nonlinear_agent/tools.py`
- `src/nonlinear_agent/experiment_tools.py`
- `src/nonlinear_agent/planner.py`
- 最新主学习文档：`docs/learning/experiment-agent-harness-v1.0.md`

能力：

- `ToolSpec`
- `ToolRegistry.describe_tools(category=...)`
- 真实实验工具带 schema、category、error_policy
- planner prompt 支持 ToolSpec 渐进式披露
- unknown tool 可按 `unknown_tool_policy="return_error"` 返回结构化失败

验证命令：

```powershell
python -m unittest tests.test_harness_runtime tests.test_experiment_tools tests.test_llm_planner
python -m unittest discover tests
```

下一步 v1.1：

- Reflection + Recovery Policy。
- 每轮结束生成失败原因、修正策略、下一轮避免项。

## 2026-07-22 追加：v1.1 Reflection / Recovery Policy

新增：

- `src/nonlinear_agent/reflection.py`
- `tests/test_reflection.py`
- 最新主学习文档：`docs/learning/experiment-agent-harness-v1.1.md`
- 结果图：`docs/assets/psd-exp016-best-41db-run.png`
- 结果图：`docs/assets/psd-exp019-self-correction-run.png`

能力：

- 每轮执行后生成 reflection record。
- 统计 `rejected`、`failed`、`succeeded`。
- 记录 `failure_causes`、`recovery_actions`、`avoid_next`。
- `RunArtifactWriter` 写入 `reflections/round-XXX.json`。
- 最终 `result.json` 和 `summary.md` 包含 reflection 信息。

验证命令：

```powershell
python -m unittest tests.test_reflection
python -m unittest discover tests
python examples\nonlinear_fit\run_planner_loop.py --provider fake --max-rounds 2 --max-experiments 1 --artifact-dir runs\fake-v11-check --goal "reflection smoke test"
```

下一步 v1.2：

- MCP Server / Tool Protocol。
- 把当前 `ToolSpec` 映射为标准 MCP tool schema。
- 让项目能回答“MCP 是什么、写过哪些 MCP 工具、Skill 和 MCP 有什么区别”。

## 2026-07-23 追加：v1.2 MCP Server / Tool Protocol

新增：

- `src/nonlinear_agent/mcp_server.py`
- `examples/nonlinear_fit/serve_mcp_tools.py`
- `tests/test_mcp_server.py`
- 最新主学习文档：`docs/learning/experiment-agent-harness-v1.2.md`

能力：

- `ToolSpec` 映射为 MCP-compatible tool schema。
- `MCPToolBridge.list_tools()` 支持 `tools/list`。
- `MCPToolBridge.call_tool()` 支持 `tools/call`。
- `MCPToolBridge.handle_json_rpc()` 支持 JSON-RPC 2.0 请求/响应。
- stdio JSON-lines mock server 可作为后续官方 MCP SDK 接入前的协议验证层。
- 底层复用现有 `ToolRegistry`，LLM Planner 与 MCP Client 共享同一套实验工具能力。

验证命令：

```powershell
python -m unittest tests.test_mcp_server
python -m unittest discover tests
```

下一步 v1.3：

- Async Runtime Hardening。
- cancellation / interrupt。
- per-tool timeout policy。
- retry policy 分类。
- structured error taxonomy。

## 2026-07-23 追加：v1.3 Async Runtime Hardening

新增：

- `src/nonlinear_agent/runtime_errors.py`
- `src/nonlinear_agent/run_control.py`
- `tests/test_runtime_hardening.py`
- 最新主学习文档：`docs/learning/experiment-agent-harness-v1.3.md`

能力：

- `ErrorType`：`validation_error`、`timeout_error`、`tool_error`、`metric_threshold_error`、`cancelled`。
- `RunController`：支持用户取消/中断。
- `RetryPolicy`：`always`、`never`、`retry_timeout`。
- `ToolResult` 增加 `error_type` 和 `retryable`。
- `TraceEvent` 增加 `error_type`。
- `ExperimentSession` 增加 `error_types` 和 `completed_steps`。
- `HarnessRequest.resume_from_step` 支持 step-level resume。
- `ReflectionPolicy` 增加 `error_type_counts`。

验证命令：

```powershell
python -m unittest tests.test_runtime_hardening
python -m unittest discover tests
```

下一步 v1.4：

- Evaluation Dashboard / Runtime Diagnostics。
- 对 benchmark 多次运行结果做汇总展示。
- 统计 error_type 分布、target_hit_rate、runtime_failure_rate、best_nmse_db。
