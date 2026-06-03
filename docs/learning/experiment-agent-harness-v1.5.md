# Experiment Agent Harness v1.5 总学习文档

更新时间：2026-07-23

这是当前最新主学习文档。你优先读这一份；旧版 `v0.1-v1.4` 保留为版本历史。

## 1. 本版主题

v1.5 补上交付面：Unified CLI / Local Dashboard Client。

之前项目已经有 runtime、planner、benchmark、diagnostics，但使用入口分散在多个 `examples/nonlinear_fit/*.py` 文件中。v1.5 把核心操作统一到一个命令入口，降低展示和复现门槛。

新增能力：

- `python -m nonlinear_agent.cli run`
- `python -m nonlinear_agent.cli benchmark`
- `python -m nonlinear_agent.cli diagnostics`
- `python -m nonlinear_agent.cli dashboard`
- `python -m nonlinear_agent.cli serve`
- 安装后可用 `nonlinear-agent`
- 生成 standalone HTML dashboard

## 2. 新增文件

- `src/nonlinear_agent/cli.py`
- `src/nonlinear_agent/dashboard.py`
- `tests/test_cli.py`
- `tests/test_dashboard.py`
- `pyproject.toml`
- `agent.py`
- `docs/diagnostics/agent-runtime-dashboard.html`

更新：

- `src/nonlinear_agent/__init__.py`
- `README.md`
- `docs/handoff/deepseek-continuation-plan.md`
- `docs/resume/experiment-agent-harness-resume.md`
- `docs/superpowers/plans/experiment-agent-harness-plan.md`

## 3. CLI 命令面

```powershell
python agent.py dashboard
python agent.py diagnostics
python -m nonlinear_agent.cli run --provider fake --max-rounds 2 --max-experiments 1
python -m nonlinear_agent.cli benchmark --output-dir benchmarks/fake-v15
python -m nonlinear_agent.cli diagnostics
python -m nonlinear_agent.cli dashboard
python -m nonlinear_agent.cli serve --host 127.0.0.1 --port 8000
```

安装为 editable package 后：

```powershell
pip install -e .
nonlinear-agent dashboard
```

## 4. 为什么不先做 exe

exe 对非技术用户更友好，但对 Agent Harness 岗位不是第一优先级：

- PyTorch 依赖会让 exe 体积很大。
- Windows 打包容易遇到 DLL、杀毒误报、路径问题。
- 面试更看重 command surface、runtime observability、可复现 workflow。

所以 v1.5 先做统一 CLI 和 HTML dashboard。这个选择更轻、更稳，也更适合 GitHub 展示。

## 5. HTML Dashboard

`src/nonlinear_agent/dashboard.py` 提供：

- `render_dashboard_html(diagnostics)`
- `write_dashboard_html(workspace, output_path=None)`

默认输出：

```text
docs/diagnostics/agent-runtime-dashboard.html
```

Dashboard 展示：

- aggregate metrics
- best candidate
- run status distribution
- error type distribution
- benchmark runs
- planner loop runs

## 6. 面试表达

```text
为 Agent Harness 增加统一命令行交付面和本地 HTML diagnostics dashboard，将 planner loop、benchmark、diagnostics、SSE server 等分散入口收敛为一个 CLI，并支持一键生成可分享的 runtime dashboard，降低复现实验和展示系统可观测性的成本。
```

## 7. 验证

```powershell
python -m unittest tests.test_cli tests.test_dashboard
python -m unittest discover tests
python -m nonlinear_agent.cli diagnostics
python -m nonlinear_agent.cli dashboard
```

## 8. 下一步

v1.6：Real DeepSeek Demo Replay / Case Study。

目标：

- 选择一轮真实 DeepSeek planner run。
- 提取 planner plan、history、reflection、leaderboard、PSD。
- 写成可直接面试讲述的 case study。
