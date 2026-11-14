# CVRP Successor20 Bounded Segment Refine Postrun - 2026-06-29

## Purpose

Summarize the completed WSL successor20 run. This report supersedes the
successor20 in-flight record for interpretation, while the in-flight record
remains useful for launch chronology.

Successor20 resumed successor19 and refined the same
`bounded_route_segment_exchange` branch. The run is valid and postrun-ready,
but it does not produce promotion-grade CVRP solver improvement.

## Run Roots

Authoritative WSL run root:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor20-bounded-segment-refine-2r-gpt55-20260629T150851Z-claw
```

Local mirror used for this analysis:

```text
/home/clawd/research/scion-experiments/v04-cvrp-successor20-bounded-segment-refine-2r-gpt55-20260629T150851Z-claw
```

Resume source:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor19-cleanfork-local-2r-gpt55-20260629T133200Z-claw/campaign
```

## Run Status

Root `run_status.json`:

- `status=finished`
- `campaign_exit_status=complete`
- `campaign_wrapper_exit_status=0`
- `wrapper_exit_status=0`
- `run_validity_status=valid`
- `run_completeness_status=complete`
- `run_complete=true`
- `completed_requested_rounds=true`
- `last_stop_reason=max_rounds_exhausted`
- `postrun_acceptance_status=ready`
- `postrun_acceptance_failed=false`
- `postrun_reports_exit_status=0`
- `postrun_readiness_exit_status=0`
- Started: `2026-06-29T15:10:04Z`
- Ended: `2026-06-29T16:24:15Z`

Postrun readiness:

- `delegation_ready=true`
- `current_run_analysis_ready=true`
- `failed_required_checks=[]`
- `failed_optional_checks=[]`

## Proposal Flow

Run constraints:

- Surface: `solver_design`
- Action: `modify`
- Target file: `policies/baseline_modules/local_search.py`
- Resumed branch: `7431c39c-2fe9-4d5c-bf79-b34d60d9f930`
- Hypothesis id: `5201e32d-bd7c-4b50-a014-45196d0948ea`

Formal candidate artifact:

- Candidate id: `8626aa8c035b15fb`
- Stage: `screening`
- Artifact:
  `campaign/artifacts/formal_candidates/7431c39c/screening-5201e32d-bd7c-4b50-a014-45196d0948ea-8626aa8c035b15fb/candidate.patch.json`
- Patch digest:
  `3bfbe7faeb72719d1c3239159dfa077a54cc054a330adb5f64567726b4431fde`
- Raw metrics ref:
  `campaign/metrics/b0f7c15a-660c-45ad-b6f5-742ccb3868f0.json`
- Replay identity: `complete`
- Gates: canary, contract, and verification all passed.

No successor20 proposal quality blocks were recorded:

- `quality_blocks=0`
- `proposal_quality_blocks=0`
- `quality_block_ledger_count=0`
- `verification_failure_consumed_candidates=0`

The inherited branch history still contains successor19's old
`AGENT_QUALITY_BLOCKED:CVRP_SOLVER_DESIGN_STATIC_QUALITY` marker. That is not a
new successor20 quality block.

## Mechanism

The retained candidate adds `_bounded_route_segment_exchange` to the default
VNS operator list in `policies/baseline_modules/local_search.py`.

Mechanism summary:

- screens up to 24 inter-route pairs;
- uses head/tail distance-saving promise filters;
- checks capacity compatibility for length-2 and length-3 contiguous segment
  swaps;
- attempts the top 8 promising route pairs with bounded search windows;
- accepts only strictly improving swaps and records phase/move telemetry under
  `bounded_route_segment_exchange`.

This preserves the telemetry boundary: the mechanism records activation and
accepted local-search improvement after a feasible candidate move is evaluated.

## Protocol Accounting

From
`postrun_acceptance/research_efficiency/cvrp_on_full.research_efficiency.v1.json`:

- Requested/effective rounds: `2 / 2`
- Protocol metric results: `2`
- Screening rows: `2`
- Validation rows: `0`
- Frozen rows: `0`
- Fresh-runtime replay rows: `0`
- Formal candidate artifact rows: `1`
- Proposal attempts total/consumed: `2 / 2`
- Verification consumed candidates: `2`

The postrun aggregate summary also sees the resumed branch history. For
current-run solver interpretation, use the two current metrics artifacts below.

## Screening Row 1

Metrics artifact:

```text
campaign/metrics/b0f7c15a-660c-45ad-b6f5-742ccb3868f0.json
```

Summary:

- Complete: `true`
- Pairs: `32 / 32`
- Failed pairs: `0`
- Pair counts: `5 wins / 5 losses / 22 ties`
- Median delta: `0.0`
- CI: `[0.0, 0.0]`
- Decision: `expand_screening`
- Reason: `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`
- Mechanism activation: `activation_observed`
- Objective effect status: `zero_objective_effect`

Protected and notable cases:

- `CMT2`: `1 win / 0 losses / 3 ties`, median delta `0.0`
- `CMT4`: `0 wins / 0 losses / 4 ties`, median delta `0.0`
- `A-n64-k9`: `2 wins / 2 losses / 0 ties`, median delta `-0.5`
- `B-n63-k10`: `1 win / 1 loss / 2 ties`, median delta `0.0`
- `P-n65-k10`: `1 win / 1 loss / 2 ties`, median delta `0.0`
- `X-n110-k13`: `0 wins / 0 losses / 4 ties`, median delta `0.0`

