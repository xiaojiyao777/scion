# ProblemSpecV1 / ProblemAdapter Boundary

## Scope

Current source reviewed:

- `scion/scion/problem/spec.py`
- `scion/scion/problem/contracts.py`
- `scion/scion/problem/bridge.py`
- `scion/scion/problem/loader.py`
- `scion/scion/problem/objectives.py`
- `scion/scion/problem/providers.py`
- `scion/scion/core/campaign.py`
- `scion/scion/core/campaign_composition.py`
- `scion/scion/core/production_boundary.py`
- `scion/scion/protocol/experiment/facade.py`
- `scion/scion/protocol/evaluation.py`
- `scion/scion/verification/requirements.py`
- `scion/scion/verification/gate.py`
- `scion/scion/contract/checks/problem_integration.py`
- `scion/scion/proposal/agentic_preview.py`
- `scion/scion/proposal/agentic_preview_compaction.py`
- `scion/scion/problems/cvrp/problem-v1.yaml`
- `scion/scion/problems/cvrp/adapter.py`
- selected boundary tests under `scion/scion/tests/`

## Current Understanding

The intended ownership boundary is:

```text
ProblemSpecV1
  -> declares problem identity, objectives, research surfaces, adapter path,
     runtime evidence, and problem-owned semantics

ProblemAdapter
  -> implements domain loading, feasibility, consistency, objective recompute,
     and optional problem-owned provider hooks

Scion generic core
  -> consumes declared objectives/surfaces/runtime fields and adapter methods,
     but should not encode CVRP, route, fleet, or solver-domain facts directly
```

The strongest current path is the production CLI path:

```text
problem-v1.yaml
  -> load ProblemSpecV1
  -> runtime preflight
  -> ProblemSpecBridge
  -> load adapter from the same ProblemSpecV1
  -> ExperimentProtocol(metric_specs/objective_policy from bridge)
  -> VerificationGate(strict adapter runtime checks)
  -> CampaignManager
```

`ProblemSpecBridge` is the compatibility seam for code that still accepts the
legacy `ProblemSpec`. It derives `problem_spec`, `metric_specs`,
`objective_policy`, and `operator_execute_signature` from one `ProblemSpecV1`.
The CLI follows that bundle. The public `CampaignManager` constructor, however,
still accepts those pieces independently.

## Positive Boundary Observations

- `ProblemSpecV1` is strict by default. Unknown fields are rejected through the
  shared `_Strict` base model.
- Objective declarations are explicit: each metric has a name, direction,
  priority, optional tolerance, and optional weight.
- Objective validation rejects duplicate names, duplicate research surface
  names, non-contiguous priorities, and incomplete/invalid weighted-sum weights.
- The main adapter loader enforces `scion.problems.<problem_id>.` as the module
  prefix and instantiates adapters with the original `ProblemSpecV1`.
- The adapter loader checks the loaded object against the `ProblemAdapter`
  protocol.
- The CLI derives the legacy spec, metric specs, objective policy, operator
  signature, and adapter from the same `ProblemSpecV1`.
- Adapter-backed production campaigns require an adapter, metric specs,
  required metric enforcement, split/seed evidence, and strict runtime
  verification.
- Runtime verification fails closed for adapter-required campaigns instead of
  silently falling back to legacy checks.
- There is a dedicated regression test scanning generic layers for CVRP and
  solver-design leakage. This is a useful architectural guardrail.

Evidence:

- strict schema base:
  - `scion/scion/problem/spec.py:16`
  - `scion/scion/problem/spec.py:17`
- objective fields:
  - `scion/scion/problem/spec.py:20`
  - `scion/scion/problem/spec.py:25`
- `ProblemSpecV1` declares objectives, surfaces, runtime dependencies, and
  adapter:
  - `scion/scion/problem/spec.py:462`
  - `scion/scion/problem/spec.py:484`
- objective and adapter-prefix validation:
  - `scion/scion/problem/spec.py:495`
  - `scion/scion/problem/spec.py:537`
- adapter loader prefix/protocol checks:
  - `scion/scion/problem/loader.py:31`
  - `scion/scion/problem/loader.py:64`
- CLI bundle construction:
  - `scion/scion/cli/commands/init_run.py:497`
  - `scion/scion/cli/commands/init_run.py:511`
- CLI protocol and verification construction:
  - `scion/scion/cli/commands/init_run.py:610`
  - `scion/scion/cli/commands/init_run.py:643`
- generic layer leakage test:
  - `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py:8`
  - `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py:92`

## Risks And Findings

### F-PROBLEM-001 [P1] Production/runtime boundary validates presence, not one coherent ProblemSpecV1-derived bundle

`ProblemSpecBridge` correctly represents the objects that should travel
together: the v1 spec, legacy spec, metric specs, objective policy, and operator
execute signature. But `CampaignManager` still exposes them as independent
constructor inputs through `problem_spec`, `experiment_protocol`, `adapter`, and
`operator_execute_signature`.

