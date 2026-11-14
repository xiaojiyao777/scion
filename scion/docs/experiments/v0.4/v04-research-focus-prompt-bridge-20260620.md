# v0.4 Prepared Research-Focus Prompt Bridge Guard

Date: 2026-06-20

## Purpose

Prepared `research_focus` projection readiness proved that problem-owned launch
guidance survived deterministic projection into `launch_research_focus`, but it
did not content-check the rendered hypothesis prompt path. That left a launch
gap: a prepared root could carry the right manifest fields and projection
summary while the compact proposal prompt omitted the research focus that the
agent must actually see.

## Change

- `prepared_prompt_context.py` now builds a prompt-safe
  `research_focus_prompt_summary()` from the prepared manifest and the current
  hypothesis prompt renderer.
- `rebuild_prepared_handoff.py` writes this summary under
  `prepared_research_focus_prompt_bridge.detail.prompt_summary`.
- `check_launch_readiness.py` recomputes the summary from the current checkout
  and rejects missing or stale summary fields before launch.
- The prompt summary now records item counts and rendered-item counts for
  prepared guidance lists: warehouse required evidence/default avoid directions,
  CVRP measurable opportunity classes, large-two-opt implementation/evidence/
  reject lists, and CMT2/CMT4 case-protection rules/evidence. Static readiness
  rejects key-only prompt projections where the field name appears but the
  actionable list items are missing.
- The summary persists only schema, boolean, count, and path evidence. It does
  not persist raw provider prompts, raw problem diagnostics, quality judgments,
  campaign mutations, scheduler mutations, promotion mutations, or
  `DecisionFeatures`.

## Verification

Local code commit: `2a89ba30`.
WSL launch-authoritative commit: `8ba1f09d`.

Local:

```bash
PYTHONPATH=scion python -m py_compile \
  scion/tools/prepared_prompt_context.py \
  scion/tools/rebuild_prepared_handoff.py \
  scion/tools/check_launch_readiness.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
# clean

PYTHONPATH=scion pytest \
  scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_missing_research_focus_prompt_summary \
  scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_stale_research_focus_prompt_summary \
  scion/scion/tests/test_rebuild_prepared_handoff.py::test_rebuild_prepared_handoff_refreshes_problem_specific_coverage \
  scion/scion/tests/test_rebuild_prepared_handoff.py::test_rebuild_prepared_handoff_adds_warehouse_code_constraint_bridge -q
# 4 passed

PYTHONPATH=scion pytest scion/scion/tests/test_rebuild_prepared_handoff.py -q
# 3 passed

PYTHONPATH=scion pytest scion/scion/tests/test_launch_readiness.py -q
# 142 passed
```

WSL after applying the same patch:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/tools/prepared_prompt_context.py \
  scion/tools/rebuild_prepared_handoff.py \
  scion/tools/check_launch_readiness.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
# clean

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_missing_research_focus_prompt_summary \
  scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_stale_research_focus_prompt_summary \
  scion/scion/tests/test_rebuild_prepared_handoff.py::test_rebuild_prepared_handoff_refreshes_problem_specific_coverage \
  scion/scion/tests/test_rebuild_prepared_handoff.py::test_rebuild_prepared_handoff_adds_warehouse_code_constraint_bridge -q
# 4 passed

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/test_rebuild_prepared_handoff.py -q
# 3 passed

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/test_launch_readiness.py -q
# 142 passed
```

## Prepared Roots

Regenerated on WSL from commit `8ba1f09d` and mirrored locally.

Warehouse:

- WSL:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-8ba1f09d-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-fullsurf-prompt96k-symbolcache-nonsolverfacts-focusitems-preflight-6r-gpt55-20260620T140918Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-8ba1f09d-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-fullsurf-prompt96k-symbolcache-nonsolverfacts-focusitems-preflight-6r-gpt55-20260620T140918Z-claw`

CVRP:

- WSL:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-8ba1f09d-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-fullsurf-prompt96k-symbolcache-nonsolverfacts-focusitems-preflight-4r-gpt55-20260620T140919Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-8ba1f09d-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-fullsurf-prompt96k-symbolcache-nonsolverfacts-focusitems-preflight-4r-gpt55-20260620T140919Z-claw`

Strict launch readiness for both roots exits `64` because completion preflight
is required and external auth is unavailable, but static launch readiness is
clean:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- completion auth: HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`; auth pool `active=0`, `total=1`

Prompt summary evidence:

- Warehouse summary schema:
  `scion.prepared_research_focus_prompt_summary.v1`.
- Warehouse renders all 19 required `research_focus` paths with
  `missing_rendered_paths=[]`, `warehouse_v2_followup_present=true`,
  `warehouse_current_question_present=true`,
  `warehouse_required_evidence_present=true`,
  `warehouse_required_evidence_item_count=5`,
  `warehouse_required_evidence_rendered_count=5`,
  `warehouse_avoid_directions_present=true`, and
  `warehouse_default_avoid_direction_item_count=6`,
  `warehouse_default_avoid_direction_rendered_count=6`, and
  `warehouse_measurement_handoff_present=true`.
- CVRP summary schema:
  `scion.prepared_research_focus_prompt_summary.v1`.
- CVRP renders all 36 required `research_focus` paths with
  `missing_rendered_paths=[]`, `cvrp_case_protection_present=true`,
  `cvrp_bounded_twoopt_present=true`, `cvrp_direct_effect_rules_present=true`,
  `cvrp_measurement_handoff_present=true`,
  `cvrp_measurable_opportunity_class_rendered_count=5`,
  `cvrp_large_twoopt_required_pair_evidence_rendered_count=5`, and
  `cvrp_case_protection_required_evidence_rendered_count=3`.
- Both summaries report `launch_focus_schema_present=true`,
  `launch_focus_taint_present=true`, `prompt_section_present=true`,
  `compact_prompt_value_present=true`,
  `launch_research_focus_key_present=true`,
  `forbidden_prompt_tokens_present=[]`, `raw_prompt_excluded=true`,
  `report_only=true`, and `decision_features_excluded=true`.

## Boundary Check

This bridge is launch-readiness evidence only. It proves that problem-owned
proposal guidance reaches the compact hypothesis prompt, but the guidance
remains tainted report-only material. It does not enter Decision,
`DecisionFeatures`, Protocol gates, scheduler state, promotion input, lifecycle
policy, or solver semantics.

## Next Step

Refresh the WSL/local proxy login, rerun strict launch readiness until
`launch_ready=true`, then launch the warehouse champion-v2 follow-up first.
