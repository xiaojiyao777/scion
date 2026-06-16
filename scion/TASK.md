# Scion v0.4 Evidence Repair Task

*Branch: `codex/v04-evidence-repair-plan`*
*Status: CVRP size70 validation stopped at failed validation; warehouse targeted repair accepted; independent VRP phase L control complete negative; regret4 broader no-LLM validation remains the next CVRP hypothesis gate*
*Updated: 2026-06-16*

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
- Implemented under acceptance: staged CVRP diagnostic-validation gate repair.
  `ExpandedBorderlineAdvanceConfig` now supports explicit pair-level diagnostic
  policy fields: `allow_pair_level_signal`, `pair_win_rate_min`,
  `min_pair_total`, `min_pair_wins`, `min_pair_win_loss_margin`,
  `pair_non_tie_win_rate_min`, and `max_pair_loss_rate`. The CVRP protocols
  enable this only as a problem-owned, expand-exhausted diagnostic-validation
  path; validation/frozen promotion gates remain strict. Boundary status:
  Decision still reads only deterministic `DecisionFeatures` aggregates, not
  raw MDE/BKS/gap/prompt/postrun diagnostics. Focused acceptance so far:
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_config.py scion/scion/tests/test_decision_screening.py scion/scion/tests/test_protocol_stats_gates.py`
  passed with `85 passed`. Wider gate-adjacent regression
  `test_config.py test_problem_bridge.py test_problem_adapter.py
  test_protocol_stats_gates.py test_decision_screening.py
  unit/core/test_branch_lifecycle_policy.py
  unit/core/test_runtime_budget_diagnostics.py
  test_verification_gate_integration.py` passed with `190 passed`;
  `py_compile` and `git diff --check` also passed.
- Implemented under acceptance: bounded post-budget stage-transition drain.
  `CampaignLoop` now has a separate `stage_transition_drain` accounting block
  and a bounded `SCION_STAGE_TRANSITION_DRAIN_LIMIT` override. After the
  requested effective proposal/screening rounds are exhausted, it can execute
  already-produced validation/frozen stage work without generating a new
  hypothesis or incrementing `effective_rounds_completed` /
  `proposal_attempts_consumed`. `BranchStepRunner` only accepts
  `READY_VALIDATE`, `VALIDATING`, `VALIDATING_EXPAND`, `READY_FROZEN`, and
  `FROZEN_TESTING` style work for this drain; arbitrary `EXPLORE`/`create_new`
  work is skipped. Validation/frozen Protocol and Decision gates still run
  normally and still form ordinary `DecisionFeatures`; this drain is not
  `decision_features_excluded`. Targeted acceptance so far:
  `test_retry_round_accounting_campaign_loop.py`,
  `test_campaign_basics_continue.py`, and
  `test_campaign_screening_verification_run.py` passed with `65 passed`;
  accounting/status tests passed with `73 passed`; touched modules
  `py_compile` passed. Combined gate/campaign/accounting regression passed with
  `328 passed`; `git diff --check` passed.
- WSL parallel execution channel is now operational for future long CVRP cells.
  The handoff/status path is
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/status/wsl_status.md`.
  The reverse SSH tunnel is user-managed from WSL; when it is up, the server
  can log in with
  `ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 xjy-ubuntu@127.0.0.1`.
  Continue to coordinate through git plus rsync/handoff directories, and do not
  let server and WSL edit the same unsynced worktree concurrently.
- Phase C long-run follow-up design is pre-registered in
  [`docs/planning/v0.4/v0.4-cvrp-baseline-strength-phaseC-longrun-20260614.md`](docs/planning/v0.4/v0.4-cvrp-baseline-strength-phaseC-longrun-20260614.md).
  It uses 16 effective rounds, `3 repeats x 2 arms`,
  `compact-measurement-diagnostics`, measurement governance `on`, and an
  explicit `SCION_STAGE_TRANSITION_DRAIN_LIMIT=4`. The protocol input must be
  an experiment-owned Phase C snapshot: Phase A's accepted 8-case/8-seed
  split/seed ledger plus the repaired CVRP staged-gate block from the current
  formal protocol. This avoids both stale Phase B gate semantics and
  non-comparable 4-seed formal sampling.
- Launcher acceptance for Phase C: `launch_cvrp_agentic_campaign.py` now exposes
  `--stage-transition-drain-limit`, records it in `launch.env` and
  `command.txt`, and exports it through `run.sh`. Focused launcher tests passed
  with `7 passed`; `py_compile` and `git diff --check` passed.
- Phase C initially launched from portable launcher commit `354a941` and is
  tracked in
  [`docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseC-launch-20260614.md`](docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseC-launch-20260614.md).
  Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z`.
  The mixed server/WSL attempt is no longer the accepted Phase C evidence set.
  WSL cells launched with the server safe data root completed/advanced as
  canary-only `EVALUATION_FAILED` rows and were archived under
  `invalid_wsl_archive/20260615T0105Z-safe-data-root-mismatch`. The partial
  server `rep01/alns_vns` run was stopped and archived under
  `superseded_server_partial_archive/20260615T0110Z-wsl-all-six-rerun` so the
  accepted matrix is a single WSL execution environment.
- Completed and audited: CVRP Phase C corrected WSL-only long run. Report:
  [`docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseC-postrun-20260615.md`](docs/experiments/v0.4/v04-cvrp-baseline-strength-phaseC-postrun-20260615.md).
  Postrun root:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z/postrun_acceptance`.
  The accepted evidence set is the corrected WSL six-cell matrix
  (`rep01/rep02/rep03 x alns_vns/alns_only`) launched from `d0bd95f` with
  WSL-native `config_wsl/`, WSL conda Python, WSL safe data root, 16 effective
  rounds, `measurement_governance=on`,
  `proposal_context_ablation=compact-measurement-diagnostics`, and
  `SCION_STAGE_TRANSITION_DRAIN_LIMIT=4`. The earlier mixed server/WSL attempt,
  canary-only WSL cells, and partial server cell remain excluded archives.
- Phase C formal outcome: all six cells were valid and completed `16/16`, and
  the strict postrun gate accepted them only after recorded formal artifacts and
  CVRPLIB metrics were present. No champion promotion occurred:
  `promote_decisions_total=0`, every accepted cell retained champion version
  `1`, and each cell's champion table contains only version `1`.
- Phase C reach/MDE result: ALNS-only reached validation in all three repeats
  and frozen in two repeats, with 6 rows at or above its Phase A MDE `4.65`.
  The strongest validation signals were rep01 `effect_to_mde=10.97` and rep02
  `effect_to_mde=4.46`, but both collapsed at frozen (`0.86` and `0.0`). The
  canonical ALNS+VNS arm reached validation in two repeats, reached no frozen
  rows, and never exceeded its Phase A MDE `9.6` (`max_effect_to_mde=0.677`).
- Phase C runtime-size diagnosis: the ALNS-only validation positives were
  measured on `30/45/60s` buckets and improved median BKS gap from about
  `5.21%` champion evidence to `4.48%-4.63%` candidate evidence. Frozen shifted
  to X-family holdouts with `60/90/120s` buckets; in the two ALNS-only frozen
  rows, `X-n573-k30`, `X-n641-k35`, and `X-n1001-k43` produced `0/18` valid
  paired comparisons due to timeout/shared-process failure, and `X-n401-k29`
  had `1/3` timeout seeds in each frozen row. A no-LLM ALNS-only champion
  smoke at
  `/home/clawd/research/scion-experiments/v04-cvrp-runtime-budget-smoke-20260615`
  replayed `X-n401` and `X-n573`, seed `61`, at current and 2x nominal budgets.
  Direct solver calls returned only after `115.9s` for `X-n401@90s` and
  `188.5s` for `X-n573@120s`, past Phase C runner kill points, but 2x budget
  still produced the same distances (`68673`, `52495`), same BKS gaps
  (`3.81%`, `3.60%`), and `best_delta=0`. Interpretation: large-X frozen
  evidence completeness is invalid under current runner timeout/grace, while
  simple 2x budget is not enough to create large-X search leverage.
- Phase C branch/context result: the run is no longer pure shallow one-off
  exploration. Every cell produced at least depth-2 branch chains, and
  ALNS+VNS reached depth/same-mechanism chain `5` in two repeats. The immediate
  report-layer gap is now narrowed, not elevated into another generic framework
  project: report-only branch-lesson usage projection found structured usage
  in `125/128` accepted Phase C sessions, with pooled counts
  `avoided=205`, `contrasted=175`, `preserved_same_branch=53`,
  `borrowed=15`, and `rejected_weak_positive=56`. This rules out the simple
  explanation that agent outputs lacked branch-lesson structure. It does not
  prove those lessons changed mechanism design or produced effective VRP
  research. Prompt sampling confirmed code-phase target/current source
  visibility held, but hypothesis and code prompts remain very large;
  `prompt_context.csv` records 76 compact-research truncations and 62
  branch-lesson truncations across accepted cells.
