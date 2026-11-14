# CVRP Size70 Tier 1 Large-X Postrun - 2026-06-15

## Boundary

This report follows `scion/design/scion-architecture-v3.md`: the runtime,
BKS-gap, activation, and best-update diagnostics below are problem-owned
postrun/proposal material only. They are not a Scion campaign, not promotion
evidence, and must not enter `DecisionFeatures`.

No formal validation replay was launched in this step.

## Inputs

- Analysis plan:
  `scion/docs/planning/v0.4/v04-cvrp-size70-tier1-postrun-analysis-plan-20260615.md`
- Launch report:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-tier1-largeX-launch-20260615.md`
- Candidate prep:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-fixed-replay-prep-20260615.md`
- Validation design:
  `scion/docs/planning/v0.4/v04-cvrp-size70-fixed-candidate-validation-design-20260615.md`
- Candidate run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z`
- Champion curve root:
  `/home/clawd/research/scion-experiments/v04-cvrp-largeX-runtime-curve-20260615T150454Z`

## Completion And Sync

The WSL run was polled read-only through the configured SSH command. It was
active through the large `X-n1001-k43` tail and completed at the final poll:

- tmux session: absent
- candidate summary:
  `results/candidate_size70_largeX_full/summary.json` present
- wrapper log:
  `run.log` ended with
  `wrote .../results/candidate_size70_largeX_full/summary.json`

The completed WSL root was synced to the server root with:

```bash
rsync -az -e 'ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes' \
  xjy-ubuntu@127.0.0.1:/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z/ \
  /home/clawd/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z/
