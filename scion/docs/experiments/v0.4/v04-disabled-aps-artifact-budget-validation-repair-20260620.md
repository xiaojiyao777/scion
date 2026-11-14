# Disabled APS Artifact Budget Validation Repair

Date: 2026-06-20

## Decision

For focused v0.4 APS research roots, zero step/tool/observation caps mean the
cap is disabled. Artifact replay validation must follow that runtime and
launch-readiness semantic. A session artifact with
`max_steps=0`, `max_tool_calls=0`, or `max_observation_chars=0` must not be
rejected merely because the agent actually used tools or retained observations.

## Issue

`validate_agentic_session_artifact()` still treated every non-negative
configured maximum as an enforced ceiling. That meant current no-cap roots could
run valid tool-rich agentic sessions and later have their APS artifact rejected
as `tool budget exceeded` during replay/audit validation.

This was a postrun evidence risk, not a Decision or Protocol rule: it could make
valid no-cap research trajectories look invalid after the run.

## Boundary

This repair changes only generic APS artifact replay/audit validation. It does
not change Decision, `DecisionFeatures`, Protocol metrics, promotion,
scheduler state, problem-owned diagnostics, solver semantics, or positive
budget enforcement for configured caps greater than zero.

## Implementation

- APS artifact validation now compares `tool_budget_used` against
  `tool_loop_config` only when the configured max is greater than zero.
- A regression artifact with zero max step/tool/observation caps and positive
  used counts now validates successfully.
- The existing positive-cap over-budget regression still rejects exceeded
  budgets.

## Verification

Local:

```bash
pytest scion/scion/tests/unit/test_agentic_session_artifacts_replay.py::test_agentic_replay_validator_treats_zero_budget_limits_as_disabled -q
python -m py_compile scion/scion/proposal/agentic_artifacts.py scion/scion/tests/unit/test_agentic_session_artifacts_replay.py
pytest scion/scion/tests/unit/test_agentic_session_artifacts_replay.py -q
pytest scion/scion/tests/unit/test_agentic_session_budget_limits.py scion/scion/tests/unit/test_agentic_session_preview_budget.py -q
pytest scion/scion/tests/unit/test_agentic_session_grounding.py scion/scion/tests/unit/test_agentic_session_surface_reads.py scion/scion/tests/unit/test_agentic_session_tool_selection.py -q
pytest scion/scion/tests/test_cli_inspect_agentic.py scion/scion/tests/unit/test_agentic_session_artifacts_replay.py -q
git diff --check
```

Results: `1 passed`, compile clean, `14 passed`, `21 passed`, `35 passed`,
`23 passed`, and diff check clean.

WSL with explicit checkout `PYTHONPATH` and launch Python:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/tests/unit/test_agentic_session_artifacts_replay.py -q

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/tests/test_cli_inspect_agentic.py \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/tests/unit/test_agentic_session_budget_limits.py \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/tests/unit/test_agentic_session_preview_budget.py -q
```

Results: `14 passed`, `30 passed`.

## Prepared Roots From This Repair

Generated on WSL at launch-authoritative runtime commit `7993da30`; the local
runtime-equivalent commit is `68118222`. Both roots are mirrored under
`/home/clawd/research/scion-experiments/` with the same directory names.

These roots were superseded after the code-phase planner reserve repair. Use
`scion/docs/status/current-state.md` for the current launch roots.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-7993da30-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-preflight-6r-gpt55-20260620T123708Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-7993da30-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-preflight-4r-gpt55-20260620T123724Z-claw`

Strict launch readiness for both reports:

- `static_ready=true`
- `launch_ready=false`
- exit `64`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- prompt context readiness `ok`
- runtime guard `ok` for prepared commit `7993da30`

The remaining blocker is external `gpt-5.5` completion auth:
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`;
auth pool `active=0`, `total=1`.