- Phase C closeout decision: valid and useful v0.4 evidence, but not enough to
  close the CVRP effective-research gate. The repaired framework can now carry
  ALNS-only weak-surface signals into validation/frozen, but it has not shown a
  formal CVRP promotion, has not produced accepted improvement against the
  canonical ALNS+VNS baseline, and has not proven effective branch-lesson use.
  Do not start another longer CVRP campaign as the immediate next step. First
  finish a no-LLM current/2x/4x runtime curve on the large-X frozen cases and
  add best-update trace/effect attribution so the agent can distinguish
  "budget killed the evidence" from "mechanism lacks large-X search leverage."
  Then improve the VRP mechanism research loop: concise branch lessons,
  same-mechanism state, per-case opportunity, mechanism rankings, and necessary
  solver telemetry should drive stronger mechanism follow-up without crowding
  out the research intent. Keep all of this outside `DecisionFeatures`.
- Large-X runtime tooling status: the CVRP solver-design runtime now emits
  problem-owned `solver_algorithm_best_update_trace` and
  `solver_algorithm_best_update_summary` telemetry for incumbent best updates,
  capped at 32 trace rows and summarized by first/last elapsed time,
  first/last iteration, update density, phase counts, and operator-pair counts.
  These fields are declared as optional `solver_design` telemetry in
  `problem-v1.yaml`; they are not required replay fields and do not enter
  `DecisionFeatures`. `scion/tools/cvrp_runtime_curve.py` now provides a
  no-LLM direct-solver replay tool that accepts `CASE=base_budget`, seeds,
  `1/2/4` budget multipliers, `--parallelism`, and writes JSON/CSV summaries
  including BKS gap and best-update summaries. Dry-run planning for
  `X-n401`, `X-n573`, `X-n641`, and `X-n1001` across seeds `61/67/89` and
  multipliers `1/2/4` produces `36` jobs. Full large-X curve execution remains
  the next experiment step, ideally on WSL using the pushed branch.
- Completed and accepted: the full CVRP large-X runtime curve. Report:
  `scion/docs/experiments/v0.4/v04-cvrp-largeX-runtime-curve-20260615.md`.
  WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-largeX-runtime-curve-20260615T150454Z`.
  Server sync:
  `/home/clawd/research/scion-experiments/v04-cvrp-largeX-runtime-curve-20260615T150454Z`.
  The no-LLM direct replay ran all `36` planned jobs across `X-n401`,
  `X-n573`, `X-n641`, and `X-n1001`, seeds `61/67/89`, and multipliers
  `1/2/4`. It produced `34` completed rows and `2` outer timeouts, both on
  `X-n1001 seed=61` at `120s/240s`. Completed rows had stable objectives and
  BKS gaps across multipliers, with `best_update_count=0` everywhere. The
  result confirms that Phase C runner grace was too short for stable large-X
  evidence, but does not support blind longer CVRP campaigns: more solver time
  did not create large-X search leverage. Next CVRP work should replay the
  validation-positive candidates on large-X and inspect mechanism/update
  density before another LLM campaign.
- Aborted invalid: warehouse Phase 4 longrun single-arm check. Report:
  `scion/docs/experiments/v0.4/v04-phase4-warehouse-longrun-compact-on-launch-20260615.md`.
  Clean WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-phase4-warehouse-longrun-compact-on-3x24r-20260615T163700Z`.
  Server sync root:
  `/home/clawd/research/scion-experiments/v04-phase4-warehouse-longrun-compact-on-3x24r-20260615T163700Z`.
  Design: `3` repeats, `24` rounds each, warehouse production protocol/split/
  seeds, `measurement_governance=on`, `compact-measurement-diagnostics`,
  `time_limit_sec=30`, disabled early stop, WSL-local `problem.yaml`,
  `problem-v1.yaml`, and split path copies, and max two concurrent cells with a
  600s stagger. The first attempted root ending `T162506Z` was stopped after
  rep01 failed immediately on server absolute paths; the second root ending
  `T163050Z` was stopped after launch verification showed legacy objective
  fallback because the experiment config lacked a sibling `problem-v1.yaml`.
  The clean rerun started at `2026-06-15T16:37:52Z` and was stopped at
  `2026-06-15T16:52:52Z` after rep01/rep02 produced `0` protocol metric rows
  and entered early patch-edit/`verification_light` failure loops. This root is
  invalid for warehouse longrun promotion evidence; keep it as agent behavior
  debug evidence and do not interpret it as warehouse inability to improve.
- Completed: CVRP candidate-specific large-X replay. Launch report:
  `scion/docs/experiments/v0.4/v04-cvrp-candidate-largeX-replay-launch-20260615.md`.
  Postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-candidate-largeX-replay-postrun-20260615.md`.
  Server root:
  `/home/clawd/research/scion-experiments/v04-cvrp-candidate-largeX-replay-20260615T164410Z`.
  Design: no-LLM direct solver replay for the two ALNS-only Phase C
  validation-positive candidates, `4` large-X cases, seeds `61/89`,
  multipliers `1/4`, parallelism `2`, and `solver_design` selected surface. It
  planned `32` candidate/champion pairs and produced `29` completed pairs.
  Overall completed-pair W/L/T was `2/0/27`, mean candidate-minus-champion
  delta `-8.6897`, median delta `0.0`, and route-count comparison was all
  ties. The incomplete rows were concentrated on `X-n1001-k43 seed61`, so
  runner grace remains a real large-X evidence-completeness issue. However, the
  completed rows show that the two Phase C validation-positive candidates
  mostly collapsed to ties, had `0` candidate best updates, and did not gain
  broad large-X search leverage from extra replay grace. Next CVRP mechanism
  work should require no-LLM evidence of nonzero best-update density and
  objective movement on large-X before another long LLM campaign.
- Completed: single-round debug/behavior audit design. Read-only subagent
  Ampere recommends starting with CVRP, not warehouse, because warehouse first
  needs proof that the repaired pre-Protocol path reaches Protocol while CVRP
  already has Phase C protocol rows, large-X runtime diagnostics, branch/context
  artifacts, and the independent VRP control signal. Minimal run design: one
  CVRP candidate/round on WSL with `gpt-5.5`, `measurement_governance=on`,
  `compact-measurement-diagnostics`, `--stage-transition-drain-limit 0`, no
  parallel cells, and foreground `timeout 2h`. Audit prompt manifests, source
  visibility, branch/cross-branch lesson use, hypothesis quality, code patch
  fidelity, Contract/Verification/Protocol rows, context composition, and
  whether visible lessons changed the mechanism action. If
  `protocol_metric_results=0`, classify as framework/environment until proven
  otherwise; judge agent research quality only after source/context and
  Protocol evidence are present.
- Launched: CVRP single-round debug/behavior audit on WSL from commit
  `17fdeb8`. WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-single-round-debug-cvrp-compact-1r-gpt55-20260615T172112Z-claw`.
  It was prepared without launcher `--launch`, checked, then started in tmux
  session `scion_cvrp_1r_debug_172112` at `2026-06-15T17:21:58Z` with
  `timeout 2h bash run.sh`. Config: one cell, `rounds=1`, `gpt-5.5`,
  `measurement_governance=on`, `compact-measurement-diagnostics`,
  `time_limit_sec=30`, `SCION_STAGE_TRANSITION_DRAIN_LIMIT=0`, WSL conda
  `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`. First launch check saw
  `run_status.json`, `status.json`, and `scion.db` created. After completion,
  sync the root to the server and run the artifact checklist before judging
  agent research quality.
- Interim result: the WSL 1R run was stopped and synced as invalid pre-repair
  evidence. Report:
  `scion/docs/experiments/v0.4/v04-cvrp-1r-debug-pre-repair-postrun-20260615.md`.
  It has `run_validity.reason=invalid_no_effective_rounds`,
  `protocol_metric_results=0`, `screening_protocol_results=0`,
  `agentic_sessions=10`, and repeated `algorithm_smoke_failure` before formal
  candidate evaluation. Read-only audit found code-stage source visibility was
  present, while prompt context remained large and diluted by rules/diagnostics.
  The repeated hard runtime failure was traced to a CVRP problem-owned boundary
  bug: ALNS/VNS scheduler best-update instrumentation passed internal
  `_Solution` objects to `record_best_update()`, which could not coerce internal
  `_Route` objects to public `CvrpSolution`.
- Accepted repair: the current local worktree fixes that pre-Protocol blocker
  without changing generic Decision input. Scheduler best-update recording now
  passes `best.routes_as_tuples()`, and CVRP-owned solution coercion accepts
  bare routes-like iterables. Focused acceptance:
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_cvrp_solver_algorithm_runtime.py scion/scion/tests/test_cvrp_solver_vrp_smoke.py scion/scion/tests/test_cvrp_protocol_smoke.py`
  passed with `21 passed`; scoped `py_compile` and `git diff --check` also
  passed. The stopped WSL 1R run remains pre-repair evidence because it launched
  from commit `17fdeb8`; rerun a small one-round debug from the repaired commit
  before any longer CVRP campaign.
- Launched: repaired CVRP single-round debug on WSL from commit `96ba571`.
  WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-single-round-debug-cvrp-compact-1r-repaired-gpt55-20260615T175742Z-claw`.
  Tmux session: `scion_cvrp_1r_repaired_20260615T175742Z`. It uses the same
  one-cell `gpt-5.5`, `measurement_governance=on`,
  `compact-measurement-diagnostics`, `time_limit_sec=30`, and
  `SCION_STAGE_TRANSITION_DRAIN_LIMIT=0` shape as the pre-repair debug, with
  `timeout 2h`. First launch check confirmed `run_status.json`,
  `status.json`, `scion.db`, and `run.log` creation.
