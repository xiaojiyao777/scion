# Runtime Telemetry, Telemetry Guard, and Runtime Feedback

## Scope

Current source reviewed:

- `scion/scion/problem/spec.py`
- `scion/scion/runtime/audit.py`
- `scion/scion/runtime/surface_telemetry.py`
- `scion/scion/runtime/telemetry_guard/contract.py`
- `scion/scion/runtime/telemetry_guard/declarations.py`
- `scion/scion/runtime/telemetry_guard/expected_schema.py`
- `scion/scion/runtime/telemetry_guard/summary.py`
- `scion/scion/runtime/telemetry_guard/summary_fields.py`
- `scion/scion/runtime/telemetry_guard/observations.py`
- `scion/scion/runtime/telemetry_guard/runtime_paths.py`
- `scion/scion/protocol/experiment/runtime_observation.py`
- `scion/scion/protocol/experiment/surface_runtime.py`
- `scion/scion/protocol/experiment/phase_telemetry.py`
- `scion/scion/protocol/experiment/stages.py`
- `scion/scion/core/telemetry_validation.py`
- `scion/scion/core/features.py`
- `scion/scion/core/runtime_budget_diagnostics.py`
- `scion/scion/core/decision_lifecycle_actions.py`
- `scion/scion/core/scheduling/runtime_pressure.py`
- `scion/scion/core/branch_cards_runtime.py`
- `scion/scion/proposal/tools/feedback/runtime.py`
- `scion/scion/proposal/tools/previews/telemetry_static.py`
- selected protocol, telemetry guard, decision, scheduler, feedback, and preview tests

CVRP solver/design implementation internals were intentionally not audited in
this pass. They are treated as problem-owned research objects. This pass only
uses generic runtime telemetry boundaries and problem-spec declarations.

## Current Understanding

Runtime telemetry is a cross-cutting generic observability lane:

```text
ProblemSpecV1 surface.evidence declarations
  -> solver RunResult.output.runtime
  -> runtime audit fail-closed checks
  -> protocol surface/runtime/phase summaries
  -> telemetry_guard expected-telemetry validation and aggregate summary
  -> runtime budget diagnostic
  -> ProtocolResult
  -> SafeFeatureExtractor structured telemetry/runtime flags
  -> DecisionEngine / lifecycle policy / scheduler guidance / feedback tools
```

The core design is that generic layers know only generic concepts: selected
research surface, declared runtime field keys, field roles, activation/effect/
budget categories, protected objective markers, runtime confidence, and repair
signals. Problem adapters own concrete runtime keys and meanings.

Evidence:

- problem surfaces declare runtime fields and roles generically:
  - `scion/scion/problem/spec.py:131`
  - `scion/scion/problem/spec.py:137`
  - `scion/scion/problem/spec.py:138`
  - `scion/scion/problem/spec.py:140`
- protocol initializes surface runtime and phase telemetry summaries from the
  selected surface:
  - `scion/scion/protocol/experiment/stages.py:156`
  - `scion/scion/protocol/experiment/stages.py:160`
  - `scion/scion/protocol/experiment/stages.py:164`
- protocol records runtime samples, guard inputs, and phase telemetry during
  pair execution:
  - `scion/scion/protocol/experiment/stages.py:333`
  - `scion/scion/protocol/experiment/stages.py:337`
  - `scion/scion/protocol/experiment/stages.py:341`
  - `scion/scion/protocol/experiment/stages.py:348`
- protocol builds telemetry guard and runtime budget summaries before exposing
  `ProtocolResult`:
  - `scion/scion/protocol/experiment/stages.py:802`
  - `scion/scion/protocol/experiment/stages.py:827`
  - `scion/scion/protocol/experiment/stages.py:834`
- decision features consume structured flags only:
  - `scion/scion/core/features.py:218`
  - `scion/scion/core/features.py:221`
  - `scion/scion/core/features.py:222`
  - `scion/scion/core/features.py:223`

## Positive Boundary Observations

- Runtime audit fail-closes selected-surface runtime contracts. Required fields
  missing, empty, error-count positive, or false boolean evidence fields become
  runtime audit failures.
- Runtime audit also catches declared diagnostic error counters, fallback events,
  and phase-runtime values that look cumulative instead of per-phase deltas.
- Expected telemetry has a bounded schema: `activity`, `activation`, `effect`,
  and `budget`. Proposal-declared telemetry must reference exact declared
  runtime fields, not prose.
