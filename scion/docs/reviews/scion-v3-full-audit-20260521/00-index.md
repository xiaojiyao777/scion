# Scion v3 Full Alignment Audit - 2026-05-21

Scope: independent code audit of current `v0.4-dev` at commit `e04b1de`, using `scion/design/scion-architecture-v3.md` as the baseline. This audit only writes review documents. It does not change production code, experiment raw artifacts, or launch experiments.

Required sources read:
- `scion/docs/AGENT_ONBOARDING.md`
- `scion/design/scion-architecture-v3.md`
- `scion/docs/experiments/v0.4/v0.4-proposal-block-ceiling-sonnet-3r-stopped-analysis-20260521.md`
- `scion/docs/engineering/agentic-proposal-reference/05-claude-code-source-reference-for-scion-v3.md`
- prior results in `scion/docs/reviews/scion-code-audit-20260521-v3-alignment/`
- `scion/docs/engineering/module-debt/large-file-modularization-audit-20260519.md`

Focused verification run:

```text
python -m pytest \
  scion/scion/tests/unit/test_agentic_active_algorithm_facts_prompt.py \
  scion/scion/tests/unit/test_agentic_solver_design_active_tools.py \
  scion/scion/tests/unit/test_runtime_telemetry_guard.py \
  scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py \
  scion/scion/tests/test_contract_solver_design_provider.py -q

43 passed in 1.34s
```

## Overall Result

The current code is materially closer to the v3 blueprint than the older audit snapshot. In particular, the active solver fact packet path is now adapter-owned, provenance/digests are exposed to the agent, the semantic novelty gate consumes the same fact packet when available, and the CVRP-specific C9e/C11 logic is mostly moved behind problem-owned providers.

The remaining highest-risk gap is not the proposal prompt path. It is the generic runtime/protocol/proposal-smoke telemetry layer: it still treats `solver_algorithm_*` counters and some CVRP outcome fields as framework-level concepts. That blocks a clean claim that Scion core is problem-generic.

## Priority Matrix

| ID | Severity | Area | Type | Finding |
| --- | --- | --- | --- | --- |
| CORE-P1-1 | P1 | core/runtime/protocol | Framework generic | Generic runtime/protocol still owns `solver_algorithm_*` telemetry and CVRP-shaped counters. |
| GATE-P1-1 | P1 | proposal/gates/telemetry | Framework generic | Validation-stage activation-missing telemetry is treated as `CONTINUE_EXPLORE`, which is ambiguous for formal validation. |
| CORE-P1-2 | P1 | core/decision | Framework generic | `DecisionFeatures.statistical_metric` is free text and is not checked by the no-free-text guard. |
| GATE-P1-2 | P1 | proposal smoke/gates | Framework generic | Generic proposal smoke/audit compaction references `solver_algorithm_total_distance` and `solver_algorithm_fleet_violation`. |
| CVRP-P1-1 | P1 | CVRP adapter | CVRP adapter | CVRP novelty fact extraction duplicates `fact_packet_digest` into `snapshot_digest`, weakening provenance. |
| TEST-P1-1 | P1 | tests | Test gap | Existing boundary sentinels do not cover runtime/protocol telemetry or a synthetic non-CVRP telemetry surface. |
| CTX-P2-1 | P2 | context/tools | Framework generic | Full code is available for current CVRP active files, but the tool API has hard 12k/24k caps and no chunked read path. |
| CORE-P2-1 | P2 | contract/core | Framework generic | Legacy fallback terms and hardcoded solver-design path aliases remain in generic contract code. |
| LIFECYCLE-P2-1 | P2 | experiments/status | Experiment/ops | `proposal_attempts` and `total_rounds` are attempts-started counters, so an interrupted in-flight attempt can look completed. |
| OPS-P2-1 | P2 | runbook/CLI | Experiment/ops | CLI handles SIGTERM, but `exit.txt` remains launcher/runbook-dependent rather than a first-class CLI artifact. |
| DEBT-P2-1 | P2 | modules/tests | Architecture debt | Several production and test files exceed the v3 large-file thresholds again. |

## Recommended Fix Order

1. Move remaining `solver_algorithm_*` runtime/protocol audit rules behind a problem/surface telemetry descriptor. Keep generic core limited to declared fields, roles, and generic guard outcomes.
2. Split validation activation-missing from ordinary `CONTINUE_EXPLORE`: use a distinct validation repair state/budget, or fail closed and require an explicit repair candidate before validation resumes.
3. Remove or constrain `DecisionFeatures.statistical_metric` so Decision receives only enum/declared metric identifiers.
4. Add a synthetic non-CVRP adapter/runtime fixture that proves generic runtime/protocol/gates work without any `solver_algorithm_*`, route, fleet, or CVRP terms.
5. Add chunked/ranged algorithm file reads, or enforce generated solver-design file size below the maximum retrievable tool payload.
6. Fix CVRP novelty provenance so `snapshot_digest` and `fact_packet_digest` remain separate.
7. Split the large files after the semantic issues are pinned down by tests.

## Next Short Experiment Readiness

No P0 was found that must block the next short CVRP screening experiment. The current CVRP active-facts, prompt-provider, C9e/C11, lifecycle, SIGTERM handling, and LLM transient retry paths are substantially repaired.

However, do not use another short run as evidence of full v3 framework cleanliness until CORE-P1-1 and TEST-P1-1 are fixed. Also avoid treating a formal validation run as architecturally clean until GATE-P1-1 is resolved.

## Document Map

- `01-core-boundary.md` - core/problem-adapter separation and generic-core residue.
- `02-agent-context-tools.md` - agent context, tool outputs, code retrieval, active facts.
- `03-proposal-gates-telemetry.md` - proposal gates, C9e/C11, telemetry validation, retry/repair semantics.
- `04-branch-lifecycle-experiments.md` - branch lifecycle and experiment/ops observability.
- `05-problem-adapter-cvrp.md` - CVRP adapter-specific alignment and risks.
- `06-tests-and-ops.md` - test coverage, large-file debt, and ops gaps.
