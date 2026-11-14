# CVRP Route-Merge Pivot Guidance Agentic Postrun

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`
Commit: `ff2e652`

## Purpose

Verify that the repaired CVRP provider guidance changes live agent behavior
after the repeated low-effect `route_merge_repair` loop. This is a steering and
research-loop field check, not a promotion gate.

Acceptance for this checkpoint: the live target-intent and hypothesis traces
must either pivot away from route-merge absorption or explicitly justify a new
route-merge causal path beyond the tested guarded/local-absorption variants.

## Launch

Run root:

`/home/clawd/research/scion-experiments/v04-cvrp-route-merge-pivot-guidance-agentic-1r-gpt55-20260618T031817Z-claw`

WSL launch used:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
SCION_MODEL=gpt-5.5 \
SCION_BASE_URL=http://127.0.0.1:8080 \
SCION_API_KEY=pwd \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python scion/tools/launch_cvrp_agentic_campaign.py \
  --rounds 1 \
  --label v04-cvrp-route-merge-pivot-guidance-agentic \
  --experiments-root /home/xjy-ubuntu/research/scion-experiments \
  --python /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  --model gpt-5.5 \
  --base-url http://127.0.0.1:8080 \
  --api-key pwd \
  --launch
```

`launch.env` records `GIT_COMMIT=ff2e652`,
`PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`,
`SCION_MODEL=gpt-5.5`, `SCION_BASE_URL=http://127.0.0.1:8080`, and
`SCION_PROBLEM_DATA_ROOT=/home/xjy-ubuntu/research/or-autoresearch-agent/vrp`.

The wrapper exited `0`; `campaign/run_status.json` reports
`status=finished`, `wrapper_exit_status=0`, and
`completed_requested_rounds=true`.

## Campaign Accounting

- Requested rounds: `1`.
- Effective protocol rounds: `1`.
- Formal screening results: `1`.
- Proposal attempts: `1`.
- Verification-consumed candidates: `1`.
- Verification failure consumed candidates: `0`.
- Telemetry failed experiments: `0`.
- LLM model counts: `gpt-5.5: 7`.

Formal candidate index:

`campaign/artifacts/formal_candidates/index.jsonl`

Recorded candidate:

- `candidate_id=3d13feb2fcf565c4`
- `hypothesis_id=0728f41b-794a-4e89-85a3-7f9a46a34544`
- `branch_id=8b1621af-a5e2-4267-8245-1c521d316fc1`
- `patch_digest=e5e1fb37a66913d93a5ca0ab3bd50195e3b85679247b48a18f4dda67d08cee94`
- Diff:
  `campaign/artifacts/formal_candidates/8b1621af/screening-0728f41b-794a-4e89-85a3-7f9a46a34544-3d13feb2fcf565c4/candidate.diff`

## Steering Evidence

The field check is accepted for the route-merge pivot checkpoint.

Target-intent trace:

`campaign/llm_traces/20260618T111818785243_hypothesis_target_intent_58c6c9a83e_aac29e65.json`

Live response selected:

- `target_file=policies/baseline_modules/destroy_repair.py`
- `mechanism_id=demand_slack_regret_insertion`
- `mechanism_family=destroy_repair`

The response explicitly avoided repeated embedded-VNS scheduler variants and
route-merge absorption follow-ups, and described the mechanism as acting during
customer reinsertion rather than post-repair route merging.

Hypothesis trace:

`campaign/llm_traces/20260618T111825791721_hypothesis_8e571db58c_a221e6b2.json`

The formal hypothesis keeps the pivot: it modifies regret insertion near-ties
with a slack-aware tie-break, contrasts itself with rejected route-merge /
absorption variants, and declares telemetry for
`demand_slack_regret_insertion`.

## Screening Evidence

Formal screening was complete and valid:

- Valid pairs: `32/32`.
- Failed pairs: `0`.
- Decision: `expand_screening`.
- Reason code: `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`.
- Pair W/L/T: `13/11/8`.
- Case W/L/T: `3/2/3`.
- Gate win rate: `0.375`.
- Median delta: `0.0`.
- CI: `[-1.75, 5.0]`.
- Runtime median ratio: `0.9998465496391379`.
- Runtime median delta: `-5 ms`.
- Runtime regression rate: `0.46875`.
- Runtime evidence confidence: sufficient/high in persisted summaries.

Case-level winners:

- `A-n64-k9.vrp`: median delta `12.5`, pair counts `3/1/0`.
- `E-n101-k14.vrp`: median delta `4.0`, pair counts `3/1/0`.
- `P-n65-k10.vrp`: median delta `5.0`, pair counts `3/1/0`.

Case-level losses:

- `CMT2.vrp`: median delta `-2.5`, pair counts `1/2/1`.
- `CMT4.vrp`: median delta `-2.5`, pair counts `1/3/0`.

Pair deltas by case:

- `A-n64-k9`: `19, 16, -11, 9`.
- `B-n63-k10`: `-53, 1, 1, -3`.
- `E-n101-k14`: `4, 4, 11, -15`.
- `P-n65-k10`: `5, 5, 7, -1`.
- `CMT2`: `-30, 0, 6, -5`.
- `CMT4`: `14, -3, -2, -19`.
- `M-n200-k17`: `0, 0, 0, 0`.
- `X-n110-k13`: `-12, 0, 0, 0`.

## Telemetry Evidence

`candidate_telemetry_guard_summary` passed. Declared mechanism telemetry was
present and active:

- Declared mechanism: `demand_slack_regret_insertion`.
- Candidate runs: `32`.
- Activation fields were present and positive for candidate runs; champion
  positive count was `0`.
- Runtime field
  `solver_algorithm_phase_runtime_ms.demand_slack_regret_insertion` was present
  and positive for `32/32` candidate runs.
- Effect fields
  `solver_algorithm_phase_improvement_counts.demand_slack_regret_insertion`
  and `solver_algorithm_phase_best_delta.demand_slack_regret_insertion` were
  present and positive for candidate runs.

The branch card records:

- `status=explore_expand`
- `lineage_status=active_marginal`
- `last_screening_feedback_tier=marginal`
- `last_telemetry_outcome=case_level_positive_signal`
- `mechanism_ids=["demand_slack_regret_insertion"]`

## Interpretation

This run accepts the provider-guidance repair as a field behavior fix. Scion
escaped the stale route-merge continuation loop and generated a problem-owned,
materially different solver-design mechanism with direct telemetry and complete
formal screening evidence.

This is also positive CVRP research-loop evidence: the framework can now carry
negative branch lessons into live target selection, produce a non-route-merge
candidate, evaluate it cleanly, retain branch evidence, and mark the branch
`explore_expand` rather than promote or discard it blindly.

It is not a solver-improvement acceptance. The candidate is marginal:
`13/11/8` pair W/L/T and `3/2/3` case W/L/T, with losses on `CMT2` and `CMT4`
and a one-seed loss on `X-n110-k13`. The correct next action is same-mechanism
follow-up on `demand_slack_regret_insertion`: reduce the CMT losses while
preserving A/E/P gains and M/X neutrality. It should not trigger another broad
budget change, generic gate change, route-merge retry, or VNS-removal sweep.

## Acceptance

- Provider repair tests before this field run:
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/test_cvrp_solver_design_provider.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py scion/scion/tests/unit/test_hypothesis_context_profiles.py`
  returned `61 passed`.
- WSL synchronized checkout repeated the same focused suite with
  `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python` and returned
  `61 passed`.
- This WSL agentic field check completed with wrapper exit `0`, complete formal
  screening, and the accepted pivot behavior described above.