- Activation contract checks reject outcome/effect/aggregate fields as activation
  evidence unless the surface declares a compatible mechanism-specific path.
- Telemetry guard summary distinguishes candidate missing, present, positive,
  zero, and champion positive counts. It also emits warning-vs-failure semantics
  so screening effect-zero diagnostics do not always become hard formal failures.
- Validation/frozen make effect observation stricter than screening by passing
  `effect_observation_required=stage != SCREENING`.
- Decision classification separates hard formal telemetry failure from
  repairable validation telemetry and non-blocking effect-zero diagnostics.
- Runtime evidence pressure and low-confidence runtime advisories are explicitly
  marked as proposal guidance / decision-feature excluded.
- `feedback.query_runtime` is read-only, screening-scoped, and carries provenance
  for active-boundary vs inactive-reference evidence.

Evidence:

- selected-surface runtime audit contract:
  - `scion/scion/runtime/audit.py:510`
  - `scion/scion/runtime/audit.py:552`
  - `scion/scion/runtime/audit.py:563`
  - `scion/scion/runtime/audit.py:568`
- generic boolean runtime evidence treatment:
  - `scion/scion/runtime/audit.py:662`
- expected telemetry contract and activation semantic checks:
  - `scion/scion/runtime/telemetry_guard/contract.py:26`
  - `scion/scion/runtime/telemetry_guard/contract.py:63`
  - `scion/scion/runtime/telemetry_guard/contract.py:91`
  - `scion/scion/runtime/telemetry_guard/contract.py:231`
  - `scion/scion/runtime/telemetry_guard/contract.py:243`
- guard field aggregation:
  - `scion/scion/runtime/telemetry_guard/observations.py:16`
  - `scion/scion/runtime/telemetry_guard/observations.py:30`
  - `scion/scion/runtime/telemetry_guard/evidence.py:8`
  - `scion/scion/runtime/telemetry_guard/runtime_paths.py:12`
- screening vs validation/frozen effect strictness:
  - `scion/scion/protocol/experiment/stages.py:802`
  - `scion/scion/protocol/experiment/stages.py:810`
  - `scion/scion/runtime/telemetry_guard/summary_fields.py:139`
- telemetry hard-failure classification:
  - `scion/scion/core/telemetry_validation.py:60`
  - `scion/scion/core/telemetry_validation.py:75`
  - `scion/scion/core/telemetry_validation.py:218`
  - `scion/scion/core/telemetry_validation.py:440`
- runtime pressure is advisory:
  - `scion/scion/core/decision_lifecycle_actions.py:592`
  - `scion/scion/core/decision_lifecycle_actions.py:630`
  - `scion/scion/core/scheduling/runtime_pressure.py:30`
  - `scion/scion/core/scheduling/runtime_pressure.py:51`
- feedback tool exposure/provenance:
  - `scion/scion/proposal/tools/feedback/runtime.py:35`
  - `scion/scion/proposal/tools/feedback/runtime.py:45`
  - `scion/scion/proposal/tools/feedback/runtime.py:94`
  - `scion/scion/proposal/tools/feedback/runtime.py:130`

## Risks And Findings

### F-RUNTIME-TELEMETRY-001 [P2] Runtime telemetry declaration extraction is split and can drift

There are two declaration extractors:

- `scion.runtime.surface_telemetry`, used by protocol runtime summaries, phase
  telemetry, runtime observations, and some previews.
- `scion.runtime.telemetry_guard.declarations`, used by expected telemetry
  contract validation, guard summary fallback logic, and guard guidance.

They are not identical. `surface_telemetry.declared_surface_telemetry_fields`
includes `phase_runtime_fields` and filters out unresolved `{mechanism}`
templates unless concrete mechanisms are available. `telemetry_guard.declarations`
does not include `phase_runtime_fields` in its top-level field scan and preserves
raw non-empty templates in some paths.

This is not just duplication. `phase_runtime_fields` is a first-class generic
problem-spec field, and protocol phase telemetry already consumes it. The guard
contract builds its `allowed` expected-telemetry field set from the other
extractor. That means protocol can summarize a declared phase-runtime field while
expected telemetry validation may reject or miss the same declaration unless the
adapter also duplicates it under another field family such as
`required_runtime_fields`, `stage_budget_runtime_fields`, or role mapping.

