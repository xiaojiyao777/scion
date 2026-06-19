# Scion v0.4 Evidence Repair Task

*Branch: `codex/v04-evidence-repair-plan`*
*Status: v0.4 framework/reporting/launcher repairs are accepted enough for focused warehouse and CVRP follow-up. Current WSL prepared roots were regenerated from runtime commit `865e0fb` and are static-ready, including problem-specific handoff, active-subject source constraints, no-early-stop launch semantics, strict postrun acceptance, review-input consistency, report-only review-surface boundary markers, report-only branch-research-state readiness/input consistency, and report-only champion-progress postrun auditing/input consistency. Launch remains blocked by external WSL `gpt-5.5` provider auth, not Scion static readiness.*
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

Current-status docs to update when operating truth changes:

- `scion/docs/status/current-state.md`
- `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`
- `scion/TASK.md`

Update `scion/docs/status/v0.4-history.md` only for sparse milestone changes,
not for every prepared root, wrapper failure, or repair-detail checkpoint.

Current checkpoint:

- Warehouse is the accepted v0.4 positive research-path checkpoint. Champion
  `v2` promoted in the validation-transfer rerun; the open question is whether
  Scion can produce additional useful research from `v2` or correctly diagnose a
  real post-v2 plateau.
- CVRP/VRP continuation is repaired enough for a focused solver-design follow-up:
  the current prepared root carries the large-instance intra-route two-opt seed
  only as proposal guidance, requires deadline-aware bounded implementation, and
  keeps the unbounded fallback as default-avoid. CVRP and warehouse
  code-generation prompts now receive provider-owned active subject code
  constraints, and launch readiness checks the family-specific code-constraint
  prompt bridge before static readiness can pass. Current-run postrun analysis
  can audit whether actual code prompt traces carried that constraints section,
  using section status, digest, and count fingerprints rather than raw prompt
  text; CVRP and warehouse delegated-analysis readiness now require that trace
  to be present and full-visible whenever a matching code trace exists. Code
  traces also require protected target/integration/algorithm source visibility;
  missing required source paths and partial required hypothesis target-source
  visibility prevent delegated current-run review readiness. CVRP bounded
  two-opt review readiness now rejects generic, cross-route,
  unbounded/fallback, VNS, and two-opt-star protocol family labels as
  two-opt-like but non-qualifying signals, and requires direct
  activation/effect/phase telemetry co-located on the same matching top effect
  row before calling the follow-up `bounded_twoopt_review_ready`.
- Protocol-evaluated CVRP/warehouse postrun review requires runtime feedback to
  be review-ready: runtime budget diagnostics remain reportable, but
  fresh-runtime replay drain status and stage-transition drain status must both
  be present before runtime evidence can support delegated conclusions.
- Postrun acceptance readiness rejects stale problem-specific summary contracts:
  `warehouse_followup_summary` and `cvrp_large_twoopt_summary` must use their
  current schema, match the prepared problem family, and use a current
  delegated-review interpretation while remaining report-only,
  non-quality-judgment, and `DecisionFeatures`-excluded before a current run
  can be called analysis-ready.
- Launch readiness applies the same boundary to prepared-only analysis briefs:
  the matching warehouse/CVRP prepared summary must be present, use the current
  schema, and remain report-only, non-quality-judgment, and
  `DecisionFeatures`-excluded before a prepared root can be static-ready.
- Postrun acceptance readiness now validates every output declared by
  `postrun_acceptance/rebuild/rebuild_manifest.v1.json`; stale directory
  counts or lexically later replacement files cannot make current-run delegated
  review ready when a manifest-declared artifact is missing.
- Postrun acceptance readiness now also requires current-run
  `research_context_actionability_summary`, prompt block-family accounting, and
  prompt signal-density token accounting for warehouse/CVRP delegated review.
  This makes branch-transfer and same-mechanism gaps auditable without turning
  research-context quality into Decision or promotion input.
- Postrun acceptance readiness now also requires current-run
  `failure_taxonomy_summary` evidence for warehouse/CVRP delegated review.
  Missing, stale, non-current, or empty failure taxonomy no longer allows a
  hand-written problem summary to make a run analysis-ready.
- Postrun acceptance readiness now also requires prompt/source visibility,
  research-context, signal-density, and failure-taxonomy review surfaces to
  preserve current schemas, report-only/non-quality-judgment boundary markers
  where applicable, `DecisionFeatures` exclusion, and raw prompt/response/patch
  body/log exclusions. Hand-written review surfaces can no longer provide
  plausible counts while bypassing the v3 tainted-material boundary.
