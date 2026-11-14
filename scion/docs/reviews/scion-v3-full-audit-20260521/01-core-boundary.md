# Core Boundary

v3 baseline: framework core owns governance, contracts, validation, lineage, and branch scheduling. Problem semantics such as CVRP, ALNS, VNS, routes, capacity, fleet, and domain-specific solver telemetry must live behind problem adapters or declared surface descriptors.

## Finding CORE-P1-1 - Generic Runtime/Protocol Still Owns `solver_algorithm_*`

Severity: P1

Type: framework generic problem.

Evidence:
- `scion/scion/runtime/audit.py:92-169` directly reads `solver_algorithm_errors`, `solver_algorithm_path`, `solver_algorithm_active`, `solver_algorithm_stop_reason`, and formats `solver_algorithm_runtime_error`.
- `scion/scion/runtime/audit.py:246-271` contains a hardcoded consistency rule for `solver_algorithm_elapsed_ms` and `solver_algorithm_phase_runtime_ms`.
- `scion/scion/protocol/experiment/runtime_observation.py:17-47` aggregates `solver_algorithm_*` counters as first-class protocol counters.
- `scion/scion/protocol/experiment/runtime_observation.py:144-178` includes every scalar field starting with `solver_algorithm_` in the runtime audit summary.
- `scion/scion/protocol/experiment/stages.py:108-124` initializes `candidate_runtime_counters` with `solver_algorithm_*` keys.
- `scion/scion/protocol/experiment/stages.py:681-694` prints `candidate_solver_algorithm_*` fields in exposed summaries.

Why this violates v3:
- v3 allows generic core to evaluate declared telemetry contracts, but not to define a problem-specific telemetry namespace.
- `solver_algorithm_*` is not inherently generic; in current CVRP it is the CVRP solver-design surface namespace. A non-CVRP adapter should not need to imitate these fields to get good runtime diagnostics.
- This also creates a subtle asymmetry: CVRP gets richer generic protocol diagnostics because the generic layer knows its field names.

Recommended fix:
- Introduce a problem/surface runtime telemetry descriptor that declares error counters, event fields, stop-reason fields, phase-runtime fields, and summary counters.
- Make `runtime/audit.py` and `protocol/experiment/runtime_observation.py` iterate declared descriptor roles instead of hardcoded prefixes.
- Move CVRP-specific `solver_algorithm_*` interpretation into the CVRP adapter/provider.

Suggested tests:
- Add a synthetic non-CVRP `solver_design` surface with fields such as `dispatch_loaded`, `dispatch_active`, `dispatch_errors`, and `dispatch_phase_runtime_ms`.
- Assert protocol summaries, runtime audit failures, and telemetry guard results work without any `solver_algorithm_*` key.
- Add a boundary sentinel that fails if generic runtime/protocol modules introduce CVRP, route, fleet, ALNS/VNS, or `solver_algorithm_total_distance`/`fleet_violation` fields outside an allowlist.

## Finding CORE-P1-2 - `DecisionFeatures.statistical_metric` Carries Free Text

Severity: P1

Type: framework generic problem.

Evidence:
- `scion/scion/core/models.py:341-342` defines `statistical_metric: Optional[str]`.
- `scion/scion/core/features.py:116-117` copies `stats.statistical_metric` into DecisionFeatures.
- `scion/scion/core/features.py:186-263` validates enums, failure codes, UUID, and numeric ranges, but never validates `statistical_metric`.

Why this violates v3:
- v3 states that Decision receives structured, safe features and no free text.
- `statistical_metric` can carry arbitrary problem/protocol strings into DecisionFeatures even if current Decision rules do not use it heavily.
- This weakens the formal boundary between protocol evidence and Decision.

Recommended fix:
- Replace `statistical_metric` with either a typed enum or a declared metric id resolved from the problem/protocol descriptor.
- If Decision does not need it, remove it from DecisionFeatures and keep it only in raw protocol metrics.

Suggested tests:
- Unit test that constructing/extracting DecisionFeatures with an unknown metric id fails.
- Unit test that arbitrary prose in `statistical_metric` cannot reach Decision.

## Finding CORE-P2-1 - Legacy CVRP-Shaped Fallbacks Remain in Generic Contract Code

Severity: P2

Type: framework generic problem.

Evidence:
- `scion/scion/contract/gate.py:59-72` defines legacy scale names including `route`, `routes`, `customers`, and `vehicles`.
- `scion/scion/contract/gate.py:776-803` falls back to those names when no v2 surface bounds are present.
- `scion/scion/contract/gate.py:814-824` treats `policies/baseline_algorithm.py`, `policies/solver_algorithm.py`, and `policies/baseline_modules/*.py` as solver-design paths in generic C8 import-whitelist handling.

Why this violates or risks v3:
- The comments correctly identify these as legacy fallbacks, and the primary path now uses research surface declarations. Still, the generic contract layer carries CVRP-shaped defaults and path aliases.
- This can mask missing adapter declarations by letting CVRP-like paths work even when the surface descriptor is incomplete.

Recommended fix:
- Move solver-design path aliases into the problem/surface descriptor or adapter provider.
- Fail closed for new v2 specs when surface bounds are missing instead of falling back to CVRP-like scale terms.
- Keep legacy fallback only behind an explicit compatibility flag for old specs.

Suggested tests:
- A v2 synthetic problem without `bounds.complexity_scale_terms` should fail closed with a declaration error.
- A non-CVRP solver-design path should be accepted only through surface declarations, not via hardcoded `policies/baseline_modules`.

## Finding DEBT-P2-1 - Generic Orchestrator Files Are Again Over Large-File Thresholds

Severity: P2

Type: framework architecture debt.

Evidence from current line counts:
- `scion/scion/proposal/llm_client.py`: 1240 lines.
- `scion/scion/core/explore_step_pipeline.py`: 1128 lines.
- `scion/scion/core/evidence_recorder.py`: 1022 lines.
- Warning-level generic files include `scion/scion/contract/gate.py` at 855 lines and `scion/scion/proposal/schemas.py` at 845 lines.

Why this matters for v3:
- v3 depends on crisp ownership boundaries: proposal transport, retry semantics, tool sessions, branch lifecycle, and evidence recording should be auditable independently.
- These files now mix enough concerns that regressions like status naming, retry classification, and agent-quality branch memory are harder to review.

Recommended fix:
- Split only along existing responsibility seams after semantic tests are added:
  - `llm_client.py`: provider transport, retry policy, schema parsing, tool-call loop.
  - `explore_step_pipeline.py`: proposal acquisition, contract/verification, quality block handling, lineage/status emission.
  - `evidence_recorder.py`: status writing, summary aggregation, postmortem/rendering helpers.

Suggested tests:
- Keep existing behavior snapshots before splitting.
- Add import-boundary tests that generic modules do not import CVRP/problem packages.

## Alignment Notes

The old audit's largest prompt-boundary issue appears repaired in this commit:
- `scion/scion/proposal/context_manager/manager.py:493-503` now resolves and injects `solver_design_prompt_provider`.
- `scion/scion/proposal/engine/solver_design_prompts.py:40-64` and `:67-92` use provider guidance before generic fallback text.
- `scion/scion/proposal/agentic_code_context.py` no longer embeds `_ALNSVNSSolver`, CVRP solution classes, or route-level algorithm instructions.
