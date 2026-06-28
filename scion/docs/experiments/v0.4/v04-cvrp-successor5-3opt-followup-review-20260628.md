# CVRP Successor5 3-opt Follow-up Review

Date: 2026-06-28

## Scope

This report records the local CVRP successor5 run launched after the
problem-owned guidance update that marked unchanged `angular_sector_removal`
as reviewed/default-avoid while keeping materially different
`destroy_repair_selection` paths available.

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor5-7c6e3ea5-local-2r-gpt55-20260628T155743Z-claw-2r-gpt55-20260628T155743Z-claw`

Runtime commit: `7c6e3ea5`

Resume source:
`/home/clawd/research/scion-experiments/v04-cvrp-successor4-6a50fcba-local-2r-gpt55-20260628T142639Z-claw-2r-gpt55-20260628T142639Z-claw/campaign`

Model: local `gpt-5.5` through `127.0.0.1:8080`

## Acceptance

- Launch readiness passed before launch, including completion preflight.
- Wrapper exit status: `0`.
- Run status: valid and complete.
- Requested/effective rounds: `2/2`.
- Formal screened candidates: `2`.
- Protocol metric rows: `2`.
- Proposal attempts: `2`.
- Proposal quality blocks: `0`.
- Scheduler active-slot blocks: `0`.
- Postrun acceptance after rebuild:
  `current_run_analysis_ready=true`, `delegation_ready=true`,
  `failed_required_checks=[]`, `failed_optional_checks=[]`.

Validation commands:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python \
  scion/tools/rebuild_postrun_acceptance.py "$ROOT"

PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python \
  scion/tools/check_postrun_acceptance.py "$ROOT" \
  --require-current-run-ready --format json
```

## Research Result

The run did not promote a champion. Champion stayed `v1`, promotion count
remained `0`, and all rows stayed below the CVRP screening MDE.

The run did show the repaired research loop doing the right kind of work:
it did not repeat unchanged `angular_sector_removal`, and it produced two
formal candidates with direct mechanism activation/effect/runtime evidence.

### Round 1: radial string removal

- Mechanism: `radial_string_removal`.
- Family after postrun review: `destroy_repair_selection`.
- Target area: `policies/baseline_modules/destroy_repair.py`.
- Decision: `abandon`.
- Reason codes:
  `SCREENING_FAIL_WIN_RATE`,
  `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`.
- Win rate: `0.25`.
- Median delta: `-2.0`.
- CI: `[-7.0, 1.25]`.
- Effect-to-MDE ratio: `-0.20202`.
- CMT2 median delta: `-7.0`.
- CMT4 median delta: `-15.0`.

Postrun successor evidence marks this family checklist `proven` with outcome
`measured_no_positive_at_mde`. This is solver-negative evidence; do not repeat
the unchanged radial-string-removal path.

### Round 2: bounded intra-route 3-opt

- Mechanism: `bounded_intra_route_3opt`.
- Family after postrun review: `bounded_local_search_variant`.
- Target area: `policies/baseline_modules/local_search.py`.
- Decision: `expand_screening`.
- Reason code: `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`.
- Win rate: `0.375`.
- Median delta: `1.25`.
- CI: `[0.0, 4.0]`.
- Effect-to-MDE ratio: `0.126263`.
- CMT2 median delta: `-6.5`.
- CMT4 median delta: `3.0`.

Postrun successor evidence marks this family checklist `proven` with outcome
`measured_no_positive_at_mde`. The branch is weak-positive but below MDE, and
it remains an active follow-up candidate rather than promotion evidence.

## Repair Note

The first postrun rebuild exposed a CVRP-owned review mapping gap:
`bounded_intra_route_3opt` was present in measurement-effect rows but was not
classified as `bounded_local_search_variant` in `cvrp_successor_summary`.

The fix is problem-owned:

- Add `bounded_intra_route_3opt` and related 3-opt aliases to
  `scion.problems.cvrp.successor_review`.
- Add the same aliases to `scion.problems.cvrp.opportunity_review`.
- Add focused unit tests for successor-summary and opportunity-usage mapping.

After this repair, rebuilding the same run root reports observed successor
families `["destroy_repair_selection", "bounded_local_search_variant"]`; both
families have checklist `proven`, no missing evidence fields, and outcome
`measured_no_positive_at_mde`.

## Next Action

The next CVRP run should resume from successor5 and follow the active
`bounded_intra_route_3opt` branch only if it adds CMT2 protection and a
material mechanism refinement. The unchanged `radial_string_removal` path
should not be repeated.
