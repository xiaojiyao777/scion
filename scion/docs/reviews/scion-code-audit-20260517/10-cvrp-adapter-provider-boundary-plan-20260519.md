# 10 - CVRP Adapter Provider Boundary Plan 2026-05-19

## Scope

This plan covers the CVRP adapter and the CVRP semantics currently embedded in
generic Scion framework modules. It is aligned to Architecture v3: Scion core
owns governance, protocol, audit, deterministic gates, and Decision; the CVRP
problem package owns objective semantics, feasibility, solver object model,
surface prompt text, preview behavior, smoke behavior, and problem-specific
contract hooks.

No runtime code was changed for this review. No experiments were run. The only
focused command was collect-only test discovery for `test_cvrp_adapter.py`,
which collected 55 tests. Original external VRP algorithm files remain out of
scope and must not be modified by this cleanup.

## Read Inputs

- `scion/docs/AGENT_ONBOARDING.md`
- `scion/docs/status/current-state.md`
- `scion/design/scion-architecture-v3.md`
- `scion/docs/reviews/scion-code-audit-20260517/08-large-file-modularization-audit-20260519.md`
- `scion/scion/problems/cvrp/adapter.py`
- `scion/scion/tests/test_cvrp_adapter.py`
- Leakage paths under `proposal`, `contract`, `protocol`, and `proposal/tools`

## Boundary Target

Framework modules may know these generic concepts:

- research surface identity, target files, allowed actions, declared evidence
  fields, prompt sections, preview hooks, smoke hooks, contract hook dispatch,
  runtime telemetry samples, and exposure levels;
- tainted proposal observations versus deterministic gate results;
- adapter-backed Verification and Protocol aggregation.

Framework modules must not hard-code these CVRP concepts:

- `CvrpInstance`, `CvrpSolution`, route/customer/demand/capacity semantics,
  ALNS/VNS vocabulary, `_ALNSVNSSolver`, `_Solution`, `_Route`,
  `baseline_algorithm.py`, `baseline_modules/*.py`, CVRP case manifest schema,
  `solver_algorithm_*` runtime fields, or CVRP-specific repair text.

Those belong under `scion/scion/problems/cvrp/` or behind CVRP-owned provider
hooks.

## Adapter Responsibility Map

Current `scion/scion/problems/cvrp/adapter.py` mixes at least these
responsibilities:

| Current Responsibility | Current Location | Owner After Cleanup |
| --- | --- | --- |
| Public adapter facade and `ProblemAdapter` runtime methods | `CvrpAdapter`, lines 331-1173 | `problems/cvrp/adapter.py` facade |
| Problem summary, problem object, solver mechanics, operator/interface prose | lines 339-927 | `problems/cvrp/surface_rendering.py` or `prompting.py` |
| Surface names, allowed values, return schemas, numeric bounds, telemetry names | lines 20-324 | `problems/cvrp/surface_schema.py` |
| Surface preview dispatch | lines 928-1049 | `problems/cvrp/preview/dispatch.py` |
| Solver-design static API preview | lines 1209-1513 | `problems/cvrp/preview/solver_design.py` |
| Synthetic preview instances and preview context | lines 1535-2213 | `problems/cvrp/preview/synthetic.py` and `preview/context.py` |
| Legacy/component policy previews | lines 1609-1799, 2216-3330 | `problems/cvrp/preview/policies.py` and focused files |
| Solver output deserialization, consistency, feasibility, objective recomputation | lines 1051-1166 | `problems/cvrp/solution_checks.py` and `instances.py` |

### Proposed Package Structure

Keep `CvrpAdapter` as the compatibility facade. Move behavior behind it:

```text
scion/scion/problems/cvrp/
  adapter.py                         # thin public facade only
  instances.py                       # JSON/CVRPLIB load dispatch
  solution_checks.py                 # deserialize, consistency, feasibility, objective
  surface_schema.py                  # constants, allowed literals, telemetry field names
  surface_rendering.py               # summary/object/mechanics/interface prompt text
  providers.py                       # CVRP provider set exported to framework hooks
  preview/
    dispatch.py
    common.py
    solver_design.py
    synthetic.py
    context.py
    legacy_policies.py
    main_search_strategy.py
    deep_mechanism_policies.py
  smoke/
    solver_design.py
  contract_checks/
    solver_design_integration.py
  telemetry.py
  algorithm_artifacts.py
```

Stable imports after the split:

- `from scion.problems.cvrp.adapter import CvrpAdapter` remains valid.
- Existing adapter methods keep the same return shapes.
- Transitional private helper imports should not be promised as public API.
- Existing surface ids and target paths remain CVRP-owned data, not framework
  constants.

## Problem Provider Hook Design

Add typed optional provider protocols under a generic module such as
`scion.problem.providers`. The framework should request providers from the
adapter or a provider registry, then dispatch without importing CVRP modules.

The public `ProblemAdapter` runtime contract can stay small. Provider access can
be additive:

```python
class ProblemProviderSet(Protocol):
    prompt: ProblemPromptProvider | None
    preview: ProblemPreviewProvider | None
    smoke: ProblemSmokeProvider | None
    contract: ProblemContractProvider | None
    telemetry: ProblemTelemetryProvider | None
    artifacts: ProblemSurfaceArtifactProvider | None
```

`CvrpAdapter.problem_providers()` can return a `CvrpProblemProviders` object.
During migration, framework call sites may fall back to existing adapter
methods with `hasattr`, but new behavior should use typed providers.

### Prompt Provider

Generic engine/context code should assemble prompt blocks from provider
sections, not own problem prose.

Proposed hooks:

- `render_problem_object(context) -> str`
- `render_solver_mechanics(context) -> str`
- `render_surface_interface(surface_name, context) -> str`
- `hypothesis_task_guidance(context) -> list[str]`
- `implementation_guidance(context) -> list[str]`
- `scope_control_guidance(context) -> list[str]`
- `repair_guidance(failure, context) -> list[str]`

For CVRP, this provider owns ALNS/VNS terms, `_ALNSVNSSolver`, `_Solution`,
`_Route`, `context.nearest_neighbor()`, `context.baseline`, route-pool wording,
and target-specific file guidance.

Framework prompt code should only know where sections are placed, how they are
bounded, and which exposure level applies.

### Preview Provider

`proposal.contract_preview` may still run generic ContractGate. Problem preview
should be a separate tainted debug hook:

- `preview_surface_patch(patch, surface, context) -> ProblemPreviewResult`
- `supports_preview(surface, patch) -> bool`

CVRP owns synthetic instances, policy function calls, baseline-algorithm static
guards, `remaining_time()` unit checks, and solver-design tiny `solve(...)`
preview. The framework owns max result size, taint labels, and the fact that
preview cannot promote or validate a candidate.

### Smoke Provider

`proposal.algorithm_smoke` should become a generic tool that asks the provider
whether a patch has smoke behavior:

- `supports_algorithm_smoke(surface, patch, context) -> bool`
- `run_algorithm_smoke(context, patch, hypothesis) -> ProblemSmokeResult`

The provider result must declare:

- `non_promotional=True`
- `tainted_debug=True`
- `verification_run=False`
- `protocol_run=False`
- `decision_run=False`
- bounded case/path provenance with no absolute path exposure

CVRP owns active split selection, canary plus screening spread, solver subprocess
arguments, CVRP runtime audit interpretation, candidate-vs-champion smoke
micro-benchmark, zero/low search effort rules, and object-model repair hints.

### Contract Provider

ContractGate should remain deterministic and fail closed, but problem-specific
static rules should be registered by the problem package:

- `problem_contract_checks(surface, patch, context) -> Iterable[ProblemContractCheck]`
- each check returns generic `CheckResult` data: id, passed, severity, detail,
  diagnosis, elapsed.

CVRP owns C9e solver-design integration, stable `_ALNSVNSSolver` constructor
shape, `_Solution` bridge bans, `baseline_algorithm.py` wiring rules, scheduler
loop-change rules, and CVRP import/export path mapping.

The framework owns check ordering, result aggregation, audit persistence, and
the guarantee that Contract is deterministic and independent of LLM reasoning.

### Telemetry Provider

Protocol should stop hard-coding `solver_algorithm_*`. It can read declared
surface evidence from `problem-v1.yaml`, then ask a provider for compaction and
failure categories:

- `runtime_field_groups(surface) -> RuntimeFieldGroups`
- `compact_runtime_payload(surface, runtime) -> Mapping[str, Any]`
- `runtime_failure_categories(surface, runtime) -> Mapping[str, int]`
- `stop_reason_fields(surface) -> tuple[str, ...]`

CVRP owns `solver_algorithm_search_iterations`,
`solver_algorithm_move_attempts`, `solver_algorithm_phase_delta_sum`,
`solver_algorithm_stop_reason`, and solver-design failure categories.

Protocol owns paired case execution, aggregate stats, runtime tie-speedup gates,
and the safe feature extraction path for Decision.