Evidence:

- generic problem spec includes phase runtime fields:
  - `scion/scion/problem/spec.py:137`
  - `scion/scion/problem/spec.py:138`
- protocol declaration helper includes phase fields and filters concrete fields:
  - `scion/scion/runtime/surface_telemetry.py:52`
  - `scion/scion/runtime/surface_telemetry.py:62`
  - `scion/scion/runtime/surface_telemetry.py:67`
  - `scion/scion/runtime/surface_telemetry.py:81`
  - `scion/scion/runtime/surface_telemetry.py:494`
- guard declaration helper scans a different list and returns raw non-empty
  fields:
  - `scion/scion/runtime/telemetry_guard/declarations.py:62`
  - `scion/scion/runtime/telemetry_guard/declarations.py:72`
  - `scion/scion/runtime/telemetry_guard/declarations.py:77`
  - `scion/scion/runtime/telemetry_guard/declarations.py:95`
  - `scion/scion/runtime/telemetry_guard/declarations.py:319`
- expected telemetry contract relies on the guard declaration helper for allowed
  fields:
  - `scion/scion/runtime/telemetry_guard/contract.py:63`
  - `scion/scion/runtime/telemetry_guard/contract.py:75`
  - `scion/scion/runtime/telemetry_guard/contract.py:106`
- protocol phase telemetry uses the protocol declaration helper:
  - `scion/scion/protocol/experiment/phase_telemetry.py:17`
  - `scion/scion/protocol/experiment/phase_telemetry.py:23`
  - `scion/scion/protocol/experiment/phase_telemetry.py:48`
  - `scion/scion/protocol/experiment/phase_telemetry.py:51`
- tests cover the two halves, but not declaration parity:
  - `scion/scion/tests/test_protocol_surface_runtime.py:454`
  - `scion/scion/tests/test_protocol_surface_runtime.py:496`
  - `scion/scion/tests/unit/test_runtime_telemetry_guard.py:459`
  - `scion/scion/tests/unit/test_runtime_telemetry_guard.py:474`

Suggested fix direction:

- Make one declaration module the source of truth. Prefer moving common logic
  into `scion.runtime.surface_telemetry` or a shared declaration model and have
  telemetry guard import it.
- Add a parity test for `declared_surface_telemetry_fields` and
  `declared_runtime_field_roles` across required, optional, activity,
  activation, effect, stage budget, phase runtime, mechanism templates, and role
  maps.
- Decide explicitly whether `phase_runtime_fields` may be referenced in
  `expected_telemetry.budget`. If yes, contract must allow it. If no, document
  that expected telemetry must use `stage_budget_runtime_fields` or a role-mapped
  field instead.

### F-RUNTIME-TELEMETRY-002 [P2] Runtime audit and surface runtime summary disagree on false `*_active` fields

Runtime audit treats `*_loaded`, `*_executed`, and `*_active` fields as generic
truthy evidence fields. Surface runtime summary only treats `*_loaded` and
`*_executed` as truthy evidence fields. A required runtime field ending in
`_active` with value `False` will fail the runtime audit path, but the aggregate
surface summary can show the field as present with `failed=0`.

This does not appear to let invalid candidates pass because runtime audit still
fails the pair. The risk is observability and repair guidance: status summaries,
raw metrics, and feedback views may under-report inactive mechanisms exactly
when the agent needs to understand why the runtime contract failed.

Evidence:

- runtime audit fails false `*_active`:
  - `scion/scion/runtime/audit.py:555`
  - `scion/scion/runtime/audit.py:568`
  - `scion/scion/runtime/audit.py:662`
- surface runtime summary omits `*_active` from true-evidence failure detection:
  - `scion/scion/protocol/experiment/surface_runtime.py:61`
  - `scion/scion/protocol/experiment/surface_runtime.py:68`
  - `scion/scion/protocol/experiment/surface_runtime.py:72`
  - `scion/scion/protocol/experiment/surface_runtime.py:272`
- tests cover active fields as present/true, but focused runtime summary tests do
  not cover a false `*_active` aggregate failure count:
  - `scion/scion/tests/test_protocol_surface_runtime.py:83`
  - `scion/scion/tests/test_protocol_surface_runtime.py:104`
  - `scion/scion/tests/test_protocol_surface_runtime.py:197`

Suggested fix direction:

