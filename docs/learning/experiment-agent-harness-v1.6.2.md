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
- 本地维护的实施与交接记录
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

v4.0.0-a 证明的是“未知模型插件可被安全边界检查并由 ExecutionAgent 执行”，不是“LLM 已能稳定自主写模型”。当前子进程提供崩溃隔离和环境清理，但不是容器级 OS sandbox。

## 10. v4.0.0-b 补充：CodingAgent 怎样写出可执行的新模型

### 为什么不能只返回 ModelClass

单独一个网络类不能被 ExecutionAgent 直接执行，因为系统仍不知道输入怎样加载、损失怎样计算、参数量怎样估算、训练结果写到哪里。v4.0.0-b 使用两个结构化交接对象：

- `CodingTaskSpec`：包含任务目标、候选名、smoke config、参数上限、超时和额外约束；
- `CodeChangePlan`：LLM 必须返回完整替换文件集，包括 Python plugin 与 manifest。plugin 自己实现 `descriptor`、`estimate_parameters()` 和 `train()`。

因此 CodingAgent 可以设计仓库从未出现过的网络、闭式算法或自定义训练过程；ExecutionAgent 不需要认识模型名字，只认识稳定的 `ModelPlugin` 协议。

### 一次 coding 尝试经过哪些闸

1. 严格 JSON：拒绝 Markdown fence、缺字段、额外字段和不匹配的 task/candidate；
2. 路径：所有文件必须位于 `models/candidates/<candidate>/`，拒绝绝对路径、反斜杠和 `..`；
3. AST capability gate：先检查语法，再拒绝 `os/subprocess/socket/network/dynamic import/eval/exec` 等能力与模块顶层执行；
4. contract gate：子进程加载 manifest，校验 descriptor、配置 schema 和参数预算；
5. smoke gate：固定 runner 真实调用 `train()`，复核有限 NMSE、参数量、descriptor hash、`metrics.json` 与有效 PNG；
6. trace：只记录 prompt、response、文件的 SHA-256 和失败事实，不保存 API key 或整段生成源码。

AST gate 与清理环境的子进程是工程防线，不是容器或虚拟机级 OS sandbox。它能阻止常见越权代码和隔离崩溃，但不能对恶意 Python 给出形式化安全保证；生产环境仍应增加容器、只读挂载、网络隔离和资源 cgroup/job object。

### 两轮修复为什么算 agentic coding

第一次生成失败后，程序不替 LLM 写修复策略，只提取可验证事实，例如：

```text
static: plugin.py: SyntaxError line 18: '(' was never closed
RuntimeError: candidate runner failed: ValueError: estimated parameter count 4200 exceeds parameter budget 4000
FileNotFoundError: candidate result is missing required artifact: psd.png
```

下一次 coding prompt 同时包含原始 `CodingTaskSpec` 和这些干净事实，要求 LLM 重写完整候选包。默认最多修复两轮，即总计最多三次模型调用。离线 E2E 已验证“首轮语法错误 -> 第二轮完整插件 -> runner smoke 成功”，但这只证明闭环机制，不代表真实 DeepSeek 的 pass rate；后续必须在固定 coding task 集上单独统计 pass@1、pass@3、平均修复轮数和未授权写入数。

### 模型怎样切换

CodingAgent 接受 `ModelRouter`，固定使用 `coding` role。角色配置可以把 idea/planner 交给便宜模型，把复杂代码交给专用 coding 模型；OpenAI-compatible 与 SDK 客户端都支持角色化 system prompt，避免 coding 调用仍携带旧 planner 的“只能选择预置 model_type”限制。

### 面试表达

> 我没有让 CodingAgent 输出任意 shell，也没有把新网络硬塞进已有 model_type 分支。LLM 生成完整 ModelPlugin 候选包，Harness 先做 JSON、路径和 AST capability gate，再由固定子进程验证契约并真实 smoke 训练。失败只抽取事实回传，最多两轮修复；ExecutionAgent 最终只接收经过 descriptor hash、参数预算、NMSE 和 PSD 证据复核的结果。当前离线 E2E 证明闭环可用，真实模型能力用独立 pass@1/pass@3 评测，不混为一谈。

## 11. v4.0.0-c 补充：WritingAgent 怎样避免“漂亮地胡说”

### EvidenceBundle 不是把全部日志塞进 prompt

WritingAgent 不直接读取杂乱 history，而是接收压缩后的 `EvidenceBundle`。每条事实都有稳定 ID：

- `architecture:<name>`：ModelDescriptor 的节点、边、operation 和 details；
- `metric:<run_id>`：NMSE、基线、参数量、达标状态和成本；
- `artifact:psd:<run_id>`：真实 PSD 路径；
- `failure:<id>`：确定性失败事实；
- `constraint:<name>`、`plan:hypotheses`、`trace:<n>` 和 `aggregate:performance`。