### Surface Artifact Provider

Context/tool code should not know CVRP support modules. Provider hooks should
return the allowlisted algorithm files and support artifacts:

- `algorithm_file_guidance(surface, context) -> Mapping[str, Any]`
- `support_artifacts(surface, root, target_file, detail) -> list[ArtifactPreview]`
- `api_manifest(surface, root, target_file) -> str`

CVRP owns support priority, branch-current module summaries, `state.py` object
model notes, and compatibility treatment for `policies/solver_algorithm.py`.

## Migration Phases

### Phase 1 - Split CVRP Adapter Internals

Move adapter internals into the proposed CVRP modules while keeping
`CvrpAdapter` as a facade. No framework call sites change.

Stable APIs after Phase 1:

- `CvrpAdapter` import and methods are unchanged.
- `preview_research_surface_patch(...)` payload shape is unchanged.
- `render_problem_object`, `render_solver_mechanics`, and
  `render_research_surface_interface` remain available through the facade.

Test boundary after Phase 1:

- Split `test_cvrp_adapter.py` into focused CVRP test files.
- Run the split CVRP adapter tests plus `test_cvrp_cvrplib_adapter.py`.
- No proposal/context/contract tests should need behavior updates.

### Phase 2 - Add Provider Protocols And CVRP Provider Set

Introduce generic provider protocols and implement `CvrpProblemProviders`.
Keep existing adapter method fallbacks so behavior stays stable.

Stable APIs after Phase 2:

- Existing `ProblemAdapter` remains valid.
- `adapter.problem_providers()` is additive.
- Generic provider result schemas are documented and tested with fake providers.

Test boundary after Phase 2:

- Unit tests for provider dispatch with a fake non-CVRP provider.
- CVRP provider tests proving facade methods and provider methods return the
  same prompt/preview outputs for representative surfaces.

### Phase 3 - Move Prompt And Context Leakage

Replace hard-coded CVRP prompt sections in `proposal/engine.py` and
`proposal/context_manager.py` with provider sections. Framework prompt code
keeps section ordering, budgets, and taint/exposure labels only.

Stable APIs after Phase 3:

- Prompt block names may remain stable, but their problem-specific body comes
  from the provider.
- `ContextManager.build_*_context` keeps the same context keys where callers
  rely on them.

Test boundary after Phase 3:

- Generic context tests assert provider sections are included and bounded.
- CVRP prompt tests move under CVRP provider tests.
- Existing APS tests should check behavior by provider outputs, not CVRP
  literals in framework modules.

### Phase 4 - Move Algorithm Smoke

Move `scion/scion/proposal/solver_design_smoke.py` to
`scion/scion/problems/cvrp/smoke/solver_design.py`. `AlgorithmSmokeTool` calls
the generic smoke provider and compacts the returned payload.

Stable APIs after Phase 4:

- Tool name `proposal.algorithm_smoke` is unchanged.
- Observation payload keeps `non_promotional`, `tainted_debug`,
  `workspace_materialized`, `verification_run`, `protocol_run`, and
  `decision_run`.
- CVRP smoke payload may preserve existing field names for compatibility, but
  they are provider data.

Test boundary after Phase 4:

- CVRP smoke tests live under CVRP tests.
- Generic proposal tool tests use a fake provider and verify taint labels,
  no Decision execution, and result compaction.

### Phase 5 - Move Solver-Design Contract Check

Move `contract/checks/solver_design_integration.py` to
`problems/cvrp/contract_checks/solver_design_integration.py`. ContractGate
dispatches registered problem checks through the provider.

Stable APIs after Phase 5:

- Contract result check id and failure details remain compatible.
- ContractGate still aggregates deterministic checks and fails closed.
- Non-CVRP problems see no CVRP paths or class names.

Test boundary after Phase 5:

- Existing C9e tests move to CVRP contract-check tests.
- Generic ContractGate tests cover provider check dispatch, failure aggregation,
  and no-provider behavior.

### Phase 6 - Move Proposal Tool Artifact And Telemetry Knowledge

Move solver-design file guidance, support artifact priority, state model notes,
and `solver_algorithm_*` compaction into CVRP artifact/telemetry providers.
Protocol runtime summaries consume declared surface evidence/provider groups.

Stable APIs after Phase 6:

- `context.read_surface`, active solver tools, feedback tools, and Protocol
  summary schemas stay stable for callers.
- Problem-specific telemetry field names are provider data.

Test boundary after Phase 6:

- Generic tool tests use fake artifact/telemetry providers.
- CVRP tests assert the provider exposes the exact current solver-design file
  guidance, support artifact summaries, and telemetry field compaction.
- Protocol tests split generic runtime aggregation from CVRP telemetry mapping.

### Phase 7 - Remove Transitional CVRP Imports From Framework

Delete compatibility imports/re-exports of CVRP private smoke helpers from
`proposal/tools/preview.py` and remove hard-coded CVRP fallback lists from
framework modules.

Stable APIs after Phase 7:

- Public tool names and adapter import paths remain unchanged.
- Private helper imports from generic modules are no longer supported.

Test boundary after Phase 7:

- `rg` for `CVRP|Cvrp|_ALNSVNSSolver|_Solution|_Route|baseline_modules|route_pool|solver_algorithm_`
  in `core`, `proposal`, `contract`, `protocol`, and `runtime` should return
  only generic tests, documentation, or provider-dispatch references.

## Test Split Map

The collect-only run found 55 tests in `scion/scion/tests/test_cvrp_adapter.py`.
Split by responsibility:

| New Test File | Current Tests |
| --- | --- |
| `tests/problems/cvrp/test_adapter_rendering.py` | `test_cvrp_problem_spec_loads`, `test_cvrp_adapter_renders_problem_object_for_solver_level_research`, `test_cvrp_instance_exposes_safe_policy_api_without_customers_alias`, `test_cvrp_policy_surface_interfaces_render_safe_instance_api[...]`, `test_cvrp_destroy_repair_policy_interface_lists_disjoint_selector_enums` |
| `tests/problems/cvrp/test_preview_legacy_policies.py` | `test_cvrp_policy_preview_rejects_instance_customers_alias`, `test_cvrp_algorithm_blueprint_preview_rejects_bad_plan`, `test_cvrp_baseline_policy_preview_accepts_valid_params`, `test_cvrp_baseline_policy_preview_rejects_invalid_params`, `test_cvrp_algorithm_blueprint_preview_rejects_instance_customers_alias` |
| `tests/problems/cvrp/test_preview_solver_design.py` | solver algorithm and baseline algorithm preview tests from `test_cvrp_solver_algorithm_preview_accepts_valid_solution` through `test_cvrp_solver_algorithm_preview_rejects_infeasible_solution` |
| `tests/problems/cvrp/test_preview_main_search_strategy.py` | main-search strategy preview tests from `test_cvrp_main_search_strategy_preview_accepts_valid_plan` through `test_cvrp_main_search_strategy_preview_rejects_instance_customers_alias` |
| `tests/problems/cvrp/test_preview_deep_mechanism_policies.py` | deep mechanism policy preview accept/reject tests for `alns_vns_policy`, `destroy_repair_policy`, `route_pair_candidate_policy`, and `acceptance_restart_policy` |
| `tests/problems/cvrp/test_solution_checks.py` | `test_valid_route_solution_passes_all_adapter_checks`, depot boundary normalization, route shape rejection parametrization, over-capacity, objective mismatch, fleet violation, tiny solver output |
| `tests/problems/cvrp/test_verification_adapter_integration.py` | `test_strict_adapter_backed_verification_gate_passes_cvrp_tiny` |

Related cross-layer split targets:

- Move CVRP smoke runtime tests from
  `tests/unit/test_agentic_proposal_tools_solver_design.py` to
  `tests/problems/cvrp/test_solver_design_smoke.py`.
- Move CVRP solver-design integration tests from
  `tests/unit/test_research_surfaces_solver_design_integration.py` to
  `tests/problems/cvrp/test_contract_solver_design_integration.py`.
- Move CVRP prompt/context tests from
  `tests/unit/test_research_surfaces_cvrp_context.py` to
  `tests/problems/cvrp/test_prompt_provider.py`, leaving generic context tests
  to assert provider dispatch and exposure limits.
- Split `tests/unit/test_agentic_proposal_tools_schema.py` into generic schema
  preview tests and CVRP active-boundary/provider tests.
- Split `tests/unit/test_agentic_proposal_tools_feedback.py` so CVRP
  solver-design priority or plateau guidance is provider-owned.
- Split Protocol runtime tests so generic aggregation is separate from CVRP
  telemetry-provider mapping.

## Exact Leakage Examples

