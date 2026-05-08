# Evaluation Decision

## Scope / Sources

Sources read: `scion/scion/contract/gate.py`, `scion/scion/verification/gate.py`, `scion/scion/verification/feasibility.py`, `objective.py`, `state_mutation.py`, `perf_guard.py`, `nondeterminism.py`, `scion/scion/core/evaluation_pipeline.py`, `evaluation_orchestrator.py`, `features.py`, `decision.py`, `decision_coordinator.py`, `decision_finalizer.py`, `scion/scion/protocol/experiment.py`, `gates.py`, `stats.py`, `evaluation.py`, and `scion/scion/problem/objectives.py`.

## End-to-End Chain

The normal evaluation chain is:

1. `ExploreStepPipeline` or `BranchStepRunner.run_eval_step()` calls `EvaluationOrchestrator.evaluate()`.
2. `EvaluationOrchestrator` asks `BranchController.next_stage()` for screening/validation/frozen.
3. It snapshots the current champion workspace and records branch weight revision.
4. It builds an `EvaluationRequest`.
5. `EvaluationPipeline` runs canary and experiment through `ExperimentProtocol`.
6. `SafeFeatureExtractor` converts structured results into `DecisionFeatures`.
7. `DecisionCoordinator` calls pure `DecisionEngine`.
8. `DecisionFinalizer` applies side effects and writes lineage.

Contract and verification gates are run before this chain for explore/reconcile paths. Eval-only validation/frozen steps use already verified workspace state and pass synthetic contract/verification results to finalization.

## ContractGate

`ContractGate` is static validation before code execution. It consumes legacy `ProblemSpec`, bridged research surfaces, and optional operator execute signature. For `research_surfaces` v2, `targets` and `interface` metadata are authoritative; legacy surface fields remain compatibility inputs and explicit v1/v2 conflicts fail closed during spec loading.

Hypothesis checks:

- required schema-ish fields;
- `change_locus` belongs to problem-defined research loci;
- action/target-file compatibility, including research-surface allow flags;
- novelty against active, blacklisted, and same-champion rejected hypotheses,
  using declared generic novelty strategies where present. `semantic_signature`
  uses declared direct fields such as objectives plus optional
  `novelty_signature` values persisted on the proposal/record. For singleton
  semantic policy/config/portfolio surfaces, unavailable structured identity no
  longer falls back to target-file duplicate blocking; C10 only collapses a
  computed semantic signature or an exactly repeated unstructured hypothesis.
  Ordinary operator modify/remove still uses strict locus/action/target-file
  duplicate protection.

Patch checks:

- path whitelist and frozen file rejection;
- patch action/target compatibility with the approved hypothesis and selected
  surface target/allow flags;
- Python AST syntax;
- operator, policy, or declared module-function surface interface;
- declared non-operator surface required-function presence;
- import whitelist;
- sensitive API detection, including `open()` in any mode and file-read
  helpers such as `Path.read_text()`, `Path.read_bytes()`, and `Path.open()`;
- case-identity access rejection for non-operator policy/config/portfolio/
  construction/acceptance_restart surfaces and singleton surfaces:
  generated surface code must not branch on `instance.name` or direct
  `getattr(instance, "name")` / `hasattr(instance, "name")` probes;
- non-`rng` randomness detection;
- complexity bound for high-order/uncapped enumeration.

For v2 research surfaces, the complexity guard uses
`bounds.complexity_scale_terms` from surface metadata. The old
route/customer/order/vehicle names remain only as a legacy fallback for
surfaces without v2 bounds metadata.
The `instance.name` rule is intentionally generic and surface-aware: it does
not restrict safe problem-owned instance APIs such as customer ids/counts,
demands, capacity, distance, or operator route helpers.

## VerificationGate

`VerificationGate` in `scion/scion/verification/gate.py` runs fail-fast checks:

- V1 syntax
- V2 interface
- V3 unit tests
- V4 regression tests
- V5 solution consistency
- V6 feasibility
- V7 objective recomputation
- V8 nondeterminism
- V9 performance guard

Light failures are fixable by `ProposalPipeline.attempt_fix()`. Heavy failures cause rejection/blacklist paths.

V2 uses the shared AST-only research-surface interface validator from
`scion/scion/contract/surface_interface.py`, the same validator used by
ContractGate C7. `VerificationGate.run()` forwards the active problem spec and
explicit or hypothesis-derived selected surface, so module-style policy/config/
portfolio/construction surfaces validate declared required functions,
function-signature prefixes, and static return constraints without importing
tainted candidate code. If a selected surface is undeclared or the patch file is
outside that surface's declared targets, V2 fails closed.

For production adapter-backed runs, `VerificationGate` should be configured with `adapter`, `strict_runtime_checks=True`, and `require_adapter_for_runtime=True`. Bridged `ProblemSpecV1` packages now carry adapter-required metadata, so `VerificationGate` also treats those specs as adapter-required even if an adapter object is accidentally omitted. V5/V6/V7/V8 fail closed before legacy fallback paths can accept such a package. When an adapter is present, V5/V6/V7 use `ProblemAdapter` methods for consistency, feasibility, and objective recomputation, and V8 compares an adapter-canonical solver artifact signature rather than raw solver JSON. Successful V8 comparisons persist bounded comparison metadata on `CheckResult` and lineage `verification_checks`, not on `DecisionFeatures`.

