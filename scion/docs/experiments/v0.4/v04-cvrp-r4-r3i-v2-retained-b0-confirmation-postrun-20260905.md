# CVRP R4 R3i-v2 retained-B0 confirmation postrun

**State:** terminal, `completed / NOT_CONFIRMED`

**Campaign:** `v04-cvrp-r4-r3i-v2-retained-b0-confirmation-20260904`

**Frozen design:**
[`R4 preregistration`](v04-cvrp-r4-r3i-v2-retained-b0-confirmation-preregistration-20260904.md)

**Primary artifacts:**
[`input.json`](/home/clawd/research/scion-experiments/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-20260904/input.json),
[`terminal.json`](/home/clawd/research/scion-experiments/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-20260904/terminal.json),
[`expanded-screening metrics`](/home/clawd/research/scion-experiments/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-20260904/metrics/ab7e221a-0d68-497c-a18e-87e80451cfe1.json)

## Result in one sentence

R4 is a valid negative confirmation, not an interrupted run: the exact
cumulative R3i v2 bundle was safe but did not clear expanded screening against
the exact R3i starting B0, so validation, frozen and retained-B0 stages were
correctly left unopened.

## Fixed contrast and population

The candidate is the exact R3i `champion_v2`; the comparator is the exact B0
from which R3i started. Their byte-level contrast contains exactly three
changed files:

- `policies/baseline_modules/destroy_repair.py`;
- `policies/baseline_modules/local_search.py`;
- `policies/baseline_modules/scheduler.py`.

The estimand is therefore the cumulative bundle, not any one operator. The six
expanded-screening cases and four seeds were fixed prospectively and were
outcome-unseen relative to R3--R3i. The reused controlled canary was a
non-estimand safety check.

## Execution integrity

The canary passed at seed `10091`. All `24/24` expanded-screening pairs were
valid, with zero candidate, B0, shared or bilateral failures; zero
candidate-only timeouts, invalid outputs or attributable infeasibility; and no
protected `fleet_violation` regression. AB/BA execution was balanced at
`12/12`, with no order mismatch. Every solver arm exited normally after using
its declared algorithm time budget; `time_limit` here is the solver's ordinary
stop reason, not a subprocess timeout.

The terminal consumed exactly the stage it reached: 50 serial solver
subprocesses, 2,660 nominal subject-seconds and 4,160 guarded subject-seconds.
The preregistered maxima of 170 subprocesses, 10,160 nominal seconds, 15,260
guarded seconds and a 21,600-second outer hardwall were ceilings for the full
conditional funnel, not quotas that had to be exhausted. R4 stopped because
of scientific evidence, not wall-clock, disk, provider or infrastructure
failure.

## Expanded-screening effect

Positive distance delta means v2 produced the shorter route set.

| Statistic | Observed | Required | Interpretation |
|---|---:|---:|---|
| case W/L/T | `1/0/5` | - | one case-level win, otherwise ties |
| net case score | `1/6 = 0.1667` | `>= 0.25` | fail |
| case loss rate | `0/6 = 0` | `<= 0.20` | pass |
| median distance delta | `0` | `>= 2.0` | fail |
| bootstrap interval | `[0, 130.5]` | lower bound `>= 0` | pass |
| pair W/L/T | `4/2/18` | descriptive | sparse and seed-sensitive |

The case-level result was concentrated in one instance:

| Case | Four paired deltas by seed order | Case median | Result |
|---|---|---:|---|
| `A-n34-k5` | `0, 0, 0, 0` | `0` | tie |
| `tai100b` | `0, 0, 0, +14` | `0` | tie |
| `X-n367-k17` | `+899, +1573, -377, -1013` | `+261` | win |
| `A-n53-k7` | `0, 0, +11, 0` | `0` | tie |
| `X-n186-k15` | `0, 0, 0, 0` | `0` | tie |
| `X-n573-k30` | `0, 0, 0, 0` | `0` | tie |

The terminal reason `SCREENING_FAIL_CASE_QUALITY` is an aggregate Protocol
label. It does not mean that only the net-case condition failed: both the
minimum net-case score and the practical median threshold failed. Removing or
weakening the case-score condition would therefore not turn this run into a
pass.

## Runtime and mechanism evidence

Paired process runtime was effectively identical: median ratio
`0.9999645693`, median delta `-1.5 ms`, regression rate `10/24`; runtime
evidence was `sufficient / high`. The solver-reported aggregate search counters
show a redistribution rather than a terminal-quality advantage:

| Counter | v2 | B0 |
|---|---:|---:|
| search iterations | 3,973 | 4,135 |
| move attempts | 56,748 | 60,453 |
| accepted moves | 12,722 | 12,372 |
| improving moves | 9,808 | 9,409 |
| neutral accepted moves | 2,914 | 2,963 |
| best updates | 43 | 45 |
| initial-to-final distance improvement | 1,170 | 1,145 |

Both arms reported zero ALNS search iterations on every `X-n367-k17` and
`X-n573-k30` pair, while `X-n186-k15` had only one to three. Consequently the
only case-level win supplies no direct positive ALNS-iteration evidence for
the changed destroy/scheduler logic. Because `local_search.py` also changed,
the result still cannot isolate any component of the bundle. In particular,
R4 neither identifies nor exonerates `_exchange_2_for_1` by itself.

## Scientific claim boundary

R4 does not support the planned retained-B0 claim and rejects progression at
the first formal effect stage. It does not invalidate the narrower R3i
statement that cumulative v2 passed the three R3i populations, but it shows
that this benefit did not reproduce as a broad, practically positive effect
on the new R4 screen. The positive `X-n367-k17` median is internally
sign-unstable and cannot carry a generalization claim.

No validation, frozen or retained pair was executed. Those outcome-unseen
blocks remain unconsumed and must not be described as tested. There is no
scientific basis to rerun the same R4 matrix longer, relax its gates, or claim
retained superiority.

## Next experiment boundary

The subsequent exact one-line 2-for-1 inclusion diagnostic is documented in
the [`R5 postrun`](v04-cvrp-r5-v2-2for1-ablation-postrun-20260905.md). Its
outcome-known cases cannot repair R4 or promote an arm.

If the R5 mechanism signal is pursued, the defensible next rung is a
provider-free, preregistered comparison of `v2-minus-2-for-1` directly against
the original B0 on new outcome-unseen cases and seeds disjoint from R3--R5.
It must begin as development screening and may expose held-out stages only
after a pass. R4 and R5 cannot be combined transitively because their
comparators and seeds differ. Any operator-specific activation or gain
telemetry belongs to that CVRP experiment, not to problem-neutral Scion core.