- Launched: independent VRP baseline researcher control. This is an intentional
  exception to the usual v3-first subagent brief: the control agent is forbidden
  from reading Scion design/docs/reports/core, may only use standalone `vrp/`,
  and must write all scratch changes, commands, `research_log.md`, and
  benchmark results under
  `/home/clawd/research/scion-experiments/independent-vrp-baseline-research-20260615T165347Z`.
  Purpose: compare Scion-guided research with a plain Codex VRP baseline
  research process.
- Completed: independent VRP baseline researcher control. Report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-baseline-control-20260615.md`.
  The non-Scion researcher found a standalone `vrp/` mechanism: preserve a
  cheap intra-route 2-opt polish for medium instances where full VNS is skipped
  by the `vns_threshold`. The scratch benchmark produced `60/60` successful
  subprocesses, mean gap improvement from `8.7653%` to `8.1732%`, paired
  outcomes `17` improved / `13` tied / `0` regressed, and X-subset outcomes
  `15` improved / `3` tied / `0` regressed. Quick portability probe shows Scion
  CVRP already has `_two_opt_intra` and the same full-VNS threshold gate, so the
  Scion hypothesis is a scheduling/gating candidate, not a duplicate operator
  addition. Treat this as a strong external-control research signal requiring
  Scion replay/protocol validation before adoption.
- Completed: second independent VRP-only research control. Report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615.md`.
  This control again read only `vrp/` and did not read Scion docs or history.
  On the complete standalone `A/B/P/E/X` EUC_2D set with seed `0` and
  `1.0s` BKS time limit, the final candidate kept small-instance full VNS
  unchanged and added only cheap `two_opt_intra` polish for instances above the
  full-VNS threshold. Paired benchmark-feasible rows: ALL W/L/T `39/1/74`,
  mean gap `3.3243% -> 3.1658`; X W/L/T `34/0/13`, mean gap
  `5.9733% -> 5.6062`, median X cost delta `-101`. Risk: one B instance lost
  benchmark feasibility and one paired B row regressed. Treat this as a stronger
  external-control hypothesis seed that needs 3-seed/repeated replay and Scion
  direct-solver/protocol validation before adoption.
- Launched: third independent VRP-only research control `Peirce`
  (`019ecc78-2582-75f2-8d0d-1448fa0761bf`) in clean worktree
  `/home/clawd/research/or-autoresearch-agent-vrp-control-20260615b` on branch
  `codex/vrp-independent-control-20260615b`. It is explicitly forbidden from
  reading Scion artifacts and writes its research log, summaries, candidate
  patch, and paired-comparison outputs under
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615b`.
  Purpose: continue the external-control line as a clean, documented VRP
  research subject whose process can be compared against Scion-guided research.
- Completed: third independent VRP-only research control `Peirce`. Report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615b.md`.
  Because real `cvrplib/` data was absent from the isolated allowed roots, this
  control generated synthetic CVRPLIB-format fixtures and found only a weaker
  hypothesis seed: add standalone intra-route relocate to VNS. Synthetic paired
  comparison W/L/T was `18/5/15`, mean cost delta `-4.8421`, median delta `0.0`,
  and no feasibility or route-count regressions. Treat this as weaker than the
  earlier real-CVRPLIB two-opt scheduling controls.
- Launched: no-LLM Scion CVRP direct replay for the stronger independent-control
  two-opt scheduling hypothesis. Report:
  `scion/docs/experiments/v0.4/v04-cvrp-twoopt-polish-direct-replay-launch-20260615.md`.
  Server root:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-direct-replay-20260615T1820Z`.
  WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-direct-replay-20260615T1820Z`.
  Tmux session: `scion_cvrp_twoopt_smoke_20260615T1820Z`. This direct replay
  creates experiment-owned copied workspaces for `USE_VNS=False` baseline and
  `USE_VNS=False + _two_opt_intra` polish candidate, then runs a smoke on
  `B-n45-k6`, `B-n66-k9`, `A-n80-k10`, and `M-n200-k17` with seeds `11/29/43`.
  Large-X replay is gated on the smoke result and has not been launched.
- Completed: repaired CVRP 1R behavior debug. WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-single-round-debug-cvrp-compact-1r-repaired-gpt55-20260615T175742Z-claw`.
  Synced server root:
  `/home/clawd/research/scion-experiments/v04-single-round-debug-cvrp-compact-1r-repaired-gpt55-20260615T175742Z-claw`.
  Report:
  `scion/docs/experiments/v0.4/v04-cvrp-1r-debug-repaired-postrun-20260615.md`.
  It finished with wrapper exit `0`, `run_validity.status=valid`,
  `effective_protocol_rounds=1`, `formal_screened_candidates=1`,
  `protocol_metric_results=1`, `screening_protocol_results=1`,
  `validation_protocol_results=0`, `frozen_protocol_results=0`,
  `agentic_sessions=2`, and `quality_block_ledger=0`. This clears the
  immediate behavior-debug health gate: the pre-repair runtime-boundary failure
  no longer blocks Protocol. Subagent `Carson`
  (`019ecc90-853a-7111-a164-166df16f2de6`) completed artifact analysis and
  accepted this only for framework path health, not for agent research quality.
  The candidate was a `split_route_ejection_merge` VNS/local-search mechanism
  with screening case W/L/T `2/1/5`, pair W/L/T `6/5/21`, `win_rate=0.25`,
  `median_delta=0.0`, CI `[0.0, 5.25]`, and decision
  `expand_screening` / `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`.
  Source visibility passed, but the hypothesis prompt was still about `120,089`
  characters and `compact_research_signals` was truncated.
- Completed: two-opt direct replay smoke. Aggregate W/L/T was `9/3/0`, mean
  candidate-minus-baseline delta `-3.4167`, median delta `-3.5`, route/fleet
  regressions `0`, and candidate two-opt activation was nonzero
  (`9` initial accepts, `3739` embedded accepts). Large-X is not launched from
  this smoke as-is because the pre-registered gate required no repeated
  B-family objective regression, while `B-n45-k6` had two losses and
  `B-n66-k9` had one. Treat this as promising but unstable problem-owned
  mechanism evidence, not promotion evidence.
- Launched: no-LLM two-opt polish follow-up smoke to explain the B-family
  regressions before any large-X replay. Report:
  `scion/docs/experiments/v0.4/v04-cvrp-twoopt-polish-followup-smoke-launch-20260615.md`.
  Server root:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z`.
  WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z`.
  Tmux session: `scion_cvrp_twoopt_followup_1848`. The two variants are
  `initial_only` and `size70`; both are problem-owned direct replay patches,
  not Scion core changes.
- Completed: two-opt follow-up smoke. Report:
  `scion/docs/experiments/v0.4/v04-cvrp-twoopt-polish-followup-smoke-postrun-20260615.md`.
  `initial_only` still failed the large-X gate with W/L/T `7/2/3` and two
  losses on `B-n45-k6`. `size70` passed the smoke gate with W/L/T `6/0/6`, mean
  delta `-3.8333`, median delta `-1.5`, route/fleet regressions `0`, B rows all
  tied with zero two-opt activation, and A/M rows all won.
- Completed: size70 large-X diagnostic replay. Launch report:
  `scion/docs/experiments/v0.4/v04-cvrp-twoopt-size70-largeX-launch-20260615.md`.
  Postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-twoopt-size70-largeX-postrun-20260615.md`.
  WSL tmux session: `scion_cvrp_twoopt_size70_large_1848`. Synced server root:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z`.
  The actual planned candidate shape was `4` large-X cases x `3` seeds x
  multipliers `{1,4}` = `24` rows. Candidate produced `24` rows, with `23`
  completed candidate/champion pairs and one planned `X-n1001-k43 seed61 m1`
  double timeout. Completed pairs were `23/0/0` W/L/T, mean
  candidate-minus-champion delta `-295.5652`, median `-192.0`, route/fleet
  regressions `0`, initial two-opt accepts `23`, embedded accepts `72`, and
  `candidate_best_update_count=0`. This satisfies the no-LLM diagnostic gate
  for large-X objective movement and makes size70 two-opt the leading CVRP
  mechanism seed. It is still not Protocol or promotion evidence because
  runtime/timeout pressure is heavy, `m=2` was intentionally not run, and the
  mechanism acts through construction/polish rather than recorded ALNS
  incumbent-update trace.
- Launched: fourth independent VRP-only research control `Anscombe`
  (`019ecc8e-d45e-7983-b346-3621f90d38f4`) as a fresh, non-forked external
  researcher. Report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615c.md`.
  It is forbidden from reading Scion artifacts and may only inspect/edit
  standalone `vrp/` in an isolated worktree. Artifact root:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615c`.
- Completed: fourth independent VRP-only control `Anscombe`. It ran real
  standalone CVRPLIB `A` subset evidence (`27` cases, seed `0`) and rejected all
  six small candidates. No `candidate.patch` was retained. The best-looking
  attempt was C3 VNS operator reordering with W/L/T `4/2/21`, mean objective
  delta `+0.741` where positive is worse, median delta `0.0`, and no feasibility
  or route-count regressions. This is negative external-control evidence, not a
  Scion hypothesis seed. It supports deprioritizing coarse VNS scheduling and
  destroy-ratio tweaks unless later instrumentation gives a more targeted
  mechanism.
- Completed: fifth independent VRP-only research control `Feynman`
  (`019eccb2-2fc0-7ff1-8032-94358c217c8a`) as a fresh, non-forked long-running
  external researcher. Report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615d.md`.
  This is another explicit exception to the v3-first Scion subagent brief: it
  was forbidden from reading `scion/`, `TASK.md`, Scion design docs, status
  docs, and experiment reports. It studied standalone `vrp/`, ran bounded
  real-case baseline/candidate experiments, and wrote a full process log under
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615d`.
  It produced `5` baseline solver runs and `16` candidate solver runs. The
  selected H3 `route_elimination` candidate has a retained `candidate.patch`:
  `B-n78-k10 seed0` tied objective and reduced routes `11 -> 10`,
  `B-n78-k10 seed1` improved `1251 -> 1250` and reduced routes `11 -> 10`,
  `X-n200-k36 seed0` improved `61796 -> 61420` and reduced routes `38 -> 37`,
  and `A-n32-k5` / `X-n101-k25` were neutral. Treat this as a positive
  external-control hypothesis seed that needs broader no-LLM replay before any
  Scion adoption; it is not Scion Protocol or promotion evidence.
- Launched: sixth independent VRP-only research control `Lovelace`
  (`019ecce4-4806-7581-b033-d33911f8b276`) as a fresh, non-forked long-running
  external researcher. Launch report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615e.md`.
  Artifact root:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-baseline-research-longrun-20260615`.
  This is another explicit external-control exception to the v3-first Scion
  subagent rule. The agent is forbidden from reading Scion artifacts and may
  only study standalone `vrp/`, write process logs, run bounded baseline/candidate
  experiments, and retain candidate patches under the artifact root. Its output
  can seed later no-LLM Scion replay but is not Scion Protocol evidence.
- Completed: sixth independent VRP-only research control `Lovelace`. Result
  report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615e.md`.
  The run produced `research_log.md`, `status.md`, `experiments.csv`,
  `experiments.jsonl`, `final_summary.md`, and a cleanly applying
  `candidate.patch`. Caveat: its observed baseline included the pre-existing
  dirty `vrp/src/solver.py` two-opt fallback, so treat it as external research
  relative to the current dirty standalone baseline. The retained
  `construction_portfolio` seed had `1s` result `2` improved / `0` worse /
  `24` same, sum delta `-11`, and `2s` expansion `2` improved / `2` worse /
  `21` same, sum delta `-20`. It is a backlog mechanism seed requiring gating
  and broader replay, weaker than current size70 two-opt priority.
