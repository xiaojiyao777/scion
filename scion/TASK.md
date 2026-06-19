# Scion v0.4 Evidence Repair Task

*Branch: `codex/v04-evidence-repair-plan`*
*Status: v0.4 framework/reporting repairs are accepted enough for focused CVRP and warehouse follow-up; the current CVRP prepared root carries structured bounded large-twoopt constraints, the current warehouse prepared root was refreshed from the current handoff tooling, and launch remains blocked by `gpt-5.5` auth, not by Scion code.*
*Updated: 2026-06-19*

This task defines the v0.4 closeout objective before v0.5 broad controlled
experiments. The goal is not to keep tuning campaign knobs blindly. The goal is
to prove whether the measurement instrument can detect useful effects, repair
the framework so agents can do effective research, introduce the minimal
measurement declaration layer needed for self-diagnosis, and then run a
governance on/off comparison to test whether that layer improves research
efficiency and evidence quality.

The primary task basis is `v04-core-framework-code-review-20260611.md`,
`v04-core-framework-review-20260611.md`, and
`v0.5-evidence-uplift-roadmap.md`. The v3 architecture blueprint remains the
boundary authority. v0.4 owns measurement proof, framework debt repair, and
demonstrating effective research behavior on CVRP/warehouse. v0.5 should start
only after that, as a broader matrix of controlled experiments across different
purposes, problem classes, and governance directions.

## Operating Principle

1. First prove whether the measurement instrument is effective.
2. Then repair Scion framework behavior that prevents effective agent research.
3. Then implement the minimal viable measurement declaration layer.
4. Finally run governance on/off comparisons for CVRP and warehouse.

Do not begin additional framework code repair until Phase 1 A/A calibration has
quantified whether the current protocol can detect the effects being claimed.
If Phase 1 cannot be completed because calibration tooling cannot represent the
formal protocol, that tooling repair is a Phase 1 prerequisite, not a general
framework repair.

The v0.4 objective is therefore:

- Prove the measurement instrument before interpreting failed promotions as
  failed mechanisms.
- Repair the framework paths that currently prevent deep, evidence-aware agent
  research.
- Add the smallest problem-owned measurement declaration layer needed for Scion
  to know whether it can measure the claimed effect.
- Run governance on/off only after the baseline framework is repaired, so the
  comparison measures governance value rather than unresolved v0.4 debt.

## Phase Gates

- Phase 1 gate: CVRP and warehouse both have usable A/A conclusions, including
  MDE, false-pass risk, variance structure, runtime behavior, selected
  cases/seeds, runtime budget policy, and any calibration-tooling caveats.
  The conclusion must say whether the protocol can detect the mechanism effects
  being pursued; if not, later gate/lifecycle tuning is not accepted as a fix.
- Phase 2 gate: every repair is accepted only after a v3 boundary check,
  focused tests, prompt/context evidence where relevant, and a status update.
- Phase 3 gate: the measurement declaration layer is problem-owned,
  schema-validated, and consumed through deterministic fields. Raw calibration
  diagnostics and free-form explanations must not become Decision input.
- Phase 4 gate: repaired v0.4 must show effective research behavior before the
  governance value experiment starts, especially CVRP branch depth,
  same-mechanism follow-up, and evidence interpreted against A/A MDE.
- Phase 5 gate: governance on/off arms must be matched on problem, champion
  start, model, round budget, cases, seeds, runtime budgets, and candidate or
  proposal replay controls strong enough to distinguish governance effects from
  LLM/RNG trajectory divergence.
- No phase closes until `scion/TASK.md`, current state, v0.4 history, and the
  v0.4 repair plan have been updated with artifact paths, commands, caveats,
  and the next owner.

## Effective Research Definition

v0.4 is considered able to do effective research only when the framework can
support evidence-backed continuation, rejection, and transfer of hypotheses.
Promotion is a useful signal, but it is not the only acceptable research result.

For CVRP, effective research requires:

- Candidate evidence interpreted against A/A MDE and case-level variance, not
  only aggregate win rate.
- Low-SNR but non-negative solver-design ideas can receive same-mechanism
  follow-up instead of being immediately parked.
- Clearly negative effects, infeasible candidates, candidate failures, and
  true runtime regressions still fail closed.
- Branches show depth beyond shallow one-off attempts, including within-branch
  iteration and mechanism-family continuity.
- Later prompts receive useful branch lessons and problem-owned opportunity
  diagnostics.
- Code-phase contexts retain direct visibility of champion/current-branch/target
  source; compression may reduce boilerplate and duplicated governance payloads
  but must not hide the research object code.

For warehouse, effective research requires:

- Existing promotion behavior does not regress.
- Repeated campaigns distinguish real plateau from missed continuous-promotion
  opportunities.
- Runtime configuration and observed fast completion are explained by the
  problem/runtime model rather than treated as incidental noise.
- Branch transfer and prompt context are inspected, not inferred from final
  promotion status alone.

## Experiment Defaults

