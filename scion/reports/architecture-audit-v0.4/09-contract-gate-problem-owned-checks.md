# ContractGate and Problem-Owned Contract Checks

## Scope

Current source reviewed:

- `scion/scion/contract/gate.py`
- `scion/scion/contract/schema.py`
- `scion/scion/contract/hypothesis_checks.py`
- `scion/scion/contract/surface_access.py`
- `scion/scion/contract/surface_interface.py`
- `scion/scion/contract/telemetry.py`
- `scion/scion/contract/checks/targeting.py`
- `scion/scion/contract/checks/security.py`
- `scion/scion/contract/checks/identity.py`
- `scion/scion/contract/checks/complexity.py`
- `scion/scion/contract/checks/randomness.py`
- `scion/scion/contract/checks/novelty.py`
- `scion/scion/contract/checks/problem_integration.py`
- `scion/scion/contract/checks/solver_design_integration.py`
- `scion/scion/problem/contracts.py`
- `scion/scion/problem/providers.py`
- `scion/scion/problems/cvrp/adapter.py`
- `scion/scion/problems/cvrp/contract_checks/*`
- `scion/scion/core/campaign_composition.py`
- `scion/scion/core/explore_step/pipeline.py`
- `scion/scion/core/explore_step/verification.py`
- `scion/scion/core/branch_step_runner.py`
- `scion/scion/proposal/tools/previews/common.py`
- `scion/scion/proposal/tools/previews/contract.py`
- selected contract, research-surface, CVRP bridge, proposal-preview, and
  campaign preflight tests

## Current Understanding

`ContractGate` is the static gate between tainted proposal artifacts and any
workspace/runtime path.

```text
HypothesisProposal
  -> ContractGate.validate_hypothesis(...)
       -> C1 schema
       -> C2 change locus / surface kind
       -> C3 action target
       -> C11 expected telemetry
       -> C12 mechanism binding
       -> C10 novelty

PatchProposal
  -> ContractGate.validate_patch(...)
       -> C4 file whitelist / frozen files / action target
       -> C6 syntax
       -> C7 surface interface
       -> C8 import whitelist
       -> C9 sensitive API
       -> C9d instance identity
       -> C9b non-rng randomness
       -> C9c complexity
       -> C12 mechanism echo
       -> C9e problem-owned integration check
```

The main campaign paths use the real gate after proposal generation. Proposal
tools can run contract previews, but those previews are marked as proposal-only
and do not replace the real gate.

Evidence:

- `ContractGate` stores the legacy problem spec, operator signature, champion
  snapshot provider, source overrides, surface access, and novelty checker:
  - `scion/scion/contract/gate.py:99`
  - `scion/scion/contract/gate.py:120`
- hypothesis validation runs schema, locus, action/target, telemetry,
  mechanism, and novelty checks:
  - `scion/scion/contract/gate.py:130`
  - `scion/scion/contract/gate.py:153`
- patch validation builds a patch graph, validates primary and additional
  changes, and runs problem integration only after earlier checks pass:
  - `scion/scion/contract/gate.py:155`
  - `scion/scion/contract/gate.py:220`
- campaign composition constructs one gate and injects it into explore and
  branch-step paths:
  - `scion/scion/core/campaign_composition.py:161`
  - `scion/scion/core/campaign_composition.py:169`
  - `scion/scion/core/campaign_composition.py:469`
  - `scion/scion/core/campaign_composition.py:518`
- explore validates generated patches before applying or evaluating them:
  - `scion/scion/core/explore_step/pipeline.py:747`
  - `scion/scion/core/explore_step/pipeline.py:763`
- fix-code preflight validates a generated fix patch before applying it:
  - `scion/scion/core/explore_step/verification.py:87`
  - `scion/scion/core/explore_step/verification.py:117`
- branch reconcile validates patches against the branch hypothesis before
  accepting them:
  - `scion/scion/core/branch_step_runner.py:354`
  - `scion/scion/core/branch_step_runner.py:358`

## Positive Boundary Observations

- The real gate is downstream of proposal generation, not delegated to the LLM
  or the proposal preview tools.
- Patch validation is multi-file aware. It validates the primary change against
  the approved hypothesis target and validates additional changed files with
  prefixed checks.
- File targeting uses normalized patch paths, editable-pattern checks, frozen
  file checks, selected surface constraints, supported actions, and target-file
  matching.
