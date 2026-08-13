# Evidence Benchmark v1

## Agent behavior

| Mode | Tasks | Attempts | pass@1 | pass@3 | Claim boundary |
| --- | ---: | ---: | ---: | ---: | --- |
| Scripted | 18 | 54 | 1.000 | - | Harness contract regression; no LLM reasoning claim. |
| DeepSeek | 18 | 54 | 0.944 | 1.000 | Real LLM action selection and recovery on deterministic faults. |

## Search quality

| Method | Seeds | Effective trials | Target hit | Best metric mean |
| --- | ---: | ---: | ---: | ---: |
| `llm_direct` | 3 | 30 | 0.333 | 0.0433625 |
| `llm_history_only` | 3 | 30 | 0.433 | 0.0433606 |
| `llm_history_facts` | 3 | 30 | 0.400 | 0.0433606 |
| `llm_history_facts_priors` | 3 | 30 | 0.533 | 0.0433606 |

### Paired increments

- `history_increment`: delta `-1.89804e-06`, paired seeds `3`, significant `True`.
- `facts_increment`: delta `0`, paired seeds `3`, significant `False`.
- `priors_increment`: delta `0`, paired seeds `3`, significant `False`.

## Runtime reliability

- duplicate execution rate: `0.0`
- event loss rate: `0.0`
- terminal consistency: `1.0`
- recovery rate: `1.0`

## Claim policy

Scripted results validate deterministic harness contracts only. Online results validate LLM decisions on fixed faults. Search results alone support model-quality claims.
