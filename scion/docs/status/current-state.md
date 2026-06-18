# Scion v0.4 Current State

Last updated: 2026-06-18

This file is the short operational resume point. Replace stale conclusions here
instead of appending event history. Detailed run evidence belongs in
`scion/docs/experiments/v0.4/`; `scion/docs/status/v0.4-history.md` is only a
curated milestone index.

## Operating Frame

- Active branch: `codex/v04-evidence-repair-plan`.
- Boundary authority: `scion/design/scion-architecture-v3.md`.
- v0.4 closeout goal: make Scion stable enough that warehouse can recover
  continuous useful research and CVRP/VRP can produce evidence-backed solver
  hypotheses before v0.5 broad experiment matrices.
- Current posture: do not add broad budgets, truncation, compression, or generic
  gate tightening. Keep CVRP/warehouse semantics in problem-owned layers and
  keep generic `DecisionFeatures` problem-neutral.

## Current Truth

Framework:

- Campaign continuation and observability are repaired enough for focused
  follow-up. Copied campaigns restore champion, active branch, workspace,
  hypothesis, candidate patch, branch evidence, compact status/progress, reduced
  measurement readiness, and research-efficiency projections.
- Research-efficiency reports now include report-only `research_continuity`
  metrics for same-mechanism follow-up selection, branch-lesson satisfaction and
  semantic gaps, weak-positive transfer acceptance, lesson actions, and branch
  shape. These are postrun audit fields only; they do not feed Decision,
  Protocol gates, scheduling, lifecycle, promotion, or proposal context.
  Postrun artifact inventories now also mark `research_continuity` as an
  explicit Phase 4 evidence-coverage requirement, and postrun analysis briefs
  summarize the current-run continuity metrics for delegated review. Postrun
  analysis briefs also summarize current-run branch/event/hypothesis state,
  protocol/formal-candidate accounting, measurement effect-vs-MDE, prompt
  context/source visibility, code/hypothesis source-visibility guarantees,
  prompt signal density, runtime feedback/drain behavior, and failure
  taxonomy/proposal quality without exposing raw prompts, responses, patches,
  raw logs, source bodies, or mutating runtime semantics. Postrun artifact
  inventories now distinguish broad source-visibility fingerprints from
  code-phase source-visibility guarantee evidence, so delegated review can see
  whether code-stage source visibility was actually evidenced. They also
  separate research-continuity coverage into same-mechanism follow-up,
  branch-lesson usage, weak-positive transfer, and branch research shape, so
  Phase 4 effective-research signals are individually auditable. Protocol row,
  candidate, and validation/frozen stage accounting are also explicit Phase 4
  coverage items.
- These accepted repairs are continuation/reporting/launcher repairs. They do
  not change Decision, `DecisionFeatures`, scheduling, budgets, lifecycle
  policy, or problem semantics.
- Runtime semantics for budget-exhausting solvers are repaired in the narrow
  v0.4 sense: high aggregate `runtime_regression_rate` no longer blocks
  low-SNR trajectory-divergent screening expansion, drives lifecycle
  soft-abandon/repeated-signal noise, assigns a proposal feedback
  `runtime_regression` tier, vetoes low-signal `retain_head` workspace
  preservation, or creates strong prompt actionability when the problem declares
  `runtime_model=budget_exhausting`.
- Low-signal same-branch observation samples now stay scheduler-visible as
  `refine_active` work rather than `repair_diagnostic`, so a retained
  no-effect branch selected for one same-mechanism sample is not misreported to
  downstream status/lineage surfaces as repair work.
- Current active no-effect branch-local lessons now become advisory
  `same_branch_refinement` proposal requirements, so the next same-mechanism
  hypothesis must contrast the prior no-effect evidence instead of merely being
  allowed to continue.
- Trajectory-divergent screening now treats all-tie, non-regressive evidence as
  low-SNR expand/continue evidence rather than a win-rate failure. Negative
  delta, loss-heavy evidence, candidate failures, and runtime vetoes still fail
  closed.
- Measurement integration is covered against real CVRP formal and warehouse
  production assets: problem-owned practical deltas, runtime model, pairing
  validity, and reduced readiness feed deterministic protocol config fields;
  raw calibration diagnostics stay outside `DecisionFeatures`; warehouse
  problem specs no longer hard-code local absolute surrogate paths.
- A/A calibration pair evidence now records explicit champion/candidate runtime
  budget-hit ratios and flags so budget saturation can be audited per replay.
