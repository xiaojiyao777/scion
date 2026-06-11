# v0.4 Architecture Audit Remediation Status

*Last updated: 2026-06-11*

This is a compact remediation tracker for the v0.4 architecture audit. It does
not restate module evidence; use the numbered audit files for source findings.

## Post-6/7 Disposition

The 6/7 remediation validation remains the source-level repair baseline, but
the later audit set changes the recommended next action:

- [`../v04-audit-agent-experiment-guide-20260609.md`](../v04-audit-agent-experiment-guide-20260609.md)
  is now required reading for post-run analysis. It defines how to resolve
  effective copied configs, counters, prompt visibility, pair-level metrics,
  and v3 layer boundaries before drawing conclusions.
- [`../v04-core-framework-review-20260611.md`](../v04-core-framework-review-20260611.md)
  and
  [`../v04-core-framework-code-review-20260611.md`](../v04-core-framework-code-review-20260611.md)
  reviewed the 2026-06-10 CVRP/Warehouse 8R runs and found the generic v3
  framework path healthy enough for analysis: DecisionFeatures boundaries,
  replay identity, evidence lineage, and warehouse promotion flow were not the
  bottleneck.
- The current blocker is evidence power, runtime-governance semantics,
  branch-depth research, and research-object fit, especially CVRP under a
  strong budget-exhausting ALNS/VNS champion. This should be fixed in v0.4, not
  deferred wholesale to v0.5. CVRP/VRP still needs effective research evidence,
  including the historical promotion mode where objective quality ties or stays
  non-regressive while runtime improves materially.
- The next work should follow
  [`../../design/v0.5-evidence-uplift-roadmap.md`](../../design/v0.5-evidence-uplift-roadmap.md):
  v0.4 lands the measurement/runtime/context/branch-depth repairs and focused
  validation; v0.5 runs the broader governance ablation, reproduction matrix,
  and problem-family comparisons. Do not resume longer CVRP runs as a default
  gate until the v0.4 measurement and runtime semantics are fixed.
- The concrete v0.4 execution split is
  [`../../docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`](../../docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md).

## Counter And Scheduler Semantics

- `max_rounds` / CLI `--rounds`: requested effective screened/formal candidate
  budget.
- `effective_rounds_completed`: budget counter for `max_rounds`.
- `formal_screened_candidates`: formal screening candidates that reached
  Protocol.
- `protocol_evaluated_candidates`: candidates evaluated by Protocol across
  screening, validation, and frozen stages.
- `proposal_attempts_consumed`: proposal/LLM attempts that may include
  proposal-quality blocks and diagnostics.
- `telemetry_repair_attempts`, `validation_repair_required_attempts`,
  `branch_lifecycle_policy_blocks`, `reconcile_lifecycle_steps`, and
  `scheduler_active_slot_blocked_attempts`: separate non-counted counters.
- `total_rounds`: legacy/external attempt surface. Do not use it as requested
  screened-round completion.
- Scheduler: deterministic resource/lifecycle governance. Current v0.4
  scheduling includes active-slot capacity, lifecycle routing,
  same-mechanism follow-up, clean fork, park/reclaim, and diagnostic repair
  routing. These are not Decision-layer promotion/abandon decisions.

## Finding Status

| Finding | Status | Still A Current Problem? | Remediation |
|---|---|---|---|
| R-CORE-001 scheduler documentation drift | Remediated for docs/status terminology | Not as a source-behavior bug. It remains a risk only where old docs or reports reduce scheduler to the obsolete one-line priority-queue summary. | Updated onboarding, current state, engineering map, runbook, and post-run handoff to describe active-slot and lifecycle-aware scheduling. |
| R-CORE-002 round-count terminology | Remediated for docs/status terminology | Not as a source-behavior bug. It remains a risk only if analyses treat `--rounds` or `total_rounds` as total loop/proposal attempts. | Updated docs to define `max_rounds`/`--rounds` as `effective_rounds_completed` budget and to separate proposal, repair, lifecycle, formal screened, and protocol-evaluated counters. |