这使 LLM 的任务从“重新理解整个工程”缩小为“在已给事实之间组织叙事”，也让报告结论可以反向追到来源。

### NarrativeSpec 的双层 fidelity

WritingAgent 输出执行摘要、架构分析、性能分析、失败分析、经验和限制六段内容。每段必须引用 EvidenceBundle 中存在的 ID。随后确定性 checker 做两层检查：

1. 引用 fidelity：未知或虚构 evidence ID 直接拒绝；
2. 数字 fidelity：叙事里的数字必须来自原始 source 或派生聚合指标，并允许与显示精度一致的舍入。比如把真实 `-37.49 dB` 写成 `-99 dB` 会失败。

LLM 负责语言与归纳，程序负责事实边界。这样比让程序写固定模板更灵活，也比完全相信 LLM 更可审计。

### 为什么报告能支持任意新模型

旧架构图根据 `model_type` 在 `complex_lstsq` 和神经网络模板之间二选一，会把未知模型画错。v4.0.0-c 的 `ArchitectureGraphSpec` 直接读取 `ModelDescriptor.nodes/edges`，通用 DAG 布局器展示每个节点的 label、operation、details 和边标签。缺 descriptor 时只显示 `Descriptor unavailable`，不会猜测隐藏层、激活函数或卷积结构。

### 为什么 HTML 和 PDF 必须同源

旧实现的网页和 ReportLab PDF 是两套模板，同一报告会出现章节、字体和分页差异。新实现先生成一份 print-ready HTML，再由 headless Edge 打印为 PDF：

- A4 print CSS 控制页边距、不可拆分图像和跨页表头；
- Microsoft YaHei 优先，消除中文与 Unicode 黑框；
- 页面同时包含关键指标、架构、真实 PSD、执行表、失败/消融、代码、trace、复现与限制；
- HTML 仍可响应式浏览，PDF 与浏览器看到的是同一份事实和版式。

### 面试表达

> WritingAgent 不直接自由发挥。我先把 ModelDescriptor、TrainingResult、PSD、失败和 trace 转成带 evidence ID 的 EvidenceBundle；LLM 输出每段带引用的 NarrativeSpec，确定性 fidelity gate 再检查未知引用和不受支持的数字。架构图完全由 descriptor 的节点和边动态生成，HTML 与 PDF 同源。这样新模型不需要预制原理图，报告也不会因为 LLM 文笔流畅就绕过事实校验。

## 12. v4.0.0-d 补充：四个 Agent 怎样成为一条可运行主链

### Multi-Agent 的价值不在角色数量

此前 Idea/Plan、Coding、Execution 和 Writing 都有独立组件与单测，但 `supervisor_graph.py` 只有一个 supervisor 节点。准确说法只能是“有多个 Agent 组件”，不能说“完成了 Multi-Agent runtime”。v4.0.0-d 的变化是把它们放进同一个 LangGraph，并由 Supervisor 统一拥有状态、路由、预算、取消、失败回路和终态：

```text
idea_plan -> plan_gate -> coding -> execution -> writing -> terminal
                    execution failure -> idea_plan (bounded)
```

Worker 不共享聊天记录，只收到窄的结构化 handoff。Plan Agent 接收 goal 和上次失败事实；Coding 接收已批准 plan；Execution 接收通过 gate 的 manifest 与 config；Writing 接收 plan、代码变化、真实执行结果和失败列表。这样既减少 token，也避免一个角色看到不该看到的 secret 或 raw history。

### Reflection 在这里是什么

Execution 失败后，程序先用 `FailureHandoff` 把异常转成事实：classification、tool、error、retryable 和 suggested action。它不替 LLM 决定新模型或超参数。若失败可恢复且 `max_replans` 尚未用完，这组事实成为下一次 Idea/Plan 的 `failure_facts`；Plan Agent 再负责提出新的因果方案。

这正是“确定性程序提取事实，LLM 做策略推理”的分工。timeline 同时记录 `failure:<classification>` 引用和完整 failure facts，因此在 Web 控制台能看到“上次为什么错、下一次计划基于什么改”。

### 为什么只有一个 terminal

每个节点只更新 `status`，最终都路由到统一 terminal 节点。正常完成、取消、invalid plan、Coding gate 失败、不可恢复执行错误、重规划预算耗尽、token/cost 越界最终都生成同一结构：run ID、status、error 和报告路径。Web 和调用方不需要猜“哪个 Agent 的最后一条消息算结束”。

取消采用协作式语义：正在执行的 LLM 或训练调用先返回，Supervisor 在进入下一节点前检查 cancel event。它不会粗暴杀死正在写文件的线程，因此产物状态更可解释；真正的进程级强制取消仍由底层训练工具的 timeout/control plane 负责。

### 角色 timeline 怎样支持面试讲解

每个角色事件包含：

