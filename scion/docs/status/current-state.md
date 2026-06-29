# Scion v0.4 Current State

Last updated: 2026-06-29

This file is the operational resume point, not a run log. Historical root
chronology belongs in focused experiment reports and git history.

## Operating Frame

- Branch: `codex/v04-evidence-repair-plan`.
- Boundary authority: `scion/design/scion-architecture-v3.md`.
- v0.4 closes only after Scion demonstrates effective research behavior:
  warehouse should recover useful continuous optimization from champion `v2`,
  and CVRP/VRP should produce evidence-backed solver-design follow-up.
- v0.5 is for broader experiment matrices. Do not defer v0.4 framework
  stability, prompt/context quality, runtime semantics, or effective-agent
  research to v0.5.
- Current posture: avoid broad budgets, generic truncation/compression, and
  decorative gates. Keep CVRP/warehouse semantics problem-owned and keep
  `DecisionFeatures` problem-neutral.

## Current Design Gate

- Designs A-K in `scion/design/v0.4-effective-research-repair-design.md` are
  accepted local framework repairs for scheduling status, research-guidance
  contracts, lifecycle/failure routing, target-intent authority, launcher
  lifecycle, and mechanism-evidence follow-up. They remain generic core
  contracts while CVRP/warehouse details remain problem-owned.
- Design L is implemented locally: budget-exhausting runtime aggregates remain
  in raw evidence, but proposal-visible feedback, phase causal runtime
  evidence, branch memory/dossier, and feedback-tool stats render
  `runtime_regression_rate_interpretation=not_applicable_budget_exhausting`
  instead of numeric `runtime_regression_rate`.
- Design M is implemented locally: budget-exhausting low/cached/insufficient or
  aggregate-excluded runtime evidence is observational and cannot accumulate
  runtime-evidence pressure or trigger `runtime_evidence_completeness_clean_fork`.
  Stale branch-card fresh-runtime markers are also suppressed under
  `budget_exhausting`. Comparative runtime pressure behavior is preserved.
- Local validation uses this machine's conda `claw` environment. The combined
  proposal/runtime-pressure/protocol focused suite passes (`108 passed`), and
  `git diff --check` is clean.
- Earlier WSL conda `scion` focused validation passed (`108 passed`) after
  sync, but current continuation should use this server's local conda `claw`
  environment. Do not assume the WSL reverse SSH channel is available until it
  has been rechecked after the local WSL runner is brought back up.
- Postrun acceptance rechecks now prefer the stored inventory artifact declared
  by the rebuild manifest before falling back to live inventory rebuild. This
  prevents historical roots from failing prepared-contract git consistency
  solely because the checkout advanced after postrun artifacts were generated.
  Local and WSL postrun acceptance tests pass (`86 passed` each), and the
  warehouse v2 positive-control root rechecks ready with
  `checks.inventory_loaded.detail.source=stored_postrun_inventory`. Detailed
  report:
  `scion/docs/experiments/v0.4/v04-postrun-acceptance-stored-inventory-recheck-20260623.md`.
- Read-only v3-boundary/code-quality audit found no blocker for Designs L/M or
  stored-inventory rechecks. The remaining engineering-quality constraint is to
  freeze new semantics in the oversized postrun/helper scripts; future work in
  that area needs a design split into named ports or problem-owned validators
  rather than more helper/projection growth.
- Current local gpt-5.5 proxy at `127.0.0.1:8080` is authenticated after the
  2026-06-28 Codex relogin. The latest check did not require another proxy
  restart. `/v1/models` lists `gpt-5.5`, and a `gpt-5.5` chat completion
  returns HTTP 200.
- Prepared successor-focus arbitration is implemented locally in the proposal
  layer. When a prepared launch focus marks branch-local mechanism ids as
  `reviewed_mechanism_ids` and supplies non-empty
  `successor_opportunity_families`, target-intent prompts and formal
  hypothesis prompts no longer force same-mechanism continuation for those
  reviewed ids, schema preview treats same-mechanism branch authority as
  superseded for the prepared run, and reviewed mechanism repeats fail with a
  proposal-only launch-focus guard. Default-avoid target-intent rejection is
  now inherited by formal hypothesis prompts through the generic
  `target_intent_rejected` authority field, and broad default-avoid matching
  no longer uses `target_file` path tokens as mechanism identity. The latest
  local repair also prevents an already rejected target intent from becoming a
  strong formal-hypothesis binding source, and requires a single-token
  `variants` match to use a sufficiently specific token before rejecting a
  target. This is generic field-driven proposal behavior, not CVRP-specific
  core logic, and remains excluded from `DecisionFeatures`. Focused local
  validation passes for prepared-successor/proposal-pipeline, target-intent
  binding, schema retry, CVRP launch guidance, and v3 problem-boundary suites,
  plus `py_compile` and `git diff --check`.
- The successor12 resume run exposed and repaired one remaining prepared
  successor-focus scheduler gap: copied reviewed `EXPLORE_EXPAND` branches were
  still selected by the high-priority tier before the research-state
  successor-focus filter ran. The scheduler fix is generic and field-driven:
  only reviewed branch-local mechanism ids in `EXPLORE_EXPAND` are suppressed
  for prepared successor clean-fork selection; validation/frozen states are not
  suppressed; when capacity is full the result is an explicit capacity block
  with prepared-successor audit metadata rather than an implicit same-mechanism
  repeat. This remains outside `DecisionFeatures` and contains no CVRP-specific
  core logic.
- Generic launcher resume handling is repaired locally for CVRP and warehouse:
  resumed campaign runtime state is copied forward, while stale terminal
  artifacts from the copied source campaign are quarantined under
  `run_root/resume_snapshot/` instead of occupying canonical current-run paths
  (`run_status.json`, `status.json`, `campaign_summary.json`, `exit.txt`, and
  `artifacts/formal_candidates/index.jsonl`). Launch metadata and postrun
  inventory expose `resume_snapshot_ref`, and prepared prompt-context readiness
  reads copied campaign status/summary from the declared snapshot as historical
  resume context instead of requiring stale canonical campaign files. Running
  and preflight-failure launcher status now preserve the same snapshot
  reference for launched resumed roots. In-flight Protocol status explicitly
  reports running state, `complete=false`, pair counters, child subprocess
  details, and redacted case/seed aliases without changing completed-only
  counters such as `protocol_metric_results` or `last_result`.
  Local focused validation passes for launcher resume preparation, CVRP and
  warehouse resume launchers, prepared-handoff rebuilds, running-status
  reporting, and postrun snapshot/in-flight summaries.
- Prepared handoff resume visibility is repaired locally. Analysis brief and
  artifact inventory generation now load quarantined resume
  `campaign_summary.json` through `scion.postrun.handoff.resume_snapshot` and
  render bounded `resume_snapshot.top_branches` as report-only launch input,
  not current-run evidence. Rebuilding the prepared successor6 root shows the
  active weak-positive `bounded_intra_route_3opt` branch first, including
  `followup_recommended=true`, `followup_required=false`,
  `weak_positive_followup`, CMT2 loss caveat in the branch card text, and
  allowed follow-up actions. This is a generic resume-snapshot handoff repair,
  not a CVRP-specific core gate.
