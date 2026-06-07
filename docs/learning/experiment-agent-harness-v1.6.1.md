# Experiment Agent Harness v1.6.1 总学习文档

更新时间：2026-07-25

这是 v1.6.1 版本：v1.6 封版后的第一轮维护升级，重点是 Web UI 集成、源码文档化。

## 1. 本版主题

v1.6.1 做四件事：

- Web UI 全功能集成：三个 Tab（Workflow / Agent Planner / Benchmark）统一入口
- 源码文档化：16 个核心文件添加完整中文注释，新人可按注释自学
- Dashboard 增强：暗色主题、Aggregate Metrics 基于全部实验数据、自动刷新
- 稳定性改进：`.env.local` 自动加载、LLM 超时提升、错误优雅退出

## 2. 新增/更新文件

新增：
- `docs/learning/experiment-agent-harness-v1.6.1.md`

更新：
- `src/nonlinear_agent/server.py` — 新增 Benchmark 端点、Agent 端点加载 .env.local
- `src/nonlinear_agent/web_ui.py` — 三 Tab 重设计、暗色主题、事件格式化显示
- `src/nonlinear_agent/dashboard.py` — 暗色主题、Recent Runs 排序、NMSE 格式化
- `src/nonlinear_agent/diagnostics.py` — Aggregate Metrics 基于全部数据、按时间排序
- `src/nonlinear_agent/benchmark.py` — 源码注释
- `src/nonlinear_agent/context_memory.py` — 源码注释
- `src/nonlinear_agent/experiment_tools.py` — 源码注释
- `src/nonlinear_agent/llm.py` — 源码注释 + DeepSeek timeout 参数化
- `src/nonlinear_agent/loop.py` — 源码注释 + run_streaming 方法
- `src/nonlinear_agent/planner.py` — 源码注释
- `src/nonlinear_agent/planner_validation.py` — 源码注释
- `src/nonlinear_agent/reflection.py` — 源码注释
- `src/nonlinear_agent/runtime.py` — 源码注释
- `src/nonlinear_agent/session.py` — 源码注释
- `src/nonlinear_agent/tools.py` — 源码注释
- `tests/test_dashboard.py` — 更新测试断言
- `tests/test_server_streaming.py` — 更新测试断言
- `pyproject.toml` — version 1.6.1
- `README.md` — 新增 v1.6.1 版本记录

## 3. 已验证可用的功能

- `python agent.py run --provider fake` — 离线 Agent Loop
- `python agent.py run --provider deepseek` — DeepSeek 真实 API（自动读 .env.local）
- `python agent.py benchmark` — CLI Benchmark
- `python agent.py dashboard` — HTML Dashboard 生成
- `python agent.py diagnostics` — Markdown 诊断报告
- `python agent.py serve` — Web UI + SSE API
- `python -m unittest discover tests` — 88 测试通过

## 4. Web UI 的三 Tab 架构

| Tab | 功能 | API Key |
|---|---|---|
| Workflow | 固定工具链（config → train → verify → report） | 否 |
| Agent Planner | LLM 多轮实验（Fake 离线 / DeepSeek 真实） | 否/是 |
| Benchmark | 3 个测试 case 评估 Agent 质量 | 否 |

## 5. 简历表达

```text
将 Agent Harness 项目升级至 v1.6.1，新增 Benchmark 在线评测、Dashboard 自动刷新、全核心源码中文注释体系；重构 Web UI 为三 Tab 集成操作面板，统一离线 Demo、LLM 实验和 Benchmark 评估入口。
```
