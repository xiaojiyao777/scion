# Contract Gate Modularization - 2026-05-19

## Context

`scion/scion/contract/gate.py` is a Scion framework gate, not a problem
adapter. Architecture v3 assigns Contract Gate the deterministic boundary role:
it validates tainted LLM proposals for schema, target, file, static interface,
imports, sensitive APIs, complexity, novelty, telemetry, and mechanism binding
before any candidate code is executed. The large-file audit marks the current
3553-line module as active P1 debt because those responsibilities have accreted
in one class.

This split keeps the public `ContractGate` API stable. The immediate goal is a
facade plus orchestration shape, not a behavioral rewrite.

Read basis for this slice:

- `scion/docs/AGENT_ONBOARDING.md`, especially the hard rule that generic
  `contract` code must stay problem-agnostic and that "extracted helpers" alone
  are not sufficient modularization.
- `scion/design/scion-architecture-v3.md`, especially the Creative Layer →
  Contract → Verification → Protocol → Decision control model and the Contract
  versus Verification boundary.
- `scion/docs/reviews/scion-code-audit-20260517/08-large-file-modularization-audit-20260519.md`.
- `scion/docs/reviews/scion-code-audit-20260517/04-contract-and-static-gates.md`.

## Constraints

- No edits to `proposal/tools/preview.py` or `proposal/tools/previews/`.
- No CVRP, route, capacity, demand, or research-object semantics are added to
  contract core. Existing legacy scale-vocabulary fallback remains untouched in
  this low-risk slice and should move behind problem/surface metadata later.
- Candidate code remains tainted. Extracted helpers must stay AST/string/spec
  based and must not import candidate modules.
- Checks and failure details should remain byte-for-byte compatible where
  practical.

## Split Principle

This is not a line-count move. A helper is moved only when it has a stable v3
Contract responsibility:

- Static proposal/schema structure.
- Static patch target/path boundary.
- Static research-surface metadata lookup.
- Static expected telemetry/mechanism binding.
- Static result payload assembly.

Anything that verifies semantic correctness, feasibility, objective behavior,
runtime behavior, or solver quality is outside Contract and stays in
Verification/Protocol/Decision or problem-owned providers. Anything that names a
problem object or algorithm implementation detail must not move into generic
contract modules; it either stays as explicitly tracked legacy debt or moves to
a problem-owned hook.

## Target Shape

`ContractGate` should own:

- Public API: `validate_hypothesis`, `validate_patch`,
  `supports_semantic_signature_field`.
- Check orchestration: C1-C12 ordering, short-circuit behavior, multi-file patch
  prefixing, and selected-surface propagation.
- Stateful dependencies: problem spec, parsed operator signature, champion
  snapshot provider.
- `CheckResult` wrapping for checks that still live outside the facade only
  when the child module returns a smaller internal result type.
- Legacy compatibility seams while callers still import/use `ContractGate`
  directly.

Helper modules should own:

- `contract/result_payload.py`: `CheckResult` construction, additional-change
  prefixing, and `ContractResult` aggregation.
- `contract/patch_paths.py`: normalized config-pattern matching and
  hypothesis/patch action mapping.
- `contract/schema.py`: objective-list schema validation, mechanism-change
  schema validation, semantic novelty signature normalization, and supported
  signature-field detection.
- `contract/surface_access.py`: problem-spec research-surface lookup and
  metadata accessors.
- `contract/telemetry.py`: mechanism telemetry declaration extraction and
  mechanism-id/declaration matching.
- `contract/checks/targeting.py`: static C4/C5/C4b file/action/target checks.
- `contract/checks/security.py`: static C8/C9 import whitelist and sensitive
  API checks, including dynamic import/reflection patterns and the current
  static baseline-wrapper guard.
- `contract/checks/randomness.py`: static C9b non-`rng` randomness sources.
- `contract/checks/complexity.py`: static C9c high-risk enumeration, loop, and
  problem-scale shape checks. It receives declared scale names from the facade
  and does not own any problem vocabulary.
- `contract/checks/identity.py`: static C9d instance-identity leakage checks.
- `contract/checks/static_risk.py`: compatibility facade for older imports of
  the C9b/C9c/C9d helpers.
