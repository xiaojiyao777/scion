# CVRP Demand-Slack Pivot Agentic 2R Postrun

Date: 2026-06-18

## Purpose

This WSL run field-tested the CVRP provider guidance added after rejecting
unchanged `demand_slack_regret_insertion`.

Acceptance questions:

- do live target-intent and hypothesis prompts contain the demand-slack negative
  lesson;
- does the agent pivot to materially different problem-owned solver-design
  mechanisms instead of repeating demand-slack or route-merge;
- does formal screening complete with valid evidence and explicit CMT2/CMT4
  coverage;
- if the candidates fail, is the failure quality evidence rather than
  framework, runtime, telemetry, or wrapper failure.

## Run

- Commit: `28f3e5f`
- Branch: `codex/v04-evidence-repair-plan`
- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-demand-slack-pivot-agentic-2r-28f3e5f-20260618T053726Z`
- Server copy:
  `/home/clawd/research/scion-experiments/v04-cvrp-demand-slack-pivot-agentic-2r-28f3e5f-20260618T053726Z`
- Wrapper status: `finished`, `valid`, `complete`, `wrapper_exit_status=0`
- Run status: `completed_requested_rounds=true`, `last_stop_reason=max_rounds_exhausted`
- Effective rounds: `2/2`
- Champion version: `v1`
- Model: `gpt-5.5`
- Environment: WSL synchronized checkout with
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`
- Runtime policy: formal CVRP protocol with size-dependent case time limits
  (`30s` for smaller screening cases, `45s` for CMT/M/X cases in this run)

Launch used:

```bash
SCION_MODEL=gpt-5.5
SCION_BASE_URL=http://127.0.0.1:8080
SCION_API_KEY=pwd
SCION_LLM_TIMEOUT_SEC=120
SCION_LLM_CODE_TIMEOUT_SEC=240
SCION_LLM_MAX_RETRIES=1
SCION_SDK_MAX_RETRIES=0
SCION_STAGE_TRANSITION_DRAIN_LIMIT=4
SCION_PROBLEM_DATA_ROOT=/home/xjy-ubuntu/research/or-autoresearch-agent/vrp
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion
python -m scion.cli.main run \
  --problem /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem.yaml \
  --protocol /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/problems/cvrp/formal/protocol.yaml \
  --split /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/problems/cvrp/formal/split_manifest.yaml \
  --seeds /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/problems/cvrp/formal/seed_ledger.yaml \
  --campaign-dir /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-demand-slack-pivot-agentic-2r-28f3e5f-20260618T053726Z/campaign \
  --rounds 2 \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 900 \
  --measurement-governance on \
  --proposal-context-ablation compact-measurement-diagnostics \
  --disable-early-stop \
  --agentic-proposal
```

## Prompt Evidence

The repair reached both proposal stages.

- Round 1 target-intent trace
  `campaign/llm_traces/20260618T133727213693_hypothesis_target_intent_f5e93e57af_440d7e40.json`
  contains the demand-slack lesson and selected
  `policies/baseline_modules/local_search.py` /
  `cross_route_2opt_reconnect`, explicitly avoiding route-merge and unchanged
  demand-slack paths.
- Round 1 hypothesis trace
  `campaign/llm_traces/20260618T133734171387_hypothesis_261bdd0697_1df5ee1e.json`
  kept the same local-search mechanism and direct telemetry plan.
- Round 2 target-intent trace
  `campaign/llm_traces/20260618T141227738267_hypothesis_target_intent_5b3f286c30_c233896b.json`
  selected `policies/baseline_modules/destroy_repair.py` /
  `cluster_biased_worst_removal`, explicitly naming CMT2/CMT4 and avoiding
  route-merge and unchanged demand-slack logic.
- Round 2 hypothesis trace
  `campaign/llm_traces/20260618T141236026570_hypothesis_31519c46e7_9559b3fd.json`
  kept the clustered high-saving destroy mechanism.

## Candidate Sequence

Round 1 created branch `5a4ab9e7-7549-447b-b3ee-cc89dc3fe43a` and candidate
`496ab576d5b4f9bf`.

- Target files: `policies/baseline_modules/local_search.py`
- Mechanism: `cross_route_2opt_reconnect`
- Formal artifact:
  `campaign/artifacts/formal_candidates/5a4ab9e7/screening-0256ab2c-95cd-43dd-bf5a-3d2c76bea258-496ab576d5b4f9bf/candidate.patch.json`
- Metric artifact:
  `campaign/metrics/47faf3d4-b7b6-405a-93d0-d500c0b3fc39.json`