## Cross-Module Remediation Checklist

| Track | Current Status | Remaining Validation |
|---|---|---|
| P1 durable evidence, promotion, terminal-status integrity | Source remediation implemented in campaign/evaluation/finalizer/promotion/evidence layers and covered by focused regression. A 4R post-audit run exposed a real status/accounting mismatch where lifecycle-soft-archived screening candidates were present in DB/raw metrics but undercounted in loop counters; this is now remediated by carrying structured protocol accounting on `StepResult` independently of finalizer action. Verify2 4R confirmed final `status.json`, `campaign_summary.json`, DB, raw metrics, lineage, and final evidence refs agree on the same formal/protocol candidate counts. | Continue checking the same invariants in the next longer run, especially if validation/frozen stages appear. |
| P1 branch-local research context | Source remediation implemented: production explore path carries branch-local `step_history` into proposal and patch validation context. | Inspect APS/session traces for branch-local history visibility, current workspace context, checkpoint/rollback events, and repair feedback continuity. |
| P1/P2 coherent ProblemRuntimeBundle | Source remediation implemented for production boundary, objective semantics, adapter/provider consistency, lazy evaluation construction, and production-equivalent verification/protocol wiring. Production boundary now requires protocol `_problem_spec` to match the campaign spec by stable hash, while adapter-visible compatibility specs must match by explicit `problem_spec_hash` when available or by problem identity and objective semantics. `ProblemRuntime` exposes problem/adapter/split/seed/runtime bundle hashes. Verify2 4R confirmed the CLI production CVRP path starts and runs under this boundary. | Continue checking CLI and direct-construction paths in longer smoke campaigns and confirm problem id, adapter, metric specs, objective semantics, runner, verification, protocol evidence, split, and seed evidence share one problem identity source. |
| P2 gates/lifecycle explainability | Source remediation implemented for configurable/explained verification/runtime/lifecycle thresholds, C10 diagnostics, V9 strictness, and validation/frozen verification reuse markers. | Confirm real branch evidence/status explains lifecycle/gate blocks with config/threshold metadata and does not collapse lifecycle action into generic reason text. |
| P2/P3 runtime telemetry and feedback semantics | Source remediation implemented: telemetry declarations share a source of truth, `*_active=False` fails consistently, runtime budget diagnostics are side-aware, and C11 can consume problem-declared telemetry templates without runtime consumers seeing templates. | Confirm telemetry declarations, status diagnostics, and agent feedback agree on activation/evaluation/runtime/effect outcomes in the next run. |
| P2/P3 decision, reason-code, and status provenance | Source remediation implemented for decision-layer provenance, split reason-code namespaces, `partial_campaign_evidence`/`protocol_in_flight`, read-only status/summary snapshots, and formal replay identity payloads. Formal experiment audit payloads now include `problem_spec_hash`, `split_manifest_hash`, `seed_ledger_hash`, `patch_digest`, `selected_surface`, `protocol_version`, and `raw_metrics_ref`; lineage write failures degrade summary/status run validity. Candidate patch artifacts now carry a self-contained `replay_identity` using the same generic identity schema as lineage audit payloads. | Verify status/summary can distinguish decision codes, lifecycle codes, proposal diagnostics, protocol observations, bypass/infra categories, replay identity completeness, and lineage integrity without string heuristics on a real run. |
| P3 documentation and terminology drift | R-CORE-001 and R-CORE-002 doc cleanup complete in this pass. | Use `rg` cleanup checks before the next experiment report and require post-run analysis to reconcile the explicit counters above. |
| P3 direct/preview compatibility risks | Source remediation implemented: production-like injected agentic sessions force anchor preflight; preview/direct contract modes are explicit; active-subject provider lookup fails closed in production and marks degraded preview metadata. | Keep direct/preview regressions in focused suites and inspect next APS traces for preview metadata visibility. |
| P3 protocol/runtime/decision cleanup | Source remediation implemented: strict case path safety, side-aware runtime budget saturation, and documented DecisionEngine candidate-runtime veto precedence. | Confirm no champion-only runtime saturation is rendered as candidate repair guidance in the next run. |

