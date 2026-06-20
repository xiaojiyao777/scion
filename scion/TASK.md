# Scion v0.4 Evidence Repair Task

*Branch: `codex/v04-evidence-repair-plan`*
*Status: v0.4 framework/readiness/launcher repairs are accepted enough for focused warehouse and CVRP follow-up, but v0.4 is not closed until live runs demonstrate effective research behavior. Current WSL prepared roots were regenerated at runtime commit `be6e7da7`; both pass static readiness and remain blocked only by external `gpt-5.5` completion auth.*
*Updated: 2026-06-20*

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
- Protocol-evaluated positive effects at or above MDE must be routed as
  continuous-improvement review opportunities, not mislabeled as plateau-ready
  evidence.
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

Current-status docs to update when operating truth changes:

- `scion/docs/status/current-state.md`
- `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`
- `scion/TASK.md`

Update `scion/docs/status/v0.4-history.md` only for sparse milestone changes,
not for every prepared root, wrapper failure, or repair-detail checkpoint.

Current checkpoint:

- Warehouse is the accepted v0.4 positive research-path checkpoint. Champion
  `v2` promoted in the validation-transfer rerun; the open empirical question is
  whether Scion can produce additional useful research from `v2` or correctly
  diagnose a real post-v2 plateau.
- CVRP/VRP continuation is repaired enough for the next focused solver-design
  follow-up, but v0.4 is not yet accepted because no current CVRP branch has
  shown continuous improvement or promotion. The active CVRP root uses the
  large-instance intra-route two-opt seed only as proposal guidance and requires
  a bounded, deadline-aware mechanism with current-run CMT2/CMT4 case-level
  protection evidence. Launch readiness also verifies that those protected
  cases are present in formal screening before the prepared root can be
  considered static-ready.
- Active WSL prepared roots:
  - Warehouse:
    `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-be6e7da-postbrief-6r-gpt55-20260620T230603Z-claw`
  - CVRP:
    `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-be6e7da-postbrief-resume-4r-gpt55-20260620T230740Z-claw`
