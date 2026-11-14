# CVRP Successor45 Repair Placement Tournament Postrun

Date: 2026-07-07

## Scope

Successor45 tested `bounded_repair_placement_tournament`, a CVRP-owned
destroy/repair placement mechanism. It compares the normally repaired
candidate against one alternate completed placement for the same removed
customer set, before downstream VNS and acceptance.

This was not a new VRP solver and did not change generic Scion protocol,
decision, scheduler, or runtime boundaries.

## Run

- Root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor45-repair-placement-tournament-server-claw-2r-gpt55-2r-gpt55-20260707T091750Z-claw`
- Launcher commit: `a0df42bf`
- Environment: server-local conda `claw`
- Model: local `gpt-5.5`
- Resume source: successor44d
- Status: `finished`, valid, complete, postrun-ready
- Effective rounds: 2 / 2
- Proposal-quality blocks: 0
- Telemetry failed experiments: 0
- Model calls: 7, all `gpt-5.5`
- Formal candidates: 1

Postrun failures: none.

## Solver Evidence

Postrun summary:

- Total experiments: 2
- Screening pass rate: 0.0
- Champion promotions: 0
- Screening pair W/L/T: `40/31/9`
- Screening case W/L/T: `8/4/8`

Final branch-card expanded evidence:

- Tier: `quality_regression`
- Expanded effect: median delta `-2.75`, CI `[-6.5, 3.25]`
- Expanded case-gate W/L/T: `5/4/3`
- Runtime confidence: `low_cached_champion`
- Runtime model: `budget_exhausting`
- Runtime ratio median: `1.014011419370819`

Expanded case medians:

- Positive: A-n64-k9 `+10.0`, A-n80-k10 `+4.5`, B-n67-k10 `+2.0`,
  E-n101-k14 `+8.5`, X-n110-k13 `+1.5`
- Negative: E-n101-k8 `-6.0`, P-n76-k4 `-8.5`, P-n101-k4 `-12.0`,
  CMT3 `-6.0`
- Protected cases: CMT2 `-3.5`, CMT4 `-7.0`

The mechanism is not a long-run candidate.

## Mechanism Telemetry

The candidate did activate and showed local mechanism effect:

- `bounded_repair_placement_tournament` runtime observed in 48 / 48 pairs
- mechanism iterations observed in 48 / 48 pairs
- positive phase-improvement or best-delta fields in 47 / 48 pairs
- telemetry guard passed with no warnings or failures
- `mechanism_contract_status=observed_positive_effect`

The local pre-VNS signal did not preserve final total-distance quality.

## Trace Audit

The trace audit found no evidence that the agent was starved of core context:

- target-intent prompt: 21 / 21 sections full
- hypothesis prompt: 28 full, 1 truncated `hypothesis_target_intent_preflight`
  section
- code prompt: 28 / 28 sections full
- code prompt included the target files and integration files
- v3 boundary constraints, CVRP lexicographic objective semantics, CMT2/CMT4
  protection requirements, and target-intent binding were visible

The proposal and patch stayed inside the CVRP-owned solver-design boundary.
The patch touched only:

- `policies/baseline_modules/destroy_repair.py`
- `policies/baseline_modules/scheduler.py`

## Design Finding

The failure is mostly mechanism quality, not framework or model-call failure.

The tournament makes a local repair-placement comparison, but this local
pre-VNS improvement is not a reliable proxy for final ALNS/VNS trajectory
quality. It also has a code-quality weakness: the alternate repair uses the
main RNG stream, so even a rejected alternate repair can change downstream
stochastic trajectory. That makes the no-op condition less clean and makes
pre-VNS telemetry easier to overinterpret.

The CMT2/CMT4 protection plan protected feasibility and route-count semantics,
but did not protect final total-distance outcomes.

## Decision

Treat unchanged `bounded_repair_placement_tournament` as reviewed/default-avoid
for v0.4:

- no long-run
- no threshold tuning
- no same-mechanism repair-placement tournament follow-up
- no promotion claim from pre-VNS local deltas

The next CVRP optimization slot should clean-fork to a materially different
problem-owned causal path. Keep:

- exact `material_difference.changed_dimensions` / `contrast` / `evidence`
  schema
- CMT2/CMT4 priority-case evidence or explicit caveat
- local selector/filter/tournament telemetry separated from final protocol
  total-distance evidence
- v3 boundary: CVRP semantics stay in CVRP-owned guidance/problem layers
