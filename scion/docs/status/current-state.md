# Scion v0.4 Current State

Last updated: 2026-06-18

This is the short operational resume point. It is not an append-only run log.
Detailed evidence belongs in `scion/docs/experiments/v0.4/`; curated milestone
history belongs in `scion/docs/status/v0.4-history.md`.

## Operating Frame

- Active branch: `codex/v04-evidence-repair-plan`.
- Governing design: `scion/design/scion-architecture-v3.md`.
- v0.4 closeout goal: make Scion stable enough that warehouse can recover
  continuous useful research and CVRP/VRP can produce evidence-backed solver
  hypotheses before v0.5 broad experiment matrices.
- Current repair posture: do not add broad budgets, truncation, compression, or
  generic gate tightening. Keep CVRP/warehouse semantics in problem-owned
  layers and keep generic `DecisionFeatures` problem-neutral.

## Current Conclusions

Warehouse:

- Warehouse recovery checkpoint is accepted. The short validation-transfer
  acceptance-contract WSL gate from commit `ce5d884` completed validly, reached
  screening/validation/frozen holdout, and promoted champion `v2`.
- This restores a useful warehouse research path, but it is not yet a long-run
  continuous-promotion proof.
- Remaining caveat: split-preserving cost-compression effects still need cleaner
  measurement interpretation, because diagnostics can over-read zero
  `split_delta_sum` even when the declared useful effect is cost compression.

CVRP/VRP:

- Framework plumbing is no longer the main known CVRP blocker for the current
  slice. Target-intent/provider guidance injection is field-verified, formal
  screening is completing with complete evidence, and branch-card evidence
  retention is repaired for the tested paths.
- The older CVRP route-merge evidence remains negative as a solver result.
  Repeated
  `route_merge_repair` absorption/guarded variants either produced zero
  objective effect or mixed/regressive evidence. Scion can now continue and
  reject those branches with evidence.
- The provider-guidance pivot is now field-accepted. The `ff2e652` WSL
  target-intent/proposal check escaped route-merge and generated
  `demand_slack_regret_insertion` in `destroy_repair.py`, with complete formal
  screening and direct mechanism telemetry.
- The new CVRP candidate is not a solver improvement yet. Screening selected
  `expand_screening` with pair W/L/T `13/11/8`, case W/L/T `3/2/3`, median
  delta `0.0`, and losses on `CMT2`/`CMT4`. This is positive research-loop
  behavior and an active marginal branch, not a promotion.
- Campaign reopen/continuation state has been repaired for the next field
  check: reopening a campaign now restores the persisted current champion,
  active branches, mechanism/evidence summaries, and existing branch workspace
  mapping needed for same-mechanism continuation.
- Rejected default directions remain broad VNS removal, pure ALNS/no-polish,
  simple initial-VNS disablement, raw cadence-2, recent-best/stall gating,
  fixed early-8, tested share70 cap/rescue variants, and unchanged route-merge
  absorption/guarded variants.
- Next CVRP work should continue the same
  `demand_slack_regret_insertion` mechanism to reduce `CMT2`/`CMT4` losses
  while preserving A/E/P gains and M/X neutrality.

## Active Work

- No LLM campaign is currently running.
- Latest WSL artifacts are synced back to the server under
  `/home/clawd/research/scion-experiments/`.
- Latest CVRP route-merge pivot field-check artifacts are synced back to:
  `/home/clawd/research/scion-experiments/v04-cvrp-route-merge-pivot-guidance-agentic-1r-gpt55-20260618T031817Z-claw`.
- WSL campaign launches must set
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`. Without
  it, Python may import stale Scion core modules from
  `/home/xjy-ubuntu/projects/scion/scion` while reading problem files from the
  synchronized repo.

## Next Actions

1. Run a same-mechanism CVRP follow-up on `demand_slack_regret_insertion`.
   Acceptance: the live traces keep the mechanism lineage visible, target the
   `CMT2`/`CMT4` regressions, and preserve A/E/P gains plus M/X neutrality.
2. If this branch expands again, inspect the field artifact for branch-card
   evidence transfer into the next target-intent/hypothesis prompts.
3. Clean up status/projection polish separately: abandoned branch DB rows retain
   mechanism/evidence, but their history-card projection can still drop compact
   status fields; in-flight `run_status.json` also remains too coarse during
   long formal screening.
4. Keep a later warehouse repeat available to test whether champion `v2`
   enables continuous follow-on improvement.

## Key Evidence

- Core reset: `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`.
- Warehouse recovery:
  `scion/docs/experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-postrun-20260617.md`.
- CVRP current negative route-merge frontier:
  `scion/docs/experiments/v0.4/v04-cvrp-routemerge-guarded-agentic-1r-f3d634c-postrun-20260618.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-routemerge-transfer-agentic-resume1r-af5b5a2-postrun-20260618.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-routemerge-branchcard-transfer-agentic-2r-9193d4e-postrun-20260618.md`.
- CVRP provider pivot repair:
  `scion/docs/experiments/v0.4/v04-cvrp-route-merge-pivot-guidance-repair-20260618.md`.
- CVRP provider pivot field check:
  `scion/docs/experiments/v0.4/v04-cvrp-route-merge-pivot-guidance-agentic-1r-ff2e652-postrun-20260618.md`.
- Campaign reopen continuation repair:
  `scion/docs/experiments/v0.4/v04-campaign-reopen-active-branch-restore-repair-20260618.md`.
- WSL reference docs:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `RSYNC_PATHS.md`.