- `run_id / sequence / role / status`：谁在何时序做了什么；
- `input_refs / output_refs`：handoff 来自哪个 plan、failure、artifact 或 report；
- `model_usage`：实际 provider、model、prompt/completion token、cost 和 latency；
- `failure_facts`：执行失败的干净事实，不含 raw chain-of-thought。

Execution 事件的 `model_usage` 必须为空，因为它只能调用 ToolRegistry。Idea/Coding/Writing 可配置不同模型，但选择来自 ModelRouter 配置，不由 Agent 临时绕过预算。

### 隔离 worktree 与可下载报告如何同时成立

CodingAgent 继续只在自有 worktree 写候选源码，main 的新模型源码写入数仍为 0。训练也在该 worktree 验证 manifest、descriptor hash、参数量、metrics.json 和 PSD。通过后，确定性 runtime 只把已存在且路径位于 worker workspace 内的 trace/metrics/PSD 发布到主工程 `reports/<run>/evidence/`；Writing 报告再写到主工程的 `reports/<run>/task-report/`。因此安全隔离没有被破坏，Web `/artifacts/` 又能真正下载证据和报告。

### 面试表达

> 我把原先可单测但互相独立的四个 Agent 接进同一 LangGraph。Supervisor 只负责结构化状态、路由、预算、取消和唯一终态；Execution 保持 tool-only。失败由程序提取成 FailureSpec，再由 Plan Agent 基于这些事实重规划，最大次数受限。每个节点产生可回放 timeline，记录 handoff 引用和实际模型 token/cost。候选代码始终留在隔离 worktree，只有校验后的实验产物和报告由确定性 runtime 发布到主工程。离线测试证明编排与安全契约成立，真实 DeepSeek 的成功率和收益需要下一阶段固定协议评测。

## 13. v4.0.0-e：真实 3x3 API 验收学到了什么

### 13.1 “Planner 看见错误”不等于“Coding 能修错误”

第一版 batch graph 只把上一轮 facts 交给 Planner；CodingTask 仍只有总目标、候选 config 和 risk，所以 Planner 即使解释了 `ArchitectureNode(id=...)` 错误，CodingAgent 仍会重复。修复后 Supervisor 把 prior outcomes 压成 `{round, experiment_id, candidate, status, metrics, failure_facts}`，去掉源码、worktree 和原始 execution payload，再交给 CodingTask。面试时应强调：**reflection 的消费者不只 Planner，事实必须沿 handoff 到真正能采取行动的角色。**

### 13.2 开放 Coding 契约必须精确，不应靠模型猜内部 API

真实 DeepSeek 连续暴露了 `id/node_id`、非法 `training_mode`、不存在的 `train_data`、`success/completed`、artifact dict/tuple 和 metrics 元数据问题。处理原则分两类：

1. 研究语义必须严格：同一 MPDPD `x/d`、固定 split/seed、保留复数 I/Q、参数/epoch 预算、真实 PSD；
2. 等价表示可以规范化：成功状态同义词、命名 artifact mapping 的 values、非数值 metrics metadata、候选目录名漂移。

这比“提示词写详细一点”更重要：LLM 输出位于不可信边界，适配层要把常见表示差异变成 canonical contract，再由确定性 gate 检查真正影响正确性和安全性的条件。

### 13.3 三轮真实结果怎样解读

连续 run `deepseek-3x3-20260811-l` 完成 9 次搜索与一次终评，8/9 搜索成功。Round 1 最好只有 `-0.0474 dB`；Round 2 修复 LUT 但仍为 `0.6773 dB`；Round 3 的 `LUTSplineV3` 达到 `-23.0778 dB / 24 params`，独立终评复现同一数值。它证明 Agent 能从失败事实逐轮推进，但没有达到 `-41 dB`，也明显弱于项目历史先验。

面试时不要说“Agent 找到最优通信模型”，应说：

> 我用真实 DeepSeek 跑了 3 轮 9 候选，8 个完成。系统从第一轮实现失败和接近 0 dB 的弱模型出发，第三轮找到 24 参数、-23.08 dB 的 LUT-Spline，并在独立终评复现。目标 -41 dB 没命中，所以结论是 Harness 的闭环和故障恢复成立，但自主算法质量仍需知识检索、标准 evaluator 和更强 coding 模型提升。

### 13.4 WritingAgent 为什么需要“生成后自修复”

真实报告两次被 fidelity gate 拒绝：一次把错误行号写进 failure analysis，却没有把字符串中的数字纳入被引事实；一次在 limitations 中写 `-23.08`，却只引用 `task:limits`。最终实现保留 section-scoped citation，不放宽成“全报告数字都可用”；第一次失败后把具体 fidelity errors 回传 WritingAgent，允许一次修改文本或 evidence refs。第二次仍失败才终止。

### 13.5 当前还很 toy 的部分