- Design N skeleton from
  `scion/design/v0.4-postrun-readiness-and-opportunity-ports.md` is
  implemented locally as the problem-neutral `scion.postrun` package:
  typed postrun inventory, lifecycle, exposure, problem-review, registry, and
  readiness-orchestrator ports with dummy generic tests. `check_postrun_acceptance.py`
  now computes a typed readiness summary through an explicit compatibility
  adapter path while preserving default JSON/Markdown output. The CVRP
  large-twoopt and warehouse follow-up summaries have moved behind
  problem-owned providers:
  `scion.problems.cvrp.postrun_review.CvrpPostrunSummaryProvider` builds the
  legacy `cvrp_large_twoopt_summary` field, and
  `scion.problems.warehouse_delivery.postrun_review.WarehousePostrunSummaryProvider`
  builds `warehouse_followup_summary`. The typed adapter registers both
  problem review ports, and checker recomputation imports both review summaries
  from problem packages. Generic acceptance is now split across named ports:
  `PostrunLifecycleAcceptancePort`, `PostrunArtifactAcceptancePort`,
  `PostrunEvidenceConsistencyAcceptancePort`,
  `PostrunReviewInputAcceptancePort`,
  `PostrunPromptVisibilityAcceptancePort`, and
  `PostrunResearchTelemetryAcceptancePort`. The checker still supplies
  required-summary policy, expected-summary rebuilds, active-subject legacy
  prompt policy, and problem-family enablement; generic ports preserve legacy
  check names/payloads and do not interpret CVRP/warehouse/VRP review
  semantics. Failure-taxonomy signature comparison lives in a named telemetry
  evaluator. Problem-summary actionability policy is now problem-owned through
  `ProblemSummaryActionabilitySpec` in the CVRP and warehouse packages; the
  checker keeps only a compatibility registry derived from those specs.
  Problem-summary input consistency now dispatches to problem-owned review
  signatures: warehouse owns follow-up/plateau consistency and CVRP owns
  large-twoopt consistency, while `scion.postrun` owns only the common
  protocol/measurement/runtime/continuity/quality-block projection. Local and
  WSL focused validation passes for provider/readiness/boundary, postrun
  brief, acceptance, and opportunity visibility suites; the
  artifact/lifecycle/evidence/review-input/prompt-visibility/research-telemetry
  port tests pass (`19 passed` each), and full postrun acceptance passes
  (`85 passed` each) in both environments. Prepared-run inventory now follows
  the same authority split: generic prepared-manifest/launcher/report-family
  checks live in `scion.postrun.inventory.prepared_contract`, while
  CVRP-specific prepared large-twoopt measurement/protected-case/resume/split
  coverage checks live in `scion.problems.cvrp.postrun_handoff`, and warehouse
  follow-up/measurement handoff checks live in
  `scion.problems.warehouse_delivery.postrun_handoff`. The legacy
  `postrun_artifact_inventory.py` is now a 443-line CLI/Markdown wrapper;
  inventory loading lives in cohesive `scion.postrun.inventory` package
  modules for constants, lifecycle, evidence coverage, traces, database
  readers, prepared ports, and the public loader. Problem-owned default ports
  plus legacy problem launcher status extensions live in
  `scion.problems.postrun_inventory`. Output JSON keys, Markdown rendering,
  launch-readiness behavior, and postrun acceptance compatibility are
  preserved through that adapter boundary, not by owning problem semantics in
  the generic inventory package. The package is source guarded against
  CVRP/warehouse/VRP vocabulary, and all new inventory modules remain below
  the 1000-line warning threshold. Local focused validation passes for postrun
  inventory/brief/acceptance/rebuild and v3 boundary suites (`163 passed`);
  strict readiness passes on the successor6 root with no required failures.
  Launch-readiness focused tests fail before commit only because the current
  worktree is intentionally dirty and trips `git_runtime_worktree_clean`.
  Prepared prompt-context focus
  signals for CVRP and warehouse now come from the same problem-owned ports;
  `rebuild_prepared_handoff.py` merges those signals and retains common
  artifact orchestration plus common decision-boundary readiness. Prepared
  prompt bridge metadata is also problem-owned:
  `scion.problems.cvrp.prompt_bridge` and
  `scion.problems.warehouse_delivery.prompt_bridge` own measurement and
  active-subject signal names, source markers, problem-v1 candidates, and
  surfaces. `scion.postrun.handoff.prompt_context_readiness` owns the generic
  spec, problem-v1 resolver, provider-payload summary, and prepared
  prompt-context readiness build/render path used by both rebuild and
  launch-readiness tooling. Shared prepared prompt/context audit summaries now
  live in `scion.postrun.handoff.prepared_prompt_context`; the legacy
  `scion/tools/prepared_prompt_context.py` path is only a compatibility
  wrapper. `rebuild_prepared_handoff.py` is back to CLI/file-output
  orchestration rather than owning readiness semantics. Local validation
  passes for rebuild delegation/problem prepared-handoff ports (`8 passed`),
  CVRP/warehouse prepare launchers (`2 passed`), py_compile, and the
  dirty-sensitive postrun artifact inventory plus launch-readiness suite
  (`134 passed`).
- The follow-up prepared prompt-context boundary split is implemented locally:
  CVRP and warehouse active-subject/code-constraint and measurement-diagnostics
  prompt-summary semantics live in `scion.problems.cvrp.prompt_bridge` and
  `scion.problems.warehouse_delivery.prompt_bridge`. Generic handoff code
  dispatches through `ProblemPromptBridgeSpec`; `prepared_prompt_context.py`
  keeps only neutral research-focus/research-shape summaries; and
  `check_launch_readiness.py` delegates prepared prompt-context artifact
  validation to `scion.postrun.handoff.prompt_context_readiness_validation`.
  Focused local validation passes for source-boundary, rebuild, and problem
  port tests (`12 passed`), plus py_compile, `git diff --check`, and the
  dirty-sensitive postrun artifact inventory plus launch-readiness suite
  (`134 passed`).
- Design O initial slice is implemented locally as
  `scion.measurement.MeasurementConsumerView`. It reduces problem-owned
  measurement declarations to generic status/runtime/pairing/effect/MDE fields
  without calibration refs, replay rows, BKS, case gaps, or mechanism rankings.
  `ProtocolConfig.with_problem_measurement()` now consumes that typed view
  while preserving its legacy readiness payload. Proposal-context measurement
  diagnostics now consume the same view while keeping calibration provenance
  proposal-only. Prepared CVRP/warehouse measurement handoff builders now
  consume the typed view for launch focus. Postrun research-efficiency
  calibration fallback now uses the typed view for copied calibration artifacts
  instead of hand-rolled readiness reconstruction. Local conda `claw` and WSL
  conda `scion` postrun/measurement focused tests pass (`54 passed` each).
  Launch-readiness and postrun brief paths consume reduced prepared/report
  payloads rather than interpreting measurement declarations directly.
- Design P proposal-context slice is implemented locally as `scion.opportunity` plus
  `scion.problems.cvrp.opportunity.CvrpOpportunityProvider`. The generic schema
  owns only proposal-only visibility/redaction and contains no CVRP solver
  semantics; CVRP residual opportunity, mechanism evidence, protected cases,
  evidence requirements, measurement view, and default-avoid summaries live in
  the problem-owned provider. The current CVRP opportunity-quality slice adds a
  compact prepared large-instance two-opt evidence recipe, CMT2/CMT4 protection
  requirements, and measurable-opportunity evidence requirements; current-run
  large-twoopt postrun summaries can update requirement status when supplied.
  Adapter/context-manager hooks now expose the typed summary to
  hypothesis context; the generic prompt projection renders a bounded
  standalone `Problem Opportunity Summary` section; prompt manifests classify
  the section as `research_signal`. Focused local/WSL validation passes
  (`57 passed` each), and the current opportunity-quality slice passes locally
  and on WSL (`15 passed` each). Postrun proposal-visibility reports now aggregate
  problem-opportunity section presence/visibility from prompt manifests without
  parsing raw prompts, raw responses, or problem semantics; local/WSL postrun
  visibility suites pass (`144 passed` each). CVRP-owned postrun review now
  adds `cvrp_opportunity_usage_summary`, which classifies structured proposal
  fingerprints as used, contrasted, ignored/unproven, default-avoid repeats, or
  selected-with-checklist-unproven for the prepared top opportunity without
  making the summary a Decision input. The current broader local/WSL
  acceptance/visibility set passes (`92 passed` each).
- A narrow local CVRP follow-through slice now separates required-evidence
  checklist proof from solver outcome: `cvrp_large_twoopt_summary` emits
  problem-owned `evidence_requirement_statuses`, opportunity usage consumes
  them as `required_evidence_proof`, and provider prompt status can report
  required evidence observed even when direct positive-at-MDE outcome evidence
  is absent. Focused local conda `claw` validation for provider, usage,
  postrun brief, and legacy large-twoopt cases passes (`15 passed`), with
  `py_compile` and `git diff --check` clean.