- Postrun acceptance readiness now also requires current-run protocol
  accounting, measurement-effect, runtime-feedback, and research-continuity
  summaries for warehouse/CVRP delegated review. A hand-written
  problem-specific summary can no longer bypass missing review-input summaries,
  those summaries must preserve report-only, non-quality-judgment,
  `DecisionFeatures`-excluded boundary markers, and runtime feedback must still
  be review-ready with drain status complete.
- Postrun acceptance readiness now also requires current-run
  `branch_research_state_summary` actionability for warehouse/CVRP delegated
  review. The summary is report-only, excludes raw prompts/responses/patch
  bodies, and makes branch/hypothesis/event/trace coverage auditable without
  requiring a positive result or changing Decision/Protocol/promotion state.
  It is recomputed from current-run inventory before readiness accepts it, so a
  hand-written or stale branch summary cannot disagree with branch, hypothesis,
  event, session, or trace counts.
- Postrun acceptance readiness also recomputes current-run
  `champion_progress_summary` from inventory before accepting it, so a stale or
  hand-written champion-progress summary cannot claim champion advancement,
  version counts, or promotion signals that the current-run champion table and
  event/hypothesis evidence do not support.
- Postrun acceptance readiness also cross-checks the problem-specific summary's
  protocol, measurement, runtime, continuity, and quality-block evidence against
  those input summaries. A stale or hand-written problem summary can no longer
  claim a protocol-evaluated conclusion when the input summaries disagree.
- Current WSL prepared roots:
  - Warehouse:
    `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-boundarymarkers-865e0fb-6r-gpt55-20260619T125317Z-claw`
  - CVRP:
    `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-boundarymarkers-865e0fb-1r-gpt55-20260619T125317Z-claw`
- Strict launch readiness for both current roots reports `static_ready=true`,
  `launch_ready=false`, `prepared_analysis_brief_current=ok`,
  `prompt_context_readiness_complete=ok`,
  `problem_specific_prepared_handoff=ok`, `postrun_families_complete=ok`,
  `run_script_strict_postrun_readiness=ok`,
  `run_script_runtime_guard_enforced=ok`,
  `run_script_postrun_reports_after_campaign=ok`, `git_runtime_consistent=ok`,
  `run_script_data_root_failure_reports=ok`,
  `run_script_api_key_env_failure_reports=ok`,
  `run_script_model_route_enforced=ok`,
  `run_script_pythonpath_enforced=ok`,
  `run_script_completion_preflight_enforced=ok`,
  `run_script_preflight_failure_reports=ok`,
  `run_script_no_early_stop_enforced=ok`, prepared contract
  `execution.disable_early_stop=true` and `command_disable_early_stop=true`,
  and runtime guard coverage for
  `scion/tools`, `scion/scion/cli`, `scion/scion/core`, `scion/scion/lineage`,
  and the matching CVRP/warehouse problem package/assets/data paths. The
  warehouse root reports
  `warehouse_active_subject_code_constraint_source_markers` all true, and the
  CVRP root reports `cvrp_active_subject_code_constraint_source_markers` all
  true. The roots were prepared from WSL runtime commit `865e0fb`. Current
  readiness also verifies executable `launch.env` sourcing, executable
  completion preflight, GPT-5.5 model/base routing, active-checkout
  `PYTHONPATH`, no-early-stop launch semantics, executable pre-campaign failure
  reporting, strict postrun readiness, runtime guard command markers, normal
  campaign-exit postrun reporting, postrun review-surface boundary markers,
  co-located CVRP two-opt direct evidence, and warehouse/CVRP problem-summary
  consistency recomputed from review inputs.
- The blocker is external WSL `gpt-5.5` provider auth, not Scion static
  readiness. With `SCION_API_KEY=pwd`, `/v1/models` lists `gpt-5.5` but real
  `/v1/chat/completions` preflight returns HTTP `401`,
  `classification=not_authenticated`, `code=invalid_api_key`. Latest strict
  launch-readiness preflight reports auth pool `active=0`, `refreshing=1`,
  `total=1`, and no launch-usable account. Do not launch either root until
  `scion/tools/check_launch_readiness.py <prepared-root> --require-launch-ready --format json`
  reports `launch_ready=true`.
