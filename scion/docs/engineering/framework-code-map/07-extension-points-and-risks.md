# Extension Points And Risks

## Scope / Sources

Sources read: framework modules under `scion/scion/core/`, `proposal/`, `contract/`, `verification/`, `protocol/`, `problem/`, `runtime/`, `evidence/`, `lineage/`, and CVRP package code/config under `scion/scion/problems/cvrp/`.

## Extension Points for Algorithm Design Space

Prefer these problem-owned extension points:

- `ProblemSpecV1.research_surfaces`: add/edit algorithm surfaces, v2
  `targets`, `interface`, bounds, evidence, novelty, prompt metadata, and
  legacy-compatible surface fields.
- `ProblemSpecV1.operator_interface`: update execute signature and categories.
- `ProblemAdapter.render_problem_summary()`, `render_operator_interface()`, and package-specific interface rendering: teach LLMs the problem model without changing core prompts.
- `ProblemAdapter` verification methods: define solution consistency, feasibility, and objective recomputation.
- `ProblemSpecV1.objectives` and `objective_policy`: add metrics, priorities, directions, tie tolerances, or weighted-sum behavior.
- Problem package solver wrapper: define how generated operators/policies are executed and audited.
- Problem package `registry.yaml`/pool manager path: define how operators are discovered and weighted.
- Problem taxonomy: `ProblemSpecV1.family_taxonomy` and aliases for search memory/classifier.
- Problem-specific final evidence builders under `scion/scion/evidence/` when final reporting needs domain fields.

Use these framework extension points only when the behavior is truly problem-agnostic:

- new generic contract checks in `ContractGate`, including surface metadata
  enforcement and declared novelty strategies;
- new generic verification checks in `VerificationGate`;
- new generic runtime stats in `RunResult`/`SolverOutput`/`runtime/audit.py`;
- new generic protocol gate or statistical method in `protocol/`;
- new generic decision feature in `SafeFeatureExtractor` and `DecisionEngine`;
- new generic evidence summary/ref field in `EvidenceRecorder`.

## Current Coupling Risks

High-risk areas:

- `ContractGate._c9c_complexity_bound()` now prefers v2 research-surface
  `bounds.complexity_scale_terms`. Route/customer/order/vehicle names remain
  only as a legacy fallback when no v2 bounds metadata is available.
- `ContextManager` is large and mixes generic prompt assembly with some heuristic guidance. It is adapter-aware, but new prompt guidance can easily become problem-specific if not routed through adapter/spec fields.
- `ExperimentProtocol` still has a legacy objective fallback. Production problem packages should pass metric specs and require them.
- `ExperimentProtocol` now receives selected-surface metadata through
  `EvaluationRequest` for problem-spec-backed protocols and enforces
  surface-declared `evidence.required_runtime_fields` on candidate-side canary
  and paired experiment runs. Compatibility protocols without declared research
  surfaces are intentionally not auto-forwarded selected-surface metadata.
- CVRP final evidence code is correctly problem-specific, but importing it from core would violate the boundary.

Medium-risk areas:

- V2/V5/V6/V7/V8 gate risks are reduced as of 2026-05-07. V2 shares the C7
  AST-only research-surface interface validator, and bridged problem-v1 specs
  disable legacy runtime fallbacks when an adapter is missing.
- V6/V7 legacy oracle fallback and V8 objective-only nondeterminism comparison
  remain for explicit legacy/no-adapter compatibility. New problem packages
  should require adapter-backed runtime verification and metric specs.
- Adapter-backed V8 has a generic canonical artifact signature and optional
  dynamic adapter fingerprint hook, but legacy/no-adapter V8 still compares
  objective maps only.
- `ProblemSpecV1` and legacy `ProblemSpec` coexist. Any new field should define bridge behavior explicitly.
- Legacy/v2 research-surface fields are intentionally conflict-checked at spec
  load. Keep both declarations identical when a problem package still emits
  legacy compatibility fields.
- `semantic_signature` is intentionally narrow: only declared bounded
  structured fields persisted on proposals/records can affect identity.
  Free-text rationale changes do not bypass duplicate detection.
- Hypothesis context may include screening aggregates, but validation/frozen
  aggregate stats and raw holdout details are not rendered.
