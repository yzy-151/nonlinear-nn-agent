# Agent Runtime Diagnostics Dashboard

## Overview

- benchmark_runs: `19`
- planner_loop_runs: `99`

## Aggregate Metrics

| metric | value |
|---|---:|
| case_count | `871` |
| target_hit_rate | `0.33639494833524686` |
| rejected_rate | `0.1928817451205511` |
| runtime_failure_rate | `0.4707233065442021` |
| average_experiments_used | `8.797979797979798` |
| best_nmse_db | `-42.42519559502256` |

## Best Candidate

| field | value |
|---|---|
| id | `exp_002` |
| nmse_db | `-42.42519559502256` |
| parameter_count | `19490` |
| source | `runs/benchmark-target-hit/result.json` |

## Run Status Distribution

| status | count |
|---|---:|
| failed | 410 |
| reflection | 97 |
| rejected | 168 |
| succeeded | 293 |

## Error Type Distribution

| error_type | count |
|---|---:|
| metric_threshold_error | 338 |
| timeout_error | 2 |
| tool_error | 69 |

## Benchmark Runs

| source | cases | target_hit_rate | best_nmse_db |
|---|---:|---:|---:|
| `benchmarks/deepseek-v21/results.json` | 10 | 0.4 | -37.42494350080102 |
| `benchmarks/deepseek-v21-final/results.json` | 10 | 0.5 | -37.42494350080102 |
| `benchmarks/deepseek-v21-final2/results.json` | 10 | 0.0 | -19.694849292675865 |
| `benchmarks/deepseek-v21b/results.json` | 10 | 0.5 | -37.42494350080102 |
| `benchmarks/deepseek-v21c/results.json` | 10 | 0.5 | -37.42494350080102 |
| `benchmarks/deepseek-v22/results.json` | 10 | 0.4 | -37.42494350080102 |
| `benchmarks/deepseek-v23/results.json` | 10 | 0.4 | -37.42494350080102 |
| `benchmarks/deepseek-v24/results.json` | 10 | 0.3 | -37.42494350080102 |
| `benchmarks/deepseek-v25/results.json` | 10 | 0.1 | -37.57686595165717 |
| `benchmarks/deepseek-v26/results.json` | 10 | 0.9 | -42.42519559502256 |
| `benchmarks/fake-v08-check/results.json` | 3 | 0.3333333333333333 | -36.0 |
| `benchmarks/fake-v16-audit/results.json` | 5 | 0.6 | -36.5 |
| `benchmarks/fake-v16-doc-ui-check/results.json` | 5 | 0.6 | -36.5 |
| `benchmarks/fake-v21/results.json` | 5 | 0.6 | -36.5 |
| `benchmarks/fake-v21b/results.json` | 10 | 0.7 | -36.5 |
| `benchmarks/web-20260724-221339/results.json` | 3 | 0.6666666666666666 | -37.42494350080102 |
| `benchmarks/web-20260724-221743/results.json` | 3 | 0.6666666666666666 | -37.42494350080102 |
| `benchmarks/web-20260725-161002/results.json` | 3 | 0.6666666666666666 | -37.42494350080102 |
| `benchmarks/web-20260725-191422/results.json` | 3 | 0.6666666666666666 | -37.42494350080102 |

## Planner Loop Runs

| source | status | rounds | history_count |
|---|---|---:|---:|
| `runs/20260806-105749-planner-loop/result.json` | `max_rounds_reached` | 2 | 10 |
| `runs/benchmark-parameter-budget-edge/result.json` | `max_experiments_reached` | 1 | 3 |
| `runs/benchmark-multi-round-self-correction/result.json` | `max_experiments_reached` | 1 | 5 |
| `runs/benchmark-long-history-compression/result.json` | `max_experiments_reached` | 3 | 11 |
| `runs/benchmark-unknown-tool/result.json` | `max_experiments_reached` | 1 | 1 |
| `runs/benchmark-json-tolerance/result.json` | `max_experiments_reached` | 1 | 2 |
| `runs/benchmark-budget-stop/result.json` | `max_experiments_reached` | 1 | 1 |
| `runs/benchmark-reflection-recovery/result.json` | `max_experiments_reached` | 1 | 2 |
| `runs/benchmark-runtime-failure/result.json` | `max_experiments_reached` | 1 | 1 |
| `runs/benchmark-invalid-plan/result.json` | `max_experiments_reached` | 1 | 1 |
| `runs/benchmark-target-hit/result.json` | `max_experiments_reached` | 1 | 2 |
| `runs/20260804-121607-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121558-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121549-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121540-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121532-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121523-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121514-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121504-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121455-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121446-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121436-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121427-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121418-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121409-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121400-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121351-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121342-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121332-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260804-121324-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260803-103958-planner-loop/result.json` | `max_experiments_reached` | 7 | 33 |
| `runs/20260803-093815-planner-loop/result.json` | `max_experiments_reached` | 1 | 3 |
| `runs/20260803-093327-planner-loop/result.json` | `stopped` | 2 | 2 |
| `runs/20260802-235440-planner-loop/result.json` | `stopped` | 6 | 35 |
| `runs/20260802-234846-planner-loop/result.json` | `max_experiments_reached` | 1 | 13 |
| `runs/20260802-192253-planner-loop/result.json` | `max_rounds_reached` | 1 | 2 |
| `runs/20260727-141737-planner-loop/result.json` | `max_experiments_reached` | 9 | 48 |
| `runs/20260727-121849-planner-loop/result.json` | `max_experiments_reached` | 11 | 50 |
| `runs/20260727-112047-planner-loop/result.json` | `max_experiments_reached` | 9 | 48 |
| `runs/20260727-002147-planner-loop/result.json` | `planner_error` | 5 | 22 |
| `runs/20260726-222348-planner-loop/result.json` | `stopped` | 9 | 39 |
| `runs/20260726-213818-planner-loop/result.json` | `max_experiments_reached` | 11 | 46 |
| `runs/20260726-200532-planner-loop/result.json` | `max_experiments_reached` | 2 | 6 |
| `runs/20260726-170203-planner-loop/result.json` | `max_experiments_reached` | 1 | 3 |
| `runs/20260726-140357-planner-loop/result.json` | `planner_error` | 13 | 53 |
| `runs/20260725-212356-planner-loop/result.json` | `planner_error` | 9 | 34 |
| `runs/20260725-202655-planner-loop/result.json` | `planner_error` | 9 | 41 |
| `runs/20260725-195714-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260725-191536-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260725-191503-planner-loop/result.json` | `stopped` | 2 | 1 |
| `runs/20260725-191433-planner-loop/result.json` | `stopped` | 2 | 1 |
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
| `runs/fake-v07-check/result.json` | `stopped` | 2 | 1 |
| `runs/fake-v06-check/result.json` | `stopped` | 2 | 1 |

## 面试解释

这个 dashboard 的重点不是炫图，而是证明 Agent Harness 的改动可以被评估：target hit rate 说明目标命中能力，rejected/runtime failure rate 说明 guardrail 和 runtime 稳定性，error_type 分布说明失败是否被结构化诊断，best_nmse_db 和参数量说明算法实验结果。