- Current postrun/delegated-review boundary: postrun readiness is report-only and
  requires the matching warehouse/CVRP problem-specific summary before a current
  run can be called `current_run_analysis_ready=true`; launchers propagate that
  readiness result into `POSTRUN_READINESS_EXIT_STATUS`, and launch readiness
  rejects prepared scripts that omit the strict marker path. It also binds the
  selected analysis brief to the rebuild manifest and checks run identity, so
  stale or lexically later brief artifacts cannot make delegated review ready.
  It also requires manifest-declared family outputs to still exist, so stale
  directory contents cannot mask a missing report artifact. For warehouse/CVRP
  current runs it additionally requires research-context actionability, prompt
  signal-density accounting, failure-taxonomy evidence, and review-input
  summaries to be present, report-only/`DecisionFeatures`-excluded, and
  internally consistent with the problem summary, while allowing valid
  review-required gaps as delegated-analysis evidence.
  CVRP bounded
  two-opt review readiness also requires a qualifying large/two-opt
  protocol-effect row signal in measurement evidence plus direct
  activation/effect/phase telemetry co-located on a matching top effect row;
  postrun acceptance recomputes that signal from review inputs before accepting
  `bounded_twoopt_review_ready`. Continuity-only family mentions remain context,
  and generic/default-avoid two-opt-like labels are explicitly rejected, not
  mechanism-effect evidence.
  This does not change
  Decision, `DecisionFeatures`, Protocol gates, promotion, scheduler state, or
  solver behavior.
- Current proposal-diagnostic boundary: adapter-owned measurement/opportunity
  diagnostics are redacted before prompt exposure for raw pair/calibration rows,
  BKS/gap details, holdout/case details, prompt ratios, and LLM text; the
  remaining payload stays tainted proposal context and does not enter
  `DecisionFeatures`.
- Current launch/runtime boundary: prepared roots must guard `scion/tools`,
  postrun/report package paths, and matching problem runtime paths as
  runtime/control-plane code, so launcher, postrun rebuild, postrun readiness,
  research-efficiency report, trajectory manifest, problem provider, problem
  asset, baseline data, and launch-readiness changes after prepare time require
  a new prepared root.
  Launch readiness also rejects a prepared root whose `run.sh` declares the
  guard contract but does not execute dirty/head-mismatch checks before
  `scion.cli.main run`, or whose normal campaign-exit path skips the postrun
  report/readiness bundle before exiting with campaign status. Warehouse roots
  also fail readiness if their data-root-missing pre-campaign failure path skips
  the postrun report/readiness bundle. Warehouse and CVRP roots also fail
  readiness if the API-key-env-missing pre-campaign failure path skips the same
  report/readiness bundle. Both warehouse and CVRP roots also fail readiness if
  generated `launch.env` disables completion preflight or generated `run.sh`
  does not run `tools/check_gpt55_proxy.py` before the real campaign command, or
  if generated `launch.env/run.sh` do not export the active Scion checkout on
  `PYTHONPATH` before campaign start, or if manifest and launch-env model route
  diverge from `gpt-5.5`, or if launch-env/manifest/run-script no-early-stop
  semantics are missing.
  Older prepared roots before the postrunexec roots above are not current
  because launch/readiness runtime paths changed after prepare time. Exact
  supersession details belong in the
  launch/readiness evidence docs, not in this current checkpoint.
- Current warehouse delegated-review boundary: plateau-review readiness requires
  protocol-evaluated current-run evidence plus measurement-effect,
  runtime-feedback, and substantive realized research-continuity signals. A
  shallow continuity block or unrealized continuity opportunity alone cannot
  distinguish a real post-v2 plateau from missed continuous-optimization
  opportunity. Postrun acceptance recomputes the warehouse continuity signal
  from `research_continuity_summary` before accepting
  `protocol_evaluated_plateau_review_ready`.
- Current postrun readiness boundary: blocking problem-summary gaps such as
  missing review inputs, incomplete handoff, launch-only or infra-only status,
  and no protocol evidence prevent `current_run_analysis_ready=true`; valid
  negative conclusions remain analysis-ready. Warehouse/CVRP readiness also
  requires current-run prompt/source visibility trace accounting, including
  hypothesis target-source visibility, in the analysis brief, so delegated
  review can audit branch transfer and source grounding instead of inferring
  them from final status.
- Current launch/readiness evidence:
  `scion/docs/experiments/v0.4/v04-launch-readiness-run-script-no-early-stop-20260619.md`.
  Earlier run-script guard details remain in `scion/docs/experiments/v0.4/`;
  they are not the current prepared-root pointer.
- Current operational truth lives in `scion/docs/status/current-state.md`.
  Historical repair details live in `scion/docs/status/v0.4-history.md` and
  `scion/docs/experiments/v0.4/`; do not read historical experiment reports by
  default unless the current task explicitly needs one.
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
- `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`

`scion/docs/status/v0.4-history.md` is a sparse milestone index; update it only
when the milestone interpretation changes, not for ordinary current-root refreshes.

## Git Hygiene

- Keep commits sliced by phase or repair surface.
- Do not mix experiment reports, framework repairs, and unrelated cleanup in one
  commit unless explicitly accepted.
- Do not revert user or subagent changes unless explicitly instructed.
- Before each commit, record tests and experiment artifacts used for acceptance.