- Launched: seventh independent VRP-only research control `Schrodinger`
  (`019eccfc-0e6c-78e2-bf02-67b1689963f8`) as a fresh, non-forked external
  researcher. Launch report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615f.md`.
  Artifact root:
  `/home/clawd/research/vrp-external-research/independent-vrp-baseline-research-phase-f-20260615`.
  It is forbidden from reading Scion artifacts and may only study standalone
  `vrp/`, standard Python tooling, and its artifact directory. This keeps a
  long-running external-control lane active for comparing plain Codex VRP
  research against Scion-guided research. Any positive result is external
  hypothesis material only and must go through later no-LLM Scion replay before
  it can influence Scion experiments.
- Completed: seventh independent VRP-only research control `Schrodinger`.
  Result report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615f.md`.
  The run produced the required process artifacts under
  `/home/clawd/research/vrp-external-research/independent-vrp-baseline-research-phase-f-20260615`.
  No candidate survived and no `candidate.patch` was retained.
  `no_route_destroy` had expansion signal (`18` rows, `11` improved, `7`
  tied, `0` regressed, net delta `-93`) but failed targeted stress on
  `E/E-n76-k10` and `X/X-n101-k25` (`6` rows, `2` improved, `4` regressed,
  `4` unsafe, net delta `+188`). Treat this as negative external-control
  evidence and not a Scion hypothesis seed.
- Launched: eighth independent VRP-only research control `Tesla`
  (`019ecd11-665c-7c32-b30a-0e023f0f29ef`) as a fresh, non-forked external
  researcher. Launch report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615g.md`.
  Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615`.
  This control is intentionally not a Scion subagent: it is forbidden from
  reading Scion design, task, status, audit, prompt, or experiment artifacts.
  Its objective is to test whether a plain Codex research subject can improve
  the standalone `vrp/` baseline and leave a high-resolution research-process
  trace. First milestone is bounded: small/medium representative cases and
  short budgets only, no broad WSL/server-heavy sweep or >2h single command
  without returning a matrix proposal for main-thread approval. Any positive
  candidate is external hypothesis material only and must pass later no-LLM
  Scion replay before it can affect Scion experiments.
- Completed: eighth independent VRP-only research control `Tesla`. Result
  report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615g.md`.
  Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615`.
  It retained a parameter-only candidate patch changing default ALNS
  `destroy_ratio` from `(0.10, 0.40)` to `(0.05, 0.25)` relative to the current
  dirty local `vrp/src/solver.py` baseline. Pilot matrix result over `7` cases
  x `2` seeds at nominal `0.4s`: baseline mean gap `7.6449519187010235%`,
  candidate mean gap `7.354517114570147%`, delta
  `-0.29043480413087686` percentage points, W/T/L `5/7/2`, and lower mean wall
  time (`0.785s` versus `1.087s`). Treat this as an external-control hypothesis
  seed only. It needs broader no-LLM validation over A/B/P/CMT plus stratified
  X/tai, seeds `0..4`, budgets `0.5/1.0/3.0s`, and comparison against both
  `(0.10, 0.40)` and `(0.05, 0.30)` before any Scion replay or default change.
- Launched: ninth independent VRP-only research control `Kuhn`
  (`019ecd29-fc9e-7f73-92bd-73b729cabfb3`). This is a fresh external Codex
  research subject and is explicitly not a Scion subagent. It must not read
  Scion design, task, audit, status, prompt, or experiment artifacts. It owns a
  clean `HEAD` archive copy of `vrp/`, records the research process, and writes
  outputs only under
  `/home/clawd/research/vrp-independent-codex-research/phase-h-20260615`.
  Expected artifacts are `research_log.md`, `status.md`, `experiments.jsonl`,
  `candidate_summary.md`, and optional `candidate.patch`. Any positive result
  is external-control hypothesis material only.
- Completed: ninth independent VRP-only research control `Kuhn`. Report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615h.md`.
  Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-h-20260615`.
  It tested four standalone `vrp/` baseline candidates plus baseline over
  `9` cases x `3` seeds x `2` short budgets (`270` rows). All rows finished
  `ok`, and all produced CVRP-feasible solutions. The recommended external
  hypothesis seed is `c02_cooler_sa`, a one-file patch to
  `vrp/src/acceptance.py` changing simulated-annealing temperature ratios
  from `0.05 -> 0.02` and `0.0001 -> 0.00005`. Paired result versus baseline:
  W/T/L `11/42/1`, total-distance delta `-236`, mean BKS-gap delta
  `-0.1403` percentage points, and mean wall delta `+0.021s`. Treat this as
  weak-to-moderate external-reference evidence only. It requires broader
  no-LLM validation with more seeds, more X cases, longer budgets, and explicit
  initial-VNS wall-time instrumentation before any Scion replay or default
  solver change.
- Launched: tenth independent VRP-only research control `Ohm`
  (`019ecd40-b8cd-7060-85e0-dc28394e2cb7`). This is a fresh external Codex
  research subject and is explicitly not a Scion subagent. It must not read
  Scion design, task, audit, status, prompt, or experiment artifacts. Its job
  is to keep a documented plain-Codex VRP baseline research lane alive, with
  process logs detailed enough to compare independent Codex research behavior
  against Scion-guided branch research. It writes outputs only under
  `/home/clawd/research/vrp-independent-codex-research/phase-i-20260615`.
  Expected artifacts are `status.md`, `research_log.md`, `experiments.jsonl`,
  `candidate_summary.md`, and optional `candidate.patch`. Any positive result
  is external-control hypothesis material only and requires later no-LLM replay
  before any Scion replay or default solver change.
- Completed: tenth independent VRP-only research control `Ohm`. Report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615i.md`.
  Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-i-20260615`.
  The run produced `8` valid JSONL experiment-ledger rows and an applicable
  `candidate.patch` (`git apply --check` passed). Baseline characterization
  covered `9` cases x `3` seeds with `27/27` ok and `27/27` CVRP-feasible
  rows. The recommended external seed is `rotated_sweep8`, a large
  construction-fallback patch in `vrp/src/construction.py` that tries up to
  `8` angular sweep starts and selects the lowest-cost feasible construction.
  AGS large-only follow-up result: W/T/L `7/3/0`, total-distance delta
  `-61,847`, mean BKS-gap delta `-1.184` pp, and runtime delta `+1.513s`
  total. Treat this as an external hypothesis seed for the large construction
  path only; it does not solve the X-subset ALNS gap, and it needs broader
  no-LLM validation before any Scion replay or default solver change.
- Launched: eleventh independent VRP-only research control `Russell`
  (`019ecd64-52d1-75b3-8b39-45ca1a78b7eb`). Launch report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615j.md`.
  Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-j-20260615`.
  This is a fresh, non-forked external research subject and explicitly not a
  Scion subagent. It is forbidden from reading `scion/`, `TASK.md`, Scion
  design/status/audit/planning/experiment artifacts, or prior Scion conclusions.
  It may only study standalone `vrp/`, write process logs, run bounded paired
  baseline/candidate experiments in copied workspaces, and retain an optional
  clean `candidate.patch`. The purpose is to compare plain Codex VRP baseline
  research behavior against Scion-guided branch research. Any positive result is
  external-control hypothesis material only and requires later no-LLM replay
  before any Scion replay or default solver change.
