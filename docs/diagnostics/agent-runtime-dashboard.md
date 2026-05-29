# Agent Runtime Diagnostics Dashboard

## Overview

- benchmark_runs: `1`
- planner_loop_runs: `9`

## Aggregate Metrics

| metric | value |
|---|---:|
| case_count | `3` |
| target_hit_rate | `0.3333333333333333` |
| rejected_rate | `0.3333333333333333` |
| runtime_failure_rate | `0.3333333333333333` |
| average_experiments_used | `0.6666666666666666` |
| best_nmse_db | `-36.0` |

## Best Candidate

| field | value |
|---|---|
| id | `planner-demo-001` |
| nmse_db | `-37.42494350080102` |
| parameter_count | `3626` |
| source | `runs/fake-v06-check/result.json` |

## Run Status Distribution

| status | count |
|---|---:|
| failed | 3 |
| rejected | 1 |
| succeeded | 5 |

## Error Type Distribution

| error_type | count |
|---|---:|
| tool_error | 1 |

## Benchmark Runs

| source | cases | target_hit_rate | best_nmse_db |
|---|---:|---:|---:|
| `benchmarks/fake-v08-check/results.json` | 3 | 0.3333333333333333 | -36.0 |

## Planner Loop Runs

| source | status | rounds | history_count |
|---|---|---:|---:|
| `runs/benchmark-invalid-plan/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/benchmark-runtime-failure/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/benchmark-target-hit/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v06-check/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v07-check/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v09-check/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v11-check/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v13-check/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v13-check-2/result.json` | `stopped` | 2 | 1 |

## 面试解释

这个 dashboard 的重点不是炫图，而是证明 Agent Harness 的改动可以被评估：target hit rate 说明目标命中能力，rejected/runtime failure rate 说明 guardrail 和 runtime 稳定性，error_type 分布说明失败是否被结构化诊断，best_nmse_db 和参数量说明算法实验结果。
