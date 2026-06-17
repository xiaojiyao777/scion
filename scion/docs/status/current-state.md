# Scion v0.4 Current State

Last updated: 2026-06-17

This file is the short operational snapshot for resuming work. It should not be
used as an append-only experiment log. Detailed run facts live in
[`../experiments/v0.4/`](../experiments/v0.4/); older milestone notes live in
[`v0.4-history.md`](v0.4-history.md).

## Operating Frame

- Active branch: `codex/v04-evidence-repair-plan`.
- Governing design: [`../../design/scion-architecture-v3.md`](../../design/scion-architecture-v3.md).
- v0.4 closeout goal: make Scion stable enough that warehouse can recover
  continuous useful research and CVRP/VRP can produce evidence-backed solver
  hypotheses before v0.5 broad experiment matrices.
- Do not use broad budgets, truncation, compression, or generic gate tightening
  as the next repair. Keep CVRP/warehouse semantics in problem-owned layers;
  keep generic `DecisionFeatures` problem-neutral.

## Current Conclusions

Warehouse:

- The short validation-transfer acceptance-contract WSL gate completed cleanly
  from commit `ce5d884` and is accepted as positive warehouse recovery
  evidence:
  [`../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-postrun-20260617.md`](../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-postrun-20260617.md).
- The run reached screening, validation, frozen holdout, and promoted champion
  `v2`: `6/6` effective rounds, `8` Protocol rows, stage counts
  `screening=5`, `validation=2`, `frozen=1`, `1` promotion, wrapper exit `0`,
  and run validity `valid`.
- The promoted `pack_compatible_vehicles` operator is a split-preserving
  cost-compression mechanism. It matched the repaired contract by computing
  `split_delta == 0`, `cost_delta > 0`, exporting diagnostics, bounding
  enumeration, and no-oping when no candidate qualifies.
- This is a warehouse recovery checkpoint, not a final continuous-promotion
  proof. The remaining measurement caveat is that diagnostics still emit
  `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC` for zero `split_delta_sum` even when the
  declared useful effect is cost compression.

CVRP/VRP:

- Scion can carry CVRP candidates through the repaired framework, but it has
  not yet produced effective CVRP research against canonical ALNS+VNS.
- Broad VNS removal, pure ALNS/no-polish, and size70/two-opt as broad
  replacements are rejected by no-LLM evidence.
- The deep `initial_vns_disabled` matrix rejected simple initial-VNS
  disablement: `160/160` rows, overall W/L/T `25/51/4`, median delta `+2.0`.
  Objective probes show the skipped initial work mostly shifts pressure into
  embedded VNS rather than creating stable ALNS benefit.
- CVRP scheduler-local budget/iteration instrumentation is locally implemented
  and accepted:
  [`../experiments/v0.4/v04-cvrp-scheduler-iteration-telemetry-repair-20260617.md`](../experiments/v0.4/v04-cvrp-scheduler-iteration-telemetry-repair-20260617.md).
  It fixes construction/initial-VNS phase accounting, adds `alns_core` timing,
  and records bounded `solver_algorithm_alns_iteration_trace`.
- The compact WSL instrumentation matrix completed `60/60` no-LLM rows and
  accepted the telemetry path:
  [`../experiments/v0.4/v04-cvrp-scheduler-instrumentation-compact-wsl-875dc83-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-scheduler-instrumentation-compact-wsl-875dc83-postrun-20260617.md).
  Disabling embedded VNS increases ALNS iterations from mean `4.0` to `22.4`,
  but is still worse or tied overall (`2/8/10`, mean delta `+17.3`). Pure
  ALNS/no-polish is worse (`2/18/0`, mean delta `+35.6`). Do not launch a long
  agentic CVRP campaign from a broad VNS-removal idea.
- A narrow adaptive embedded-VNS scheduling probe is locally implemented and
  accepted:
  [`../experiments/v0.4/v04-cvrp-adaptive-embedded-vns-probe-repair-20260617.md`](../experiments/v0.4/v04-cvrp-adaptive-embedded-vns-probe-repair-20260617.md).
  `adaptive_embedded_vns_cadence4` keeps initial VNS, runs embedded VNS every
  fourth ALNS iteration, and still polishes candidates that already improve
  current/best after repair. Canonical behavior is unchanged by default.
- The compact WSL adaptive matrix completed `40/40` no-LLM rows:
  [`../experiments/v0.4/v04-cvrp-adaptive-embedded-vns-compact-wsl-dd5b17a-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-adaptive-embedded-vns-compact-wsl-dd5b17a-postrun-20260617.md).
  It is accepted as mechanism evidence and rejected as a production candidate:
  whole-matrix embedded-VNS runtime share dropped from `0.651` to `0.361`, mean
  ALNS iterations rose from `4.0` to `8.35`, but paired quality was still worse
  overall (`4/7/9`, mean delta `+6.95`). Cadence-only skipping is too blunt for
  a long CVRP LLM campaign.