- CVRP and warehouse launch helpers now support prepared follow-up roots with
  top-level `prepared` status, completion preflight, secret-safe API-key env
  wiring, runtime-source guards, campaign copy/resume, secret-free prepared-run
  manifests, prepare-time delegated handoff briefs/inventories,
  launch-readiness snapshots, and default postrun report generation. The
  launchers now auto-fill a deterministic report-only `control_pair_key` when
  the operator omits one, so prepare-only roots do not fail the prepared
  contract solely because optional metadata was blank. The
  generated briefs carry the prepared manifest's analysis intent, acceptance
  focus, current problem-owned research-focus/default-avoid handoff, CVRP
  measurement/opportunity diagnostics, and resume source; inventory/contract/
  readiness checks remain report-only and outside `DecisionFeatures`.
  For CVRP, the prepared contract now requires those measurement/opportunity
  diagnostics before static launch readiness can pass, plus default-avoid
  coverage, direct-effect route-merge/construction-seed rules, and a
  decision-boundary note; artifact inventories and analysis briefs expose these
  as CVRP `problem_specific_requirements`.
  For warehouse, the prepared contract now requires a problem-specific v2
  follow-up handoff covering plateau-vs-continuous-improvement framing,
  promotion preservation, branch transfer, quality-blocked-vs-protocol-evaluated
  distinction, cost-vs-split telemetry, and fast-completion runtime explanation;
  artifact inventories and analysis briefs expose these as
  `problem_specific_requirements`.
  Prepared-only roots now carry explicit launcher
  lifecycle/evidence-scope metadata, so copied resume snapshots are marked
  `prepared_only/not_started` with zero current-run effective rounds instead of
  masquerading as completed postrun evidence. Postrun inventory and analysis
  briefs now keep top-level branch/event/hypothesis/LLM-trace fields scoped to
  current-run evidence and report copied resume-campaign counts only under
  `resume_snapshot`.
- If a prepared root is started while completion preflight fails, launcher
  reports now mark the root `invalid_infra_only` with zero current-run evidence
  and skip current-run report families while preserving analysis brief,
  inventory, and rebuild manifest artifacts. The launcher also preserves
  `pre_campaign_completion_preflight.v1.json` plus structured status fields for
  failure classification, sanitized auth/account state, login-url presence, and
  operator action.
- `scion/tools/check_launch_readiness.py` is the current pre-launch verifier:
  static readiness covers prepared contracts, runtime guard consistency,
  `run.sh` syntax, report-family expectations, and unstarted root state; launch
  readiness is true only when the optional real completion preflight succeeds.
  Completion-preflight failures now carry an `operator_action` and, when the
  proxy exposes it, a login URL.
- Historical and current run roots can be normalized for delegated analysis with
  `scion/tools/rebuild_postrun_acceptance.py`. The rebuild manifest reports
  per-family success/failure and preserves Phase 4 evidence gaps instead of
  treating missing postrun artifacts as complete evidence. Current launcher
  postrun paths call this rebuild tool directly.

Warehouse:

- Warehouse has a v0.4 positive research-path checkpoint: champion `v2` promoted
  in the validation-transfer rerun, and the later cost-compression telemetry
  repair preserves real cost/improving-move effects without turning zero split
  delta into a false effect-zero diagnosis.
- The open warehouse question is continuous follow-on improvement, not basic
  viability.
- Prepared but not launched:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-317cacb-6r-gpt55-6r-gpt55-20260618T183318Z-claw`.

CVRP/VRP:

- CVRP can now steer target intent, carry branch lessons into prompts, generate
  material solver code, complete formal screening, preserve mechanism telemetry,
  and reject weak or negative hypotheses with evidence.
- CVRP still has not met v0.4 effective-research acceptance: no current
  solver-design branch has produced continuous improvement or promotion.
- Avoid repeating unchanged broad VNS removal, pure ALNS/no-polish, simple
  initial-VNS disablement, raw cadence-2, recent-best/stall gating, fixed
  early-8, tested share70 cap/rescue variants, route-merge absorption,
  demand-slack regret insertion, cross-route 2-opt reconnect, cluster-biased
  worst removal, or route-limit seed diversification.
- Construction seed/portfolio mechanisms need direct effect attribution from a
  same-run seed baseline or same-mechanism accepted delta. Fallback activation,
  seed-pool size, or merely selecting a seed is only activation/design evidence.
- CVRP proposal context now receives problem-owned measurement/opportunity
  diagnostics: MDE-vs-practical-delta, low-SNR interpretation, aggregate
  screening headroom, default-avoid mechanism directions, and measurable
  opportunity classes. These diagnostics are proposal-only and remain excluded
  from `DecisionFeatures`, Protocol gates, lifecycle, scheduler, and promotion.
- Prepared but not launched:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-317cacb-1r-gpt55-1r-gpt55-20260618T183304Z-claw`.

Infrastructure:

- No LLM campaign is currently running.
- The next focused campaigns are blocked by LLM infrastructure. The latest WSL
  `gpt-5.5` launch-readiness preflight reaches the proxy and reports
  no active authenticated account; the real chat completion returns HTTP `401`
  with `classification=not_authenticated`, and readiness includes
  `operator_action.login_url`. The auth pool may move between expired and
  refreshing states, but launch remains blocked until a real completion
  succeeds. The current `317cacb` prepared roots pass static readiness and
  remain unstarted.
  Do not launch prepared roots until `/v1/chat/completions` returns HTTP `200`
  with non-empty output after re-login/token refresh.