- Use the local `gpt-5.5` model for Scion runs that involve LLM proposal,
  diagnosis, or code-generation calls.
- Treat copied configs, protocol/split/seed hashes, champion versions,
  workspace commits, and run directories as required evidence.
- When runtime caps are size-dependent in the formal protocol, experiment
  reports must say whether a run used the formal policy or a conservative
  approximation such as a uniform time limit.
- Do not treat aggregate win rate as sufficient evidence. Pair-level deltas,
  per-case behavior, seed/RNG sensitivity, runtime events, and branch trajectory
  must be inspected for experiments whose purpose depends on them.
- Resource policy: one or two live cells may run on the 2-core server when they
  are short acceptance checks or single-run diagnostics. Larger matrices and
  long parallel experiments should run on WSL through the reverse SSH channel,
  but only from a synchronized clean runner worktree; do not run new WSL cells
  from an unsynced dirty project tree.

## Required Reading

Every main-thread phase and every Scion subagent brief must start with the v3
architecture baseline:

1. `scion/design/scion-architecture-v3.md`

Task-specific references:

2. `scion/reports/v04-core-framework-code-review-20260611.md`
3. `scion/reports/v04-core-framework-review-20260611.md`
4. `scion/design/v0.5-evidence-uplift-roadmap.md`
5. `scion/reports/v04-audit-agent-experiment-guide-20260609.md`
6. `scion/docs/AGENT_ONBOARDING.md`
7. `scion/docs/status/current-state.md`
8. `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`

Exception: explicitly designated independent VRP-only control agents are not
Scion subagents. They must not read Scion design, task, audit, status, or
experiment artifacts, because their purpose is to test what an uncontaminated
plain Codex VRP researcher can discover against the standalone `vrp/` baseline.
Their outputs are external-control hypothesis seeds, not Scion Protocol
evidence.

## Roles

Main thread owns:

- v3 boundary alignment and architecture decisions.
- Task decomposition, subagent brief design, and acceptance criteria.
- Git hygiene, branch/commit management, and conflict resolution.
- Experiment design, launch decisions, postrun acceptance, and status updates.
- Final integration review before any repair is accepted.

Subagents own bounded execution slices:

- Code changes in explicitly assigned, disjoint file scopes.
- Read-only design audits for focused questions.
- Experiment postrun analysis, prompt/context analysis, and branch-level
  research analysis.

Every subagent brief must require:

- Read `scion/design/scion-architecture-v3.md` first.
- State how the proposed work preserves the v3 boundary.
- Keep CVRP/VRP/warehouse semantics in problem-owned layers.
- Report changed files, tests run, experiment artifacts inspected, and residual
  risks.
- Avoid reverting unrelated work in the shared worktree.

Default subagent brief template:

- Objective: one bounded outcome tied to a phase gate.
- Required reading: `scion/design/scion-architecture-v3.md` first, then only the
  audit/design/experiment artifacts needed for the assignment.
- Scope: exact files, modules, or run directories the subagent may touch or
  inspect.
- Boundary requirement: what must remain in generic core, what must remain
  problem-owned, and what must stay outside `DecisionFeatures`.
- Acceptance: tests, artifact checks, prompt/context samples, or experiment
  analyses required before the main thread can accept the work.
- Deliverables: concise report with changed files, commands run, artifacts
  inspected, evidence-backed conclusions, and residual risks.

## V3 Boundary Acceptance

- LLM output remains tainted proposal material.
- Decision may read only `DecisionFeatures`.
- `DecisionFeatures` must not contain raw BKS, case gap, case hardness,
  mechanism rankings, LLM text, prompt ratios, cross-branch lessons, or raw
  problem diagnostics.
- Problem-owned diagnostics may guide proposal context, protocol configuration,
  runtime governance, lifecycle policy, and readiness checks only through
  deterministic, schema-validated fields.
- Validation/frozen details must not leak into proposal context in a way that
  violates staged exposure control.

## Phase 0 - Freeze Current Evidence Baseline

Purpose: finish and audit the current CVRP/warehouse validation runs before any
new repair changes.

Tasks:

- Wait for current experiments to finish.
- Record commit, branch, run directories, launch command, copied problem
  configs, protocol/split/seed hashes, and wrapper exit status.
- Reconcile counters: proposal sessions, unique hypotheses, formal candidates,
  screening rows, validation rows, frozen rows, fresh-runtime replays, and
  effective rounds.
- Audit pair-level metrics rather than only aggregate win rate.
- Inspect prompt manifests and selected LLM contexts for each candidate,
  including hypothesis, target intent, code, tool observations, compact signals,
  cross-branch map, and source visibility.
- Analyze branch dimensions: branch depth, mechanism family continuity,
  sibling/ancestor lessons, active/park/archive transitions, and whether branch
  experience transfers into later prompts.

Exit criteria:

- A postrun report explains why each candidate stopped and whether the run
  reached validation/frozen.
- Runtime saturation/fresh replay behavior is explicitly checked.
- Prompt signal density is measured separately for governance, research signal,
  problem-domain diagnostics, source/code, and cross-branch material.
