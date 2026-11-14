# CVRP Large-X Runtime Curve

Date: 2026-06-15

Purpose: close the Phase C frozen-collapse question by separating "runner grace
made large-X evidence invalid" from "more solver time creates large-X search
leverage." This was a no-LLM direct solver replay over the ALNS-only Phase C
champion, not a Scion campaign.

## Artifacts

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-largeX-runtime-curve-20260615T150454Z`
- Server sync:
  `/home/clawd/research/scion-experiments/v04-cvrp-largeX-runtime-curve-20260615T150454Z`
- Inputs: `X-n401-k29`, `X-n573-k30`, `X-n641-k35`, `X-n1001-k43`
- Seeds: `61`, `67`, `89`
- Multipliers: `1`, `2`, `4`
- Jobs: `36`
- Runtime tool commit: `72491c0`
- Runner: `scion/tools/cvrp_runtime_curve.py`
- Mode: direct solver replay only; no LLM or APS calls.

## Result

The run finished and synced cleanly. `run.log` has all `36` planned rows:
`34` completed and `2` hit outer `timeout_expired`. `summary.json` was written
with `dry_run=false`.

Across all completed rows, `solver_algorithm_best_update_count=0` and
`solver_algorithm_best_delta=0`. Completed rows had stable objective and BKS
gap across time multipliers:

| Case | Completed / Timeout | Objective | BKS Gap | Best Updates |
| --- | ---: | ---: | ---: | ---: |
| `X-n401-k29` | `9 / 0` | `68673` | `3.8078%` | `0` |
| `X-n573-k30` | `9 / 0` | `52495` | `3.5956%` | `0` |
| `X-n641-k35` | `9 / 0` | `68211` | `7.1085%` | `0` |
| `X-n1001-k43` | `7 / 2` | `77183` | `6.6727%` | `0` |

The two outer timeouts were `X-n1001-k43 seed=61` at `120s` and `240s`
nominal limits. The `480s` rows for `X-n1001-k43` completed, but wall times
still reached roughly `623s`, `933s`, and `1054s`.

## Interpretation

The curve confirms that Phase C frozen large-X protocol grace was too short for
stable paired evidence, especially on `X-n1001-k43`. But it does not support
the claim that simply extending solver time is enough to produce better large-X
solutions. More time produced more wall-clock cost and a few more iterations,
but no incumbent best update on any completed row.

The next CVRP step should not be another blind longer LLM campaign. The next
step should be targeted mechanism diagnostics: replay the actual ALNS-only
validation-positive candidates on large-X cases, inspect iteration/update
density by operator family, and determine whether the research loop can create
mechanisms with large-X search leverage. These diagnostics remain
problem-owned postrun/proposal feedback and must not enter `DecisionFeatures`.

