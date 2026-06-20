# Disabled Diagnosis Planner Cap Runtime Repair

Date: 2026-06-20

## Decision

When `agentic_tool_max_steps=0` and `agentic_tool_max_calls=0`, the diagnosis
planner selection loop must also treat those limits as disabled. It must not
derive a one-decision cap from `0 + 0`.

The focused v0.4 prepared roots intentionally disable APS step/tool-call caps.
The generic runtime helpers already exposed large remaining budgets for this
state, but `_run_bounded_planner_tools()` still derived
`max_planner_decisions=max(1, (max_steps + max_tool_calls) * 2)`. With no-cap
roots this became `1`, so the diagnosis planner could make only one selection
before `planner_selection_limit` took over and framework-required completion
filled the remaining generic context. That weakens agent-led research planning
even though launch readiness correctly reports the APS caps as disabled.

## Boundary

This is generic APS diagnosis-loop control-plane behavior. It does not change
Decision, `DecisionFeatures`, Protocol metrics, promotion, scheduler state, or
problem-owned solver semantics.

## Implementation

- `agentic_session_budget.py` now exposes
  `_planner_selection_decision_limit()`.
- When step/tool-call limits are enabled, the existing derived selection limit
  remains in force.
- When both limits are disabled, the planner-selection loop uses the same
  disabled-limit fuse as other APS no-cap counters.
- `test_agentic_session_grounding.py` proves a no-cap diagnosis planner can
  execute `context.list_surfaces` and then `context.read_problem` as
  planner-selected calls without hitting `planner_selection_limit`.

## Verification

Local:

```bash
pytest scion/scion/tests/unit/test_agentic_session_grounding.py::test_zero_agentic_tool_budgets_do_not_cap_diagnosis_planner_decisions -q
pytest scion/scion/tests/unit/test_agentic_session_grounding.py -q
pytest scion/scion/tests/unit/test_agentic_session_surface_reads.py scion/scion/tests/unit/test_agentic_session_tool_selection.py -q
python -m py_compile scion/scion/proposal/agentic_session_budget.py scion/scion/proposal/agentic_session_common.py scion/scion/proposal/agentic_session_planner_loop.py
pytest scion/scion/tests/test_cli_run_options.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py -q
git diff --check
```

Results: `1 passed`, `9 passed`, `26 passed`, compile clean, `49 passed`, and
diff check clean.

WSL with explicit checkout `PYTHONPATH`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_session_grounding.py -q

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_session_surface_reads.py \
  scion/scion/tests/unit/test_agentic_session_tool_selection.py -q

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/test_cli_run_options.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py -q
```

Results: `9 passed`, `26 passed`, `49 passed`.

## Current Prepared Roots

Generated on WSL at launch-authoritative runtime commit `f010f383`; the local
runtime-equivalent commit is `cd298d5b`. Both roots are mirrored under
`/home/clawd/research/scion-experiments/` with the same directory names.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-f010f383-nocaps-aps0-sourceheadroom-codecap0-plannercap0-preflight-6r-gpt55-20260620T121026Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-f010f383-nocaps-aps0-sourceheadroom-codecap0-plannercap0-preflight-4r-gpt55-20260620T121026Z-claw`

Strict launch readiness for both reports:

- `static_ready=true`
- `launch_ready=false`
- exit `64`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- `git_runtime_consistent=ok`
- runtime guard OK for prepared commit `f010f383`
- `worktree_status=ok`
- `headroom_failures=[]`
- `headroom_warning_count=0`
- disabled cap detail count `18`

The remaining blocker is external `gpt-5.5` completion auth:
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`;
auth pool `active=0`, `total=1`.
