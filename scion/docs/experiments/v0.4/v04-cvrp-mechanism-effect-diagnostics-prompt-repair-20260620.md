# v0.4 CVRP Mechanism Effect Diagnostics Prompt Repair

Date: 2026-06-20

## Purpose

Phase 2 requires CVRP proposal context to expose useful problem-owned research
signals, including residual opportunity, noise/MDE context, and mechanism-effect
ranking, without moving those facts into `DecisionFeatures`. Before this repair,
the CVRP adapter already carried measurement and opportunity diagnostics, but
several planning fields were only visible inside a broad `adapter_diagnostics`
blob.

## Change

- `CvrpAdapter.render_problem_measurement_diagnostics()` now emits a
  proposal-only `mechanism_effect_ranking` for current CVRP solver-design
  planning.
- `ContextManager` promotes safe adapter planning fields to top-level
  `problem_measurement_diagnostics`: `measurement_context`,
  `screening_headroom`, `default_avoid_directions`,
  `measurable_opportunity_classes`, and `mechanism_effect_ranking`.
- The hypothesis context profile explicitly projects those fields and keeps raw
  BKS, validation/frozen, pair-row, raw calibration, LLM-text, and prompt-ratio
  details hidden.
- Prepared prompt/context readiness now emits
  `cvrp_problem_measurement_diagnostics_prompt_bridge`, a report-only summary
  proving that the CVRP adapter diagnostics, context projection, compact
  hypothesis profile, and prompt renderer still carry
  `mechanism_effect_ranking` into hypothesis prompts.
- Launch readiness recomputes that summary from the current checkout and rejects
  missing or stale prepared summaries before launch. The summary stores only
  marker booleans, prompt-projection booleans, and counts; it does not persist
  the raw provider prompt or raw adapter diagnostics payload.

These diagnostics remain tainted proposal material. They do not change
Decision, `DecisionFeatures`, Protocol gates, lifecycle, scheduler, promotion,
solver behavior, or problem-runtime semantics.

## Verification

Local:

```bash
PYTHONPATH=scion python -m py_compile \
  scion/tools/prepared_prompt_context.py \
  scion/tools/rebuild_prepared_handoff.py \
  scion/tools/check_launch_readiness.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
# clean

PYTHONPATH=scion pytest scion/scion/tests/test_rebuild_prepared_handoff.py -q
# 3 passed

PYTHONPATH=scion pytest \
  scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_missing_cvrp_problem_measurement_diagnostics_bridge \
  scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_stale_cvrp_problem_measurement_diagnostics_summary -q
# 2 passed

PYTHONPATH=scion pytest \
  scion/scion/tests/unit/test_cvrp_measurement_diagnostics.py \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py \
  scion/scion/tests/unit/test_prompt_manifest_accounting.py \
  scion/scion/tests/unit/test_problem_measurement_artifacts.py \
  scion/scion/tests/test_postrun_artifact_inventory.py -q
# 41 passed

python -m py_compile \
  scion/scion/problems/cvrp/adapter.py \
  scion/scion/proposal/context_manager/manager.py \
  scion/scion/proposal/engine/hypothesis_context_profiles.py \
  scion/scion/tests/unit/test_cvrp_measurement_diagnostics.py
# clean
```

WSL verification for the CVRP prompt-bridge repair patch at commit `330b90e2`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/unit/test_cvrp_measurement_diagnostics.py \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py \
  scion/scion/tests/unit/test_prompt_manifest_accounting.py \
  scion/scion/tests/unit/test_problem_measurement_artifacts.py \
  scion/scion/tests/test_postrun_artifact_inventory.py -q
# 41 passed
```

## Prepared Roots

The runtime-guarded prepared roots were refreshed from WSL commit `2cf20b0f`
after the later warehouse prompt-diagnostics bridge guard and mirrored locally.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-2cf20b0f-preflight-6r-gpt55-20260620T094851Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-2cf20b0f-preflight-4r-gpt55-20260620T094851Z-claw`

Strict launch readiness for both roots reports:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`

The remaining blocker is external `gpt-5.5` proxy auth: completion preflight
returns HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`,
with auth pool `active=0`, `total=1`.
