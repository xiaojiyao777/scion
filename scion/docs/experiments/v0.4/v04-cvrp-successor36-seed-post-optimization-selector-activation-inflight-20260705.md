# CVRP successor36 seed-post selector activation in-flight

Date: 2026-07-05

## Purpose

Run successor36 as the promoted `seed_post_optimization_selector` activation
repair after successor35 completed valid active but loss-heavy
`capacity_tightness_removal` evidence.

Design:
`scion/docs/experiments/v0.4/v04-cvrp-successor36-seed-post-optimization-selector-activation-design-20260705.md`

## Clean Launch

Root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor36-seed-post-optimization-selector-activation-server-clean-2r-gpt55-20260705T081741Z-claw`

PID:
`1468229`

Commit:
`2ad08e52`

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
- completion preflight reached `pre_campaign_completion_preflight.v1.json`
- campaign execution marker was written
- run log reached `Starting campaign: cvrp`

## Non-evidence Failed Root

An earlier root with the same mechanism exited before campaign execution:

`/home/clawd/research/scion-experiments/v04-cvrp-successor36-seed-post-optimization-selector-activation-server-2r-gpt55-20260705T081548Z-claw`

That root failed the launcher runtime guard because CVRP guidance/code changes
were still uncommitted under guarded runtime paths. It has
`wrapper_exit_status=64` and `git_runtime_dirty=true`. Treat it as a launch
hygiene failure, not as proposal, model-call, or solver evidence.

## Acceptance Notes

Interpret only the clean root above. Minimum useful result:

- target-intent and formal hypothesis name `seed_post_optimization_selector`;
- code target is `policies/baseline_modules/seed_selector.py` with
  `create_new`;
- scheduler edits are minimal construction-boundary wiring;
- mechanism activation and direct pre-ALNS/VNS selected-seed-versus-baseline
  `record_move` delta are visible;
- CMT2/CMT4 case evidence is visible;
- postrun readiness is ready before analysis.
