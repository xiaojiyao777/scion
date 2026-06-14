# Scion v0.4 Evidence Repair Task

*Branch: `codex/v04-evidence-repair-plan`*
*Status: CVRP baseline-strength Phase B audited; staged CVRP gate repair and long-run design next*
*Updated: 2026-06-14*

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

- Use the local `gpt5.5` model for Scion runs that involve LLM proposal,
  diagnosis, or code-generation calls.
- Treat copied configs, protocol/split/seed hashes, champion versions,
  workspace commits, and run directories as required evidence.
- When runtime caps are size-dependent in the formal protocol, experiment
  reports must say whether a run used the formal policy or a conservative
  approximation such as a uniform time limit.
- Do not treat aggregate win rate as sufficient evidence. Pair-level deltas,
  per-case behavior, seed/RNG sensitivity, runtime events, and branch trajectory
  must be inspected for experiments whose purpose depends on them.

## Required Reading

Every main-thread phase and every new subagent brief must start with the v3
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

## Current Status

- Completed: CVRP baseline-strength Phase A no-LLM characterization is accepted.
  Report:
  `scion/docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseA-20260613.md`.
  Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw`.
  The full wrapper finished at `2026-06-14T02:24:47Z` with all three stages
  exiting `0`. ALNS+VNS A/A produced `n_pairs=192`, MDE `9.6`, false-pass
  `0.0`, and `recommended_min_seeds=16`; ALNS-only A/A produced
  `n_pairs=192`, MDE `4.65`, false-pass `0.0`, and
  `recommended_min_seeds=8`. Paired characterization showed ALNS-only as a
  weaker but more measurable research surface: contrast W/L/T `7/56/1`,
  median signed delta `-20.0`, mean signed delta `-65.25`, median runtime ratio
  `0.9883`, and mean BKS gap `6.50%` versus `4.20%` for ALNS+VNS. VNS telemetry
  matched the construction (`64/64` control pairs had VNS, `0/64` contrast
  pairs had VNS). Phase B is allowed only as a pre-registered matched
  research-surface campaign; ALNS-only is not a canonical baseline replacement
  and no VNS/BKS/baseline-strength diagnostic enters `DecisionFeatures`.
- Implemented: problem-owned `measurement` schema, protocol practical-delta
  resolution, runtime model resolution, budget-exhausting runtime governance,
  V9 budget-compliance semantics, read-only branch research-shape diagnostics,
  prompt block-family accounting, compact research signals, and
  `scion/tools/calibrate_aa_noise.py`.
- Implemented during Phase 2 framework repair: protocol config now resolves
  deterministic `pairing_validity` from problem-owned measurement declarations;
  screening gates and Decision can expand tie-heavy or weak non-negative
  low-SNR evidence below `0.5` aggregate win rate only for
  `trajectory_divergent` problems; trajectory-stable warehouse behavior remains
  unchanged; hard negatives, candidate failures, runtime guard failures, and
  true runtime regressions still fail closed. Lifecycle thresholds are relaxed
  only for trajectory-divergent low-SNR research so same-mechanism follow-up can
  continue beyond shallow one-off attempts.
- Implemented during Phase 2 context/source repair: proposal context now exposes
  tainted, problem-owned measurement/noise/opportunity diagnostics as research
  signal, filters raw calibration rows, validation/frozen detail, BKS/gap
  detail, LLM text, prompt ratios, and raw cross-branch material, and records
  code-phase source visibility guarantees proving target and required
  integration source survived compression.
- Implemented during Phase 1 prerequisite repair: A/A artifacts now include
  replayable pair evidence, selected cases/seeds, replicate count, seed offset,
  bootstrap samples, selected surface, safe data roots, case resolution,
  elapsed runtime, and explicit runtime-policy metadata. The calibration CLI can
  wire declared problem data roots and can run either uniform time limits or
  protocol-resolved per-case time limits.
- Completed: Phase 1 A/A calibration. Warehouse create/modify screening
  calibrations finished with wrapper exit 0. The first CVRP safe-root `tl30`
  run failed on `M/M-n200-k17.vrp` timeout and is diagnostic only. The
  corrected uniform-60s CVRP legacy run finished at `2026-06-11T20:34:59Z`
  with `n_pairs=96`, `mde_at_power_80=8.7` raw `total_distance`, and
  `false_pass_rate_at_current_gate=0.0`, but it lacks Worker F pair/runtime
  evidence and is not a formal per-case-runtime reproduction. The repaired
  formal protocol-time CVRP run finished at `2026-06-11T22:03:18Z` with
  `n_pairs=96`, `mde_at_power_80=9.9` raw `total_distance`,
  `false_pass_rate_at_current_gate=0.0`, complete pair evidence, and
  protocol-resolved time limits. Read-only subagent cross-check accepted that
  Phase 0 CVRP candidates were below measured screening power, not disproven by
  failed screening outcomes. The Phase 1 report is
  `scion/docs/experiments/v0.4/v04-phase1-aa-calibration-20260611.md`.
- Verified Phase 2 focused suite:
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest scion/scion/tests/test_config.py scion/scion/tests/test_problem_bridge.py scion/scion/tests/test_problem_adapter.py scion/scion/tests/test_cli_run_options.py scion/scion/tests/test_protocol_stats_gates.py scion/scion/tests/test_decision_screening.py scion/scion/tests/unit/core/test_branch_lifecycle_policy.py scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py scion/scion/tests/unit/core/test_runtime_budget_diagnostics.py scion/scion/tests/test_verification_gate_integration.py scion/scion/tests/unit/test_runtime_feedback_guidance.py scion/scion/tests/unit/test_hypothesis_context_profiles.py scion/scion/tests/unit/test_prompt_manifest_accounting.py scion/scion/tests/unit/test_cross_branch_research.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py scion/scion/tests/unit/test_agentic_target_file_grounding.py scion/scion/tests/unit/test_agentic_session_tool_selection.py`
  passed with `311 passed`. Additional v3 boundary check
  `test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py` passed after
  removing a legacy generic-core `vns` hardcode from mechanism-signature
  grouping.
- Completed: Phase 0 postrun baseline for the paired 2026-06-11 CVRP and
  warehouse 4R verification runs is captured in
  `scion/docs/experiments/v0.4/v04-evidence-verify-4r-gpt55-20260611-phase0-postrun.md`.
  CVRP finished `4/4` screening-only rounds; warehouse finished `4/4` with a
  full promotion path to champion v2.
