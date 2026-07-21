# Agent Benchmark Summary

- case_count: `10`
- target_hit_rate: `0.9`
- rejected_rate: `0.07407407407407407`
- runtime_failure_rate: `0.07407407407407407`
- average_experiments_used: `2.5`
- best_nmse_db: `-42.42519559502256`

## Cases

- `target-hit`: hit=True, best_nmse=-42.42519559502256, rejected=0, failed=0, succeeded=2
- `invalid-plan`: hit=True, best_nmse=-38.72509875795173, rejected=0, failed=0, succeeded=1
- `runtime-failure`: hit=False, best_nmse=-25.29114250603827, rejected=0, failed=1, succeeded=0
- `reflection-recovery`: hit=True, best_nmse=-42.26426827395959, rejected=0, failed=0, succeeded=2
- `budget-stop`: hit=True, best_nmse=-38.63197495437891, rejected=0, failed=0, succeeded=1
- `json-tolerance`: hit=True, best_nmse=-42.322425181376566, rejected=0, failed=0, succeeded=2
- `parameter-budget-edge`: hit=True, best_nmse=-38.39716977170435, rejected=1, failed=0, succeeded=2
- `unknown-tool`: hit=True, best_nmse=-38.428267365482235, rejected=0, failed=0, succeeded=1
- `long-history-compression`: hit=True, best_nmse=-42.322425181376566, rejected=0, failed=1, succeeded=8
- `multi-round-self-correction`: hit=True, best_nmse=-40.97879144915566, rejected=1, failed=0, succeeded=4