- Status docs are updated before Phase 1.

Status docs to update:

- `scion/docs/status/current-state.md`
- `scion/docs/status/v0.4-history.md`
- `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`
- `scion/TASK.md`

Current checkpoint:

- Warehouse remains the accepted v0.4 positive research-path checkpoint.
  Champion `v2` promotion and the split-preserving cost-compression telemetry
  repair show that the framework can still support useful warehouse research.
  The open warehouse question is continuous follow-on improvement, not basic
  viability.
- CVRP continuation and observability are now repaired enough for meaningful
  follow-up: copied campaigns restore champion, active branch, workspace,
  hypothesis, candidate patch, branch evidence, follow-up case targeting, compact
  status/progress, measurement readiness, and research-efficiency reporting.
- Research-efficiency reports now include a report-only `research_continuity`
  block that turns existing observability counters into same-mechanism follow-up
  selection rate, branch-lesson satisfaction/semantic-gap rates, weak-positive
  transfer acceptance rate, lesson action counts, and branch-shape summary. This
  is postrun audit material only; it does not feed Decision, Protocol gates,
  scheduling, lifecycle, promotion, or proposal context. Postrun artifact
  inventories now mark `research_continuity` as an explicit Phase 4
  evidence-coverage requirement, and postrun analysis briefs summarize the
  current-run continuity metrics for delegated review. Postrun analysis briefs
  also summarize current-run branch/event/hypothesis state,
  protocol/formal-candidate accounting, measurement effect-vs-MDE, prompt
  context/source visibility, code/hypothesis source-visibility guarantees,
  prompt signal density, runtime feedback/drain behavior, and failure
  taxonomy/proposal quality without exposing raw prompts, responses, patches,
  raw logs, source bodies, or mutating runtime semantics. Postrun artifact
  inventories now distinguish broad source-visibility fingerprints from
  code-phase source-visibility guarantee evidence, and split
  research-continuity coverage into same-mechanism follow-up, branch-lesson
  usage, weak-positive transfer, and branch research shape. Protocol row,
  candidate, and validation/frozen stage accounting are also explicit Phase 4
  coverage items.
  Reports:
  `scion/docs/experiments/v0.4/v04-research-continuity-report-metrics-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-phase4-research-continuity-coverage-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-phase4-research-continuity-subsignal-coverage-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-phase4-protocol-stage-coverage-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-postrun-research-continuity-brief-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-postrun-prompt-context-visibility-brief-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-postrun-measurement-effect-brief-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-postrun-runtime-feedback-brief-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-postrun-failure-taxonomy-brief-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-postrun-protocol-accounting-brief-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-postrun-branch-state-brief-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-postrun-source-visibility-brief-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-phase4-code-source-visibility-coverage-repair-20260618.md`.
- Budget-exhausting runtime semantics now avoid treating high aggregate
  `runtime_regression_rate` as a hard low-SNR expansion blocker, lifecycle
  soft-abandon signal, repeated-signal discriminator, screening feedback
  `runtime_regression` tier, low-signal `retain_head` workspace veto, or strong
  prompt action signal when the problem declares
  `runtime_model=budget_exhausting`. Reports:
  `scion/docs/experiments/v0.4/v04-budget-exhausting-runtime-regression-semantics-repair-20260618.md`
  and
  `scion/docs/experiments/v0.4/v04-budget-exhausting-decision-lifecycle-runtime-semantics-repair-20260618.md`
  and
  `scion/docs/experiments/v0.4/v04-budget-exhausting-screening-feedback-runtime-tier-repair-20260618.md`
  and
  `scion/docs/experiments/v0.4/v04-budget-exhausting-finalizer-retain-head-repair-20260618.md`.
- Low-signal same-branch observation samples now retain scheduler/result
  semantics as `refine_active` instead of `repair_diagnostic`, so the one
  allowed no-effect same-mechanism sample is not reported as repair work before
  any subsequent clean fork. Report:
  `scion/docs/experiments/v0.4/v04-low-signal-same-branch-scheduler-slot-repair-20260618.md`.
- Current active no-effect branch-local lessons now produce advisory
  `same_branch_refinement` proposal requirements, so the next same-mechanism
  hypothesis must contrast the prior no-effect evidence rather than repeat the
  same activation/effect path. Report:
  `scion/docs/experiments/v0.4/v04-low-signal-same-branch-lesson-usage-repair-20260618.md`.
- Trajectory-divergent all-tie screening now counts as low-SNR expand/continue
  evidence instead of a win-rate failure when quality is non-regressive and no
  runtime/candidate-failure veto is present. Report:
  `scion/docs/experiments/v0.4/v04-trajectory-divergent-all-tie-low-snr-expand-repair-20260618.md`.
