# Agent Context And Tools

v3 baseline: the agent receives bounded context, but must be able to retrieve complete relevant code. Default summaries must not mislead. Active algorithm facts shown to the agent and consumed by semantic gates must come from the same adapter-owned packet with provenance and digests.

## Alignment - Active Facts Are Now Adapter-Owned And Shared

Evidence:
- `scion/scion/proposal/active_solver_snapshot.py:405-421` requests `active_algorithm_facts` from the problem provider and sets `snapshot_digest` / `fact_packet_digest` defaults.
- `scion/scion/proposal/agentic_grounding.py:704-737` extracts the latest `context.read_active_solver_design` fact packet into `agentic_active_algorithm_facts`, preserving observation id, tool call id, provenance, source digest, snapshot digest, and fact packet digest.
- `scion/scion/proposal/engine/prompt_common.py:75-83` renders Active Algorithm Facts before raw tool observations and tells the agent these are shared with deterministic semantic gates.
- `scion/scion/problems/cvrp/active_solver_facts.py:274-325` builds CVRP-specific facts in the CVRP package.
- `scion/scion/problems/cvrp/active_solver_facts.py:551-565` marks each fact as `used_by_prompt=True` and `used_by_gate=True`.
- `scion/scion/problems/cvrp/active_solver_facts.py:594-606` computes a stable fact-packet digest.
- `scion/scion/proposal/mechanism_novelty.py:75-105` dispatches semantic novelty to the adapter and uses the active-solver snapshot gathered through tools.
- `scion/scion/problems/cvrp/mechanism_novelty/provider.py:96-99` returns no CVRP novelty result if a fact packet is unavailable, avoiding a gate that sees richer fallback facts than the agent.

Assessment:
- This is close to the v3 invariant: "agent and gate share one adapter fact packet."
- The strongest remaining provenance issue is CVRP-specific and recorded as CVRP-P1-1 in `05-problem-adapter-cvrp.md`.

Suggested regression tests:
- Assert every semantic rejection includes `fact_packet_digest`, fact ids, and provenance from the same tool observation that produced the prompt facts.
- Assert a missing fact packet makes the CVRP novelty gate abstain rather than fall back to hidden summary/call-graph details.

## Finding CTX-P2-1 - Full-Code Retrieval Has Hard Caps But No Chunking Contract

Severity: P2

Type: framework generic problem.

Evidence:
- `scion/scion/proposal/tools/active_solver.py:51-55` caps active solver file previews at 24,000 chars.
- `scion/scion/proposal/tools/active_solver.py:66-89` caps `context.read_algorithm_file.max_chars` at 24,000 chars with a 12,000 default.
- `scion/scion/proposal/tools/active_solver.py:199-229` reads only one allowlisted file through that bounded payload.
- `scion/scion/proposal/tools/surface/constants.py:8-9` caps compact surface code at 1,200 chars and full surface code at 12,000 chars.
- `scion/scion/proposal/tools/surface/readers.py:88-95` returns `content_preview`, `truncated`, `size_chars`, and `max_chars`, but no chunk cursor or offset.
- Current CVRP active files fit under the full surface/read caps: `local_search.py` is 10,994 chars, `scheduler.py` is 8,580, `destroy_repair.py` is 7,304, `construction.py` is 5,825, `state.py` is 5,456, and `baseline_algorithm.py` is 1,634.

Why this risks v3:
- Current CVRP code is fully retrievable, so this is not an immediate CVRP blocker.
- v3 says complete relevant code must be obtainable. A future branch-current solver-design file over 24,000 chars would be auditable as truncated, but the agent would not have a tool path to retrieve the rest.
- That can distort hypothesis/code stages for large generated solver bodies or future adapters.

Recommended fix:
- Add ranged/chunked `context.read_algorithm_file` support with `offset` and `limit`, or a `context.read_algorithm_file_chunk` tool.
- Alternatively, enforce a maximum generated solver-design file size below the largest readable payload and reject larger code proposals at schema/contract time.
- Surface a clear prompt/tool contract: if `truncated=true`, call the next chunk until complete before editing that file.

Suggested tests:
- Create a branch workspace file larger than 24,000 chars and assert the agent tool can retrieve all chunks.
- Add a contract/schema test that rejects generated code exceeding the configured retrievable maximum if chunking is not implemented.

## Finding CTX-P2-2 - Tool Path Guarding Is Strong But Surface Names Are Still Hardcoded To `solver_design`

Severity: P2

Type: framework generic problem.

Evidence:
- `scion/scion/proposal/tools/active_solver.py:51-88` defines tool schemas with `surface: Literal["solver_design"]`.
- `scion/scion/proposal/tools/active_solver.py:271-297` validates file paths against adapter-returned allowlisted paths and rejects surface ids such as `solver_design` / `solver_algorithm`.

Why this is partially aligned:
- For the current v0.4 focus, `solver_design` is the active boundary and path validation is good.
- For v3 as a framework, the active algorithm tool family is still named and typed around one surface. Future active algorithm surfaces would require code changes instead of adapter declaration.

Recommended fix:
- Keep path validation as-is, but derive valid active algorithm surfaces from problem/spec descriptors.
- Tool schemas may remain restricted for v0.4, but generic code should make the restriction explicit as a current product limit rather than a framework assumption.

Suggested tests:
- Synthetic adapter with a different active algorithm surface name should either be cleanly unsupported with a clear declaration error, or fully supported through descriptors.

## Alignment - Default Summaries Are Auditable

Evidence:
- Tool payloads include `truncated`, `size_chars`, and `max_chars` in `scion/scion/proposal/tools/surface/readers.py:88-95`.
- `context.read_algorithm_file` requires exact allowlisted paths returned by `context.list_algorithm_files`, enforced by `scion/scion/proposal/tools/active_solver.py:209-221` and `:280-297`.
- The prompt tells the agent raw observations are support material while compact active facts are primary (`prompt_common.py:75-83`).

Assessment:
- Default context should be less misleading than the experiment failure described in the 2026-05-21 stopped-run analysis.
- The remaining issue is completeness for large files, not silent truncation.