- Local adaptive-trigger variants are implemented and accepted for the next
  no-LLM matrix:
  [`../experiments/v0.4/v04-cvrp-adaptive-trigger-variants-repair-20260617.md`](../experiments/v0.4/v04-cvrp-adaptive-trigger-variants-repair-20260617.md).
  The selectable mechanisms are `adaptive_embedded_vns_cadence2` and
  `adaptive_embedded_vns_improve_only`.
- The compact WSL adaptive-trigger matrix completed `80/80` no-LLM rows:
  [`../experiments/v0.4/v04-cvrp-adaptive-trigger-compact-wsl-eddaf8c-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-adaptive-trigger-compact-wsl-eddaf8c-postrun-20260617.md).
  `adaptive_embedded_vns_cadence2` is accepted as a proposal-context
  opportunity source, not as a production default: embedded-VNS share dropped
  from `0.653` to `0.528`, ALNS iterations rose from `4.0` to `6.0`, median
  paired delta stayed `0.0`, and mean delta was `+1.8`. The next CVRP agent
  task should refine cadence-2 using objective/budget/best-update triggers,
  especially preserving `CMT2` gains while avoiding `P-n76-k4` losses.
- The cadence-2 opportunity is now wired into CVRP solver-design hypothesis
  context as proposal-only guidance:
  [`../experiments/v0.4/v04-cvrp-adaptive-trigger-proposal-context-repair-20260617.md`](../experiments/v0.4/v04-cvrp-adaptive-trigger-proposal-context-repair-20260617.md).
  The repair also makes hypothesis context consume the problem-owned
  solver-design prompt provider, matching the existing code-context path.
- The first post-repair CVRP agentic `4R` WSL run completed with wrapper
  `exit_code=0`, `4/4` effective screening rounds, `4` Protocol rows, `3`
  formal candidate artifacts, `19` `gpt-5.5` traces, and no infra failures:
  [`../experiments/v0.4/v04-cvrp-adaptive-trigger-agentic-4r-7104928-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-adaptive-trigger-agentic-4r-7104928-postrun-20260617.md).
  It is accepted as positive CVRP research-loop behavior evidence: Scion formed
  a depth-3 `route_limit_aware_regret_repair` branch, continued weak screening
  signal in the same mechanism family, retained the active branch as marginal,
  and abandoned a loss-heavy `local_search.py` clean fork.
- The same postrun found that the intended cadence-2 adaptive embedded-VNS
  opportunity text was absent from live hypothesis prompts. The prompt engine
  used fallback solver-design guidance because agentic context sanitization
  removed the provider object and the resolver did not recover from
  `solver_design_prompt_provider_ref`. The prompt-provider-ref repair and
  cadence-specific guidance wording repair are now accepted by focused tests
  and field-verified for final hypothesis rendering.
