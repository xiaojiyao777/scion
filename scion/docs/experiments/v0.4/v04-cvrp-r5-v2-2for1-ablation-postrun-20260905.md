# CVRP R5 exact 2-for-1 inclusion diagnostic postrun

**State:** terminal, `completed / DIAGNOSTIC_COMPLETE`

**Scope:** **diagnostic-only; no promotion decision and no Scion core change**

**Campaign:** `v04-cvrp-r5-v2-2for1-ablation-20260904`

**Frozen external design:**
[`PREREGISTRATION.md`](/home/clawd/research/scion-experiment-inputs/v04-cvrp-r5-v2-2for1-ablation-20260904/PREREGISTRATION.md)

**Primary artifacts:**
[`input.json`](/home/clawd/research/scion-experiments/v04-cvrp-r5-v2-2for1-ablation-20260904/input.json),
[`terminal.json`](/home/clawd/research/scion-experiments/v04-cvrp-r5-v2-2for1-ablation-20260904/terminal.json),
[`diagnostic metrics`](/home/clawd/research/scion-experiments/v04-cvrp-r5-v2-2for1-ablation-20260904/metrics/72cbb5bf-1b86-4f12-aa7c-b4ba1d8e21b7.json)

## Result in one sentence

On the six already outcome-known R4 screening cases, including
`_exchange_2_for_1` in full v2 was safe but produced no positive case median,
while removal was favored on two of six case medians; this is a negative
mechanism diagnostic, not evidence that the comparator should be promoted.

## Exact intervention and estimand

The candidate is the exact full R3i v2 used in R4. The comparator is an
ordinary source copy with exactly the `_exchange_2_for_1` entry removed from
the default local-search operator registry; the implementation remains in the
file but is unreachable through that registry. Direct source comparison has
exactly one changed line in
`policies/baseline_modules/local_search.py` and no other changed file.

The declared estimand is
`full_v2_minus_v2_without_exchange_2_for_1`; positive total-distance delta
means full v2 was shorter. This exact one-line contrast supports attribution
to operator *inclusion as an intervention*. The metrics do not contain direct
operator invocation, acceptance or gain counters, so they do not establish
which individual move was attempted or caused an observed solution change.

The six cases deliberately reuse R4's now outcome-known expanded-screening
population. Seeds `10103, 10111, 10133, 10139` and canary seed `10141` are
fresh, but fresh seeds do not make the cases outcome-unseen. The result is
therefore case-conditioned diagnosis only.

## Execution integrity and resource interpretation

The controlled canary passed. All `24/24` paired diagnostic observations were
valid, with zero candidate, comparator, shared or bilateral failures; zero
candidate-only timeouts, invalid outputs or attributable infeasibility; and
no protected `fleet_violation` regression. Execution order was balanced
`AB=12 / BA=12`, with no mismatch. Every solver arm ended normally with
`time_limit`, meaning its declared algorithm budget was consumed; no
subprocess timed out.

The run completed its entire declared diagnostic matrix using 50 solver
subprocesses, 2,660 nominal subject-seconds and 4,160 guarded subject-seconds.
The 72-hour outer alarm was only a process-failure ceiling. It is neither a
six-hour campaign limit nor a Scion policy that prevents future multi-day
research runs.

## Diagnostic effect

Positive delta favors full v2; negative delta favors v2 without the registry
entry.

| Statistic | Observed | Screening reference | Diagnostic reading |
|---|---:|---:|---|
| case W/L/T | `0/2/4` | - | no case-level win for inclusion |
| net case score | `-2/6 = -0.3333` | `>= 0.25` | below reference |
| case loss rate | `2/6 = 0.3333` | `<= 0.20` | above reference |
| median distance delta | `0` | `>= 2.0` | below reference |
| bootstrap interval | `[-281.75, 0]` | lower bound `>= 0` | below reference |
| pair W/L/T | `3/6/15` | descriptive | sparse, net unfavorable |

| Case | Four paired deltas by seed order | Case median | Result |
|---|---|---:|---|
| `A-n34-k5` | `0, 0, 0, 0` | `0` | tie |
| `tai100b` | `0, 0, -7, -6` | `-3` | loss |
| `X-n367-k17` | `+551, -508, -1124, -613` | `-560.5` | loss |
| `A-n53-k7` | `0, 0, +5, 0` | `0` | tie |
| `X-n186-k15` | `0, 0, 0, +3` | `0` | tie |
| `X-n573-k30` | `0, -1, 0, 0` | `0` | tie |

The reused Protocol evaluator reports `gate_outcome=fail` and
`SCREENING_FAIL_CASE_QUALITY`, but the R5 stage and terminal both record
`decision=null`. That reason code is a descriptive comparison with the R4
screening thresholds, not a promotion gate or an instruction to add more
gates to Scion. R5 completed exactly as designed.

## Search-behavior evidence

Paired process runtime was effectively identical: median ratio
`0.9999429863`, median delta `-4 ms`, regression rate `10/24`; runtime evidence
was `sufficient / high`. Under the same time budgets, full v2 performed less
recorded search work without a final-quality benefit:

| Counter | full v2 | minus 2-for-1 | Relative reading |
|---|---:|---:|---|
| search iterations | 3,586 | 4,338 | full `-17.3%` |
| move attempts | 51,723 | 53,371 | full `-3.1%` |
| accepted moves | 11,783 | 12,835 | full `-8.2%` |
| improving moves | 9,079 | 9,687 | full `-6.3%` |
| neutral accepted moves | 2,704 | 3,148 | full `-14.1%` |
| best updates | 41 | 39 | nearly equal |
| initial-to-final distance improvement | 1,111 | 1,116 | nearly equal |

This pattern is consistent with 2-for-1 inclusion displacing other search
throughput on these cases without compensating terminal-quality gain. It is
not proof of the unobserved per-move mechanism. `X-n367-k17` is especially
unstable: one seed favors full v2 and three favor removal. Its R5 deltas also
must not be compared directly with R4's because the comparator and seeds
changed.

## Claim and implementation boundary

R5 supports only this narrow statement: on the declared, outcome-known cases
and fresh seeds, retaining the 2-for-1 registry entry did not show benefit as
a bundle-level inclusion intervention. It does **not**:

- promote `v2-minus-2-for-1`;
- establish that removal beats original B0;
- generalize to fresh CVRP cases or other problem families;
- consume validation, frozen or retained evidence;
- justify a problem-specific field, operator rule or gate in Scion core.

The label `R5` identifies this experiment-local diagnostic; it is not a
project-wide release or closeout milestone.

## Next experiment boundary

Do not rerun this same outcome-known matrix as confirmation and do not infer
`minus-2-for-1 > B0` by chaining R4 and R5. If the intervention is pursued,
freeze the exact comparator as a new candidate and compare it directly with
the exact original B0 on new outcome-unseen cases and seeds disjoint from
R3--R5. Begin with development screening; expose new held-out stages only if
it passes unchanged scientific criteria.

If direct operator activation telemetry is needed, keep it lightweight and
local to the CVRP experiment/solver. Do not add provider dependence, a new
Scion gate, object identity, hashes, trust chains, signing, registration,
leases, receipts or repeated closure. Ordinary source trees and a single
bounded experiment record are sufficient.
