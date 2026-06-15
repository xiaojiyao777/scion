# CVRP Two-Opt Polish Follow-Up Smoke Postrun - 2026-06-15

## Purpose

This postrun analyzes the no-LLM follow-up for the prior aggregate-positive
two-opt polish smoke that failed its large-X gate because of repeated B-family
objective regressions.

The follow-up tested two problem-owned direct replay variants:

- `initial_only`: run `_two_opt_intra` polish only after initial construction;
  do not run embedded ALNS-repair polish.
- `size70`: run initial and embedded `_two_opt_intra` polish only when
  `instance.customer_count >= 70`.

This remains CVRP solver-design diagnostic evidence only. It is not promotion
evidence and does not alter generic core or `DecisionFeatures`.

## Artifacts

- Server root:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z`
- Wrapper status:
  `exit=0 finished_at=2026-06-15T18:57:15Z`
- Launch report:
  [`v04-cvrp-twoopt-polish-followup-smoke-launch-20260615.md`](v04-cvrp-twoopt-polish-followup-smoke-launch-20260615.md)

Primary results:

- `results/smoke_compare_initial_only.summary.json`
- `results/smoke_compare_initial_only.paired.csv`
- `results/smoke_compare_size70.summary.json`
- `results/smoke_compare_size70.paired.csv`

## Initial-Only Result

`initial_only` completed all pairs, but did not pass the large-X smoke gate.

- Completed pairs: `12/12`
- W/L/T: `7/2/3`
- Mean candidate-minus-baseline delta: `-2.6667`
- Median delta: `-3.0`
- Route regressions: `0`
- Fleet regressions: `0`
- Two-opt accepts: `9` initial, `0` embedded

The blocking issue remained repeated B-family regression:

- `B-n45-k6`: W/L/T `1/2/0`, mean delta `+4.3333`, median delta `+2.0`
- `B-n66-k9`: W/L/T `0/0/3`, all ties

Interpretation: embedded polish was not the only cause of small-row instability.
Even initial polish can perturb `B-n45-k6` enough to fail the pre-registered
"no repeated B-family objective regression" gate.

## Size70 Result

`size70` passed the follow-up smoke gate.

- Completed pairs: `12/12`
- W/L/T: `6/0/6`
- Mean candidate-minus-baseline delta: `-3.8333`
- Median delta: `-1.5`
- Median nonzero delta: `-7.5`
- Route regressions: `0`
- Fleet regressions: `0`
- Two-opt accepts: `6` initial, `558` embedded
- Candidate best-update count: `137`

By case:

- `B-n45-k6`: W/L/T `0/0/3`, all ties
- `B-n66-k9`: W/L/T `0/0/3`, all ties
- `A-n80-k10`: W/L/T `3/0/0`, mean delta `-3.0`
- `M-n200-k17`: W/L/T `3/0/0`, mean delta `-12.3333`

Per-row telemetry confirms the size gate behaved as intended on the small rows:

- B rows had `candidate_two_opt_initial_accepts=0`.
- B rows had `candidate_two_opt_embedded_accepts=0`.
- B rows tied the baseline objective and route count.

## Gate Decision

`initial_only` is rejected for large-X because it still has repeated B-family
objective regression.

`size70` is accepted for diagnostic large-X replay. This is not a promotion or
merge-ready claim. It only means the narrower scale-gated version cleared the
small smoke criteria and can be tested on large-X to see whether the apparent
medium/large search leverage survives outside the smoke set.

## Next Step

Launch size70 large-X direct replay against the completed ALNS-only champion
large-X baseline:

- Cases: `X-n401-k29`, `X-n573-k30`, `X-n641-k35`, `X-n1001-k43`
- Seeds: `61`, `67`, `89`
- Multipliers: `1`, `4`
- Baseline summary:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-largeX-runtime-curve-20260615T150454Z/summary.csv`

The replay should be interpreted as mechanism/update-density diagnosis, not
Scion Protocol evidence.

## Boundary Note

Size, route count, BKS gap, runtime, best-update trace, two-opt activation, and
case-family diagnostics remain problem-owned postrun/proposal-context material.
They must not enter generic `DecisionFeatures`.