## Screening Row 2

Expanded metrics artifact:

```text
campaign/metrics/56d86ed3-6d12-4672-9fa4-1125f903e387.json
```

Summary:

- Complete: `true`
- Pairs: `48 / 48`
- Failed pairs: `0`
- Pair counts: `5 wins / 4 losses / 39 ties`
- Median delta: `0.0`
- CI: `[0.0, 0.0]`
- Decision: `continue_explore`
- Reasons:
  - `SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE`
  - `SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL`
  - `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE`
- Mechanism activation: `activation_observed`
- Objective effect status: `zero_objective_effect`

Protected and notable cases:

- `CMT2`: `1 win / 0 losses / 3 ties`, median delta `0.0`
- `CMT3`: `0 wins / 0 losses / 4 ties`, median delta `0.0`
- `CMT4`: `1 win / 0 losses / 3 ties`, median delta `0.0`
- `A-n64-k9`: `2 wins / 2 losses / 0 ties`, median delta `-0.5`
- `A-n80-k10`: `0 wins / 1 loss / 3 ties`, median delta `0.0`
- `B-n67-k10`: `0 wins / 1 loss / 3 ties`, median delta `0.0`
- `P-n76-k4`: `0 wins / 0 losses / 4 ties`, median delta `0.0`
- `E-n101-k8`: `1 win / 0 losses / 3 ties`, median delta `0.0`

All listed metrics preserve `fleet_violation=0.0` in the reported median
metric deltas.

## Runtime And Phase Evidence

Phase telemetry was observed on both rows:

- Row 1: `bounded_route_segment_exchange` weighted phase time `1671.0 ms`,
  max `109.0 ms`, over 32 runtime-observed pairs.
- Row 2: `bounded_route_segment_exchange` weighted phase time `2155.0 ms`,
  max `121.0 ms`, over 48 runtime-observed pairs.

The main runtime budget is still dominated by the embedded VNS/ALNS phases, so
the mechanism is active but not producing measurable objective lift.

## MDE Interpretation

Measurement readiness:

- `status=ready`
- `reason_code=ok`
- `mde_at_power_80=9.9`
- `n_pairs=96`
- `noise_band_p90_abs=45.5`
- `signal_to_noise_tier=low_power`

Effect-vs-MDE:

- `protocol_row_count=2`
- `positive_rows=0`
- `nonpositive_rows=2`
- `rows_at_or_above_mde=0`
- `rows_below_mde=2`
- `rows_with_ci_high_below_mde=2`
- `max_median_delta=0.0`
- `max_effect_to_mde_ratio=0.0`
- `interpretation=all_available_ci_high_below_mde`

Mechanism-family mapping:

- Family: `bounded_route_segment_exchange`
- Protocol row count: `2`
- Positive rows: `0`
- Rows at or above MDE: `0`
- Rows with CI high below MDE: `2`

## Branch State Caveat

The campaign branch card remains active:

- Branch status: `explore`
- Branch code status: `active_weak_positive`
- Branch scheduling lane: `weak_positive_followup`
- Candidate code retained: `true`
- Candidate evidence retained: `true`
- Allowed next actions include `refine_checkpoint`, `tune`, `integrate`, and
  `parameterize`.

This is a scheduler/exploration label, not a promotion claim. The same branch
card also reports median effect `[0.0, 0.0, 0.0]`, `objective_effect_status` as
`zero_objective_effect`, and runtime confidence as `low_cached_champion`.

The postrun CVRP successor checklist is also incomplete under its successor
family taxonomy: `observed_successor_families=[]` and the reported gap is
`no_successor_family_protocol_evidence`. The measurement-effect report does
map the rows to `bounded_route_segment_exchange`; the checklist gap should not
be read as an infra failure, but it is another reason not to claim v0.4 solver
success from this run.

## Interpretation

Solver conclusion: no promotion-grade effect.

Successor20 is valid, complete, and mechanism-active, but both current screening
rows have median delta `0.0`, CI `[0.0, 0.0]`, and
`rows_at_or_above_mde=0`. The protected CMT cases are not harmed, but they also
do not show a material objective improvement. There are no validation or frozen
rows, no champion promotion, and `latest_champion_version=1`.

Framework conclusion: positive for v0.4 behavior.

The run exercised repaired framework behavior:

- WSL `gpt-5.5` completion preflight and launch readiness were healthy;
- a resumed same-branch refinement stayed on the intended CVRP solver-design
  surface;
- proposal, verification, screening, postrun, and readiness stages completed;
- no new quality block or verification failure consumed the run;
- phase telemetry showed the selected mechanism was active;
- low-SNR zero-effect evidence did not promote;
- postrun/readiness artifacts were generated and marked ready.

## Next Action

Do not close v0.4 on this CVRP solver result.

Treat `bounded_route_segment_exchange` as framework-useful but solver-negative
below MDE for closeout purposes. If CVRP remains the active v0.4 blocker, the
next attempt should be a fresh, problem-owned causal path or an explicit
activation/effect repair for a materially different mechanism. Do not spend the
next WSL slot on another same-branch bounded segment refinement unless the
design first explains why a zero-median, below-MDE operator can cross the
measurement threshold.