- Syntax and interface checks are AST-based. The contract layer does not import
  candidate modules for static interface validation.
- Import checks use AST import collection and allow same-patch relative imports
  only for editable solver files and created modules.
- Sensitive API checks include both generic sensitive calls and problem-owned
  forbidden entrypoint calls.
- Instance identity checks detect direct and indirect instance-name access and
  subtract inherited champion violations before failing a candidate.
- Randomness checks reject non-injected randomness such as `random`, `uuid`,
  `secrets`, and `os.urandom`, while allowing injected `rng.*` usage.
- Complexity checks catch obvious static blowups such as high-risk
  combinations/permutations/products and unbounded loop patterns.
- Expected telemetry and mechanism binding are explicit. A hypothesis must
  declare mechanism changes when the selected surface declares mechanism
  telemetry, and the patch must echo the approved mechanism ids.
- Problem-owned CVRP contract facts live under
  `scion/scion/problems/cvrp/contract_checks/`, not in the generic CVRP-free
  contract checks.
- The CVRP adapter exposes a contract check provider. That provider owns active
  subject policy, forbidden entrypoints, state-bridge API checks, helper
  reachability, stable scheduler API checks, and same-patch import/export
  checks.
- `C9e_solver_design_integration` fails closed when a declared solver-design
  surface has no problem provider, no provider method, or a provider exception.
- Tests explicitly guard that the generic solver-design integration facade does
  not contain CVRP terms, and that CVRP-specific behavior comes from the CVRP
  adapter/provider.

Evidence:

- targeting and surface constraints:
  - `scion/scion/contract/checks/targeting.py:19`
  - `scion/scion/contract/checks/targeting.py:50`
  - `scion/scion/contract/checks/targeting.py:115`
  - `scion/scion/contract/surface_access.py:56`
- AST-only surface interface checks:
  - `scion/scion/contract/surface_interface.py:1`
  - `scion/scion/contract/surface_interface.py:26`
- import and sensitive API checks:
  - `scion/scion/contract/checks/security.py:27`
  - `scion/scion/contract/checks/security.py:134`
- identity, randomness, and complexity checks:
  - `scion/scion/contract/checks/identity.py:20`
  - `scion/scion/contract/checks/identity.py:200`
  - `scion/scion/contract/checks/randomness.py:29`
  - `scion/scion/contract/checks/complexity.py:11`
- telemetry and mechanism binding:
  - `scion/scion/contract/hypothesis_checks.py:141`
  - `scion/scion/contract/hypothesis_checks.py:191`
  - `scion/scion/contract/hypothesis_checks.py:247`
  - `scion/scion/contract/telemetry.py:11`
- CVRP adapter/provider hooks:
  - `scion/scion/problems/cvrp/adapter.py:60`
  - `scion/scion/problems/cvrp/adapter.py:68`
  - `scion/scion/problems/cvrp/contract_checks/solver_design_integration.py:29`
  - `scion/scion/problems/cvrp/contract_checks/solver_design_integration.py:124`
- CVRP-owned focused checks:
  - `scion/scion/problems/cvrp/contract_checks/api_contracts.py:51`
  - `scion/scion/problems/cvrp/contract_checks/api_contracts.py:121`
  - `scion/scion/problems/cvrp/contract_checks/reachability.py:21`
  - `scion/scion/problems/cvrp/contract_checks/reachability.py:85`
  - `scion/scion/problems/cvrp/contract_checks/state_bridge.py:11`
  - `scion/scion/problems/cvrp/contract_checks/imports.py:13`
- problem integration fail-closed behavior:
  - `scion/scion/contract/checks/solver_design_integration.py:22`
  - `scion/scion/contract/checks/solver_design_integration.py:69`
- boundary tests:
  - `scion/scion/tests/test_contract_solver_design_provider.py:21`
  - `scion/scion/tests/test_contract_solver_design_provider.py:60`
  - `scion/scion/tests/test_contract_solver_design_provider.py:78`
  - `scion/scion/tests/test_contract_solver_design_provider.py:146`
  - `scion/scion/tests/unit/test_research_surfaces_solver_design_cvrp_bridge.py:53`

## Risks And Findings

### F-CONTRACT-001 [P2] Generic ContractGate still hardwires `solver_design` as a first-class integration surface

The CVRP-specific checks are now problem-owned, which is the right direction.
But the generic contract layer still treats `solver_design` and
`solver_algorithm` as built-in vocabulary. This appears in C9e naming, provider
resolution, selected-surface classification, active-subject patch-path
detection, and support-module interface deferral.