## Local Validation Snapshot

Last local validation on 2026-06-07:

- `git diff --check`: passed.
- `python -m compileall -q scion/scion/core scion/scion/protocol scion/scion/problem scion/scion/contract scion/scion/verification scion/scion/runtime scion/scion/proposal scion/tools/launch_cvrp_agentic_campaign.py`: passed.
- `python -m pytest -q scion/scion/tests/unit/core`: 414 passed.
- P3 focused suite covering contract/provider/protocol/runtime/decision paths: 94 passed.
- P1/P2 integration-oriented suite covering protocol, CVRP smoke/control, contract/provider, verification, telemetry, agentic planning, launcher, promotion/status: 309 passed.

Additional validation after the post-audit 4R analysis on 2026-06-07:

- `git diff --check`: passed.
- `python -m compileall -q scion/scion/core scion/scion/protocol scion/scion/problem scion/scion/contract scion/scion/verification scion/scion/runtime scion/scion/proposal scion/tools/launch_cvrp_agentic_campaign.py`: passed.
- Focused lifecycle-accounting regression for soft-abandoned completed screening candidates: 4 passed.
- Formal lineage/replay identity and lineage-degraded status focused suites: 50 passed.
- Production boundary/runtime identity focused suites: 34 passed.
- `python -m pytest -q scion/scion/tests/unit/core`: 422 passed.
- Protocol, CVRP launcher/formal readiness, contract/provider, verification, telemetry, agentic planning, data-root safety, and v3 problem-boundary focused suite: 294 passed.

4R verification after the accounting/replay-identity/runtime-boundary fixes:

- First attempt
  `/home/clawd/research/scion-experiments/v04-audit-identity-accounting-verify-4r-gpt55-20260607T193013Z-claw`
  failed before campaign start because the production boundary compared the
  adapter-visible compatibility spec to the full campaign spec by full stable
  hash. This was a regression in the new boundary hardening.
- The boundary was adjusted generically: protocol `_problem_spec` still uses
  strict stable-hash parity with the campaign spec; adapter-visible specs use
  explicit `problem_spec_hash` when available, otherwise problem identity and
  objective-semantics compatibility. This keeps production fail-closed without
  requiring legacy/compat adapter views to byte-match `ProblemSpecV1`.
- Second attempt
  `/home/clawd/research/scion-experiments/v04-audit-identity-accounting-verify2-4r-gpt55-20260607T193539Z-claw`
  completed with wrapper exit 0 and `run_validity_status=valid`.
- Verify2 final counters agreed across raw protocol metrics, DB experiment
  events, `status.json`, and `campaign_summary.json`:
  `effective_rounds_completed=4`, `formal_screened_candidates=4`,
  `protocol_evaluated_candidates=4`, and `protocol_stage_counts.screening=4`.
- Verify2 used 27 LLM traces, all `gpt-5.5`; request kinds were
  `hypothesis_target_intent=4`, `hypothesis=4`, `tool_selection=14`, `code=5`.
- Verify2 formal replay identity was complete for all 4 screening experiment
  events: `problem_spec_hash`, `split_manifest_hash`, `seed_ledger_hash`,
  `patch_digest`, `patch_hash`, `selected_surface`, `protocol_version`, and
  `raw_metrics_ref` were present; lineage/evidence integrity was `complete`.
- Post-regression validation after the boundary adjustment:
  `git diff --check` passed; compileall passed; core + CVRP formal readiness +
  v3 problem-boundary focused tests passed with 432 tests.

Additional provenance/remediation validation on 2026-06-07:

- Tool-selection provenance is now audit-only and traceable without changing the
  model-visible selector context: transcript and output artifacts agree on
  `deterministic_prefetch_plan_id`; tool-selection LLM traces/session index rows
  carry prompt manifest refs and tooling provenance.
