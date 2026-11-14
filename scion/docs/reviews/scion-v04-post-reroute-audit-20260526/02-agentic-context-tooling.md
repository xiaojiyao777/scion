# Agentic Context and Tooling

Audit question: do hypothesis/code phases have enough safe context and tools for top models without leaking hidden problem facts or relying on raw workspace mutation?

## Positive Findings

The context/tooling direction is much better than the prior audit target.

- The active solver map facade is provider-backed and schema-normalized. The fallback from algorithm-slice reads to the active map is correctly routed through `read_active_solver_map_payload`: `scion/scion/proposal/active_solver_map/facade.py:279-292`.
- Solver-design grounding now reads the active map in addition to the legacy active solver snapshot: `scion/scion/proposal/agentic_grounding.py:335-360`.
- Full-source visibility for code-stage integration edits is checked against the API-visible prompt manifest, not just tool read receipts: `scion/scion/proposal/agentic_session_patch_flow.py:911-958`.
- The retry path injects required full integration source into the prompt when visibility is missing: `scion/scion/proposal/agentic_session_patch_flow.py:961-982`.
- The prompt manifest records the rendered provider-visible prompt and explicitly states raw `prompt_context` is not treated as provider-visible text: `scion/scion/proposal/prompt_manifest.py:1-6` and `scion/scion/proposal/prompt_manifest.py:41-59`.

## Finding CT-1: active map is not yet the sole canonical grounding path

Severity: P2 for current CVRP, P1 before adding new surface classes.

Solver-design grounding still requires `context.read_active_solver_design` and `context.read_solver_call_graph` as first-class required tools:

- Required tuple: `scion/scion/proposal/agentic_grounding.py:27-31`.
- Required preface calls: `scion/scion/proposal/agentic_grounding.py:335-360`.
- Repair grounding calls: `scion/scion/proposal/agentic_grounding.py:446-455`.

The active solver map is present and useful, but the old snapshot/call-graph path remains equal or stronger in the control flow. For current CVRP this is acceptable because the adapter owns the provider. For a v3-generic framework, active map should become the canonical provider surface, with legacy active-solver snapshots as compatibility.

Suggested fix: let a surface provider declare required grounding tools. For CVRP solver-design, the provider can request both map and legacy snapshot during migration. Generic APS should only require generic `list_surfaces`/`read_problem` plus provider-declared grounding.

Suggested tests:

- A fake provider with active-map-only grounding succeeds through hypothesis and code context.
- A fake provider without `read_active_solver_design` does not fail generic grounding if its map provider is complete.

## Finding CT-2: broad context caps are safe but should be watched in live traces

Severity: P2.

The code does not show the old "tool was read but API-visible prompt omitted it" failure for code-stage modified files. It does still allow large projections:

- Hypothesis full algorithm reads can project up to 1,000,000 chars and code phase up to 400,000 chars: `scion/scion/proposal/engine/prompt_common.py:23-27`.
- Code prompt compaction keeps only bounded algorithm reads and compact values in `scion/scion/proposal/agentic_code_context.py:20-26`.

This is a reasonable tradeoff for top-model research space, but long-cycle runs should inspect prompt manifests for repeated giant sections and cache hit behavior. The current code has the observability needed to do that.