For `research_surfaces` v2, selected surface metadata is passed into
`VerificationGate.run()` from `HypothesisProposal.change_locus` in the explore
and stale-reconcile paths. V5/V6/V7/V8/V9 call `scion.runtime.audit` with that
surface name. If the declared surface has
`evidence.required_runtime_fields`, missing or empty fields in solver
`runtime` output fail closed as runtime evidence failures, not objective ties.
Declared `*_errors` fields must be zero, and declared `*_loaded`,
`*_executed`, or `*_active` fields must be truthy. Unknown selected surfaces
also fail closed. Calls that provide no selected surface are the legacy
compatibility path.

Legacy verification fallback still exists:

- V5 fallback checks `assignment` and `vehicles` shape in `scion/scion/verification/state_mutation.py`, but only for legacy/no-adapter compatibility. It is disabled for bridged adapter-required `problem-v1` specs.
- V6/V7 fallback require generic oracle hooks in `oracle.py`, but are disabled
  for adapter-required specs when the adapter is missing.
- V8 objective-only nondeterminism comparison remains a legacy/no-adapter
  compatibility path; adapter-backed checks compare canonical artifacts.

Do not extend these legacy fallbacks with new problem semantics. New problem support should go through `ProblemAdapter`.

## ExperimentProtocol

`ExperimentProtocol` owns paired A/B execution through the generic `Runner` protocol. It selects cases from `SplitManager`, seeds from `SeedLedger`, runs champion and candidate workspaces, writes raw metrics snapshots, aggregates pair feedback to case-level results, computes stats, applies stage protocol gates, and returns `ProtocolResult`.

Key input objects:

- `ProtocolConfig` thresholds/case counts/runtime governance.
- `SplitManifest` stage case lists and canary list.
- `SeedLedger` stage and canary seeds.
- `Runner` implementation.
- optional objective metric specs and objective policy from `ProblemSpecV1`.

When metric specs are present, objective comparison uses `scion/scion/problem/objectives.py` for lexicographic or weighted-sum comparison. Without metric specs, `scion/scion/protocol/evaluation.py` provides a generic minimization fallback. Production CLI sets `require_metric_specs=True` when a `ProblemSpecV1` adapter is loaded.

Canary is veto-only. Validation/frozen incomplete evidence with failed pairs becomes protocol gate failure. Raw metrics are persisted to JSON refs but should not be injected directly into proposal context except through controlled screening feedback.

Canary and paired experiment execution can now receive the selected research
surface. `EvaluationOrchestrator` carries `HypothesisProposal.change_locus`
into `EvaluationRequest`, and `EvaluationPipeline` forwards it only to
surface-aware protocol implementations that also carry declared research
surface metadata. `ExperimentProtocol` stores the problem spec, accepts
`selected_surface` on canary and experiment runs, and applies
`runtime_audit_failure_from_result()` with `problem_spec` + `selected_surface`
to candidate runs. This enforces surface-declared
`evidence.required_runtime_fields` outside the verification-only path while
leaving champion-side audit on the generic legacy/runtime-failure checks.
Metrics snapshots record the selected surface as metadata. For selected
surfaces with declared `evidence.required_runtime_fields`, candidate-side pair
metrics also preserve those required runtime fields with bounded JSON values,
including non-scalar values such as structured plans or phase lists. The
protocol result carries a bounded per-field surface runtime summary for
reporting; `SafeFeatureExtractor` does not read those tainted runtime values.

## SafeFeatureExtractor

`SafeFeatureExtractor` in `scion/scion/core/features.py` is the decision boundary. It converts branch state, contract result, verification result, canary result, protocol result, and budget state into `DecisionFeatures`.

Important invariants:

- `DecisionFeatures` contains numeric/enumerated facts only, not free text.
- branch id must be UUID-shaped;
- stage and hypothesis action are known enums;
- protocol gate outcome and failure codes are checked against allow lists;
- runtime guard fields and runtime stats must be finite and non-negative where applicable.

This boundary prevents LLM text or diagnostic strings from influencing deterministic promotion rules.

## DecisionEngine

`DecisionEngine` in `scion/scion/core/decision.py` is pure deterministic logic. It first applies safety vetoes:

- contract failure;
- verification failure;
- canary failure;
- runtime guard timeout/failure;
- candidate runtime failures;
- runtime regression above configured ratio;
- incomplete runtime evidence in validation/frozen.

Then it branches by stage:

- Screening can continue explore, expand screening once, queue validation, or reject weak candidates.
- Validation can queue frozen, expand validation once, or abandon.
- Frozen promotes only on conservative positive evidence.

`DecisionCoordinator` wraps this with normalized reason codes and a readable rule string. `DecisionFinalizer` is responsible for the side effects; the engine itself does not mutate state.

## Finalization Boundary

`DecisionFinalizer` applies deterministic decisions:

- `CONTINUE_EXPLORE`: optionally preserves workspace only if verified and there is positive signal; otherwise discards workspace and resets hypothesis.
- `PROMOTE`: requires `FROZEN_TESTING`, prepares/persists/commits champion via promotion lifecycle, writes promotion lineage with a promotion event id.
- `ABANDON`: archives/cleans workspace, rejects hypothesis, hard-abandon counts where applicable.
- queue/expand decisions are applied through `BranchController.apply_decision()`.

This separation matters: evaluation computes facts and decisions, finalizer mutates branches/champions/evidence.