- The targeted post-repair CVRP agentic `1R` WSL run completed with wrapper
  `exit_code=0`, run validity `valid`, `1` effective screening round, `1`
  formal candidate artifact, `32/32` screening pairs, `0` failed pairs, and
  high-confidence runtime evidence:
  [`../experiments/v0.4/v04-cvrp-cadence2-providerref-agentic-1r-6c842f6-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-cadence2-providerref-agentic-1r-6c842f6-postrun-20260617.md).
  It verified that the final `hypothesis` trace contains cadence-2 opportunity
  text, but the earlier `hypothesis_target_intent` trace does not. The agent
  selected `route_merge_savings_vns` in `local_search.py`, stayed bound to that
  target, and produced an `active_marginal` branch rather than a cadence-trigger
  refinement.
- The current CVRP prompt steering fault is therefore precise: problem-owned
  solver-design opportunity guidance reaches the final hypothesis call too
  late to steer target/action/mechanism selection. A local proposal-layer
  repair now exposes solver-design guidance to `hypothesis_target_intent`
  whenever solver-design is targetable. This remains proposal-only and outside
  `DecisionFeatures`.

## Active Work

- No LLM campaign is currently running.
- Local code has a focused target-intent prompt repair and regression test.
  WSL must be fast-forwarded after commit/push before the next CVRP agentic
  rerun.
- The latest CVRP no-LLM and agentic artifacts are synced back to the server.

## Next Actions

1. Commit and push the target-intent solver-design guidance repair, fast-forward
   WSL, then rerun a short targeted CVRP agentic campaign. First inspect the
   live `hypothesis_target_intent` trace for the cadence-2 opportunity text;
   only then interpret the selected mechanism.
2. Preserve the `route_limit_aware_regret_repair` branch evidence as a viable
   CVRP same-mechanism research line, but do not confuse it with cadence-2
   adaptive-VNS trigger evidence.
3. Keep a later warehouse repeat available to test whether champion `v2`
   enables continuous follow-on improvement.

## Evidence Index

Core audits and plan:

- [`../../reports/v04-core-framework-review-20260611.md`](../../reports/v04-core-framework-review-20260611.md)
- [`../../reports/v04-core-framework-code-review-20260611.md`](../../reports/v04-core-framework-code-review-20260611.md)
- [`../../design/v0.5-evidence-uplift-roadmap.md`](../../design/v0.5-evidence-uplift-roadmap.md)
- [`../planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`](../planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md)

Warehouse current evidence:

- [`../experiments/v0.4/v04-warehouse-validation-transfer-acceptance-contract-repair-20260617.md`](../experiments/v0.4/v04-warehouse-validation-transfer-acceptance-contract-repair-20260617.md)
- [`../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-launch-20260617.md`](../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-launch-20260617.md)
- [`../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-postrun-20260617.md`](../experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-postrun-20260617.md)

CVRP current evidence:

- [`../experiments/v0.4/v04-cvrp-mechanism-matrix-and-size70-repair-20260617.md`](../experiments/v0.4/v04-cvrp-mechanism-matrix-and-size70-repair-20260617.md)
- [`../experiments/v0.4/v04-cvrp-focused5-mechanism-wsl-70dfc53-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-focused5-mechanism-wsl-70dfc53-postrun-20260617.md)
- [`../experiments/v0.4/v04-cvrp-p76-deepseed-wsl-14c2a34-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-p76-deepseed-wsl-14c2a34-postrun-20260617.md)
- [`../experiments/v0.4/v04-cvrp-vns-variant-telemetry-repair-20260617.md`](../experiments/v0.4/v04-cvrp-vns-variant-telemetry-repair-20260617.md)
- [`../experiments/v0.4/v04-cvrp-vns-variant-matrix-wsl-6d742c6-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-vns-variant-matrix-wsl-6d742c6-postrun-20260617.md)
- [`../experiments/v0.4/v04-cvrp-initial-vns-deepseed-wsl-6d742c6-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-initial-vns-deepseed-wsl-6d742c6-postrun-20260617.md)
- [`../experiments/v0.4/v04-cvrp-scheduler-iteration-telemetry-repair-20260617.md`](../experiments/v0.4/v04-cvrp-scheduler-iteration-telemetry-repair-20260617.md)
- [`../experiments/v0.4/v04-cvrp-scheduler-instrumentation-compact-wsl-875dc83-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-scheduler-instrumentation-compact-wsl-875dc83-postrun-20260617.md)
- [`../experiments/v0.4/v04-cvrp-adaptive-embedded-vns-probe-repair-20260617.md`](../experiments/v0.4/v04-cvrp-adaptive-embedded-vns-probe-repair-20260617.md)
- [`../experiments/v0.4/v04-cvrp-adaptive-embedded-vns-compact-wsl-dd5b17a-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-adaptive-embedded-vns-compact-wsl-dd5b17a-postrun-20260617.md)
- [`../experiments/v0.4/v04-cvrp-adaptive-trigger-variants-repair-20260617.md`](../experiments/v0.4/v04-cvrp-adaptive-trigger-variants-repair-20260617.md)
- [`../experiments/v0.4/v04-cvrp-adaptive-trigger-compact-wsl-eddaf8c-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-adaptive-trigger-compact-wsl-eddaf8c-postrun-20260617.md)
- [`../experiments/v0.4/v04-cvrp-adaptive-trigger-proposal-context-repair-20260617.md`](../experiments/v0.4/v04-cvrp-adaptive-trigger-proposal-context-repair-20260617.md)
- [`../experiments/v0.4/v04-cvrp-adaptive-trigger-agentic-4r-7104928-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-adaptive-trigger-agentic-4r-7104928-postrun-20260617.md)
- [`../experiments/v0.4/v04-cvrp-cadence2-providerref-agentic-1r-6c842f6-postrun-20260617.md`](../experiments/v0.4/v04-cvrp-cadence2-providerref-agentic-1r-6c842f6-postrun-20260617.md)

WSL coordination:

- `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
- `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/RSYNC_PATHS.md`
