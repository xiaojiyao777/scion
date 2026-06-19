# v0.4 APS Tool-Loop Headroom Readiness

Date: 2026-06-19

## Purpose

Focused warehouse/CVRP v0.4 launches must not be stopped by hidden APS
tool-loop limits before the agent can inspect source, reason through the active
subject, and produce useful proposal/code evidence. This repair keeps generic
defaults unchanged unless explicitly configured, then makes the focused
launchers pass and declare higher APS headroom.

## Repair

- Local commit: `38ae0c65` (`Raise APS headroom for focused v0.4 launches`).
- WSL commit: `e69d6e53` (`Raise APS headroom for focused v0.4 launches`).
- `scion run` now accepts explicit APS controls:
  `--agentic-tool-max-steps`, `--agentic-tool-max-calls`, and
  `--agentic-observation-max-chars`.
- Focused warehouse/CVRP launchers now default to:
  `agentic_session_timeout_sec=3600`, `agentic_tool_max_steps=240`,
  `agentic_tool_max_calls=200`,
  `agentic_observation_max_chars=2000000`,
  `proposal_attempt_limit=64`, and `proposal_quality_loop_limit=64`.
- Launch readiness verifies these values across `launch.env`, prepared manifest
  execution, prepared manifest command, and `run.sh`.

## Verification

Local:

```bash
PYTHONPATH=scion python -m py_compile \
  scion/scion/core/proposal_pipeline/agentic_requests.py \
  scion/scion/core/proposal_pipeline/facade.py \
  scion/scion/core/campaign.py \
  scion/scion/core/campaign_composition.py \
  scion/scion/cli/commands/init_run.py \
  scion/tools/launch_warehouse_agentic_campaign.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/check_launch_readiness.py \
  scion/tools/postrun_artifact_inventory.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_cli_run_options.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_session_controls.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
```

Result: `224 passed in 47.90s`.

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q \
  scion/scion/tests/test_cli_run_options.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_session_controls.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
```

Result: `224 passed in 31.86s`.

## Prepared Roots

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-toolheadroom-e69d6e53-6r-gpt55-20260619T200840Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-toolheadroom-e69d6e53-1r-gpt55-20260619T200841Z-claw`

Both roots report:

- `static_ready=true`
- `launch_ready=false`
- `run_script_proposal_headroom_enforced=ok`
- `git_runtime_worktree_clean=ok`
- APS headroom values:
  `3600`/`240`/`200`/`2000000`
- Proposal headroom values: `64`/`64`

The remaining launch blocker is external WSL `gpt-5.5` provider auth. Strict
preflight returns HTTP `401`, `classification=not_authenticated`,
`code=invalid_api_key`, with auth pool `active=0`, `refreshing=1`, `total=1`.

## Prompt Bridge Check

Prepared prompt-context readiness remains report-only and excludes raw provider
payloads from DecisionFeatures:

- Warehouse active-subject provider summary:
  `warehouse_operator_validation_transfer_code_constraints.v1`,
  constraints `5`, forbidden patterns `5`, total guidance items `10`.
- CVRP active-subject provider summary:
  `cvrp_solver_design_code_constraints.v1`, constraints `2`,
  object-model hints `3`, API contracts `2`, forbidden patterns `6`,
  total guidance items `13`.
