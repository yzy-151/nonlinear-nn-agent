# Experiment Agent Harness v1.6.2 学习文档

更新时间：2026-07-26

## 1. 版本主题

v1.6.2 是维护定版，不再扩张新概念，重点补齐 Agent Harness 的工程闭环：

- 实验产物路径不污染项目根目录。
- Reflection 不只落盘，而是进入下一轮 planner history。
- Benchmark 从 3 个 smoke case 扩展为 5 个关键场景。
- Web UI 和 Dashboard 统一为深色展示界面。
- 文档收敛为新人上手、交接维护、简历表达和版本学习四条主线。

## 2. 你应该从这个版本学会什么

### Artifact Guard

LLM planner 和手工配置都可能写出 `output_dir: exp001` 这类裸路径。如果不处理，训练脚本会在项目根目录生成大量实验文件。v1.6.2 增加 `artifact_paths.normalize_experiment_output_dir()`，把裸实验目录统一归入 `reports/`。

面试要点：

> Agent 系统要防止 LLM 生成的路径污染工作区。我的做法是在 planner validation 和 config generation 两层都归一化 output_dir，属于 runtime guardrail 的一部分。

### Reflection Context

旧问题是 reflection 只生成 `reflections/round-XXX.json`，但下一轮 planner 看不到这些恢复建议。v1.6.2 把 reflection 以 `run_status: reflection` 的记录写入 history，并在 benchmark/leaderboard 统计时过滤这种非实验记录。

面试要点：

> Reflection 要进入决策上下文才有意义。否则它只是日志，不是 agentic loop 的一部分。

### Benchmark Coverage

3 个 case 只能证明 smoke test。v1.6.2 使用 5 个 case 覆盖：

- target hit under budget
- invalid planner output rejection
- runtime failure handling
- reflection-based recovery
- experiment budget stop

指标口径：

- `target_hit_rate` = 达标 case 数 / 总 case 数。
- `rejected_rate` = rejected 记录数 / 全部实验记录。
- `runtime_failure_rate` = failed 记录数 / 全部实验记录。
- `average_experiments_used` = 消耗实验数 / case 数。
- `best_nmse_db` = 全部 case 最优 NMSE，越小越好。

### 文档收敛

本版本删除旧的零散 case/interview/plan 文档，把内容合并到：

- `docs/onboarding/newcomer-guide.md`
- `docs/handoff/llm-continuation-plan.md`
- `docs/resume/experiment-agent-harness-resume.md`
- `docs/learning/experiment-agent-harness-v*.md`

这能避免后续维护时同一件事散落在多处，面试前也更容易复习。

## 3. 主要改动文件

```text
src/nonlinear_agent/artifact_paths.py
src/nonlinear_agent/planner_validation.py
src/nonlinear_agent/experiment_tools.py
src/nonlinear_agent/loop.py
src/nonlinear_agent/benchmark.py
src/nonlinear_agent/run_artifacts.py
src/nonlinear_agent/server.py
src/nonlinear_agent/web_ui.py
src/nonlinear_agent/dashboard.py
examples/nonlinear_fit/run_benchmark.py
tests/test_planner_validation.py
tests/test_experiment_tools.py
tests/test_reflection.py
tests/test_benchmark.py
tests/test_server_benchmark.py
tests/test_web_ui.py
```

## 4. 验证命令

```powershell
python -m unittest discover tests
python examples\nonlinear_fit\run_benchmark.py --output-dir benchmarks\fake-v16-doc-ui-check
python agent.py dashboard
python agent.py serve --host 127.0.0.1 --port 8000
```

预期：

- 单元测试全部通过。
- Benchmark 输出 5 个 case 的 summary。
- Dashboard 生成 `docs/diagnostics/agent-runtime-dashboard.html`。
- 浏览器打开 `http://127.0.0.1:8000/` 后能看到深色 Web UI，并可运行 Workflow / Agent Planner / Benchmark。

## 5. 简历写法

- 维护并定版面向算法实验的 Agent Harness Runtime，补齐 artifact path guard、reflection-to-history 决策闭环、5-case benchmark evaluation 和 Web/Dashboard 展示界面，使 LLM 实验 Agent 具备可复现、可审计、可交接的工程化能力。

## 6. 后续边界

本项目到 v1.6.2 已经适合作为 Agent Harness 岗位项目展示。后续优先做维护：

- 保证测试通过。
- 更新 README 和面试表达。
- 保持 Web UI 能演示。
- 不再无目标堆新模块。

RAG、长期语义记忆、多 Agent 协作等内容交给 Storm 或新的独立项目覆盖。
## 9. v4.0.0-a 补充：CodingAgent 生成的新模型怎样被执行

本阶段解决的不是“再给 `build_model()` 增加一个 `if model_type == ...`”，而是建立一个开放契约：模型名称可以完全未知，但它必须说明自己是谁、怎样训练、怎样估算参数量、架构由哪些节点和边组成。

### 四个核心对象

- `ModelDescriptor`：模型名、版本、训练模式、配置 schema、架构节点和边。WritingAgent 后续应读取它画图，而不是按模型名猜结构。
- `ModelPlugin`：插件必须实现 `estimate_parameters(config)` 和 `train(request)`。普通神经网络可在 `train()` 中复用公共 trainer，闭式算法或特殊优化也可提供自定义训练。
- `CandidateRegistry`：从 `models/candidates/*.json` manifest 加载插件。它不限制模型名字，但入口文件 resolve 后必须留在候选目录，并校验 descriptor、配置和参数预算。
- `TrainingResult`：统一返回终态、数值指标、artifact 路径和 descriptor hash，使 ExecutionAgent 与 WritingAgent 不依赖模型内部实现。

### 为什么要固定 runner

ExecutionAgent 不接受 CodingAgent 提供的任意 shell 命令，只能调用 `run_candidate_model`。工具内部启动固定的 `python -m nonlinear_agent.model_plugins.runner`，清理 secret 环境变量，并在子进程结束后重新检查：

1. `nmse_db`、`parameter_count` 等指标必须是有限数；
2. 报告参数量必须等于契约校验阶段的估算；
3. descriptor hash 必须和执行前一致，防止训练时替换模型描述；
4. 所有 artifact 必须真实存在且位于 workspace 内；
5. 插件返回 failed 或 runner 非零退出都不能伪装成成功。

### 当前边界

v4.0.0-a 证明的是“未知模型插件可被安全边界检查并由 ExecutionAgent 执行”，不是“LLM 已能稳定自主写模型”。当前子进程提供崩溃隔离和环境清理，但不是容器级 OS sandbox；后续 v4.0.0-b 仍需加入 LLM `CodeChangePlan`、AST/import gate、测试门和最多两轮事实修复，之后才能统计真实 CodingAgent pass rate。
