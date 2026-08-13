# Agent Task Benchmark

- Domain: `nonlinear-modeling`
- Evaluation mode: `real_llm_fault_fixture`
- Tasks: 2
- Attempts: 6
- pass@1: 1.000

| Case | Attempt | Passed | Passed checks | Failed checks |
| --- | ---: | --- | --- | --- |
| `stop-after-target-hit` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, required_metric | - |
| `stop-after-target-hit` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, required_metric | - |
| `stop-after-target-hit` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, required_metric | - |
| `reuse-history-best` | 1 | True | terminal_status, action_budget, required_tools, forbidden_tools, required_metric | - |
| `reuse-history-best` | 2 | True | terminal_status, action_budget, required_tools, forbidden_tools, required_metric | - |
| `reuse-history-best` | 3 | True | terminal_status, action_budget, required_tools, forbidden_tools, required_metric | - |

Scripted fixture results prove harness contract regression only. They do not measure autonomous LLM reasoning quality.