- Design Q initial relay is implemented locally as
  `scion.opportunity.commitment`: code context now derives a proposal-only
  `Opportunity Evidence Commitment` from the redacted problem opportunity
  summary plus approved-hypothesis mechanism ids, and code prompts render it as
  a bounded standalone section. Prompt manifests classify the section as
  `research_signal`. The relay is excluded from `DecisionFeatures` and does
  not change Protocol, scheduler, lifecycle, runtime-pressure, or promotion
  behavior. Local focused opportunity/code-prompt tests pass (`15 passed`), and
  the broader postrun visibility/agentic prompt set passes (`117 passed`).
- Design R initial visibility slice is implemented locally: prompt manifests
  now carry manifest-safe opportunity commitment ids/digests, proposal
  trajectory traces project `opportunity_commitment_visibility`, postrun prompt
  context summaries aggregate code-phase commitment section visibility, and
  prompt-visibility consistency checks compare stored vs recomputed commitment
  visibility only when a commitment section or summary is actually present.
  A narrow R2 audit field now reports manifest-safe commitment summaries that
  lack the rendered `Opportunity Evidence Commitment` section, including the
  code-phase count, so relay drops are visible without parsing raw prompts or
  problem semantics. This is report-only, excludes raw prompt/response/patch
  bodies, and does not alter `DecisionFeatures`, Protocol, scheduler,
  lifecycle, runtime-pressure, or promotion behavior. Focused local
  opportunity/prompt-visibility tests pass (`18 passed`), and broader local
  postrun brief/acceptance tests pass (`124 passed`). The WSL checkout was
  synced to head `7394757b`, and an isolated WSL no-resume worktree at commit
  `23f24bca` ran the fresh Design Q/R root
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-designqr-codeprompt-fresh-23f24bca-data-2r-gpt55-20260625T140430Z-claw`.
  It passed strict launch readiness, finished valid/complete and
  postrun-ready, and was mirrored locally to
  `/home/clawd/research/scion-experiments/v04-cvrp-designqr-codeprompt-fresh-23f24bca-data-2r-gpt55-20260625T140430Z-claw`.
  This live-validates the code-prompt commitment relay: the code prompt
  rendered `Opportunity Evidence Commitment` for
  `large_instance_intra_route_two_opt_seed`, postrun visibility reported
  `code_section_visible_trace_count=1`, `commitment_summary_trace_count=1`,
  and both summary-without-section counts `0`. It remains solver-negative and
  checklist-unproven; detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-designqr-codeprompt-postrun-20260625.md`.
- The WSL proof-status follow-up root
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-proofstatus-followup-05ade2e0-2r-gpt55-20260625T155106Z-claw`
  resumed the Design Q/R campaign from WSL runtime commit `05ade2e0`, finished
  valid/complete and postrun-ready, and was mirrored locally to
  `/home/clawd/research/scion-experiments/v04-cvrp-proofstatus-followup-05ade2e0-2r-gpt55-20260625T155106Z-claw`.
  It validates the live `evidence_requirement_statuses` to
  `required_evidence_proof` carrier, but remains solver-negative and
  checklist-unproven: 2 screening rows, champion `v1`, promotions `0`,
  positive rows `0`, rows at or above MDE `0`, same-mechanism follow-up `2/2`,
  `required_evidence_proof.checklist_status=not_ready`, and
  `cvrp_opportunity_usage_summary.usage_status=checklist_unproven`. The
  problem-owned review alignment repair now recognizes
  `large_instance_intra_route_two_opt_seed` as the prepared large-twoopt
  evidence family and counts `zero_objective_effect` as measured
  objective-effect telemetry, while keeping positive-at-MDE and CMT evidence
  separate from solver success. Recomputing the local mirror now reports
  `mechanism_family_available=true`, activation/objective/phase counts `2/2/2`,
  `required_evidence_proof.checklist_status=unproven`, and only CMT case
  protection missing from the requirement checklist. Detailed reports:
  `scion/docs/experiments/v0.4/v04-cvrp-seed-family-review-alignment-20260626.md`
  and
  `scion/docs/experiments/v0.4/v04-cvrp-proofstatus-followup-postrun-20260625.md`.
- The CMT follow-through repair now projects that remaining missing field into
  the CVRP problem-owned code-phase opportunity commitment: next
  `large_instance_intra_route_two_opt_seed` code prompts should see
  `missing_cmt_case_protection_evidence` and the requirement for case-level
  `total_distance` deltas on CMT2 and CMT4. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-cmt-commitment-followthrough-20260628.md`.

## Current Decision

- v0.4 is not closed. The remaining acceptance question is effective research
  behavior, not more broad framework churn.
- CVRP has accepted framework evidence for active-slot scheduling,
  weak-positive follow-up, target-intent authority, mechanism-evidence
  follow-up, MDE-aware rejection, prompt/source visibility, and
  budget-exhausting runtime semantics. The prepared seed-family review repair
  also separates observed large-twoopt requirement evidence from positive
  solver outcome. The CMT gap is now closed at the report layer: generic
  research-efficiency postrun projection carries bounded case-level metric
  deltas from public raw-metrics refs, and the CVRP-owned review consumes them
  as CMT2/CMT4 `total_distance` protection evidence. CVRP still lacks solver
  improvement or promotion.
- The latest local CVRP successor6 run is complete and postrun-ready:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor6-dbd478af-local-2r-gpt55-2r-gpt55-20260628T172422Z-claw`.
  It launched from commit `dbd478af`, resumed successor5, and validates the
  generic resume-snapshot branch handoff repair under live execution. The run
  finished valid/complete with wrapper exit `0`, 2 of 2 effective screening
  rows, 2 Protocol metric rows, 2 proposal attempts, 0 quality blocks, and
  0 active-slot blocks. Strict postrun acceptance reports
  `current_run_analysis_ready=true` and `failed_required_checks=[]`; the only
  failed optional check is `postrun_report_status_marker`. Solver outcome is
  negative: champion stayed `v1`, rows at or above MDE were `0`, positive rows
  were `0`, and all available CI highs were below MDE. Round 1 expanded the
  active `bounded_intra_route_3opt` branch to 48 valid pairs, then abandoned it
  as quality regression after CMT2 and other losses. Round 2 clean-forked to
  `farthest_noise_related_removal`, reached 32 valid pairs, and abandoned it as
  quality regression. This is positive framework evidence for continuation,
  MDE-aware rejection, and lesson transfer, not CVRP solver progress. Detailed
  report:
  `scion/docs/experiments/v0.4/v04-cvrp-successor6-branch-handoff-rejection-review-20260628.md`.
- The current local CVRP problem-owned guidance repair incorporates successor6
  negative evidence into structured prepared handoff fields. `reviewed_mechanism_ids`
  and `reviewed_successor_evidence.mechanisms[]` now include
  `bounded_intra_route_3opt`, `radial_string_removal`, and
  `farthest_noise_related_removal` alongside earlier reviewed successor paths,
  with exact default-avoid directions for unchanged repeats. The CVRP adapter
  proposal projection now ranks `construction_seed_portfolio` first only when
  same-run seed-effect evidence is isolated, keeps materially different
  `destroy_repair_selection` as the next eligible family, and demotes bounded
  local search unless the hypothesis names a non-reviewed causal path. This is
  CVRP-owned guidance/projection, not generic core or `DecisionFeatures`
  behavior.
- The previous local CVRP successor7 run is complete and postrun-ready:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor7-47c8169b-local-2r-gpt55-20260628T192208Z-claw`.
  It launched from commit `47c8169b`, resumed successor6, and selected a real
  construction seed selection mechanism, `savings_seed_selection_probe`, rather
  than repeating reviewed 3-opt/radial/farthest mechanisms. The run finished
  valid/complete with 2 of 2 effective screening rows, 0 quality blocks, and
  0 active-slot blocks. Strict postrun acceptance reports
  `current_run_analysis_ready=true`, `delegation_ready=true`, and no failed
  required checks; the only failed optional check is
  `postrun_report_status_marker`. Solver outcome is still below threshold:
  champion stayed `v1`, rows at or above CVRP MDE were `0`, screening rows were
  `4/2/26` then `4/1/43` wins/losses/ties, and both median deltas were `0.0`.
  The key framework gap is now enforcement, not routing: the candidate recorded
  construction activation/phase telemetry without same-mechanism direct
  objective-effect `record_move`. The current local repair adds a CVRP-owned
  proposal-side patch-quality block for construction seed/portfolio patches
  lacking selected-seed-vs-baseline direct effect attribution under the declared
  mechanism id. This is problem-owned solver-design quality, not a generic core
  gate.
