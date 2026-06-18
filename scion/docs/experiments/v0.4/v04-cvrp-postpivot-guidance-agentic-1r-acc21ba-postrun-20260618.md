# CVRP Post-Pivot Guidance Agentic 1R Postrun

Date: 2026-06-18

## Purpose

This WSL field check validated the post-demand-slack pivot guidance added after
the `28f3e5f` run rejected unchanged `cross_route_2opt_reconnect` and
`cluster_biased_worst_removal`.

Acceptance questions:

- do live target-intent and hypothesis prompts contain the post-demand-slack
  pivot lesson;
- does the agent avoid unchanged demand-slack, route-merge, cross-route 2-opt,
  and cluster-biased worst-removal defaults;
- does the new candidate complete formal CVRP screening with CMT2/CMT4 present;
- if rejected, is the rejection based on complete formal quality evidence.

## Run

- Commit: `acc21ba`
- Branch: `codex/v04-evidence-repair-plan`
- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z`
- Server copy:
  `/home/clawd/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z`
- Wrapper status: `finished`, `valid`, `complete`, `wrapper_exit_status=0`
- Run status: `completed_requested_rounds=true`, `last_stop_reason=max_rounds_exhausted`
- Effective rounds: `1/1`
- Champion version: `v1`
- Model: `gpt-5.5`
- Environment: WSL synchronized checkout with
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`

## Prompt Evidence

The new provider lesson reached both live proposal stages.

- Target-intent trace:
  `campaign/llm_traces/20260618T144211482482_hypothesis_target_intent_1e475640a1_0dd3d387.json`
- Hypothesis trace:
  `campaign/llm_traces/20260618T144219534958_hypothesis_6252069250_42048cb6.json`

Both traces contain the post-demand-slack pivot lesson and mention
`cross_route_2opt_reconnect`, `cluster_biased_worst_removal`,
`demand_slack_regret_insertion`, CMT2, and CMT4. Target-intent selected a new
problem-owned owner: `policies/baseline_modules/construction.py` /
`route_limit_seed_diversification`.

## Candidate

The run created branch `7f30af37-e782-44c7-a226-c8036d35cacf` and candidate
`db20d06096d9bf15`.

- Target file: `policies/baseline_modules/construction.py`
- Mechanism: `route_limit_seed_diversification`
- Formal artifact:
  `campaign/artifacts/formal_candidates/7f30af37/screening-b42838e1-ed25-4ff3-8bd9-f902e701c00f-db20d06096d9bf15/candidate.patch.json`
- Metric artifact:
  `campaign/metrics/824b13d7-3023-4442-8349-0cd7f6f50696.json`
- Decision: `abandon`
- Reason codes:
  `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`
- Screening: `32/32` valid pairs, `0` failed pairs
- Pair W/L/T: `1/3/28`
- Case W/L/T: `0/1/7`
- Median total-distance delta: `0.0`
- Runtime evidence: `sufficient`, `high`
- Champion cache: `0` hits, `32` misses, `32` writes, so runtime comparison was
  not relying on cached champion runtime.

Case-level evidence:

- A, B, E, P, CMT4, M, and X were objective-neutral.
- CMT2 was negative: `1/3/0`, median delta `-4.5`.

Telemetry:

- Telemetry guard passed.
- `route_limit_seed_diversification` activation/runtime were observed only in
  `4/32` candidate runs, because the mechanism activates only when route-cap
  fallback construction is used.
- The telemetry diagnostic reported `effect_attribution_missing`: no direct
  effect fields were present for the mechanism, and direct objective-changing
  seed-selection effect was not demonstrated.

## Conclusion

Accepted as framework evidence:

- The `acc21ba` post-demand-slack pivot lesson was visible in live
  target-intent and hypothesis prompts.
- The agent avoided the most recent rejected defaults and selected a new
  problem-owned construction mechanism.
- Contract, verification, telemetry guard, and formal screening completed.
- CMT2/CMT4 were included in the formal screening set.

Rejected as solver evidence:

- `route_limit_seed_diversification` is no-effect/negative under this exact
  implementation.
- It activated too narrowly (`4/32` candidate runs), lacked direct effect
  attribution, and regressed CMT2.

Interpretation:

The CVRP framework loop is now capable of ingesting recent negative lessons and
steering the agent to new solver owners. The remaining blocker is mechanism
quality and opportunity diagnosis, not prompt delivery, formal screening, or
runtime execution.

## Follow-Up Repair

CVRP-owned provider guidance was updated again after this postrun so unchanged
`route_limit_seed_diversification` is not repeated as the next default. A future
construction hypothesis must explain broader formal-surface activation or a
direct objective-changing seed-selection effect with CMT2 protection; otherwise
it should pivot to a different problem-owned solver-design owner.

This remains proposal-only guidance and stays outside `DecisionFeatures`,
Protocol rules, promotion gates, and runtime budget policy.

## Next

Run the next CVRP research slice from a clean synchronized commit only after the
construction-pivot lesson is synced to WSL. First acceptance check: inspect live
target-intent and hypothesis traces for the construction-pivot lesson, then
judge the new candidate on complete formal evidence.
