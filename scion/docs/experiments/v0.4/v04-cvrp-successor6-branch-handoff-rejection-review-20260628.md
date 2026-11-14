# CVRP Successor6 Branch Handoff and Rejection Review

Date: 2026-06-28

## Scope

This report records the local successor6 run launched after the generic
resume-snapshot branch handoff repair.

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor6-dbd478af-local-2r-gpt55-2r-gpt55-20260628T172422Z-claw`

Runtime commit: `dbd478af`

Resume source:
`/home/clawd/research/scion-experiments/v04-cvrp-successor5-7c6e3ea5-local-2r-gpt55-20260628T155743Z-claw-2r-gpt55-20260628T155743Z-claw/campaign`

Model: local `gpt-5.5` through `127.0.0.1:8080`

## Acceptance

- Launch readiness passed before launch, including completion preflight.
- Wrapper exit status: `0`.
- Run status: valid and complete.
- Stop reason: `max_rounds_exhausted`.
- Requested/effective rounds: `2/2`.
- Formal screened candidates: `2`.
- Protocol metric rows: `2`.
- Proposal attempts: `2`.
- Proposal quality blocks: `0`.
- Scheduler active-slot blocks: `0`.
- Postrun acceptance:
  `current_run_analysis_ready=true`, `delegation_ready=true`,
  `failed_required_checks=[]`.
- The only failed optional check is `postrun_report_status_marker`.

Validation command:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python \
  scion/tools/check_postrun_acceptance.py "$ROOT" \
  --require-current-run-ready --format json
```

## Research Result

The run did not promote a champion. Champion stayed `v1`, and both screening
rows were below the CVRP MDE (`9.9`). Postrun measurement review reports
`rows_at_or_above_mde=0`, `positive_rows=0`, and
`interpretation=all_available_ci_high_below_mde`.

The framework behavior is useful v0.4 evidence: the prepared handoff exposed
the active weak-positive `bounded_intra_route_3opt` branch, Scion expanded it
instead of losing it, interpreted the expanded case-level result against MDE,
abandoned it after the negative expansion, transferred that lesson into a clean
fork, and then rejected the second negative mechanism.

### Round 1: bounded intra-route 3-opt expansion

- Mechanism: `bounded_intra_route_3opt`.
- Family after postrun review: `bounded_local_search_variant`.
- Target area: `policies/baseline_modules/local_search.py`.
- Protocol pairs: `48/48` valid.
- Win/loss/tie pairs: `18/22/8`.
- Median delta: `0.0` at raw-pair level; branch summary effect `-0.75`.
- Case positives: `A-n64-k9`, `B-n63-k10`, `P-n65-k10`, `CMT4`.
- Case negatives include `B-n67-k10`, `E-n101-k8`, `P-n76-k4`,
  `P-n101-k4`, and `CMT2`.
- CMT2 deltas: `[-37.0, -11.0, -2.0, 3.0]`, median `-6.5`.
- CMT4 deltas: `[17.0, 0.0, 6.0, 0.0]`, median `3.0`.
- Decision: abandoned as quality regression.
- Reason codes include `SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA`,
  `SCREENING_BORDERLINE_POLICY_FAIL_CLOSED`,
  `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP`,
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`, and `SCREENING_FAIL_WIN_RATE`.

The CVRP successor checklist is `proven`, with CMT2/CMT4 protection evidence
observed and direct activation/effect/runtime evidence observed. The outcome is
still `measured_no_positive_at_mde`, not solver progress.

### Round 2: farthest noise related removal

- Mechanism: `farthest_noise_related_removal`.
- Family after postrun review: `destroy_repair_selection`.
- Target area: `policies/baseline_modules/destroy_repair.py`.
- Protocol pairs: `32/32` valid.
- Win/loss/tie pairs: `10/17/5`.
- Median delta: `-1.0` at raw-pair level; branch summary effect `-3.0`.
- Positive case: `A-n64-k9`, median `7.0`.
- Negative cases include `B-n63-k10`, `P-n65-k10`, `CMT2`, and
  `X-n110-k13`.
- CMT2 deltas: `[-44.0, -17.0, 4.0, -7.0]`, median `-12.0`.
- CMT4 deltas: `[1.0, -24.0, -1.0, 17.0]`, median `0.0`.
- Decision: abandoned as quality regression.
- Reason codes include `SCREENING_FAIL_WIN_RATE`,
  `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP`,
  `SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`, and
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`.

This was a clean fork from the abandoned 3-opt branch: the proposal recorded
`closed_negative_bounded_intra`, changed target file from `local_search.py` to
`destroy_repair.py`, and selected a materially different destroy/repair
mechanism rather than repeating unchanged `angular_sector_removal` or
`radial_string_removal`.

## Interpretation

This run is positive framework evidence and negative solver evidence.

Accepted framework evidence:

- Resume-snapshot prepared handoff exposed the active weak-positive branch.
- In-flight Protocol status reported running pair progress without inflating
  completed counters.
- MDE-aware postrun analysis rejected noisy case-level positives.
- Branch lessons were used in the clean fork (`branch_lesson_usage` satisfied).
- CVRP-owned successor review proved evidence checklists while keeping outcome
  interpretation problem-owned and report-only.

Remaining gaps:

- No promotion or positive-at-MDE CVRP solver result.
- Current active branch after the run is the older diagnostic
  `large_instance_intra_route_two_opt_seed` repair branch, not a new promising
  solver-improvement branch.
- `research_continuity.same_mechanism_followup` reports one missed
  same-mechanism opportunity, so follow-up routing still needs review before
  claiming the CVRP loop is fully strong.
- Postrun acceptance has one optional marker gap:
  `postrun_report_status_marker`.

## Next Action

Do not repeat unchanged `bounded_intra_route_3opt`,
`farthest_noise_related_removal`, `radial_string_removal`, or
`angular_sector_removal`.

The next CVRP/VRP step should be design-first problem-owned opportunity work:
either improve CVRP opportunity guidance toward a materially different solver
mechanism with direct objective-effect telemetry, or inspect whether the
remaining `large_instance_intra_route_two_opt_seed` diagnostic branch should be
closed/reframed instead of occupying the active slot.

The next framework cleanup candidate is to move
`postrun_artifact_inventory.py::build_inventory()` into a package-owned
`scion.postrun.inventory.loader` port so the resume-snapshot current-run versus
historical-context boundary no longer lives in a large CLI compatibility script.
