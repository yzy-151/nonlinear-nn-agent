# Agent Runtime Diagnostics Dashboard

## Overview

- benchmark_runs: `4`
- planner_loop_runs: `51`

## Aggregate Metrics

| metric | value |
|---|---:|
| case_count | `412` |
| target_hit_rate | `0.5024271844660194` |
| rejected_rate | `0.2645631067961165` |
| runtime_failure_rate | `0.23300970873786409` |
| average_experiments_used | `8.07843137254902` |
| best_nmse_db | `-40.86985111609215` |

## Best Candidate

| field | value |
|---|---|
| id | `exp-029` |
| nmse_db | `-40.86985111609215` |
| parameter_count | `21122` |
| source | `runs/20260725-143359-planner-loop/result.json` |

## Run Status Distribution

| status | count |
|---|---:|
| failed | 96 |
| rejected | 109 |
| succeeded | 207 |

## Error Type Distribution

| error_type | count |
|---|---:|
| metric_threshold_error | 75 |
| tool_error | 19 |

## Benchmark Runs

| source | cases | target_hit_rate | best_nmse_db |
|---|---:|---:|---:|
| `benchmarks/fake-v08-check/results.json` | 3 | 0.3333333333333333 | -36.0 |
| `benchmarks/web-20260724-221339/results.json` | 3 | 0.6666666666666666 | -37.42494350080102 |
| `benchmarks/web-20260724-221743/results.json` | 3 | 0.6666666666666666 | -37.42494350080102 |
| `benchmarks/web-20260725-161002/results.json` | 3 | 0.6666666666666666 | -37.42494350080102 |

## Planner Loop Runs

| source | status | rounds | history_count |
|---|---|---:|---:|
| `runs/20260725-172317-planner-loop/result.json` | `planner_error` | 8 | 18 |
| `runs/20260725-143359-planner-loop/result.json` | `planner_error` | 16 | 42 |
| `runs/20260725-161140-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260725-161053-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260725-161002-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-221942-planner-loop/result.json` | `planner_error` | 29 | 73 |
| `runs/20260724-221845-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-221814-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-221743-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-221449-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-221419-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-221348-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-200716-planner-loop/result.json` | `max_rounds_reached` | 30 | 64 |
| `runs/20260724-165007-planner-loop/result.json` | `max_experiments_reached` | 10 | 30 |
| `runs/20260724-163209-planner-loop/result.json` | `max_rounds_reached` | 10 | 30 |
| `runs/20260724-161639-planner-loop/result.json` | `max_rounds_reached` | 10 | 25 |
| `runs/20260724-160347-planner-loop/result.json` | `max_rounds_reached` | 10 | 28 |
| `runs/20260724-155349-planner-loop/result.json` | `max_experiments_reached` | 5 | 14 |
| `runs/20260724-153438-planner-loop/result.json` | `max_rounds_reached` | 5 | 13 |
| `runs/20260724-152617-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-152226-planner-loop/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/20260724-151001-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-150545-planner-loop/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/20260724-145729-planner-loop/result.json` | `stopped` | 4 | 8 |
| `runs/20260724-144800-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-144541-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-143350-planner-loop/result.json` | `max_rounds_reached` | 10 | 26 |
| `runs/20260724-143127-planner-loop/result.json` | `planner_error` | 1 | 0 |
| `runs/20260724-141620-planner-loop/result.json` | `max_experiments_reached` | 2 | 5 |
| `runs/20260724-141323-planner-loop/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/20260724-140556-planner-loop/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/20260724-130805-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-130607-planner-loop/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/20260724-125958-planner-loop/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/20260724-123004-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-122816-planner-loop/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/20260724-122211-planner-loop/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/20260724-121347-planner-loop/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/20260724-120937-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260724-120809-planner-loop/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/test/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v15-cli-check/result.json` | `max_rounds_reached` | 0 | 0 |
| `runs/fake-v13-check-2/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v13-check/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v11-check/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v09-check/result.json` | `stopped` | 2 | 1 |
| `runs/benchmark-runtime-failure/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/benchmark-invalid-plan/result.json` | `max_rounds_reached` | 1 | 1 |
| `runs/benchmark-target-hit/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v07-check/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v06-check/result.json` | `stopped` | 2 | 1 |

## 面试解释

这个 dashboard 的重点不是炫图，而是证明 Agent Harness 的改动可以被评估：target hit rate 说明目标命中能力，rejected/runtime failure rate 说明 guardrail 和 runtime 稳定性，error_type 分布说明失败是否被结构化诊断，best_nmse_db 和参数量说明算法实验结果。
