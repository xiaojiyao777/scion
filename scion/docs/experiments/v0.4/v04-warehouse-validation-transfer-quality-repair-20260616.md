# Warehouse Validation-Transfer Quality Repair - 2026-06-16

## Verdict

Accepted as a code-level research-quality repair, not as warehouse efficacy
evidence.

The previous short warehouse rerun proved that v0.4 could reach validation
again, but research quality still failed: the validation candidate produced
`VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`, and no frozen row or promotion occurred.
The repair below makes warehouse operator proposals handle
screening-to-validation transfer before code generation.

## Change

- Added a generic optional adapter hook:
  `scion.core.proposal_pipeline.problem_quality.validate_problem_hypothesis_quality`.
- Wired the hook into both non-agentic `ProposalPipeline.generate_hypothesis`
  and agentic output validation before code generation.
- Kept warehouse semantics problem-owned in
  `WarehouseDeliveryAdapter.validate_hypothesis_quality`.
- Added warehouse prompt/context diagnostics describing the aggregate
  no-hierarchical-gain validation-fail pattern without exposing validation
  per-case rows.
- Updated warehouse surface guidance so operator proposals must state:
  validation-transfer risk, proposal-level activation/effect diagnostics, and
  a guard against screening-only no-effect gains.
- Clarified that these counters are a proposal-level diagnostic plan unless
  matching runtime telemetry is explicitly declared; the agent must not invent
  undeclared `expected_telemetry` keys.

## Boundary Check

- No `DecisionFeatures` fields were added.
- No validation, frozen, promotion, or generic Decision thresholds changed.
- Raw validation/frozen per-case details remain excluded from proposal context.
- The generic core only calls an optional adapter-owned proposal-quality hook;
  warehouse semantics stay in the warehouse adapter/problem spec.
- Failures are tagged as `agent_quality_blocked` so they are counted as
  pre-code research-quality blocks rather than infra or ordinary protocol
  evidence.

## Acceptance Commands

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_warehouse_target_preview.py
```

Result: `12 passed`.

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_proposal_tools_context.py \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/unit/test_agentic_telemetry_static_preview.py \
  scion/scion/tests/unit/test_agentic_session_core_flow.py \
  scion/scion/tests/unit/test_agentic_session_hypothesis_preview_retry.py
```

Result: `90 passed`.

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/core/test_proposal_pipeline_hypothesis.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_failure_paths.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_code_outputs.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_session_controls.py
```

Result: `64 passed`.

Additional checks:

```bash
git diff --check
/home/clawd/miniconda3/envs/claw/bin/python -m py_compile \
  scion/scion/core/proposal_pipeline/problem_quality.py \
  scion/scion/core/proposal_pipeline/agentic_validation.py \
  scion/scion/core/proposal_pipeline/facade.py \
  scion/scion/problems/warehouse_delivery/adapter.py \
  scion/scion/proposal/context_manager/manager.py \
  scion/scion/proposal/engine/hypothesis_context_profiles.py
```

Both passed.

## Residual Risk

This repair blocks low-quality warehouse operator hypotheses before code. It
does not prove that the agent can now produce validation-transferable
warehouse improvements. The next gate is a short production warehouse rerun
from this repair commit. Acceptance should require either:

- a proposal-quality block that correctly rejects missing transfer diagnostics
  before code, or
- screened candidates whose hypotheses explicitly explain transfer risk,
  activation/effect diagnostic plan, and screening-only guard before any
  validation decision is interpreted.

Do not loosen validation/frozen gates to compensate for weak research output.
