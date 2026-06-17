# Scion v0.4 Current State

Last updated: 2026-06-17

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
  opportunities and carry candidates through repaired formal screening without
  infrastructure failures.
- Rejected default directions remain: broad VNS removal, pure ALNS/no-polish,
  simple initial-VNS disablement, raw cadence-2, recent-best/stall gating, and
  fixed early-8 as a production default.
- Accepted current lesson: scheduler-owned adaptive embedded-VNS share70
  refinement was useful for steering and diagnostics, but the tested variants
  are not production solver improvements.
- Latest agentic field check from commit `7e312a7` is positive research-loop
  evidence: target-intent, hypothesis, tool-selection, and code all stayed on
  `policies/baseline_modules/scheduler.py` /
  `adaptive_embedded_vns_share70_trigger`; formal screening completed `32/32`
  valid pairs with `0` failures; Decision chose `expand_screening` for
  `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`.
- The generated hard share70 cap is not accepted as a production solver
  improvement. It produced pair W/L/T `16/11/5`, median candidate-minus-champion
  delta `-0.5`, mean `+2.0`, CMT4 case-level win, M-n200 neutrality, and an
  X-n110 tail loss (`+116`) that prevents promotion.
- Follow-up no-LLM diagnostics added direct mechanism effect telemetry and
  rejected share70 floor/hardcap/softrescue/tail6 as X-n110 fixes. X-n110 30s
  seed 43 keeps the `+116` tail loss across those variants.
- Post-share70 target-selection field check from commit `7557a15` accepted the
  guidance repair in the field. Target-intent selected
  `policies/baseline_modules/destroy_repair.py` / `route_merge_repair`, not
  another scheduler/share70 variant. Formal screening was valid (`32/32`, `0`
  failed pairs) and Decision chose `expand_screening` for low-SNR divergent
  evidence: pair W/L/T `10/3/19`, median delta `0.0`, favorable mean delta
  `+1.406`, no case-level losses, and X-n110/CMT4/M-n200 neutral.
- `route_merge_repair` is not promoted, but it is now the active CVRP branch
  lesson to continue. It has direct mechanism telemetry under its own phase id
  and should get same-mechanism follow-up before opening another unrelated
  scheduler target.

## Active Work

- No LLM campaign is currently running.
- Latest WSL artifacts are synced back to the server under
  `/home/clawd/research/scion-experiments/`.
- Latest CVRP share70 cap/tail diagnostic artifacts are synced back to the
  server experiment root.

## Next Actions

1. Continue CVRP on the `route_merge_repair` branch: inspect activation/effect
   rows, explain why A/B/E improve while CMT2/P are mixed, and refine trigger or
   acceptance conditions without touching generic gates.
2. Keep share70 as a rejected scheduler lesson. Do not repeat floor, hardcap,
   softrescue, or tail6 unless a future scheduler hypothesis is materially
   different and explains the X-tail mechanism.
3. Keep a later warehouse repeat available to test whether champion `v2`
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
- WSL reference docs:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `RSYNC_PATHS.md`.
