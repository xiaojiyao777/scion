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
  is limited to declared bounded structured fields persisted on the
  proposal/record; free-text fields are not identity inputs, and unsupported
  signature fields fall back to strict target-file identity.

Patch checks:

- path whitelist and frozen file rejection;
- patch action/target compatibility with the approved hypothesis and selected
  surface target/allow flags;
- Python AST syntax;
- operator, policy, or declared module-function surface interface;
- declared non-operator surface required-function presence;
- import whitelist;
- sensitive API detection;
- non-`rng` randomness detection;
- complexity bound for high-order/uncapped enumeration.

For v2 research surfaces, the complexity guard uses
`bounds.complexity_scale_terms` from surface metadata. The old
route/customer/order/vehicle names remain only as a legacy fallback for
surfaces without v2 bounds metadata.

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

For production adapter-backed runs, `VerificationGate` should be configured with `adapter`, `strict_runtime_checks=True`, and `require_adapter_for_runtime=True`. Then V5/V6/V7 use `ProblemAdapter` methods and fail closed when required runtime configuration is missing.

For `research_surfaces` v2, selected surface metadata is passed into
`VerificationGate.run()` from `HypothesisProposal.change_locus` in the explore
and stale-reconcile paths. V5/V6/V7/V8/V9 call `scion.runtime.audit` with that
surface name. If the declared surface has
`evidence.required_runtime_fields`, missing or empty fields in solver
`runtime` output fail closed as runtime evidence failures, not objective ties.
Unknown selected surfaces also fail closed. Calls that provide no selected
surface are the legacy compatibility path.

Legacy verification fallback still exists:

- V5 fallback checks `assignment` and `vehicles` shape in `scion/scion/verification/state_mutation.py`.
- V6/V7 fallback require generic oracle hooks in `oracle.py`.

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

Current gap: canary and paired experiment execution still receive action
metadata but not the selected research surface. They consume generic runtime
audit failures, but they do not yet enforce selected-surface
`evidence.required_runtime_fields` in the way `VerificationGate` does.

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