- Completed: eleventh independent VRP-only research control `Russell`. Result
  report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615j-result.md`.
  Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-j-20260615`.
  The run produced the required process artifacts, `experiments.jsonl` has
  `4` valid JSONL rows, and no `candidate.patch` was retained. The external
  researcher identified X as the clearest standalone weakness but rejected or
  failed to retain all screened candidates: `no_vns_param` W/T/L `0/0/15` with
  mean cost delta `+240.73`, `rotated_sweep_initial` W/T/L `0/15/0`, and
  `max_destroy_160_param` W/T/L `0/15/0`. Treat this as negative
  external-control evidence; it should not seed Scion replay.
- Completed: warehouse abort behavior analysis. Report:
  `scion/docs/experiments/v0.4/v04-warehouse-abort-behavior-analysis-20260615.md`.
  Root cause was not warehouse mechanism quality: candidates failed before
  Protocol because the WSL verification environment lacked `pytest`
  (`V3_unit_tests` / `No module named pytest`), then fix-stage `wrong_owner`
  handling had no legal no-op / abort-repair path and degenerated into empty or
  whole-file `exact_replace` patch protocol errors.
- Completed: warehouse abort pre-Protocol repair. Campaign startup now calls
  `VerificationGate.run_preflight()` after problem runtime preflight; configured
  pytest-backed V3/V4 checks fail before proposal work when `pytest` is missing.
  `CreativeLayer.fix_code` now treats explicit `premise_check=wrong_owner` with
  a concrete reason as a legal no-patch repair exit, avoiding invalid
  empty/whole-file `exact_replace` attempts for environmental or boundary-owned
  failures. Focused acceptance:
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_verification_runner_checks.py scion/scion/tests/unit/core/test_campaign_control_preflight_contract.py scion/scion/tests/unit/test_agentic_session_core_flow.py -q`
  passed with `39 passed`. Next warehouse order is now empirical:
  1-candidate lifecycle debug with `protocol_metric_results>0`, short 3-5R
  debug, then rerun 3x24R.
- Completed: warehouse 1-candidate lifecycle debug design. Report:
  `scion/docs/experiments/v0.4/v04-warehouse-1candidate-lifecycle-debug-design-20260615.md`.
  Recommended gate: one WSL warehouse production cell, `rounds=1`,
  `gpt-5.5`, `measurement_governance=on`,
  `compact-measurement-diagnostics`, `time_limit_sec=30`, disabled early stop,
  and foreground `timeout 2h`, using experiment-local WSL copies of
  `problem.yaml`, sibling `problem-v1.yaml`, and `split_manifest_prod.yaml`.
  CVRP size70 large-X finished and solver load cleared before this gate was
  run.
  WSL environment preflight was repaired: `pytest` is now installed in
  `/home/xjy-ubuntu/miniconda3/envs/scion`, the WSL repo was fast-forwarded to
  `9204315`, and the focused preflight/fix-stage tests passed on WSL with
  `39 passed`.
- Completed: warehouse 1-candidate lifecycle debug gate. Postrun:
  `scion/docs/experiments/v0.4/v04-warehouse-1candidate-lifecycle-debug-postrun-20260615.md`.
  First root
  `/home/clawd/research/scion-experiments/v04-warehouse-1candidate-lifecycle-debug-20260615T1950Z`
  is invalid launch/config evidence: `run_validity.status=invalid`,
  `protocol_metric_results=0`, and canary failed because the experiment-local
  copied split resolved `safe_data_roots` to the wrong WSL data root. Accepted
  rerun root:
  `/home/clawd/research/scion-experiments/v04-warehouse-1candidate-lifecycle-debug-20260615T2000Z`.
  The rerun used an absolute WSL safe root, exited `0`, and passed the intended
  lifecycle gate with `run_validity.status=valid`, `effective_rounds_completed=1`,
  `protocol_metric_results=1`, `protocol_metric_stage_counts.screening=1`,
  `formal_screened_candidates=1`, Contract/Verification/canary all passed, and
  no postrun failures. The candidate
  `operators/subcategory_consolidate_upgrade.py` reached screening and got
  `continue_explore` with reason codes `SCREENING_FAIL_WIN_RATE` and
  `SCREENING_MARGINAL_SIGNAL_CONTINUE`; screening case W/L/T was `1/2/7`,
  pair W/L/T was `5/8/7`, median delta `0.0`. This confirms the repaired
  warehouse path can reach Protocol again. Next owner: run a short `3-5R`
  compact warehouse debug before any full `3 x 24R` longrun.
- Launched: warehouse short `3R` compact debug. Launch report:
  `scion/docs/experiments/v0.4/v04-warehouse-short-debug-3r-launch-20260615.md`.
  WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-short-debug-3r-20260615T201259Z`.
  Server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-short-debug-3r-20260615T201259Z`.
  Tmux session: `scion_warehouse_short3r_201259`. It started at
  `2026-06-15T20:14:17Z` from commit `dabfcee` with `rounds=3`,
  `measurement_governance=on`, `compact-measurement-diagnostics`,
  `time_limit_sec=30`, local `gpt-5.5`, disabled early stop, and the corrected
  absolute WSL safe root. Launch health check confirmed `status.txt`,
  `status.json`, `run_status.json`, `scion.db`, and `run.log`; campaign startup
  was reached. This is the current active warehouse task.
- Completed: warehouse short `3R` compact debug. Postrun:
  `scion/docs/experiments/v0.4/v04-warehouse-short-debug-3r-postrun-20260615.md`.
  The run exited `0` and is valid: `requested_rounds=3`,
  `effective_rounds_completed=3`, `protocol_metric_results=2`,
  `formal_screened_candidates=2`, and `verification_consumed_candidates=3`.
  The third attempt failed before Protocol on `V9_perf_guard` heavy runtime
  (`1421ms` candidate versus `445ms` champion on `instance_small_1.json`), so
  the `3R` versus `2` Protocol row difference is reconciled. Branch behavior
  was useful but not successful research: first `subcategory_pack_upgrade`
  create was marginal (`1/2/7` case W/L/T, `5/8/7` pair W/L/T), the second
  same-branch modify became no-effect (`0/0/6`, `0/0/12`), and the third
  clean-fork `swap_orders.py` candidate failed Verification. Prompt manifests
  show branch lesson usage present in all `6` sessions, but a read-only
  semantic audit judged only the same-branch modify as clearly satisfying the
  lesson intent. Aggregate prompts remain large (`932,623` chars) and dominated
  by tool-selection/general content. Do not relaunch full warehouse `3 x 24R`
  yet; do targeted guidance/context repair and another short `3-6R` debug
  first.
- Completed: targeted warehouse prompt/guidance repair before short rerun,
  commit `38262b7`. The repair keeps warehouse semantics problem-owned while
  moving compact branch-lesson usage context before the broad cross-branch map,
  adding clean-fork semantic-contrast requirements to the hypothesis prompt,
  discouraging low-value rereads in tool selection, and adding bounded
  order-level/swap guidance to both packaged warehouse `problem-v1.yaml` copies
  and adapter-rendered interface context. Focused main-thread verification
  passed:
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/test_hypothesis_context_profiles.py scion/scion/tests/unit/test_agentic_session_tool_selection.py scion/scion/tests/unit/test_warehouse_target_preview.py scion/scion/tests/unit/test_prompt_manifest_accounting.py scion/scion/tests/unit/test_agentic_target_file_grounding.py scion/scion/tests/unit/test_agentic_code_stage_invariants.py`
  with `84 passed`. Next warehouse gate: launch a short repaired `3-6R` compact
  debug before any full `3 x 24R` longrun.
- Launched: repaired warehouse short `4R` compact debug from commit `bf420c2`.
  Launch report:
  `scion/docs/experiments/v0.4/v04-warehouse-short-debug-4r-guidance-launch-20260615.md`.
  WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z`.
  Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-short-debug-4r-guidance-20260615T205022Z`.
  Tmux session: `scion_warehouse_short4r_guidance_205022`. It uses local
  `gpt-5.5`, `measurement_governance=on`,
  `compact-measurement-diagnostics`, `rounds=4`, `time_limit_sec=30`, disabled
  early stop, and an absolute WSL warehouse safe root. Launch health check
  confirmed `status=running`, `commit=bf420c2`, experiment-local WSL configs,
  and campaign startup. Postrun acceptance must inspect Protocol rows,
  branch-lesson semantic use, prompt truncation, order-level runtime behavior,
  and code-stage source visibility.
