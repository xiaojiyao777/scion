# Warehouse Longrun Compact ON Launch

Date: 2026-06-15

Purpose: continue the Phase 4 effective-research gate for warehouse by testing
whether the current v0.4 default can still produce repeated improvement or
continuous promotion under a longer budget. This is not a governance on/off
comparison; it is a single-arm longrun check.

## Design

- Problem: warehouse production protocol/split/seeds.
- Model: local `gpt-5.5`.
- Arm: `measurement_governance=on`.
- Prompt context: `compact-measurement-diagnostics`.
- Rounds: `24` per repeat.
- Repeats: `3`.
- Solver cap: `--time-limit-sec 30`.
- Early stop: disabled.
- Agentic session timeout: `900s`.
- Scheduling: WSL, max two concurrent cells, with a 600s stagger before rep02
  and rep03 starting after rep01 completes.

## Artifacts

Clean active WSL run:

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-phase4-warehouse-longrun-compact-on-3x24r-20260615T163050Z`
- Server prep root:
  `/home/clawd/research/scion-experiments/v04-phase4-warehouse-longrun-compact-on-3x24r-20260615T163050Z`
- Commit: `0298b0a`
- Script: `run_wsl.sh`

The first attempted root ended immediately because the warehouse problem and
production split in the repository contain server absolute paths. It was stopped
before rep02 launched:

- Aborted root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-phase4-warehouse-longrun-compact-on-3x24r-20260615T162506Z`
- Failure: missing `/home/clawd/research/or-autoresearch-agent/surrogate` on WSL.

The clean rerun uses experiment-local WSL copies of `problem.yaml` and
`split_manifest_prod.yaml`, replacing server paths with:

- `/home/xjy-ubuntu/research/or-autoresearch-agent`
- `/home/xjy-ubuntu/research/scion-data`

Server `scion-data` was synced to WSL before the clean launch.

## Current State

The clean rerun started at `2026-06-15T16:29:12Z`. At launch verification,
rep01 was actively running the 24-round campaign with the WSL-local problem and
split paths. Final interpretation is pending completion and sync.