- Completed: Phase 3 minimal measurement readiness consumption. The
  problem-owned measurement schema now includes optional reduced readiness
  summary fields, `measurement_readiness_status()` resolves `calibration_ref`
  and reports missing, unreadable, incompatible, incomplete, stale, and ready
  states, and `ProtocolConfig.measurement_readiness` carries only deterministic
  enum/numeric status. Compact Phase 1 A/A artifacts are installed at
  `scion/scion/problems/cvrp/formal/calibration/aa_noise_floor.json` and
  `surrogate/calibration/aa_noise_floor.json`; warehouse package and legacy
  specs point to the latter through `calibration/aa_noise_floor.json`.
  As of 2026-06-11, CVRP readiness is `ready` with MDE `9.9`,
  effect-to-MDE ratio `0.202`, and signal tier `low_power`; warehouse readiness
  is `ready` with MDE `577.5`, effect-to-MDE ratio about `1.7e-6`, and signal
  tier `low_power`. Raw A/A pair evidence remains outside
  `DecisionFeatures`.
- Completed through first-rung Phase 4 focused validation. Short CVRP and
  warehouse campaigns have been run and audited with local `gpt5.5`; evidence
  is now interpreted against A/A MDE/readiness rather than only promotion or
  aggregate win rate.
- Launched: Phase 4 first-rung 4R focused validation runs from commit
  `32ab596` using local `gpt5.5`.
  CVRP formal run:
  `/home/clawd/research/scion-experiments/v04-phase4-focused-cvrp-measreadiness-20260611-4r-gpt55-20260611T224916Z-claw`
  with PID `1753912`, formal CVRPLIB split, protocol time rules, and
  `--time-limit-sec 30`. Warehouse run:
  `/home/clawd/research/scion-experiments/v04-phase4-focused-warehouse-measreadiness-20260611-4r-gpt55-20260611T225004Z-claw`
  with Python PID `1754001`, production protocol/split/seeds, and
  `--time-limit-sec 30`. Both runs use `--disable-early-stop` and
  `--agentic-proposal`.
- Warehouse result: invalid for Phase 4 validation. The wrapper exited 0 and
  consumed four candidate attempts, but all four were abandoned with
  `CANARY_FAILED` before screening protocol rows were produced:
  `screening_protocol_results=0`, `effective_protocol_rounds=0`, no formal
  candidate index, and missing protocol `raw_metrics_ref`. Treat this as a
  canary evidence/accounting repair finding, not as warehouse research
  evidence.
- Accepted: Worker H's generic canary evidence/accounting repair in the canary
  accounting repair commit. Canary-vetoed candidates now persist structured
  `canary_result` details, do not backfill formal/protocol row counters, keep old
  loop-reported values under `legacy_*_reported`, and mark terminal
  consumed-attempt/no-protocol-row runs as `invalid_no_protocol_rows`.
  Acceptance: full core unit suite `489 passed`, protocol/canary focused suite
  `31 passed`, and `git diff --check`.
- Next: rerun warehouse Phase 4 from the repair commit. The current CVRP Phase 4
  run was launched from `32ab596` and remains valid for its own run environment,
  but it does not exercise this later accounting fix.
- Verified: warehouse accounting rerun from repair commit `a6a34d6` completed at
  `/home/clawd/research/scion-experiments/v04-phase4-focused-warehouse-canaryfix-foreground-20260611-4r-gpt55-20260611T234843Z-claw`
  with wrapper exit 0, four consumed attempts, zero experiments, and correct
  no-protocol-row accounting:
  `formal_screened_candidates=0`, `protocol_evaluated_candidates=0`,
  `effective_protocol_rounds=0`, `screening_protocol_results=0`,
  `protocol_metric_results=0`, and
  `run_validity.reason=invalid_no_protocol_rows`. The run is not warehouse
  research evidence; it exposes the next blocker, a warehouse production canary
  safe-root failure on
  `artifact:instance_prod_can_s01.json#64a747f955e8`
  (`absolute_outside_roots`).
- Accepted: Curie's warehouse safe-root repair. The production split declares
  `safe_data_roots: ../../../../scion-data`, so production canary paths resolve
  through problem-owned safe roots under strict protocol. Acceptance: focused
  protocol/CLI/e2e subset `12 passed` and `git diff --check`.
- Completed: warehouse safe-root Phase 4 rerun from commit `63f01d7` at
  `/home/clawd/research/scion-experiments/v04-phase4-focused-warehouse-saferoot-20260611-4r-gpt55-20260612T000035Z-claw`.
  It finished valid with wrapper exit 0, `effective_protocol_rounds=4`,
  `formal_screened_candidates=4`, `protocol_evaluated_candidates=4`,
  `screening_protocol_results=5`, `protocol_metric_results=5`,
  `validation_protocol_results=0`, `frozen_protocol_results=0`, and champion
  v1. The fifth screening row is non-counted fresh-runtime replay evidence;
  candidate reconciliation reports four formal candidate artifacts. No
  promotion occurred.
- Completed: warehouse Phase 4 postrun audit at
  `scion/docs/experiments/v0.4/v04-phase4-warehouse-saferoot-4r-postrun-20260612.md`.
  It accepts the run as valid no-promotion evidence: count reconciliation is
  healthy, v3 boundaries held, prompt/source visibility looked adequate, and no
  candidate cleared warehouse A/A readiness. Candidate 1 was weak mixed signal
  below MDE, candidates 2/3 were zero-effect same-mechanism follow-ups, and the
  clean fork was negative. Fresh-runtime replay should stay out-of-band for
  Phase 5 accounting/design.
- Completed: CVRP first-rung Phase 4 run from commit `32ab596` at
  `/home/clawd/research/scion-experiments/v04-phase4-focused-cvrp-measreadiness-20260611-4r-gpt55-20260611T224916Z-claw`.
  It finished valid with wrapper exit 0, `effective_protocol_rounds=4`,
  `formal_screened_candidates=4`, `screening_protocol_results=4`,
  `protocol_metric_results=4`, `validation_protocol_results=0`,
  `frozen_protocol_results=0`, and champion v1. Decisions:
  `expand_screening`, `continue_explore`, `expand_screening`, `abandon`. No
  promotion occurred.
- Completed: CVRP Phase 4 postrun audit at
  `scion/docs/experiments/v0.4/v04-phase4-cvrp-measreadiness-4r-postrun-20260612.md`.
  It accepts the run as valid screening-only Phase 4 evidence: launch config,
  copied formal config, A/A calibration, replayable patch artifacts, protocol
  metrics, verification records, and deterministic decisions reconcile. Runtime
  semantics are materially healthier for budget-exhausting CVRP: no fresh
  runtime replay drain, no runtime-only promotion leakage, and saturation is
  info rather than a gate veto. Branch mechanics improved enough that both
  mechanisms received same-mechanism expansion under a 4R budget; the strongest
  research signal was `double_bridge_relink_vns`, which moved from `17/9/6`
  pair evidence initially to `22/19/7` after expansion, with stable positive
  clusters on `A-n64-k9`, `A-n80-k10`, `M-n151-k12`, and `X-n110-k13`.
