# CVRP Two-Opt Size70 Large-X Postrun - 2026-06-15

## Purpose

This no-LLM diagnostic replay tested the size-gated two-opt polish hypothesis
on large-X CVRP rows after the follow-up smoke removed the B-family regressions
seen in the ungated two-opt replay.

This is problem-owned mechanism evidence only. It is not Scion Protocol
evidence, not promotion evidence, and does not alter `DecisionFeatures`.

## Artifacts

- Root:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z`
- WSL source root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z`
- Launch report:
  `scion/docs/experiments/v0.4/v04-cvrp-twoopt-size70-largeX-launch-20260615.md`
- Candidate summary:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/results/candidate_size70_largeX/summary.csv`
- Paired comparison:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/results/largeX_compare_size70.paired.csv`
- Summary:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/results/largeX_compare_size70.summary.json`
- Exit:
  `exit=0 finished_at=2026-06-15T19:44:01Z`

## Shape

Candidate replay shape:

- Cases: `X-n401-k29`, `X-n573-k30`, `X-n641-k35`, `X-n1001-k43`
- Seeds: `61`, `67`, `89`
- Candidate multipliers: `1`, `4`
- Planned candidate rows: `24`
- Candidate JSON rows: `24`
- Completed candidate/champion pairs: `23`
- Noncompleted planned pair: `X-n1001-k43`, seed `61`, multiplier `1`, where
  both baseline and candidate timed out.

The paired comparison summary reports `total_keys=36` and
`missing_candidate=12` because the champion runtime curve also had multiplier
`2` rows. Those `m=2` rows were intentionally not part of this candidate replay
and should not be counted as missing planned candidate work.

## Results

Completed planned-pair objective result:

- W/L/T: `23/0/0`
- Mean candidate-minus-champion delta: `-295.5652`
- Median delta: `-192.0`
- Median nonzero delta: `-192.0`
- Route regressions: `0`
- Route improvements: `0`
- Fleet regressions: `0`

By case:

| case | completed pairs | W/L/T | mean delta | median delta |
| --- | ---: | --- | ---: | ---: |
| `X-n401-k29` | 6 | `6/0/0` | `-152.0` | `-152.0` |
| `X-n573-k30` | 6 | `6/0/0` | `-192.0` | `-192.0` |
| `X-n641-k35` | 6 | `6/0/0` | `-484.0` | `-484.0` |
| `X-n1001-k43` | 5 | `5/0/0` | `-366.0` | `-366.0` |

By multiplier:

| multiplier | completed pairs | W/L/T | mean delta | median delta |
| ---: | ---: | --- | ---: | ---: |
| `1` | 11 | `11/0/0` | `-292.3636` | `-192.0` |
| `4` | 12 | `12/0/0` | `-298.5` | `-279.0` |

By seed:

| seed | completed pairs | W/L/T | mean delta | median delta |
| ---: | ---: | --- | ---: | ---: |
| `61` | 7 | `7/0/0` | `-288.8571` | `-192.0` |
| `67` | 8 | `8/0/0` | `-298.5` | `-279.0` |
| `89` | 8 | `8/0/0` | `-298.5` | `-279.0` |

Telemetry:

- Candidate two-opt initial accepts on completed rows: `23`
- Candidate two-opt embedded accepts on completed rows: `72`
- Embedded accepts by case: `X-n401=44`, `X-n573=10`, `X-n641=13`,
  `X-n1001=5`
- Candidate best-update counts on completed rows: all `0`
- Candidate completed runtime was slower on `12` paired rows and faster on `11`;
  median candidate-minus-champion runtime delta was `+0.2896s`, mean
  `-37.9842s`.

## Interpretation

This replay satisfies the immediate no-LLM mechanism gate that the Phase C
candidate-specific replay failed: it shows completed-pair objective movement on
large-X, across all four large-X cases, with no completed-pair objective loss
and no route/fleet regression.

The effect is stable by case because the size70 two-opt polish changes the
constructed/polished solution before or outside the ALNS incumbent-update trace.
That is why `candidate_best_update_count=0` does not invalidate the replay:
the objective movement is visible in the final solution and two-opt activation
counters, but not as an ALNS incumbent-update event. The mechanism is therefore
best described as a construction/polish scheduling mechanism, not as a deeper
large-X ALNS search-leverage mechanism.

The replay is still not final CVRP promotion evidence:

- It is direct no-LLM replay, not formal Scion Protocol.
- One planned pair on `X-n1001-k43 seed61 m1` timed out on both baseline and
  candidate; the candidate wrapper reached the 1020s timeout envelope for that
  row.
- The comparison did not run a candidate `m=2` arm, so `m=2` is intentionally
  absent.
- The positive rows keep route counts tied rather than improving fleet size.
- Runtime pressure remains heavy on large-X. Many completed candidate rows
  exceed nominal solver time limits, especially at `m=1` where fixed polish
  overhead dominates the time-limit ratio.

## Next Gate

This is strong enough to treat the size70 two-opt polish as the leading CVRP
mechanism seed for the next Scion CVRP work. The next step should be formal
validation, not another blind Phase C-style LLM campaign:

- either a fixed-candidate formal replay using the size70 mechanism against the
  CVRP protocol splits, with a pre-registered full key set and explicit
  inclusion or exclusion of `m=2`;
- or a short Scion CVRP agent run seeded with this mechanism and audited for
  whether branch/context machinery preserves and follows the evidence.

Before promotion claims, also fix or pre-register the large-X timeout/wall-clock
policy and repeat with enough seeds to make runtime and objective evidence
complete under the intended protocol.

In either case, keep BKS gaps, runtime behavior, two-opt activation, and
best-update traces as problem-owned diagnostics outside `DecisionFeatures`.
