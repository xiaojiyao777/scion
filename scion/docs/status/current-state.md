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
- The latest CVRP evidence is still negative as a solver result. Repeated
  `route_merge_repair` absorption/guarded variants either produced zero
  objective effect or mixed/regressive evidence. Scion can now continue and
  reject those branches with evidence, but it has not yet escaped the
  low-effect route-merge loop.
- CVRP provider guidance has therefore been changed to stop defaulting to
  another route-merge absorption/guarded-v2 follow-up. A new route-merge branch
  must name a new causal path beyond tested local absorption; otherwise the
  proposal should pivot to another problem-owned solver-design lever such as
  construction diversity, destroy selection, local-search move scheduling,
  acceptance/temperature policy, or stable algorithm entrypoint integration.
- Rejected default directions remain broad VNS removal, pure ALNS/no-polish,
  simple initial-VNS disablement, raw cadence-2, recent-best/stall gating,
  fixed early-8, tested share70 cap/rescue variants, and unchanged route-merge
  absorption/guarded variants.
- Focused tests now cover the CVRP route-merge pivot guidance in both provider
  text and live prompt payload assembly. The next proof must be a WSL
  target-intent/proposal field check showing that the agent actually pivots or
  explicitly justifies a genuinely new route-merge causal path.

## Active Work

- No LLM campaign is currently running.
- Latest WSL artifacts are synced back to the server under
  `/home/clawd/research/scion-experiments/`.
- Latest post-repair CVRP branch-card transfer artifacts are synced back to:
  `/home/clawd/research/scion-experiments/v04-cvrp-routemerge-branchcard-transfer-agentic-2r-9193d4e-20260618T021452Z`.
- WSL campaign launches must set
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`. Without
  it, Python may import stale Scion core modules from
  `/home/xjy-ubuntu/projects/scion/scion` while reading problem files from the
  synchronized repo.

## Next Actions

1. Run a short WSL CVRP target-intent/proposal field check from the repaired
   provider guidance. Acceptance: the live traces either pivot away from
   route-merge absorption or explicitly justify a new route-merge causal path
   that is not guarded-v2 / pressure-material-gain absorption.
2. If a natural CVRP run hits `EXPAND_SCREENING`, inspect the field artifact for
   populated branch-card evidence. Focused tests already cover the repaired
   code path, but the `9193d4e` field run only exercised `CONTINUE_EXPLORE`.
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
- WSL reference docs:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `RSYNC_PATHS.md`.
