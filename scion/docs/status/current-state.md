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

- The framework can now steer CVRP agents to problem-owned solver-design
  opportunities and carry candidates through complete formal screening. This is
  not yet enough: v0.4 still needs one fresh proof that repaired branch evidence
  supports continuous CVRP follow-up.
- Rejected default directions remain broad VNS removal, pure ALNS/no-polish,
  simple initial-VNS disablement, raw cadence-2, recent-best/stall gating,
  fixed early-8, and tested share70 cap/rescue variants.
- The `f3d634c` WSL rerun field-verified route-merge target-intent guidance
  injection: target-intent, hypothesis, and code stayed on
  `policies/baseline_modules/destroy_repair.py` / `route_merge_repair`, all LLM
  traces used `gpt-5.5`, screening completed `32/32` valid pairs with `0`
  failures, and the candidate was correctly rejected as no-effect (`0/0/32`,
  zero objective deltas).
- The `af5b5a2` transfer run from copied campaign state is valid and useful but
  not a solver improvement. It produced a materially different
  `route_merge_repair` variant with direct mechanism effect in `19/32` pairs,
  but screening remained mixed (`7/7/18`, median total-distance delta `0.0`,
  mean `-0.28125`) and Decision stayed at `expand_screening`.
- The same transfer run exposed a framework continuity bug: non-terminal
  decisions such as `EXPAND_SCREENING` recorded metric/formal-candidate
  evidence but did not persist `direction`, `branch_mechanism_ids`, or compact
  `branch_evidence_summary` onto the branch card. This made an evaluated branch
  appear as an empty clean branch to later prompts.
- That branch-card evidence-retention bug is now repaired in
  `scion/scion/core/decision_finalizer.py` with a focused regression test in
  `scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py`.
- The `9193d4e` copied-campaign WSL field check after that repair completed
  validly (`2/2` effective protocol rounds, all `27` LLM traces on
  `gpt-5.5`). It did not naturally hit another `EXPAND_SCREENING` decision, so
  it is not a direct field verification of that repaired path. It did verify
  that later route-merge prompts can see prior branch lesson material and that
  the normal `CONTINUE_EXPLORE` branch card retains direction, mechanism id,
  evidence tier, telemetry-zero outcome, and not-promoted reason codes.
- The same run is still negative solver evidence: the first new route-merge
  candidate was abandoned as quality-regressive (`10/15/7` pair W/L/T), and the
  second remained active only as `active_no_effect` (`0/0/32`, zero objective
  effect). CVRP is therefore not closed; Scion can continue/reject
  evidence-backed route-merge branches, but it has not escaped the low-effect
  route-merge loop.
- WSL execution caveat: Scion campaign runs in WSL must set
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`. Without
  it, Python may import stale Scion core modules from
  `/home/xjy-ubuntu/projects/scion/scion` while reading problem files from the
  synchronized repo, invalidating prompt/runtime conclusions.

## Active Work

- No LLM campaign is currently running.
- Latest WSL artifacts are synced back to the server under
  `/home/clawd/research/scion-experiments/`.
- Latest valid CVRP transfer artifacts are synced back to:
  `/home/clawd/research/scion-experiments/v04-cvrp-routemerge-transfer-agentic-resume1r-af5b5a2-env-20260618T0130Z`.
- Latest post-repair CVRP branch-card transfer artifacts are synced back to:
  `/home/clawd/research/scion-experiments/v04-cvrp-routemerge-branchcard-transfer-agentic-2r-9193d4e-20260618T021452Z`.

## Next Actions

1. Stop rerunning route-merge absorption variants unchanged. The next CVRP
   branch should either pivot to a materially different problem-owned
   solver-design opportunity or first improve proposal opportunity diagnostics
   enough to justify spending another branch slot on `route_merge_repair`.
2. If a natural CVRP run hits `EXPAND_SCREENING`, inspect the field artifact for
   populated branch-card evidence; focused tests already cover the repaired
   code path, but the `9193d4e` field run only exercised `CONTINUE_EXPLORE`.
3. Clean up status/projection polish separately: abandoned branch DB rows retain
   mechanism/evidence, but their history-card projection can still drop compact
   status fields; in-flight `run_status.json` also remains too coarse during
   long formal screening.
4. Keep share70 as a rejected scheduler lesson. Do not repeat floor, hardcap,
   softrescue, or tail6 unless a future scheduler hypothesis is materially
   different and explains the X-tail mechanism.
5. Keep a later warehouse repeat available to test whether champion `v2`
   enables continuous follow-on improvement.

## Key Evidence

- Core reset: `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`.
- Warehouse recovery:
  `scion/docs/experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-postrun-20260617.md`.
- CVRP share70 no-LLM diagnostic:
  `scion/docs/experiments/v0.4/v04-cvrp-embedded-vns-share-trigger-focus-20260617.md`.
- CVRP share70 agentic field check:
  `scion/docs/experiments/v0.4/v04-cvrp-share70-agentic-1r-7e312a7-postrun-20260617.md`.
- CVRP share70 cap/tail diagnostics:
  `scion/docs/experiments/v0.4/v04-cvrp-share70-cap-tail-diagnostics-20260617.md`.
- CVRP post-share70 target-selection field check:
  `scion/docs/experiments/v0.4/v04-cvrp-post-share70-targetselect-agentic-1r-7557a15-postrun-20260617.md`.
- CVRP route-merge guarded field failure:
  `scion/docs/experiments/v0.4/v04-cvrp-routemerge-guarded-agentic-1r-71666ae-field-failure-20260618.md`.
- CVRP route-merge target-intent guidance injection repair:
  `scion/docs/experiments/v0.4/v04-cvrp-route-merge-target-intent-guidance-injection-repair-20260618.md`.
- CVRP route-merge guarded post-repair field check:
  `scion/docs/experiments/v0.4/v04-cvrp-routemerge-guarded-agentic-1r-f3d634c-postrun-20260618.md`.
- CVRP route-merge transfer field check and branch-card repair:
  `scion/docs/experiments/v0.4/v04-cvrp-routemerge-transfer-agentic-resume1r-af5b5a2-postrun-20260618.md`.
- CVRP route-merge post-branch-card-repair field check:
  `scion/docs/experiments/v0.4/v04-cvrp-routemerge-branchcard-transfer-agentic-2r-9193d4e-postrun-20260618.md`.
- WSL reference docs:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `RSYNC_PATHS.md`.
