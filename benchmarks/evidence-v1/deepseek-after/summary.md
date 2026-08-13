# Agent Task Benchmark

- Domain: `nonlinear-modeling`
- Evaluation mode: `real_llm_fault_fixture`
- Tasks: 18
- Attempts: 54
- pass@1: 0.889

| Case | Attempt | Passed | Passed checks | Failed checks |
| --- | ---: | --- | --- | --- |
| `complete-experiment` | 1 | False | terminal_status, action_budget, forbidden_tools, required_metric, required_artifact | required_tools, tool_order |
| `complete-experiment` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, tool_order, required_metric, required_artifact | - |
| `complete-experiment` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, tool_order, required_metric, required_artifact | - |
| `generate-config-only` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `generate-config-only` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `generate-config-only` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `unknown-tool-rejection` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `unknown-tool-rejection` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `unknown-tool-rejection` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `missing-required-argument` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `missing-required-argument` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `missing-required-argument` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `unexpected-argument` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `unexpected-argument` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `unexpected-argument` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `wrong-argument-type` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `wrong-argument-type` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `wrong-argument-type` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `training-failure-recovery` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `training-failure-recovery` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `training-failure-recovery` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `threshold-failure-switch-candidate` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `threshold-failure-switch-candidate` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `threshold-failure-switch-candidate` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `timeout-reduce-training-budget` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `timeout-reduce-training-budget` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `timeout-reduce-training-budget` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `missing-artifact-reverify` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery, required_metric | - |
| `missing-artifact-reverify` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery, required_metric | - |
| `missing-artifact-reverify` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery, required_metric | - |
| `verify-before-report` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, tool_order, required_artifact | - |
| `verify-before-report` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, tool_order, required_artifact | - |
| `verify-before-report` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, tool_order, required_artifact | - |
| `stop-after-target-hit` | 1 | False | terminal_status, action_budget, forbidden_tools | required_tools, required_metric |
| `stop-after-target-hit` | 2 | False | terminal_status, action_budget | required_tools, forbidden_tools, required_metric |
| `stop-after-target-hit` | 3 | False | terminal_status, action_budget, forbidden_tools | required_tools, required_metric |
| `hard-action-budget-stop` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `hard-action-budget-stop` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `hard-action-budget-stop` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `avoid-duplicate-candidate` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `avoid-duplicate-candidate` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `avoid-duplicate-candidate` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `reuse-history-best` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, required_metric | - |
| `reuse-history-best` | 2 | False | terminal_status, action_budget, required_tools, forbidden_tools | required_metric |
| `reuse-history-best` | 3 | False | terminal_status, action_budget, required_tools, forbidden_tools | required_metric |
| `consume-reflection-facts` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `consume-reflection-facts` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `consume-reflection-facts` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `resolve-conflicting-history` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `resolve-conflicting-history` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `resolve-conflicting-history` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `compressed-context-constraint` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `compressed-context-constraint` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `compressed-context-constraint` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |

Scripted fixture results prove harness contract regression only. They do not measure autonomous LLM reasoning quality.