- Phase 4 closeout decision: the repaired v0.4 evidence path is auditable, and
  agents can now generate real CVRP/warehouse research attempts with healthier
  runtime/context/branch mechanics. However, CVRP quality-improvement evidence
  remains underpowered under the current 4-seed screening protocol: final
  `double_bridge_relink_vns` median was `-1.25`, CI `[-5.75, 7.25]`, and high
  CI remained below the Phase 1 CVRP MDE `9.9`. Do not start a long CVRP
  promotion campaign or use CVRP as the first governance-value ablation without
  an 8-seed or otherwise power-adjusted measurement configuration check.
- Next: design the Phase 4 closeout follow-up. Main thread should define the
  CVRP power-adjusted screening check, decide whether warehouse or another
  effect-measurable problem is the first governance on/off candidate, and brief
  subagents for concrete experiment design/analysis. Governance on/off should
  begin only after the comparison would measure governance value rather than
  unresolved measurement power.
- Completed: two read-only next-rung design passes. Schrodinger designed the
  CVRP power check: start with an 8-case x 8-seed x 3-replicate A/A calibration
  using temporary run-root protocol/seed/split copies, protocol-resolved runtime
  limits, and no LLM calls. Lovelace accepted warehouse production saferoot as
  the first governance on/off candidate, while CVRP remains blocked from being
  the first governance-value target until the 8-seed/power-adjusted check shows
  usable measurement resolution.
- Completed and audited: CVRP 8-seed A/A power check at
  `/home/clawd/research/scion-experiments/v04-phase4-cvrp-8seed-aa-saferoot-20260612T011824Z-claw`.
  Report:
  `scion/docs/experiments/v0.4/v04-phase4-cvrp-8seed-aa-postrun-20260612.md`.
  It used `8` selected screening cases, screening seeds
  `11,29,43,59,73,79,97,103`, `3` replicates, protocol-time runtime limits,
  champion v1 from the completed Phase 4 CVRP run, and no LLM calls. It
  completed with wrapper exit `0`, `n_pairs=192`, MDE `9.6` raw
  `total_distance`, false-pass rate `0.0`, and `recommended_min_seeds=16`.
  This is only a small improvement over the Phase 1 MDE `9.9` and remains
  `4.8x` above `practical_delta_screen=2.0`, so CVRP is still not ready for a
  formal governance ON/OFF main experiment or long promotion campaign. A prior
  attempt at
  `/home/clawd/research/scion-experiments/v04-phase4-cvrp-8seed-aa-20260612T011722Z-claw`
  failed before solver execution because the temporary protocol copy no longer
  activated the formal data root; the saferoot rerun fixes this by declaring
  `/home/clawd/research/or-autoresearch-agent/vrp` in the run-root split copy.
  Caveat: `CMT4` contains `DIMENSION : 151` but received the default `30s`
  because current dimension resolution appears filename-based; exact
  protocol-time fidelity needs CMT dimension handling repair or
  pre-registration.
- Completed: Ramanujan's minimal `measurement_governance` implementation is
  accepted. `scion run` now exposes `--measurement-governance {on,record-only}`.
  Default ON preserves current measurement-aware protocol/runtime/lifecycle/
  context behavior. Record-only/OFF still records reduced measurement readiness
  but does not copy problem measurement into practical deltas, runtime model, or
  pairing validity, and suppresses prompt-visible measurement diagnostics.
  Main-thread acceptance passed:
  focused config/CLI/context suite `40 passed`, protocol/Decision/lifecycle/
  runtime suite `124 passed`, full `unit/core` suite `489 passed`, problem/
  boundary/context subset `113 passed`, Python compile on touched files, and
  `git diff --check`.
- Completed and audited: first warehouse governance ON/OFF shakedown from
  commit `f604e81`, local `gpt5.5`, production saferoot protocol/split/seeds,
  `--rounds 8`, `--time-limit-sec 30`, `--disable-early-stop`, and
  `--agentic-proposal`. Report:
  `scion/docs/experiments/v0.4/v04-phase5-warehouse-governance-onoff-8r-postrun-20260612.md`.
  ON arm:
  `/home/clawd/research/scion-experiments/v04-phase5-governance-warehouse-on-pilot-8r-gpt55-20260612T013119Z-claw`.
  Record-only/OFF arm:
  `/home/clawd/research/scion-experiments/v04-phase5-governance-warehouse-record_only-pilot-8r-gpt55-20260612T013119Z-claw`.
  Both arms finished valid/complete with `8/8` effective protocol rows,
  `6` screening rows, `1` validation row, `1` frozen row, and champion v2.
  This validates the switch and warehouse evidence path, but it is not a
  causal governance-value result: the LLM trajectories and promoted
  `operators/merge_vehicles.py` patches diverged. Record-only suppresses
  `problem_measurement_diagnostics` but still exposes opportunity/runtime/
  cross-branch/research-governance signals; code-phase source visibility held.
- Accepted before a formal governance experiment: fixed-candidate replay
  manifest construction and explicit measurement-only OFF audit assertions.
  Fixed-order proposal replay is deferred because current APS replay validates
  stored artifacts but does not safely re-execute the same LLM/tool trajectory,
  and scheduler order is dynamic. Fixed-candidate replay is the lower-risk v0.4
  control because it reuses recorded `formal_candidates/index.jsonl` and
  `candidate.patch.json` artifacts, then evaluates identical patches under
  `measurement_governance=on` and `record_only`.
- Accepted after the warehouse shakedown and CVRP 8-seed A/A audit: the first
  post-shakedown framework repair slice now covers the previously identified
  observability and lineage debts. `campaign_summary.json` records
  `measurement_governance`; CLI/status/summary tests assert governance visibility;
  prompt/context tests assert measurement diagnostics suppression and code-phase
  source visibility; CVRP formal protocol explicitly pre-registers `CMT4` for
  the 45s screening budget; expanded-screening borderline advance is an explicit
  protocol policy instead of hidden `0.05` behavior; fresh-runtime replay pressure
  reports "no scheduler-eligible replay candidate" with materialization and
  scheduling block reasons; and durable same-branch hypotheses now record
  `parent_hypothesis_id` without adding that lineage to `DecisionFeatures`.
  Acceptance: targeted repair suite `296 passed`, full `unit/core`
  `494 passed`, protocol/adapter subset `99 passed`, Python compile on touched
  core/config files, and `git diff --check`.
- Active main-thread design decision: v0.4 `record_only` means measurement
  governance OFF, not all governance OFF. It may still expose non-measurement
  objective opportunity, runtime feedback, cross-branch research, branch memory,
  and source visibility. Formal experiment reports must name this scope
  precisely; causal claims require `causal_candidate_pairing=true` from a
  fixed-candidate replay manifest or an equivalent pre-registered control.
