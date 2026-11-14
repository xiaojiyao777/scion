# CVRP Successor44c Attribution Contract Repair Postrun

Date: 2026-07-07

## Status

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor44c-attribution-contract-repair-server-claw-2r-gpt55-20260707T051421Z-claw`
- Launcher commit: `2bcf831a`
- Runner: server-local `claw`, local `gpt-5.5`
- Completion preflight: passed, chat HTTP `200`, classification `healthy`.
- Outcome: valid, complete, postrun-ready.
- Stop reason: `max_rounds_exhausted`.
- Effective protocol rows: 2 screening rows, 0 validation, 0 frozen.
- Formal candidate artifacts: 1. The two screening rows are the original screen
  and expanded screen for the same candidate, not two independent code
  hypotheses.
- LLM calls: 7 total: target-intent 1, hypothesis 1, tool-selection 4, code 1.
- Quality/model/telemetry/verification/postrun failures: 0.

## Contract Repair Verification

The CVRP-owned attribution contract repair worked. The hypothesis declared
activation/activity/budget telemetry plus formal per-case outcome evidence for
`post_vns_best_anchor_acceptance_guard`; it did not require direct
`expected_telemetry.effect`.

The generated patch placed the guard helper in
`policies/baseline_modules/acceptance.py` and kept
`policies/baseline_modules/scheduler.py` to import/call wiring. The candidate
recorded activation and phase runtime under the successor44 mechanism id, and
did not add successor44 `record_move(..., delta=..., best_improved=...)`
effect telemetry. Ordinary ALNS/VNS best/current-improving bookkeeping remained
ordinary ALNS/VNS bookkeeping.

This satisfies the intended v3 boundary: generic telemetry guard and Decision
logic stayed unchanged; successor44 interpretation stayed in CVRP-owned
proposal/static-quality/guidance layers.

## Screening Evidence

| row | pairs | pair W/L/T | raw pair median | raw pair mean | postrun median / CI | effect/MDE | decision | priority cases |
|---|---:|---:|---:|---:|---:|---:|---|---|
| original screen | 32/32 | 17/9/6 | +4.5 | +7.25 | +7.5 / [-1.0, 27.0] | 0.757576 | expand screening | CMT2, CMT4 |
| expanded screen | 48/48 | 28/15/5 | +1.5 | +6.3125 | +4.5 / [-0.5, 17.0] | 0.454545 | continue explore | CMT2, CMT4, A-n64, B-n63, X-n110 |

Postrun MDE remained `9.9`; the best postrun median was `+7.5`, so no row was
positive at MDE. The run is solver weak-positive/inconclusive, not
promotion-grade evidence.

Runtime was not a blocker: row 1 runtime median ratio was
`0.9977492778896655` with median delta `-55ms`; row 2 runtime median ratio was
`0.9947394808092698` with median delta `-129ms`.

## Case Signals

The protected cases split:

- CMT2 stayed positive: row 1 `3/1/0`, median `+8.5`; row 2 `3/1/0`, median
  `+7.0`.
- CMT4 stayed negative: both rows `0/2/2`, median `-6.0`.

Expanded screening also showed strong A-family signal and useful B/X signal,
but losses remained in B-n67, CMT3, CMT4, P-n101, and mixed E/P-family cases.
The signal is too uneven for a long run.

## Telemetry

The candidate activated the mechanism in every candidate run:

- row 1: iterations positive `32/32`, phase runtime positive `8/32`;
- row 2: iterations positive `48/48`, phase runtime positive `10/48`;
- direct effect fields were intentionally absent: `phase_improvement_counts`
  and `phase_best_delta` for the successor44 mechanism were positive `0`.

The generic telemetry guard passed because `effect_observation_required=false`,
but it still emitted a non-blocking
`TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED` warning and generic repair guidance to
add `context.record_move('post_vns_best_anchor_acceptance_guard', ...)`.
Branch-card summary then surfaced `mechanism_contract_status =
effect_attribution_missing` and `same_mechanism_followup_required = true`.

That summary is now the main research-quality risk. It can induce the next
agent to repair the run by adding the exact fake effect telemetry that
successor44c was designed to prevent.

## Code And Algorithm Review

The candidate code quality was clean for the attribution repair: small helper
in `acceptance.py`, minimal scheduler wiring, no fake effect telemetry, and no
code retries.

The solver mechanism itself was coarse. The guard only fires after simulated
annealing would accept a worse candidate and then rejects candidates with
`candidate_cost > current_cost` and `candidate_cost > best_cost`. Since
`best_cost <= current_cost`, the best-cost check is mostly redundant, so the
guard rejects nearly all strict worse simulated-annealing accepts. Candidate
trace counts show `post_vns_best_anchor_guard_reject` 191 times in the 32-pair
row and 291 times in the 48-pair row. That likely reduces diversification and
helps explain the CMT4/P-family weakness.

## Decision

Do not long-run unchanged successor44c.

Successor44c should be treated as a successful attribution-contract repair and
weak-positive acceptance-policy diagnostic, not as a promotion candidate.

Before any same-mechanism follow-up, fix the CVRP-owned summary/guidance path
that turns policy-mechanism no-direct-effect evidence into generic
`record_move(delta=...)` repair advice. Do not special-case the generic v3
telemetry guard unless a problem-neutral contract can be designed; the safer
next repair is to normalize CVRP successor44 branch-card/postrun/guidance
interpretation when `effect_observation_required=false` and the hypothesis
declared policy telemetry rather than direct move effect.

After that hygiene repair, either run one short protected successor44
follow-up with a narrower worse-SA risk threshold and explicit allow/reject
trajectory evidence, or clean-fork to a materially different CVRP-owned causal
path.
