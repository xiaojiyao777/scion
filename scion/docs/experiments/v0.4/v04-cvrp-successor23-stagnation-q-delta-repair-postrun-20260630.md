# CVRP Successor23 Stagnation q-Delta Repair Postrun - 2026-06-30

## Run Identity

- Run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor23-stagnation-q-delta-repair-2r-gpt55-20260630T020559Z-claw`
- WSL runner repo:
  `/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629`
- Runner commit: `b0adf692`
- Model route: `gpt-5.5` via `http://127.0.0.1:8080`
- Start/end: `2026-06-30T02:06:31Z` / `2026-06-30T03:21:42Z`
- Wrapper exit status: `0`
- Campaign stop reason: `max_rounds_exhausted`
- Postrun acceptance: ready for analysis

The first prepared root,
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor23-stagnation-q-delta-repair-2r-gpt55-20260630T014819Z-claw`,
failed before campaign start because the pre-campaign completion preflight
returned HTTP 502 from a TLS handshake EOF. It is a launch-path transient, not
CVRP experiment evidence.

## Validity

The run is valid and complete:

- requested rounds: `2`;
- effective protocol rounds: `2`;
- screening protocol rows: `2`;
- formal candidates: `2` accounting entries for one candidate expanded once;
- proposal attempts: `2`;
- proposal/verification/telemetry/infra failure categories: none;
- champion promotions: `0`;
- latest champion version: `1`.

Postrun acceptance generated current-run artifacts under
`postrun_acceptance/` and reported `current_run_analysis_ready=true`,
`failed_required_checks=[]`, and `delegation_ready=true`.

## Mechanism

The live candidate targeted the intended mechanism:

- primary mechanism: `stagnation_adaptive_destroy_size_schedule`;
- mechanism family: scheduler destroy-size policy;
- forced target file: `policies/baseline_modules/scheduler.py`;
- patch scope: local scheduler change.

The patch computed `baseline_q`, modified `q` after stagnation or recent
improving acceptance state, and computed local `q_delta`. It recorded
mechanism phase/iteration telemetry only when `q_delta != 0`.

Important caveat: the runtime trace did not explicitly record
`baseline_q`, `adapted_q`, or `q_delta` fields. The q-delta repair is therefore
supported by aligned `q` trace divergence and mechanism telemetry, but it does
not fully satisfy the stricter explicit q-audit-field requirement.

## q-Trajectory Audit

Successor23 fixed successor22b's zero-q-trajectory failure in the observable
ALNS `q` trace:

| Row | Pairs | Aligned q iterations | Changed aligned q iterations | Pairs with any q change | Explicit q-delta fields |
|---|---:|---:|---:|---:|---:|
| row 1 | 48 | 722 | 581 | 47 | 0 |
| row 2 | 32 | 497 | 367 | 28 | 0 |

Schedule phase runtime was positive in 21/48 row-1 pairs and 11/32 row-2
pairs. This is no longer the successor22b inactive-q-trajectory no-op.

However, because `baseline_q`, `adapted_q`, and `q_delta` were not emitted as
runtime fields, future analysis should call this an inferred q-trajectory
repair rather than a complete q-audit implementation.

## Objective Evidence

The objective evidence is solver-negative for v0.4 closeout:

- rows at or above MDE: `0`;
- positive rows: `0`;
- rows with CI high below MDE: `2`;
- max median delta: `0.0`;
- max effect/MDE ratio: `0.0`;
- interpretation: `all_available_ci_high_below_mde`;
- MDE at 80% power: `9.9`.

Protocol rows:

| Row | Pairs | Pair W/L/T | Median delta | CI | Decision | Interpretation |
|---|---:|---|---:|---|---|---|
| row 1 | 48 | 19/20/9 | `0.0` | `[-2.0, 3.5]` | `expand_screening` | below MDE |
| row 2 | 32 | 14/10/8 | `-0.5` case-level | `[-3.0, 3.25]` | `continue_explore` plus lifecycle park | below MDE / quality regression |

Overall postrun summary reported case-level `7W/5L/8T` and pair-level
`33W/30L/17T`. The branch was parked as `quality_regression` with reason codes
including `SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA`,
`SCREENING_BORDERLINE_POLICY_FAIL_CLOSED`,
`BRANCH_LIFECYCLE_PARK_LINEAGE`, and
`SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`.

Protected-case signal:

- CMT4 remained positive in the screened rows, with median delta `3.5`;
- CMT2 appeared in row 2 and had median delta `-1.5`, so it remains a
  protected-case caveat.

Runtime interpretation stays report-only under the CVRP budget-exhausting
runtime model. Row-2 runtime ratio median was approximately `1.0`, with both
candidate and champion near budget saturation; do not direct solver repair from
runtime alone.

## Interpretation

Successor23 is framework-useful but not solver-positive.

It demonstrates that the repaired guidance can drive the agent to:

- target the intended scheduler mechanism;
- keep implementation in the intended scheduler file;
- generate a material q-trajectory difference versus champion;
- complete formal screening and postrun acceptance.

It does not support a v0.4 solver-improvement claim because both rows are
below MDE, the expanded row has negative median case-level effect, the branch
is parked as quality regression, and the explicit q-audit fields are missing.

Classification:

- `activation-repaired-but-below-MDE`;
- with `quality-regression-parked` and `explicit-q-delta-telemetry-missing`
  caveats.

## Next Action

Do not continue the unchanged successor23 scheduler policy.

The scheduler destroy-size branch should be parked unless a future task is
explicitly scoped as a telemetry-only repair for `baseline_q`,
`adapted_q`, and `q_delta` fields. For solver research, the next CVRP slot
should clean-fork to a materially different CVRP-owned causal path instead of
spending another branch on this same q schedule.