That may be an intentional v0.4 framework concept. If so, it should be
documented as a generic first-class surface. If not, it is a CVRP-era solver
concept that still shapes the generic gate.

Evidence:

- `ContractGate` imports and runs `check_solver_design_integration(...)`:
  - `scion/scion/contract/gate.py:20`
  - `scion/scion/contract/gate.py:547`
  - `scion/scion/contract/gate.py:567`
- generic patch classification hardcodes solver-design surface names, kinds,
  roles, and active-subject policy:
  - `scion/scion/contract/gate.py:658`
  - `scion/scion/contract/gate.py:674`
  - `scion/scion/contract/checks/problem_integration.py:42`
  - `scion/scion/contract/checks/problem_integration.py:64`
  - `scion/scion/contract/checks/problem_integration.py:113`
  - `scion/scion/contract/checks/problem_integration.py:127`
- support-module interface checking has a solver-design-specific deferral:
  - `scion/scion/contract/surface_interface.py:85`
  - `scion/scion/contract/surface_interface.py:100`
- instance-name policy treats solver-design-like kinds as a built-in category:
  - `scion/scion/contract/gate.py:696`
  - `scion/scion/contract/gate.py:714`

Why this matters:

- A new problem type must either adopt the solver-design vocabulary or miss the
  strongest problem-owned integration hook.
- The generic core still knows about solver/algorithm subject shape even though
  concrete solver API rules live in the problem package.
- Reviewers need to decide whether `solver_design` is a Scion-wide research
  surface kind or a CVRP compatibility path.

Suggested fix direction:

- Rename C9e to a generic surface integration check, for example
  `C9e_surface_integration`, and dispatch through surface-declared provider
  capabilities.
- Let `ProblemSpecV1.research_surfaces[*]` declare whether a surface requires a
  problem-owned integration check, active-subject policy, interface deferral, or
  runtime smoke.
- Keep `CvrpContractCheckProvider` as the CVRP implementation of that generic
  hook.
- If `solver_design` is intentionally first-class, document that in the v0.4
  architecture notes and keep the no-CVRP-term tests around the generic layer.

### F-CONTRACT-002 [P2] `C10_novelty` duplicate detection is diagnostic/pass, not a hard contract block

`C10_novelty` currently fails closed for invalid schema, unknown novelty
strategy, missing identity fields, and unsupported semantic fields. But when it
detects a duplicate against active or blacklisted candidates, it returns
`passed=True` with `metadata.gate_action == "diagnostic"`.

This may be a deliberate shift from hard blocking to proposal guidance. If so,
the naming and evidence path should make that explicit. As implemented, the
main explore flow only branches on `not c_result.passed`, and the durable
campaign step records only booleans/result labels rather than the full
per-check diagnostic payload.

Evidence:

- duplicate novelty returns a passing `CheckResult` with diagnostic metadata:
  - `scion/scion/contract/checks/novelty.py:62`
  - `scion/scion/contract/checks/novelty.py:76`
- dedicated tests assert duplicate active and blacklist cases pass:
  - `scion/scion/tests/test_contract_complexity_novelty_result.py:324`
  - `scion/scion/tests/test_contract_complexity_novelty_result.py:352`
- explore treats contract failure only through `not c_result.passed`:
  - `scion/scion/core/explore_step/pipeline.py:424`
  - `scion/scion/core/explore_step/pipeline.py:490`
- successful step records store gate booleans, not the full passed-with-warning
  contract checks:
  - `scion/scion/core/explore_step/pipeline.py:1023`
  - `scion/scion/core/explore_step/pipeline.py:1045`
- lineage/formal candidate surfaces record contract status as a boolean or
  pass/fail label:
  - `scion/scion/core/lineage.py:175`
  - `scion/scion/core/lineage.py:178`
  - `scion/scion/core/lineage.py:231`
  - `scion/scion/evidence/formal_candidate.py:130`
  - `scion/scion/evidence/formal_candidate.py:134`

Why this matters:

- `ContractGate` should not be described as the hard duplicate-research gate
  unless another layer consumes `gate_action == "diagnostic"` and blocks or
  reprioritizes duplicates.
- Non-agentic paths can continue through repeated semantic candidates if no
  downstream search-control layer acts on the diagnostic.
- Passed diagnostics are easy to lose in durable campaign evidence, which makes
  later analysis of duplicate-search behavior harder.