- Acceptance for the fixed-candidate/OFF-contract gate: real warehouse shakedown
  artifacts generated fixed-candidate manifests for both source arms (`5`
  candidates, `0` omitted rows each) without leaking code body, prompt text, LLM
  rationale, raw measurement diagnostics, BKS/gap, or raw A/A rows. Tests passed:
  focused replay/OFF-contract/report suite `117 passed`, core+report suite
  `513 passed`, config/model/context/protocol/Decision suite `212 passed`,
  Python compile on touched implementation files, and `git diff --check`.
- Accepted: fixed-candidate replay executor. `scion report
  fixed-candidate-replay` materializes each manifest candidate from its recorded
  `candidate.patch.json`, evaluates the same patch under the manifest arms, and
  writes a posthoc `scion.fixed_candidate_replay_comparison.v1` artifact. The
  executor does not enter the campaign loop, scheduler, Decision, lifecycle, or
  promotion state. Real warehouse smoke:
  `/home/clawd/research/scion-experiments/v04-phase5-fixed-candidate-replay-smoke-warehouse-20260612T0508Z-claw/fixed_candidate_replay_comparison.v1.json`
  replayed one warehouse shakedown candidate under `on` and `record_only` with
  `row_count=2`, `error_count=0`, and no code/prompt/raw-diagnostic/BKS/A/A-row
  leakage. Both rows completed and failed screening with all ties, which is
  acceptable for executor smoke because the gate is replayability and causal
  candidate pairing, not candidate efficacy. Acceptance tests: focused
  replay/report suite `22 passed`, core/config/context regression `592 passed`,
  Python compile on touched implementation files, and `git diff --check`.
- Completed and audited: full warehouse fixed-candidate replay over all five
  ON-shakedown formal screening candidates. Report:
  [`docs/experiments/v0.4/v04-phase5-warehouse-fixed-candidate-replay-postrun-20260612.md`](docs/experiments/v0.4/v04-phase5-warehouse-fixed-candidate-replay-postrun-20260612.md).
  Artifact:
  `/home/clawd/research/scion-experiments/v04-phase5-fixed-candidate-replay-warehouse-5c-20260612T0525Z-claw/fixed_candidate_replay_comparison.v1.json`.
  The run produced `candidate_count=5`, `row_count=10`, `error_count=0`, and no
  forbidden-field leakage. ON and `record_only` outcomes were identical for
  every fixed candidate; four candidates remained all-tie screening failures
  and `f40dd9b672cf6cc2` remained `SCREENING_EXPAND` in both arms. This validates
  fixed-candidate causal pairing and shows that the warehouse shakedown
  divergence was not caused by evaluating the same patch differently. It does
  not prove LLM trajectory governance value. Next governance work should be a
  trajectory-aware prompt/context or stored-proposal control, not another
  fixed-candidate screening replay.
- Accepted: report-only proposal trajectory artifacts. `scion report
  proposal-trajectory-manifest` projects agentic session indexes, trace indexes,
  prompt manifests, and replayable formal-candidate joins into compact
  fingerprints without raw prompts, raw responses, patch bodies, raw metrics, or
  Decision inputs. `scion report proposal-trajectory-compare` compares two such
  manifests and labels the result `observational_only=true` unless a future
  explicit control-pair key exists. Real warehouse ON/OFF artifacts generated
  under
  `/home/clawd/research/scion-experiments/v04-phase5-proposal-trajectory-warehouse-onoff-20260612T0550Z-claw/`:
  report
  [`docs/experiments/v0.4/v04-phase5-warehouse-proposal-trajectory-compare-20260612.md`](docs/experiments/v0.4/v04-phase5-warehouse-proposal-trajectory-compare-20260612.md).
  both arms had `session_count=10`, `trace_count=32`,
  `formal_candidate_count=5`, all `32` prompt manifests loaded, and no forbidden
  field/value leakage. The comparison reproduced the trajectory divergence:
  ON had `9` hypothesis, `18` tool-selection, `5` code traces and mechanisms
  `subcategory_pack_upgrade`, `split_preserving_evacuate`,
  `split_safe_cost_merge`; record-only had `10` hypothesis, `17`
  tool-selection, `5` code traces and mechanisms `subcategory_block_repack`,
  `safe_gap_fill`, `best_of_k_merge`, `compatible_repack_merge`. Acceptance:
  proposal/fixed-candidate/report suite `27 passed`, py_compile on touched
  files, real artifact smoke, exact forbidden-key/value scan, and
  `git diff --check`.
- Accepted: proposal-visible context ablation switch and first warehouse
  three-arm shakedown. `scion run --proposal-context-ablation` supports `full`,
  `no-measurement-diagnostics`, and `minimal-research-context`. All arms keep
  `measurement_governance=on`; the switch only changes tainted hypothesis
  prompt visibility and does not enter Protocol, DecisionFeatures, promotion,
  or evidence decisions. The shakedown report is
  [`docs/experiments/v0.4/v04-phase5-warehouse-proposal-context-ablation-shakedown-20260612.md`](docs/experiments/v0.4/v04-phase5-warehouse-proposal-context-ablation-shakedown-20260612.md).
  It confirmed intended prompt visibility and report-only guardrails, but no
  arm promoted, fresh-runtime replay pressure persisted in the two non-full
  arms, and the initial trajectory report exposed weak attribution. The
  follow-up report repair adds top-level trajectory `context_arm_fingerprint`
  and conservative `branch_code_sequence` formal-candidate attribution,
  validated on the real shakedown artifacts. The fallback assumes branch-local
  code-session order matches formal candidate row order, so direct stable
  linkage remains preferred. CVRP remains excluded from formal governance-value
  conclusions until measurement power improves.