- Completed: repaired warehouse short `4R` compact debug. Postrun:
  `scion/docs/experiments/v0.4/v04-warehouse-short-debug-4r-guidance-postrun-20260615.md`.
  The run is valid and complete: wrapper exit `0`,
  `run_validity_status=valid`, `requested_rounds=4`,
  `effective_rounds_completed=4`, `effective_protocol_rounds=4`, all four
  requested attempts reached screening, and `formal_candidate_artifact_count=4`.
  `protocol_metric_results=5` because one non-counted fresh-runtime replay row
  was executed after the four counted screening rows. There were no
  verification failures, no `V9_perf_guard`, no validation/frozen rows, and no
  promotion. The order-level `move_order.py` candidate reached screening and
  avoided the previous V9 failure mode, with median runtime ratio `0.814`, but
  only marginal objective evidence (`case 1/2/3`, pair `3/5/4`, median delta
  `0`). Verdict: execution/safety gate passed, research-quality gate not ready
  for full warehouse `3 x 24R`. Remaining issues: only `1/4` branch-lesson
  usages satisfied the campaign semantic projection, three counted candidates
  stayed in same-file `subcategory_pack_upgrade.py`, hypothesis manifests still
  truncated `compact_research_signals`, general/tool-selection prompt payloads
  dominated context, and one fresh-runtime replay was still spent on a
  no-effect budget-exhausting warehouse path. Next warehouse action: targeted
  repair for semantic branch-lesson enforcement, same-mechanism no-effect
  lifecycle pressure, prompt overhead, and no-effect fresh-runtime demotion;
  then rerun another short compact `4-6R`, not full `3 x 24R` yet.
- Completed: CVRP size70 fixed-candidate validation design. Report:
  `scion/docs/planning/v0.4/v04-cvrp-size70-fixed-candidate-validation-design-20260615.md`.
  Next CVRP order: fixed-candidate validation-grade replay first, seeded Scion
  CVRP run only after mechanism validity passes. Pre-register large-X
  completion with `X-n401`, `X-n573`, `X-n641`, `X-n1001`, seeds `61/67/89`,
  multipliers `1/2/4` (`36` keys, explicitly adding `m=2`), then formal
  validation `12` cases x seeds `47/53/71/83` at protocol budgets, then frozen
  only if validation passes. Minimal tool gap: stage-aware fixed-candidate
  replay for `validation|frozen` and external full-file candidate artifacts.
- Completed: CVRP fixed-candidate replay tooling gap, commit `2a1ccb8`.
  `scion report fixed-candidate-replay-manifest` now supports repeated
  `--stage screening|validation|frozen` and `--external-candidate-artifact` for
  human-approved full-file candidates that were not produced by a previous LLM
  formal candidate index. The replay executor now runs the manifest-declared
  stage instead of hardcoding screening, and manifest/comparison artifacts
  record `stage_filter`, `source_stage`, and `replay_stage` for audit. Focused
  main-thread verification passed:
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_fixed_candidate_replay.py scion/scion/tests/test_cli_reports_postmortem.py scion/scion/tests/test_cli.py`
  with `29 passed`. This is tooling only; true CVRP size70 mechanism validity
  still requires the pre-registered no-LLM replay tiers.
- Prepared: CVRP size70 external full-file candidate artifact and validation
  fixed-replay manifest. Prep report:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-fixed-replay-prep-20260615.md`.
  Artifact:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/external_candidates/size70_twoopt_candidate.patch.json`.
  Manifest:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/fixed_replay/validation_manifest.v1.json`.
  The manifest has `candidate_count=1`, `stage_filter=["validation"]`, and no
  omitted rows. A materialization check confirmed that baseline workspace
  `workspaces/baseline_alns_only` plus the external full-file patch recreates
  `workspaces/candidate_twoopt_size70/policies/baseline_modules/scheduler.py`
  with sha256 `1cdc55672fd14f357605fbb253186fef621864c4972dd1ddf73bec31a9c826ac`.
  No validation replay has been launched yet; do not start solver-heavy CVRP
  replay while the warehouse short debug is actively evaluating solver rows.
- Launched: CVRP size70 Tier 1 Large-X completion diagnostic. Launch report:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-tier1-largeX-launch-20260615.md`.
  Postrun analysis plan:
  `scion/docs/planning/v0.4/v04-cvrp-size70-tier1-postrun-analysis-plan-20260615.md`.
  WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z`.
  Server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z`.
  Tmux session: `scion_cvrp_size70_tier1_211545`. The run uses commit
  `2548560`, no LLM/APS, `scion/tools/cvrp_runtime_curve.py`, parallelism `4`,
  and a 16h wrapper timeout. Dry-run confirmed `36` planned keys:
  `X-n401`, `X-n573`, `X-n641`, `X-n1001` x seeds `61/67/89` x multipliers
  `1/2/4`. This is Tier 1 only; formal validation remains gated on postrun
  completeness and large-X regression checks.
- Health check: after server sync on 2026-06-15, the Tier 1 WSL tmux session
  was still running. `28/36` planned keys were accounted in `run.log`: `27`
  completed and `1` `timeout_expired`. Completed `X-n401-k29`,
  `X-n573-k30`, and `X-n641-k35` rows are feasible and produced `27/27` wins
  versus the champion Large-X curve (`X-n401=-152`, `X-n573=-192`,
  `X-n641=-484` total distance on matched keys). Two-opt phase-level effects
  are present in raw runtime diagnostics. The first `X-n1001-k43` row
  (`seed61`, `multiplier1`, nominal `120s`) hit `timeout_expired` after
  `1020s`, so the remaining postrun must treat `X-n1001` as a
  runtime-completeness risk. This is not a postrun conclusion; all `36` keys
  must be accounted before deciding whether to launch formal validation.
- Completed and accepted: CVRP size70 Tier 1 Large-X completion diagnostic.
  Postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-tier1-largeX-postrun-20260615.md`.
  The WSL run completed, synced to
  `/home/clawd/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z`,
  and accounted all `36/36` planned keys. Candidate status was `35 completed /
  1 timeout`; champion curve status was `34 completed / 2 timeout`; there was
  no candidate-only timeout/failure. On the `34` completed-vs-completed pairs,
  candidate won `34/0/0`, total-distance sum delta was `-10014.0`, route count
  was unchanged, and all completed candidate outputs were feasible with
  `fleet_violation=0`. `two_opt_polish_initial` improved `35/35` completed
  rows and `two_opt_polish_embedded` improved `26/35`; `best_update_count`
  remained `0` on all rows. Decision: Tier 1 passes to formal fixed-candidate
  validation readiness, but this is no-LLM mechanism-validity material only,
  not promotion evidence or `DecisionFeatures` input. Keep `X-n1001` as a
  heavy-tail runtime diagnostic and describe the mechanism as two-opt polish
  phase movement, not deeper ALNS incumbent-update leverage.
- Launched: CVRP size70 fixed-candidate validation replay on WSL. Launch
  report:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-fixed-validation-launch-20260615.md`.
  Initial WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-fixed-validation-20260615T223636Z`.
  Initial server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-size70-fixed-validation-20260615T223636Z`.
  Initial tmux session: `scion_cvrp_size70_validation_223636`. WSL repo was
  fast-forwarded to `2e0db05`, the external candidate artifact was synced, the
  validation manifest was rebuilt with WSL-local paths, and materialization
  recreated `scheduler.py` with sha256
  `1cdc55672fd14f357605fbb253186fef621864c4972dd1ddf73bec31a9c826ac`.
  The replay uses the formal CVRP `problem-v1.yaml`, `formal/protocol.yaml`,
  `formal/split_manifest.yaml`, and `formal/seed_ledger.yaml`, with no
  explicit `--time-limit-sec` override so protocol runtime rules apply. This is
  no-LLM/no-APS mechanism-validity replay only, not promotion evidence.
  The initial run failed before Protocol with `error_count=2` because strict
  `ExperimentProtocol` case-path resolution could not resolve
  `cvrplib/A/A-n60-k9.vrp`; the formal split manifest had no WSL
  `safe_data_roots`. A repaired run is now active with an experiment-local
  split manifest adding `/home/xjy-ubuntu/research/or-autoresearch-agent/vrp`.
  Repaired WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-fixed-validation-rerun-20260615T224151Z`.
  Repaired server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-size70-fixed-validation-rerun-20260615T224151Z`.
  Repaired tmux session: `scion_cvrp_size70_validation_rerun_224151`.
  The repaired run was then stopped as invalid-spec shakedown after raw metrics
  showed `total_pairs=32` from formal `validation.n_cases=8`; the
  pre-registered Tier 2 requires all `12` validation cases x `4` seeds =
  `48` pairs per arm. A full validation relaunch is now active with an
  experiment-local protocol override `validation.n_cases=12` and
  `validation.expand_to=12`, plus the WSL data-root split fix. Full WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-fixed-validation-full-20260615T225148Z`.
  Full server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-size70-fixed-validation-full-20260615T225148Z`.
  Full tmux session: `scion_cvrp_size70_validation_full_225148`. Initial raw
  metrics report `total_pairs=48`. A later sync showed the run still active,
  with no `exit_code.txt`, no top-level comparison yet, and raw validation
  metrics at `9/48` attempted/valid pairs, `0` failed pairs, W/T/L `0/8/1`,
  mean delta `-0.222`, and median delta `0.0`. This is progress telemetry
  only; no validation conclusion is accepted until all `48` pairs and
  comparison outputs are present. Later sync clarified that `48` pairs are per
  replay arm, not the whole fixed-replay gate: the `on` arm completed `48/48`
  with `0` failed pairs, and the run then started the `record_only` arm. The
  fixed-candidate validation gate remains open until `record_only` completes,
  `exit_code.txt` is written, and `fixed_candidate_replay_comparison.v1.json`
  is present.
- Launched: CVRP fixed-validation monitor/postrun worker `Erdos`
  (`019ecd76-f213-7050-a344-36419ce5314b`). It must read v3 first, poll the
  full `48`-pair validation run sparingly, sync WSL results when complete, analyze
  top-level comparison plus raw validation metrics, and write
  `scion/docs/experiments/v0.4/v04-cvrp-size70-fixed-validation-postrun-20260615.md`.
  It must not start new experiments or edit status docs.
- Completed and accepted by main-thread verification: CVRP size70
  fixed-candidate validation replay. Postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-fixed-validation-postrun-20260615.md`.
  The Erdos monitor returned a completion summary when closed; its conclusions
  agreed with the main-thread synced artifact verification. Final acceptance is
  main-thread owned.
  Full server root:
  `/home/clawd/research/scion-experiments/v04-cvrp-size70-fixed-validation-full-20260615T225148Z`.
  Wrapper exit was `0`; `fixed_candidate_replay_comparison.v1.json` exists
  with schema `scion.fixed_candidate_replay_comparison.v1`, `row_count=2`,
  `candidate_count=1`, arms `on` and `record_only`, both rows `completed`, no
  row errors, and no campaign/promotion/scheduler state mutation. Raw metrics
  completed both arms at `48/48` valid pairs with `0` failed pairs. ON W/T/L
  was `26/13/9`, mean delta `34.4167`, median delta `4.0`; `record_only`
  W/T/L was `27/13/8`, mean delta `34.5208`, median delta `6.0`. Both arms
  reported `runtime_gate_visibility.gate_outcome=fail` with
  `VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`, despite complete/high runtime
  evidence, route-count delta `0`, fleet violation `0`, and visible two-opt
  activation. Decision: accept the run as valid fixed-candidate validation
  evidence, but stop the size70 candidate here. Do not launch frozen fixed
  replay and do not launch a seeded Scion CVRP campaign for this candidate as a
  validated mechanism.