- WSL runs must use the synchronized WSL checkout and set
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`.

## Next Actions

1. Restore and verify the live `gpt-5.5` route with a real chat-completion
   preflight. `/v1/models` is not enough; on WSL run
   `scion/tools/check_launch_readiness.py <prepared-root>
   --completion-preflight --format json` and require `launch_ready=true`. If it
   fails, follow the reported `operator_action`; the readiness tool now requests
   a proxy login URL on failure.
2. Launch the prepared CVRP post-pivot follow-up from the clean WSL checkout,
   then inspect target-intent, hypothesis, branch lesson transfer, protocol
   effect-vs-MDE, budget-exhausting runtime feedback, source visibility, and
   postrun research-efficiency reports before accepting any conclusion.
3. Keep the prepared warehouse `v2` follow-up available as the simpler
   continuous-improvement check once LLM access is stable.
4. Keep status updates short: change this file only when the current operating
   truth or next action changes; put detailed evidence in experiment reports.

## Evidence Pointers

- Reset/audit basis:
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`, and
  `scion/design/scion-architecture-v3.md`.
- Current task and milestone summaries:
  `scion/TASK.md`, `scion/docs/status/v0.4-history.md`, and
  `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`.
- Detailed repair, launch, and postrun evidence:
  `scion/docs/experiments/v0.4/`. Current report-only observability slice:
  `scion/docs/experiments/v0.4/v04-research-continuity-report-metrics-repair-20260618.md`.
  Current prepared-root refresh:
  `scion/docs/experiments/v0.4/v04-prepared-root-runtime-guard-refresh-317cacb-20260618.md`.
  Current launcher-default repair:
  `scion/docs/experiments/v0.4/v04-launcher-control-pair-key-default-repair-20260618.md`.
  Current Phase 4 continuity coverage repair:
  `scion/docs/experiments/v0.4/v04-phase4-research-continuity-coverage-repair-20260618.md`.
  Current Phase 4 continuity subsignal coverage repair:
  `scion/docs/experiments/v0.4/v04-phase4-research-continuity-subsignal-coverage-repair-20260618.md`.
  Current Phase 4 protocol stage coverage repair:
  `scion/docs/experiments/v0.4/v04-phase4-protocol-stage-coverage-repair-20260618.md`.
  Current continuity brief repair:
  `scion/docs/experiments/v0.4/v04-postrun-research-continuity-brief-repair-20260618.md`.
  Current prompt context visibility brief repair:
  `scion/docs/experiments/v0.4/v04-postrun-prompt-context-visibility-brief-repair-20260618.md`.
  Current measurement effect brief repair:
  `scion/docs/experiments/v0.4/v04-postrun-measurement-effect-brief-repair-20260618.md`.
  Current runtime feedback brief repair:
  `scion/docs/experiments/v0.4/v04-postrun-runtime-feedback-brief-repair-20260618.md`.
  Current failure taxonomy brief repair:
  `scion/docs/experiments/v0.4/v04-postrun-failure-taxonomy-brief-repair-20260618.md`.
  Current protocol accounting brief repair:
  `scion/docs/experiments/v0.4/v04-postrun-protocol-accounting-brief-repair-20260618.md`.
  Current branch state brief repair:
  `scion/docs/experiments/v0.4/v04-postrun-branch-state-brief-repair-20260618.md`.
  Current source visibility brief repair:
  `scion/docs/experiments/v0.4/v04-postrun-source-visibility-brief-repair-20260618.md`.
  Current code source visibility coverage repair:
  `scion/docs/experiments/v0.4/v04-phase4-code-source-visibility-coverage-repair-20260618.md`.
  Current CVRP measurement/opportunity diagnostics repair:
  `scion/docs/experiments/v0.4/v04-cvrp-measurement-opportunity-diagnostics-repair-20260618.md`.
  Current CVRP prepared-handoff diagnostics repair:
  `scion/docs/experiments/v0.4/v04-cvrp-prepared-handoff-measurement-diagnostics-repair-20260618.md`.
  Current CVRP prepared-contract diagnostics repair:
  `scion/docs/experiments/v0.4/v04-cvrp-prepared-contract-measurement-handoff-repair-20260618.md`.
  Current CVRP handoff coverage repair:
  `scion/docs/experiments/v0.4/v04-cvrp-handoff-coverage-repair-20260618.md`.
  Current warehouse follow-up handoff coverage repair:
  `scion/docs/experiments/v0.4/v04-warehouse-followup-handoff-coverage-repair-20260618.md`.
- WSL reference:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `RSYNC_PATHS.md`.