- `contract/checks/novelty.py`: C10 novelty comparison and semantic-signature
  identity checks.
- Future `contract/checks/*`: problem-owned integration hook dispatch once
  solver-design checks can be removed from generic contract code.

Current mapping after Phase 3:

| v3 Contract responsibility | Owner after this slice |
| --- | --- |
| Public facade and C1-C12 orchestration | `contract/gate.py` |
| Hypothesis/patch schema subrules | `contract/schema.py` |
| Semantic novelty signature normalization | `contract/schema.py` |
| Objective metric-name lookup for static proposal schema | `contract/schema.py` |
| Mechanism-change schema shape | `contract/schema.py` |
| Mechanism telemetry declaration discovery and matching | `contract/telemetry.py` |
| Research-surface metadata lookup and target membership | `contract/surface_access.py` |
| Path glob matching and action mapping | `contract/patch_paths.py` |
| Check/result aggregation payloads | `contract/result_payload.py` |
| AST syntax check | `contract/gate.py` for now |
| Import whitelist and sensitive API checks | `contract/checks/security.py` |
| Randomness static risk | `contract/checks/randomness.py` |
| Complexity static risk | `contract/checks/complexity.py` |
| Instance-identity static risk | `contract/checks/identity.py` |
| Static-risk compatibility imports | `contract/checks/static_risk.py` |
| File/action/target checks | `contract/checks/targeting.py` |
| Solver-design integration static check | `contract/checks/solver_design_integration.py` for now |

## First Slice

The first implementation slice extracts only stateless helpers and metadata
readers. It intentionally leaves the AST-heavy C8/C9/C9b/C9c/C9d helper graph in
`gate.py` because those checks have subtle alias, parent-node, and inherited
champion behavior.

Expected low-risk effect:

- `gate.py` becomes smaller and more orchestration-oriented.
- Check names, severities, ordering, and public method signatures remain
  compatible.
- Existing contract tests continue to exercise the same behavior through
  `ContractGate`.

## Phase 2 Slice

The second slice moves executable check bodies out of the facade according to
stable Contract subdomains:

| v3 Contract responsibility | Owner after Phase 2 | Dependency direction |
| --- | --- | --- |
| C4 editable-file whitelist | `contract/checks/targeting.py` | `gate -> targeting`, with `ProblemSpec` passed in |
| C5 frozen-file rejection | `contract/checks/targeting.py` | `gate -> targeting`, with `ProblemSpec` passed in |
| C4b patch action/target/surface consistency | `contract/checks/targeting.py` | `gate -> targeting`, with `SurfaceAccess` passed in |
| C8 import whitelist | `contract/checks/security.py` | `gate -> security`, with optional `PatchSetGraph` and solver-file predicate |
| C9 sensitive API/static reflection risk | `contract/checks/security.py` | `gate -> security`; no problem adapter dependency |
| C9b non-`rng` randomness | `contract/checks/static_risk.py` | `gate -> static_risk`; no problem adapter dependency |
| C9c complexity shape | `contract/checks/static_risk.py` | `gate -> static_risk`, after facade resolves declared scale terms |
| C9d instance identity | `contract/checks/static_risk.py` | `gate -> static_risk`, with `SurfaceAccess`, champion snapshot reader, and a generic surface-policy predicate |

Dependency rules:

- `contract/checks/*` may depend on generic Scion models, `ProblemSpec`,
  `SurfaceAccess`, `PatchSetGraph`, and AST/path utilities.
- `contract/checks/*` must not import problem packages or proposal tools.
- `ContractGate` may pass callbacks for facade-owned state such as champion
  snapshot reads or solver-design path recognition; check modules should not
  reach back into `ContractGate`.
- C9e remains a generic facade around the existing solver-design integration
  check only for compatibility. The current implementation still carries
  problem-specific assumptions and remains marked for a problem-owned hook.

Phase 2 intentionally leaves C10 novelty in `gate.py` because it shares
semantic-signature identity, active/blacklist ordering, and champion-version
retry semantics. It is a good next slice, but moving it safely should include
focused tests for `semantic_signature`, rejected-hypothesis champion-version
reset, and duplicate detail text.

## Phase 3 Slice

The third slice finishes the low-risk C10 and static-risk moves without changing
public `ContractGate` behavior or C-check ordering.