Suggested fix direction:

- Decide explicitly whether duplicate novelty is a hard gate, a soft diagnostic,
  or a proposal-ranking signal.
- If it is soft, split `ContractResult` into blocking checks and diagnostics, or
  rename/report `C10_novelty` accordingly.
- Persist passed-with-diagnostic check metadata in `StepRecord`, lineage, or a
  contract diagnostics artifact.
- Add an end-to-end test that proves duplicate diagnostics are consumed by the
  intended non-agentic or agentic retry/search-control path.
- Update stale comments or docs that still describe C10 duplicate detection as a
  blocking gate.

### F-CONTRACT-003 [P2] Problem-owned provider consistency depends on legacy spec and adapter import path, not a coherent runtime bundle

The production CLI path likely stays coherent because it loads the v1 problem
spec, bridge, adapter, protocol, and gate together. The lower-level contract
path is weaker: `ContractGate` is constructed from the legacy `ProblemSpec`,
and problem-owned contract providers can be resolved by instantiating an adapter
from `problem_spec.adapter_import_path`.

That means the gate does not necessarily reuse the adapter instance already
loaded by `CampaignManager`, `ProblemRuntime`, `VerificationGate`, or
`ExperimentProtocol`. This is the contract-specific version of the broader
ProblemSpec/Adapter bundle risk.

Evidence:

- campaign composition constructs `ContractGate` from `problem_spec`, not a
  loaded adapter or runtime bundle:
  - `scion/scion/core/campaign_composition.py:161`
  - `scion/scion/core/campaign_composition.py:169`
- provider resolution first checks provider factories, then instantiates an
  adapter from `problem_spec.adapter_import_path`:
  - `scion/scion/contract/checks/problem_integration.py:28`
  - `scion/scion/contract/checks/problem_integration.py:40`
  - `scion/scion/contract/checks/problem_integration.py:82`
  - `scion/scion/contract/checks/problem_integration.py:110`
- proposal contract preview builds a gate from the adapter spec first when the
  adapter is present, which can diverge from the real gate if construction
  inputs are mixed:
  - `scion/scion/proposal/tools/previews/common.py:63`
  - `scion/scion/proposal/tools/previews/common.py:87`

Why this matters:

- Programmatic construction can mix a legacy spec from one problem with an
  adapter/protocol from another and still build a `ContractGate`.
- Contract preview and real ContractGate can disagree if the preview context has
  an adapter whose spec differs from the real campaign `problem_spec`.
- The highest-risk symptom is semantic mismatch, not an import error: the gate,
  verification, protocol, and decision layers could each be operating under a
  different problem-owned interpretation.

Suggested fix direction:

- Pass a coherent `ProblemRuntimeBundle` or loaded `ProblemAdapter` into
  `ContractGate`.
- Make provider resolution prefer the already-loaded adapter instance and fail
  if adapter spec identity does not match the campaign problem spec.
- Add negative tests that intentionally mix problem spec, adapter, protocol
  metric specs, and contract provider, and assert fail-fast construction.

### F-CONTRACT-004 [P3] Contract previews and direct patch validation can skip stateful or hypothesis-bound checks

The proposal preview tools are correctly labeled as proposal-only, static
previews. But their behavior is narrower than the real gate in ways that matter
for LLM self-check loops and debugging:

- hypothesis preview passes empty active, blacklist, and rejected sets, so it
  cannot mirror stateful novelty checks used by the real explore path;
- patch preview can run without an approved hypothesis, and the mechanism echo
  check then reports a skipped/pass result rather than enforcing ids;
- preview construction can use adapter-derived problem spec context, while the
  real gate is built from the campaign `problem_spec`.

The real campaign paths reviewed do pass approved hypotheses to patch
validation, and patch preview marks missing-hypothesis cases as incomplete. This
is therefore a preview/API clarity issue more than an immediate production
correctness issue.

Evidence:

- contract preview marks itself as proposal-only and non-promotional:
  - `scion/scion/proposal/tools/previews/contract.py:50`
  - `scion/scion/proposal/tools/previews/contract.py:59`
- hypothesis preview uses empty state sets:
  - `scion/scion/proposal/tools/previews/contract.py:60`
  - `scion/scion/proposal/tools/previews/contract.py:87`
- schema preview also invokes `ContractGate` with empty state sets:
  - `scion/scion/proposal/tools/previews/schema.py:561`
  - `scion/scion/proposal/tools/previews/schema.py:570`
