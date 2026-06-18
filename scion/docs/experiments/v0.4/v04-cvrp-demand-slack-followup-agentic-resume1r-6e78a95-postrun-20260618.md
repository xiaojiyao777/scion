# CVRP Demand-Slack Follow-Up Copied-Campaign Postrun

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`
Run commit: `6e78a95`
Postrun repair commit: `a81b77f`

## Purpose

Run a real copied-campaign continuation of the active
`demand_slack_regret_insertion` branch produced by the `ff2e652` CVRP provider
pivot check. The checkpoint was not promotion. The checkpoint was whether the
same mechanism could reduce the prior `CMT2`/`CMT4` losses while preserving the
A/E/P gains and M/X neutrality.

## Artifacts

- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-demand-slack-followup-agentic-resume1r-6e78a95-20260618T042015Z-claw`
- Synced server run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-demand-slack-followup-agentic-resume1r-6e78a95-20260618T042015Z-claw`
- Source copied campaign:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-route-merge-pivot-guidance-agentic-1r-gpt55-20260618T031817Z-claw/campaign`
- Raw metrics:
  `campaign/metrics/60400f57-b626-4ced-96de-0ff89c0367d3.json`
- Branch/hypothesis:
  `branch_id=8b1621af-a5e2-4267-8245-1c521d316fc1`,
  `hypothesis_id=0728f41b-794a-4e89-85a3-7f9a46a34544`.

## Launch

The run copied only the prior `campaign/` directory into a new run root and ran:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
SCION_MODEL=gpt-5.5 \
SCION_BASE_URL=http://127.0.0.1:8080 \
SCION_API_KEY=pwd \
SCION_STAGE_TRANSITION_DRAIN_LIMIT=4 \
SCION_PROBLEM_DATA_ROOT=/home/xjy-ubuntu/research/or-autoresearch-agent/vrp \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m scion.cli.main run \
  --problem scion/problems/cvrp/problem.yaml \
  --protocol scion/problems/cvrp/formal/protocol.yaml \
  --split scion/problems/cvrp/formal/split_manifest.yaml \
  --seeds scion/problems/cvrp/formal/seed_ledger.yaml \
  --campaign-dir /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-demand-slack-followup-agentic-resume1r-6e78a95-20260618T042015Z-claw/campaign \
  --rounds 1 \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 900 \
  --measurement-governance on \
  --proposal-context-ablation full \
  --disable-early-stop \
  --agentic-proposal
```

## Validity

- Wrapper exit: `0`.
- `run_validity_status=valid`.
- `completed_requested_rounds=true`.
- `requested_rounds=1`.
- `effective_protocol_rounds=1`.
- `protocol_metric_results=1`.
- `screening_protocol_results=1`.
- Failed pairs: `0`.

## Result

The copied-campaign continuation successfully resumed the existing active
branch and ran expanded screening. It did not improve the solver.

Canonical branch evidence summary:

- Tier: `quality_regression`.
- Final branch state: `parked_lineage`.
- Hypothesis status: `rejected`.
- Pair W/L/T: `16/28/4`.
- Case W/L/T: `3/6/3`.
- Median delta: `-3.75`.
- CI: `[-7.0, 1.75]`.
- Runtime median ratio: `0.9925414788228181`.
- Runtime median delta: `-185 ms`.
- Runtime regression rate: `0.3958333333333333`.
- Runtime evidence confidence/status: `sufficient`.
- Decision/lifecycle reason codes included
  `SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA`,
  `SCREENING_BORDERLINE_POLICY_FAIL_CLOSED`,
  `BRANCH_LIFECYCLE_PARK_LINEAGE`,
  `SCREENING_SOFT_ABANDON_LOSS_HEAVY_FOLLOWUP`,
  `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`, and
  `SCREENING_FAIL_WIN_RATE`.

Case-level positive signals remained only on:

- `A-n64-k9.vrp`: delta `+12.5`, W/L/T `3/1/0`.
- `A-n80-k10.vrp`: delta `+3.5`, W/L/T `3/1/0`.
- `E-n101-k14.vrp`: delta `+4.0`, W/L/T `3/1/0`.

Clear negative cases included:

- `B-n67-k10.vrp`: delta `-8.0`, W/L/T `1/3/0`.
- `E-n101-k8.vrp`: delta `-8.5`, W/L/T `0/4/0`.
- `P-n76-k4.vrp`: delta `-5.0`, W/L/T `1/3/0`.
- `P-n101-k4.vrp`: delta `-5.5`, W/L/T `1/3/0`.
- `CMT3.vrp`: delta `-8.5`, W/L/T `0/4/0`.
- `CMT4.vrp` also remained negative by direct pair aggregation:
  deltas `[14.0, -3.0, -2.0, -19.0]`.

The expanded screening set did not include `CMT2.vrp`, even though `CMT2` was a
prior negative case and is present in the screening split. Therefore this run
partially, not fully, satisfied the intended `CMT2`/`CMT4` follow-up target:
`CMT4` was retested and remained negative; `CMT2` was not retested.

## Framework Findings

This run is useful negative research-loop evidence. It proves that copied
campaign continuation can execute same-branch expanded screening and fail-close
a weak branch with evidence.

It also exposed two resume-state gaps:

- Before commit `6e78a95`, copied-campaign reopen restored the branch/workspace
  but not the active hypothesis. A first smoke run failed closed immediately
  with `no hypothesis for eval step - abandoning` and produced no Protocol
  rows.
- The valid `6e78a95` run restored the active hypothesis and completed
  screening, but the reconciled candidate artifact was omitted with
  `missing_patch` / `missing_replay_identity` because the in-memory patch object
  was not restored.

Both gaps are now covered by the campaign reopen repair note:
`scion/docs/experiments/v0.4/v04-campaign-reopen-active-branch-restore-repair-20260618.md`.
Commit `a81b77f` adds patch restoration from existing `candidate.patch.json`;
focused tests passed locally and on WSL (`53 passed`), and a real artifact
restore smoke recovered the `destroy_repair.py` primary patch plus
`scheduler.py` support patch from the original pivot campaign.

## Conclusion

The `demand_slack_regret_insertion` branch should not continue unchanged. The
expanded evidence is loss-heavy and the lifecycle correctly parked the lineage.
Next CVRP work should avoid broad budget/gate changes and avoid returning to
route-merge absorption. It should either repair branch-specific follow-up case
targeting so prior negative cases such as `CMT2` stay in scope, or pivot to a
materially different problem-owned solver-design mechanism with explicit
CMT4/CMT2 coverage in the acceptance check.
