# CVRP successor36b seed-post selector static-smoke repair in-flight

Date: 2026-07-05

## Purpose

Relaunch successor36 after repairing the CVRP construction-seed static smoke
recognizer so that the promoted `seed_post_optimization_selector` module path,
`policies/baseline_modules/seed_selector.py`, is scanned for direct
same-mechanism `record_move(..., delta=...)` telemetry.

Predecessor quality-block postrun:
`scion/docs/experiments/v0.4/v04-cvrp-successor36-seed-post-optimization-selector-quality-block-postrun-20260705.md`

Design:
`scion/docs/experiments/v0.4/v04-cvrp-successor36-seed-post-optimization-selector-activation-design-20260705.md`

## Launch

Root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor36b-seed-post-selector-static-smoke-repair-server-2r-gpt55-20260705T104029Z-claw`

PID:
`1476526`

Commit:
`9fc23c86`

Command shape:

- `--rounds 2`
- `--model gpt-5.5`
- `--base-url http://127.0.0.1:8080`
- `--completion-preflight`
- `--force-surface solver_design`
- `--force-action create_new`
- `--force-target-file policies/baseline_modules/seed_selector.py`
- server-local conda env: `claw`

Initial health check:

- `run_status.status=running`
- runtime guard passed on commit `9fc23c86`
- completion preflight detail file was written
- campaign execution marker was written
- run log reached `Starting campaign: cvrp`

## Acceptance Notes

Minimum useful result:

- the previous `cvrp_construction_seed_direct_effect_missing` recognizer block
  should not repeat for candidates that record direct telemetry in
  `seed_selector.py`;
- target-intent and formal hypothesis name `seed_post_optimization_selector`;
- scheduler edits remain minimal construction-boundary integration;
- mechanism activation and direct pre-ALNS/VNS selected-seed-versus-baseline
  `record_move` delta are visible;
- postrun readiness is ready before solver-effect analysis.