- The previous local CVRP successor8 run is complete and postrun-ready:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor8-ac64db75-local-2r-gpt55-20260628T204428Z-claw`.
  It launched from commit `ac64db75`, resumed successor7, and validated the new
  construction-seed enforcement: the candidate again selected
  `savings_seed_selection_probe`, but this time included same-mechanism direct
  objective-effect telemetry through `record_move(... delta=..., best_improved=...)`.
  Strict postrun acceptance reports `current_run_analysis_ready=true`,
  `delegation_ready=true`, and no failed required or optional checks. A CVRP-owned
  alias-registry repair now maps savings seed-selection identifiers into
  `construction_seed_portfolio` for successor/opportunity postrun review. Rebuilt
  successor8 acceptance reports `construction_seed_portfolio` observed with
  checklist `proven`, activation/objective/phase counts `2/2/2`, CMT2/CMT4
  protection observed, and outcome `measured_no_positive_at_mde`. This is clean
  framework/evidence-chain progress, not solver progress: 2 screening rows,
  champion stayed `v1`, rows at or above CVRP MDE were `0`, and median deltas
  were `0.0`. CVRP prepared guidance now records
  `savings_seed_selection_probe` as reviewed/default-avoid evidence; future
  construction revisits must name a distinct construction seed-selection causal
  path and direct objective-effect evidence plan.
- The previous local CVRP successor9 run is complete and postrun-ready:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor9-fb685975-local-2r-gpt55-20260628T221602Z-claw`.
  It launched from commit `fb685975`, resumed successor8, and validated that
  reviewed/default-avoid guidance suppresses the savings branch: prepared
  successor focus clean-forked away from `savings_seed_selection_probe` and
  selected a new bounded-local-search mechanism,
  `bounded_ejection_chain_relocate`. The run finished valid/complete with 2 of
  2 effective screening rows, 2 Protocol rows, 0 quality blocks, and 0
  active-slot blocks. Strict postrun acceptance reports
  `current_run_analysis_ready=true`, `delegation_ready=true`, and no failed
  required or optional checks after rebuilding the ejection-chain alias mapping.
  This is positive framework/evidence-chain progress and marginal solver
  signal, not promotion-grade progress: median deltas were `4.25` and `3.75`,
  max effect/MDE ratio was `0.429293`, rows at or above MDE were `0`, CMT2 and
  CMT4 were losses in the expanded screening row, and champion stayed `v1`.
  CVRP prepared guidance now records `bounded_ejection_chain_relocate` as
  reviewed/default-avoid evidence; future bounded-local-search revisits must
  name a distinct causal path with direct objective-effect evidence.
- The previous local CVRP successor10 run is complete and postrun-ready:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor10-20620b3a-local-2r-gpt55-20260628T233735Z-claw`.
  It launched from commit `20620b3a`, resumed successor9, and validated that
  the reviewed/default-avoid guidance suppresses savings/ejection-chain
  repeats. The run clean-forked to two destroy/repair mechanisms,
  `polar_sweep_destroy_repair` and `route_fragment_recombination_repair`.
  It finished valid/complete with 2 of 2 effective screening rows, 2 Protocol
  rows, 0 quality blocks, and 0 active-slot blocks. Strict postrun acceptance
  reports `current_run_analysis_ready=true`, `delegation_ready=true`, and no
  failed required or optional checks after rebuild. This is strong
  framework/effective-research evidence and weak solver evidence, not
  promotion-grade progress: both rows were `32/32` valid with 0 failed pairs,
  champion stayed `v1`, rows at or above MDE were `0`, `polar_sweep` screened
  W/L/T `11/15/6` with pair median `0.0` and CMT2/CMT4 medians
  `-19.5`/`-12.0`, and `route_fragment` screened W/L/T `13/13/6` with pair
  median `0.0`, CMT2 median `-4.5`, and CMT4 median `3.0`. CVRP prepared
  guidance now records both mechanisms as reviewed/default-avoid
  destroy/repair evidence; future destroy/repair revisits must name a distinct
  causal path with direct objective-effect evidence.
- The latest local CVRP successor11 run is complete and postrun-ready:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor11-0c402130-local-2r-gpt55-20260629T004514Z-claw`.
  It launched from commit `0c402130`, resumed successor10, and validated that
  reviewed/default-avoid guidance suppresses the previously reviewed savings,
  ejection-chain, polar-sweep, and route-fragment paths. The run clean-forked to
  `adjacency_pair_removal_repair` and `load_compatible_ruin_recreate`. It
  finished valid/complete with 2 of 2 effective screening rows, 2 Protocol rows,
  0 quality blocks, and 0 active-slot blocks. Strict postrun acceptance reports
  `current_run_analysis_ready=true`, `delegation_ready=true`, and no failed
  required or optional checks after rebuild. This is continued effective-research
  evidence, not promotion-grade solver progress: both rows were `32/32` valid
  with 0 failed pairs, champion stayed `v1`, rows at or above MDE were `0`,
  `adjacency_pair_removal_repair` screened W/L/T `15/11/6` with pair median
  `0.0` and CMT2/CMT4 medians `-7.5`/`-6.0`, and
  `load_compatible_ruin_recreate` screened W/L/T `16/11/5` with pair median
  `0.5` and CMT2/CMT4 medians `-13.0`/`-10.0`. CVRP prepared guidance now
  records both mechanisms as reviewed/default-avoid destroy/repair evidence.
- Previous local CVRP CMT-commitment follow-through root:
  `/home/clawd/research/scion-experiments/v04-cvrp-cmtcommit-33e79e0b-server-2r-2r-gpt55-20260628T022008Z-claw`.
  It finished valid/complete and postrun-ready with 2 of 2 effective screening
  rows, but remains solver-negative and not clean acceptance: it launched from
  old commit `33e79e0b` before the resume-snapshot repair and the checkout
  advanced while it was live. First screening was 32/32 valid with 2 wins, 2
  losses, and 28 ties; expanded screening was 48/48 valid with 3 wins, 3
  losses, and 42 ties. Postrun interpretation is
  `protocol_evaluated_without_large_twoopt_direct_evidence`; opportunity usage
  is `checklist_unproven`, with CMT protection still missing. Treat it as
  weak effective-research behavior and a continuation seed, not solver
  improvement.
- Clean local CVRP CMT-commitment follow-up:
  `/home/clawd/research/scion-experiments/v04-cvrp-cmtcommit-404c4f8c-cleanfollow-2r-gpt55-20260628T034012Z-claw`.
  It resumed the previous CMT-commitment campaign from current HEAD
  `404c4f8c`, passed strict launch readiness, and finished wrapper/postrun-ready:
  validity `valid`, completeness `complete`, 2 of 2 effective screening rows,
  2 Protocol metric rows, 2 proposal attempts, 0 quality blocks, and
  `last_stop_reason=max_rounds_exhausted`. First screening was 32/32 valid
  with 3 wins, 2 losses, and 27 ties; expanded screening was 48/48 valid with
  1 win, 1 loss, and 46 ties. The run is clean effective-research evidence for
  same-branch low-SNR follow-up and mechanism telemetry, not solver progress:
  postrun interpretation is
  `protocol_evaluated_without_large_twoopt_direct_evidence`, activation,
  objective, and phase evidence are observed in 2 of 2 Protocol rows, and
  positive-at-MDE is absent. After rebuilding postrun acceptance with the
  report-only case-delta projection, opportunity usage is `used`,
  `required_evidence_proof.checklist_status=proven`, CMT2/CMT4 protected cases
  are observed, `evidence_requirement_statuses.status=complete`, and
  `check_postrun_acceptance.py --require-current-run-ready` reports
  `current_run_analysis_ready=true` with no failed required checks. During
  postrun, the stored inventory recovered `resume_snapshot_ref` from the
  prepared manifest, but final root `run_status.json` dropped the field after
  copying campaign status; the local final-status writer repair now preserves
  resume metadata for future roots.