- Launched: CVRP agent behavior debug audit worker `Gibbs`
  (`019ecd49-1c1b-7240-afa1-57084260772c`). This is a Scion read-only
  experiment-analysis subagent, so its brief requires reading
  `scion/design/scion-architecture-v3.md` first and preserving the v3 boundary.
  It must inspect existing Phase C, repaired 1R debug, candidate replay, and
  size70 prep/launch artifacts without launching new experiments or changing
  code. Deliverable:
  `scion/docs/experiments/v0.4/v04-cvrp-agent-behavior-debug-audit-20260615.md`.
  Purpose: separate framework path health from actual CVRP research quality by
  auditing branch depth, branch-lesson use, prompt/context signal density, and
  mechanism continuity.
- Completed: CVRP agent behavior debug audit worker `Gibbs`. Report:
  `scion/docs/experiments/v0.4/v04-cvrp-agent-behavior-debug-audit-20260615.md`.
  Judgment: Scion is CVRP research-capable but not yet research-effective. It
  can reach Protocol, has durable branch parentage, branch-lesson fields,
  source visibility, validation/frozen paths, and some same-mechanism chains.
  The effective-research evidence is still insufficient: Phase C had no
  promotion, canonical ALNS+VNS never exceeded its MDE, validation-positive
  large-X candidates collapsed to ties/no best-update leverage, and branch
  lesson usage is observable but not proven causal. The next useful CVRP
  debug-mode Scion run, after the size70 Tier 1 postrun, should be a small
  fixed-mechanism or strongly seeded behavior debug judged by semantic lesson
  use and mechanism continuity, not promotion alone.
- Launched: twelfth independent VRP-only research control `Helmholtz`
  (`019ecd83-3324-7820-912e-2c7d94517e7e`). This is a fresh, non-forked
  external research subject, not a Scion subagent. It is forbidden from reading
  `scion/`, `TASK.md`, Scion design/status/audit/planning/experiment artifacts,
  or prior Scion conclusions. It may only study standalone `vrp/`, write
  process logs, run bounded baseline/candidate experiments, and retain an
  optional `candidate.patch` under
  `/home/clawd/research/vrp-independent-codex-research/phase-k-20260615`.
  Required process artifacts are `research_log.md`, `experiments.jsonl`, and
  `summary.md`. Its purpose is to compare an uncontaminated plain Codex VRP
  researcher against Scion-guided branch research. Any positive result is
  external-control hypothesis material only and requires later no-LLM replay
  before any Scion replay or default solver change.
- Completed: twelfth independent VRP-only research control `Helmholtz`.
  Result report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260615k-result.md`.
  Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-k-20260615`.
  Required artifacts are present, `experiments.jsonl` has `3` valid rows, and
  `candidate.patch` dry-runs against a clean `HEAD` archive without applying to
  the main checkout. The retained `regret4_repair` seed adds a `regret4`
  repair operator and measured W/T/L `8/5/2`, mean delta `-32.333`, median
  delta `-11.0`, failures `0` on a `5` case x `3` seed x `1s` standalone VRP
  smoke grid. Treat it as a positive external-control hypothesis seed only:
  it has two X-family regressions and needs broader no-LLM validation before
  any Scion replay or default solver change.
- Launched: thirteenth independent VRP-only research control `Newton`
  (`019ecded-8a24-7a03-b64b-8b1929c9af49`). Launch report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260616l.md`.
  This is a fresh, non-forked external research subject and a deliberate
  exception to the v3-first Scion-subagent rule: it is forbidden from reading
  `scion/`, `TASK.md`, Scion design/status/audit/planning/experiment artifacts,
  or prior Scion conclusions. It may only study standalone `vrp/`, available
  VRP problem data, and standard Python tooling. Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-l-20260616`.
  Required outputs are `research_journal.md`, `candidate.patch` or
  `rejected_candidates.md`, machine-readable experiment results, `summary.md`,
  and `README.md`. Purpose: keep a bounded but continuing plain-Codex VRP
  research lane alive as an external-control comparison against Scion-guided
  branch research. Any positive result is hypothesis material only and must
  pass broader no-LLM replay before Scion replay, Protocol evidence, or default
  solver changes.
- Completed: thirteenth independent VRP-only research control `Newton`.
  Result report:
  `scion/docs/experiments/v0.4/v04-independent-vrp-research-agent-20260616l-result.md`.
  Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-l-20260616`.
  Required artifacts are present: `research_journal.md`,
  `rejected_candidates.md`, `experiment_results.jsonl`, `summary.md`, and
  `README.md`. No `candidate.patch` was retained. The implemented intra-route
  Or-opt VNS extension was rejected after `30` paired real CVRPLIB runs at
  `1s` and `3` seeds: combined W/T/L `7/12/11`, mean delta `+1.6`, median
  delta `0.0`, failures `0`, CVRP feasibility failures `0`, and candidate
  route-count regressions `0`. The follow-up outside-case sanity slice was
  negative at W/T/L `2/1/6`, mean delta `+5.666667`, median delta `+6.0`.
  Treat this as negative external-control evidence and do not send it to
  broader replay or Scion fixed replay.
- Launched: warehouse longrun regression check against the v0.3 promotion
  reference. Launch report:
  `scion/docs/experiments/v0.4/v04-warehouse-longrun-regression-3x24r-launch-20260616.md`.
  The run is a single intended-default warehouse arm from commit `f384884`:
  `measurement_governance=on`, `compact-measurement-diagnostics`, `3` repeats
  x `24R`, production protocol/split/seeds, `30s` solver cap, disabled early
  stop, local `gpt-5.5`, and WSL max parallelism `2` with a `900s` stagger.
  Purpose: verify whether current v0.4 warehouse has regressed relative to v0.3
  promotion cadence and continuous-improvement evidence. Postrun must compare
  promotions and final champion version with champion quality/gap, branch
  depth, Protocol row completeness, and whether no-promotion represents real
  plateau or pre-Protocol framework failure.
- Warehouse longrun WSL tmux session: `scion_wh_longrun_reg_071323`. WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z`.
  Initial health check at launch showed `status=running`, commit `f384884`,
  and `rep01` started. Monitor/postrun worker `Sartre`
  (`019ecf4a-359e-7870-8764-ae389aafb106`) was launched with a v3-first brief
  to poll sparingly, sync the WSL root when complete, and write
  `scion/docs/experiments/v0.4/v04-warehouse-longrun-regression-3x24r-postrun-20260616.md`.