- Strict launch readiness for both current roots reports `static_ready=true`,
  `launch_ready=false`, and `failed_static_required_checks=[]`. The only
  required failure is external completion auth:
  HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`.
  The auth pool has `active=0`, `total=1`; there is no active account
  available. Ignore volatile substate changes such as expired versus refreshing
  unless active auth becomes available. Launch readiness exposes these fields in
  top-level `completion_preflight_summary` and compatible flat fields, so status
  refreshes do not need to know nested check paths. Prepared static handoff
  reports now expose `readiness_scope=static_only_completion_preflight_not_run`
  and `launch_blockers=["completion_preflight_not_run"]`; only strict launch
  checks with `readiness_scope=launch_with_completion_preflight` can approve
  launch. Launch readiness also exposes top-level runtime/env status fields for
  status refreshes; the current roots report `runtime_guard_status=ok`,
  `prepared_runtime_commit=be6e7da7`, and either
  `runtime_guard_reason=runtime_guard_commit_matches` or
  `runtime_guard_paths_unchanged_since_prepare` after doc-only commits. They
  also report `launch_env_secret_permissions=ok`, `launch_env_mode=0o600`, and
  `campaign_execution_marker_status=ok` through top-level marker summary
  fields.
  Disabled proposal/APS caps, code-source visibility, source-read headroom,
  item-level `research_focus` prompt visibility, and CVRP/warehouse
  adapter-derived opportunity diagnostics are covered by current evidence
  reports rather than repeated here.
  Do not launch either root until
  `scion/tools/check_launch_readiness.py <prepared-root> --require-launch-ready --format json`
  reports `launch_ready=true`.
- Current framework guarantees, all report-only/control-plane or problem-owned
  unless explicitly part of Protocol:
  - Measurement declarations and A/A calibration are problem-owned and excluded
    from `DecisionFeatures`.
  - Budget-exhausting runtime semantics suppress stale fresh-runtime replay
    markers/pressure and comparative runtime-ratio slowdown blockers for
    low-SNR follow-up. Low-SNR trajectory-divergent lifecycle continuation and
    hard-negative fail-closed behavior are covered by focused tests. Postrun
    runtime budget diagnostics preserve saturated-side and repairable counts so
    delegated review can distinguish candidate repair signals from champion-only
    or observational saturation.
  - Screening gate reporting and Decision routing agree on marginal evidence:
    high-win-rate, non-negative, sub-practical-delta screening evidence is a
    diagnostic validation candidate (`SCREENING_PASS_MARGINAL_DELTA`) and is
    recorded in proposal feedback/search memory as marginal rather than
    promotable, while high-win-rate negative median effect remains
    inconclusive/fail-closed.
  - Runtime telemetry summaries distinguish explicit inactive activation
    evidence from numeric zero counters. `candidate_false` and activation
    status `inactive` keep delegated review and proposal feedback from
    confusing a non-triggered mechanism with a no-effect mechanism or
    zero/sub-ms runtime budget evidence.
  - Code-phase prompts preserve target/integration/algorithm source visibility;
    `context.read_algorithm_file`, `context.read_algorithm_symbol`, and
    `context.read_surface` can carry the current 96k source window without
    registry result-cap rejection, shallow-preview symbol misses, code-prompt
    projection shrinkage, symbol-read receipt-only visibility, or unstable
    retry-block placement. Non-solver/operator code prompts also retain
    cacheable active algorithm facts in the stable system block; current-run
    postrun readiness audits prompt/source visibility, branch state, champion
    progress, failure taxonomy, research-context actionability, signal density,
    runtime drain readiness, and interpretation-specific review inputs.
    Hypothesis prompts render cross-branch maps and branch-lesson context as
    mechanism-level distilled signals with lesson ids, signatures, maturity,
    evidence counts/statuses, and explicit `omitted_*`/digest audit markers
    instead of default-visible raw long lesson prose, raw rows, or large
    branch/case enumerations.
  - Warehouse positive-at-or-above-MDE evidence routes to
    `protocol_evaluated_positive_effect_review_ready`; plateau conclusions
    require plateau-consistent measurement, review-ready runtime feedback, and
    substantive continuity evidence without fully missed same-mechanism
    follow-up opportunities. Quality-blocked no-protocol negative conclusions
    require matching current-run failure-taxonomy evidence.
  - CVRP bounded two-opt review readiness requires a qualifying bounded or
    deadline-aware large two-opt protocol-effect signal plus co-located
    activation/effect/intra-large-two-opt phase telemetry on a matching top
    effect row; seed-only guidance labels, generic/intra-only two-opt-like
    labels, `two_opt_star`/cross-route phases, VNS, unbounded, fallback,
    `size70_two_opt_*` fallback telemetry, unrelated mechanism evidence, and
    continuity-only mentions are not sufficient. Ready summaries must also
    match recomputed direct-evidence counters, mechanism-family lists,
    rejection counts, and top-row signal count from the current
    measurement/continuity inputs.
  - Current-run warehouse/CVRP problem summaries must carry an explicit
    `evidence` payload before delegated review can accept protocol-evaluated,
    plateau, positive-effect, or bounded two-opt conclusions; free-text summary
    claims alone remain insufficient evidence. Their `current_run_evidence`
    flag must also match the analysis brief lifecycle and Phase 4 current-run
    evidence state.
  - Protocol-evaluated warehouse/CVRP problem summaries must match current
    protocol-accounting detail: formal-screened candidates, protocol metric
    rows, formal candidate artifact rows, and stage-row distribution.
  - Current-run warehouse/CVRP measurement evidence must match current
    measurement-effect interpretation counts and `max_effect_to_mde_ratio`; CVRP
    bounded two-opt ready summaries must also match current mechanism-family
    mapped/unmapped row counts.
  - Current-run warehouse/CVRP problem-summary runtime evidence must match
    runtime-feedback raw availability, drain/review readiness, runtime model
    counts, and runtime budget diagnostic counts before delegated review can
    accept the summary as current-run analysis evidence.
  - Current-run warehouse/CVRP problem-summary `interpretation`,
    `evidence_gaps`, `review_axes_actionability`, and launch-required flags
    must match the recomputed problem-specific summary from current
    review-input summaries. Readiness rejects stale or overly optimistic
    delegated-review conclusions even when an omitted gap would otherwise be
    nonblocking.
  - Quality-blocked no-protocol warehouse/CVRP conclusions must match the
    current failure-taxonomy quality-block counts, reports-with-quality-blocks,
    and reason-count distribution; matching only the aggregate blocked count is
    insufficient evidence.
  - Current-run warehouse/CVRP failure-taxonomy summaries must be recomputable
    from the current research-efficiency reports, including aggregate failure
    counts, proposal-quality counts, run-status counts, entries, and top
    examples; entry paths must match current artifact identity through a
    local/WSL-safe path-tail signature. A shape-correct but stale taxonomy
    summary is not delegated-review evidence.
  - Current-run warehouse/CVRP review-input summaries must be current-run when
    required by the interpretation or when present in the brief, so optional
    measurement/runtime/continuity summaries cannot carry stale report-only
    material or stale entry path identity into delegated review.
  - Current-run warehouse/CVRP research-context actionability must be a fresh
    projection of prompt visibility and research-continuity inputs; stale
    prompt token, continuity, gap, recommendation, or prompt-context entry-path
    projections fail postrun readiness before delegated review.
    Human-readable postrun briefs must expose missed same-mechanism follow-up
    directly in continuity/actionability and problem-specific review summaries,
    so plateau or bounded two-opt review cannot depend on a reviewer manually
    subtracting selected from observed opportunities.
  - Agentic proposal recovery can reuse a persisted
    `partial_hypothesis_only` / `hypothesis_awaiting_approval` artifact for the
    same branch and code-phase idempotency key, avoiding duplicate hypothesis
    LLM calls after restart while still rerunning normal anchor, problem
    quality, follow-up, lineage, and ContractGate approval checks. Persisted
    pre-approval patches are never restored.
  - Current-run warehouse/CVRP research-context readiness requires a formal
    hypothesis-generation prompt trace. Code-only prompt manifests and
    target-intent prompts cannot prove that branch-depth, continuity, or
    cross-branch research signals reached the next proposal prompt. When
    current continuity signals exist, readiness now also requires the formal
    hypothesis-generation trace itself, not only aggregate prompt manifests, to
    carry research or cross-branch lesson signal. Formal trace accounting is an
    explicit allowlist of hypothesis generation and retry prompt call kinds;
    unknown `hypothesis_*` labels cannot bypass this requirement.
  - Prepared prompt-context readiness now checks the deterministic
    `research_focus` projection path and required nested projected paths, so
    problem-owned launch guidance such as CVRP CMT2/CMT4 protected cases,
    rules, and required evidence cannot pass only as manifest/report data while
    being absent from proposal prompt focus. It also renders the compact
    hypothesis prompt summary in memory and stores only safe boolean/count/path
    evidence, proving warehouse renders 33 required `research_focus` paths and
    CVRP renders 50 required paths with `missing_rendered_paths=[]`.
  - CVRP prepared-run contract checks the same protected cases against the
    configured split manifest's formal screening set; the current root reports
    CMT2 and CMT4 in `screening`, preventing prompt-only CMT2/CMT4 protection
    from becoming a false-ready launch state.
  - Launch readiness guards the active checkout, absolute WSL `SCION_DIR` /
    `PYTHONPATH`, prepared-handoff identity, completion preflight, model route,
    private `launch.env` permissions, campaign-execution marker placement after
    completion-preflight failure handling with top-level marker status/failure
    evidence, no-early-stop semantics, strict postrun rebuild/readiness,
    committed runtime-guard drift, and wrapper/manifest runtime-guard contract
    consistency.
  - Launcher wrappers now promote strict postrun rebuild/readiness failure to
    an effective wrapper failure and annotate top-level `run_status.json`, so a
    campaign that finishes but lacks current-run-ready postrun acceptance cannot
    look like a successful analysis-ready launch.
  - Postrun inventory fails closed when root launcher `run_status.json` is
    missing or unreadable, or when launcher status exists but campaign execution
    `run_status.json`/`status.json`/`campaign_summary.json` artifacts are all
    missing or unreadable: copied or partial campaign artifacts remain resume
    snapshots, lifecycle/Phase 4 current-run evidence is false, and the run is
    marked invalid infra-only before delegated review can treat it as research
    evidence. Launch wrappers write a current campaign-execution marker after
    pre-campaign checks, and launch readiness rejects wrappers that omit that
    marker, place it before completion-preflight failure handling can exit, or
    place it after the campaign command. When the marker exists, stale copied
    resume-campaign documents older than the marker are rejected as
    `campaign_execution_artifacts_stale_resume_snapshot`. Postrun rebuild
    consumes the same lifecycle source and skips
    current-run summary, failure, research-efficiency, and manifest report
    families whenever current-run evidence is false.
  - Current-run postrun readiness also fails closed on missing or nonzero root
    wrapper exit status, nonzero campaign wrapper exit status, top-level
    postrun acceptance failure markers, and nonzero postrun readiness/report
    exit status before delegated review. It also rejects launcher status-writer
    failure markers in `run.log`, postrun acceptance/readiness/report failure
    markers in `exit.txt`, and effective wrapper-exit markers in `exit.txt`, so
    a failed or interrupted status annotation cannot leave a stale clean
    `run_status.json` looking review-ready.
- Current operational truth lives in `scion/docs/status/current-state.md`.
  Detailed repair evidence lives in `scion/docs/experiments/v0.4/`; do not read
  historical experiment reports by default unless the current task explicitly
  needs one.

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
- `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`

`scion/docs/status/v0.4-history.md` is a sparse milestone index; update it only
when the milestone interpretation changes, not for ordinary current-root refreshes.

## Git Hygiene

- Keep commits sliced by phase or repair surface.
- Do not mix experiment reports, framework repairs, and unrelated cleanup in one
  commit unless explicitly accepted.
- Do not revert user or subagent changes unless explicitly instructed.
- Before each commit, record tests and experiment artifacts used for acceptance.
