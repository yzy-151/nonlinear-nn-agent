# 新人上手指南：Nonlinear NN Agent Harness

更新时间：2026-07-26

这份文档给第一次接手项目的人看。目标是 15 分钟内知道项目是什么、怎么跑、从哪里读代码、当前状态如何、哪些内容不要乱动。

## 1. 项目一句话

这是一个面向 Agent Harness / Runtime / Agent Coding 岗位的项目：用真实非线性系统拟合实验作为业务场景，实现 LLM planner、受控工具调用、runtime event streaming、trace/session、context compression、reflection、benchmark、MCP bridge、diagnostics dashboard 和 Web UI。

不要把它讲成“自动训练脚本”。正确讲法是：

> LLM 只负责结构化规划，Harness Runtime 负责工具执行、trace、session、错误分类、上下文压缩、reflection、benchmark 和结果落盘。底层任务是真实非线性拟合实验，所以可以展示 NMSE、PSD、leaderboard 和完整运行证据。

## 2. 项目路径

```text
D:\FILEEEEEEEEEEE\projects\nonlinear-nn-agent
```

注意：不要在 `storm` 仓库里改这个项目。

## 3. 最快跑起来

```powershell
cd D:\FILEEEEEEEEEEE\projects\nonlinear-nn-agent
pip install -r requirements.txt
python -m unittest discover tests
python agent.py dashboard
python agent.py run --provider fake --max-rounds 2 --max-experiments 1 --artifact-dir runs\newcomer-first-run
```

Web UI：

```powershell
python agent.py serve --host 127.0.0.1 --port 8000
```

浏览器打开：

```text
http://127.0.0.1:8000/
```

## 4. 先读哪些文件

建议顺序：

1. `README.md`
2. `docs/learning/experiment-agent-harness-v1.6.2.md`
3. `docs/learning/experiment-agent-harness-v1.6.1.md`
4. `docs/learning/experiment-agent-harness-v1.6.md`
5. `docs/handoff/deepseek-continuation-plan.md`
6. `docs/resume/experiment-agent-harness-resume.md`
7. `src/nonlinear_agent/loop.py`
8. `src/nonlinear_agent/runtime.py`
9. `src/nonlinear_agent/tools.py`
10. `src/nonlinear_agent/experiment_tools.py`
11. `src/nonlinear_agent/server.py`
12. `src/nonlinear_agent/web_ui.py`

## 5. 核心链路

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

## 6. 常用命令

| 命令 | 作用 |
|---|---|
| `python agent.py run --provider fake` | 离线运行 planner loop demo |
| `python agent.py run --provider deepseek` | 调 DeepSeek 真实设计实验 |
| `python agent.py benchmark` | 跑内置 benchmark |
| `python agent.py diagnostics` | 生成 Markdown dashboard |
| `python agent.py dashboard` | 生成 HTML dashboard |
| `python agent.py serve` | 启动 Web UI + SSE API |

## 7. 重要产物

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

## 8. 当前状态审查

### 根目录实验产物

历史上根目录出现过大量 `exp_001/`、`exp-007/`、`experiment_014/`、`output/`、`outputs/`、`results/`、`experiments/`、`exps/` 等目录。根因是 `output_dir` 被当成普通配置字段：当 planner 或手工配置写 `output_dir: exp_001` 时，`train.py` 会按项目根目录解析并写出产物。

当前修复：

- `src/nonlinear_agent/artifact_paths.py` 提供 `normalize_experiment_output_dir()`。
- `planner_validation.normalize_planner_overrides()` 会把裸实验目录名改为 `reports/<name>`。
- `generate_config_tool()` 也做同样归一化，防止手工调用绕过 planner。
- 旧根目录产物已移到 `reports/relocated-root-artifacts/`。
- `.gitignore` 已忽略根目录误生成的实验输出目录。

关于 `artifact_paths.py`：保留是有必要的。该逻辑同时被 planner guard 和 experiment tool 使用，单独成文件能避免循环依赖和复制逻辑。

### Reflection 是否进入下一轮决策

旧实现会写 `runs/<run-id>/reflections/round-XXX.json`，也会保存在 `PlannerLoopResult.reflections`，但下一轮 planner 只读取压缩后的 `history`，所以 reflection 没有稳定进入下一轮决策。

当前修复：

- 每轮 reflection 会追加为 `run_status: reflection` 的 history record。
- 下一轮 planner prompt 能看到 `reflection-round-XXX`、`recovery_actions`、`avoid_next`。
- benchmark 和 leaderboard 会过滤 reflection/summary record，避免把复盘当实验统计。

设计取舍：

- runtime 错误、schema 失败、timeout、指标阈值、预算停止这类 reflection 默认用确定性逻辑做，便宜、稳定、可审计。
- LLM reflection 可以作为后续增强，用来提出实验假设，但必须过 schema guard，并且只能作为建议，不作为事实来源。

### Benchmark 是否合理

3 个 case 只够 smoke test，不够面试级评估。当前 benchmark 覆盖 5 类行为：

- target hit under budget
- invalid planner output rejection
- runtime failure handling
- reflection-based recovery
- experiment budget stop

更强版本可以继续加：多 seed、长上下文压缩、tool timeout/retry、真实 DeepSeek replay case。

### Memory 状态

当前 memory 是短期实验记忆：

- 完整 history 保存在 artifacts。
- prompt memory 是 `history-summary + recent records`。
- reflection 已进入下一轮 history。

它还不是完整长期记忆系统。缺少跨 run 检索、向量/BM25 召回、过期记忆校验、记忆写入策略、用户/session 级绑定、记忆污染修复。

### 面试覆盖边界

本项目强覆盖：

- Agent harness/runtime
- tool definition / registration / tool call execution
- schema guard and parameter budget
- trace/session/artifact observability
- planner loop and plan-run-observe
- benchmark and regression evaluation
- context compression
- deterministic reflection and recovery policy
- MCP bridge basics
- UI/demo packaging

部分覆盖：

- memory system：有短期压缩，没有长期检索记忆
- hallucination handling：覆盖工具参数幻觉，不覆盖 RAG 答案幻觉
- Skill：ToolSpec 接近 Skill 描述层，但不是完整 Skill marketplace/hot reload
- ReAct：是 plan-run-observe，不是教科书 Thought/Action trace

需要 Storm 或另一个项目支撑：

- RAG 全流程：解析、切片、embedding、向量/BM25 混合检索、rerank、答案生成
- RAG 评测：Ragas、answer relevance、context precision/recall
- 长期语义记忆
- 多 Agent 协作和并发
- 更完整的 LangGraph/LangChain state graph 对比

## 9. 新人不要做什么

- 不要提交 `.env.local`、`.claude/settings.local.json`、API key。
- 不要把完整 `runs/`、`reports/` 大量产物直接提交。
- 不要把临时脚本、截图、缓存放进项目根目录；统一放 `C:\Users\yzy\Desktop\codex\`。
- 不要让 LLM 直接执行 shell；必须通过受控工具链。
- 不要为了追版本继续堆功能；当前项目以后以维护、展示、面试表达为主。
