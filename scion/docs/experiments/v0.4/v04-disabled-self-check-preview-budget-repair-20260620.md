# Disabled Self-Check Preview Budget Repair

Date: 2026-06-20

## Decision

`agentic_observation_max_chars=0` disables observation budgeting for APS
research roots. Authoritative self-check preview observations must follow that
same disabled-cap semantic; they must not be secondarily compressed through a
512-character fallback budget.

The focused v0.4 prepared roots need Contract/Smoke preview feedback to remain
visible enough for repair and analysis. `_enforce_self_check_preview_budget()`
already returned the original observation when observation caps were disabled,
but `_call_tool()` then compared the preview payload against
`_self_check_preview_budget_chars()`. With `agentic_observation_max_chars=0`,
that helper returned the minimum budget floor, so large authoritative preview
payloads could still be fitted down to an empty or budget-summary payload.

## Boundary

This is generic APS preview-budget behavior. It does not change Decision,
`DecisionFeatures`, Protocol metrics, promotion, scheduler state, problem-owned
diagnostics, or solver semantics.

## Implementation

- `_self_check_preview_budget_chars()` now returns the shared disabled-limit
  value when observation caps are disabled.
- A direct `_call_tool()` regression proves a large authoritative
  `proposal.contract_preview` payload is retained when
  `max_observation_chars=0`.

## Verification

Local:

```bash
pytest scion/scion/tests/unit/test_agentic_session_preview_budget.py::test_disabled_observation_budget_does_not_truncate_authoritative_preview -q
pytest scion/scion/tests/unit/test_agentic_session_preview_budget.py -q
pytest scion/scion/tests/unit/test_agentic_session_grounding.py scion/scion/tests/unit/test_agentic_session_surface_reads.py scion/scion/tests/unit/test_agentic_session_tool_selection.py -q
python -m py_compile scion/scion/proposal/agentic_session_common.py scion/scion/proposal/agentic_session_budget_runtime.py scion/scion/tests/unit/test_agentic_session_preview_budget.py
pytest scion/scion/tests/test_cli_run_options.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py -q
git diff --check
```

Results: `1 passed`, `11 passed`, `35 passed`, compile clean, `49 passed`, and
diff check clean.

WSL with explicit checkout `PYTHONPATH`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_session_preview_budget.py -q

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_session_grounding.py \
  scion/scion/tests/unit/test_agentic_session_surface_reads.py \
  scion/scion/tests/unit/test_agentic_session_tool_selection.py -q

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/test_cli_run_options.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py -q
```

Results: `11 passed`, `35 passed`, `49 passed`.

## Prepared Roots From This Repair

Generated on WSL at launch-authoritative runtime commit `506f9423`; the local
runtime-equivalent commit is `0264e987`. Both roots are mirrored under
`/home/clawd/research/scion-experiments/` with the same directory names.

These roots were superseded after the APS artifact budget-validation repair.
Use `scion/docs/status/current-state.md` for the current launch roots.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-506f9423-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-preflight-6r-gpt55-20260620T122341Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-506f9423-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-preflight-4r-gpt55-20260620T122341Z-claw`

Strict launch readiness for both reports:

- `static_ready=true`
- `launch_ready=false`
- exit `64`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- runtime guard OK for prepared commit `506f9423`
- `worktree_status=ok`
- `headroom_failures=[]`
- `headroom_warning_count=0`
- disabled cap detail count `18`

The remaining blocker is external `gpt-5.5` completion auth:
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`;
auth pool `active=0`, `total=1`.
