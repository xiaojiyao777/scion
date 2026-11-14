# CVRP successor46b postrun: best-solution activation contract repair

Date: 2026-07-08

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor46b-best-solution-activation-contract-repair-server-claw-2r-gpt55-2r-gpt55-20260707T150022Z-claw`

## Status

- Run status: valid / complete / postrun-ready.
- Stop reason: `max_rounds_exhausted`.
- Requested and completed rounds: 2 / 2.
- Model: local `gpt-5.5`.
- Current-run LLM calls: 7 total, all successful.
- Proposal/model/telemetry/postrun failures: none.
- Postrun readiness: ready.

## Result

Successor46b improved the successor46 activation contract but did not produce
promotion-grade solver evidence.

- Row 1: 48/48 valid pairs, pair W/L/T `8/4/36`, case W/L/T `2/0/10`,
  median delta `0.0`, CI `[0.0, 0.5]`.
- Row 2: 64/64 valid pairs, pair W/L/T `12/6/46`, case W/L/T `3/0/13`,
  median delta `0.0`, CI `[0.0, 1.0]`.
- Aggregate pair W/L/T: `20/10/82`.
- Aggregate case W/L/T: `5/0/23`.
- MDE: `9.9`.
- Rows at or above MDE: `0`.
- Max median delta: `0.0`.
- Max effect/MDE ratio: `0.0`.

This is weak-positive pair/case noise, not a long-run candidate. Both CI highs
are far below the 9.9 MDE.

## Mechanism Evidence

The repaired mechanism did activate, unlike successor46 row 1.

- Row 1 mechanism runtime observed in 29/48 candidate runs.
- Row 1 positive mechanism best-delta observed in 11/29 activated runs.
- Row 2 mechanism runtime observed in 41/64 candidate runs.
- Row 2 positive mechanism best-delta observed in 15/41 activated runs.
- Runtime ratio median was near neutral, about `1.001` and `1.003`.
- Candidate and champion failed pairs were both zero.

The evidence says the mechanism was measured but too weak to change the final
distribution. It does not support another same-line solver slot.

## Protected Cases

The formal screening set included CMT2/CMT4 priority coverage.

- CMT2 stayed unsafe: both rows had median delta `-3.5` with pair deltas
  `[-23, -7, 0, 0]`.
- CMT4 was neutral: both rows tied all measured seeds.
- Raw pair telemetry showed no mechanism phase on CMT4 seeds, so CMT4 is not
  mechanism-level protection evidence; it is an outcome tie.

## Trace Audit

A delegated read-only trace audit reviewed all 7 current-run LLM calls:

1. `hypothesis_target_intent` correctly selected
   `best_solution_ruin_recreate_intensification_activation_repair`.
2. `hypothesis` produced the right contract, including RNG isolation,
   rejected-cause telemetry, final post-VNS effect, and CMT2/CMT4 obligations.
3. Tool selection read branch state.
4. Tool selection read a compact target preview.
5. Tool selection read `policies/baseline_algorithm.py`.
6. Tool selection stopped without reading the successor46 original patch.
7. Code generation had full source visibility and produced a runnable patch.

The failure was not provider, target-binding, or code-prompt truncation. The
code implementation only partially satisfied the hypothesis contract: it used a
child RNG for ruin/recreate attempts and improved activation, but collapsed
`rejected_no_improvement`, `rejected_infeasible`, `rejected_route_count`, and
`budget_stopped` into generic `accepted=0` telemetry. It also relied on phase
best-delta/improvement counters rather than explicit accepted/new-best update
attribution.

## Decision

Park `best_solution_ruin_recreate_intensification_activation_repair` as solver
evidence for v0.4.

Do not long-run, threshold-tune, or create a successor46c solver follow-up. If
this line is revisited later, it should be telemetry hygiene only, not a solver
experiment slot. The next CVRP optimization slot should be a materially
different CVRP-owned clean fork with final objective attribution and CMT2/CMT4
priority coverage.