- Latest local CVRP postprojection follow-up:
  `/home/clawd/research/scion-experiments/v04-cvrp-postprojection-followup-e687d758-local-4r-gpt55-4r-gpt55-20260628T065805Z-claw`.
  It launched from commit `e687d758`, finished valid/complete and
  postrun-ready, and rechecks with `current_run_analysis_ready=true`,
  `delegation_ready=true`, and no failed required postrun-acceptance checks.
  It is clean framework evidence, not solver progress: 4 of 4 effective
  rounds, 4 screening Protocol rows, 0 quality blocks, champion still `v1`,
  promotions `0`, positive rows `0`, and rows at or above CVRP MDE `0`.
  The important conclusion is problem-owned: the
  `large_instance_intra_route_two_opt_seed` checklist is now proven, including
  activation/objective/phase and CMT2/CMT4 protection evidence, but measured
  `measured_no_positive_at_mde`. The current local CVRP guidance repair therefore
  downgrades that seed to reviewed evidence/default-avoid and rotates the next
  branch slot to a materially different successor opportunity family
  (`bounded_local_search_variant` or `destroy_repair_selection`) unless a
  same-seed revisit explicitly names a new causal path. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-postprojection-successor-portfolio-20260628.md`.
- Latest local CVRP successor diagnostic/evaluation:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor-7a4590a7-local-1r-gpt55-20260628T111147Z-claw`.
  It launched before the final `0c0afd9b` rejected-binding prompt fix, from
  runtime commit `7a4590a7`, but it validates the repaired successor-focus
  propagation and clean successor branch path. The target-intent prompt
  rendered prepared successor/default-avoid guidance, selected
  `bounded_2node_cross_exchange` in `bounded_local_search_variant`, and did
  not repeat the reviewed large-instance two-opt seed or acceptance variants.
  The run finished wrapper-valid/complete and postrun-ready with
  `current_run_analysis_ready=true`, `delegation_ready=true`, 1 of 1 effective
  Protocol row, 0 quality blocks, 0 telemetry failures, and 32 of 32 valid
  screening pairs. It is solver-negative: champion stayed `v1`, promotions
  `0`, pair results were 10 wins, 14 losses, and 8 ties, median delta `0.0`,
  rows at or above CVRP MDE `0`, CI high below MDE `1`, and max effect/MDE
  `-0.10101`. Case-level signal was mixed: CMT4 was positive/tie, CMT2 was
  0/4 losses. Current interpretation: the framework now supports a materially
  different successor attempt, but this bounded local-search successor did not
  produce solver improvement. The current local repair adds a CVRP-owned
  `cvrp_successor_summary` and `cvrp_opportunity_usage_summary.v2`: live brief
  recomputation on this root recognizes `bounded_local_search_variant` direct
  successor evidence as checklist `proven`, outcome
  `measured_no_positive_at_mde`, with activation/objective/phase and CMT2/CMT4
  evidence observed. The root's stored opportunity-usage brief predates this
  schema and is expected to show an optional stale-signature warning under the
  new checker; `--require-current-run-ready` still has no failed required
  checks. Current interpretation: the remaining work is now to use this
  problem-owned successor evidence in the next CVRP/VRP design attempt, not to
  add another generic gate. The current CVRP-owned guidance now carries
  `bounded_2node_cross_exchange` as reviewed successor evidence and an exact
  default-avoid item, while leaving the broader
  `bounded_local_search_variant` successor family available for materially new
  causal paths. The next prepared CVRP attempt should therefore prefer
  `destroy_repair_selection` or another non-cross-exchange problem-owned
  mechanism unless a bounded-local-search revisit names a distinct causal path
  with direct per-case objective-effect telemetry.
- Local successor2 proposal-loop probe:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor2-eaa11f98-local-1r-gpt55-20260628T122607Z-claw`.
  Prepared launch readiness passed with completion preflight on commit
  `eaa11f98`; the manifest carried
  `reviewed_mechanism_ids=[large_instance_intra_route_two_opt_seed,
  bounded_2node_cross_exchange]`, `destroy_repair_selection` as a successor
  family, and an exact `bounded_2node_cross_exchange` default-avoid item. The
  run failed before Protocol rows (`wrapper_exit_status=64`,
  `stopped_reason=circuit_breaker`, `proposal_quality_blocks=3`) after three
  target-intent binding mismatches. The useful diagnosis is proposal-layer:
  default-avoid broad matching rejected route-named destroy/repair targets on
  generic one-token overlap, and the binding gate then treated those rejected
  target intents as still binding for formal hypotheses. The local repair now
  keeps rejected target intents from acting as binding sources and narrows
  single-token `variants` matches to specific tokens.
- Repaired local successor2 verification:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor2-19811b02-local-1r-gpt55-20260628T123904Z-claw`.
  It finished valid/complete and postrun-ready from commit `19811b02`, with
  one proposal attempt, zero quality blocks, one effective Protocol screening
  row, `current_run_analysis_ready=true`, `delegation_ready=true`, and no
  readiness failures after postrun rebuild. This accepts the proposal-loop
  repair: the run reached formal screening rather than circuit-breaking on a
  rejected target intent. The selected mechanism was
  `intra_route_or_opt_reinsert`, a distinct bounded-local-search path from the
  reviewed large-twoopt seed and `bounded_2node_cross_exchange`. The solver
  result is negative: win-rate `0.25`, median delta `-0.75`, CI high `7.5`
  below CVRP MDE, CMT2/CMT4 both `1` win and `3` losses, champion stayed `v1`,
  and promotions `0`. CVRP-owned `cvrp_successor_summary` now maps this exact
  mechanism id to `bounded_local_search_variant`, marks the checklist
  `proven`, records outcome `measured_no_positive_at_mde`, and leaves no
  successor evidence gaps. Prepared guidance now lists the exact mechanism id
  as reviewed/default-avoid without blocking the whole bounded-local-search
  family.
- Clean local successor3 construction-seed verification:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor3-b430c646-local-1r-gpt55-20260628T133031Z-claw`.
  It resumed successor2 from commit `b430c646`, finished valid/complete and
  postrun-ready, and rechecks with `current_run_analysis_ready=true`,
  `delegation_ready=true`, and no failed postrun checks after rebuild. The
  agent selected a materially different construction successor,
  `rotated_sweep_seed_tournament` in `construction.py`, with 1 proposal
  attempt, 0 quality blocks, 1 effective screening row, and 32 of 32 valid
  screening pairs. It is not solver progress: champion stayed `v1`,
  promotions `0`, rows at or above CVRP MDE `0`, top effect row
  `win_rate=0.0`, `median_delta=0.0`, `ci_high=0.0`, and
  `positive_effect_at_or_above_mde=false`. The branch was abandoned for
  `SCREENING_TELEMETRY_FAILED`: ordinary construction phase runtime was
  observed, but activation under the declared mechanism id was missing. The
  current CVRP-owned review repair makes construction a first-class successor
  family: live brief recomputation maps `rotated_sweep_seed_tournament` to
  `construction_seed_portfolio`, records checklist `unproven`, outcome
  `measured_no_positive_at_mde`, missing `missing_activation_observed`, and
  maps opportunity usage to `construction_seed_portfolio` instead of
  `no_structured_match`. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-construction-successor-review-20260628.md`.