- Completed and accepted as observational Phase 5 evidence: the warehouse
  proposal-context ablation formal repeat from commit `171648c4204d` at
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-context-ablation-formal-3x3-8r-20260612T114219Z-claw`.
  Report:
  [`docs/experiments/v0.4/v04-phase5-warehouse-context-ablation-formal-3x3-20260612.md`](docs/experiments/v0.4/v04-phase5-warehouse-context-ablation-formal-3x3-20260612.md).
  The run used warehouse production protocol/split/seeds, local `gpt-5.5`,
  `measurement_governance=on`, three repeats of `full`,
  `no-measurement-diagnostics`, and `minimal-research-context`, 8 rounds per
  cell, and `--time-limit-sec 30`. All 9 cells exited `0` and were valid
  complete runs; no arm promoted beyond champion v1. Full context produced the
  strongest evidence quality, with the only frozen row and no fresh-runtime
  replay rows. `no-measurement-diagnostics` removed measurement diagnostics
  while preserving other research context and reached one validation row.
  `minimal-research-context` reduced pooled research-signal share to `3.83%`,
  reached no validation/frozen rows, and triggered fresh-runtime replay in all
  three repeats. Generated manifests and compares were report-only,
  non-mutating, free of forbidden raw prompt/response/patch/Decision payload
  leakage, and `observational_only=true`; this is valid context-ablation
  evidence, not a causal governance-value conclusion. Next: design the next
  warehouse governance/context experiment with trajectory-aware control or
  explicit control-pair keys, and do not use `minimal-research-context` as the
  default compression strategy.
- Accepted: explicit report-only `control_pair_key` plumbing for proposal
  trajectory manifests. `scion report proposal-trajectory-manifest` now accepts
  `--control-pair-key`, validates it as a path-safe top-level manifest field, and
  echoes it in the CLI summary. `proposal-trajectory-compare` treats equal
  non-empty keys as a pre-registered control-pair match while still reporting
  `llm_deterministic_replay=false` and
  `control_pair_key_matched_not_deterministic_llm_replay`; mismatched or missing
  keys remain `observational_only=true`. The key is report metadata only: it is
  not stored in sessions, proposals, prompts, `DecisionFeatures`, campaign loop
  state, scheduler state, Protocol, or promotion state. Acceptance:
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest scion/scion/tests/test_proposal_trajectory_artifacts.py`
  passed with `16 passed`,
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile scion/scion/core/proposal_trajectory_artifacts.py scion/scion/cli/commands/reports.py`
  passed, and `git diff --check` passed. Next: use explicit control-pair keys in
  a warehouse strong-control experiment that keeps branch/cross-branch research
  context visible while isolating measurement diagnostics; CVRP remains excluded
  from formal governance-value conclusions until measurement power improves.
- Launched: warehouse Phase 5 explicit-control-pair strong-control experiment
  from commit `bd8bfd8e020be2a51d1268070870c7ee2ff6b2ce` at
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-controlpair-full-vs-nomeas-4x2-8r-20260613T011820Z-claw`.
  Design: warehouse production problem/protocol/split/seeds, local `gpt-5.5`,
  `measurement_governance=on`, arms `full` and
  `no-measurement-diagnostics`, four order-balanced repeats, 8 rounds per cell,
  `--time-limit-sec 30`, `--disable-early-stop`, and
  `--agentic-session-timeout-sec 900`. Postrun manifests use matched
  `control_pair_key=warehouse.full-vs-nomeas:<repeat>` for each repeat. This
  isolates prompt-visible measurement diagnostics while keeping branch and
  cross-branch research context visible; it still does not make LLM trajectories
  deterministic. A prior launch root ending `20260613T011255Z-claw` was aborted
  after two failed cells because the ambient `SCION_API_KEY` pointed at an
  upstream key instead of the local proxy key. The active rerun script pins the
  local proxy key and passed `bash -n`; postrun acceptance is recorded in the
  completed audit below.
- Completed and audited: the warehouse Phase 5 explicit-control-pair
  strong-control experiment. Report:
  [`docs/experiments/v0.4/v04-phase5-warehouse-controlpair-full-vs-nomeas-4x2-20260613.md`](docs/experiments/v0.4/v04-phase5-warehouse-controlpair-full-vs-nomeas-4x2-20260613.md).
  All 8 cells exited `0`, every cell is valid and complete, and scripted
  postrun summaries, failure reports, proposal-trajectory manifests, and four
  matched-key compares were generated under
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-controlpair-full-vs-nomeas-4x2-8r-20260613T011820Z-claw/postrun_acceptance`.
  The compares all use `control_pair_key=warehouse.full-vs-nomeas:<repeat>`,
  report `observational_only=false`, and preserve
  `llm_deterministic_replay=false` with
  `control_pair_key_matched_not_deterministic_llm_replay`; this remains
  pre-registered report pairing, not deterministic replay. Prompt isolation
  worked: `full` had `problem_measurement_diagnostics` in all 62 hypothesis
  manifests, while `no-measurement-diagnostics` had it in 0/46 and still kept
  compact research, cross-branch maps, branch lessons, branch history, sibling
  branches, and champion research code visible. Outcome favored
  `no-measurement-diagnostics`: 2 promotions, 3 validation rows, and 2 frozen
  rows versus 0/0/0 for `full`. `full` showed deeper branch research
  (`max_depth=4`, mean `2.06` vs `max_depth=3`, mean `1.53`) but did not turn
  that extra depth into acceptance evidence. Leakage/boundary checks passed for
  report-only/non-mutating artifacts and no raw prompt content was stored
  (`raw_prompt` appeared only as `raw_prompt_saved=false`). Phase 5 conclusion:
  always-visible measurement diagnostics are not supported as the warehouse
  prompt default; keep deterministic measurement governance ON, prefer a compact
  or on-demand diagnostics rendering, and keep CVRP excluded from formal
  governance-value conclusions until measurement power improves.
- Completed and audited: promoted-only fixed-candidate screening replay for
  the two warehouse promotions from the `no-measurement-diagnostics` arm.
  Report:
  [`docs/experiments/v0.4/v04-phase5-warehouse-promoted-fixed-replay-20260613.md`](docs/experiments/v0.4/v04-phase5-warehouse-promoted-fixed-replay-20260613.md).
  The fixed-candidate manifest builder now supports `--candidate-id` and
  `--hypothesis-id` filters and records `candidate_filter` plus
  `filtered_out_row_count`; acceptance passed with
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_fixed_candidate_replay.py`
  (`7 passed`). The valid promoted-only replay root is
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-promoted-only-fixed-replay-20260613T075754Z-claw`.
  Each manifest included 1 candidate, filtered 4 candidates, omitted 0 rows,
  and replayed ON vs `record_only` with no row errors. The rep01
  `merge_vehicles.py` promotion remained a screening-expand candidate under
  both arms (`3/0/3` case W/L/T, median delta `875.0`). The rep04
  `split_safe_cost_repack.py` old artifact did not reproduce its source
  screening result because replay materialized an inactive operator: the source
  workspace registered `SplitSafeCostRepack` in `registry.yaml`, but the old
  formal candidate artifact recorded only the new operator file.
- Implemented and validated the formal-artifact completeness repair for future
  `create_new`/activation-surface candidates. `FormalCandidatePatchArtifactRecorder`
  now compares candidate workspace activation files against the base workspace,
  appends changed `registry.yaml` as canonical full-file patch content, records
  `proposal_target_files` and `activation_files`, and includes those files in
  the patch digest/replay identity. This keeps the fix generic and replay-owned
  rather than warehouse-specific. Acceptance:
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_fixed_candidate_replay.py scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py`
  (`21 passed`),
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile scion/scion/core/formal_candidate_artifacts.py scion/scion/core/fixed_candidate_replay.py scion/scion/cli/commands/reports.py`,
  and `git diff --check`.
- Reconstructed and replayed the historical rep04 artifact with activation
  files included. Reconstruction root:
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-reconstructed-rep04-fixed-replay-20260613T081722Z-claw`.
  Corrected candidate `2acf36e8e8709eb6` records
  `target_files=["operators/split_safe_cost_repack.py", "registry.yaml"]` and
  `activation_files=["registry.yaml"]`. The production-scope replay at
  `replay_corrected_prod/fixed_candidate_replay_comparison.v1.json` completed
  with `row_count=2`, no errors, identical ON/`record_only` outcomes, and
  `SCREENING_EXPAND`: current case W/L/T `5/1/4`, pair W/L/T `12/2/6`,
  median delta `775.0`, CI `[0.0, 3025.0]`, and canary passed. This validates
  the artifact-completeness repair and makes rep04 positive replay evidence
  when represented by an activation-complete artifact. The historical old
  `d27b539b2b540a74` artifact remains incomplete and should stay marked as a
  negative artifact-completeness example.