```

## Key Accounting

Planned key set:

- cases: `X-n401-k29`, `X-n573-k30`, `X-n641-k35`, `X-n1001-k43`
- seeds: `61`, `67`, `89`
- multipliers: `1`, `2`, `4`
- total planned keys: `36`

Candidate accounting:

- represented keys: `36/36`
- missing keys: none
- extra keys: none
- completed: `35`
- resumed: `0`
- timeout: `1`
- failed: `0`

Champion curve accounting:

- represented keys: `36/36`
- completed: `34`
- timeout: `2`
- failed: `0`

Status-pair comparison on matching keys:

- candidate completed, champion completed: `34`
- candidate timeout, champion timeout: `1`
- candidate completed, champion timeout: `1`
- candidate-only timeout/failure: `0`

The only candidate timeout was `X-n1001-k43 seed=61 m=1`, which was also a
champion timeout. Candidate completed `X-n1001-k43 seed=61 m=2`, while champion
timed out on that key.

## Feasibility And Routes

Raw solver JSON was present for all `35` candidate completed rows.

- `feasible=true`: `35/35`
- `fleet_violation=0`: `35/35`
- runtime total-distance matched objective total-distance: `35/35`
- route-count delta versus champion on completed-vs-completed keys: `0` for
  all `34` comparisons

Route counts by case remained stable:

| Case | Candidate routes | Champion routes |
|---|---:|---:|
| `X-n401-k29` | 29 | 29 |
| `X-n573-k30` | 30 | 30 |
| `X-n641-k35` | 35 | 35 |
| `X-n1001-k43` | 43 | 43 |

## Candidate vs Champion

On the `34` completed-vs-completed matching keys, candidate improved
`total_distance` on every key.

Aggregate completed-vs-completed deltas, measured as
`candidate - champion`:

- improved: `34`
- tied: `0`
- worse: `0`
- min delta: `-484.0`
- median delta: `-192.0`
- max delta: `-152.0`
- sum delta: `-10014.0`
- BKS-gap delta range: `-0.760003` to `-0.229767` percentage points

Per-case summary:

| Case | Completed comparisons | Candidate distance | Candidate BKS gap | Champion distance | Champion BKS gap | Distance delta | Timeout relation |
|---|---:|---:|---:|---:|---:|---:|---|
| `X-n401-k29` | 9 | 68521.0 | 3.578015% | 68673.0 | 3.807782% | -152.0 | none |
| `X-n573-k30` | 9 | 52303.0 | 3.216703% | 52495.0 | 3.595603% | -192.0 | none |
| `X-n641-k35` | 9 | 67727.0 | 6.348533% | 68211.0 | 7.108536% | -484.0 | none |
| `X-n1001-k43` | 7 | 76817.0 | 6.166816% | 77183.0 | 6.672656% | -366.0 | `seed=61 m=1` both timeout; `seed=61 m=2` candidate completed, champion timeout |

There is no broad candidate regression in distance, BKS gap, routes, status, or
timeout behavior on this Tier 1 key set.

## Runtime Behavior

Among the `35` candidate completed rows:

- `solver_algorithm_runtime_budget_hit=true`: `25`
- `solver_algorithm_runtime_budget_hit=false`: `10`
- `solver_algorithm_stop_reason=time_limit`: `25`
- `solver_algorithm_stop_reason=completed`: `10`

By case:

| Case | Budget hit true | Budget hit false | Stop `time_limit` | Stop `completed` |
|---|---:|---:|---:|---:|
| `X-n401-k29` | 3 | 6 | 3 | 6 |
| `X-n573-k30` | 6 | 3 | 6 | 3 |
| `X-n641-k35` | 9 | 0 | 9 | 0 |
| `X-n1001-k43` | 7 | 1 | 7 | 1 |

This remains runtime-pressure evidence, not promotion evidence. The important
Tier 1 distinction is that the pressure did not create candidate-only timeout
or completed-key objective regression.

## Phase Activation

The raw `runtime.solver_algorithm_actionability_summary` and phase stats show
that the size70 two-opt mechanism activated on completed rows.

`two_opt_polish_initial`:

- present: `35/35`
- attempted: `35/35`
- accepted moves > 0: `35/35`
- improvement count > 0: `35/35`
- best delta > 0: `35/35`
- move attempts: `35`
- accepted moves: `35`
- delta sum: `10380.0`
- max best delta: `484.0`

By case, initial polish was present, attempted, accepted, and improving on all
completed rows:

- `X-n401-k29`: `9/9`
- `X-n573-k30`: `9/9`
- `X-n641-k35`: `9/9`
- `X-n1001-k43`: `8/8`

`two_opt_polish_embedded`:

- present: `28/35`
- attempted: `28/35`
- accepted moves > 0: `26/35`
- improvement count > 0: `26/35`
- best delta > 0: `26/35`
- move attempts: `115`
- accepted moves: `100`
- delta sum: `11929.0`
- max best delta: `710.0`

By case:

| Case | Embedded present | Embedded accepted/improving |
|---|---:|---:|
| `X-n401-k29` | 9/9 | 9/9 |
| `X-n573-k30` | 8/9 | 6/9 |
| `X-n641-k35` | 7/9 | 7/9 |
| `X-n1001-k43` | 4/8 | 4/8 |

Rows with limited embedded polish had concrete runtime explanations: the
initial polish had already produced measurable objective movement, and several
rows hit `time_limit` after only one or two search iterations. Two
`X-n573-k30` rows attempted embedded polish but had no accepted embedded move.

## Best-Update Diagnostics

For all `35` candidate completed rows:

- `solver_algorithm_best_update_count`: `0`
- `solver_algorithm_best_update_trace` length: `0`
- best-update summary phase/operator counts: empty

This means the Tier 1 mechanism evidence is phase-level construction/polish
movement, not deeper ALNS incumbent-update movement. Under the pre-registered
validation design, this is acceptable for this mechanism because final
objective movement and two-opt phase accepts are present; it must not be
described as best-update leverage from deeper ALNS search.

## Recommendation

Tier 1 Large-X completion diagnostic passes to the next human-reviewed step:
formal fixed-candidate validation replay readiness.

Rationale:

- all `36` planned keys are accounted;
- there are no missing keys and no failed rows;
- candidate has no candidate-only timeout;
- completed outputs are feasible, fleet-clean, and route-count stable;
- all `34` completed-vs-completed champion comparisons improve
  `total_distance` and BKS gap;
- `two_opt_polish_initial` activates and improves on every completed row;
- embedded polish often activates and improves, with limited rows explained by
  runtime pressure and low iteration count.

Do not treat this report as promotion evidence. Formal validation and, if that
passes, frozen evaluation are still required through the intended Scion
Protocol path.

## Residual Risks

- Runtime pressure remains high: `25/35` completed candidate rows hit the
  runtime budget and stopped with `time_limit`.
- The single candidate timeout is not candidate-only, but `X-n1001-k43` remains
  a heavy-tail diagnostic case.
- Best-update trace/count stayed zero throughout, so the mechanism claim should
  be limited to two-opt polish phase movement and final objective improvement.
- Direct no-LLM replay is mechanism-validity material only; it does not replace
  formal validation/frozen protocol evidence.