| v3 Contract responsibility | Owner after Phase 3 | Dependency direction |
| --- | --- | --- |
| C10 novelty and duplicate semantic signatures | `contract/checks/novelty.py` | `gate -> NoveltyChecker`, with `ProblemSpec`, `SurfaceAccess`, and hypothesis lists passed in |
| C9b non-`rng` randomness | `contract/checks/randomness.py` | `gate -> randomness`; no facade state |
| C9c high-risk enumeration/loop shape | `contract/checks/complexity.py` | `gate -> complexity`, after the facade resolves surface-declared scale names |
| C9d instance-identity leakage | `contract/checks/identity.py` | `gate -> identity`, with `SurfaceAccess`, champion snapshot reader, and a generic surface-policy predicate |
| Static-risk import compatibility | `contract/checks/static_risk.py` | facade re-exports only |
| C9e solver-design integration | `contract/checks/solver_design_integration.py` | unchanged compatibility module; see residual debt |

`ContractGate` now retains:

- Public API and C1-C12 orchestration order.
- Stateful dependencies: `ProblemSpec`, parsed operator signature, champion
  snapshot provider, `SurfaceAccess`, and the `NoveltyChecker` instance.
- C1/C2/C3/C6/C7/C11/C12 facade checks that are still small or depend directly
  on facade state.
- Legacy scale-term resolution before C9c.
- Generic callback wiring around the C9e solver-design compatibility check.

`ContractGate` no longer owns:

- C4/C5/C4b target/file/path checks.
- C8/C9 import and sensitive static-risk checks.
- C9b/C9c/C9d static-risk implementations.
- C10 novelty comparison implementation.

### C9e Decision

`contract/checks/solver_design_integration.py` remains a 1265-line
compatibility module after Phase 3. Splitting it further inside generic
`contract` would spread current branch assumptions into more modules:
`_ALNSVNSSolver`, `baseline_algorithm.py`, `scheduler.py`,
`policies/baseline_modules/*`, `_Solution` bridge APIs, stable constructor
keyword names such as `max_routes`, and CVRP route/state guidance in failure
details. These are existing debt, not new Phase 3 semantics.

The safer next phase is not a line-level split. It should first define a
problem-owned integration-check hook, then migrate those solver-design policies
out of generic Contract. Only after that migration should reusable static
pieces be extracted as generic helpers:

- same-patch import/export resolution;
- AST module/class/function discovery;
- static call graph and inert-helper reachability;
- result payload conversion for integration hooks.

## Residual Debt

- `gate.py` is now below the preferred threshold, but still owns syntax checks,
  surface-interface dispatch, solver-design integration dispatch, champion
  snapshot access, and legacy scale-term resolution.
- C9c still has a legacy generic fallback for problem-scale term names. This
  phase does not add new problem semantics, but the fallback should be replaced
  by required surface/problem metadata so generic Contract no longer carries
  any problem vocabulary. The Phase 3 complexity module receives scale terms as
  input instead of owning that fallback.
- `contract/checks/solver_design_integration.py` remains generic-package code
  with problem-specific implementation assumptions called out by the audit. It
  needs a problem-owned registered check, not a larger generic helper. Phase 3
  intentionally did not split it into more generic modules because doing so
  would make the v3 boundary less clear.
- `surface_interface.py` and `surface_access.py` now share some surface metadata
  concepts. A later cleanup should converge them without expanding either into a
  new monolith.
- `contract/checks/security.py` is still the largest pure generic check module.
  It remains under the 800-line target, but later slices can split import graph
  helpers from sensitive API/reflection checks if behavior is added.

## Remaining Phases

1. Move C9c scale-term resolution out of `ContractGate` while
   replacing legacy problem-scale fallback with adapter/surface-declared scale
   metadata.
2. Move problem-specific solver-design integration out of generic
   `contract/checks/solver_design_integration.py` behind a problem-owned
   registered check.
3. After the problem-owned hook exists, split reusable C9e pieces into generic
   import/export resolution, module graph, inert-helper reachability, and hook
   result helpers.
4. Converge `surface_interface.py` and `surface_access.py` around one metadata
   reader API without coupling interface validation back to `ContractGate`.