- Reuse the runtime audit helper or align
  `_is_runtime_true_evidence_field(...)` with
  `_is_generic_true_evidence_field(...)`.
- Add a focused protocol surface runtime test where a required `*_active` field
  is present but false, and assert both runtime audit failure and surface summary
  `failed > 0`.

### F-RUNTIME-TELEMETRY-003 [P3] Runtime budget saturation is side-blind but guidance is candidate-directed

`runtime_budget_diagnostic(...)` computes saturation from the max of candidate
and champion budget ratios. The returned guidance tells the candidate to reduce
per-case work. Protocol then appends the same reason code to the result whenever
the diagnostic exists, and lifecycle runtime pressure can consume that code when
there is no objective signal.

That is reasonable when the candidate is the saturated side. It is ambiguous
when only the champion is close to the time limit. In that case, the signal may
still be useful as low-confidence runtime evidence, but candidate-directed repair
guidance can mislead the agent and inflate same-branch runtime pressure.

Evidence:

- diagnostic takes both candidate and champion samples and uses max saturation:
  - `scion/scion/core/runtime_budget_diagnostics.py:17`
  - `scion/scion/core/runtime_budget_diagnostics.py:36`
  - `scion/scion/core/runtime_budget_diagnostics.py:41`
  - `scion/scion/core/runtime_budget_diagnostics.py:46`
- guidance is candidate-directed:
  - `scion/scion/core/runtime_budget_diagnostics.py:78`
- protocol appends the reason code whenever the diagnostic exists:
  - `scion/scion/protocol/experiment/stages.py:834`
  - `scion/scion/protocol/experiment/stages.py:839`
- lifecycle pressure treats saturation reason codes as runtime pressure when no
  objective signal exists:
  - `scion/scion/core/decision_lifecycle_actions.py:613`
  - `scion/scion/core/decision_lifecycle_actions.py:618`
  - `scion/scion/core/decision_lifecycle_actions.py:626`
- tests cover candidate saturation, not champion-only saturation:
  - `scion/scion/tests/unit/core/test_runtime_budget_diagnostics.py:11`
  - `scion/scion/tests/unit/core/test_runtime_budget_diagnostics.py:15`
  - `scion/scion/tests/unit/core/test_runtime_budget_diagnostics.py:23`
  - `scion/scion/tests/test_protocol_surface_runtime.py:8`
  - `scion/scion/tests/test_protocol_surface_runtime.py:24`

Suggested fix direction:

- Add `saturated_side` or side-specific reason codes such as
  `candidate_runtime_budget_saturation` and
  `champion_runtime_budget_saturation`.
- Keep champion-only saturation visible as evidence-confidence guidance, but do
  not phrase it as candidate repair unless candidate samples are also saturated.
- Add champion-only and both-sides saturation tests through both the unit helper
  and protocol summary path.

## Questions For Follow-Up

- Should `phase_runtime_fields` be first-class expected telemetry budget fields,
  or should they remain only phase-summary fields unless duplicated into
  `stage_budget_runtime_fields`?
- Is the `solver_algorithm -> solver_design` compatibility alias in the generic
  runtime helper still needed, or should surface-name aliases move to
  problem/adapter-owned migration metadata?
- Should runtime budget pressure count only candidate-side saturation when making
  same-branch repair recommendations?

## Verification

Focused tests run:

```bash
pytest -q \
  scion/scion/tests/test_protocol_surface_runtime.py \
  scion/scion/tests/unit/test_runtime_telemetry_guard.py \
  scion/scion/tests/unit/test_runtime_telemetry_guard_mechanism_diagnostics.py \
  scion/scion/tests/unit/test_expected_telemetry_activation_contract.py \
  scion/scion/tests/unit/core/test_runtime_budget_diagnostics.py \
  scion/scion/tests/test_decision_feature_extraction.py \
  scion/scion/tests/unit/core/test_evaluation_pipeline.py \
  scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py \
  scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py \
  scion/scion/tests/unit/test_runtime_feedback_guidance.py \
  scion/scion/tests/unit/test_agentic_feedback_runtime_diagnosis.py \
  scion/scion/tests/unit/test_agentic_telemetry_static_preview.py \
  scion/scion/tests/unit/test_agentic_feedback_screening.py \
  scion/scion/tests/unit/test_protocol_champion_result_cache.py
```

Result: `167 passed in 1.45s`.
