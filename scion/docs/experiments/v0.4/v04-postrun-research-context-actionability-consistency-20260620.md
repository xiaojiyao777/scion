# v0.4 Postrun Research Context Actionability Consistency

Date: 2026-06-20

Status: accepted as a report-only postrun-readiness repair.

## Reason

Postrun readiness already required prompt-context visibility, prompt signal
density accounting, a formal hypothesis-generation prompt trace, and research
context actionability evidence. It did not verify that
`research_context_actionability_summary.indicators`, gaps, and recommendations
were freshly projected from the same `prompt_context_visibility_summary` and
`research_continuity_summary` review inputs.

That left a delegated-review gap: stale actionability summaries could hide
prompt token, branch-continuity, branch-lesson, or weak-positive projection
drift while the underlying review inputs had changed.

## Change

- `scion/tools/check_postrun_acceptance.py` now recomputes the report-only
  research-context actionability projection from prompt visibility and research
  continuity inputs during readiness.
- The `research_context_actionability` check now rejects mismatches in
  current-run availability, guidance status, actionability gaps,
  recommendations, continuity counts, semantic branch-lesson count maps,
  prompt signal-density tokens, omitted/truncated prompt trace counts, and
  research-plus-source/governance ratio.
- `scion/scion/tests/test_check_postrun_acceptance.py` adds a regression test
  that poisons only the actionability projection while leaving the underlying
  prompt and continuity inputs intact.

Boundary: this remains postrun/reporting validation only. It does not enter
`DecisionFeatures`, Protocol gates, scheduler state, promotion, or problem
solver semantics.

## Verification

Local:

- `python -m py_compile scion/tools/check_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py -k stale_research_context_actionability_projection`
  passed: `1 passed, 51 deselected`.
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py`
  passed: `52 passed`.
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_postrun_analysis_brief.py`
  passed: `87 passed`.
- After local commit `d80be754`, `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_postrun_analysis_brief.py`
  passed: `175 passed`.

WSL:

- `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_check_postrun_acceptance.py -k stale_research_context_actionability_projection`
  passed: `1 passed, 51 deselected`.
- `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_postrun_analysis_brief.py`
  passed: `87 passed`.
- After WSL commit `7c80f84b`, `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_postrun_analysis_brief.py`
  passed: `175 passed`.

Commits:

- Local: `d80be754`
- WSL runtime checkout: `7c80f84b`

## Prepared Root Refresh

Because `scion/tools` is part of the runtime guard set, the active prepared
roots were regenerated from WSL commit `7c80f84b` before launch:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ctxproj-7c80f84b-preflight-6r-gpt55-20260620T020853Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-ctxproj-7c80f84b-preflight-4r-gpt55-20260620T020854Z-claw`

Both roots were mirrored locally under `/home/clawd/research/scion-experiments/`.
Strict launch readiness for both roots reports:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- completion preflight HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`, auth pool `active=0`, `refreshing=1`, `total=1`

No campaign was launched. Refresh the WSL/local proxy login and rerun strict
launch readiness before starting warehouse, then CVRP.