- Clean local successor4 destroy/repair verification:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor4-6a50fcba-local-2r-gpt55-20260628T142639Z-claw-2r-gpt55-20260628T142639Z-claw`.
  It resumed successor3 from commit `6a50fcba`, finished valid/complete and
  postrun-ready, and rechecks with `current_run_analysis_ready=true`,
  `delegation_ready=true`, and no failed postrun checks after rebuild. The
  agent selected the preferred successor family,
  `angular_sector_removal` in `destroy_repair.py`, with 2 proposal attempts,
  0 quality blocks, 0 active-slot blocks, 2 formal candidate artifacts, and
  2 effective screening rows. It is not solver progress: champion stayed `v1`,
  promotions `0`, rows at or above CVRP MDE `0`, both effect rows had win rate
  `0.25`, median deltas `-3.25` and `0.0`, and both CI highs were below MDE.
  It is evidence-clean rejection: `cvrp_successor_summary` marks
  `destroy_repair_selection` checklist `proven`, outcome
  `measured_no_positive_at_mde`, and observes activation, objective effect,
  phase telemetry, and CMT2/CMT4 protected-case evidence. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-destroy-repair-successor-review-20260628.md`.
- Warehouse has positive movement evidence from earlier v2-to-v3 work. The
  fresh positive-control run from synchronized status/runtime commit `2f8e9f21`
  finished valid/complete and postrun-ready:
  `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-positive-2f8e9f21-current-8r-gpt55-20260623T161630Z-claw`.
  The local mirror is
  `/home/clawd/research/scion-experiments/v04-wh-v2-positive-2f8e9f21-current-8r-gpt55-20260623T161630Z-claw`.
  Strict launch readiness passed before launch, including runtime commit match,
  clean runtime guard paths, complete prepared contract, warehouse v2 follow-up
  handoff, prepared prompt-context readiness, and healthy `gpt-5.5` completion
  preflight. Run counters: 8 of 8 effective Protocol rows, 10 screening metric
  rows, 6 proposal quality blocks, 0 active-slot blocks, wrapper/postrun exit
  `0`, and no postrun readiness failures. It did not produce a new champion:
  starting/current champion version is `2`/`2`, champion version gain is `0`,
  and every protocol-effect row is below MDE. Postrun interpretation is
  `protocol_evaluated_plateau_review_ready`, with no evidence gaps and no
  research-context actionability gaps. Research behavior is nevertheless
  effective: max branch depth is 8, all 11 observed same-mechanism follow-up
  opportunities were selected, and the active shape is `deep_focused`. Detailed
  plateau postrun report:
  `scion/docs/experiments/v0.4/v04-warehouse-v2-positive-plateau-postrun-20260623.md`.
- The old live CVRP solver-depth follow-up root
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-solverdepth-mechfollowup-readyfix-6r-gpt55-20260623T115013Z-claw`
  has finished and was mirrored locally to
  `/home/clawd/research/scion-experiments/v04-cvrp-solverdepth-mechfollowup-readyfix-6r-gpt55-20260623T115013Z-claw`.
  WSL postrun acceptance is ready and current-run analysis ready: 6 of 6
  effective Protocol rows, 0 proposal quality blocks, 0 active-slot blocks, max
  branch depth 4, and 4 of 4 observed same-mechanism follow-up opportunities
  selected. It is solver-negative and caveated: champion stayed `v1`, there
  were 0 promotions, all rows were below MDE, direct large-two-opt signal was
  missing, and launch/readiness reports the checkout changed while the process
  was live. Use it as live-run research evidence only, not as clean acceptance
  for Designs L/M.
- The warehouse plateau postrun analysis is complete. Treat the clean v2
  positive-control root as restored warehouse effective-research evidence and
  plateau-review readiness for v0.4 framework purposes, not as continuous
  promotion and not as a universal warehouse plateau proof. Do not launch
  another warehouse run by default; one narrow repeat is optional only if an
  independent solver-level plateau confirmation is needed. The main next
  operational action is design-first CVRP/VRP solver-opportunity work.
- The clean CVRP current-sync follow-up finished and was mirrored locally:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-current-sync-d3efc3cb-postsolverdepth-6r-gpt55-20260623T182433Z-claw`.
  It resumed the old solver-depth campaign from clean WSL commit `d3efc3cb`,
  passed strict launch readiness and `gpt-5.5` completion preflight, and
  finished wrapper/postrun-ready with validity `valid`, completeness
  `complete`, and `last_stop_reason=max_rounds_exhausted`. The local mirror is
  `/home/clawd/research/scion-experiments/v04-cvrp-current-sync-d3efc3cb-postsolverdepth-6r-gpt55-20260623T182433Z-claw`.
  Counters: 6 of 6 effective-budget rounds, 7 completed Protocol metric rows,
  7 screening rows, 8 proposal attempts, 2 proposal quality blocks, 0
  active-slot blocks, and no validation/frozen rows. This is clean framework
  research evidence, not solver progress: champion stayed `v1`, promotions
  were `0`, all 7 rows were below CVRP MDE `9.9`, rows at or above MDE were
  `0`, direct large-twoopt evidence was not ready, and the postrun
  interpretation is `protocol_evaluated_without_large_twoopt_signal`.
  Framework behavior is nevertheless materially improved: max branch depth is
  5, same-mechanism follow-up is 8/8, research-context actionability gaps are
  empty, prompt/source visibility has no missing required target-source
  evidence, and runtime budget saturation remained observational under
  `budget_exhausting`. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-current-sync-large-twoopt-postrun-20260624.md`.
  Accepted conclusion: current-sync CVRP validates the repaired research loop
  for continuation/rejection, while leaving the solver-opportunity problem
  open in the CVRP/VRP problem-owned layer.
- The CVRP opportunity-recipe continuation finished valid/complete and was
  mirrored locally:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-opportunity-recipe-resume-633d1d25-4r-gpt55-20260625T110617Z-claw`.
  Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-opportunity-recipe-resume-633d1d25-4r-gpt55-20260625T110617Z-claw`.
  It launched from clean WSL commit `633d1d25`, resumed the current-sync CVRP
  root, and WSL postrun acceptance is authoritative and ready:
  `current_run_analysis_ready=true`, `delegation_ready=true`, no required
  readiness failures, optional `postrun_report_status_marker` only. Counters:
  4 of 4 effective rounds, 4 screening Protocol rows, 4 proposal attempts, 0
  proposal quality blocks, champion still `v1`, promotions `0`. Measurement
  remains solver-negative: 0 positive rows, 0 rows at or above MDE, all 4 rows
  with CI high below MDE, max effect-to-MDE ratio `0.0`, and CVRP review
  interpretation `protocol_evaluated_without_large_twoopt_signal`. The useful
  evidence is Design P proposal visibility and opportunity usage: `Problem
  Opportunity Summary` was visible in hypothesis prompts, CVRP opportunity
  usage is `mixed`, with `used_opportunity=4`, `contrasted_opportunity=56`,
  and only `proposal_repeats_default_avoid_family` as evidence gap. This root
  launched before Designs Q/R, so code prompts are not expected to include
  `Opportunity Evidence Commitment`. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-opportunity-recipe-postrun-20260625.md`.
