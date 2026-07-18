# Agent Benchmark Summary

- case_count: `10`
- target_hit_rate: `0.7`
- rejected_rate: `0.21052631578947367`
- runtime_failure_rate: `0.10526315789473684`
- average_experiments_used: `1.5`
- best_nmse_db: `-36.5`

## Cases

- `target-hit`: hit=True, best_nmse=-36.0, rejected=0, failed=0, succeeded=1
- `invalid-plan`: hit=False, best_nmse=None, rejected=1, failed=0, succeeded=0
- `runtime-failure`: hit=False, best_nmse=-20.0, rejected=0, failed=1, succeeded=0
- `reflection-recovery`: hit=True, best_nmse=-36.5, rejected=1, failed=0, succeeded=1
- `budget-stop`: hit=True, best_nmse=-35.5, rejected=0, failed=0, succeeded=1
- `json-tolerance`: hit=True, best_nmse=-36.0, rejected=0, failed=0, succeeded=1
- `parameter-budget-edge`: hit=True, best_nmse=-35.8, rejected=0, failed=0, succeeded=1
- `unknown-tool`: hit=False, best_nmse=None, rejected=1, failed=0, succeeded=0
- `long-history-compression`: hit=True, best_nmse=-36.0, rejected=0, failed=0, succeeded=6
- `multi-round-self-correction`: hit=True, best_nmse=-36.0, rejected=1, failed=1, succeeded=2
