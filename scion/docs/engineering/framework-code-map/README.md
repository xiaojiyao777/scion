# Scion Framework Code Map

## Scope / Sources

Sources read: `scion/scion/cli/`, `scion/scion/core/`, `scion/scion/proposal/`, `scion/scion/contract/`, `scion/scion/verification/`, `scion/scion/protocol/`, `scion/scion/problem/`, `scion/scion/runtime/`, `scion/scion/evidence/`, `scion/scion/lineage/`, and CVRP package code/config under `scion/scion/problems/cvrp/`.

Not read: raw benchmark/data contents, run logs, `vrp/results`, `vrp/cvrplib`, and raw experiment result CSV/JSON outputs. CVRP checked-in config/manifest files were read only as configuration artifacts.

## Runtime Overview

Scion enters the runtime either through the Typer CLI in `scion/scion/cli/main.py` or through direct construction in runner/test scripts. The CLI resolves legacy `problem.yaml`, optionally loads authoritative `problem-v1.yaml`, bridges it to the legacy runtime shape, loads the `ProblemAdapter`, and passes metric specs/objective policy into `ExperimentProtocol`. It then builds `VerificationGate`, `LocalSubprocessRunner`, initial `ChampionState`, and `CampaignManager`.

`CampaignManager` in `scion/scion/core/campaign.py` is mostly a facade. Its constructor delegates all service wiring to `compose_campaign_services` in `scion/scion/core/campaign_composition.py`. The outer loop lives in `CampaignLoop` (`scion/scion/core/campaign_loop.py`): write status, drain weight optimization events, check governance/termination/circuit breaker, run one branch step, run stagnation checks, and finally write summaries.

The branch step path is:

1. `BranchStepRunner` selects work through `Scheduler`.
2. New or exploratory branches enter `ExploreStepPipeline`.
3. Round 1 proposal: `ProposalPipeline` builds context through `ProblemRuntime`/`ContextManager` and asks `CreativeLayer` for a `HypothesisProposal`.
4. Contract gates validate hypothesis and patch.
5. Workspace lifecycle materializes candidate code and registry.
6. `VerificationGate` runs static, test, runtime, adapter-backed feasibility/objective, nondeterminism, and perf checks.
7. `EvaluationOrchestrator` runs canary/experiment through `EvaluationPipeline` and `ExperimentProtocol`.
8. `SafeFeatureExtractor` turns raw results into `DecisionFeatures`.
9. `DecisionEngine` returns deterministic decisions.
10. `DecisionFinalizer` applies branch state, lineage, promotion, abandon, or continue side effects.
11. `EvidenceRecorder` appends `StepRecord`, updates search memory, writes status and summary artifacts.

## Core vs Problem Package

Framework core is problem-agnostic orchestration: `scion/scion/core/`, `proposal/`, `contract/`, `verification/`, `protocol/`, `problem/`, `runtime/`, `evidence/`, `lineage/`, and `parameter/`.

Problem packages live under `scion/scion/problems/<id>/`. CVRP is one such package (`scion/scion/problems/cvrp/`): it owns route semantics, solver wrapper, adapter, models, policies, operator interface, CVRPLIB parsing, and CVRP-specific evidence helpers. Warehouse and toy TSP are also problem packages, not framework primitives.

The intended boundary is `ProblemSpecV1` plus `ProblemAdapter`. Core should consume objective specs, research surfaces, taxonomy, adapter methods, runner output, and generic metrics. Core should not know route/customer/fleet or warehouse/order/vehicle semantics except in legacy compatibility fallbacks that should be retired or isolated.

## Documents

- `01-core-campaign.md`: campaign loop, branch stepping, scheduler, stale/reconcile, budget/termination.
- `02-proposal-context.md`: proposal pipeline, context assembly, schemas, memory, taxonomy, research surfaces.
- `03-evaluation-decision.md`: contract/verification/protocol/features/decision chain.
- `04-evidence-lineage.md`: `EvidenceRecorder`, `StepRecord`, lineage DB, champion store, final evidence refs.
- `05-problem-adapter-boundary.md`: `ProblemSpecV1`, bridge, adapter contract, metric specs, runner, verification boundary.
- `06-cvrp-package-map.md`: CVRP package structure and runtime audit surfaces.
- `07-extension-points-and-risks.md`: extension points, coupling risks, recommended implementation slice.

## Maintainer Notes

Update `01-core-campaign.md` after changes to campaign composition, loop lifecycle, branch state transitions, scheduler priority, stale/reconcile, promotion lifecycle, frozen budget, early stop, or termination rules.

Update `02-proposal-context.md` after changes to proposal schemas/tools, `ContextManager`, prompt exposure control, search memory, classifier/taxonomy, research surfaces, or LLM failure routing.

Update `03-evaluation-decision.md` after changes to contract checks, verification checks, `ExperimentProtocol`, metric comparison, `SafeFeatureExtractor`, `DecisionEngine`, protocol gates, or runtime veto rules.

Update `04-evidence-lineage.md` after changes to `StepRecord`, `EvidenceRecorder`, lineage schema, champion persistence, final evidence refs, readiness checks, or campaign summary/status schemas.

Update `05-problem-adapter-boundary.md` after changes to `ProblemSpecV1`, adapter protocol, bridge/loader, objective specs, adapter-backed verification, runner contract, or any framework code that starts naming a specific problem domain.

Update `06-cvrp-package-map.md` after CVRP adapter/solver/policy/operator/config/formal asset changes.

Update `07-extension-points-and-risks.md` when introducing new algorithm design surfaces, broadening what LLMs can edit, or moving logic between core and problem packages.
