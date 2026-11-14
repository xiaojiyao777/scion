# Warehouse Short Debug 3R Postrun - 2026-06-15

## Purpose

This compact ON-arm run followed the one-candidate warehouse lifecycle gate. It
tested whether the repaired warehouse path can produce multiple Protocol rows,
continue a marginal branch, and surface prompt/context evidence before any full
`3 x 24R` warehouse longrun is relaunched.

This is not a governance on/off comparison and not promotion evidence.

## Artifacts

- Launch report:
  `scion/docs/experiments/v0.4/v04-warehouse-short-debug-3r-launch-20260615.md`
- Server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-short-debug-3r-20260615T201259Z`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-short-debug-3r-20260615T201259Z`
- Commit: `dabfcee`
- Started: `2026-06-15T20:14:17Z`
- Finished: `2026-06-15T20:21:26Z`
- Exit: `0`
- Shape: `rounds=3`, local `gpt-5.5`,
  `measurement_governance=on`, `compact-measurement-diagnostics`,
  `time_limit_sec=30`, disabled early stop, corrected absolute WSL safe root.

## Validity

The run is valid and complete:

- `run_validity.status=valid`
- `requested_rounds=3`
- `effective_rounds_completed=3`
- `stopped_reason=max_rounds_exhausted`
- `protocol_metric_results=2`
- `protocol_metric_stage_counts.screening=2`
- `formal_screened_candidates=2`
- `formal_candidate_artifact_count=2`
- `verification_consumed_candidates=3`
- `verification_failure_consumed_candidates=1`
- `agentic_sessions=6`
- LLM request counts: `hypothesis=6`, `tool_selection=10`, `code=3`
- Postrun failures report: `total_failures=0`

The apparent `3R` versus `2` Protocol row mismatch is reconciled: the third
candidate consumed the requested-round budget but failed at Verification before
Protocol. Research-efficiency accounting records one
`verification_heavy` event:

```text
V9_perf_guard: too slow: case=instance_small_1.json
candidate=1421ms champion=445ms ratio=3.19x timeout=30s (limit=2x)
```

This is not missing evidence and not an infra failure.

## Candidate Trajectory

Round 1:

- Hypothesis: create `operators/subcategory_pack_upgrade.py`
- Surface: `vehicle_level`
- Mechanism: `subcategory_pack_upgrade`
- Contract: passed
- Verification: passed
- Canary: passed
- Decision: `continue_explore`
- Reason codes: `SCREENING_FAIL_WIN_RATE`,
  `SCREENING_MARGINAL_SIGNAL_CONTINUE`
- Screening case W/L/T: `1/2/7`
- Screening pair W/L/T: `5/8/7`
- Median delta: `0.0`
- Branch status after artifact: `active_marginal`

Round 2:

- Hypothesis: modify the same `operators/subcategory_pack_upgrade.py`
- Surface: `vehicle_level`
- Mechanism: `subcategory_pack_upgrade`
- Contract: passed
- Verification: passed
- Canary: passed
- Decision: `continue_explore`
- Reason codes: `SCREENING_FAIL_WIN_RATE`,
  `SCREENING_NEUTRAL_SIGNAL_CONTINUE`,
  `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE`
- Screening case W/L/T: `0/0/6`
- Screening pair W/L/T: `0/0/12`
- Median delta: `0.0`
- Branch status after artifact: `active_no_effect`

Round 3:

- Hypothesis: modify `operators/swap_orders.py`
- Surface: `order_level`
- Mechanism: `split_neutral_cost_swap`
- Contract: passed
- Verification: failed
- Failure: `V9_perf_guard`, severity `heavy`
- Status: hypothesis blacklisted before Protocol

## Branch Research

This run provides a useful small positive on branch mechanics:

- A marginal first candidate was not immediately discarded.
- The second candidate stayed on the same branch and modified the same
  `subcategory_pack_upgrade.py` mechanism.
