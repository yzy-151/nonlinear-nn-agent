# Agent Task Benchmark

- Domain: `nonlinear-modeling`
- Evaluation mode: `scripted_fixture`
- Tasks: 18
- Attempts: 18
- pass@1: 1.000

| Case | Attempt | Passed | Passed checks | Failed checks |
| --- | ---: | --- | --- | --- |
| `complete-experiment` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, tool_order, required_metric, required_artifact | - |
| `generate-config-only` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `unknown-tool-rejection` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `missing-required-argument` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `unexpected-argument` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `wrong-argument-type` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, guard_rejection | - |
| `training-failure-recovery` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `threshold-failure-switch-candidate` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `timeout-reduce-training-budget` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `missing-artifact-reverify` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery, required_metric | - |
| `verify-before-report` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, tool_order, required_artifact | - |
| `stop-after-target-hit` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, required_metric | - |
| `hard-action-budget-stop` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `avoid-duplicate-candidate` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `reuse-history-best` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, required_metric | - |
| `consume-reflection-facts` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, causal_recovery | - |
| `resolve-conflicting-history` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |
| `compressed-context-constraint` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools | - |

Scripted fixture results prove harness contract regression only. They do not measure autonomous LLM reasoning quality.