- patch mechanism echo is skipped when no approved hypothesis is supplied:
  - `scion/scion/contract/hypothesis_checks.py:273`
  - `scion/scion/contract/hypothesis_checks.py:280`
- production-ish paths reviewed pass approved hypotheses:
  - `scion/scion/core/explore_step/pipeline.py:755`
  - `scion/scion/core/explore_step/pipeline.py:763`
  - `scion/scion/core/explore_step/verification.py:90`
  - `scion/scion/core/explore_step/verification.py:94`
  - `scion/scion/core/branch_step_runner.py:355`
  - `scion/scion/core/branch_step_runner.py:358`
- preview marks no-hypothesis patch cases as incomplete:
  - `scion/scion/proposal/tools/previews/contract.py:136`
  - `scion/scion/proposal/tools/previews/contract.py:140`

Why this matters:

- A preview pass is useful guidance, but it is not a faithful replay of the real
  ContractGate state.
- Agentic sessions may over-trust preview outcomes unless the result says which
  stateful checks were excluded or skipped.
- Direct API callers can accidentally validate patches without the approved
  hypothesis context needed for mechanism binding.

Suggested fix direction:

- Add explicit preview metadata such as
  `stateful_checks_excluded=["C10_active_blacklist_rejected"]` and
  `hypothesis_bound_checks_skipped=["C12_patch_mechanism_echo"]`.
- Split direct APIs into production validation and preview validation modes, or
  require `approved_hypothesis` for production patch validation when the surface
  declares mechanism telemetry.
- Keep the real gate as the only source of promotion/evaluation authority.

### F-CONTRACT-005 [P3] Active-subject policy lookup can fail open for some auxiliary checks

The main C9e integration check fails closed when a declared solver-design
surface has no provider. Some auxiliary active-subject lookups, however, return
empty/default policy on provider resolution errors. That affects support-path
classification, forbidden entrypoint call injection, and code-constraint
provider discovery.

This is not equivalent to bypassing C9e, because C9e still fails closed for a
declared solver-design patch. But the error mode is inconsistent and can make
some lower-level contract messages less precise or less strict.

Evidence:

- active-subject policy payload returns `{}` on provider resolution errors:
  - `scion/scion/problem/providers.py:191`
  - `scion/scion/problem/providers.py:220`
- active-subject code constraint provider discovery ignores adapter-load
  failure and continues with an empty provider list:
  - `scion/scion/problem/providers.py:329`
  - `scion/scion/problem/providers.py:374`
- `ContractGate` uses active-subject policy for patch classification and
  forbidden entrypoint calls:
  - `scion/scion/contract/gate.py:658`
  - `scion/scion/contract/gate.py:694`
- C9e itself fails closed for missing provider/method/exception:
  - `scion/scion/contract/checks/solver_design_integration.py:38`
  - `scion/scion/contract/checks/solver_design_integration.py:69`

Why this matters:

- ContractGate can produce different intermediate behavior depending on which
  provider lookup path fails.
- Provider misconfiguration may surface late as a broad integration failure
  instead of an explicit active-subject policy error.

Suggested fix direction:

- For production ContractGate runs, make active-subject policy provider load
  errors explicit diagnostics or blocking failures when the selected surface
  declares active-subject requirements.
- Keep preview mode tolerant if needed, but label it as degraded.

## Open Questions

- Is `solver_design` intended to be a generic Scion research-surface kind, or
  should it become a problem-owned active-subject declaration?
- Should duplicate novelty be a hard contract gate, a soft search-control
  diagnostic, or an agentic retry hint?
- Where should passed-with-diagnostic contract checks be persisted so later
  evidence review can reconstruct soft contract warnings?
- Should `ContractGate` receive the same adapter/runtime bundle that
  `VerificationGate` and `ExperimentProtocol` use?
- Do proposal previews need access to current active/blacklisted/rejected
  hypothesis signatures, or should they remain stateless by design?

## Suggested Next Audit Target

`VerificationGate and runtime/adapter checks` should come next. ContractGate
stops structurally invalid or out-of-contract proposals before execution, but
several C7/C9e paths deliberately defer parts of behavior to workspace smoke,
runtime verification, or problem-owned adapter checks. The next pass should
confirm that runtime checks fail closed, use the same problem bundle, and record
enough evidence to explain why a candidate passed or failed after static
contract validation.
