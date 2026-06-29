# Scion v0.4 Current State

Last updated: 2026-06-29

This file is the operational resume point, not a run log. Historical root
chronology belongs in focused experiment reports, sparse milestones, and git
history.

## Operating Frame

- Branch: `codex/v04-evidence-repair-plan`.
- Boundary authority: `scion/design/scion-architecture-v3.md`.
- Current task source: `scion/TASK.md`.
- Latest cross-document audit:
  `scion/reports/v04-task-basis-alignment-audit-20260629.md`.
- v0.4 closes only after Scion demonstrates effective research behavior on the
  repaired framework. v0.5 is for broad controlled experiment matrices, not
  deferred v0.4 framework repair.
- Current execution should use the server conda `claw` environment unless WSL
  SSH is rechecked and available.

## Current Decision

v0.4 is not closed.

The framework direction is largely correct:

- v3 `DecisionFeatures` boundaries remain intact.
- Measurement declarations, A/A/MDE diagnostics, opportunity summaries, and
  postrun review summaries are problem-owned and proposal/readiness-visible,
  not Decision input.
- CVRP `runtime_model=budget_exhausting` semantics are now treated as
  observational for comparative runtime pressure while preserving raw evidence.
- Branch depth, prepared successor focus, reviewed/default-avoid evidence,
  inactive-mechanism suppression, resume snapshots, and postrun readiness have
  materially improved.
- Warehouse is restored as a positive effective-research control and
  plateau-review-ready for v0.4 framework evidence.

The remaining closeout gaps are:

- CVRP remains solver-negative. Recent successor work proves framework
  behavior, not promotion-grade solver improvement.
- Warehouse calibration provenance is incomplete: both warehouse spec copies
  reference `calibration/aa_noise_floor.json`, but the artifact is not checked
  in under the corresponding calibration directories.
- Large files remain a design risk. Further behavior changes in oversized
  core/postrun/proposal/problem files need a modularization design first.
- The v0.5 governance ablation matrix should be preregistered, but not run as a
  v0.4 closeout substitute.

## Active Technical State

- Designs A-K in `scion/design/v0.4-effective-research-repair-design.md` are
  accepted local repairs for scheduling status, guidance contracts,
  lifecycle/failure routing, target-intent authority, launcher lifecycle, and
  mechanism-evidence follow-up.
- Designs L/M are accepted runtime repairs: budget-exhausting runtime evidence
  remains in raw artifacts but no longer creates numeric proposal-visible
  runtime-regression pressure or stale fresh-runtime clean-fork pressure.
- Design N moved postrun/readiness behavior toward typed generic ports and
  problem-owned review providers. Do not add new semantics to legacy postrun
  helper scripts when a named port/provider is the right boundary.
- Design O introduced `MeasurementConsumerView` as the typed consumer view for
  protocol/runtime/proposal/readiness paths.
- Designs P/Q/R introduced problem-owned opportunity summaries, opportunity
  evidence commitments, and postrun visibility for those commitments. These are
  proposal/report signals and remain excluded from Decision.
- Prepared successor-focus arbitration and scheduler filtering are generic and
  field-driven: reviewed or suppressed branch-local mechanism ids can be
  superseded for prepared runs, but mixed branches with non-excluded mechanisms
  remain schedulable under proposal guards.
- Resume launches quarantine copied terminal artifacts under
  `run_root/resume_snapshot/`; current-run canonical files must represent the
  current execution.

## Problem Frontiers

Warehouse:

- Treat the clean v2 positive-control run as restored effective-research and
  plateau-review evidence for v0.4 framework purposes.
- Do not launch another warehouse run by default.
- Resolve the checked-in calibration artifact mismatch before treating
  warehouse measurement readiness as fully reproducible.

CVRP:

- Treat current successor evidence as framework-positive and solver-negative.
- Continue using A/A MDE and case variance when interpreting CVRP effects.
- Do not repeat unchanged reviewed mechanisms. The next attempt should
  clean-fork to a materially different CVRP-owned causal path or explicitly
  repair `seed_post_optimization_selector` activation.
- Use problem-owned successor review evidence, row-local `mechanism_family`,
  direct `mechanism_evidence.primary_mechanism`, and phase telemetry as the
  current source of truth.

## Next Actions

1. Resolve warehouse calibration provenance by restoring the artifact, changing
   both specs to a checked-in artifact, or documenting intentional external
   calibration.
2. Continue one CVRP successor attempt from the current problem-owned guidance:
   materially new causal path or explicit seed-post activation repair.
3. Write a lightweight large-file modularization design before adding behavior
   to oversized files.
4. Preregister the v0.5 governance on/off experiment matrix.
5. Keep status documents compact; put detailed root counters and caveats in
   focused experiment reports.

## Runner Notes

Server:

- Repo: `/home/clawd/research/or-autoresearch-agent`
- Use conda `claw` for local validation/runs unless the task explicitly
  requires WSL.

WSL, only after rechecking connectivity:

```bash
ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 \
  -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no \
  xjy-ubuntu@127.0.0.1 \
  'echo SSH_OK; hostname; whoami; /home/xjy-ubuntu/miniconda3/envs/scion/bin/python --version'
```

If WSL-origin roots are mirrored locally, WSL postrun acceptance remains
authoritative because mirrored artifacts can keep WSL absolute paths.

## Preserved Guarantees

- Generic core must not contain CVRP/VRP/warehouse-specific scheduler,
  target-intent, launcher-lifecycle, mechanism-evidence, or runtime-pressure
  exceptions.
- Raw calibration rows, BKS data, case-level problem facts, LLM prose, prompt
  text, runtime feedback prose, and branch-lesson prose stay out of
  `DecisionFeatures`.
- Candidate crashes, invalid outputs, telemetry guard failures, hard negative
  evidence, verification failures, and actionable comparative runtime
  regressions remain fail-closed.
- Problem-owned declarations define runtime model, effect scale, pairing
  validity, practical delta, and readiness diagnostics; generic consumers use
  normalized deterministic views.
- Status docs should replace stale facts rather than append chronology.

## Pointers

- Architecture: `scion/design/scion-architecture-v3.md`
- Task source: `scion/TASK.md`
- Current basis audit:
  `scion/reports/v04-task-basis-alignment-audit-20260629.md`
- Framework repair design:
  `scion/design/v0.4-effective-research-repair-design.md`
- Postrun/readiness port design:
  `scion/design/v0.4-postrun-readiness-and-opportunity-ports.md`
- v0.4 planning:
  `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`
- Sparse milestone index: `scion/docs/status/v0.4-history.md`
- Detailed experiment evidence: `scion/docs/experiments/v0.4/`
- Audit basis:
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`
