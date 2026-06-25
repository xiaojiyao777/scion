# Scion v0.4 Current State

Last updated: 2026-06-25

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
- The WSL reverse SSH tunnel is restored. The current local repair files were
  synced to the WSL runner worktree, and WSL conda `scion` focused validation
  passes (`108 passed`). Local and WSL sync commits have been recorded in git;
  use each checkout's `git rev-parse --short HEAD` as the current sync point.
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
- The current WSL reverse SSH channel is available. A server-side probe on
  2026-06-24 returned `SSH_OK`, host `xjy-workspace`, user `xjy-ubuntu`, and
  WSL conda `scion` Python `3.10.20`.
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
  (`85 passed` each) in both environments.
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
  This is report-only, excludes raw prompt/response/patch bodies, and does not
  alter `DecisionFeatures`, Protocol, scheduler, lifecycle, runtime-pressure,
  or promotion behavior. Focused local tests pass (`17 passed`).

## Current Decision

- v0.4 is not closed. The remaining acceptance question is effective research
  behavior, not more broad framework churn.
- CVRP has accepted framework evidence for active-slot scheduling,
  weak-positive follow-up, target-intent authority, mechanism-evidence
  follow-up, MDE-aware rejection, prompt/source visibility, and
  budget-exhausting runtime semantics. It still lacks solver improvement or
  promotion.
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
- Active WSL CVRP opportunity-recipe run:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-opportunity-recipe-resume-633d1d25-4r-gpt55-20260625T110617Z-claw`.
  It launched from clean WSL commit `633d1d25` and resumed the current-sync
  CVRP root. As of the 2026-06-25T11:56Z server-side check it was still
  running with 1 of 4 effective rounds complete, 1 Protocol row, 0 proposal
  quality blocks, and champion still `v1`. New live prompt traces prove the
  hypothesis prompt includes `Problem Opportunity Summary` and the prepared
  `large_instance_two_opt_objective_runtime_requirement` recipe. The code
  prompt from that run does not include Design Q's code-phase commitment
  because the run started before Design Q. Do not hot-sync the WSL checkout
  while this run is active unless accepting checkout-changed caveats.

## WSL Runner

- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- WSL Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- WSL experiment root: `/home/xjy-ubuntu/research/scion-experiments`
- Current server-side SSH probe:
  `ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no xjy-ubuntu@127.0.0.1 'echo SSH_OK; hostname; whoami; /home/xjy-ubuntu/miniconda3/envs/scion/bin/python --version'`
- Current probe result: `SSH_OK`, host `xjy-workspace`, user `xjy-ubuntu`,
  Python `3.10.20`.

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
  same-mechanism follow-up, and solver-design improvements. The current-sync
  root above is now clean acceptance evidence for repaired continuation and
  MDE-aware rejection, but not for solver improvement. The next CVRP/VRP work
  should improve problem-owned solver-opportunity evidence and proposal context,
  not add CVRP-specific core gates.
- Runtime semantics: keep budget-exhausting runtime ratios observational while
  preserving comparative runtime evidence as a valid pressure and failure
  signal.

## Next Actions

1. Design the next repair as ports, not more helper/projection patches:
   generic core should own artifact identity, current-run evidence,
   fail-closed lifecycle/readiness status, schema validation, and exposure
   boundaries; CVRP/warehouse/VRP review semantics should sit in problem-owned
   validators/providers. Design basis:
   `scion/design/v0.4-postrun-readiness-and-opportunity-ports.md`. Design N
   skeleton and the `check_postrun_acceptance.py` compatibility adapter are
   implemented, CVRP large-twoopt plus warehouse follow-up reviews are now
   problem-owned, and generic lifecycle/marker acceptance checks are behind
   `PostrunLifecycleAcceptancePort` while artifact identity/schema checks are
   behind `PostrunArtifactAcceptancePort`; evidence/brief consistency checks
   are behind `PostrunEvidenceConsistencyAcceptancePort`; review-input summary
   validation is behind `PostrunReviewInputAcceptancePort`; prompt/source
   visibility envelope checks are behind `PostrunPromptVisibilityAcceptancePort`;
   research-telemetry checks are behind
   `PostrunResearchTelemetryAcceptancePort`. All six preserve legacy check
   payloads.
   Problem-summary actionability policy is now defined by
   `ProblemSummaryActionabilitySpec` in each problem package, with the checker
   retaining only compatibility dispatch.
   Design O's typed measurement consumer feeds protocol config,
   proposal-context measurement diagnostics, prepared measurement handoff
   builders, and postrun research-efficiency fallback. Designs Q/R now make
   selected opportunity commitments visible to code prompts and auditable in
   postrun reports as ids/digests only. The next v0.4 work is effective-
   research validation and problem-owned opportunity/review evidence, not more
   generic checker growth.
2. Extend problem-owned opportunity providers/reviews beyond the CVRP initial
   slice only when a concrete problem package needs it. Generic core should
   continue to render/audit `ProblemOpportunitySummary`; residual opportunity,
   protected cases, mechanism evidence, direct-effect requirements, and MDE
   comparison stay in problem-owned providers and out of `DecisionFeatures`.
3. Keep warehouse as positive effective-research evidence. Launch one narrow
   warehouse repeat only if an independent solver-level plateau confirmation is
   explicitly needed.
4. Keep evaluating v0.4 against effective research behavior: warehouse plateau
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
- Task source: `scion/TASK.md`
- Audit basis:
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`