- 候选自己上报 NMSE，Executor 只检查有限值和参数一致性；下一版应要求预测 artifact，由 Executor 在固定测试集上重算 NMSE。
- Coding 源码塞在单个 JSON 字符串中，长响应会截断；应改为结构化文件流、patch tool 或分文件 tool call。
- batch 内是先完成三个 Coding 再执行，长候选拖慢整轮；可改为候选级流水并发，同时保持 round barrier。
- Windows 外层取消没有杀完整进程树，曾留下孤儿 run；应使用 Job Object 或 control plane 记录并递归终止 owned process tree。
- 最终 PSD 来自候选插件，能证明 artifact 链路真实，但图的领域基线和统一绘图语义仍应由 Executor 负责。

### 13.6 本阶段可核验资产

- PDF：`docs/reports/v4.0.0-e-deepseek-3x3-report.pdf`
- 架构：`docs/assets/results/v4.0.0-e/architecture.png`
- 最终 PSD：`docs/assets/results/v4.0.0-e/final-psd.png`
- 九实验 NMSE：`docs/assets/results/v4.0.0-e/nine-experiment-nmse.png`
- 主搜索：21 次模型调用，37,914 prompt tokens，71,483 completion tokens，估算 `$0.08886808`

## 14. v4.1.0：从“页签表单”到 Agent Operations Console

### 14.1 为什么要拆掉单文件 Web UI

旧 `web_ui.py` 把 HTML、CSS、表单、SSE 解析和结果绘制混在一个大字符串中。它能运行，但事件语义、视觉布局和后端接口相互牵连，修改日志颜色也可能误伤表单。v4.1.0 将边界拆成 `index.html`、`styles.css`、`event_view_model.js` 和 `app.js`；Python 只从白名单读取这些资产，wheel 也显式打包 `web/*`，因此源码运行和安装运行保持一致。

### 14.2 Timeline、Console、Raw 与 Inspector 各自回答什么

- Timeline 回答“哪一个 Agent/Tool 按什么顺序做了什么”，适合讲 Agentic Loop 和角色 handoff。
- Console 回答“运行时具体输出了什么”，保留错误原因、reflection facts、新计划、metrics 和 artifacts。
- Raw Events 回答“后端实际上发了什么”，用于核对 UI 没有改写指标或隐去错误。
- Inspector 回答“当前事件来自哪里、输入输出引用什么、模型用量是多少”，原始 payload 默认折叠。

`normalizeEvent(raw)` 是四种视图的共同语义层。未知事件仍保留 raw；warning、failure、planner、reflection 和 benchmark 使用不同状态色。这样面试时可以从 Timeline 讲全链路，再下钻到 Inspector 证明 provenance，而不是滚动一整屏字符串。

### 14.3 为什么 Multi-Agent 结果需要后端裁剪

九次实验的真实指标原本存在 Supervisor state，旧 SSE 只发送角色和 artifact refs，前端无法诚实生成实验表。现在 execution 事件增加 `experiments`，final-evaluation 事件增加 `final_evaluation`，但服务端只公开 experiment ID、模型名、状态、有限数值 metrics、artifacts 和失败计数。候选源码、CodingAgent 内部结果、详细失败文本和 worker state 不进入浏览器。

运行控制采用单活动 run 互斥：任何工作流运行时，其他启动按钮一起禁用，防止覆盖当前 `AbortController/session_id`。Stop 只设置该 session 的协作式取消事件，不再扫描并误杀系统内所有 `train.py`；训练中的即时终止需要后续在 control plane 建立 `session_id -> owned process` 映射。

### 14.4 Knowledge 与 Memory 如何真正进入下一轮决策

v4.2.0 将原先只存在于 UI 的入口接到了 Multi-Agent 主链路：每轮由 goal、round 和最近的验证记录形成检索 query，`PlannerContextBuilder` 分别从白名单知识库和同 namespace 的有效 typed memory 取 top-k。Runtime 只把有限的 evidence 字段放进 Idea/Plan prompt，不传完整文档、raw history、源码或密钥。

两类上下文必须分清：Knowledge 是项目维护者审核过的领域先验，citation 形如 `knowledge:<chunk_id>`；Memory 是 Execution 产生的可验证经验，citation 形如 `memory:<memory_id>`。PlanGate 使用本轮 evidence ID 作为 allowlist，拒绝引用不存在材料的 hypothesis 或 candidate。这样 citation 既是给人看的出处，也是运行时安全边界。

Execution 完成或失败后会写一条 episodic memory，包含状态、候选名、有限数值指标、artifact refs、config hash、模型和角色 provenance。下一轮按 `(domain, dataset_hash, model_family)` namespace 检索，失效 memory 会被过滤，跨数据集经验不会串入。Web 的 `/memory` 与 Multi-Agent 使用同一个进程内 backend，Inspector 展示裁剪后的 evidence provenance；当前默认 backend 在服务重启后不持久化，生产环境应切换已有 Postgres adapter。