- Implemented the prompt-only `compact-measurement-diagnostics` context mode
  in commit `3c068c8`. This keeps protocol `measurement_governance=on` and
  leaves Protocol, DecisionFeatures, evaluation, lifecycle, and promotion
  semantics unchanged. It preserves branch history, cross-branch research,
  branch lessons, runtime feedback, objective opportunity profile, and
  code-phase source visibility, but removes the standalone
  `## Problem Measurement Diagnostics` hypothesis prompt section. Measurement
  diagnostics remain visible only through bounded `Compact Research Signals`
  under `compact_problem_measurement_diagnostics`, with
  `context_profile_metadata.measurement_diagnostics_visibility="compact"`.
  `no-measurement-diagnostics` and `measurement_governance=record_only` still
  fully suppress prompt-visible measurement diagnostics and strip
  measurement-owned opportunity diagnostics from experiment history. Acceptance:
  focused context/control suite `20 passed`, prompt/source visibility check
  `1 passed`, report/CLI/model suite `61 passed`, py_compile on touched
  proposal/CLI files, and `git diff --check`.
- Completed and audited: warehouse compact diagnostics shakedown. Report:
  [`docs/experiments/v0.4/v04-phase5-warehouse-compact-diagnostics-shakedown-20260613.md`](docs/experiments/v0.4/v04-phase5-warehouse-compact-diagnostics-shakedown-20260613.md).
  Run root:
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-compact-diagnostics-shakedown-3arms-2r-20260613T084629Z-claw`.
  The run launched from commit `5159249` with one repeat, two rounds per arm,
  warehouse production protocol/split/seeds, `measurement_governance=on`, and
  report-only `control_pair_key=warehouse.compactdiag-shakedown:rep01`. All
  three arms exited `0` and produced summaries, failures, proposal trajectory
  manifests, and pairwise compares. Prompt evidence passed: `full` had
  standalone `problem_measurement_diagnostics` in 3/3 hypothesis manifests;
  `compact-measurement-diagnostics` had 0/4 standalone sections and 4/4 bounded
  `compact_research_signals` with
  `compact_problem_measurement_diagnostics`; `no-measurement-diagnostics` had
  0/4 measurement diagnostics and no measurement string leakage while preserving
  broader research context. This is accepted as prompt/manifest shakedown only,
  not governance-value evidence.
- Fixed after the shakedown: report-only proposal trajectory joins now handle
  activation-complete duplicate formal-candidate rows, and code-phase source
  visibility accounting now infers create-new mode when action is absent but
  `target_file_exists=false` or `source_status=new_file` is present. Commit
  `3835670` repaired both accounting issues. Rebuilt report-only manifests at
  `postrun_acceptance_rebuilt_after_joinfix` restore compact trajectory joins
  from `0` to `2` joined code sessions, leaving only the hypothesis-only
  sessions unjoined. Acceptance: trajectory/report/source prompt suite
  `84 passed`, py_compile on touched manifest modules, and `git diff --check`.
- Completed design choice: run a longer compact diagnostics control rather than
  another 2R shakedown. The accepted design used warehouse production, three
  repeats, matched report-only control keys, `measurement_governance=on` in
  every arm, and primary comparison among `compact-measurement-diagnostics`,
  `no-measurement-diagnostics`, and `full`. Continue to treat
  `control_pair_key` as pre-registered report pairing, not deterministic LLM
  replay.
- Launched: warehouse compact diagnostics longer control from commit `0eca84f`
  at
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-compact-diagnostics-control-3x3-4r-20260613T092510Z-claw`.
  Design: 3 repeats x 3 prompt arms x 4 rounds, order-balanced arms,
  warehouse production protocol/split/seeds, local `gpt-5.5`, uniform 30s
  solver cap, `measurement_governance=on` in every arm, and matched report-only
  `control_pair_key=warehouse.compactdiag-control:<repeat>`. Purpose is a
  longer prompt-context control, not a final governance-value conclusion.
- Completed and audited: warehouse compact diagnostics longer control. Report:
  [`docs/experiments/v0.4/v04-phase5-warehouse-compact-diagnostics-control-3x3-20260613.md`](docs/experiments/v0.4/v04-phase5-warehouse-compact-diagnostics-control-3x3-20260613.md).
  All 9 cells exited `0`, produced complete postrun summaries/failures/
  manifests/compares, and had no `run_errors.log`. Prompt contracts held:
  `full` had standalone measurement diagnostics in 24/24 hypothesis manifests;
  `compact-measurement-diagnostics` had 0/22 standalone sections and 22/22
  compact diagnostics; `no-measurement-diagnostics` had 0/22 measurement
  diagnostic hits. No arm reached validation, frozen, or promotion. Compact is
  accepted as a viable prompt baseline candidate because it preserves research
  context and branch follow-up while removing the large diagnostics block, but
  this run does not prove quality superiority or final governance value.
  On-demand diagnostics remain deferred: there is no evidence yet that compact
  failed because it lacked pull-based detailed measurement facts.
