# CVRP Successor24 Lookahead Insertion Repair In-Flight - 2026-06-30

## Status

Successor24 is running on WSL.

- Active WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor24-lookahead-insertion-repair-2r-gpt55-20260630T073830Z-claw`
- WSL runner repo:
  `/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629`
- Runner commit used by `run.sh`: `462d6e0a`
- Wrapper pid: `81009`
- Campaign pid: `81024`
- Started UTC: `2026-06-30T07:38:30Z`
- Model route: `gpt-5.5` via `http://127.0.0.1:8080`
- Pre-campaign completion preflight: `ok`, HTTP 200, authenticated local proxy
- Requested rounds: `2`
- Forced target:
  `solver_design` / `modify` /
  `policies/baseline_modules/destroy_repair.py`

Prepared handoff focus is correct:

- `current_question` names `lookahead_insertion_cost_repair`;
- `next_required_direction` identifies the mechanism as the prepared
  successor24 clean-fork design;
- `required_mechanism_ids` remains `[]`;
- required evidence includes target file
  `policies/baseline_modules/destroy_repair.py` and pre-VNS direct repair
  effect telemetry.

Early target-intent evidence is aligned:

- `mechanism_id`: `lookahead_insertion_cost_repair`
- `mechanism_family`: `destroy_repair_selection`
- `target_file`: `policies/baseline_modules/destroy_repair.py`

## Superseded Launch Attempt

The first prepared root did not enter the campaign:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor24-lookahead-insertion-repair-2r-gpt55-20260630T073154Z-claw`

It exited before campaign start with `WRAPPER_EXIT_STATUS=64` because the WSL
runner worktree was dirty under runtime guard paths:
`scion/scion :(exclude)scion/scion/tests scion/tools scion/problems/cvrp vrp`.
This is a launch hygiene failure, not CVRP experiment evidence. The fix was a
runner-local commit, `462d6e0a`, for the CVRP guidance/catalog state needed by
successor24.

## Acceptance Focus

Postrun analysis must check:

- live hypothesis and completed proposal name `lookahead_insertion_cost_repair`;
- primary target is `policies/baseline_modules/destroy_repair.py`;
- scheduler edits, if present, are only import/repair-operator registration and
  mechanism telemetry;
- telemetry records mechanism activation/runtime under
  `lookahead_insertion_cost_repair`;
- effect telemetry records direct pre-VNS repair effect, or the postrun report
  explicitly carries a missing-attribution caveat;
- formal rows are complete and interpreted against CVRP A/A MDE;
- CMT2/CMT4 case-level deltas are visible;
- postrun acceptance readiness is ready.

If the candidate drifts to scheduler q, acceptance tuning, demand-slack regret,
reviewed removal families, construction seed selection, or local-search
neighborhood expansion, classify it as `wrong-mechanism` rather than solver
evidence for successor24.