- Measurement integration now has real-asset coverage for CVRP formal and
  warehouse production problem/protocol loading plus the `scion run` problem-v1
  ingress path. Problem-owned practical deltas, runtime model, pairing
  validity, and reduced readiness feed deterministic `ProtocolConfig` fields;
  raw calibration diagnostics remain outside `DecisionFeatures`; warehouse
  specs no longer hard-code local surrogate paths, so WSL checkouts resolve the
  same calibration asset. Report:
  `scion/docs/experiments/v0.4/v04-measurement-integration-real-asset-coverage-20260618.md`.
- A/A calibration artifacts now include explicit champion/candidate runtime
  budget-hit ratios and flags per replay, so budget saturation is auditable
  without feeding raw diagnostics into `DecisionFeatures`. Report:
  `scion/docs/experiments/v0.4/v04-aa-calibration-runtime-budget-hit-evidence-20260618.md`.
- CVRP live agentic checks now demonstrate useful research-loop behavior
  without yet demonstrating solver improvement. The framework can steer
  target-intent, carry branch lessons into prompts, generate material solver
  code, complete formal screening, preserve mechanism telemetry, and reject weak
  or negative mechanisms with evidence.
- Rejected/default-avoid CVRP directions include broad VNS removal, pure
  ALNS/no-polish, simple initial-VNS disablement, raw cadence-2,
  recent-best/stall gating, fixed early-8, tested share70 cap/rescue variants,
  unchanged route-merge absorption, unchanged demand-slack regret insertion,
  unchanged cross-route 2-opt reconnect, unchanged cluster-biased worst removal,
  and unchanged route-limit seed diversification.
- Construction seed/portfolio mechanisms must show direct objective-changing
  seed effect via same-run seed baseline or same-mechanism accepted delta.
  Route-cap fallback activation, seed-pool size, or merely selecting a seed is
  only activation/design evidence.
- A direct WSL external-control replay found a strong large-instance
  intra-route two-opt signal above the VNS threshold (`8/8` feasible wins on
  four XL cases x two seeds), but the tested unbounded `vrp/src/solver.py`
  fallback is not accepted and is not present in the clean checkout because the
  local-search operator is not deadline-aware. It may be used as a
  problem-owned research-focus seed for a budget-aware CVRP hypothesis, not as
  Scion Protocol evidence or an accepted baseline update.
  Report:
  `scion/docs/experiments/v0.4/v04-vrp-large-instance-two-opt-seed-evidence-20260618.md`.
- The CVRP launcher now exposes this seed in the prepared `research_focus`,
  requires the agent to pursue it only as a deadline-aware bounded
  local-search mechanism, and lists the unbounded fallback as default-avoid.
  Report:
  `scion/docs/experiments/v0.4/v04-cvrp-large-twoopt-launch-focus-repair-20260618.md`.
- Prepared contract/inventory coverage now requires both the
  `large_instance_intra_route_two_opt_seed` opportunity token and the
  unbounded large-instance two-opt fallback default-avoid token, so future
  prepared roots fail static handoff coverage if the guidance is dropped. The
  coverage is also exposed as named problem-specific prepared-brief/inventory
  items for delegated review.
  Report:
  `scion/docs/experiments/v0.4/v04-cvrp-large-twoopt-contract-coverage-repair-20260618.md`.
- CVRP hypothesis proposal context now receives problem-owned
  measurement/opportunity diagnostics: MDE-vs-practical-delta, low-SNR
  interpretation, aggregate screening headroom, current default-avoid
  mechanisms, and measurable opportunity classes. These diagnostics are
  proposal-only and remain outside `DecisionFeatures`, Protocol gates,
  lifecycle, scheduler, and promotion. Report:
  `scion/docs/experiments/v0.4/v04-cvrp-measurement-opportunity-diagnostics-repair-20260618.md`.
- Phase 4 artifact inventories now expose prompt signal-density coverage as a
  separate report-only requirement, so delegated postrun review can distinguish
  missing prompt block-family accounting from generic source-visibility
  evidence. Report:
  `scion/docs/experiments/v0.4/v04-prompt-signal-density-coverage-repair-20260618.md`.
- Research-continuity and measurement-effect analysis briefs now expose
  branch-depth distribution, active shape, mechanism-family breadth, and
  mechanism-family effect summaries. They also aggregate branch-lesson semantic
  failure/block counts, so delegated postrun review can distinguish deep
  follow-up from shallow branch scattering, family-level sub-MDE/no-effect
  patterns, and follow-up hypotheses that mention prior evidence without
  semantically using it. Postrun briefs now also include a report-only
  `research_context_actionability_summary` joining prompt block-family signal
  with research-continuity gaps, so delegated review can tell whether semantic
  branch-lesson gaps or missed follow-up opportunities align with missing
  research/cross-branch context, omitted/truncated sections, or governance-heavy
  prompts. That actionability summary now also carries branch-lesson semantic
  failure/block reason mixes, so reviewers can separate metadata-only payloads,
  unrecognized linkage aliases, and true semantic mismatches. Live hypothesis
  prompts now also receive a compact proposal-only `research_shape_diagnostics`
  signal from the cross-branch research map, so branch depth, shallow scatter,
  and repeated non-positive family shape are available during proposal planning
  while remaining excluded from `DecisionFeatures`. Reports:
  `scion/docs/experiments/v0.4/v04-research-continuity-brief-shape-projection-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-mechanism-family-effect-summary-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-branch-lesson-semantic-diagnostics-brief-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-research-context-actionability-brief-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-branch-lesson-actionability-reason-mix-repair-20260618.md`.
  and
  `scion/docs/experiments/v0.4/v04-research-shape-prompt-signal-repair-20260618.md`.