- Formal candidate patch artifacts now write top-level `replay_identity` and
  preserve legacy `replay_metadata`, while lineage audit payloads and candidate
  artifacts share the same replay identity schema and patch digest semantics.
- Screening gate aggregate counts now retain legacy `screening_case_*` fields
  and add explicit `screening_case_level_gate_*` aliases; branch prompt cards
  render concrete case lists as `case_level_positive_cases` /
  `case_level_negative_cases`.
- `git diff --check`: passed.
- `python -m compileall -q scion/scion/core scion/scion/proposal scion/scion/lineage`:
  passed.
- Combined provenance/replay/naming focused tests: 50 passed.
- Broader trace, lineage, decision-finalizer, and summary focused suite:
  172 passed.
- `python -m pytest -q scion/scion/tests/unit/core`: 424 passed.
- CVRP formal readiness + v3 problem-boundary focused suite: 8 passed.

6/7 experiment readiness note, now superseded by the 6/11 evidence-power
reviews:

- Fresh 4R after the provenance/replay fixes completed valid with 4/4 formal
  screened candidates, 0 quality blocks, all LLM traces on `gpt-5.5`, complete
  tool-selection provenance, and complete formal candidate replay identities.
  Independent framework and research-quality analyses found no blocker to try
  8R, while noting that research signal remained weak.
- The first 8R attempt
  `/home/clawd/research/scion-experiments/v04-audit-provenance-replay-verify-8r-gpt55-20260607T210441Z-8r-gpt55-20260607T210441Z-claw`
  ended as `valid_partial_interrupted`: 5/8 formal screened candidates,
  `scheduler_active_slot_blocked_attempts=3`, 0 quality blocks, all LLM traces
  on `gpt-5.5`, complete tool-selection provenance, and complete replay
  identity. Experiment analyses concluded this is useful partial evidence but
  not a valid 8R gate.
- Root cause was active-slot reclaim handoff: after the fifth formal screening
  candidate, the scheduler needed a clean fork but 3/3 active slots were full;
  reclaim found eligible branches but required a Decision-origin park marker
  and deadlocked into repeated `capacity_blocked` skips.
- Scheduler reclaim is now remediated generically: `new_branch_reclaim` may
  write a `scheduler_active_slot_reclaim` origin `park_lineage` marker for a
  branch that already satisfies the structured reclaim predicate; overflow
  reconciliation still requires existing lifecycle/Decision-origin markers.
  This keeps the change in resource governance, not promotion/abandon Decision.
- Scheduler reclaim validation after the fix: `git diff --check` passed;
  compileall for scheduler/branch-loop files passed; focused reclaim tests
  passed with 6 tests; broader scheduler/core focused suite passed with 108
  tests; `python -m pytest -q scion/scion/tests/unit/core` passed with 424
  tests; CVRP formal readiness + v3 problem-boundary focused suite passed with
  8 tests.
- The 8R rerun after scheduler reclaim remediation
  `/home/clawd/research/scion-experiments/v04-scheduler-reclaim-verify-8r-gpt55-20260607T222206Z-8r-gpt55-20260607T222206Z-claw`
  completed valid with 8/8 formal screened candidates, 0 quality blocks,
  0 `scheduler_active_slot_blocked_attempts`, all 59 LLM traces on `gpt-5.5`,
  complete tool-selection provenance, and complete replay identities for all
  8 candidate patch artifacts. At the time, independent framework and research
  analyses recommended proceeding to 12R.
- Caveat: this successful 8R did not actually emit a scheduler-origin reclaim
  audit event; it proves the post-fix campaign can complete 8R without the
  previous partial-stop failure, while the exact scheduler-origin reclaim path
  remains covered by focused unit tests. The next longer run should explicitly
  report whether `scheduler_active_slot_reclaim` appears in campaign metadata.
- Superseding note: the later 6/10 8R CVRP/Warehouse comparison and 6/11
  reviews shift the next gate away from "run 12R" and toward v0.4 measurement
  calibration, runtime-governance repair, branch-depth/context repair, and then
  focused VRP/warehouse validation.
