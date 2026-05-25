# APS Flow, Context Tools, Ledgers, And Prompt Projection

Audit question: does APS implement the v3 two-stage agentic proposal flow, shared active facts, cache-stable context, tool ledgers, and cross-stage receipts?

## Finding APS-1: read-only tool boundary is explicit

- Severity: OK.
- Evidence: `scion/scion/proposal/tools/registry.py::ProposalToolRegistry.register` rejects tools where `read_only` is false. `ProposalToolRegistry.default_read_only` registers context, feedback, active solver map, preview, draft, and smoke tools as proposal-layer capabilities.
- V3 judgment: conforms. These tools are Creative Layer context/proposal tools; they do not run Verification, Protocol, or Decision as authority.
- Suggested fix: keep all APS tools read-only or preview-only. Any future external patch runner should still hand off to Contract/Verification/Protocol instead of mutating workspace directly.
- Suggested tests: registry test for rejecting a non-read-only tool; capability-policy test proving validation/frozen raw details are not exposed.

## Finding APS-2: active facts are projected before raw observations

- Severity: OK.
- Evidence: `scion/scion/proposal/engine/prompt_common.py` renders `agentic_active_algorithm_facts` before `agentic_tool_observations`, labels it as shared with deterministic semantic gates, and deduplicates raw observation fact packets into digest references.
- V3 judgment: conforms to the onboarding invariant that the agent and semantic gates share the same active fact packet and that raw observations are audit support, not the primary mechanism context.
- Suggested fix: keep the active facts block stable and digest-addressed; avoid burying active facts in large raw observation dumps.
- Suggested tests: snapshot prompt tests asserting active facts appear before generic observations and duplicated fact packets become refs with digest/fact ids.

## Finding APS-3: observation ledger and read receipts are implemented

- Severity: OK.
- Evidence: `scion/scion/proposal/agentic_observation_ledger/recording.py` records source digests, fact packet digests, coverage, provenance, and read receipts. `scion/scion/proposal/agentic_observation_ledger/reuse.py::already_observed_from_inherited_ledger` returns compact `already_observed` observations for code/repair phases when source digest and coverage still match.
- V3 judgment: conforms. Hypothesis and code remain separate APS requests, while the handoff carries audit-safe receipts instead of rehydrating unbounded raw context.
- Suggested fix: keep receipts compact and deterministic; do not allow stale receipts when source digest or requested coverage changes.
- Suggested tests: existing `test_agentic_observation_ledger.py` style coverage should include digest mismatch, insufficient coverage, and stale branch workspace cases.

## Finding APS-4: generic ledger defaults still assume `solver_design`

- Severity: P1 high for future problem-generic use.
- Evidence: `scion/scion/proposal/agentic_observation_ledger/digests.py::normalize_tool_args` defaults several active solver tools to `surface="solver_design"`. `scion/scion/proposal/agentic_observation_ledger/reuse.py::_entry_matches_args` also defaults missing active metadata surfaces to `solver_design`.
- V3 judgment: acceptable for current CVRP experiments but not fully v3-generic. Generic infrastructure should not assume the active research object is named `solver_design`.
- Suggested fix: derive default surface from the selected research surface, active subject id, or provider context. If missing, preserve "unspecified" rather than silently coercing to `solver_design`.
- Suggested tests: build a dummy problem with active surface `policy_bundle` and verify active map, registry, slice, and inherited read receipts do not cross-match to `solver_design`.

## Finding APS-5: novelty/premise parity is still tied to `read_active_solver_design`

- Severity: P1 high.
- Evidence: `scion/scion/proposal/mechanism_novelty.py::_active_solver_snapshot_from_observations` only considers observations with tool name `context.read_active_solver_design`. It ignores `context.read_active_solver_map`, even though recent design work makes active solver map the preferred bounded context surface.
- V3 judgment: partial conformance. Gate-prompt parity exists for active design snapshots, but the newer active-map route can become a second source of truth unless explicitly included.
- Suggested fix: allow semantic novelty/premise providers to consume the active map fact packet and cite its digest/provenance. Treat `read_active_solver_design` as compatibility, not the only parity carrier.
- Suggested tests: a gate-prompt parity regression where the hypothesis prompt includes only `context.read_active_solver_map` active facts and the provider rejection cites the same digest/fact ids.

## Finding APS-6: CVRP active map provider gives the agent the right kind of system context

- Severity: OK/P1 modularity risk.
- Evidence: `scion/scion/problems/cvrp/active_solver_map_provider.py::CvrpActiveSolverMapProvider` exposes entrypoint, editable files, operator registries, scheduler integrations, algorithm slices, telemetry fields, and known mechanism facts through generic schema.
- V3 judgment: conforms to the external APS lesson: give the model bounded, provider-declared context equivalent to reading the solver as a system, without unbounded repository access.
- Suggested fix: split the 1094-line provider by registry/slice/telemetry/fact responsibility, while preserving the public provider facade.
- Suggested tests: keep provider tests for no holdout leakage, stable digests, unknown slice unavailable payloads, and per-slice budget bounds.