- The next prepared campaign is temporarily blocked by LLM infrastructure, not by
  Scion code. Restore a `gpt-5.5` route that passes a real
  `/v1/chat/completions` check with non-empty output before launching; the
  latest WSL launch-readiness preflight reaches the proxy and reports
  no active authenticated account, while the real chat completion returns HTTP
  `401` with `classification=not_authenticated`. The auth pool may move between
  expired and refreshing states, but launch remains blocked until a real
  completion succeeds.
  Readiness now includes `operator_action.login_url`. Use the repaired launcher
  `--completion-preflight` and `--api-key-env` paths when appropriate, use
  `--resume-from-campaign` for branch-continuation checks, and keep its
  prepare/postrun acceptance bundle enabled, including the secret-free
  prepared-run manifest, prepare-time delegated handoff brief/inventory,
  CVRP research-focus/default-avoid handoff and CVRP
  measurement/opportunity handoff diagnostics,
  postrun analysis brief, and artifact/count inventory with report-only Phase 4
  evidence coverage, prepared contract checks, launch-readiness handoff
  snapshots, and prepared-only lifecycle guards plus structured
  preflight-failed launch-root guards that preserve failure classification,
  login-url presence, and operator action while preventing copied resume
  artifacts from being treated as current-run postrun evidence. Launchers now
  auto-fill deterministic report-only `control_pair_key` metadata when the
  operator omits it, preventing prepare-only roots from failing the prepared
  contract because optional handoff metadata was blank. CVRP prepared contracts
  now also require the measurement/opportunity handoff diagnostics before
  static readiness can pass, plus default-avoid coverage,
  route-merge/construction-seed direct-effect rules, and explicit
  decision-boundary coverage exposed as CVRP `problem_specific_requirements`.
  Current CVRP handoff coverage repair:
  `scion/docs/experiments/v0.4/v04-cvrp-handoff-coverage-repair-20260618.md`.
  Inventory and
  analysis-brief top-level branch/event/hypothesis/LLM-trace fields are
  current-run scoped; copied campaign counts live under `resume_snapshot`. For
  historical roots or schema drift, rebuild the report-only acceptance bundle
  with
  `scion/tools/rebuild_postrun_acceptance.py` before delegating postrun
  analysis; current launcher postrun paths call this rebuild tool directly.
  Before launch, require
  `scion/tools/check_launch_readiness.py <prepared-root> --require-launch-ready --format json`
  to report `launch_ready=true`; if completion preflight fails, follow its
  `operator_action` and use the reported proxy login URL when present.
  The previous prepared roots were invalidated by runtime guard path changes.
  The current CVRP root was prepared from WSL checkout `44f78e9` with the
  large-instance two-opt seed as proposal-only research focus and structured
  `large_instance_two_opt_constraints`; the current
  warehouse root was prepared from WSL checkout `44f78e9` for the champion
  `v2` continuous-improvement follow-up. Both current roots pass static
  launch, prompt/context identity, launch-env readiness, and runtime-guard
  consistency. Their prepared analysis briefs keep required review questions
  problem-specific: warehouse roots do not ask the CVRP large-twoopt question,
  and CVRP roots do not ask the warehouse plateau question.
  Their prepared handoff artifacts carry current CVRP/warehouse
  `problem_specific_requirements`, and strict launch readiness now expands the
  corresponding problem-specific prepared contract checks as
  `problem_specific_prepared_handoff=ok`, while
  `--require-launch-ready` still exits `64` because real `gpt-5.5`
  completion preflight returns HTTP `401` / `not_authenticated` with
  `code=invalid_api_key` and auth pool `active=0`, `total=1`.
  The non-active account may appear as expired or refreshing.
  Prepared handoff rebuilds now also emit report-only
  `prompt_context_readiness` artifacts. The current CVRP and warehouse
  prepared roots both report `ready_for_launch_prompt_audit=true` with no
  missing required sources, proving prepared research focus, copied
  campaign summary/status, problem-specific handoff fields, the live
  `research_shape_diagnostics` prompt path, and the
  `prepared_research_focus_prompt_bridge` source and launch-environment markers
  are visible before launch without rendering raw provider prompts or changing
  runtime decisions. `check_launch_readiness.py` now requires this
  prompt/context readiness artifact, checks that it belongs to the current
  prepared root and manifest commit, and rechecks the source and launch markers
  as part of static readiness. The launchers export `PREPARED_RUN_MANIFEST` in
  the generated `run.sh`; readiness audits require the manifest file,
  `launch.env` assignment, and `run.sh` export marker.
  Current prepared-handoff rebuild report:
  `scion/docs/experiments/v0.4/v04-prepared-handoff-rebuild-tool-20260618.md`.
  Current warehouse prepared-root refresh:
  `scion/docs/experiments/v0.4/v04-warehouse-v2-followup-root-refresh-20260619.md`.
  Current launch-readiness problem-specific handoff visibility and prepared-root
  refresh:
  `scion/docs/experiments/v0.4/v04-launch-readiness-problem-specific-handoff-visibility-20260619.md`.
  Current postrun handoff review-ready guard and prepared-root refresh:
  `scion/docs/experiments/v0.4/v04-postrun-handoff-review-ready-guard-20260619.md`.
  Current incomplete-handoff required-review-question refresh:
  `scion/docs/experiments/v0.4/v04-postrun-incomplete-handoff-review-question-20260619.md`.
  Current problem-specific postrun review-question filter and prepared-root
  refresh:
  `scion/docs/experiments/v0.4/v04-postrun-problem-specific-review-question-filter-20260619.md`.
  Current prepared prompt/context readiness report:
  `scion/docs/experiments/v0.4/v04-prepared-prompt-context-readiness-handoff-repair-20260618.md`.
  Current strict launch-readiness report:
  `scion/docs/experiments/v0.4/v04-launch-readiness-strict-launch-ready-repair-20260618.md`.
  Current prepared-root refresh:
  `scion/docs/experiments/v0.4/v04-research-shape-prompt-signal-repair-20260618.md`.
  Current prepared handoff measurement-diagnostics repair:
  `scion/docs/experiments/v0.4/v04-cvrp-prepared-handoff-measurement-diagnostics-repair-20260618.md`.
  Current prepared contract measurement-diagnostics repair:
  `scion/docs/experiments/v0.4/v04-cvrp-prepared-contract-measurement-handoff-repair-20260618.md`.
  Current CVRP active solver context repair:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-active-solver-context-repair-20260618.md`.
  Current prepared research-focus prompt bridge repair:
  `scion/docs/experiments/v0.4/v04-prepared-research-focus-prompt-bridge-repair-20260618.md`.
  Current launch readiness prompt/context guard repair:
  `scion/docs/experiments/v0.4/v04-launch-readiness-prompt-context-guard-repair-20260618.md`.
  Current CVRP bounded large-twoopt handoff repair:
  `scion/docs/experiments/v0.4/v04-cvrp-large-twoopt-bounded-handoff-repair-20260619.md`.
  Current CVRP large-twoopt postrun summary guard:
  `scion/docs/experiments/v0.4/v04-cvrp-large-twoopt-postrun-summary-guard-20260619.md`.
  Current launch-prepared CVRP root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-44f78e9-1r-gpt55-20260619T011450Z-claw`.
