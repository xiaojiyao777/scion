# CVRP Route-Merge Branch-Card Transfer Agentic Postrun

Date: 2026-06-18

## Purpose

This run copied the valid `af5b5a2` route-merge transfer campaign and appended
two agentic rounds after the branch-card evidence-retention repair in commit
`9193d4e`.

The acceptance questions were:

- whether the repaired campaign still completed valid CVRP formal screening on
  WSL with the synchronized Scion checkout;
- whether later prompts could see branch lessons from the previous
  route-merge result;
- whether Scion could produce useful same-mechanism follow-up instead of
  repeating an unchanged route-merge patch.

This run did not naturally hit another `EXPAND_SCREENING` decision, so it is
not a direct field verification of the newly repaired `EXPAND_SCREENING`
branch-card path. That path remains covered by focused unit/core tests.

## Run

- Commit: `9193d4e`
- Branch: `codex/v04-evidence-repair-plan`
- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-routemerge-branchcard-transfer-agentic-2r-9193d4e-20260618T021452Z`
- Server copy:
  `/home/clawd/research/scion-experiments/v04-cvrp-routemerge-branchcard-transfer-agentic-2r-9193d4e-20260618T021452Z`
- Source campaign copied from:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-routemerge-transfer-agentic-resume1r-af5b5a2-env-20260618T0130Z/campaign`
- Wrapper status: `valid`, `complete`, `completed_requested_rounds=true`
- Time: `2026-06-18T02:14:53Z` to `2026-06-18T02:54:56Z`
- Model: all `27` LLM traces used `gpt-5.5`.
- Accounting: `requested_rounds=2`, `effective_protocol_rounds=2`,
  `protocol_metric_results=2`, `screening_protocol_results=2`,
  `proposal_attempts_total=2`.

The launch explicitly set:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion
SCION_MODEL=gpt-5.5
SCION_BASE_URL=http://127.0.0.1:8080
SCION_API_KEY=pwd
```

## Candidate Sequence

Round 1 created branch `bf7c34b0-591a-4af8-bf54-f11eb0f2789f` and candidate
`4726abc76aa80544`.

- Formal artifact:
  `campaign/artifacts/formal_candidates/bf7c34b0/screening-35cbb8b1-3fb5-422d-8ba1-6ddbce3e7a5a-4726abc76aa80544/candidate.patch.json`
- Patch digest:
  `521208f545150f00536e579df1f4ee079a45ba2fa4ee2e920210b6361d654d12`
- Decision: `abandon`
- Reason codes:
  `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP`,
  `SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`,
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`
- Screening pairs: `32/32` valid, `0` failed
- Pair W/L/T: `10/15/7`
- Case W/L/T: `1/3/4`
- Median total-distance delta: `-2.0`
- CI: `[-12.5, 0.0]`

The patch was materially different code, but it was quality-regressive and was
correctly archived.

Round 2 created branch `12d26afd-fae9-46f2-9cbb-b7b6039fed54` and candidate
`00fed907691c2249`.

- Formal artifact:
  `campaign/artifacts/formal_candidates/12d26afd/screening-392f5fcf-d58e-485e-b8cc-ae0ac4091a54-00fed907691c2249/candidate.patch.json`
- Patch digest:
  `5a9ac749e9b6b8a77acdc5a875043aba83d987e604f133ef20c9c649bd1471eb`
- Decision: `continue_explore`
- Reason codes:
  `SCREENING_FAIL_WIN_RATE`, `SCREENING_ZERO_WIN_STREAK_CONTINUE`,
  `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE`,
  `SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`,
  `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`
- Screening pairs: `32/32` valid, `0` failed
- Pair W/L/T: `0/0/32`
- Case W/L/T: `0/0/8`
- Median total-distance delta: `0.0`
- CI: `[0.0, 0.0]`
- Branch code status: `active_no_effect`
- Screening feedback tier: `no_effect`
- Telemetry outcome: `telemetry_effect_zero`

The second patch added a bounded whole-route absorption pass and scheduler
wiring, but the formal metrics show no objective effect.

## Prompt And Branch Evidence

The run verifies that later prompts can receive route-merge branch lesson
material after the repaired campaign state:

- target-intent trace
  `campaign/llm_traces/20260618T103517840473_hypothesis_target_intent_ef54d0626a_6c737b45.json`
  contains `bf7c34b0`, `lesson:09ee8abb6f7cf7ed`, and `route_merge_repair`;
- final hypothesis trace
  `campaign/llm_traces/20260618T103524804663_hypothesis_ff4a31d6d7_79953c90.json`
  contains `Branch Lesson Usage Context`, `lesson:09ee8abb6f7cf7ed`,
  `bf7c34b0`, and `route_merge_repair`;
- the generated hypothesis explicitly borrowed or contrasted visible
  route-merge lessons through `branch_lesson_usage`.

The active branch card for `12d26afd` is also populated:

- `direction=solver_design: Refine the existing route_merge_repair...`;
- `branch_mechanism_ids=["route_merge_repair"]`;
- evidence tier `no_effect`;
- `phase_activation_summary.activation_status=observed`;
- `phase_activation_summary.objective_effect_status=zero_objective_effect`;
- `why_not_promoted_reason_codes` include the zero-win and telemetry-zero
  diagnostics;
- candidate code and evidence are both retained.

This field-validates the normal `CONTINUE_EXPLORE` evidence path and confirms
that prompt visibility is no longer the immediate route-merge blocker. It does
not field-hit the repaired `EXPAND_SCREENING` path.

## Residual Issues

This run is useful framework evidence but still not CVRP solver improvement
evidence.

- The agent did transfer lessons, but it stayed in the same narrow
  `route_merge_repair` family and produced another no-effect candidate.
- The second candidate's telemetry guard passed, but direct objective effect
  was zero in all `32` screening pairs.
- Runtime evidence remained low-confidence because champion runtime came from
  cached evidence; runtime aggregates were excluded and kept as proposal/audit
  guidance only.
- While the final status branch card for the active branch is populated, the
  abandoned branch history-card projection still loses some compact fields
  that exist in the branch DB row, such as mechanism id/status. This is a
  status/projection cleanup item, not the immediate prompt blocker.
- During the long WSL screening, `run_status.json` exposed only coarse
  `running` state. Better in-flight progress visibility remains a runtime
  status-observability improvement.

## Conclusion

Accepted:

- The `9193d4e` branch-card repair did not regress WSL agentic screening.
- The copied-campaign run completed validly with `2/2` effective protocol
  rounds and all LLM traces on `gpt-5.5`.
- Route-merge branch lessons and prior branch ids were visible in later
  target-intent/hypothesis traces.
- The active branch card after `continue_explore` retained direction,
  mechanism id, evidence summary, telemetry outcome, and not-promoted reason
  codes.

Not accepted:

- No route-merge candidate is a solver improvement.
- This run does not field-verify `EXPAND_SCREENING` branch-card retention.
- CVRP effective research is still not closed: Scion can continue and reject
  evidence-backed route-merge hypotheses, but it has not yet escaped the
  low-effect route-merge loop or produced a stronger CVRP mechanism.

Next CVRP work should stop rerunning route-merge absorption variants unchanged.
Either pivot to a materially different problem-owned solver-design opportunity
or improve the proposal opportunity diagnostics so the agent can explain why
continuing route-merge is still worth a branch slot despite repeated no-effect
evidence.