| File | Example | Move To |
| --- | --- | --- |
| `proposal/engine.py:460-477` | `_SOLVER_DESIGN_BROAD_SCOPE_TERMS` includes `alns`, `vns`, `destroy`, `repair`, `route-pool`, `population`, `perturb`. | CVRP prompt/scope provider. |
| `proposal/engine.py:728-759` | Active boundary hypothesis task hard-codes `policies/baseline_modules/scheduler.py`, construction, destroy/repair, local improvement, acceptance, `baseline_algorithm.py`, and `solver_algorithm.py`. | CVRP prompt provider `hypothesis_task_guidance`. |
| `proposal/engine.py:918-1027` | Full solver-algorithm rules name `baseline_algorithm.py`, `baseline_modules`, `_ALNSVNSSolver`, constructor keywords, `solver_algorithm_*`, `_Solution`, `_Route`, `context.nearest_neighbor()`, and objective fields. | CVRP prompt provider `implementation_guidance`. |
| `proposal/engine.py:1248-1284` | Compact scope control repeats scheduler, `_ALNSVNSSolver`, `_Solution`, route/customer caps, and solver_algorithm telemetry. | CVRP prompt provider `scope_control_guidance`. |
| `proposal/engine.py:1364-1373` | Timeout repair text says to avoid large ALNS helper forests. | Generic timeout text plus provider-specific repair guidance. |
| `proposal/context_manager.py:1416-1441` | Plateau guidance names scheduler-only variants and concrete CVRP mechanism modules. | CVRP context/prompt provider. |
| `proposal/context_manager.py:3493-3516` | `_SOLVER_DESIGN_API_MODULES` and integration file lists are CVRP path constants. | CVRP artifact provider. |
| `proposal/context_manager.py:3716-3747` | Target-specific guidance names destroy/repair exports, construction exports, `_ALNSVNSSolver`, `_default_vns_operators`, and `_vns`. | CVRP artifact/prompt provider. |
| `proposal/solver_design_smoke.py:65-330` | Proposal package materializes a CVRP solver-design workspace, applies patches, runs solver smoke, and compares champion. | `problems/cvrp/smoke/solver_design.py`; generic tool dispatch only. |
| `proposal/solver_design_smoke.py:714-743` | Smoke scans manifests for schema `scion.cvrp_case_manifest.v1`. | CVRP smoke provider. |
| `proposal/solver_design_smoke.py:988-1015` | Runtime compaction hard-codes `solver_algorithm_*` fields. | CVRP telemetry provider. |
| `proposal/solver_design_smoke.py:1069-1111` | Smoke micro-benchmark compares `fleet_violation` then `total_distance`. | CVRP smoke/objective provider. |
| `proposal/solver_design_smoke.py:1135-1242` | Zero/low effort rules mention ALNS/VNS/search loop and solver_algorithm counters. | CVRP smoke provider. |
| `proposal/solver_design_smoke.py:1394-1433` | Repair guidance explains `_Solution`, `_Route`, `CvrpInstance.distance`, demand, route load, and route distance. | CVRP smoke repair provider. |
| `contract/checks/solver_design_integration.py:34-52` | Stable `_ALNSVNSSolver` constructor keywords and forbidden `_Solution` bridge methods. | CVRP contract check. |
| `contract/checks/solver_design_integration.py:180-202` | Generic C9e detail requires reachability from `_ALNSVNSSolver.solve`. | CVRP contract check. |
| `contract/checks/solver_design_integration.py:224-234` | Check detail teaches CVRP `_Solution` bridge construction. | CVRP contract check. |
| `contract/checks/solver_design_integration.py:362-608` | Baseline/scheduler integration checks enforce `_ALNSVNSSolver` API. | CVRP contract check. |
| `contract/checks/solver_design_integration.py:620-710` | Scheduler loop rewrite guard compares `_ALNSVNSSolver.solve`. | CVRP contract check. |
| `contract/checks/solver_design_integration.py:901-910` | Import path mapping recognizes `policies.baseline_modules.*`. | CVRP contract check/artifact provider. |
| `proposal/tools/preview.py:28,78-120` | Generic preview tool imports and re-exports private solver-design smoke helpers from `scion.proposal`. | Remove re-exports; call generic smoke provider. |
| `proposal/tools/preview.py:1371-1402` | Algorithm smoke compaction hard-codes `solver_algorithm_*` counters. | CVRP telemetry provider. |
| `proposal/tools/surface.py:58-68` | Support artifact priority lists CVRP baseline modules. | CVRP artifact provider. |
| `proposal/tools/surface.py:917-997` | Generic surface tool reads solver-design support artifacts by CVRP paths. | CVRP artifact provider. |
| `proposal/tools/surface.py:1022-1028` | Generic API summary appends `_Solution` bridge guidance for `state.py`. | CVRP artifact provider. |
| `proposal/tools/active_solver.py:324-366` | Active solver guidance hard-codes `solver_design`, `baseline_algorithm.py`, and `solver_algorithm.py` compatibility. | CVRP artifact provider. |
| `protocol/experiment.py:452-468` | Protocol initializes `solver_algorithm_*` counters directly. | Surface evidence schema plus CVRP telemetry provider. |
| `protocol/experiment.py:996-1018` | Protocol summary formats solver_algorithm iterations, moves, baseline calls, errors. | CVRP telemetry provider formatting. |
| `protocol/experiment.py:1100-1139` | Runtime observation maps `solver_algorithm_errors` and `solver_algorithm_baseline_errors` to failure categories. | CVRP telemetry provider. |
| `protocol/experiment.py:1338-1363` | Runtime scalar summary includes the `solver_algorithm_` prefix and event field. | Surface/provider-driven runtime summary. |
| `contract/gate.py:77-90` | Legacy problem-scale names include route/customer/vehicle vocabulary. | Prefer surface `bounds.complexity_scale_terms`; remove fallback after specs are migrated. |
| `contract/gate.py:1197-1200` | Complexity-check comment references vehicles and VNS pool. | Reword generic; keep CVRP examples in CVRP provider docs/tests. |
| `contract/gate.py:3315-3318` | Bounded expression logic hard-codes `customer_count` and `route_count`. | Provider/spec scale vocabulary. |