- Warehouse continuous-improvement follow-up is now launch-prepared but not
  launched. `launch_warehouse_agentic_campaign.py` writes copied production
  configs with repo/data-root path rewrites, secret-safe env handling, and the
  same real completion preflight requirement before campaign startup. It can
  copy the accepted warehouse `v2` campaign as the new run root so the next
  check continues from the promoted champion rather than restarting baseline,
  writes a secret-free prepared-run manifest and delegated handoff
  brief/inventory at prepare time, and writes the standard postrun acceptance
  report bundle by default after Scion exits, including delegated analysis
  brief and artifact/count inventory with report-only Phase 4 evidence coverage
  flags, prepared contract checks, problem-specific warehouse follow-up handoff
  coverage, launch-readiness handoff snapshots, prepared-only lifecycle guards,
  and preflight-failed launch-root guards. Warehouse prepared contracts now
  require the champion-v2 plateau-vs-continuous-improvement framing, promotion
  preservation, branch transfer, quality-blocked-vs-protocol-evaluated
  distinction, cost-vs-split telemetry, and fast-completion runtime explanation
  needed for the next postrun review. Warehouse postrun analysis briefs now
  also include `warehouse_followup_summary`, so delegated review can separate
  prepared-only launch roots, quality-blocked proposal behavior,
  protocol-evaluated evidence with missing review inputs, and
  plateau-review-ready evidence before making any stagnation conclusion.
  Report:
  `scion/docs/experiments/v0.4/v04-warehouse-followup-handoff-coverage-repair-20260618.md`.
  Current warehouse follow-up analysis-brief repair:
  `scion/docs/experiments/v0.4/v04-warehouse-followup-analysis-brief-repair-20260618.md`.
  Current warehouse plateau-review regression coverage:
  `scion/docs/experiments/v0.4/v04-warehouse-followup-plateau-review-coverage-20260618.md`.
  Current warehouse plateau-review input guard:
  `scion/docs/experiments/v0.4/v04-warehouse-plateau-review-inputs-guard-20260619.md`.
  Current launch-prepared warehouse root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-44f78e9-6r-gpt55-20260619T011450Z-claw`.
- Future WSL campaign launches must set
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`; without
  it, WSL may import stale Scion core modules from
  `/home/xjy-ubuntu/projects/scion/scion`.

