# CVRP Successor28 Route-Pair-Overlap Follow-Up Postrun - 2026-07-01

## Run

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor28-route-pair-overlap-protected-followup-server-2r-gpt55-20260701T001959Z-claw`
- Runner: server-local `claw`
- Commit: `ed051d93`
- Model: local `gpt-5.5`
- Forced target: `solver_design` / `modify` /
  `policies/baseline_modules/destroy_repair.py`
- Wrapper status: `finished`, exit `0`
- Validity: `valid`
- Completeness: `complete`
- Postrun acceptance: `ready`
- Stop reason: `max_rounds_exhausted`

Postrun artifacts:

- analysis brief:
  `postrun_acceptance/analysis_brief/cvrp_on_full.postrun_analysis_brief.md`
- research efficiency:
  `postrun_acceptance/research_efficiency/cvrp_on_full.research_efficiency.v1.json`
- readiness:
  `postrun_acceptance/readiness/cvrp_on_full.postrun_acceptance_readiness.v1.json`

## Health

- Requested rounds: `2`
- Effective rounds completed: `2`
- Effective protocol rows: `2`
- Screening protocol rows: `2`
- Validation/frozen rows: `0`
- Proposal attempts: `2`
- Verification-consumed candidates: `2`
- Proposal quality blocks: `0`
- Telemetry failures: `0`
- Failure report: `total_failures=0`
- LLM calls: `gpt-5.5=8`

The run is operationally healthy and analysis-ready.

## Result Summary

Successor28 did not produce promotion-grade CVRP evidence. Both candidates
failed screening and were abandoned by lifecycle policy.

Effect-vs-MDE:

- interpretation: `protocol_effects_below_mde_or_inconclusive`
- MDE at 80% power: `9.9`
- protocol rows: `2`
- positive rows: `0`
- nonpositive rows: `2`
- rows at or above MDE: `0`
- max median delta: `-1.5`
- max effect/MDE ratio: `-0.151515`
- champion promotions: `0`

## Protocol Rows

Row 1, `boundary_spoke_outlier_removal`:

- decision: `abandon`
- gate outcome: `fail`
- win rate: `0.25`
- median delta: `-1.5`
- CI: `[-7.25, 13.0]`
- effect/MDE ratio: `-0.151515`
- reason codes:
  `SCREENING_FAIL_WIN_RATE`,
  `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP`,
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`
- key case medians:
  - `A-n64=15.5`
  - `B-n63=-9.0`
  - `CMT2=-5.5`
  - `CMT4=-8.0`
  - `E-n101-k14=-2.0`
  - `M-n200=0.0`
  - `P-n65=-1.0`
  - `X-n110=13.0`

Row 2, `edge_conflict_endpoint_removal`:

- decision: `abandon`
- gate outcome: `fail`
- win rate: `0.25`
- median delta: `-2.5`
- CI: `[-8.0, 2.0]`
- effect/MDE ratio: `-0.252525`
- reason codes:
  `SCREENING_FAIL_WIN_RATE`,
  `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP`,
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`
- key case medians:
  - `A-n64=16.5`
  - `B-n63=-2.5`
  - `CMT2=-8.0`
  - `CMT4=-12.0`
  - `E-n101-k14=-2.5`
  - `M-n200=2.0`
  - `P-n65=0.0`
  - `X-n110=-6.0`

## Interpretation

Successor28 is valid negative evidence for two alternative destroy/repair
clean forks:

- `boundary_spoke_outlier_removal`
- `edge_conflict_endpoint_removal`

It is not evidence for a successful protected same-mechanism continuation of
successor27. The live hypotheses explicitly moved away from
`route_pair_overlap_removal`:

- `boundary_spoke_outlier_removal` recorded `not_route_pair_overlap=true`.
- `edge_conflict_endpoint_removal` recorded
  `route_pair_overlap_continuation=no`.

This means successor28 should not be interpreted as closing the successor27
route-pair-overlap question. It does show that two nearby non-seed
destroy/repair alternatives are solver-negative and should be treated as
reviewed/default-avoid unless a future proposal changes the causal path
materially.

The protected-case issue remains unresolved. Both rows still lost on
`CMT2`/`CMT4`, and row 2 also regressed `X-n110`. The A-n64 gains are not enough
to rescue either mechanism because aggregate win rate stayed at `0.25` and both
median deltas were negative.

## Follow-Up

- Park unchanged `boundary_spoke_outlier_removal`.
- Park unchanged `edge_conflict_endpoint_removal`.
- Do not treat successor28 as promotion evidence or as a validation candidate.
- Do not spend another branch on broad endpoint/geometric destroy variants
  unless the proposal names a materially different causal path and direct
  objective-effect telemetry.
- If the successor27 line is still worth resolving, the next run should enforce
  a true protected `route_pair_overlap_removal` follow-up rather than another
  clean fork. Otherwise pivot to a materially different non-seed CVRP-owned
  mechanism and explicitly mark the route-pair-overlap marginal signal as
  abandoned.
