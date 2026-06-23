# Scion v0.4 Current State

Last updated: 2026-06-23

This file is the operational resume point, not a run log. Historical root
chronology belongs in focused experiment reports and git history.

## Operating Frame

- Branch: `codex/v04-evidence-repair-plan`.
- Boundary authority: `scion/design/scion-architecture-v3.md`.
- v0.4 closes only after Scion demonstrates effective research behavior:
  warehouse should recover useful continuous optimization from champion `v2`,
  and CVRP/VRP should produce evidence-backed solver-design follow-up.
- v0.5 is for broader experiment matrices. Do not defer v0.4 framework
  stability, prompt/context quality, runtime semantics, or effective-agent
  research to v0.5.
- Current posture: avoid broad budgets, generic truncation/compression, and
  decorative gates. Keep CVRP/warehouse semantics problem-owned and keep
  `DecisionFeatures` problem-neutral.

## Current Design Gate

- Designs A-K in `scion/design/v0.4-effective-research-repair-design.md` are
  accepted local framework repairs for scheduling status, research-guidance
  contracts, lifecycle/failure routing, target-intent authority, launcher
  lifecycle, and mechanism-evidence follow-up. They remain generic core
  contracts while CVRP/warehouse details remain problem-owned.
- Design L is implemented locally: budget-exhausting runtime aggregates remain
  in raw evidence, but proposal-visible feedback, phase causal runtime
  evidence, branch memory/dossier, and feedback-tool stats render
  `runtime_regression_rate_interpretation=not_applicable_budget_exhausting`
  instead of numeric `runtime_regression_rate`.
- Design M is implemented locally: budget-exhausting low/cached/insufficient or
  aggregate-excluded runtime evidence is observational and cannot accumulate
  runtime-evidence pressure or trigger `runtime_evidence_completeness_clean_fork`.
  Stale branch-card fresh-runtime markers are also suppressed under
  `budget_exhausting`. Comparative runtime pressure behavior is preserved.
- Local validation uses this machine's conda `claw` environment. The combined
  proposal/runtime-pressure/protocol focused suite passes (`108 passed`), and
  `git diff --check` is clean.
- The WSL reverse SSH tunnel is restored. The current local repair files were
  synced to the WSL runner worktree, and WSL conda `scion` focused validation
  passes (`108 passed`).

## Current Decision

- v0.4 is not closed. The remaining acceptance question is effective research
  behavior, not more broad framework churn.
- CVRP has accepted framework evidence for active-slot scheduling,
  weak-positive follow-up, target-intent authority, mechanism-evidence
  follow-up, and MDE-aware rejection. It still lacks solver improvement or
  promotion.
- Warehouse has positive movement evidence from earlier v2-to-v3 work and a
  prepared/current positive-control path. The next run should start only after
  local runtime-semantics repairs are synchronized and validated on WSL.
- The next operational action is to record a clean WSL/local sync point, then
  inspect or launch the prepared warehouse positive-control and CVRP follow-up
  runs.

## WSL Runner

- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- WSL Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- WSL experiment root: `/home/xjy-ubuntu/research/scion-experiments`
- Current server-side SSH probe:
  `ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no xjy-ubuntu@127.0.0.1 'echo SSH_OK; hostname; whoami; /home/xjy-ubuntu/miniconda3/envs/scion/bin/python --version'`
- Current probe result: `SSH_OK`, host `xjy-workspace`, user `xjy-ubuntu`,
  Python `3.10.20`.

Before launching any prepared root, require strict launch readiness from the
same WSL checkout:

```bash
PY=/home/xjy-ubuntu/miniconda3/envs/scion/bin/python
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  "$PY" /home/xjy-ubuntu/research/or-autoresearch-agent/scion/tools/check_launch_readiness.py \
  <prepared-root> --require-launch-ready --format json
```

After a run, inspect `exit.txt`, `run_status.json`, and
`postrun_acceptance/readiness/` on WSL, then mirror the WSL root back to the
server. For WSL-origin roots, WSL postrun acceptance is authoritative; the
local mirror keeps WSL absolute paths in postrun artifacts, so use
`--skip-postrun-check` during mirror-only sync:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  python scripts/sync_wsl_run_root.py <wsl-run-root> \
  --execute --skip-postrun-check --format json
```

## Preserved Guarantees

- No CVRP/VRP/warehouse-specific scheduler, target-intent, launcher-lifecycle,
  mechanism-evidence, or runtime-pressure exceptions are accepted in generic
  core.
- Raw calibration rows, BKS data, case-level problem facts, free-form proposal
  prose, and runtime feedback text remain excluded from `DecisionFeatures`.
- Runtime regressions still fail closed when they are actionable comparative
  evidence or hard execution failures. Design L/M only make budget-exhausting
  aggregate slowdown semantics observational.
- Candidate crashes, invalid outputs, telemetry guard failures, and verification
  failures remain fail-closed.
- Problem-owned measurement declarations define runtime model, effect scale,
  pairing validity, and readiness diagnostics; generic core consumes normalized
  semantics.
- Status docs should be replaced with current facts rather than appended with
  root chronology.

## Problem Frontiers

- Warehouse: recover continuous improvement behavior from champion `v2` without
  misclassifying guidance-binding or quality-feedback defects as a true plateau.
- CVRP: use A/A MDE and case variance while seeking branch depth,
  same-mechanism follow-up, and solver-design improvements. Existing framework
  roots show rejection/repair behavior but no solver promotion yet.
- Runtime semantics: keep budget-exhausting runtime ratios observational while
  preserving comparative runtime evidence as a valid pressure and failure
  signal.

## Next Actions

1. Record the current local/WSL sync point so experiment roots have an auditable
   code baseline.
2. Launch or inspect the prepared warehouse
   positive-control root and the next CVRP follow-up from the synchronized
   checkout.
3. Evaluate runs for effective research behavior: warehouse continuous
   optimization, CVRP branch depth and solver-design follow-up, MDE-aware
   rejection, and absence of framework-control blockers.

## Pointers

- Architecture: `scion/design/scion-architecture-v3.md`
- Repair design: `scion/design/v0.4-effective-research-repair-design.md`
- Task source: `scion/TASK.md`
- Audit basis:
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`