## Phase 1 - A/A Calibration and Measurement Power

Purpose: prove whether the current protocol can detect useful effects before
changing gates or lifecycle policy.

Tasks:

- Run champion vs champion A/A calibration for CVRP with independent RNG streams
  on the formal screening set.
- Run champion vs champion A/A calibration for warehouse with its production
  protocol shape.
- Report MDE, false-positive win rate, pair delta distribution, case-level
  variance, seed-level variance, practical-delta detectability, and runtime
  saturation profile.
- Compare MDE against expected mechanism effects and against
  `practical_delta_screen` / `practical_delta_validate`.

Exit criteria:

- CVRP and warehouse both have calibration reports.
- If MDE is larger than the expected mechanism effect, the protocol is marked
  measurement-power insufficient and framework repair must focus on measurement
  and protocol design before more campaign runs.
- Calibration results become proposal-visible diagnostics only; they are not
  promotion evidence.

Phase 1 decision:

- Concluded on 2026-06-11. CVRP and warehouse both have usable A/A artifacts.
- CVRP formal protocol-time A/A:
  `/home/clawd/research/scion-experiments/v04-phase1-aa-cvrp-screening-modify-r3-protocoltime-20260611T191356Z-claw/aa_noise_floor.json`.
  It produced `n_pairs=96`, `mde_at_power_80=9.9` raw `total_distance`,
  `false_pass_rate_at_current_gate=0.0`, and `recommended_min_seeds=8`.
  The run used protocol-resolved per-case time limits (`30s` and `45s`) and
  complete pair evidence. Current CVRP `practical_delta_screen=2.0` is below
  this measured detection floor, so Phase 0 screening failures are
  measurement-power insufficient evidence, not mechanism disproof.
  Read-only subagent validation confirmed wrapper exit status, artifact hash,
  selected cases/seeds, seed-offset rule, safe data-root resolution,
  runtime-policy metadata, pair evidence completeness, positive elapsed runtime
  fields, and `DecisionFeatures` exclusion.
- Warehouse modify A/A:
  `/home/clawd/research/scion-experiments/v04-phase1-aa-warehouse-screening-modify-r3-defaultbudget-20260611T164426Z-claw/aa_noise_floor.json`.
  It produced `n_pairs=36`, `mde_at_power_80=577.5` raw `total_cost`, and
  `false_pass_rate_at_current_gate=0.0`.
- Warehouse create A/A:
  `/home/clawd/research/scion-experiments/v04-phase1-aa-warehouse-screening-create-r3-defaultbudget-20260611T164426Z-claw/aa_noise_floor.json`.
  It produced `n_pairs=60`, `mde_at_power_80=1725.0` raw `total_cost`, and
  `false_pass_rate_at_current_gate=0.0`.
- Phase 2 may begin, but blind win-rate/lifecycle tuning is not accepted as a
  fix. Repairs must make measurement power, runtime semantics, lifecycle depth,
  and context signal density explicit.

## Phase 2 - Framework Repairs for Effective Research

Purpose: repair the v0.4 blockers identified by the 2026-06-11 audits while
preserving v3 boundaries.

Required repair slices:

- F-1 practical delta: resolve problem-owned practical delta declarations into
  protocol gates and remove dead hard-coded behavior from effective decisions.
- F-2 runtime semantics: support `runtime_model: budget_exhausting`, downgrade
  budget saturation to info for anytime solvers, disable meaningless runtime-tie
  fresh replay, and preserve quality-tie runtime speedup semantics where valid.
- F-3 low-SNR screening: make screening expand reachable for declared
  trajectory-divergent problems when evidence is low-signal but not
  regressively negative.
- Lifecycle depth: prevent low-SNR CVRP branches from being parked before
  same-mechanism follow-up can happen, while still fail-closing hard negative
  delta, infeasibility, candidate failures, and runtime regressions.
- Context signal density: add problem-owned CVRP proposal diagnostics such as
  per-case residual opportunity, gap-to-BKS where available, noise/MDE summary,
  and mechanism effect ranking.
- Source visibility: protect champion/current branch/target source visibility,
  especially during code phase. Context compression may target governance
  boilerplate, raw duplicated logs, and generic cross-branch payloads, not the
  research object code.
- Context phase policy: proposal/research phases should increase problem-domain
  signal density, while code phases must preserve direct visibility of the
  champion/current branch/target source needed to modify or judge the research
  object.

Exit criteria:

- Focused tests cover each repair slice.
- Warehouse `trajectory_stable` behavior is unchanged unless explicitly covered
  by a problem-owned declaration.
- CVRP `trajectory_divergent` behavior can expand/continue low-SNR research
  without admitting negative-effect candidates.
- Prompt manifests show better problem-domain signal density without removing
  required source/code context.

## Phase 3 - Minimal Measurement Declaration Layer

Purpose: give Scion a problem-owned, schema-validated way to know whether its
instrument is likely to measure the claimed effect.

Minimum viable fields:

