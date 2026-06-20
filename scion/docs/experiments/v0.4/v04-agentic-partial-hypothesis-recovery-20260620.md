# v0.4 Agentic Partial Hypothesis Recovery

Date: 2026-06-20

## Summary

Scion now recovers a valid persisted
`partial_hypothesis_only` / `hypothesis_awaiting_approval` agentic artifact
after restart, instead of issuing a duplicate hypothesis-generation LLM call.
The recovery is deliberately narrow: it must match the same branch and
code-phase idempotency key, the restored hypothesis remains tainted, and normal
pipeline validation, problem-quality, follow-up, lineage/session-ref, and
ContractGate approval checks still run before code generation. Persisted
pre-approval patches are ignored and never restored.

This addresses the v0.4 audit symptom where restarted/continued campaigns could
turn one effective hypothesis into separate partial and completed agentic
sessions, increasing proposal cost and obscuring research efficiency.

During full agentic-suite verification this slice also exposed and repaired two
nearby solver-design preview drifts: algorithm-smoke counter compaction now
prioritizes path/file fields such as `solver_algorithm_path` before the counter
limit is applied, and the branch-workspace import test helper now derives the
current scheduler `local_search` import line instead of assuming an older CVRP
baseline import string.

## Changed Files

- `scion/scion/proposal/agentic_artifacts.py`
- `scion/scion/proposal/agentic_session_common.py`
- `scion/scion/core/proposal_pipeline/agentic_refs.py`
- `scion/scion/core/proposal_pipeline/agentic_lifecycle.py`
- `scion/scion/proposal/tools/previews/algorithm_smoke_feedback_runtime.py`
- `scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py`
- `scion/scion/tests/unit/test_agentic_solver_design_branch_workspace_imports.py`

## Boundary Check

- LLM/artifact content remains tainted proposal material.
- Recovery is not Decision input and does not touch `DecisionFeatures`.
- The generic core recovery check validates generic session identity; problem
  quality and semantics remain in existing problem-owned validators.
- Code generation still requires a ContractGate-approved hypothesis through the
  existing code-context builder.

## Verification

Local focused checks passed:

- `python -m py_compile scion/scion/proposal/agentic_artifacts.py scion/scion/proposal/agentic_session_common.py scion/scion/core/proposal_pipeline/agentic_refs.py scion/scion/core/proposal_pipeline/agentic_lifecycle.py scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py`
- `pytest -q scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py -k 'recovers_waiting_hypothesis or rejects_stale_partial_hypothesis_key'`
- `pytest -q scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py scion/scion/tests/unit/core/test_proposal_pipeline_session_controls.py`
- `pytest -q scion/scion/tests/unit/test_agentic_session_artifacts_replay.py scion/scion/tests/unit/test_agentic_observation_ledger.py`
- `pytest -q scion/scion/tests/unit/core`
- `pytest -q scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py::test_algorithm_smoke_runs_tainted_synthetic_preview_without_promotion scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py::test_algorithm_smoke_runs_solver_design_module_patch_through_entrypoint scion/scion/tests/unit/test_agentic_solver_design_branch_workspace_imports.py::test_contract_preview_resolves_same_patch_solver_design_imports`
- `pytest -q $(find scion/scion/tests/unit -maxdepth 1 -name 'test_agentic*.py' -print | sort)`
- `git diff --check`

WSL checks used the current synchronized checkout explicitly:

- `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile scion/scion/proposal/agentic_artifacts.py scion/scion/proposal/agentic_session_common.py scion/scion/core/proposal_pipeline/agentic_refs.py scion/scion/core/proposal_pipeline/agentic_lifecycle.py scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py`
- `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py -k 'recovers_waiting_hypothesis or rejects_stale_partial_hypothesis_key'`
- `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/unit/test_agentic_session_artifacts_replay.py scion/scion/tests/unit/test_agentic_observation_ledger.py scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py scion/scion/tests/unit/core/test_proposal_pipeline_session_controls.py`
- `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/unit/core`
- `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py::test_algorithm_smoke_runs_tainted_synthetic_preview_without_promotion scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py::test_algorithm_smoke_runs_solver_design_module_patch_through_entrypoint scion/scion/tests/unit/test_agentic_solver_design_branch_workspace_imports.py::test_contract_preview_resolves_same_patch_solver_design_imports`
- `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q $(find scion/scion/tests/unit -maxdepth 1 -name 'test_agentic*.py' -print | sort)`

Important WSL note: the `scion` conda environment has an editable install that
points at `/home/xjy-ubuntu/projects/scion`. Tests and launch/readiness checks
for this repository must set `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`
or otherwise assert the import source before treating results as authoritative.

## Operational Impact

Existing prepared roots predate this repair. After `gpt-5.5` completion auth is
refreshed, refresh the warehouse and CVRP prepared roots before launch so the
runtime checkout includes partial-hypothesis recovery.
