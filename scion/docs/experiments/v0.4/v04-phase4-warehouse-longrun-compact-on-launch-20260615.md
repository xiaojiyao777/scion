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

Clean WSL run:

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-phase4-warehouse-longrun-compact-on-3x24r-20260615T163700Z`
- Server prep root:
  `/home/clawd/research/scion-experiments/v04-phase4-warehouse-longrun-compact-on-3x24r-20260615T163700Z`
- Commit: `0298b0a`
- Script: `run_wsl.sh`

The first attempted root ended immediately because the warehouse problem and
production split in the repository contain server absolute paths. It was stopped
before rep02 launched:

- Aborted root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-phase4-warehouse-longrun-compact-on-3x24r-20260615T162506Z`
- Failure: missing `/home/clawd/research/or-autoresearch-agent/surrogate` on WSL.

The second attempted root fixed server paths but put the problem copy in a
config directory without a sibling `problem-v1.yaml`. CLI therefore used the
legacy problem path, logged `ExperimentProtocol initialized without
metric_specs; using legacy objective fallback`, and produced a surface contract
mismatch. It was stopped before rep02 launched:

- Aborted root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-phase4-warehouse-longrun-compact-on-3x24r-20260615T163050Z`
- Failure: missing `problem-v1.yaml` sibling in the experiment-local config
  directory.

The clean rerun used experiment-local WSL copies of `problem.yaml`,
`problem-v1.yaml`, and `split_manifest_prod.yaml`, replacing server paths with:

- `/home/xjy-ubuntu/research/or-autoresearch-agent`
- `/home/xjy-ubuntu/research/scion-data`

Server `scion-data` was synced to WSL before the clean launch.

## Outcome

The active clean rerun started at `2026-06-15T16:37:52Z` and was stopped at
`2026-06-15T16:52:52Z`.

The launch configuration itself was correct enough to enter the adapter-backed
production path: rep01 and rep02 used WSL-local problem/split paths, the
`problem-v1.yaml` sibling was present, and the log did not show the legacy
metric-spec fallback.

The run is invalid for warehouse longrun promotion evidence. Early agentic code
attempts repeatedly violated the patch-edit protocol, including empty
`exact_replace.old_string` fields and an attempted whole-file replacement of a
host-visible file. Both active repeats then entered `verification_light`
hard-failure loops before any protocol rows were produced:

- rep01: `protocol_metric_results=0`,
  `verification_failure_consumed_candidates=7`.
- rep02: `protocol_metric_results=0`,
  `verification_failure_consumed_candidates=2`.

Interpretation: keep this root as agent-behavior/debug evidence for patch
protocol and source-edit quality. Do not treat it as evidence that warehouse
cannot recover continued improvement or promotion under a longer v0.4 budget.
The next warehouse longrun should first address or explicitly debug this
agentic patch failure mode, then re-run from a clean root.