- `runtime_model`: `comparative` or `budget_exhausting`.
- `pairing_validity`: `trajectory_stable` or `trajectory_divergent`.
- `effect_scale`: metric, unit, practical screening delta, practical validation
  delta.
- `calibration_ref`: path to the latest compatible A/A calibration report.
- `calibration_max_age_days`.
- Optional readiness summary: MDE, noise band, effect-to-MDE ratio, and
  signal-to-noise tier.

Consumers:

- Protocol gates may resolve practical deltas and low-SNR expand policy.
- Runtime governance may switch between comparative and budget-exhausting
  semantics.
- Lifecycle may use deterministic measurement-readiness tiers.
- Proposal context may receive problem-owned diagnostics and opportunity
  summaries.
- Decision must not read raw calibration diagnostics or free-form explanations.

Exit criteria:

- The declaration layer is documented and tested.
- Missing or stale calibration is visible as readiness/status, not silently
  ignored.
- Measurement diagnostics are excluded from `DecisionFeatures` unless reduced to
  approved deterministic enums/numeric features.

## Phase 4 - Focused Validation

Purpose: verify that repaired v0.4 can support effective research before the
governance value experiment.

CVRP acceptance signals:

- Validation/frozen can be reached when evidence justifies it.
- Branch depth increases beyond shallow one-off attempts.
- Same-mechanism follow-up occurs when low-SNR evidence is inconclusive.
- Mechanism-family lessons are visible in later prompts and affect proposal
  choices.
- Runtime saturation/fresh replay no longer pollutes feedback for
  budget-exhausting solvers.
- Results are interpreted against A/A MDE, not only raw win rate.

Warehouse acceptance signals:

- Existing promotion path does not regress.
- Repeated campaigns clarify whether warehouse has continuous promotion
  potential or a real plateau.
- Runtime budget calibration explains why actual warehouse runs finish quickly
  despite high configured caps.

Required analysis:

- Inspect every LLM call context relevant to the experiment purpose.
- Audit branch-level research: within-branch depth, sibling divergence,
  cross-branch transfer, and whether failed hypotheses improve later proposals.
- Reconcile final evidence with protocol metrics, lifecycle state, prompt
  visibility, and copied configs.

## Phase 5 - Governance On/Off Comparison

Purpose: test whether measurement-aware governance improves research efficiency
and evidence quality after baseline repairs are complete.

Experiment design:

- Same problem, champion start, model, round budget, cases, seeds, and runtime
  budgets.
- ON arm: measurement-aware protocol/runtime/lifecycle/context enabled.
- OFF arm: calibration and diagnostics recorded, but not allowed to drive
  protocol/runtime/lifecycle/context.
- At least three independent repeats per problem when budget permits.

Primary metrics:

- Promotions above A/A MDE.
- Validation/frozen reach rate.
- Branch depth and same-mechanism follow-up rate.
- Useful cross-branch transfer rate.
- Prompt problem-domain signal density.
- Runtime replay/saturation noise rate.
- Cost per effective protocol row and cost per accepted research insight.

Exit criteria:

- The on/off result supports or rejects the claim that measurement-aware
  governance improves Scion research quality.
- v0.5 can start from a clean experiment matrix rather than unresolved v0.4
  framework debt.

## Current Historical Index

The previous append-only status log has been intentionally removed from this
active task file. It duplicated experiment reports, stale run roots, and older
interpretations that no longer define the v0.4 operating truth.

Use these sources instead:

- Current operational truth: `scion/docs/status/current-state.md`.
- Curated milestone index: `scion/docs/status/v0.4-history.md`.
- Detailed launch, postrun, and repair evidence: `scion/docs/experiments/v0.4/`.
- Exact legacy chronology when needed: git history for this file.

Keep this section short. New facts should update the Current checkpoint above or
the relevant status/experiment report, not recreate an append-only log here.

## Status Cadence

The main thread updates status when the active operating truth changes:

- Phase gate pass/fail decision.
- Experiment result that changes current interpretation or the next action.
- Accepted or rejected subagent work that changes current interpretation or the
  next action.
- Commit that changes task scope, protocol behavior, measurement behavior,
  context composition, runtime governance, or lifecycle policy.

Do not record every launch, rerun, intermediate failure, or subagent exchange in
status docs. Detailed run facts, counters, commands, wrapper status, and
artifact-level caveats belong in launch/postrun reports. `current-state.md`
should stay a short operational snapshot that replaces stale conclusions, and
`v0.4-history.md` should stay a sparse milestone index rather than an
append-only event stream.

Status docs to keep aligned:

- `scion/TASK.md`
- `scion/docs/status/current-state.md`
- `scion/docs/status/v0.4-history.md`
- `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`

## Git Hygiene

- Keep commits sliced by phase or repair surface.
- Do not mix experiment reports, framework repairs, and unrelated cleanup in one
  commit unless explicitly accepted.
- Do not revert user or subagent changes unless explicitly instructed.
- Before each commit, record tests and experiment artifacts used for acceptance.