### 14.5 为什么 Reflection 与 Memory 不能混为一谈

Reflection 是当前 run 内的确定性事实提取：它把 metrics、失败类型和 artifacts 压缩进 planner history，不替 LLM 输出策略。Memory 是跨轮或跨 run 的可检索经验，必须有 namespace、置信度和 evidence refs。前者保证错误事实马上到达下一次决策，后者避免重复踩已经验证过的坑。两者同时存在，才不是“有 history 就等于有长期记忆”。

### 14.6 当前可用于面试的工程点

> 我把单文件演示页重构成无 Node 构建步骤的 Agent Operations Console，并把白名单 Knowledge 与 typed Memory 接入 Multi-Agent 每轮规划。检索只注入 top-k evidence，PlanGate 用 evidence allowlist 拒绝伪造 citation；Execution 将验证结果写回按 domain、dataset 和 model family 隔离的 episodic memory。SSE Inspector 展示 provenance 而不泄露完整 prompt，Web 开关和 CLI 参数可以做 context on/off 消融。当前诚实边界是默认 Memory 仍为进程内存储，算法增益还需固定预算评测。

### 14.7 为什么保留受控模型搜索

开放式 CodingAgent 能展示代码生成、隔离执行和失败修复，但它的算法质量受模型能力和领域先验影响。v4.2.0 因此保留另一条生产路径：受控搜索只在 `DomainPlugin.design_space()` 注册的成熟模型族内规划，并通过 `FilteredDomain` 同时限制允许的模型取值与可覆盖字段。

Web 中“允许模型”决定 Planner 可选的固定实现；“可调参数”决定本轮可写入 overrides 的字段。未勾选字段继承 baseline，越权修改由 Guard 拒绝。即使可调参数全部关闭，空列表也不会退化为“全部可调”。两条路径共享 ExperimentPlannerLoop、ToolRegistry、真实训练、Reflection、Trace 和报告，因此性能稳定性与 Agent 工程展示可以同时保留。

面试时可表述为：

> 我没有把所有任务都强制交给自由代码生成，而是设计了双轨实验系统。开放式 Multi-Agent 用于新架构探索；受控搜索在经过验证的模型族内优化，用户可以分别锁定模型集合和参数字段。Planner 只看到允许空间，Guard 再做一次确定性校验，两条链路最终进入同一训练和评测内核。

## 20. v4.4.0：Coding 契约修复与运行级统计

真实 Multi-Agent 历史运行中，CodingAgent 的失败发生在训练之前：LLM 返回的 `manifest.name`、候选目录或 `entrypoint` 形式与请求略有差异，严格 parser 在三次修复内重复拒绝。修复没有放开 AST、路径、参数预算和 smoke-training gate，而是把 Supervisor 拥有的 `task_id`、`candidate_name`、manifest name 与候选根目录做确定性 canonicalization，并兼容单一 JSON code fence；prompt 同时给出完整 manifest 示例。安全边界与格式容错被拆开处理。

受控搜索的空表来自前端数据契约错误：`plan_generated.experiments` 只是待执行计划，旧组件却把它当成结果行。现在只有 `experiment_end`、`experiment_rejected`、Multi-Agent execution 和 final-evaluation 能写入结果表。服务端还为 Coding role 投影 `candidate_count / passed_count / failed_count / repair_attempts`，不公开源码或详细 worker state。

受控搜索中的 `output_dir` 是运行时产物路径，不是模型超参数。`FilteredDomain` 现在把它作为经过底层路径规范化的 operational metadata 允许通过，但不把它放进 Planner 可调 design space。模型/超参数锁定能力不受影响。

### 20.1 真实 API 回归结果

`v440-coding-smoke-final` 关闭本地知识注入，仅向 DeepSeek 发送公开目标与任务契约。CodingAgent 第一次调用就生成可执行的 `mlp_tanh_2x8` 插件，固定 gate 复核为 `162` 参数；ExecutionAgent 通过注册工具独立运行，得到 `-20.1689 dB`，无失败事实、无修复尝试。Idea/Plan、Plan Gate、Coding、Execution、Writing、Terminal 六个 timeline 节点均为 `completed`。

WritingAgent 连续调用两次，是因为第一份草稿未满足证据忠实度约束，第二次用于基于具体错误修复。若第二次仍不合规，系统不放宽引用或数字规则，而是生成只包含 evidence registry 已知引用、且不引入未验证数字的确定性保底叙述，再用同一个 `NarrativeFidelityChecker` 复核。这样把“报告模型能力不足”降级为可观测质量事件，而不是让已经完成的实验整体失败。

完整回归为 `508/508` 通过。这里要分清两类证据：单次真实 API run 证明 Agent 间契约、代码执行和报告降级能闭环；固定任务集上的 pass@1/pass@3 与多 seed NMSE 才能证明模型质量，二者不能混写。

