# CVRP Problem Adapter

v3 baseline: CVRP, ALNS, VNS, route, capacity, demand, fleet, and protected objective semantics belong in the CVRP adapter and CVRP-owned providers. Generic core may consume declared facts, telemetry roles, and gate results, but must not know CVRP semantics directly.

## Alignment - CVRP Active Facts Are In The Adapter

Evidence:
- `scion/scion/problems/cvrp/active_solver_facts.py:274-325` defines active solver facts with CVRP/ALNS/VNS/route semantics inside the CVRP package.
- `scion/scion/problems/cvrp/active_solver_facts.py:551-565` marks facts as shared by prompt and gate.
- `scion/scion/problems/cvrp/mechanism_novelty/provider.py:89-99` only evaluates solver-design hypotheses and abstains if no fact packet is available.

Assessment:
- This is the right v3 ownership boundary.
- The recent novelty-gate false-positive problem is no longer caused by generic core knowing route/Shaw semantics; it is now a CVRP provider quality issue, which is the correct failure domain.

## Finding CVRP-P1-1 - Novelty Provenance Confuses Snapshot Digest And Fact Packet Digest

Severity: P1

Type: CVRP adapter problem.

Evidence:
- `scion/scion/problems/cvrp/mechanism_novelty/snapshot.py:536-537` assigns both `snapshot_digest` and `fact_packet_digest` from `_fact_packet_digest(fact_packet, snapshot)`.
- `scion/scion/problems/cvrp/mechanism_novelty/provider.py:580-590` returns `facts.snapshot_digest` and `facts.fact_packet_digest` in semantic novelty results.

Why this violates v3:
- v3 asks for provenance/digest sufficient to audit "which active code/facts the agent and gate saw."
- `snapshot_digest` should identify the active solver source snapshot. `fact_packet_digest` should identify the extracted fact packet. Collapsing them loses a useful audit boundary.
- This matters when comparing whether a semantic rejection was based on the same code snapshot as the prompt context.

Recommended fix:
- In the fact-packet path, set:
  - `snapshot_digest` from `fact_packet["snapshot_digest"]` if present, otherwise `_snapshot_digest(snapshot)`.
  - `fact_packet_digest` from `fact_packet["fact_packet_digest"]`, otherwise computed packet digest.
- Keep both values in rejection payloads and negative fact memory.

Suggested tests:
- Build a snapshot with distinct `source_digest.snapshot_digest` and `active_algorithm_facts.fact_packet_digest`; assert novelty rejection returns both unchanged.
- Assert the prompt fact packet digest and gate rejection digest match the same fact packet, while snapshot digest remains the source digest.

## Finding CVRP-P2-1 - CVRP Novelty Provider Is Still Regex-Heavy And Large

Severity: P2

Type: CVRP adapter problem.

Evidence:
- `scion/scion/problems/cvrp/mechanism_novelty/destroy_repair.py` is 1050 lines.
- The module encodes many specific premise/novelty cases for segment, route, Shaw, double-bridge, savings, regret, perturbation, and allowed variants.
- Recent stopped-run analysis showed novelty overreach where segment/double-bridge directions were blocked with unrelated route/Shaw guidance; current code includes repairs, but the module remains high-risk.

Why this matters for v3:
- Adapter-owned semantics are correct, but they still must be auditable and precise.
- A large regex rule file can regress into "gate sees more or interprets more than the agent" even if the facts are shared.

Recommended fix:
- Split by mechanism family: construction, destroy, repair, local-search/VNS, route-limit/feasibility, and duplicate/recent-history rules.
- Normalize hypotheses into structured mechanism claims before applying family-specific rules where feasible.
- Keep each rejection tied to fact ids and exact spans.

Suggested tests:
- Focused false-positive tests for segment destroy, double-bridge perturbation, Shaw variants, route-limit claims, and adaptive-weight changes.
- Golden tests that each rejection includes `premise_check`, `fact_ids`, digest, contradicted/matched span, and allowed variant guidance.

## Finding CVRP-P2-2 - CVRP Solver Design Provider Is Broad

Severity: P2

Type: CVRP adapter architecture debt.

Evidence:
- `scion/scion/problems/cvrp/solver_design_provider.py` is 872 lines.
- The provider owns prompt guidance, API manifest behavior, telemetry declarations, smoke diagnostics, and CVRP-specific repair guidance.

Why this matters:
- This is adapter code, so CVRP semantics are allowed here.
- The risk is maintainability: prompt guidance and telemetry declarations can drift apart if kept in one large provider.

Recommended fix:
- Split into provider facade plus submodules:
  - `prompt_guidance.py`
  - `api_manifest.py`
  - `telemetry_declarations.py`
  - `smoke_feedback.py`
  - `repair_guidance.py`

Suggested tests:
- Provider facade tests should assert the same public behavior after splitting.
- Add contract tests that prompt guidance and telemetry declaration field names stay consistent.

## Finding CVRP-P2-3 - CVRP Telemetry Names Are Correctly Adapter-Owned But Leak Upstream

Severity: P2

Type: cross-boundary CVRP adapter/framework problem.

Evidence:
- `scion/scion/tests/unit/test_cvrp_solver_design_provider.py:91-128` correctly verifies CVRP problem declarations for `solver_algorithm_fleet_violation` and mechanism activation fields.
- But generic modules listed in CORE-P1-1 and GATE-P1-2 still name those fields directly.

Why this matters:
- CVRP adapter declarations are doing the right thing.
- The leak is upstream generic code consuming these field names as defaults rather than as declarations.

Recommended fix:
- Keep CVRP telemetry names where they are declared: CVRP problem spec/provider/tests.
- Remove direct references from generic runtime/protocol/proposal-smoke code.

Suggested tests:
- Boundary sentinel allowlist should permit `solver_algorithm_fleet_violation` in `problems/cvrp/**` and CVRP-specific tests, but not in generic runtime/proposal/protocol modules.