- Completed and audited: warehouse compact-baseline measurement-governance
  ON/OFF control from commit `e1e4c48` at
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-governance-compact-onoff-4x2-8r-20260613T115956Z-claw`.
  Report:
  [`docs/experiments/v0.4/v04-phase5-warehouse-governance-compact-onoff-4x2-20260613.md`](docs/experiments/v0.4/v04-phase5-warehouse-governance-compact-onoff-4x2-20260613.md).
  All 8 cells exited `0`. Every cell completed
  `effective_rounds_completed=8`, but effective protocol rows, formal
  candidates, screening rows, formal artifact rows, and sessions diverged
  because verification-heavy attempts, proposal/code failures, one-hypothesis
  multi-candidate artifacts, and fresh-runtime replay drain are distinct
  evidence layers. Raw trajectory had one record-only promotion and no ON
  promotion, but fixed-candidate replay for the promoted record-only candidate
  and the strongest ON candidate produced identical ON vs record-only screening
  outcomes. Treat this run as valid observational governance shakedown evidence
  and a concrete repair driver, not as final causal proof that either
  governance arm is better.
- Next repair gate before another formal governance-value matrix: implement a
  stable postrun research-efficiency/accounting report that separates effective
  budget, protocol rows, formal candidates, artifact rows, fresh-runtime drain,
  validation/frozen rows, quality blocks, verification-heavy failures, and
  code-generation failures; make non-fatal agentic/code/timeout failures appear
  in failure taxonomy; repair code-phase source identity for modify operations
  after `old_string_not_found`/`stale_source` failures and 11/78 code manifests
  with `missing_required_source_paths`; and align fixed-candidate replay with
  the campaign problem-spec bridge or fail clearly when a V1 spec is required.
- Completed after the immediate warehouse governance-run repair planning: the
  CVRP/VRP baseline-strength contrast finished Phase A no-LLM characterization.
  Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw`.
  The canonical ALNS+VNS champion remains intact. The ALNS-only arm is a copied
  champion snapshot whose only intentional solver config diff is
  `USE_VNS=True -> False` in
  `policies/baseline_modules/config.py`. Smoke and 2-case x 2-seed pilot
  checks passed: ALNS-only had `0` VNS-observed pairs while the control had
  VNS evidence on every sampled pair; ALNS-only still produced ALNS move
  attempts. The accepted full run ended at `2026-06-14T02:24:47Z` with all
  stages exiting `0`; the report is
  `scion/docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseA-20260613.md`.
  Matched Scion/LLM campaigns remain gated on explicit Phase B design, not on
  missing Phase A characterization.

## Completed CVRP Baseline-Strength Phase A

Purpose: test whether the current strong ALNS+VNS champion leaves too little
measurable headroom for Scion's proposal/research loop, compared with an
ALNS-only baseline where VNS is disabled.

Pre-registration document:

- `scion/docs/planning/v0.4/v0.4-cvrp-baseline-strength-contrast-20260613.md`