- Completed: warehouse longrun regression check. Postrun:
  `scion/docs/experiments/v0.4/v04-warehouse-longrun-regression-3x24r-postrun-20260616.md`.
  Server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z`.
  Wrapper exit was `0`; all three cells exited `0`; all reached Protocol,
  validation, and frozen. Promotions were `rep01=1`, `rep02=0`, `rep03=1`;
  final champions were `v2`, `v1`, and `v2`, respectively. This is valid
  longrun evidence and rules out a catastrophic v0.4 warehouse launch/preflight
  regression. It does not recover the v0.3 cadence: v0.3 production Sonnet
  promoted `3/3` after fixes, while this v0.4 run promoted `2/3` and produced
  only isolated single promotions rather than a continuous chain. Main limiting
  path: proposal/context/code-edit quality plus unresolved fresh-runtime replay
  closure, not lack of warehouse opportunity.
- Launched: CVRP/VRP `regret4_repair` broader no-LLM validation worker
  `Aquinas` (`019ecf46-fbac-7a42-b360-b1bd4aecf6a0`). This is a Scion worker,
  so its brief requires reading `scion/design/scion-architecture-v3.md` first.
  It must preserve the v3 boundary, create clean baseline/candidate scratch
  workspaces from `git archive HEAD`, apply the phase K `candidate.patch` only
  in the candidate copy, and write artifacts under
  `/home/clawd/research/scion-experiments/v04-vrp-regret4-broader-validation-20260616`.
  This is no-LLM/no-APS external-candidate validation only, not Scion Protocol
  evidence or a solver default change.
- Completed: CVRP/VRP `regret4_repair` broader no-LLM validation. Postrun:
  `scion/docs/experiments/v0.4/v04-vrp-regret4-broader-validation-postrun-20260616.md`.
  Artifact root:
  `/home/clawd/research/scion-experiments/v04-vrp-regret4-broader-validation-20260616`.
  Required outputs are present and all `80/80` rows completed. Overall W/T/L
  was `21/31/28`, W-L `-7`, mean delta `-4.4625`, median delta `0.0`,
  failures `0`, feasibility regressions `0`, and route-count regressions `0`.
  Repeated regression families were `E`, `M`, and `P`. Decision: reject as-is
  for Scion fixed replay; any future use should be a narrower X-slice
  diagnostic or a new mechanism-family hypothesis, not the broad original
  `regret4_repair` patch.
- Launched: warehouse longrun per-cell branch/process analysis workers. Each
  worker has a v3-first brief and must inspect branch evolution, per-round
  context/output, branch-lesson transfer, proposal/code quality failures, and
  measurement/noise before writing a report:
  - `Kepler` (`019ed0da-651c-7741-99be-bc770758840b`): `rep01`, report
    `scion/docs/experiments/v0.4/v04-warehouse-longrun-rep01-branch-analysis-20260616.md`.
  - `Russell` (`019ed0da-a9a6-7b63-b4f4-eadecf7ad988`): `rep02`, report
    `scion/docs/experiments/v0.4/v04-warehouse-longrun-rep02-branch-analysis-20260616.md`.
  - `Curie` (`019ed0da-ed19-7393-b91e-beee247e2624`): `rep03`, report
    `scion/docs/experiments/v0.4/v04-warehouse-longrun-rep03-branch-analysis-20260616.md`.
- Launched: VRP independent-research process audit worker `Halley`
  (`019ed0db-448e-76a0-865c-901917310c3c`). It must analyze phase K
  `Helmholtz`, phase L `Newton`, the broader `regret4` validation, and optional
  earlier independent roots to explain why visible BKS gap did not translate
  into robust broad improvement. Report:
  `scion/docs/experiments/v0.4/v04-vrp-independent-research-process-audit-20260616.md`.
- Completed: all four process audits returned and were closed. Reports:
  `scion/docs/experiments/v0.4/v04-warehouse-longrun-rep01-branch-analysis-20260616.md`,
  `scion/docs/experiments/v0.4/v04-warehouse-longrun-rep02-branch-analysis-20260616.md`,
  `scion/docs/experiments/v0.4/v04-warehouse-longrun-rep03-branch-analysis-20260616.md`,
  and
  `scion/docs/experiments/v0.4/v04-vrp-independent-research-process-audit-20260616.md`.
- Main-session synthesis accepted:
  `scion/docs/experiments/v0.4/v04-warehouse-vrp-process-synthesis-20260616.md`.
  Judgement: warehouse is not a catastrophic framework regression, because
  `3 x 24R` reached Protocol/validation/frozen and produced `2/3` single
  promotions, but it does not recover v0.3-style continuous improvement.
  Branch lessons are visible in every inspected warehouse session, yet many
  traces truncate branch-lesson context and the model often fails the strict
  machine-readable `branch_lesson_usage` linkage. The next warehouse work is a
  targeted research-loop repair package: deterministic lesson canonicalization,
  explicit same-mechanism/clean-fork/sibling/weak-positive proposal modes,
  `semantic_linkage_valid` reporting, robust same-file code patching, cheap
  warehouse operator invariants, replay-candidate materialization/closure, and
  earlier all-tie branch stop/diagnosis.
- VRP judgement: the independent lane has usable process logs, but it also
  failed to turn BKS headroom into robust broad improvement. `regret4_repair`
  broadened to `80/80` rows and was rejected at W/T/L `21/31/28`, while the
  Or-opt VNS candidate was rejected in phase L. BKS gap is therefore targeting
  information, not Decision evidence. The next VRP rung should be a
  family/slice mechanism diagnostic that records construction cost,
  post-initial-local-search cost, ALNS iterations, destroy/repair choices,
  accepted moves, best-update count, route-count status, runtime phase split,
  budget tier, and final gap before proposing another broad candidate.
- Completed and accepted: W4/P2 prompt signal-density repair. The warehouse
  branch audits showed `compact_research_signals` and
  `branch_lesson_usage_context` still hit provider-visible truncation markers
  in many hypothesis traces. Re-reading `scion-architecture-v3.md`,
  `v04-core-framework-code-review-20260611.md`,
  `v04-core-framework-review-20260611.md`, and
  `v0.5-evidence-uplift-roadmap.md` confirmed this was a v0.4 closeout blocker,
  not a v0.5-only experiment item. Worker `Lovelace`
  (`019ed10e-aa46-7e02-bcdc-71d5d05383b4`) implemented the repair in proposal
  prompt/context rendering: critical research sections no longer route through
  tiny `_bounded_json` budgets, branch-lesson prompt records preserve compact
  ids/target/action/mechanism/evidence fields, and repeated
  `required_response`/raw audit/session payloads are kept out of provider-visible
  research context. Acceptance stress test proves `compact_research_signals`,
  `branch_lesson_usage_context`, and `cross_branch_research_map` are not marked
  truncated while champion/source code remains visible and v3 Decision
  boundaries are unchanged. Main-session verification:
  `test_hypothesis_context_profiles.py`, `test_proposal_validation.py`,
  `test_branch_lesson_usage.py` (`79 passed`), plus proposal pipeline/artifact
  regression subset (`45 passed`), `py_compile`, and `git diff --check`. Next
  real campaign must still confirm prompt manifests stay untruncated on live
  warehouse/CVRP traces.
- Completed and accepted: no-hard-truncation follow-up to W4/P2 prompt
  signal-density repair. User review clarified that the current research phase
  should not impose hard prompt budgets, fixed item caps, or field-level
  truncation on useful projected research context. Worker `Kant`
  (`019ed11a-7885-7b40-840f-20ba66678ee9`) implemented commit `fd185cf`
  (`fix: remove prompt research signal hard caps`): compact research signals,
  branch lesson usage context, cross-branch research map, and generic projected
  research values no longer apply default character caps, list caps, array
  slicing, or ellipsis/truncation markers. Noise removal remains intact:
  raw audit/session rows and `required_response` payloads stay out of
  provider-visible research context. Main-session acceptance repeated the
  focused prompt/validation/branch-lesson and proposal pipeline/artifact suites
  together (`124 passed`), plus `py_compile` and `git diff --check`. Next
  action returns to the live warehouse/CVRP field check: verify prompt manifests
  from a real campaign under `fd185cf` or descendant.
- Launched: warehouse no-hard-truncation short `4R` field check. Launch report:
  `scion/docs/experiments/v0.4/v04-warehouse-nohardtrunc-short-debug-4r-launch-20260616.md`.
  Official WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-postrepair-nohardtrunc-short-debug-4r-20260616T155951Z`.
  Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-postrepair-nohardtrunc-short-debug-4r-20260616T155951Z`.
  Tmux session: `scion_wh_nohardtrunc_short4r_155951`. Commit `061eba0`,
  code repair commit `fd185cf`, local `gpt-5.5`, `measurement_governance=on`,
  `compact-measurement-diagnostics`, production warehouse protocol/split/seeds,
  `time_limit_sec=30`, disabled early stop, `4` rounds. Purpose: field-check
  real hypothesis prompt manifests for no hard research-signal truncation while
  preserving raw/noise filtering. An earlier root
  `...20260616T155433Z` is invalid launch-env evidence only because it omitted
  `SCION_API_KEY` and APS failed with missing credentials; do not interpret it
  as research evidence.
- Completed and accepted: targeted warehouse research-quality repair by Scion
  worker `Planck` (`019ecd2c-d228-7292-99c3-4ebc1f855034`). Acceptance report:
  `scion/docs/experiments/v0.4/v04-warehouse-targeted-repair-20260615.md`.
  The repair preserves the v3 boundary and changes only proposal/report
  mechanics: strict `clean_fork_new_branch` / `sibling_nearby_attempt`
  branch-lesson requirements now hard pre-code block missing,
  metadata-only, linkage-unrecognized, or semantic-mismatch usage; no-effect
  fresh-runtime drain no longer materializes bare
  `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` without pair-win/no-loss or actionable
  loss-diagnostic signal; `same_branch_refinement` remains non-hard-blocking.
  Main-thread verification passed `149 + 79 + 76` focused tests plus
  `py_compile` and `git diff --check`. The later `3 x 24R` longrun confirms
  warehouse can still promote, but prompt/context/code-edit overhead and
  fresh-runtime closure remain unresolved.
- Prepared: post-repair warehouse short debug design. Report:
  `scion/docs/planning/v0.4/v04-warehouse-postrepair-short-debug-design-20260615.md`.
  This design is not launched. It requires WSL to be fast-forwarded to commit
  `1144239` or a descendant, local `gpt-5.5`, `measurement_governance=on`,
  `compact-measurement-diagnostics`, one warehouse production cell, and `4-6`
  rounds with early stop disabled. The CVRP size70 Tier 1 solver replay has now
  cleared; coordinate any warehouse rerun with the formal CVRP validation replay
  so WSL solver load does not distort either gate.

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
