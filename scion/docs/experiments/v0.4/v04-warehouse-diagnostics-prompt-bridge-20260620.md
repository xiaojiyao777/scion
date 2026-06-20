# v0.4 Warehouse Diagnostics Prompt Bridge Guard

Date: 2026-06-20

## Purpose

Warehouse v0.4 recovery depends on the agent seeing the current
validation-transfer follow-up opportunity, not only a generic plateau summary.
Before this repair, the warehouse adapter already produced problem-owned
diagnostics, but prepared prompt/readiness only proved the CVRP diagnostics
bridge. A warehouse prepared root could therefore pass static readiness while
losing the validation-transfer continuation signal before hypothesis
generation.

## Change

- `prepared_prompt_context.py` now supports
  `problem_measurement_diagnostics_prompt_summary()` for both `cvrp` and
  `warehouse_delivery`.
- Warehouse prompt summaries prove that adapter diagnostics, context payload,
  hypothesis-context projection, and prompt rendering still carry
  validation-transfer continuation signals.
- `rebuild_prepared_handoff.py` writes the warehouse-specific
  `warehouse_problem_measurement_diagnostics_prompt_bridge` readiness entry.
- `check_launch_readiness.py` recomputes the warehouse summary from the current
  checkout and rejects missing or stale summaries before launch.
- `hypothesis_context_profiles.py` keeps nested warehouse
  `opportunity_diagnostics` and `measurable_opportunity_classes` inside
  `adapter_diagnostics`, so target previews retain follow-up opportunity text
  when those diagnostics arrive only through the adapter payload.

The bridge is report/readiness proof only. It does not move warehouse semantics
into `DecisionFeatures`, Protocol gates, scheduler state, promotion, lifecycle,
or generic core decision logic.

## Verification

Local commit: `6530a4e0`.
WSL launch-authoritative commit: `2cf20b0f`.

Local:

```bash
PYTHONPATH=scion python -m py_compile \
  scion/tools/prepared_prompt_context.py \
  scion/tools/rebuild_prepared_handoff.py \
  scion/tools/check_launch_readiness.py \
  scion/scion/proposal/engine/hypothesis_context_profiles.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
# clean

PYTHONPATH=scion pytest \
  scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_missing_warehouse_problem_measurement_diagnostics_bridge \
  scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_stale_warehouse_problem_measurement_diagnostics_summary \
  scion/scion/tests/test_rebuild_prepared_handoff.py::test_rebuild_prepared_handoff_adds_warehouse_code_constraint_bridge \
  scion/scion/tests/unit/test_warehouse_target_preview.py::test_warehouse_problem_context_surfaces_validation_transfer_diagnostic -q
# 4 passed

PYTHONPATH=scion pytest \
  scion/scion/tests/unit/test_warehouse_target_preview.py \
  scion/scion/tests/unit/test_cvrp_measurement_diagnostics.py \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py -q
# 62 passed

PYTHONPATH=scion pytest scion/scion/tests/test_rebuild_prepared_handoff.py -q
# 3 passed

PYTHONPATH=scion pytest scion/scion/tests/test_launch_readiness.py -q
# 97 passed
```

WSL after applying the same patch:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/tools/prepared_prompt_context.py \
  scion/tools/rebuild_prepared_handoff.py \
  scion/tools/check_launch_readiness.py \
  scion/scion/proposal/engine/hypothesis_context_profiles.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
# clean

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_missing_warehouse_problem_measurement_diagnostics_bridge \
  scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_stale_warehouse_problem_measurement_diagnostics_summary \
  scion/scion/tests/test_rebuild_prepared_handoff.py::test_rebuild_prepared_handoff_adds_warehouse_code_constraint_bridge \
  scion/scion/tests/unit/test_warehouse_target_preview.py::test_warehouse_problem_context_surfaces_validation_transfer_diagnostic -q
# 4 passed

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/unit/test_warehouse_target_preview.py \
  scion/scion/tests/unit/test_cvrp_measurement_diagnostics.py \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py -q
# 62 passed

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/test_launch_readiness.py -q
# 97 passed
```

## Prepared Roots

The runtime-guarded prepared roots were regenerated on WSL from commit
`2cf20b0f` and mirrored locally.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-2cf20b0f-preflight-6r-gpt55-20260620T094851Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-2cf20b0f-preflight-4r-gpt55-20260620T094851Z-claw`

Strict launch readiness for both roots reports:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`

Warehouse readiness also reports all warehouse diagnostics live markers present:
`adapter_hook`, `context_payload`, `profile_projection`, and
`prompt_renderer`.

The remaining blocker is external WSL `gpt-5.5` proxy auth: completion
preflight returns HTTP `401`, `classification=not_authenticated`,
`code=invalid_api_key`, with auth pool `active=0`, `total=1`.