面试表达：

> 我把 Planner proposal 与 Execution observation 分成不同事件契约，UI 只从 observation 构建统计，避免把待执行计划误算成实验结果。CodingAgent 对服务端身份字段做 canonicalization，但危险能力、越界路径、参数预算和真实 smoke run 仍由确定性 gate 拦截。最终两条搜索链路都能给出运行级成功率、失败分类、目标命中和最优性能证据。

## 21. 面试复盘：为什么这样设计、遇到了什么、怎样解决

### 21.1 90 秒项目介绍

> 这个项目最初解决的是非线性拟合实验依赖人工改模型、调参、跑训练和整理结果的问题。我希望让 LLM 负责提出假设和探索方向，但很快发现“让模型输出一份配置”只是工作流，并不等于可靠的 Agent Harness：它可能生成非法参数、看见错误却无法修正、写出不能执行的代码，也可能在报告里编造数字。因此我把系统逐步拆成 Idea/Plan、Coding、Execution、Writing 四个角色，由 Supervisor 管理结构化状态、预算、失败回路和唯一终态；把训练、参数校验、artifact 检查和报告 fidelity 留给确定性运行时。开放式 Multi-Agent 用来探索新模型，受控搜索用白名单模型和字段锁定提供稳定路径。最后我又把 Agent 行为、搜索质量和运行时可靠性拆成三套评测，避免用单个 NMSE 代表整个系统。固定协议下，10-case 目标命中率从 50% 提升到 90%，Planner 合法率从 15% 提升到 92.6%；18 项真实 DeepSeek 行为评测 pass@1 达到 94.4%、pass@3 达到 100%；508 项回归测试通过。

### 21.2 最初的出发点

第一层需求是**减少实验机械劳动**：用户只描述目标、参数预算和时间预算，系统自动设计实验、执行训练、比较 NMSE/PSD 并汇总结果。

第二层需求是**让迭代有因果依据**：下一轮不能只看到一大段日志，而要消费“哪个候选失败、在哪个 gate 失败、得到了什么指标、哪些 artifact 可验证”等事实。

第三层需求是**把 Demo 变成可解释的 Agent 工程**：系统必须回答谁做了决定、调用了哪个工具、为什么重试、证据来自哪里、花了多少 token、最终为什么停止，而不仅是最后跑出一张图。

核心设计原则因此是：**LLM 负责开放推理，确定性程序负责权限、执行、验证和记账。** 不是因为 LLM 不聪明，而是因为安全边界、状态一致性和指标真实性必须可复现。

### 21.3 演进过程中的关键困难与解决方法

| 困难 | 为什么是问题 | 解决方法 | 我学到的工程原则 |
| --- | --- | --- | --- |
| 早期系统只是 Planner 输出固定配置 | 没有基于 observation 的循环，也不能探索仓库外的新模型 | 建立 `Plan -> Tool -> Observation -> Reflection Facts -> Replan`，再引入可生成完整插件包的 CodingAgent | Agentic 不取决于角色数量，而取决于是否能根据环境反馈改变下一步动作 |
| Reflection 产物没有真正影响下一次决策 | “生成了反思文本”不等于消费者拿到了可执行信息；Planner 看见错误，Coding 仍会重复犯错 | Reflection 只提取验证事实，不输出硬编码策略；Supervisor 将压缩后的失败事实同时传给 Planner 和真正能修代码的 CodingAgent | 先确定信息的消费者，再设计 memory/reflection；不要为了有 Reflection 而 Reflection |
| CodingAgent 只输出 `ModelClass`，ExecutionAgent 无法运行 | 缺少数据入口、训练函数、参数统计、产物协议和配置 schema | 定义 `ModelPlugin + manifest + descriptor` 完整候选包；固定 runner 负责加载、训练和输出 metrics/PSD | 跨 Agent 交接必须是可验证协议，不能依赖隐含约定 |
| 放开代码生成后存在执行风险 | LLM 代码可能路径逃逸、导入危险模块、读取密钥或启动任意命令 | 候选在隔离 worktree 中生成；依次执行 JSON、路径、AST capability、参数预算、descriptor hash 和 smoke-training gate；ExecutionAgent 只能调用注册工具 | LLM 可以提议能力，但能力授予必须由 runtime 决定 |
| 真实 DeepSeek 多次因格式细节在训练前失败 | `manifest.name`、候选目录、entrypoint 等由 Supervisor 已知，却要求模型逐字复制，浪费修复轮次 | 对 Supervisor 拥有的身份元数据做确定性 canonicalization，同时保留路径、AST、预算和 smoke gate | 严格应该用于安全语义，不应用于机器可确定修复的表面格式 |
| 报告看起来完整但可能“漂亮地胡说” | 数字、模型结构和失败原因若没有来源，报告越专业风险越高 | 建立 EvidenceBundle、section-scoped evidence refs 和 numeric fidelity checker；一次 LLM 定向修复后仍失败则生成保守的确定性叙述，并再次走同一 checker | 生成质量与事实忠实度是两件事；失败降级不能绕过原验证器 |
| MultiAgent 自由生成模型的实际性能不稳定 | 开放探索能展示能力，但弱模型可能远差于已有通信先验 | 保留双轨入口：开放 Multi-Agent 探索新结构；受控搜索选择成熟模型白名单，并分别锁定允许模型与可调字段 | 生产系统不应把所有请求都押在开放生成上，要允许探索与稳定路径共存 |
| Web 里计划行被画成空实验结果 | 前端把 `plan_generated.experiments` 当 observation，出现空白 NMSE/参数列，统计失真 | 明确 proposal 与 observation 事件契约；只有 execution/final-evaluation 事件进入结果表，并增加运行级聚合统计 | 可观测性不是多打印日志，而是每类事件语义稳定、来源明确 |
| 早期 benchmark 把不同能力混成一个结论 | 算法 NMSE、Planner 决策和控制面可靠性互相受随机性干扰，无法归因 | 拆成 Agent behavior、Search comparison、Runtime stress 三层；同模型、同 seed、同 trial budget 做消融并保留原始结果和修正 provenance | 评测先回答“想证明什么”，再选择指标；不能用一个总分替代因果分析 |