Current Phase A artifacts:

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw`
- Baseline manifest:
  `baseline_manifest.json`
- Reproducibility inputs:
  `artifacts/repo_head.txt`, `artifacts/repo_status_short.txt`, and
  `artifacts/phaseA_inputs.sha256`
- Smoke outputs:
  `smoke/telemetry_smoke.json`, `smoke/pair_characterization_smoke.json`,
  `smoke/aa_smoke_alns_vns.json`, and `smoke/aa_smoke_alns_only.json`
- Pilot outputs:
  `aa/pair_characterization_pilot_2case_2seed_uniform10.json`,
  `aa/aa_pilot_alns_vns_2case_2seed_r1_uniform10.json`, and
  `aa/aa_pilot_alns_only_2case_2seed_r1_uniform10.json`
- Full run status:
  `aa/full_status.json`
- Full A/A and paired characterization:
  `aa/aa_alns_vns_protocoltime_8case_8seed_r3.json`,
  `aa/aa_alns_only_protocoltime_8case_8seed_r3.json`, and
  `aa/pair_characterization_protocoltime_8case_8seed.json`

Current Phase A evidence:

- Variant construction was independently checked by subagents and by manifest:
  the copied snapshots differ only in the ALNS-only config switch
  `USE_VNS=False`; the repository/canonical baseline was not mutated.
- Smoke telemetry on `A-n64-k9`, seed `11`, 5s budget showed ALNS-only
  `vns_runtime_present=false`, `phase_move_attempts.alns=162`, and no VNS
  phase runtime. The ALNS+VNS control showed `vns_initial`, `vns_embedded`,
  `phase_move_attempts.vns=465`, and ALNS attempts.
- The 2-case x 2-seed pilot confirmed the wiring across multiple pairs:
  ALNS-only had `contrast_vns_observed_pairs=0`, control had
  `control_vns_observed_pairs=4`, and all pairs succeeded.
- Pilot quality signal is diagnostic only: ALNS-only had `1` win and `3`
  losses versus control with median raw delta `-14.5`. Pilot A/A estimates were
  unstable by design; ALNS+VNS pilot MDE was `3.33`, while ALNS-only pilot MDE
  was `41.76`. Do not interpret those pilot MDEs as full protocol power.
- The accepted full no-LLM characterization ended at `2026-06-14T02:24:47Z`.
  ALNS+VNS A/A: `n_pairs=192`, MDE `9.6`, false-pass `0.0`,
  `recommended_min_seeds=16`. ALNS-only A/A: `n_pairs=192`, MDE `4.65`,
  false-pass `0.0`, `recommended_min_seeds=8`. Paired characterization:
  ALNS-only W/L/T `7/56/1`, median signed delta `-20.0`, mean signed delta
  `-65.25`, median runtime ratio `0.9883`, and VNS observed on `0/64`
  contrast pairs versus `64/64` control pairs.

Design constraints:

- Keep the current ALNS+VNS champion intact as the control baseline. The
  existing switch is `USE_VNS=True` in
  `scion/problems/cvrp/policies/baseline_modules/config.py`.
- Create the ALNS-only start as a separate problem-owned run-root variant or
  copied champion snapshot with `USE_VNS=False`. Do not delete VNS code or
  mutate the canonical formal baseline in place.
- First run no-LLM characterization for both starts on the same formal split,
  seeds, and protocol-resolved runtime limits: raw quality, runtime profile,
  pair variance, A/A MDE, BKS/headroom where available, and runtime saturation.
- Only after characterization, run matched Scion campaigns from each baseline
  with the same commit, problem package, cases, seeds, model, solver budgets,
  measurement-governance setting, prompt-context mode, round budget, and
  postrun acceptance scripts.
- Interpret results relative to each baseline's own measurement power and
  headroom. The primary question is not "which baseline has lower distance";
  it is whether Scion can produce accepted, evidence-backed research more
  effectively under one starting research surface than the other.

Primary metrics:

- Validation/frozen/promotion evidence above that baseline's A/A MDE.
- Branch depth by distinct formal hypotheses, not artifact retry rows.
- Same-mechanism follow-up and mechanism-family transfer.
- Proposal/code failure rate and source-identity health.
- Runtime/headroom profile and cost per accepted research insight.

Exit criteria:

- A pre-registered experiment note records exact baseline snapshots, config
  diff, protocol/split/seed hashes, and no-LLM characterization results before
  any LLM campaign starts.
- The ALNS-only arm is never used as a hidden replacement for the canonical
  ALNS+VNS control; both are labeled in prompts, summaries, and reports.
- If ALNS-only improves research productivity, the conclusion is framed as a
  baseline-strength/research-surface finding. It does not by itself prove that
  final solver quality is better than ALNS+VNS.

Phase B launch design - 2026-06-14:

- Pre-registered:
  [`docs/planning/v0.4/v0.4-cvrp-baseline-strength-phaseB-20260614.md`](docs/planning/v0.4/v0.4-cvrp-baseline-strength-phaseB-20260614.md).
- Launched:
  [`docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseB-launch-20260614.md`](docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseB-launch-20260614.md).
- Purpose: matched agentic Scion campaigns to test whether CVRP research becomes
  deeper and more evidence-backed from a lower-noise, larger-headroom copied
  research surface.
- Matrix: `3` repeats x `2` baselines (`alns_vns`, `alns_only`) x `8` rounds,
  with `measurement_governance=on`,
  `proposal_context_ablation=compact-measurement-diagnostics`,
  `--disable-early-stop`, `--agentic-proposal`, local `gpt-5.5`, and identical
  provider/retry settings.
- Protocol choice: use the accepted Phase A 8-case/8-seed config for Phase B so
  MDE interpretation is directly anchored to Phase A. This is intentionally more
  expensive than the ordinary 4-seed formal campaign.
- Boundary: ALNS-only remains a copied CVRP problem-owned snapshot. It is not a
  canonical champion replacement, and any ALNS-only promotion is interpreted as
  research-surface/headroom evidence rather than a production win over ALNS+VNS.
- Acceptance: formal outcomes come only from Contract/Verification/Protocol/
  `DecisionFeatures`/Decision. MDE, BKS gap, VNS telemetry, prompt trajectories,
  and A/A rows are postrun research-analysis facts only.
- Launcher readiness gate: before launch, update the CVRP agentic launcher so
  each cell can record custom problem/protocol/split/seeds, measurement
  governance, proposal-context arm, and report-only `control_pair_key` metadata
  in `launch.env`/`command.txt`.
- Launch state: the matrix group root is
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-claw`.
  Server `rep01` completed at `2026-06-14T15:06:31Z`. WSL `rep02`/`rep03`
  completed cleanly at `2026-06-14T16:57:58Z` from commit `2a7e1e4`, after the
  CVRP solver-design smoke data-root fallback fix. The WSL group was synced to
  the server as
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-wsl`.
- Completed and audited:
  [`docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseB-postrun-20260614.md`](docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseB-postrun-20260614.md).
  All six accepted cells are valid, complete, and `8/8`; all 48 formal rows
  remained in screening; there were no validation/frozen rows, promotions,
  failed pairs, fresh-runtime replays, or run-validity failures. ALNS-only
  produced the only validation-ready signal: WSL `rep02/alns_only`
  `route_count_aware_repair_selection` queued validation at the final protocol
  row with case W/L/T `5/1/2`, pair W/L/T `46/12/6`, median delta `16.75`, and
  CI `[3.25, 36.5]`, above the ALNS-only Phase A MDE `4.65`. It did not reach
  validation because `max_rounds_exhausted` stopped the cell.
- Phase B closeout decision: accepted as valid CVRP research-surface evidence,
  not as promotion evidence and not as a final CVRP governance-value conclusion.
  `validation=0` is not a standalone mechanism-failure diagnosis here; several
  active weak/marginal branches were censored by the 8-round budget. Next
  actions are a staged CVRP gate repair/design and a pre-registered 12/16-round
  follow-up, preferably after or explicitly paired with the repaired gate.
- Prompt/context closeout: `compact-measurement-diagnostics` did suppress the
  large standalone measurement diagnostics block, and code-stage source
  visibility held for all inspected code prompts. However, compact research
  signals and branch lesson context were often truncated; future context repair
  should keep branch lessons, same-mechanism follow-up, per-case opportunity,
  and mechanism rankings short, deterministic, and non-truncated while
  preserving full target/current source in code phase.

## Current Repair Acceptance - 2026-06-13

The immediate repair gate after the warehouse compact governance ON/OFF run is
implemented and accepted.

Accepted repair slices:

- Postrun research-efficiency accounting: `scion report research-efficiency`
  now emits a report-only JSON object separating effective budget, attempts,
  protocol rows, formal candidates, formal candidate artifacts, stage rows,
  fresh-runtime replay drain, proposal quality blocks, failure taxonomy, and
  run status.
- Failure taxonomy: the new report surfaces non-fatal agentic/code/runtime
  control signals from campaign artifacts and `run.log`, including
  `agentic_proposal:code_generation_failed`, `old_string_not_found`,
  `stale_source`, `Tool call timeout`, `verification_heavy`, and
  `abandon_fast` after repeated verification-heavy failures.
- Code-phase source identity: code prompt manifests now distinguish
  `target_source`, `required_integration_source`, and
  `activation_source_dependency_source`; duplicate required integration paths
  already satisfied by visible target source no longer create false
  `missing_required_source_paths`.
- Fixed-candidate replay problem input: default fixed replay now fails early
  with a short actionable error when `--problem` is not `ProblemSpecV1`, instead
  of emitting long Pydantic validation noise for legacy `problem.yaml`.

Acceptance commands:

- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_cli_report_research_efficiency.py scion/scion/tests/test_cli_reports_postmortem.py`
  passed with `19 passed`.
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_fixed_candidate_replay.py scion/scion/tests/unit/test_agentic_target_file_grounding.py scion/scion/tests/unit/test_prompt_manifest_accounting.py scion/scion/tests/unit/test_agentic_code_stage_invariants.py`
  passed with `55 passed`.
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile ...`
  passed on the touched report, replay, and prompt-manifest modules.
- `git diff --check` passed.

Real-artifact smoke:

- Research-efficiency reports were generated for all 8 cells under
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-governance-compact-onoff-4x2-8r-20260613T115956Z-claw/postrun_acceptance/research_efficiency`.
- The reports reproduce the key repair signals: `rep04/on_compact` has
  code-generation `2`, `old_string_not_found` `1`, `stale_source` `1`,
  tool timeouts `2`, and verification-heavy failures `2`; `rep04/record_only`
  has `abandon_fast_verification_heavy` `1` and fresh replay drain executed
  `2`.

Boundary status:

- All three repair slices are report/manifest/replay tooling only.
- No repair changes `DecisionFeatures`, Protocol gates, scheduler state,
  campaign execution semantics, lifecycle policy, or promotion state.

## Status Cadence

The main thread updates status after each material event:

- Experiment launch, completion, failure, or rerun.
- Subagent brief creation, completion, rejection, or acceptance.
- Phase gate pass/fail decision.
- Commit that changes task scope, protocol behavior, measurement behavior,
  context composition, runtime governance, or lifecycle policy.

Status updates must identify the current phase, artifact path, commit/branch,
tests or commands used for acceptance, known caveats, next gate, and whether the
next action belongs to the main thread or a subagent.

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
