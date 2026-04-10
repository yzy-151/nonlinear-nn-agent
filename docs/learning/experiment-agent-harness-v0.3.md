# Experiment Agent Harness v0.3 学习文档

更新时间：2026-07-22

## 这一版做了什么

v0.3 给实验 Agent Harness 增加了流式服务层。v0.1 解决 runtime 抽象，v0.2 接入真实实验工具，v0.3 开始把 runtime event 变成可被前端、CLI、WebSocket/SSE 服务消费的在线事件流。

新增核心文件：

- `src/nonlinear_agent/server.py`：SSE 编码、HarnessRunSpec、默认工具链构造、FastAPI app 工厂。
- `examples/nonlinear_fit/serve_harness.py`：启动 FastAPI 服务的 CLI。
- `tests/test_server_streaming.py`：验证 SSE 格式、event stream 和默认工具链构造。

更新文件：

- `requirements.txt`：增加 `fastapi`、`uvicorn` 作为 server 运行依赖。
- `src/nonlinear_agent/__init__.py`：导出 v0.3 server API。

## 为什么这一步重要

Agent Harness 岗位关心的不只是“最终返回一个答案”，而是执行过程能不能在线观测。真实 Agent 经常要处理长链路：规划、工具调用、等待外部 API、重试、验证、生成报告。如果用户只能等最后结果，系统很难调试，也很难做体验优化。

SSE 层让 runtime 每个事件都能被实时消费：

- `start`：任务开始。
- `tool_start`：某个工具开始执行。
- `tool_end`：工具成功结束，带 attempts、output、latency。
- `metric`：训练指标流式出现，例如 NMSE。
- `error`：失败路径实时暴露。
- `complete`：任务结束。

## 当前接口形态

纯 Python 层：

```python
from nonlinear_agent.server import HarnessRunSpec, build_harness_request, build_runtime, stream_sse_events

spec = HarnessRunSpec(session_id="server-demo")
runtime = build_runtime(".", session_id=spec.session_id)
request = build_harness_request(spec)

async for chunk in stream_sse_events(runtime, request):
    print(chunk)
```

FastAPI 层：

```powershell
python examples\nonlinear_fit\serve_harness.py --host 127.0.0.1 --port 8000
```

启动后可请求：

```powershell
curl -N -X POST http://127.0.0.1:8000/runs/server-demo/events `
  -H "Content-Type: application/json" `
  -d "{\"epochs\":0,\"nmse_threshold_db\":-35}"
```

接口会返回 `text/event-stream` 格式，每个事件类似：

```text
event: metric
data: {"session_id":"server-demo","event_type":"metric",...}
```

## 你应该从中学会什么

### 1. SSE 是最小可用流式接口

相比 WebSocket，SSE 更适合服务端单向推送：Agent runtime 把状态不断推给客户端，客户端只读事件。对于训练进度、工具状态、trace event，这已经够用。

后续如果要做双向实时交互、barge-in、语音中断，再升级 WebSocket。

### 2. 服务层不应该绑死业务逻辑

`server.py` 没有重写训练逻辑，而是复用：

- `build_experiment_tool_registry`
- `ExperimentHarnessRuntime`
- `SessionStore`
- `TraceLogger`
- `write_replay_report`

这说明服务层只是适配器，不应该把 runtime、tools、training 混成一个大函数。

### 3. 可选依赖要懒加载

`create_app()` 内部才 import FastAPI。这样没有安装 FastAPI 时，核心库和单元测试仍然可用。工程上这比在模块顶层 import server 依赖更稳。

### 4. 岗位表达要强调“在线可观测”

v0.3 以后，项目可以明确说支持流式观测 Agent 执行链路。面试时不要只讲“我用了 FastAPI”，要讲：

> 我把 Agent runtime 的内部事件转成 SSE 流，让工具调用状态、耗时、重试、指标和错误可以实时返回给客户端。这解决的是长任务 Agent 的可观测性和用户等待体验问题。

## 当前不足

- 还没有实现 cancel/interrupt。
- 还没有 WebSocket 双向通信。
- 还没有 MCP server。
- 还没有前端可视化 trace timeline。

v0.4 建议做 cancel/interrupt，因为它最接近岗位里 barge-in/实时交互的能力。