- The fresh no-resume CVRP Design Q/R root finished valid/complete and
  postrun-ready:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-designqr-codeprompt-fresh-23f24bca-data-2r-gpt55-20260625T140430Z-claw`.
  Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-designqr-codeprompt-fresh-23f24bca-data-2r-gpt55-20260625T140430Z-claw`.
  It launched from isolated WSL worktree commit `23f24bca` after strict
  readiness and `gpt-5.5` completion preflight. WSL postrun acceptance is
  authoritative and ready: `current_run_analysis_ready=true`,
  `delegation_ready=true`, no required readiness failures, optional
  `postrun_report_status_marker` only. This root validates Designs Q/R on a
  clean no-resume launch: one code prompt rendered
  `Opportunity Evidence Commitment`, the manifest-safe commitment digest was
  `a70515cce42ea190`, selected mechanism id was
  `large_instance_intra_route_two_opt_seed`, requirement ids were
  `large_instance_two_opt_objective_runtime_requirement` and
  `cmt2_cmt4_case_protection`, and postrun visibility reported
  `code_section_visible_trace_count=1` with both summary-without-section counts
  `0`. It is not solver progress: 2 of 2 effective rounds, 2 screening
  Protocol rows, 0 proposal quality blocks, 0 active-slot blocks, max branch
  depth 2, same-mechanism follow-up 1/1, champion still `v1`, promotions `0`,
  positive rows `0`, rows at or above MDE `0`, and CVRP review interpretation
  `protocol_evaluated_without_large_twoopt_signal`. The useful next problem
  signal is `cvrp_opportunity_usage_summary.usage_status=checklist_unproven`:
  both structured proposal fingerprints selected the prepared opportunity but
  did not prove the required objective/runtime plus CMT2/CMT4 evidence
  checklist. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-designqr-codeprompt-postrun-20260625.md`.

## WSL Runner

- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- WSL Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- WSL experiment root: `/home/xjy-ubuntu/research/scion-experiments`
- Server-side SSH probe to re-run before using WSL:
  `ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no xjy-ubuntu@127.0.0.1 'echo SSH_OK; hostname; whoami; /home/xjy-ubuntu/miniconda3/envs/scion/bin/python --version'`
- Current execution uses the server conda `claw` environment. Treat WSL as
  unavailable until the probe above succeeds after the local WSL runner is
  brought back up.

Before launching any prepared root, require strict launch readiness from the
same WSL checkout:

```bash
PY=/home/xjy-ubuntu/miniconda3/envs/scion/bin/python
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  "$PY" /home/xjy-ubuntu/research/or-autoresearch-agent/scion/tools/check_launch_readiness.py \
  <prepared-root> --require-launch-ready --format json
```

After a run, inspect `exit.txt`, `run_status.json`, and
`postrun_acceptance/readiness/` on WSL, then mirror the WSL root back to the
server. For WSL-origin roots, WSL postrun acceptance is authoritative; the
local mirror keeps WSL absolute paths in postrun artifacts, so use
`--skip-postrun-check` during mirror-only sync:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  python scripts/sync_wsl_run_root.py <wsl-run-root> \
  --execute --skip-postrun-check --format json
```

## Preserved Guarantees

- No CVRP/VRP/warehouse-specific scheduler, target-intent, launcher-lifecycle,
  mechanism-evidence, or runtime-pressure exceptions are accepted in generic
  core.
- Raw calibration rows, BKS data, case-level problem facts, free-form proposal
  prose, and runtime feedback text remain excluded from `DecisionFeatures`.
- Runtime regressions still fail closed when they are actionable comparative
  evidence or hard execution failures. Design L/M only make budget-exhausting
  aggregate slowdown semantics observational.
- Candidate crashes, invalid outputs, telemetry guard failures, and verification
  failures remain fail-closed.
- Problem-owned measurement declarations define runtime model, effect scale,
  pairing validity, and readiness diagnostics; generic core consumes normalized
  semantics.
- Status docs should be replaced with current facts rather than appended with
  root chronology.

## Problem Frontiers

- Warehouse: the current clean v2 follow-up is plateau-review-ready rather than
  a new promotion. The plateau postrun report accepts restored effective
  research and current plateau-review readiness for v0.4; a narrow repeat is
  optional only for independent solver-level plateau confirmation.
- CVRP: use A/A MDE and case variance while seeking branch depth,
  same-mechanism follow-up, and solver-design improvements. The current-sync,
  opportunity-recipe, Q/R, CMT-commitment, and postprojection roots are clean
  evidence for repaired continuation, MDE-aware rejection, opportunity
  visibility, code-phase commitment visibility, and required-evidence
  follow-through. They are not solver-improvement evidence. The
  large-instance intra-route two-opt seed is reviewed after checklist proof
  with no positive-at-MDE effect; earlier bounded-local-search successors are
  reviewed negative, the ejection-chain bounded-local-search successor is
  reviewed marginal/no-positive-at-MDE, and the first activation-only
  construction-seed successor is reviewed checklist-unproven. Successor8 closes
  the narrower
  construction evidence-chain gap for `savings_seed_selection_probe`: direct
  objective-effect telemetry is now observed under the declared mechanism id,
  and the construction checklist is proven after postrun rebuild, but the
  solver outcome is still no-positive-at-MDE. Successor10 and successor11 show
  the framework can now execute new destroy/repair research paths end-to-end,
  but `polar_sweep_destroy_repair`, `route_fragment_recombination_repair`,
  `adjacency_pair_removal_repair`, and `load_compatible_ruin_recreate` are also
  reviewed no-positive-at-MDE. Successor12 is valid/postrun-ready but
  partially tainted by the reviewed-`EXPLORE_EXPAND` scheduler gap above: its
  first row repeated `load_compatible_ruin_recreate` and should be treated as
  repair evidence, not a new successor choice. Its clean-forked second row,
  `capacity_tightness_removal`, is useful weak-positive CVRP evidence rather
  than promotion evidence: 32/32 valid pairs, W/L/T `17/10/5`, median delta
  `2.0`, effect/MDE `0.202`, CI high `5.5 < 9.9` MDE, CMT2 median `4.0`, CMT4
  median `-13.0`, branch state `explore_expand` with marginal evidence.
  Successor13 then verified the prepared successor-focus repair on commit
  `46b01ebb`: the first row followed `capacity_tightness_removal` instead of
  the reviewed `load_compatible_ruin_recreate` repeat, bad code was blocked
  before Protocol, and postrun acceptance stayed current-run ready. Solver
  evidence remained no-positive-at-MDE: `capacity_tightness_removal` screened
  `48/48` W/L/T `27/19/2`, median delta `2.0`; two
  `route_pair_crossover_repair` rows screened `32/32` each with W/L/T
  `13/12/7` and `13/13/6`, both median delta `0.0`; champion stayed `v1`.
  The clean route-pair branch is active marginal `explore_expand` evidence,
  but any continuation must directly address CMT2/CMT4/X-n110 losses and
  runtime cost or switch to a materially different problem-owned mechanism.
  The report-layer bug exposed by this run is fixed: research-efficiency now
  resolves row-level `mechanism_family` from direct primary-mechanism evidence
  before branch-level family summaries, so the capacity row is no longer
  mislabeled as route-pair after postrun rebuild.
  Successor14 from commit `9fed32ad` then completed 2 effective rounds with 2
  formal screening rows, 0 quality blocks, and strict postrun acceptance ready
  after a generic launcher-marker readiness repair. Solver evidence remained
  no-positive-at-MDE: the active `route_pair_crossover_repair` follow-up
  screened 48/48 pairs with raw W/L/T `19/24/5`, raw pair median `-0.5`,
  research-efficiency median `-3.5`, CI high `6.5 < 9.9`, and persistent
  CMT2/CMT4/X-n110 losses; the branch was parked as quality regression. The
  clean fork `timewarp_string_removal` screened 32/32 pairs with raw W/L/T
  `9/15/8`, raw pair median `0.0`, research-efficiency median `-5.25`, CI high
  `0.0 < 9.9`, and was abandoned/discarded as loss-heavy evidence. This is
  effective-research/closed-loop evidence, not solver-improvement evidence.
  The local CVRP guidance repair now records both successor14 mechanisms in a
  problem-owned `successor_evidence_catalog` as reviewed/default-avoid evidence
  before successor15 preparation, while keeping generic core and
  `DecisionFeatures` free of CVRP mechanism semantics.
  Successor15 from commit `dc0603c6` then completed 2 effective rounds with 2
  formal screening rows, 0 quality blocks, champion still `v1`, and strict
  postrun acceptance ready. It did not repeat unchanged route-pair or timewarp
  paths. The first clean fork, `load_complement_pair_removal`, screened 32/32
  pairs, W/L/T `10/17/5`, median delta `-4.75`, CI `[-8.75, 0.0]`, with CMT4
  `-15.0` and X-n110 `-6.0`; it was abandoned as loss-heavy evidence and is
  now problem-owned reviewed/default-avoid. The second row,
  `granular_savings_seed_portfolio`, screened 32/32 pairs, W/L/T `17/8/7`,
  median delta `3.5`, CI `[0.0, 12.75]`, and effect/MDE `0.354`, with no rows
  at or above MDE. It is active weak-positive construction evidence rather
  than promotion or reviewed/default-avoid evidence: A-n64, CMT2, CMT4, and
  M-n200 were positive; E/P were mixed; X-n110 has a one-loss caveat.
  Successor16 from commit `78bf620c` followed that branch first and finished
  valid/complete with strict postrun readiness clean. The expanded
  `granular_savings_seed_portfolio` row reached 48/48 valid pairs with
  activation/effect evidence and marginal positive but below-MDE signal: pair
  W/L/T `32/13/3`, case W/L/T `7/1/4`, median delta `4.5`, CI
  `[-0.5, 12.75]`, effect/MDE `0.455`, rows at or above MDE `0`. It remains
  the retained marginal construction checkpoint, not promotion or
  reviewed/default-avoid evidence. The second screened construction follow-up,
  `seed_post_optimization_selector`, reached 32/32 valid pairs but was
  inactive/missing activation: case W/L/T `0/0/8`, median delta `0.0`, and the
  declared primary mechanism was not observed. Two pre-protocol attempts were
  correctly blocked by proposal quality diagnostics.
  Successor17 from commit `dcf08884` then finished valid/complete with strict
  postrun readiness clean. It showed one remaining prepared-run scheduling gap:
  the resumed `seed_post_optimization_selector` diagnostic branch consumed the
  first Protocol row even though successor16 had already shown missing
  activation. The row again had missing primary activation (`48/48`, pair W/L/T
  `2/2/44`, case W/L/T `0/0/12`, median delta `0.0`). The material
  `granular_savings_seed_portfolio` follow-up activated and remained
  weak-positive but below MDE (`32/32`, pair W/L/T `16/8/8`, case W/L/T
  `4/2/2`, median delta `3.0`, CI `[-0.5, 12.75]`, effect/MDE `0.303`), with
  E/P regressions and B/X ties. The local repair is generic:
  prepared research focus now carries problem-provided
  `suppressed_mechanism_ids` alongside `reviewed_mechanism_ids`; scheduler,
  target-intent, formal-hypothesis, and schema-preview paths exclude those ids
  for the prepared run while keeping the problem reason out of
  `DecisionFeatures`. CVRP uses this for unchanged
  `seed_post_optimization_selector`; it is not reviewed no-positive evidence.