The production boundary checks that an adapter exists, metric specs are
non-empty, metric specs are required, split/seed values exist, and verification
is strict. It does not prove that all of those values came from the same
`ProblemSpecV1`, that the adapter belongs to the problem id, that the protocol's
metric specs match the problem objectives, or that the operator signature
matches the declared interface.

Evidence:

- `ProblemSpecBridge` is the coherent derived bundle:
  - `scion/scion/problem/bridge.py:29`
  - `scion/scion/problem/bridge.py:49`
- the legacy spec conversion carries some v1 fields, but not the full v1 object:
  - `scion/scion/problem/bridge.py:67`
  - `scion/scion/problem/bridge.py:101`
- `CampaignManager.__init__` accepts independent pieces:
  - `scion/scion/core/campaign.py:81`
  - `scion/scion/core/campaign.py:110`
- campaign composition wires those pieces separately into runtime, contract,
  protocol, verification, and production-boundary checks:
  - `scion/scion/core/campaign_composition.py:129`
  - `scion/scion/core/campaign_composition.py:207`
- production boundary checks presence/flags, not identity or consistency:
  - `scion/scion/core/production_boundary.py:69`
  - `scion/scion/core/production_boundary.py:93`
- `_has_metric_specs(...)` treats any non-empty sequence or iterable as present:
  - `scion/scion/core/production_boundary.py:121`
  - `scion/scion/core/production_boundary.py:129`
- tests currently accept opaque adapters and dummy metric spec objects for some
  production-boundary paths:
  - `scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py:246`
  - `scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py:264`
  - `scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py:430`
  - `scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py:437`

Why this matters:

- Programmatic callers can mix a legacy spec from one problem, an adapter from
  another, metric specs from a third, and an operator signature from a fourth.
- The CLI path is coherent because it builds these values from one v1 spec, but
  direct construction can bypass that invariant.
- The risk is not just runtime failure. If mismatched metric specs make it into
  `ExperimentProtocol`, objective comparison and downstream evidence may be
  judged under the wrong semantics.

Suggested fix direction:

- Introduce a single runtime object, for example `ProblemRuntimeBundle`, derived
  from `ProblemSpecV1` and passed into `CampaignManager`.
- Alternatively, allow `CampaignManager` to accept `ProblemSpecBridge` plus an
  adapter loaded from the same `spec_v1`, and derive the rest internally.
- Validate production campaign consistency:
  - adapter implements `ProblemAdapter`;
  - adapter spec id matches `problem_spec.name`;
  - protocol problem spec matches the campaign problem spec;
  - protocol metric specs match `problem_spec.objectives`;
  - operator signature matches the declared operator interface.
- Add negative tests that intentionally mix problem spec, adapter, metric specs,
  and signature from different specs and assert fail-fast construction.

### F-PROBLEM-002 [P2] Legacy objective fallback remains active for direct ExperimentProtocol use

`ExperimentProtocol` has a correct strict mode: when `require_metric_specs` is
true and metrics are missing, it raises. But when metrics are absent and strict
mode is off, the protocol falls back to legacy lexicographic-minimize semantics.

That fallback is useful for skeleton/legacy paths, but it is semantically weak
for `ProblemSpecV1`. It cannot honor declared maximize/minimize directions,
weighted-sum policies, priorities, or tolerances unless `metric_specs` are
provided.

Evidence:

- missing metrics raise only when required:
  - `scion/scion/protocol/experiment/facade.py:68`
  - `scion/scion/protocol/experiment/facade.py:75`
- metric-aware comparison is used only when `_metric_specs` exists:
  - `scion/scion/protocol/experiment/facade.py:96`
  - `scion/scion/protocol/experiment/facade.py:113`
- fallback comparison remains active when metrics are absent and not required:
  - `scion/scion/protocol/experiment/facade.py:114`
  - `scion/scion/protocol/experiment/facade.py:124`

Why this matters:

- Direct runs using a v1 problem can silently compare objectives under legacy
  minimization semantics.
- This undermines the v1 objective declaration boundary unless every caller
  remembers to set `metric_specs` and `require_metric_specs`.
- The production CLI protects its path, but the lower-level API remains easy to
  misuse.

Suggested fix direction:

- If `problem_spec.spec_version == "problem-v1"` or runtime requires an adapter,
  require metric specs by default unless an explicit skeleton/legacy flag is
  set.
- Auto-hydrate metric specs from `problem_spec.objectives` when that field is
  present on the bridged legacy spec.
- Record the objective comparison mode in status/summary/protocol artifacts so
  evidence consumers can distinguish declared-objective mode from legacy
  fallback mode.

### F-PROBLEM-003 [P2] Provider fallback instantiates adapters with legacy specs and a broad module prefix

The main adapter loader is strict: it accepts `ProblemSpecV1`, enforces
`scion.problems.<problem_id>.`, and checks the `ProblemAdapter` protocol. Some
provider fallback paths use a weaker loader. They read `adapter_import_path`
from the legacy problem spec, enforce only `scion.problems.*`, instantiate the
adapter with the legacy `ProblemSpec`, and then ask it for provider hooks.