### 21.4 最值得讲的三次真实故障

**故障一：Planner 明明看见错误，Coding 下一轮仍重复。**

排查后发现 history 只进入 Planner prompt，没有沿结构化 handoff 进入 CodingTask。修复不是增加一段更长的全局 prompt，而是把 prior outcomes 压缩为 round、candidate、status、metrics 和 failure facts，再发送给能够采取行动的角色。这个案例可以用于回答“你怎样设计跨 Agent 上下文”和“怎样控制 token”。

**故障二：CodingAgent 连续失败，但训练根本没有开始。**

根因并非模型不会写网络，而是候选名、manifest 名和目录等重复元数据存在轻微不一致。系统原先把格式一致性与安全性混在同一个严格 parser 中。修复后由 Supervisor canonicalize 自己拥有的字段，危险导入、越界路径、参数超限和 smoke 失败仍严格拒绝。真实最小回归中，DeepSeek 第一次 Coding 就通过，生成 162 参数插件并由 ExecutionAgent 完成运行。

**故障三：WritingAgent 导致已完成实验整体失败。**

真实报告中模型会引用不存在的 evidence ID，或在某一节写入没有被该节证据支持的数字。第一步把 fidelity errors 反馈给 WritingAgent 修复；第二次仍失败时，不降低 checker 标准，而由程序生成不引入未知数字的保底叙述，再交给同一 checker。结果是报告质量问题被降级和记录，训练成果不会丢失，最终 terminal 仍然唯一且可解释。

### 21.5 可以量化的结果，以及它们分别证明什么

| 证据 | 结果 | 只证明什么 |
| --- | --- | --- |
| 10-case 前后版本对照 | target hit `50% -> 90%`；Planner 合法率 `15% -> 92.6%`；最佳 NMSE `-37.42 -> -42.43 dB` | 固定项目协议下，Domain 上下文、输出契约和 timeout 传递修复有效 |
| 18 项 Agent 行为集 | DeepSeek pass@1 `77.8% -> 94.4%`，pass@3 `100%` | 同 ToolSpec 和评分器下，停止、去重、坏 JSON 事实化和初始证据注入有效 |
| 3 seeds 固定预算搜索消融 | Direct target hit `33.3%`；History `43.3%`；完整 Priors `53.3%` | 知识与历史提高命中频率；尚不能证明最终 best 有显著增益 |
| 运行时压力测试 | 并发 8、300 请求、15% 故障注入；重复执行和事件丢失均为 0，唯一终态一致率和注入故障恢复率均为 100% | 本地单进程 SQLite 控制面的可靠性基线，不是分布式 SLA |
| 真实 3x3 DeepSeek run | 搜索候选 `8/9` 完成，最佳 `-23.0778 dB / 24 params` 并独立复现 | MultiAgent 能跨轮生成、失败恢复和终评；没有证明算法达到 `-41 dB` |
| 工程回归 | `508/508` tests passed | 当前代码契约未发生已覆盖范围内的回归，不代表真实 LLM 永不失败 |

### 21.6 STAR 讲法

**S（背景）**：非线性拟合实验需要反复改结构、调参、跑训练和整理 PSD/NMSE；单纯让 LLM 生成配置无法保证代码可执行、迭代有依据和报告可信。

**T（任务）**：设计一个能够自主提出实验、生成新模型、受控执行、根据失败修正并交付可核验报告的 Agent Harness，同时限制参数量、epoch、时间和代码能力。

