# Experiment Agent Harness v0.6 学习文档

更新时间：2026-07-22

## 本版主题

v0.6 把 planner loop 从“终端输出一次结果”升级为“自动保存可复盘 run artifacts”。

新增核心文件：

- `src/nonlinear_agent/run_artifacts.py`
- `tests/test_llm_planner.py` 中的 artifact 测试

## 新增能力

每次 loop 自动生成：

```text
runs/<timestamp-or-user-dir>/
  plans/
    round-001.json
    round-002.json
  result.json
  leaderboard.csv
  summary.md
```

CLI 新增：

- `--artifact-dir`

## 你应该学会什么

Agent 工程不能只看最终答案，要保留计划、执行、观察、停止原因。否则无法解释为什么失败，也无法比较 planner prompt 或 schema guard 是否让 Agent 变强。

面试表达：

```text
我为 LLM-driven experiment harness 增加 run artifact 自动落盘能力，结构化保存每轮 planner JSON、最终 result、leaderboard.csv 与 summary.md，使实验循环具备可复现、可审计和结果展示闭环。
```