Evidence:

- generic provider resolution instantiates an adapter when no direct provider is
  available:
  - `scion/scion/problem/providers.py:430`
  - `scion/scion/problem/providers.py:447`
- provider fallback enforces only `scion.problems.*` and calls
  `cls(problem_spec)`:
  - `scion/scion/problem/providers.py:602`
  - `scion/scion/problem/providers.py:630`
- contract-check provider resolution follows the same pattern:
  - `scion/scion/contract/checks/problem_integration.py:28`
  - `scion/scion/contract/checks/problem_integration.py:39`
  - `scion/scion/contract/checks/problem_integration.py:82`
  - `scion/scion/contract/checks/problem_integration.py:110`
- the CVRP adapter currently declares a v1-spec constructor:
  - `scion/scion/problems/cvrp/adapter.py:45`
  - `scion/scion/problems/cvrp/adapter.py:50`

Why this matters:

- Provider behavior can differ depending on whether the real adapter object was
  threaded through or lazily re-instantiated from a legacy spec.
- Future adapters that need v1-only fields such as `objective_policy`,
  `llm_hints`, or richer evidence declarations may fail or degrade under the
  fallback path.
- A legacy spec can point to any module under `scion.problems.*`, not
  necessarily `scion.problems.<problem_id>.*`.

Suggested fix direction:

- Thread the already-loaded adapter object into contract/provider helpers.
- Preserve the original `spec_v1` on the bridge or on the legacy spec only as a
  compatibility pointer, then use it for provider fallback.
- Enforce the same `scion.problems.<problem_id>.` prefix in provider fallback
  loaders.
- Add a test adapter/provider that requires a v1-only field and fails if
  constructed from legacy `ProblemSpec`.

### F-PROBLEM-004 [P2] Generic proposal preview/compaction hardcodes solver_algorithm telemetry names

Generic proposal preview code still knows about `solver_algorithm_*` runtime
field names. This is not as direct as hardcoding `fleet_violation` or
`total_distance`, but it is still a surface-specific telemetry namespace in a
generic proposal module. If `solver_algorithm_*` is intended to be a generic
Scion telemetry contract, it should be declared centrally. If it is a CVRP
solver-design convention, it should be consumed through problem/surface
declarations or provider hooks.

Evidence:

- `agentic_preview.py` extracts and formats `solver_algorithm_events` and
  `solver_algorithm_errors` directly:
  - `scion/scion/proposal/agentic_preview.py:330`
  - `scion/scion/proposal/agentic_preview.py:372`
- preview compaction keeps hardcoded solver-algorithm fields and prefixes:
  - `scion/scion/proposal/agentic_preview_compaction.py:338`
  - `scion/scion/proposal/agentic_preview_compaction.py:357`
  - `scion/scion/proposal/agentic_preview_compaction.py:392`
  - `scion/scion/proposal/agentic_preview_compaction.py:420`
- the current no-hardcoded-field test only scans `proposal/tools/previews`, not
  these generic proposal files:
  - `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py:95`
  - `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py:112`
- onboarding says problem packages own runtime audit field meanings:
  - `scion/docs/AGENT_ONBOARDING.md:52`
  - `scion/docs/AGENT_ONBOARDING.md:56`

Why this matters:

- A new problem or research surface can declare different runtime evidence
  fields, but proposal preview summaries will not get equivalent handling unless
  they match the solver-algorithm naming convention.
- Proposal memory can become biased toward the CVRP solver-design surface,
  even though proposal artifacts are supposed to consume bounded declared
  feedback.
- The existing boundary test gives a useful safety net, but it misses the
  remaining hardcoded telemetry in these files.

Suggested fix direction:

- Drive preview and compaction from declared surface evidence:
  `required_runtime_fields`, `optional_runtime_fields`, and
  `runtime_field_roles`.
- If some telemetry keys are globally reserved, define them in a generic runtime
  contract and make problem specs opt into them explicitly.
- Extend the boundary test to include `proposal/agentic_preview.py` and
  `proposal/agentic_preview_compaction.py`, or add a narrow documented
  compatibility allowlist with an owner and migration target.

## Open Questions

- Should `CampaignManager` remain a low-level constructor with independent
  pieces, or should it become the place that enforces the `ProblemSpecV1`
  runtime bundle invariant?
- Is `solver_algorithm_*` intended to be a generic Scion telemetry namespace,
  or is it a CVRP solver-design convention that should move behind declarations?
- How much legacy `ProblemSpec` support is still needed for real runs versus
  tests and archived scripts?

## Suggested Next Audit Step

Review `ProposalPipeline / ContextManager / AgenticProposalSession` next.
This module directly consumes the proposal preview/compaction path identified
above, and it is the next likely place where problem-owned facts, active solver
facts, prompt context, and tainted proposal memory can drift apart.
