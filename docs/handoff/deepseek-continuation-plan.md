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