**A（行动）**：我用结构化 handoff 和 Supervisor 串联四个 Agent；将执行收敛到 ToolRegistry；为生成代码增加隔离 worktree、AST/路径/预算/smoke gate；把 Reflection 改为事实提取并定向传给决策消费者；为报告建立 evidence registry 与 fidelity checker；最后拆分三层 benchmark，并用真实 DeepSeek、固定预算消融和故障注入验证。

**R（结果）**：固定 10-case 协议下目标命中率提高 40 个百分点，Planner 合法率提高 77.6 个百分点；真实行为评测 pass@1 达到 94.4%、pass@3 达到 100%；本地压力测试保持零重复执行和零事件丢失；完整回归 508 项通过。对于没有达到的 `-41 dB`，我保留了失败证据并引入受控模型搜索，而没有把 Harness 成功偷换成算法 SOTA。

### 21.7 面试官可能追问什么

**为什么不用一个 Agent 加很多工具？** 角色拆分不是为了显得复杂，而是为了建立最小权限和清晰交接。Coding 可以写候选包但不能任意执行；Execution 只能调用注册工具；Writing 只读证据。简单任务仍可走 Fixed Workflow 或受控搜索，不强制 MultiAgent。

**Reflection 为什么不用纯 LLM？** LLM 适合从干净 observation 中归纳失败事实，但事实 schema、数值提取、权限判断和状态写入应由程序校验。当前设计是 LLM 推理加确定性约束，而不是几个 `if` 替代推理，也不是把原始日志全部塞回 prompt。

**Memory 与 Reflection 有什么区别？** Reflection 是本轮 observation 到事实的转换；Memory 是跨轮或跨 run 的持久化与检索。Memory 按 domain、dataset hash、model family 隔离，并带 provenance/confidence；无效或过期记忆不能进入 Planner context。

**为什么需要受控搜索？** 自由 CodingAgent 的价值是探索未知结构，但真实 3x3 结果显示算法质量不稳定。受控搜索复用同一 Planner Loop、训练、Reflection 和报告链路，只把设计空间限制在成熟模型与用户开放字段内，适合要求稳定结果的场景。

**这个项目还有什么不足？** 当前隔离主要是子进程和 worktree，不是容器或微虚拟机；SQLite 压测只代表单机控制面；知识增益对最终 best 尚无显著证据；开放 Coding 还需要更大的固定任务集统计 pass@1/pass@3；当前只有一个 nonlinear-modeling domain。主动说明这些边界，比声称“已经量产级”更可信。

### 21.8 一句话收尾

> 这个项目真正的贡献不是让 LLM 多跑了几次神经网络，而是把不稳定的模型推理放进了一个有协议、有权限、有反馈、有证据、可降级、可评测的实验运行时里，并且用真实失败推动每一层设计。

## 22. v4.4.1：为什么 Web Multi-Agent 一直没有结果

真实 UI run `ui-multi-1786683942603` 生成了六份 Coding trace，但每个候选的三次响应都是空内容哈希，插件和训练都没有开始。原因是 DeepSeek V4 默认启用 thinking，而 Coding 的结构化调用只读取最终 `content`；在输出预算主要消耗于 reasoning 时，最终 JSON 可能为空。修复后，`deepseek-v4-flash` 和 `deepseek-v4-pro` 的 JSON Agent 请求显式发送 `thinking.type=disabled`，SDK 与手写兼容客户端保持同一行为。

第二个问题由真实 `1 x 1` SSE 复现：请求明确要求每轮一个实验，但 `_idea_plan()` 的文字和 JSON 示例始终写死三个候选，模型正确遵循了错误的 prompt，随后又被 PlanGate 以候选数不等于一拒绝。修复不是放宽 gate，而是根据 `experiments_per_round` 动态生成候选 contract 和 DAG。Web 同时开放轮次、每轮实验数和独立终评开关，默认 `1 x 1`，需要批量探索时再改为 `3 x 3`。

修复后通过同一个 Web `/multi-agent/{run_id}/events` 接口真实调用 `deepseek-v4-flash`：七个阶段全部 `completed`，Coding `1/1` 通过，候选 `mlp_tanh_16_8` 在第二次尝试通过 gate，搜索与独立终评均得到 `-21.0804 dB / 266 params`，HTML/PDF 报告可访问。完整回归为 `511/511`。

面试时可以这样总结：

> 这次故障不是训练算法问题，而是控制面同时存在模型推理模式和实验预算契约不一致。我先从六份空响应 trace 定位到 V4 thinking，再通过真实 1 x 1 SSE 找到 prompt 写死三候选。最终保持 PlanGate 严格，只在请求源头关闭结构化任务的 thinking 并动态生成 contract；修复后用默认 V4 完成 Coding、训练、独立终评和报告全链路。
