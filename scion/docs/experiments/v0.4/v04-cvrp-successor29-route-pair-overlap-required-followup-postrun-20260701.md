# CVRP Successor29 Required Route-Pair Overlap Follow-Up Postrun - 2026-07-01

## Run

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor29-route-pair-overlap-required-followup-server-2r-gpt55-20260701T031419Z-claw`
- Runner: server-local `claw`
- Commit: `9cfee8e3`
- Model: local `gpt-5.5`
- Forced target: `solver_design` / `modify` /
  `policies/baseline_modules/destroy_repair.py`
- Required mechanism id:
  `route_pair_overlap_removal_protected_followup`
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
- summary:
  `postrun_acceptance/summaries/cvrp_on_full.summary.json`
- readiness:
  `postrun_acceptance/readiness/cvrp_on_full.postrun_acceptance_readiness.v1.json`

## Health

- Requested rounds: `2`
- Effective rounds completed: `2`
- Effective protocol rows: `2`
- Screening protocol rows: `2`
- Proposal attempts: `2`
- Verification-consumed candidates: `2`
- Proposal quality blocks: `0`
- Telemetry failures: `0`
- Failure report: `total_failures=0`
- LLM calls: `gpt-5.5=8`

The run is operationally healthy and analysis-ready. Postrun readiness reported
no failed required or optional checks, remained report-only, and did not mutate
campaign, promotion, or scheduler state.

## Result Summary

Successor29 answered the question successor28 did not answer: the live
candidates did keep the required
`route_pair_overlap_removal_protected_followup` mechanism through formal
screening. The answer is negative for the route-pair-overlap line.

Aggregate effect-vs-MDE:

- interpretation: `protocol_effects_below_mde_or_inconclusive`
- MDE at 80% power: `9.9`
- protocol rows: `2`
- positive rows: `0`
- nonpositive rows: `2`
- rows at or above MDE: `0`
- rows below MDE: `2`
- rows with CI high below MDE: `1`
- max median delta: `-1.75`
- max effect/MDE ratio: `-0.176768`
- screening pass rate: `0.0`
- screening case wins/losses/ties: `4 / 8 / 4`
- screening pair wins/losses/ties: `21 / 29 / 14`
- champion promotions: `0`

## Protocol Rows

Row 1, `route_pair_overlap_removal_protected_followup`:

- decision: `abandon`
- gate outcome: `fail`
- win rate: `0.25`
- median delta: `-1.75`
- CI: `[-6.75, 8.5]`
- effect/MDE ratio: `-0.176768`
- mechanism evidence: activation observed, primary effect recorded positive
- reason codes:
  `SCREENING_FAIL_WIN_RATE`,
  `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP`,
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`
- key case medians:
  - `A-n64=8.5`
  - `B-n63=4.0`
  - `CMT2=-10.0`
  - `CMT4=-9.0`
  - `E-n101-k14=-4.5`
  - `M-n200=0.0`
  - `P-n65=-3.5`
  - `X-n110=22.5`

Row 2, `route_pair_overlap_removal_protected_followup`:

- decision: `abandon`
- gate outcome: `fail`
- win rate: `0.25`
- median delta: `-3.75`
- CI: `[-7.5, 12.0]`
- effect/MDE ratio: `-0.378788`
- mechanism evidence: activation observed, primary effect recorded zero
- reason codes:
  `SCREENING_FAIL_WIN_RATE`,
  `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP`,
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`,
  `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`
- key case medians:
  - `A-n64=12.0`
  - `B-n63=-5.5`
  - `CMT2=-10.0`
  - `CMT4=-6.5`
  - `E-n101-k14=-7.5`
  - `M-n200=0.0`
  - `P-n65=-2.0`
  - `X-n110=13.0`

## Interpretation

Successor29 is valid negative evidence for a protected
`route_pair_overlap_removal` follow-up. It no longer has successor28's caveat:
the required mechanism was selected and formally screened.

The protected follow-up did not preserve successor27's weak-positive aggregate
signal. A/X gains still appear in both rows, but CMT2 remains `-10.0` in both
rows, CMT4 stays negative, P-family remains negative, and the aggregate medians
turned negative. The second row also recorded direct-effect-zero telemetry.

This should park the route-pair-overlap branch for v0.4. Do not continue
unchanged `route_pair_overlap_removal`, unchanged
`route_pair_overlap_removal_protected_followup`, or adjacent endpoint/spoke
destroy variants as the next CVRP slot.

## Follow-Up

- Treat successor29 as closing the successor27 route-pair-overlap question for
  v0.4: active mechanism, formal evidence, solver-negative outcome.
- Mark `route_pair_overlap_removal_protected_followup` reviewed/default-avoid
  unless a future proposal names a materially different causal path.
- Pivot successor30 to a materially different non-seed CVRP-owned mechanism.
- Prefer a bounded local-search design slot over another destroy/repair
  clean fork unless the proposal can explain why the already-reviewed
  destroy/repair variants no longer apply.
- Keep CMT2/CMT4 in the acceptance reading for the next slot, but do not
  hardcode case ids, BKS values, seeds, split membership, or thresholds in
  solver code.
