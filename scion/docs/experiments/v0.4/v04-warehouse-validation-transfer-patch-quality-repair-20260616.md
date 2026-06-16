# Warehouse Validation-Transfer Patch Quality Repair - 2026-06-16

## Purpose

Close the code-stage gap exposed by the early-stopped warehouse
validation-transfer rerun from commit `88e31d7`.

The previous repair blocked weak warehouse operator hypotheses before code when
they omitted validation-transfer risk, activation/effect diagnostics, or a
screening-only guard. The field rerun showed that this was not enough: an agent
could write an acceptable hypothesis, then generate a patch that did not make
the promised diagnostics executable or observable.

This repair adds a second problem-owned quality check for tainted code patches
before Protocol. It is proposal-side validation only.

## Boundary

The v3 boundary is preserved:

- core adds only a generic optional adapter hook and lifecycle routing;
- warehouse-specific validation-transfer semantics stay in
  `WarehouseDeliveryAdapter`;
- failures are recorded as `agent_quality_blocked`, not infra;
- no `DecisionFeatures`, Protocol thresholds, validation/frozen/promotion
  gates, or holdout exposure policy changed;
- patch-quality diagnostics remain proposal-visible guidance and do not become
  promotion evidence.

## Implementation

Changed files:

- `scion/scion/core/proposal_pipeline/problem_quality.py`
  - adds `ProblemPatchQualityCheck` and `validate_problem_patch_quality(...)`.
- `scion/scion/core/proposal_pipeline/agentic_validation.py`
  - runs patch quality for completed agentic outputs before returning a patch.
  - failed patch-quality output becomes `FAILED`, `patch=None`, and
    `CODE_GENERATION_FAILED`.
- `scion/scion/core/proposal_pipeline/agentic_lifecycle.py`
  - passes the approved hypothesis into code-stage output validation.
- `scion/scion/core/proposal_pipeline/facade.py`
  - runs the same hook in the non-agentic code path.
- `scion/scion/core/proposal_pipeline/classification.py`
  - classifies structured `agent_block_reason=agent_quality_blocked` payloads
    as quality blocks for feedback/lifecycle handling.
- `scion/scion/problems/warehouse_delivery/adapter.py`
  - adds `validate_patch_quality(...)`.
  - high-risk warehouse operator patches must expose recognizable
    activation/effect diagnostic counters or an explicit instrumentation path,
    plus a screening-only or lexicographic guard.
- `scion/scion/tests/unit/test_warehouse_target_preview.py`
  - covers warehouse patch block/allow and agentic validation failure.
- `scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py`
  - covers quality-block feedback for patch-quality failures.

The warehouse hook rejects patches under the failure code:

`agent_quality_blocked:warehouse_validation_transfer_patch_quality_missing`

## Field-Sample Recheck

The two code patches generated during the early-stopped field rerun were
reconstructed from the LLM trace JSON and checked against the new hook.

Both are now blocked before Protocol:

- `merge_vehicles.py` sample:
  `allowed=False`, missing `activation_effect_diagnostic_code`.
- `move_order.py` sample:
  `allowed=False`, missing `activation_effect_diagnostic_code`.

This directly covers the observed failure mode: the hypothesis promised
activation/effect counters, but the code did not implement any recognizable
counter or instrumentation path.

## Acceptance Tests

Main-session verification:

- `PYTHONPATH=scion python -m pytest scion/scion/tests/unit/test_warehouse_target_preview.py -q`
  - `15 passed`
- `PYTHONPATH=scion python -m pytest scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py -q`
  - `18 passed`
- `PYTHONPATH=scion python -m pytest scion/scion/tests/unit/core/test_proposal_pipeline_*.py -q`
  - `74 passed`
- `PYTHONPATH=scion python -m pytest scion/scion/tests/unit/test_agentic_proposal_tools_context.py scion/scion/tests/unit/test_hypothesis_context_profiles.py scion/scion/tests/unit/test_agentic_telemetry_static_preview.py scion/scion/tests/unit/test_agentic_session_core_flow.py scion/scion/tests/unit/test_agentic_session_hypothesis_preview_retry.py -q`
  - `90 passed`
- `PYTHONPATH=scion python -m pytest scion/scion/tests/unit/core/test_retry_round_accounting.py scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py -q`
  - `48 passed`
- `PYTHONPATH=scion python -m pytest scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py scion/scion/tests/unit/core/test_cross_branch_observability.py -q`
  - `66 passed`
- `python -m py_compile` on touched core/warehouse modules
  - passed
- `git diff --check`
  - passed

## Decision

Accept the repair as code and framework behavior. This is not warehouse
efficacy evidence.

Next gate: launch a fresh short production warehouse rerun from the repair
commit. Acceptance should require one of:

- transfer/diagnostic-blind warehouse operator patches are blocked before
  Protocol as
  `agent_quality_blocked:warehouse_validation_transfer_patch_quality_missing`;
  or
- non-blocked patches carry executable/observable activation/effect diagnostics
  and still pass ordinary Contract/Verification/Protocol.

Validation and frozen gates must remain unchanged. If research quality is still
poor after this gate, the next repair should focus on the agent's mechanism
quality or operator-feedback loop, not on promotion thresholds.

## Residual Risk

The patch-quality check is static. It intentionally rejects the observed
failure mode with a conservative named-counter/instrumentation requirement.
Future agents may use different but legitimate diagnostic names, in which case
the warehouse-owned recognizer may need to be extended. That extension should
remain in the problem adapter, not generic core.