- Runtime semantics: keep budget-exhausting runtime ratios observational while
  preserving comparative runtime evidence as a valid pressure and failure
  signal.

## Next Actions

1. Continue CVRP/VRP successor work using the problem-owned successor review
   layer. The reviewed `large_instance_intra_route_two_opt_seed` path,
   `bounded_2node_cross_exchange`, and `intra_route_or_opt_reinsert` are all
   solver-negative under current evidence. The construction successor
   `rotated_sweep_seed_tournament` reached formal screening but failed the
   direct activation checklist, while `savings_seed_selection_probe` now proves
   direct construction-seed evidence but remains no-positive-at-MDE.
   `bounded_ejection_chain_relocate` is now reviewed bounded-local-search
   no-positive-at-MDE evidence with CMT2/CMT4 losses. `angular_sector_removal`,
   `radial_string_removal`, `farthest_noise_related_removal`,
   `polar_sweep_destroy_repair`, `route_fragment_recombination_repair`,
   `adjacency_pair_removal_repair`, `load_compatible_ruin_recreate`, and
   `load_complement_pair_removal` are all reviewed destroy/repair
   no-positive-at-MDE evidence, and
   `bounded_intra_route_3opt` is reviewed bounded-local-search no-positive
   evidence after successor6 expanded and rejected it. Prepared CVRP guidance
   now exposes these as exact reviewed/default-avoid mechanisms. Successor13
   confirms the generic prepared-successor scheduler repair, and successor14
   confirms Scion can park the route-pair quality-regression branch and
   clean-fork to a distinct destroy/repair mechanism, but neither run provides
   solver improvement evidence. Local problem-owned guidance now also treats
   `route_pair_crossover_repair` and `timewarp_string_removal` as
   reviewed/default-avoid successor evidence. Successor15 adds
   `load_complement_pair_removal` to that reviewed/default-avoid set.
   Successor16/17 confirm that Scion can follow the active granular
   construction branch, but the result is marginal below-MDE rather than solver
   closure. Successor17 also upgrades unchanged
   `seed_post_optimization_selector` from a prompt caveat to a prepared-run
   suppressed mechanism after repeated missing activation. The next CVRP
   attempt should make a stronger material
   `granular_savings_seed_portfolio` variant that directly addresses E/P/X
   variability and the MDE gap, explicitly repair
   `seed_post_optimization_selector` activation with pre-protocol and formal
   mechanism evidence, or name a materially different non-reviewed CVRP-owned
   mechanism. It should not
   repeat unchanged route-pair, timewarp-string removal, load-complement pair
   removal, seed-post selector, 3-opt, radial-string, farthest-noise,
   angular-sector, polar-sweep, route-fragment recombination, adjacency-pair
   removal, load-compatible ruin/recreate, cross-exchange, Or-opt, large
   two-opt seed, savings seed-selection, or ejection-chain relocation paths
   unless the hypothesis names a distinct causal path and direct
   objective-effect evidence plan. Use
   the corrected row-local `mechanism_family` summary, direct
   `mechanism_evidence.primary_mechanism`, and phase telemetry as the current
   source of truth for successor review. Explicitly close/reframe the
   remaining `large_instance_intra_route_two_opt_seed` diagnostic branch before
   spending more active-slot budget there.
2. Continue design-first postrun/readiness cleanup only where it removes active
   risk. `scion.postrun` should own generic artifact, lifecycle, schema,
   readiness, and exposure boundaries; CVRP/warehouse/VRP semantics should sit
   in problem-owned validators/providers. Do not add more behavior to oversized
   postrun scripts when a typed port or cohesive report module is appropriate.
3. Extend problem-owned opportunity providers/reviews beyond the CVRP initial
   slice only when a concrete problem package needs it. Generic core should
   continue to render/audit `ProblemOpportunitySummary`; residual opportunity,
   protected cases, mechanism evidence, direct-effect requirements, and MDE
   comparison stay in problem-owned providers and out of `DecisionFeatures`.
4. Keep warehouse as positive effective-research evidence. Launch one narrow
   warehouse repeat only if an independent solver-level plateau confirmation is
   explicitly needed.
5. Keep evaluating v0.4 against effective research behavior: warehouse plateau
   evidence, CVRP branch depth and solver-design follow-up, MDE-aware
   rejection, and absence of framework-control blockers.

## Pointers

- Architecture: `scion/design/scion-architecture-v3.md`
- Repair design: `scion/design/v0.4-effective-research-repair-design.md`
- Next port design:
  `scion/design/v0.4-postrun-readiness-and-opportunity-ports.md`
- Postrun checker repair:
  `scion/docs/experiments/v0.4/v04-postrun-acceptance-stored-inventory-recheck-20260623.md`
- CVRP current-sync postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-current-sync-large-twoopt-postrun-20260624.md`
- CVRP postprojection successor portfolio:
  `scion/docs/experiments/v0.4/v04-cvrp-postprojection-successor-portfolio-20260628.md`
- CVRP successor13 postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor13-postrun-20260629.md`
- CVRP successor14 postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor14-postrun-20260629.md`
- CVRP successor16 postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor16-postrun-20260629.md`
- CVRP successor17 postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor17-postrun-20260629.md`
- Task source: `scion/TASK.md`
- Audit basis:
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`
