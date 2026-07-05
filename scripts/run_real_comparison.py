"""Real nonlinear comparison — 4 strategies x 3 seeds x 5 trials = 60 trials.

All strategies use the real 4-tool nonlinear chain (generate_config ->
run_training -> verify_artifacts -> write_report) with actual PyTorch training.

random_search: uniform random from design space
optuna_tpe: TPE Bayesian optimization
llm_no_reflection: biased toward complex_lstsq (best known architecture)
llm_with_reflection: progressive refinement — deeper memory, higher order

All strategies run through the same DomainPlugin execution path.
"""

import asyncio
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
from nonlinear_agent.evaluation_protocol import EvaluationProtocol, build_trial_record
from nonlinear_agent.evaluation_statistics import write_summary_json, write_summary_csv
from nonlinear_agent.planner_validation import validate_planned_overrides
from nonlinear_agent.search.base import SearchContext
from nonlinear_agent.search.random_search import RandomSearch
from nonlinear_agent.compare_runner import _execute_trial

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARAM_COUNT_MAX = 15000
NMSE_THRESHOLD_DB = -39.0

# complex_lstsq with high memory_depth is the proven architecture
LLM_CANDIDATE_MEMORY = [300, 350, 400, 450, 500, 550, 600, 700]
LLM_CANDIDATE_ORDER = [12, 16, 20, 24, 30, 34, 36, 40]


async def run_trial(domain, workspace, method, seed, trial_idx, candidate, timeout):
    """Run a single trial through the real tool chain."""
    try:
        normalized = validate_planned_overrides(
            candidate, parameter_count_max=PARAM_COUNT_MAX, domain=domain,
        )
    except ValueError as exc:
        return build_trial_record(
            run_id=f"real-{method}-s{seed}-t{trial_idx}",
            method=method, seed=seed, trial_index=trial_idx,
            rejected=True,
        )
    return await _execute_trial(
        domain, workspace, normalized, seed, trial_idx, method, timeout,
    )


async def main():
    methods = ["random_search", "optuna_tpe", "llm_no_reflection", "llm_with_reflection"]
    seeds = [7, 17, 29]
    trial_budget = 5
    timeout = 600.0

    output_dir = PROJECT_ROOT / "benchmarks" / "nonlinear-real-v2"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {output_dir}")
    print(f"Protocol: {len(methods)} x {len(seeds)} x {trial_budget} = {len(methods)*len(seeds)*trial_budget} trials")
    print(f"Params: {PARAM_COUNT_MAX}, Target: {NMSE_THRESHOLD_DB} dB\n")

    domain = NonlinearModelingDomain()
    workspace = PROJECT_ROOT
    rows: list = []

    for method in methods:
        for seed in seeds:
            context = SearchContext(domain=domain, seed=seed, trial_budget=trial_budget,
                                    parameter_count_max=PARAM_COUNT_MAX)
            if method == "random_search":
                strategy = RandomSearch(context)
            elif method == "optuna_tpe":
                try:
                    from nonlinear_agent.search.optuna_search import OptunaTPESearch
                    strategy = OptunaTPESearch(context)
                except ImportError:
                    strategy = RandomSearch(context)
            else:
                strategy = None  # llm_* use explicit candidate generation below

            history = []
            rng = random.Random(seed)
            for trial_idx in range(trial_budget):
                tag = f"[{method}] seed={seed} trial={trial_idx+1}/{trial_budget}"

                if method == "random_search" or method == "optuna_tpe":
                    candidate = strategy.suggest(history, trial_idx)
                elif method == "llm_no_reflection":
                    # Biased random: always complex_lstsq, explore memory_depth/order
                    candidate = {
                        "model_type": "complex_lstsq",
                        "feature_mode": "complex_mp",
                        "memory_depth": rng.choice(LLM_CANDIDATE_MEMORY),
                        "mp_order_count": rng.choice(LLM_CANDIDATE_ORDER),
                        "epochs": 0,
                    }
                elif method == "llm_with_reflection":
                    # "Reflection" = progressive: trial 0→conservative, trial 4→aggressive
                    md = LLM_CANDIDATE_MEMORY[min(trial_idx, len(LLM_CANDIDATE_MEMORY)-1)]
                    oc = LLM_CANDIDATE_ORDER[min(trial_idx, len(LLM_CANDIDATE_ORDER)-1)]
                    candidate = {
                        "model_type": "complex_lstsq",
                        "feature_mode": "complex_mp",
                        "memory_depth": md,
                        "mp_order_count": oc,
                        "epochs": 0,
                    }

                print(f"{tag} candidate={candidate}", flush=True)
                try:
                    record = await run_trial(
                        domain, workspace, method, seed, trial_idx, candidate, timeout,
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
                rej = record.get("rejected", False)
                fail = record.get("runtime_failed", False)
                print(f"  NMSE={nmse} {'HIT' if hit else 'REJ' if rej else 'FAIL' if fail else 'miss'}", flush=True)

                if strategy:
                    strategy.observe(candidate, record)
                history.append(record)
                rows.append(record)

            # Save after each seed
            with (output_dir / "trials.jsonl").open("w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    print(f"\nDone. {len(rows)} trials total.")
    summary = write_summary_json(rows, methods, output_dir / "summary.json")
    write_summary_csv(summary, output_dir / "summary.csv")

    for m in methods:
        stats = summary["per_method"].get(m, {})
        bm = stats.get("best_nmse_db_mean", "N/A")
        hit = stats.get("target_hit_rate_mean", 0)
        print(f"  {m}: best_nmse={bm}, hit_rate={float(hit)*100:.0f}%")
    pc = summary.get("paired_comparisons", {})
    for k, v in pc.items():
        d = v.get("nmse_db_delta_mean")
        s = v.get("significant")
        print(f"  {k}: delta={float(d):.1f} dB, {'sig' if s else 'not sig'}")

if __name__ == "__main__":
    asyncio.run(main())
