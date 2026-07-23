# Newcomer Guide: Nonlinear NN Agent Harness

更新时间：2026-07-23

这份文档给第一次接手项目的人看。目标是 15 分钟内知道项目是什么、怎么跑、从哪里读代码、面试怎么讲。

## 1. 项目一句话

这是一个面向 Agent Harness / Runtime / Agent Coding 岗位的项目：用真实非线性系统拟合实验作为业务场景，实现 LLM planner、受控工具调用、runtime event streaming、trace/session、context compression、reflection、benchmark、MCP bridge 和 diagnostics dashboard。

## 2. 最快跑起来

在项目根目录：

```powershell
pip install -r requirements.txt
python -m unittest discover tests
python agent.py dashboard
python agent.py run --provider fake --max-rounds 2 --max-experiments 1 --artifact-dir runs\newcomer-first-run
```

如果要看 Web UI：

```powershell
python agent.py serve --host 127.0.0.1 --port 8000
```

然后打开：

```text
http://127.0.0.1:8000/
```

## 3. 先读哪些文件

建议顺序：

1. `README.md`
2. `docs/learning/experiment-agent-harness-v1.6.md`
3. `docs/case-studies/deepseek-planner-self-correction.md`
4. `src/nonlinear_agent/loop.py`
5. `src/nonlinear_agent/runtime.py`
6. `src/nonlinear_agent/tools.py`
7. `src/nonlinear_agent/experiment_tools.py`
8. `src/nonlinear_agent/server.py`
9. `src/nonlinear_agent/web_ui.py`

## 4. 核心链路

```text
User Goal
  -> ExperimentPlanner
  -> ExperimentPlan JSON
  -> validate_planned_overrides
  -> HarnessRunSpec
  -> HarnessRequest
  -> ExperimentHarnessRuntime
  -> ToolRegistry
  -> generate_config / run_training / verify_artifacts / write_report
  -> TraceEvent
  -> history
  -> ReflectionPolicy
  -> RunArtifactWriter
```

## 5. 常用命令

| 命令 | 作用 |
|---|---|
| `python agent.py run --provider fake` | 离线运行一个 planner loop demo |
| `python agent.py run --provider deepseek` | 调 DeepSeek 真实设计实验 |
| `python agent.py benchmark` | 跑内置 benchmark |
| `python agent.py diagnostics` | 生成 Markdown dashboard |
| `python agent.py dashboard` | 生成 HTML dashboard |
| `python agent.py serve` | 启动 Web UI + SSE API |

## 6. 重要产物

Planner loop：

```text
runs/<run-id>/
  plans/
  reflections/
  result.json
  leaderboard.csv
  summary.md
```

单次实验：

```text
reports/<experiment-id>/
  metrics.json
  psd.png
  agent-harness-report.md
  replay.md
```

诊断页面：

```text
docs/diagnostics/agent-runtime-dashboard.md
docs/diagnostics/agent-runtime-dashboard.html
```

## 7. 新人不要做什么

- 不要提交 `.env.local`、`.claude/settings.local.json`、API key。
- 不要把完整 `runs/`、`reports/` 大量产物直接提交。
- 不要让 LLM 直接执行 shell；必须通过受控工具链。
- 不要为了追版本继续堆功能；当前项目功能基本封版，后续以 case study 和面试表达为主。

## 8. 面试主线

项目讲法不要说“自动训练脚本”。应说：

> 我实现的是一个轻量 Agent Harness Runtime。LLM 只负责结构化规划，Runtime 负责工具执行、trace、session、错误分类、上下文压缩、reflection 和 benchmark。底层任务是真实非线性拟合实验，所以可以展示 NMSE、PSD、leaderboard 和完整运行证据。
