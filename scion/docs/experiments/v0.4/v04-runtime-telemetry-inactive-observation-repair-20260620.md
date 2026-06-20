# Runtime Telemetry Inactive Observation Repair

Date: 2026-06-20
Branch: `codex/v04-evidence-repair-plan`

## Purpose

Make telemetry guard summaries distinguish explicit inactive mechanism
telemetry from numeric zero counters. This keeps agent-facing diagnostics from
collapsing `mechanism_active=false` into ordinary no-effect or zero-runtime
evidence.

## Issue

Runtime audit can fail required `*_active` fields when they are present but
false, while telemetry guard summaries previously counted the same values only
as `candidate_zero`. Delegated review and proposal feedback could therefore see
"zero-valued" evidence without knowing that the mechanism was explicitly not
triggered.

## Repair

- `scion.runtime.telemetry_guard.evidence` now recognizes explicit false
  scalar values (`False`, `false`, `disabled`, `off`, `no`) without treating
  numeric `0` counters as false.
- Runtime field summaries now carry `candidate_false` while preserving
  `candidate_zero` for backward-compatible zero-valued accounting.
- Mechanism diagnostics report activation status `inactive` when activation
  evidence is present but explicitly false.
- Guard issues and repair guidance carry the inactive distinction so prompts
  steer toward trigger, threshold, or mechanism-id wiring review instead of
  fake activation or effect-strength tuning.

## Boundary Check

This is generic runtime telemetry accounting and report/guidance text. It does
not change Protocol gates, Decision, `DecisionFeatures`, scheduler state,
promotion, or problem solver semantics.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/unit/test_runtime_telemetry_guard.py \
  scion/scion/tests/unit/test_runtime_telemetry_guard_mechanism_diagnostics.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/unit/core/test_evaluation_pipeline.py \
  scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py \
  scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/unit/test_runtime_telemetry_guard.py \
  scion/scion/tests/unit/test_runtime_telemetry_guard_mechanism_diagnostics.py \
  scion/scion/tests/test_protocol_surface_runtime.py \
  scion/scion/tests/unit/core/test_evidence_recorder_redaction_lineage.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke_feedback.py \
  scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py \
  scion/scion/tests/unit/test_agentic_proposal_tools_context.py
```

Results: `34 passed`, `90 passed`, `57 passed`, `109 passed`, `65 passed`.

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/unit/test_runtime_telemetry_guard.py \
  scion/scion/tests/unit/test_runtime_telemetry_guard_mechanism_diagnostics.py \
  scion/scion/tests/test_protocol_surface_runtime.py \
  scion/scion/tests/unit/core/test_evidence_recorder_redaction_lineage.py

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/unit/core/test_evaluation_pipeline.py \
  scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py \
  scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke_feedback.py \
  scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py \
  scion/scion/tests/unit/test_agentic_proposal_tools_context.py
```

Results: `57 passed`, `109 passed`, `90 passed`, `65 passed`.

## Prepared Roots

Because `scion/scion/runtime/telemetry_guard` is covered by prepared runtime
guards, the previous prepared roots are superseded. New launch-authoritative
WSL commit: `febeaf11`. Corresponding local repair commit: `e4a30277`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-febeaf11-runtimeinactive-6r-gpt55-20260620T150740Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-febeaf11-runtimeinactive-4r-gpt55-20260620T150741Z-claw`

Local mirrors exist under `/home/clawd/research/scion-experiments/` with the
same directory names.

Strict readiness for both roots reports `static_ready=true`,
`failed_static_required_checks=[]`, `prompt_context_readiness_complete=ok`,
`problem_specific_prepared_handoff=ok`, and
`runtime_guard_commit_matches`. The only required launch failure remains
external `gpt-5.5` completion auth: HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`.
