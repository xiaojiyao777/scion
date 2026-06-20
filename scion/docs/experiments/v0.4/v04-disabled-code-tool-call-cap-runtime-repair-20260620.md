# Disabled Code-Tool Call Cap Runtime Repair

Date: 2026-06-20

## Decision

`agentic_code_tool_max_calls=0` is a disabled cap. It must not mean "make zero
code-phase planner calls."

The focused warehouse and CVRP prepared roots intentionally disable proposal
and APS research caps so the agent can inspect source, revise hypotheses, and
iterate on code without early artificial ceilings. Launch readiness already
reported `agentic_code_tool_max_calls=0` as disabled, but the code-phase
proposal loop still used the raw value as an effective loop bound. That could
skip planner-selected code-phase source reads even though the prepared root was
declared no-cap.

## Boundary

This is generic APS runtime budget semantics. It does not add CVRP, warehouse,
BKS, mechanism-ranking, prompt text, or raw diagnostics to `DecisionFeatures`.
Problem-specific research signals remain problem-owned and proposal-only.

## Implementation

- `agentic_session_budget.py` now exposes `_code_tool_call_limit()` and
  `_code_tool_call_limit_enabled()` alongside the existing disabled-limit
  helpers.
- `agentic_session_code_tools.py` uses the effective disabled limit for the
  code-phase planner loop and records both configured and effective limits in
  transcript/planner metadata.
- `test_agentic_session_surface_reads.py` adds a regression proving that
  `max_code_tool_calls=0` still permits a `code_phase_planner`
  `context.read_surface` call.

## Verification

Local:

```bash
pytest scion/scion/tests/unit/test_agentic_session_surface_reads.py::test_zero_code_tool_call_budget_does_not_disable_code_phase_planner -q
pytest scion/scion/tests/unit/test_agentic_session_surface_reads.py -q
python -m py_compile scion/scion/proposal/agentic_session_budget.py scion/scion/proposal/agentic_session_common.py scion/scion/proposal/agentic_session_code_tools.py
pytest scion/scion/tests/unit/test_agentic_session_grounding.py scion/scion/tests/unit/test_agentic_session_tool_selection.py -q
pytest scion/scion/tests/test_cli_run_options.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py -q
git diff --check
```

Results: `1 passed`, `4 passed`, compile clean, `30 passed`, `49 passed`, and
diff check clean.

WSL with explicit checkout `PYTHONPATH`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_session_surface_reads.py -q

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_session_grounding.py \
  scion/scion/tests/unit/test_agentic_session_tool_selection.py -q

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/test_cli_run_options.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py -q
```

Results: `4 passed`, `30 passed`, `49 passed`.

## Prepared Roots From This Repair

These roots are superseded by the later disabled diagnosis planner cap runtime
repair. See `scion/docs/status/current-state.md` for the current launch roots.

Generated on WSL at launch-authoritative runtime commit `aa916783`; the local
runtime-equivalent commit is `a36e4604`. Both roots are mirrored under
`/home/clawd/research/scion-experiments/` with the same directory names.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-aa916783-nocaps-aps0-sourceheadroom-codecap0-preflight-6r-gpt55-20260620T115809Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-aa916783-nocaps-aps0-sourceheadroom-codecap0-preflight-4r-gpt55-20260620T115809Z-claw`

Strict launch readiness for both reports:

- `static_ready=true`
- `launch_ready=false`
- exit `64`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- runtime guard OK for prepared commit `aa916783`
- `headroom_failures=[]`
- `headroom_warning_count=0`
- disabled cap detail count `18`

The remaining blocker is external `gpt-5.5` completion auth:
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`;
auth pool `active=0`, `total=1`.
