# CVRP Successor19 Clean-Fork Local Postrun - 2026-06-29

## Purpose

Summarize the completed local successor19 run. This report supersedes the
in-flight record for interpretation, but the in-flight record remains useful
for launch and progress chronology.

## Run Root

```text
/home/clawd/research/scion-experiments/v04-cvrp-successor19-cleanfork-local-2r-gpt55-20260629T133200Z-claw
```

Run status:

- `status=finished`
- `campaign_exit_status=complete`
- `wrapper_exit_status=0`
- `run_validity_status=valid`
- `run_completeness_status=complete`
- `completed_requested_rounds=true`
- `last_stop_reason=max_rounds_exhausted`
- `postrun_acceptance_status=ready`
- `postrun_acceptance_failed=false`

Postrun readiness:

- `delegation_ready=true`
- `current_run_analysis_ready=true`
- `failed_required_checks=[]`
- report-only boundary checks passed; postrun analysis did not mutate campaign,
  scheduler, promotion, protocol, or `DecisionFeatures` state.

## Runner Caveat

The WSL high-resource runner was prepared but not launched:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor19-cleanfork-2r-gpt55-20260629T132904Z-claw
```

That WSL root remains `prepared_only=true`. Earlier main-session preflight
attempts observed WSL-side local model failures: first HTTP 502/TLS backend
failure, then HTTP 401 `auth_token_invalidated` / `All accounts exhausted
(1 expired)`. After WSL `gpt-5.5` was refreshed, the 2026-06-29 recheck on
that prepared root returned `launch_ready=true`, static readiness true,
completion preflight `ok`, HTTP 200, healthy classification, and auth pool
active 1/1. Use WSL for future concurrent batches only from a freshly prepared
target root, with completion preflight re-run for that root before launch.

## Proposal Flow

First proposed mechanism:

- Hypothesis id: `f9727ce5-30b6-4b3f-b8ac-8e99a7ced0f2`
- Target: `policies/baseline_modules/destroy_repair.py`
- Mechanism ids: `radial_load_slice_removal`,
  `destroy_repair_selection`
- Outcome: pre-protocol quality block.
- Quality gate: `cvrp_solver_design_static_quality`
- Reason: non-causal effect telemetry was recorded inside
  `destroy_repair.py`. Destroy helpers may record activation or budget during
  removal, but effect telemetry must be recorded after repair and acceptance on
  a feasible candidate or directly attributable accepted improvement.

Second proposed mechanism:

- Hypothesis id: `ec55f92f-3aef-4870-b7cb-22f27d6625f5`
- Target: `policies/baseline_modules/local_search.py`
- Mechanism id: `bounded_route_segment_exchange`
- Candidate artifact index:
  `campaign/artifacts/formal_candidates/index.jsonl`
- Candidate patch digest:
  `a23e167b0cfa8ead31361738d2d89a3c11572812c7dfac2b615a1a8cd9b695a2`
- Outcome: two screening rows, no validation/frozen rows.

Mechanism description:

`bounded_route_segment_exchange` adds a bounded VNS local-search neighborhood
that swaps short contiguous length-2/3 blocks between distinct routes when
capacity remains feasible and combined route distance strictly decreases.

## Protocol Accounting

From `postrun_acceptance/research_efficiency/cvrp_on_full.research_efficiency.v1.json`:

- Requested/effective rounds: `2 / 2`
- Protocol metric results: `2`
- Screening rows: `2`
- Validation rows: `0`
- Frozen rows: `0`
- Formal candidate artifact rows: `1`
- Proposal attempts total/consumed: `3 / 3`
- Quality blocks: `1`
- Verification consumed candidates: `2`
- Verification failure consumed candidates: `0`

## Screening Row 1

Metrics artifact:

```text
campaign/metrics/aa5f9356-aea5-49e2-9592-14130395517e.json
```

Summary:

- Complete: `true`
- Pairs: `32 / 32`
- Failed pairs: `0`
- Pair counts: `15 wins / 8 losses / 9 ties`
- Median delta: `2.0`
- CI: `[-6.0, 7.0]`
- Decision: `expand_screening`
- Reason: `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`

Protected-case evidence:

- `CMT2`: `2 wins / 2 losses / 0 ties`, median delta `4.0`
- `CMT4`: `1 win / 1 loss / 2 ties`, median delta `0.0`

Notable case-level pattern:

- Strong positive on `A-n64-k9`: `4 wins`, median delta `15.0`
- Mixed/negative on `B-n63-k10` and `X-n110-k13`
- Neutral on `M-n200-k17`: `4 ties`

## Screening Row 2

Expanded metrics artifact:

```text
campaign/metrics/6713e5d8-57d8-4ca6-b317-a273024eba4c.json
```

Summary:

- Complete: `true`
- Pairs: `48 / 48`
- Failed pairs: `0`
- Pair counts: `19 wins / 15 losses / 14 ties`
- Median delta: `0.0`
- CI: `[-3.5, 3.25]`
- Decision: `continue_explore`
- Reasons:
  - `SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_CI_LOW`
  - `SCREENING_BORDERLINE_POLICY_FAIL_CLOSED`
  - `SCREENING_MARGINAL_SIGNAL_CONTINUE`

Protected-case evidence:

- `CMT4`: `1 win / 1 loss / 2 ties`, median delta `0.0`
- `CMT3`: `2 wins / 2 losses / 0 ties`, median delta `-3.0`
- `CMT2` was present in row 1 and remains an explicit caveat for any same
  mechanism follow-up.

Notable case-level pattern:

- Positive or neutral pockets exist, including `A-n64-k9`, `A-n80-k10`,
  `E-n101-k14`, and `P-n65-k10`.
- Loss-heavy or negative-median pockets remain, including `B-n67-k10`,
  `E-n101-k8`, `P-n76-k4`, `CMT3`, and `X-n110-k13`.
- All listed pair summaries preserve `fleet_violation=0.0`.

## MDE Interpretation

Measurement readiness:

- `status=ready`
- `reason_code=ok`
- `mde_at_power_80=9.9`
- `effect_to_mde_ratio=0.20202020202020202`
- `signal_to_noise_tier=low_power`
- `n_pairs=96`
- `noise_band_p90_abs=45.5`

Effect-vs-MDE:

- `protocol_row_count=2`
- `positive_rows=1`
- `nonpositive_rows=1`
- `rows_at_or_above_mde=0`
- `rows_with_ci_high_below_mde=2`
- `max_effect_to_mde_ratio=0.20202`
- `interpretation=all_available_ci_high_below_mde`

Mechanism family mapping:

- `bounded_route_segment_exchange`
- `protocol_row_count=2`
- `positive_rows=1`
- `nonpositive_rows=1`
- `rows_at_or_above_mde=0`
- `rows_with_ci_high_below_mde=2`

## Branch And Decision State

Final branch card:

- Branch status: `explore`
- Final classification: `active`
- Mechanism ids: `bounded_route_segment_exchange`
- Evidence tier: `marginal`
- Phase activation: `activation_observed`
- Objective effect status: `positive`
- Runtime confidence: `low_cached_champion`
- Why not promoted:
  - `SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_CI_LOW`
  - `SCREENING_BORDERLINE_POLICY_FAIL_CLOSED`
  - `SCREENING_MARGINAL_SIGNAL_CONTINUE`
  - `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`
- Allowed next actions include same-branch refinement actions such as
  `refine`, `repair`, `diagnostic`, `observability`, and
  `telemetry_wiring`.

Research-continuity behavior:

- Active research shape: `deep_focused`
- Max branch depth: `3`
- Same-mechanism follow-up selection rate: `1.0`
- Lesson usage was visible and report-only.

## Interpretation

Solver conclusion: not promotion-grade.

The run produced a valid, mechanism-active CVRP candidate with local positive
signals, but both protocol rows are below MDE. The expanded row ended with
borderline/marginal evidence and a fail-closed `continue_explore` decision.
There is no validation row, no frozen row, no champion version gain, and no
positive-at-MDE evidence.

Framework conclusion: positive for v0.4 behavior.

The run exercised the intended repaired framework behavior:

- problem-owned static quality blocked non-causal telemetry before protocol;
- a materially different clean-fork mechanism was proposed and evaluated;
- CMT protected cases were included in formal screening evidence;
- low-SNR trajectory-divergent evidence triggered expansion rather than
  premature promotion;
- expanded mixed evidence produced fail-closed continuation rather than
  promotion;
- postrun acceptance/readiness artifacts were generated and marked ready;
- effect-vs-MDE stayed report-only and excluded from `DecisionFeatures`.

## Next Action

Do not close v0.4 on this solver result.

If continuing CVRP within v0.4, the next task should be a focused same-branch
refinement only if it explicitly addresses the negative-median pockets
(`B-n67-k10`, `P-n76-k4`, `X-n110-k13`, and CMT-family caveats) without
weakening the mechanism telemetry boundary. Otherwise, clean-fork to a new
CVRP-owned causal path. Use WSL for concurrent batches from a freshly prepared
target root, after re-running completion preflight on that root.
