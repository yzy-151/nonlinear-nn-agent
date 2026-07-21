# agent-dry-run-001 Experiment Plan

## Goal

Validate the Agentic Experiment Runner loop for nonlinear NN MPDPD fitting and produce resume-ready evidence.

## Agent Steps

1. Read the baseline YAML configuration.
2. Write a reproducible experiment configuration.
3. Run the nonlinear NN training command.
4. Parse `metrics.json` and verify NMSE.
5. Check that PSD output exists for visual inspection.
6. Write a resume-ready change log.

## Success Criteria

- NMSE must be <= 5.00 dB.
- `metrics.json` must exist.
- `psd.png` must exist.
- Summary must include config, metrics, and resume angle.
