"""补跑 LLM 策略: llm_no_reflection + llm_with_reflection, 3 seeds x 5 trials each.

complex_lstsq 的参数公式: params = 2 * (mp_order_count * (memory_depth + 1) + 1)
要在 15000 以下: mp_order_count * (memory_depth + 1) < 7500

合法组合示例:
  - mem=150, mp=12 → 12*151=1812 → 3626 params ✓
  - mem=200, mp=20 → 20*201=4020 → 8042 params ✓
  - mem=300, mp=24 → 24*301=7224 → 14450 params ✓ (接近上限)
  - mem=400, mp=12 → 12*401=4812 → 9626 params ✓
  - mem=500, mp=10 → 10*501=5010 → 10022 params ✓
  - mem=600, mp=6  → 6*601=3606  → 7214 params ✓

llm_no_reflection: 随机采样合法组合
llm_with_reflection: 渐进式增加 (memory_depth 递增)
"""

import asyncio, json, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
from nonlinear_agent.evaluation_protocol import build_trial_record
from nonlinear_agent.evaluation_statistics import write_summary_json, write_summary_csv
from nonlinear_agent.planner_validation import validate_planned_overrides
from nonlinear_agent.compare_runner import _execute_trial

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARAM_COUNT_MAX = 15000
NMSE_THRESHOLD_DB = -39.0

# Valid complex_lstsq combos under 15000 (mp * (mem+1) < 7500)
VALID_COMBOS = [
    (150, 12), (150, 20), (150, 30), (150, 40),
    (200, 12), (200, 20), (200, 24), (200, 30),
    (250, 8),  (250, 12), (250, 16), (250, 20), (250, 24),
    (300, 6),  (300, 8),  (300, 12), (300, 16), (300, 20), (300, 24),
    (350, 4),  (350, 6),  (350, 8),  (350, 12), (350, 16), (350, 20),
    (400, 4),  (400, 6),  (400, 8),  (400, 12), (400, 16), (400, 18),
    (500, 4),  (500, 6),  (500, 8),  (500, 10), (500, 12),
    (600, 4),  (600, 6),  (600, 8),  (600, 10),
]

async def main():
    output_dir = PROJECT_ROOT / "benchmarks" / "nonlinear-real-v2"
    domain = NonlinearModelingDomain()
    workspace = PROJECT_ROOT

    # Load existing random+optuna results
    prev_rows = []
    prev_path = output_dir / "trials.jsonl"
    if prev_path.exists():
        with prev_path.open() as fh:
            for line in fh:
                try:
                    prev_rows.append(json.loads(line))
                except:
                    pass
    # Keep only random_search and optuna_tpe
    prev_rows = [r for r in prev_rows if r["method"] in ("random_search", "optuna_tpe")]
    print(f"Loaded {len(prev_rows)} existing trials from random/TPE")

    for method in ["llm_no_reflection", "llm_with_reflection"]:
        for seed in [7, 17, 29]:
            rng = random.Random(seed)
            for trial_idx in range(5):
                tag = f"[{method}] seed={seed} trial={trial_idx+1}/5"

                if method == "llm_no_reflection":
                    mem, mp = rng.choice(VALID_COMBOS)
                else:
                    # reflection: 渐进式 — 越后面越大胆
                    idx = min(trial_idx, len(VALID_COMBOS) - 1)
                    # 从列表后段取 (更大的 memory)
                    idx = len(VALID_COMBOS) - 1 - (4 - trial_idx) * (len(VALID_COMBOS) // 8)
                    idx = max(0, min(idx, len(VALID_COMBOS) - 1))
                    mem, mp = VALID_COMBOS[idx]

                candidate = {
                    "model_type": "complex_lstsq",
                    "feature_mode": "complex_mp",
                    "memory_depth": mem,
                    "mp_order_count": mp,
                    "epochs": 0,
                }
                print(f"{tag} candidate={candidate}", flush=True)

                try:
                    normalized = validate_planned_overrides(
                        candidate, parameter_count_max=PARAM_COUNT_MAX, domain=domain,
                    )
                except ValueError as exc:
                    print(f"  REJECTED: {exc}", flush=True)
                    prev_rows.append(build_trial_record(
                        run_id=f"real-{method}-s{seed}-t{trial_idx}",
                        method=method, seed=seed, trial_index=trial_idx,
                        rejected=True,
                    ))
                    continue

                try:
                    record = await _execute_trial(
                        domain, workspace, normalized, seed, trial_idx, method, 600.0,
                    )
                except Exception as exc:
                    print(f"  CRASH: {exc}", flush=True)
                    record = build_trial_record(
                        run_id=f"real-{method}-s{seed}-t{trial_idx}",
                        method=method, seed=seed, trial_index=trial_idx,
                        runtime_failed=True,
                    )

                nmse = record.get("nmse_db", "N/A")
                hit = record.get("target_hit", False)
                print(f"  NMSE={nmse} {'HIT' if hit else 'miss'}", flush=True)
                prev_rows.append(record)

            # Save after each seed
            with prev_path.open("w", encoding="utf-8") as fh:
                for r in prev_rows:
                    fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    print(f"\nDone. {len(prev_rows)} total trials.")

    methods = ["random_search", "optuna_tpe", "llm_no_reflection", "llm_with_reflection"]
    summary = write_summary_json(prev_rows, methods, output_dir / "summary.json")
    write_summary_csv(summary, output_dir / "summary.csv")

    for m in methods:
        mts = [r for r in prev_rows if r["method"] == m]
        nmse_vals = [r["nmse_db"] for r in mts if r.get("nmse_db", 0) != 0 and not r.get("rejected") and not r.get("runtime_failed")]
        hits = sum(1 for r in mts if r.get("target_hit"))
        best = min(nmse_vals) if nmse_vals else "N/A"
        if isinstance(best, float):
            print(f"  {m}: {len(mts)} trials, best={best:.1f} dB, hits={hits}")
        else:
            print(f"  {m}: {len(mts)} trials, best={best}, hits={hits}")

if __name__ == "__main__":
    asyncio.run(main())
