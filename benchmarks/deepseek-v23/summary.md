# Agent Benchmark Summary

- case_count: `10`
- target_hit_rate: `0.4`
- rejected_rate: `0.8934426229508197`
- runtime_failure_rate: `0.03278688524590164`
- average_experiments_used: `1.3`
- best_nmse_db: `-37.42494350080102`

## Cases

- `target-hit`: hit=True, best_nmse=-37.42494350080102, rejected=8, failed=0, succeeded=2
- `invalid-plan`: hit=True, best_nmse=-37.42494350080102, rejected=4, failed=0, succeeded=1
- `runtime-failure`: hit=False, best_nmse=-1.488099266918831, rejected=1, failed=1, succeeded=0
- `reflection-recovery`: hit=False, best_nmse=-29.928910101282284, rejected=20, failed=1, succeeded=0
- `budget-stop`: hit=False, best_nmse=None, rejected=11, failed=0, succeeded=0
- `json-tolerance`: hit=False, best_nmse=None, rejected=20, failed=0, succeeded=0
- `parameter-budget-edge`: hit=False, best_nmse=None, rejected=0, failed=0, succeeded=0
- `unknown-tool`: hit=False, best_nmse=-29.928910101282284, rejected=5, failed=1, succeeded=0
- `long-history-compression`: hit=True, best_nmse=-37.42494350080102, rejected=32, failed=1, succeeded=2
- `multi-round-self-correction`: hit=True, best_nmse=-37.42494350080102, rejected=8, failed=0, succeeded=4