- The second candidate converted marginal signal into no-effect, so the branch
  was downgraded to `active_no_effect`.
- The third attempt clean-forked into a different target/mechanism after low
  value pressure and material-difference guidance, then failed Verification.

This is the shape v0.4 wanted to observe, but it is not yet warehouse research
success: there was no validation/frozen row, no promotion, and no sustained
objective movement.

## Prompt And Context

Proposal-trajectory manifest summary:

- `session_count=6`
- `trace_count=19`
- `formal_candidate_joined_session_count=2`
- `missing_join_count=4`, corresponding to hypothesis-only sessions.
- Aggregate prompt chars: `932,623`
- Aggregate estimated tokens: `233,164`
- Prompt family token share:
  - `tool_selection`: `36.9414%`
  - `general`: `36.1844%`
  - `research_signal`: `12.5899%`
  - `tool_observation`: `7.4145%`
  - `governance`: `4.5612%`
  - `feedback`: `2.2302%`
  - `source_context`: `0.0828%`

Branch lesson usage projection is present in all six sessions:

- `usage_present_count=6`
- `usage_missing_count=0`
- `avoided_lessons=8`
- `contrasted_lessons=4`
- `preserved_same_branch_lesson=2`
- `rejected_weak_positive_lessons=2`
- Two traces still truncated `branch_lesson_usage_context`.

A follow-up read-only audit judged the semantic use of those lessons as weaker
than the raw presence counters suggest. In that audit, the second candidate was
the only clear branch-lesson success because it preserved the same branch and
responded to the marginal first result. The clean-fork `swap_orders.py`
hypothesis showed contrast/rejection fields and material-difference guidance,
but the branch-lesson context was truncated and the resulting candidate still
failed the V9 runtime guard. Treat this as evidence that branch lessons are
visible, not yet reliably acted on.

Code-phase source visibility is better than the aggregate `source_context`
share suggests because several source/code sections are classified as
`general`, not `source_context`. The three code prompt manifests all included
`current_champion_research_code` with full visibility. The target file content
was also present with full visibility:

- `subcategory_pack_upgrade.py` create: target section `455` chars
- `subcategory_pack_upgrade.py` modify: target section `7539` chars
- `swap_orders.py` modify: target section `1923` chars

The remaining context issue is therefore not total source absence. It is that
tool-selection and general scaffolding still dominate the visible prompt, while
compact research signals and branch lessons can still be truncated.

The read-only audit also checked the code manifests directly: each code prompt
reported `target_source_visible=true` and `required_source_satisfied=true`.
So the next context repair should target prompt economy and lesson semantic
satisfaction, not raw target-source inclusion.

## Interpretation

The short run clears the immediate warehouse post-preflight health check:
multiple candidates reached Contract/Verification/canary/Protocol, branch
continuation happened, and the third round failed closed on a concrete runtime
guard instead of producing silent bad evidence.

It does not justify relaunching the full `3 x 24R` warehouse longrun yet. The
two Protocol rows were marginal/no-effect, the third round was consumed by a
verification-heavy candidate, and prompt/context evidence still shows heavy
tool-selection/general payload.

Recommended next step:

- do a targeted guidance/context repair before full longrun;
- reduce tool-selection/general prompt overhead enough to avoid
  `branch_lesson_usage_context` truncation;
- make clean-fork branch lesson use a hard audit or quality signal, especially
  requiring contrast dimensions when leaving a no-effect branch;
- add performance-aware proposal/code guidance for order-level warehouse
  operators so candidates avoid O(n^2) or heavy recompute paths that trip
  `V9_perf_guard`;
- then run another short `3-6R` compact debug. Acceptance should require every
  requested attempt to be accounted, no verification-heavy candidate consuming
  a new direction, and visibly stronger semantic branch-lesson satisfaction
  before full `3 x 24R`.

All prompt ratios, branch lessons, runtime guard diagnostics, and warehouse
mechanism details in this report are proposal/report-only evidence and remain
outside `DecisionFeatures`.
