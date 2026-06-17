# Warehouse Validation-Transfer Contract 6R Postrun

Date: 2026-06-17

## Verdict

Accepted as a short field gate for the warehouse validation-transfer acceptance
contract and as positive v0.4 warehouse recovery evidence. The run completed
cleanly, reached screening, validation, frozen holdout, and promoted a new
champion.

This is not yet a broad continuous-promotion claim. It is one production `6R`
cell, and the promoted mechanism exposes a remaining measurement-declaration
semantic issue: the candidate is a split-preserving cost-compression operator,
so `split_delta_sum` stays zero while `cost_delta_sum` is positive. Scion
correctly allowed the candidate under the repaired contract, but still records
`TELEMETRY_EFFECT_ZERO_DIAGNOSTIC` for the zero split field.

## Run

- Commit: `ce5d884`
- Cell: `rep01/full_context`
- Problem: warehouse production
- Rounds: `6`
- Model: WSL-local `gpt-5.5`
- Measurement governance: `on`
- Early stop: disabled
- Stage drain / retry / session timeout overrides: none
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z`
- Launch report:
  `scion/docs/experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-launch-20260617.md`

## Completion

- Wrapper status: `finished`
- Wrapper exit code: `0`
- Campaign validity: `valid`
- Stopped reason: `max_rounds_exhausted`
- Effective rounds completed: `6/6`
- Protocol metric rows: `8`
- Stage counts: `screening=5`, `validation=2`, `frozen=1`
- Proposal quality blocks: `6`
- Verification-consumed failures: `0`
- Champion promotions: `1`
- Final champion: `v2`

Postrun acceptance artifacts:

- `postrun_acceptance/summaries/rep01_full_context.summary.json`
- `postrun_acceptance/research_efficiency/rep01_full_context.research_efficiency.v1.json`
- `postrun_acceptance/failures/rep01_full_context.failures.json`
- `rep01/full_context/campaign/artifacts/promotions/champion_v2_promotion_dossier.json`

## Promotion Chain

The promoted branch is `da6c4a81-5d6e-4a0b-ac39-ebfb2ff1a50f`, hypothesis
`5badd2e1-01f4-49fe-a9dd-93fcc521ddbe`.

The candidate created `operators/pack_compatible_vehicles.py` and registered a
bounded vehicle-level operator. Its executable policy matches the repaired
warehouse contract:

- group compatible low-utilization vehicles by region and vehicle category;
- cap candidate enumeration with bucket and group limits;
- compute `split_delta` and `cost_delta` before accepting a move;
- reject negative split deltas;
- accept split-preserving moves only when `split_delta == 0` and
  `cost_delta > 0`;
- return the original solution if no qualifying candidate exists;
- export `operator_diagnostics.pack_compatible_vehicles.*`.

Stage chain from the promotion dossier:

- Screening: `queue_validate`, median delta `375.0`, CI `[50.0, 1200.0]`,
  `7/0/9` case W/L/T over `16` cases, raw metrics
  `metrics/2668cb3d-5e7f-454a-91ae-c45b0af671e9.json`.
- Validation: `queue_frozen`, win rate `1.0`, median delta `0.0`, CI
  `[0.0, 1.0]`, raw metrics
  `metrics/ff951549-7775-4ac3-aaf5-8bfb2b555d29.json`.
- Frozen: `promote`, win rate `1.0`, median delta `37250.0`, CI
  `[25900.0, 51600.0]`, `4/0/0` case W/L/T and `12/0/0` pair W/L/T, raw
  metrics `metrics/0ab74c47-5700-40d8-b62a-3849413a22b8.json`.

Frozen runtime evidence is high confidence: champion cache hits `0`, runtime
pairs `12`, median runtime ratio `1.0119`, median runtime delta `239 ms`, and
runtime evidence status `sufficient`.

## Research Behavior

This run is materially healthier than the preceding failed warehouse gates.

- The first lineage, `67a6a89f-ba51-4c55-bfd6-621d195c5eb7`, received repeated
  proposal/code quality blocks for missing executable validation-transfer
  diagnostics, missing validation-transfer risk, or missing bounded acceptance.
  It was later parked after weak or negative screening evidence.
- The second lineage, `da6c4a81-5d6e-4a0b-ac39-ebfb2ff1a50f`, used the repaired
  constraints to produce a new bounded operator, progressed through screening
  and validation, then passed frozen holdout and promoted.
- Research-shape diagnostics report branch depths `9` and `5`, with no active
  branch left stuck after completion.
- The quality blocks were non-infra, pre-Protocol blocks. They consumed proposal
  attempts but did not create invalid protocol evidence.

The run therefore field-accepts the acceptance-contract repair as behavior and
research-loop evidence for warehouse. It also supports the user's desired v0.4
direction: filter bad proposals with problem-owned constraints, but do not use
generic budget cuts, prompt truncation, or meaningless gate tightening as a
substitute for research.

## Caveats

- This is a single `6R` cell, so it does not prove restored continuous
  promotion across long warehouse runs.
- The promoted mechanism is cost-only compression under a split-preserving
  guard. That is allowed by the repaired contract, but the telemetry diagnostics
  still emphasize `split_delta_sum == 0` and emit
  `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`. The next measurement-declaration repair
  should distinguish a declared cost-compression effect from a missing
  split-reduction effect.
- Screening and validation used some cached champion runtime evidence; frozen
  used fresh champion runtime and is the decisive promotion evidence.
- Proposal quality blocks remain frequent. They are now useful fail-closed
  feedback rather than an invalid zero-protocol-row blocker.

## Next Step

Warehouse does not need another immediate short repair gate from this result.
Keep this as a positive v0.4 warehouse recovery checkpoint, then continue with
the compact CVRP scheduler-instrumentation matrix before any longer agentic
CVRP campaign. A later warehouse repeat can test whether champion `v2` enables
continuous follow-on improvement.