- Decision: `abandon`
- Reason codes:
  `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`
- Screening: `32/32` valid pairs, `0` failed pairs
- Pair W/L/T: `5/10/17`
- Case W/L/T: `1/3/4`
- Median total-distance delta: `0.0`
- Runtime evidence: `sufficient`, `high`
- Telemetry guard: passed; mechanism activation observed in `32/32` candidate
  runs, and direct improvement/effect telemetry positive in `23/32` runs.

Case-level notes:

- A-n64 was positive (`2/1/1`, median delta `0.5`).
- CMT2 was negative (`1/3/0`, median delta `-17.0`).
- CMT4 was mixed/tie-heavy (`1/1/2`, median delta `0.0`).
- P-n65 was negative (`0/2/2`, median delta `-3.5`).
- M-n200 and X-n110 were neutral by objective.

Round 2 created branch `58ad6aef-a332-411c-84d5-a010c8ca6260` and candidate
`982fbc22191eefdc`.

- Target files:
  `policies/baseline_modules/destroy_repair.py`,
  `policies/baseline_modules/scheduler.py`
- Mechanism: `cluster_biased_worst_removal`
- Formal artifact:
  `campaign/artifacts/formal_candidates/58ad6aef/screening-f1682073-75d0-490e-ac4c-6ea84339a627-982fbc22191eefdc/candidate.patch.json`
- Metric artifact:
  `campaign/metrics/c5729930-d45a-494f-9636-44458b4074b7.json`
- Decision: `abandon`
- Reason codes:
  `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`,
  `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`,
  `SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`,
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`
- Screening: `32/32` valid pairs, `0` failed pairs
- Pair W/L/T: `8/16/8`
- Case W/L/T: `0/4/4`
- Median total-distance delta: `-0.5`
- Runtime evidence: `insufficient`, `low_cached_champion`
- Telemetry guard: passed; mechanism activation/runtime observed in `29/32`
  candidate runs, and direct improvement/effect telemetry positive in `17/32`
  runs.

Case-level notes:

- A-n64 was mixed (`2/2/0`, median delta `7.0`).
- B-n63, E-n101, P-n65, and CMT2 were negative.
- CMT2 remained negative (`1/3/0`, median delta `-4.5`).
- CMT4 was mixed with negative median delta (`2/2/0`, median delta `-7.0`).
- M-n200 and X-n110 were objective-neutral overall.

## Conclusion

Accepted as framework evidence:

- The demand-slack provider guidance reached live target-intent and hypothesis
  prompts.
- The agent escaped unchanged demand-slack and route-merge defaults twice.
- Both proposals were material solver-design code changes with direct mechanism
  telemetry, successful contract checks, successful verification, and complete
  formal screening.
- CMT2/CMT4 were present in both screening sets.
- The run completed validly through the wrapper and campaign lifecycle.

Rejected as solver evidence:

- Neither candidate is a CVRP solver improvement.
- `cross_route_2opt_reconnect` is a negative/low-value local-search pivot
  under this exact implementation, especially on CMT2.
- `cluster_biased_worst_removal` is quality-regressive under this exact
  implementation and does not repair CMT2/CMT4.

Interpretation:

Scion is now doing more useful CVRP research than the earlier broken loop: it
can consume problem-owned lessons, choose different solver owners, generate
instrumented code, and fail candidates on complete formal quality evidence.
However, this still does not close v0.4 CVRP effective-research acceptance,
because the loop has not yet produced a continuously improving or promoted CVRP
mechanism.

## Follow-Up Repair

After this postrun, CVRP-owned provider guidance was updated again so both
prompt stages carry the post-demand-slack pivot lesson. The new guidance says
not to repeat unchanged `cross_route_2opt_reconnect` or unchanged
`cluster_biased_worst_removal` by default. If either owner is revisited, the
next hypothesis must explain a materially different causal path and explicit
CMT2/CMT4 protection. Otherwise, it should pivot to a different problem-owned
solver-design owner such as construction diversity, acceptance/temperature
policy, adaptive operator selection with direct effect attribution, or stable
algorithm entrypoint integration.

This remains proposal-only problem guidance. It does not enter
`DecisionFeatures`, Protocol selection, promotion gates, or runtime budget
policy.

Focused acceptance:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/test_cvrp_solver_design_provider.py \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py
```

Result: `61 passed`.

## Next

Run the next WSL CVRP agentic slice from a clean synchronized commit. The first
acceptance check should inspect live target-intent and hypothesis traces for
the post-demand-slack pivot lesson before interpreting the new candidate.
