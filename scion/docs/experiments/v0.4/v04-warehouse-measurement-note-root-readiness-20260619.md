# v0.4 Warehouse Measurement-Note Root Readiness

Date: 2026-06-19

## Purpose

The warehouse production protocol had a stale comment saying the practical
delta was hard-coded and still needed future protocol-config support. Current
code already resolves `median_delta_min` through the problem-owned measurement
declaration in `problem-v1.yaml`, so the comment was corrected without changing
any protocol threshold or gate value.

Because `scion/problems/warehouse_delivery/protocol_prod.yaml` is covered by
the launch runtime guard, the earlier warehouse prepared root from WSL commit
`cf8fb5a7` is now superseded by a regenerated prepared root.

## Repair

- Local commit: `927297c4 Refresh warehouse protocol measurement note`.
- WSL commit: `19af96c2 Refresh warehouse protocol measurement note`.
- No protocol threshold changed.
- Warehouse `practical_delta_screen` and `practical_delta_validate` remain raw
  problem-owned `0.001` declarations.
- The prepared handoff still reports measurement source
  `problem_v1.measurement.calibration_ref`, metric `total_cost`, runtime model
  `comparative`, pairing validity `trajectory_divergent`, and screening MDE
  `577.5`.

Focused verification:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_config.py::test_warehouse_prod_protocol_consumes_problem_measurement_declaration \
  scion/scion/tests/test_problem_bridge.py::test_warehouse_legacy_and_package_specs_share_measurement_declaration \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Result: `10 passed in 4.64s`.

WSL verification:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent &&
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_config.py::test_warehouse_prod_protocol_consumes_problem_measurement_declaration \
  scion/scion/tests/test_problem_bridge.py::test_warehouse_legacy_and_package_specs_share_measurement_declaration \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Result: `10 passed in 2.85s`.

## Prepared Root

Measurement-note prepared root:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-measnote-19af96c2-preflight-6r-gpt55-20260619T212315Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-measnote-19af96c2-preflight-6r-gpt55-20260619T212315Z-claw`

Prepared manifest summary at creation time:

- Runtime commit: `19af96c2`.
- Rounds: `6`.
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign`.
- Model route: `gpt-5.5` at `http://127.0.0.1:8080`.
- Proposal headroom: `proposal_attempt_limit=64`,
  `proposal_quality_loop_limit=64`.
- APS headroom: `agentic_session_timeout_sec=3600`,
  `agentic_tool_max_steps=240`, `agentic_tool_max_calls=200`,
  `agentic_code_tool_max_calls=200`,
  `agentic_observation_max_chars=2000000`.

## Readiness

Strict readiness artifact:

`/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-measnote-19af96c2-preflight-6r-gpt55-20260619T212315Z-claw/readiness.strict.json`

Summary:

- `static_ready=true`
- `launch_ready=false`
- Failed check: `completion_preflight`
- Completion preflight: HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`
- Auth pool: `active=0`, `expired=1`, `total=1`
- `git_runtime_consistent=ok`
- `git_runtime_worktree_clean=ok`
- `run_script_proposal_headroom_enforced=ok`
- `run_script_pythonpath_enforced=ok`
- `run_script_runtime_guard_enforced=ok`
- `run_script_model_route_enforced=ok`
- `runtime_guard_paths_cover_problem_runtime=ok`

## Acceptance

Accepted as the warehouse measurement-note prepared-root evidence. It was later
superseded for launch by the proxy-format root refresh documented in
`scion/docs/experiments/v0.4/v04-prepared-root-refresh-after-proxy-format-alias-20260619.md`
because a runtime-guarded `scion/tools` file changed. This does not close v0.4;
warehouse still needs a live champion-v2 follow-up run showing useful post-v2
research behavior or a protocol-evaluated plateau diagnosis.
