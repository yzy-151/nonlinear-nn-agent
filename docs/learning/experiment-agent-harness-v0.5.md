# Experiment Agent Harness v0.5 学习文档

更新时间：2026-07-22

## 本版主题

v0.5 解决 LLM Planner 的第一个生产级问题：模型会输出“看起来合理但系统不能执行”的字段。

新增核心文件：

- `src/nonlinear_agent/planner_validation.py`
- `tests/test_planner_validation.py`

## 新增能力

- `train_samples` 自动映射为真实配置字段 `max_train_samples`。
- 拒绝 `rank`、`parameter_count`、`nmse_db`、`status` 等结果字段或未支持控制字段。
- 在运行前估算 `complex_lstsq`、`linear`、`tiny_mlp`、`spline_mlp` 的参数量。
- 超过 `parameter_count_max` 的候选不进入 runtime。
- rejected 候选写入 loop history，形成下一轮 planner 可读取的错误反馈。

## 你应该学会什么

Agent Harness 不能相信 LLM 输出。Prompt 是软约束，schema guard 是硬边界。

面试表达：

```text
我在 LLM planner 与 runtime 之间加入 schema guard 和参数预算预检查，LLM 只能提出配置候选，不能绕过工具 schema、参数预算和执行边界；非法候选不会触发训练，而是作为 rejected record 写入 history，供下一轮 planner 修正。
```