- Search memory family extraction depends on taxonomy quality. Without problem taxonomy, framework defaults are intentionally weak.
- Runtime audit fields are generic by convention, but solver packages choose field names. Keep new fields under general prefixes or document them in adapter/solver mechanics.
- CVRP now exposes `algorithm_blueprint` as a problem-owned top-level
  algorithm lifecycle surface. Its solver integration stays inside the CVRP
  package: Scion core sees only declared surface metadata and generic required
  runtime fields, not CVRP construction modes or local-search component names.
- CVRP now exposes `baseline_policy` as a problem-owned baseline/main-search
  policy surface. Its solver integration stays inside the CVRP package: Scion
  core sees only declared surface metadata and selected-surface runtime fields,
  not ALNS/VNS parameter semantics.
- Promotion and weight optimization mutate champion state asynchronously/synchronously. Any new design surface that changes registry semantics should be checked against promotion snapshot and stale/reconcile behavior.

## Places to Avoid Editing for Problem Features

Avoid changing these for CVRP/warehouse-specific feature work:

- `DecisionEngine`: should not name CVRP/warehouse metrics.
- `SafeFeatureExtractor`: should not parse problem-specific objective text.
- `ExperimentProtocol`: should not hardcode `fleet_violation`, `total_distance`, order, vehicle, route, or warehouse terms.
- `VerificationGate`: should not import concrete problem packages.
- `ContextManager`: should not embed problem-specific instructions when adapter/spec rendering can supply them.
- `LineageRegistry`: should not grow problem-specific tables for ordinary campaign evidence.
- `CampaignLoop` and `BranchStepRunner`: should not know algorithm-surface semantics.
- `scion.runtime.audit`: may enforce generic surface runtime evidence fields
  declared in `ProblemSpecV1`, but should not interpret CVRP, warehouse, or
  other domain-specific field meanings beyond generic presence, error-count,
  and loaded/executed checks.

## Recommended Next Implementation Slice

For future algorithm design space expansion, use a thin vertical slice:

1. Add/adjust `research_surfaces` in the problem package `problem-v1.yaml`.
2. Update adapter rendering so prompts describe the new surface and invariants.
3. Update the problem solver wrapper to execute the surface and emit runtime audit fields.
4. Update `ContractGate` only if the new surface requires a generic interface check pattern that can apply to other problems.
5. Add adapter-backed verification coverage for consistency/feasibility/objective and selected-surface runtime audit.
6. Propagate selected-surface metadata through protocol/canary pair execution
   when surface-declared runtime fields must be enforced outside verification.
   This generic protocol-audit plumbing is implemented for problem-spec-backed
   `ExperimentProtocol`; future slices should keep custom protocol
   implementations explicit about whether they support selected-surface audit.
7. Add focused tests around bridge loading, context rendering, contract validation, solver runtime audit, and one campaign smoke.
8. Add or update problem-specific final evidence only if final reporting needs new domain fields.

The CVRP `algorithm_blueprint` and `baseline_policy` slices follow this pattern
for top-level lifecycle and main-search parameter surfaces: problem spec
declaration, adapter interface/preview, solver execution and audit,
selected-surface runtime evidence, focused tests, and engineering docs were
updated without adding CVRP semantics to core governance. Future surfaces
should keep the same boundary.

## Design Review Checklist

Before merging architecture changes, check:

- Does this belong in `ProblemSpecV1`/adapter/solver instead of core?
- Does the LLM see only screening detail and aggregate holdout facts?
- Are objective semantics defined by metric specs, not metric-name conditionals?
- Does verification fail closed when adapter/runtime config is missing?
- Does selected-surface runtime audit fail closed when declared evidence fields
  are missing in both Verification and candidate-side Protocol/Canary runs?
- Are raw metrics and final evidence represented as refs, not copied into step schemas?
- Does promotion still snapshot immutable candidate code before stale-marking other branches?
- Does stale/reconcile re-run contract, verification, and screening after champion changes?
- Are new runtime audit fields consumed as evidence failures rather than objective ties?

## Open Areas for Deeper Audit

The following areas need targeted sub-agent review before large architecture changes:

- Full prompt exposure audit in `ContextManager`, especially any future use of validation/frozen data.
- ContractGate complexity guard generalization for non-route/non-warehouse problems.
- Legacy verification fallback removal plan.
- Weight optimization, stale branch reconciliation, and promotion concurrency invariants.
- Formal final evidence package lifecycle from campaign closeout through readiness refs.
