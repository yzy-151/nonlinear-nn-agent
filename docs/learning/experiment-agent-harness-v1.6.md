# Experiment Agent Harness v1.6 总学习文档

更新时间：2026-07-23

这是当前最新主学习文档。v1.6 是收口版本，不再继续堆核心功能。

## 1. 本版主题

v1.6 做三件事：

- 文档收口：case study、Q&A、新人上手。
- 新人友好：明确读代码顺序、常用命令、产物位置。
- 展示 UI：`python agent.py serve` 后打开 `/`，可以从浏览器触发 runtime streaming demo。

## 2. 新增文件

- `docs/onboarding/newcomer-guide.md`
- `docs/case-studies/deepseek-planner-self-correction.md`
- `docs/interview/agent-harness-qa.md`
- `src/nonlinear_agent/web_ui.py`

更新：

- `src/nonlinear_agent/server.py`
- `tests/test_server_streaming.py`
- `README.md`
- `docs/superpowers/plans/experiment-agent-harness-plan.md`
- `docs/handoff/deepseek-continuation-plan.md`
- `docs/resume/experiment-agent-harness-resume.md`

## 3. UI 展示方式

启动：

```powershell
python agent.py serve --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000/
```

首页支持：

- 打开 HTML diagnostics dashboard。
- 打开 Markdown diagnostics dashboard。
- 填 session id、goal、epochs、threshold、timeout。
- 通过 `fetch` POST `/runs/{session_id}/events`。
- 在页面中实时显示 SSE chunks。

## 4. 为什么这是封版版本

面试文档里高频 Agent Harness 点已经覆盖：

- context management
- tool calling
- MCP
- runtime
- benchmark
- reflection
- diagnostics
- CLI/UI delivery

继续堆新功能会让主线发散。后续精力应该转到：

- 熟读 Q&A。
- 准备 2-3 分钟项目介绍。
- 算法题和基础八股。
- RAG 部分用 Storm 项目覆盖。

## 5. 验证

```powershell
python -m unittest tests.test_server_streaming
python -m unittest discover tests
python agent.py dashboard
python agent.py serve --host 127.0.0.1 --port 8000
```

## 6. 简历表达

```text
将 Agent Harness 项目收口为可展示交付版本，补充新人上手文档、DeepSeek self-correction case study、Agent Harness 面试 Q&A，并为 FastAPI SSE runtime 增加浏览器首页 UI，支持从页面配置实验参数并实时查看工具调用事件流。
```