## Risks

- Prompt drift: moving CVRP text can change APS behavior even if runtime code is
  unchanged. Preserve section names and add snapshot-style provider tests.
- Taint drift: smoke and preview must remain proposal-layer debug evidence.
  Their payloads must continue to say `non_promotional` and `tainted_debug`;
  Decision must never read them directly.
- Contract weakening: moving C9e behind a provider must not make missing
  provider registration pass silently for CVRP. CVRP should fail closed if its
  declared solver-design surface lacks the required provider check.
- Telemetry loss: replacing hard-coded `solver_algorithm_*` summaries with
  provider fields can drop evidence if field declarations are incomplete.
  Provider tests should compare current and migrated compaction output.
- Exposure regression: artifact providers must preserve branch/champion
  provenance, bounded content, no validation/frozen raw records, and redacted
  absolute paths.
- Merge risk: these files are active P0 cleanup targets. Keep each phase small,
  avoid touching external `vrp/` algorithm files, and do not fold unrelated
  solver-quality changes into boundary cleanup.

## Recommended First Implementation Slice

Start with Phase 1 plus the provider skeleton, but do not migrate framework
call sites yet:

1. Split `CvrpAdapter` into facade, surface schema/rendering, preview modules,
   and solution checks.
2. Add `CvrpProblemProviders` with prompt/preview/artifact/telemetry methods
   that delegate to the newly split modules.
3. Split `test_cvrp_adapter.py` along the map above and add provider/facade
   equivalence tests.

This slice reduces the largest CVRP adapter debt, creates the destination for
later leakage moves, and keeps public behavior stable. The next slice should
move `proposal/solver_design_smoke.py` into the CVRP package because it is the
largest direct problem implementation currently living in the proposal layer.

## v3 Compliance Notes

- Tainted proposal separation: prompt text, proposal tool observations,
  preview, and algorithm smoke remain tainted. They may guide repair or later
  proposals, but cannot decide promotion.
- Contract boundary: generic ContractGate dispatches deterministic checks and
  aggregates results. CVRP-specific C9e logic is deterministic but
  problem-owned.
- Verification boundary: adapter-backed Verification continues to use
  `load_instance`, `deserialize_solver_output`, `check_solution_consistency`,
  `check_feasibility`, and `recompute_objective`. It does not read prompt text
  or proposal smoke claims.
- Protocol boundary: Protocol runs canary/screening/validation/frozen and
  aggregates declared runtime evidence. Problem telemetry providers may label
  fields and categories, but do not alter split/seed selection, gate thresholds,
  or paired comparison rules.
- Decision boundary: Decision reads only safe deterministic features and reason
  codes. It does not read CVRP prompt guidance, LLM rationale, preview text, or
  smoke micro-benchmark prose.
- Exposure control: provider payloads must preserve current validation/frozen
  restrictions, bounded code/artifact previews, branch/champion provenance, and
  path redaction. CVRP can expose problem-object semantics and screening/runtime
  summaries inside policy, but not raw holdout data.
