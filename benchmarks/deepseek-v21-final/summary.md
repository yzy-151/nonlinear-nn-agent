# Agent Benchmark Summary

- case_count: `10`
- target_hit_rate: `0.5`
- rejected_rate: `0.85`
- runtime_failure_rate: `0.0`
- average_experiments_used: `0.9`
- best_nmse_db: `-37.42494350080102`

## Cases

- `target-hit`: hit=False, best_nmse=None, rejected=7, failed=0, succeeded=0
- `invalid-plan`: hit=False, best_nmse=None, rejected=3, failed=0, succeeded=0
- `runtime-failure`: hit=False, best_nmse=None, rejected=3, failed=0, succeeded=0
- `reflection-recovery`: hit=True, best_nmse=-37.42494350080102, rejected=6, failed=0, succeeded=1
- `budget-stop`: hit=False, best_nmse=None, rejected=4, failed=0, succeeded=0
- `json-tolerance`: hit=True, best_nmse=-37.42494350080102, rejected=5, failed=0, succeeded=2
- `parameter-budget-edge`: hit=True, best_nmse=-37.42494350080102, rejected=7, failed=0, succeeded=1
- `unknown-tool`: hit=False, best_nmse=None, rejected=3, failed=0, succeeded=0
- `long-history-compression`: hit=True, best_nmse=-37.42494350080102, rejected=10, failed=0, succeeded=1
- `multi-round-self-correction`: hit=True, best_nmse=-37.42494350080102, rejected=3, failed=0, succeeded=4
