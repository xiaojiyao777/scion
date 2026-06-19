# Scion v0.4 Current State

Last updated: 2026-06-19

This is the operational resume point, not a run log. Replace stale conclusions
instead of appending history. Detailed commands, counters, and caveats belong in
`scion/docs/experiments/v0.4/`; curated milestones belong in
`scion/docs/status/v0.4-history.md`.

## Operating Frame

- Active branch: `codex/v04-evidence-repair-plan`.
- Boundary authority: `scion/design/scion-architecture-v3.md`.
- v0.4 closeout goal: make Scion stable enough that warehouse recovers
  continuous useful research and CVRP/VRP can produce evidence-backed solver
  hypotheses before v0.5 broad experiment matrices.
- Current posture: do not add broad budgets, truncation, compression, or generic
  gate tightening. Keep CVRP/warehouse semantics in problem-owned layers and
  keep generic `DecisionFeatures` problem-neutral.

## Current Truth

Framework:

- v0.4 framework/reporting/launcher repairs are accepted enough for focused
  warehouse and CVRP follow-up. This is not v0.4 closeout: the empirical proof
  still has to show effective research, especially warehouse follow-on
  improvement and CVRP/VRP solver-design progress.
- All current repair signals remain report-only, control-plane, or
  problem-owned proposal diagnostics. They must not enter Decision,
  `DecisionFeatures`, promotion, scheduler state, or solver semantics.
- Launch readiness is the authority for prepared roots. It must prove the
  current prepared contract/brief identity, prompt-context bridge,
  problem-specific handoff, runtime guards, model route, active-checkout
  `PYTHONPATH`, no-early-stop semantics, completion preflight, pre-campaign
  failure reporting, strict postrun rebuild-before-readiness reporting, strict
  postrun readiness status-after-check reporting,
  launch-env/`SCION_DIR`/runtime-guard failure postrun reporting,
  pre-campaign infra-only evidence isolation,
  prepared/postrun rebuild-manifest identity and output scope, and strict
  postrun readiness before a root is launched.
- Postrun delegated-review readiness is interpretation-specific. Protocol
  conclusions require current-run measurement/runtime/continuity inputs;
  taxonomy-backed quality-blocked no-protocol conclusions can be analysis-ready
  without plateau inputs only when failure taxonomy agrees. CVRP and warehouse
  quality-blocked summaries both expose quality-block counts and reason mix for
  delegated audit. No-protocol quality-blocked conclusions fail readiness if
  protocol accounting reports any protocol-evaluated candidate. Unsupported or
  stale conclusions still fail readiness.
- Adapter-owned diagnostics are redacted before prompt exposure for raw
  pair/calibration rows, BKS/gap details, holdout/case details, prompt ratios,
  and LLM text. Problem-owned proposal diagnostics may guide proposal context
  and readiness checks only through deterministic, schema-validated,
  report-only fields.
- Measurement-governed `pairing_validity: trajectory_divergent` lifecycle now
  keeps non-regressive low-SNR screening branches researching instead of parking
  them via fixed no-effect, repeated-signature, rollback-budget, or zero-win
  lifecycle counters. Negative median delta, loss-heavy evidence, candidate
  runtime failure, verification failure, canary failure, timeout, and true
  runtime regression still fail closed. Default/trajectory-stable lifecycle
  behavior is unchanged.
- Focused warehouse/CVRP v0.4 launchers now pass explicit proposal-attempt and
  proposal-quality-loop headroom (`64`/`64`) into `scion run`. This removes the
  old prepared-root exposure to the core `rounds + max(6, rounds * 2)` fallback,
  which could stop a 1-round CVRP follow-up after only seven quality-blocked
  proposal attempts before useful protocol evidence existed. Launch readiness
  now also requires clean runtime-guard paths and verifies the headroom across
  `launch.env`, manifest execution, manifest command, and `run.sh`.
- CVRP prepared handoff measurement diagnostics are now derived from
  `problem-v1.yaml` measurement declarations and the declared A/A
  `calibration_ref`. Prepared-contract readiness rejects CVRP handoffs that
  contain MDE/practical-delta values without problem-owned source, calibration,
  and measurement-readiness proof.

Warehouse:

- Positive checkpoint: champion `v2` promoted in the validation-transfer rerun.
  Warehouse is not blocked on basic viability; the open question is whether
  Scion can produce additional useful research from `v2` or correctly diagnose a
  real post-v2 plateau.
- Current prepared root, prepared from WSL runtime commit `3b74b90e`:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-measurecontract-3b74b90e-6r-gpt55-20260619T181700Z-claw`.
  Its prepared manifest records `proposal_attempt_limit=64` and
  `proposal_quality_loop_limit=64`.
- The handoff exposes the warehouse v2 checkpoint, plateau question,
  default-avoid directions, required evidence, and decision-boundary coverage.
  Static readiness verifies the active-subject source-constraint prompt bridge.
  Because this root is prepare-only, warehouse specialist review axes remain
  deferred until post-launch current-run evidence exists.
- Postrun warehouse plateau review readiness now requires substantive
  realized research-continuity evidence, such as branch depth, selected
  same-mechanism follow-up, satisfied branch-lesson transfer, or accepted
  weak-positive transfer. A shallow continuity block or unrealized opportunity
  is not enough to call a protocol-evaluated run plateau-review-ready. Postrun
  acceptance recomputes this continuity signal from review inputs before
  accepting a `protocol_evaluated_plateau_review_ready` summary claim.
  Postrun analysis also reports champion-progress from current-run champion
  table evidence, comparing the prepared champion checkpoint such as `v2`
  against the current champion max version while keeping copied resume history
  separate.
- Warehouse quality-blocked no-protocol conclusions are valid negative
  delegated-analysis conclusions only when the problem summary and
  `failure_taxonomy_summary` agree on current-run quality-block evidence.
  Missing measurement-effect, runtime-feedback, and research-continuity inputs
  are nonblocking only for that quality-blocked interpretation, not for
  protocol-evaluated plateau conclusions.

CVRP/VRP:

- CVRP can now steer target intent, carry branch lessons into prompts, generate
  material solver code, complete formal screening, preserve mechanism telemetry,
  and reject weak or negative hypotheses with evidence. It still has not met
  v0.4 effective-research acceptance because no current solver-design branch has
  produced continuous improvement or promotion.
- A direct WSL external-control replay found a strong large-instance
  intra-route two-opt seed above the VNS threshold (`8/8` feasible wins on four
  XL cases x two seeds). The tested unbounded fallback is not accepted and is
  not present in the clean checkout because it is not deadline-aware.
- Current prepared root, prepared from WSL runtime commit `3b74b90e`:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-measurecontract-3b74b90e-1r-gpt55-20260619T181700Z-claw`.
  Its prepared manifest records `proposal_attempt_limit=64` and
  `proposal_quality_loop_limit=64`, and its measurement handoff source is
  `problem_v1.measurement.calibration_ref`.
- The handoff exposes the large-instance two-opt seed only as proposal guidance.
  It requires bounded/deadline-aware implementation, pair-level
  objective/feasibility/route-count/wall-clock evidence, and CMT2/CMT4 case
  protection before another construction, route-merge, demand-slack, VNS, or
  share70-derived branch slot is spent. The code-generation prompt receives the
  same constraints through CVRP active-subject source constraints. Because this
  root is prepare-only, CVRP specialist review axes remain deferred until
  post-launch current-run evidence exists.
- Postrun bounded two-opt review readiness now requires both a qualifying
  large/two-opt protocol-effect row signal in measurement evidence and direct
  activation/effect/phase telemetry co-located on the same matching top effect
  row, and postrun acceptance recomputes that signal from review inputs before
  accepting a problem-summary `bounded_twoopt_review_ready` claim. Generic,
  cross-route, unbounded/fallback, VNS, or two-opt-star family labels are listed
  as rejected two-opt-like families instead of making the follow-up
  review-ready. Research-continuity family mentions remain context only.
- CVRP quality-blocked no-protocol conclusions are valid negative
  delegated-analysis conclusions only when the problem summary and
  `failure_taxonomy_summary` agree on current-run quality-block evidence.
  Missing measurement-effect, runtime-feedback, and research-continuity inputs
  are nonblocking only for that quality-blocked interpretation, not for
  protocol-evaluated bounded-two-opt conclusions.

Infrastructure:

- No LLM campaign is currently running.
- The active prepared roots were generated from WSL runtime commit `3b74b90e`
  after the trajectory-divergent open low-SNR lifecycle repair, CVRP CMT
  case-protection handoff, analysis-brief surface repairs, postrun and
  prepared-handoff stale/undeclared output guards, prepared/postrun
  rebuild-manifest identity and output scope validation, and focused launcher
  proposal-headroom/readiness-contract repair plus CVRP problem-owned
  measurement-handoff source repair.
- WSL strict launch readiness for both current prepared roots reports
  `static_ready=true`, `launch_ready=false`, exit `64`; the prepared manifests
  expose proposal-attempt and proposal-quality-loop limits as `64`/`64`, and
  readiness reports `git_runtime_worktree_clean=ok` plus
  `run_script_proposal_headroom_enforced=ok`; the CVRP root also reports
  `problem_specific_prepared_handoff=ok` with problem-owned measurement source
  proof.
- Static readiness includes
  `prepared_handoff_rebuild_declared_outputs_present=ok`, with no missing,
  inconsistent, or unexpected generated files, no manifest identity/boundary
  failures, and no out-of-scope declared outputs in standard prepared-handoff
  families.
- Postrun rebuild manifests are also checked for report-only identity and
  boundary flags before a current-run delegated-review bundle can be accepted.
  Prepare-only roots do not yet have current-run postrun bundles; `run.sh`
  remains responsible for strict postrun rebuild before postrun readiness after
  the campaign exits.
- Launch readiness also requires strict postrun rebuild reporting:
  `run_script_strict_postrun_rebuild=ok`, with the rebuild command before the
  postrun readiness command and `POSTRUN_REPORTS_EXIT_STATUS` emitted after the
  rebuild command, so incomplete postrun bundle rebuilds produce a nonzero
  status instead of a misleading success.
- It also requires `run_script_strict_postrun_readiness=ok`, with
  `POSTRUN_READINESS_EXIT_STATUS` emitted after the strict postrun readiness
  command.
- It also requires `run_script_launch_env_failure_reports=ok`, so missing or
  unreadable `launch.env` writes status and runs the same report-only postrun
  rebuild/readiness path before exiting.
- It also requires `run_script_runtime_guard_failure_reports=ok`, so dirty
  runtime paths or guarded commit mismatches write status and run the same
  report-only postrun rebuild/readiness path before exiting.
- It also requires `run_script_scion_dir_failure_reports=ok`, so missing or
  inaccessible `SCION_DIR` writes status and runs the same report-only postrun
  rebuild/readiness path before exiting.
- Pre-campaign infra failures such as missing API key env, missing `launch.env`,
  missing `SCION_DIR`, missing warehouse data root, dirty runtime paths, or
  guarded commit mismatches are resume-snapshot-only evidence. They must not
  rebuild copied campaign artifacts into current-run reports.
- The current blocker is external WSL `gpt-5.5` provider auth, not Scion static
  readiness. With `SCION_API_KEY=pwd`, `/v1/models` lists `gpt-5.5` but real
  `/v1/chat/completions` preflight returns HTTP `401`,
  `classification=not_authenticated`, `code=invalid_api_key`. Latest strict
  launch-readiness preflight saw auth pool `active=0`, `expired=1`, `total=1`,
  and no launch-usable account.
- Do not launch prepared roots until
  `scion/tools/check_launch_readiness.py <prepared-root> --require-launch-ready --format json`
  reports `launch_ready=true`.

## Next Actions

1. Refresh the WSL/local proxy login, then rerun strict launch readiness on the
   prepared root to be started, with `SCION_API_KEY=pwd` or the current proxy
   key set in the WSL launch environment. `/v1/models` is not enough.
2. Once auth is stable, run the warehouse `v2` follow-up as the simpler
   continuous-improvement proof, then run the CVRP large-two-opt follow-up.
3. For warehouse postrun review after launch, classify the result as
   taxonomy-backed quality-blocked, protocol-evaluated no-effect/plateau, or
   missed continuity opportunity. Only protocol-evaluated plateau conclusions
   can use measurement-effect, runtime-feedback, and substantive continuity as
   plateau evidence.
4. For CVRP postrun review, inspect target intent, bounded two-opt mechanism
   design, branch-lesson transfer, effect-vs-MDE, runtime budget behavior,
   source visibility, and research-efficiency artifacts. Continuity-only
   two-opt family mentions are not enough; require protocol/effect row evidence.
5. Keep this file short. Update it only when the operating truth or next action
   changes.

## Evidence Pointers

- Core task and acceptance source: `scion/TASK.md`.
- Boundary and audit basis:
  `scion/design/scion-architecture-v3.md`,
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`, and
  `scion/design/v0.5-evidence-uplift-roadmap.md`.
- Current planning summary:
  `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`.
- Current launch/readiness evidence:
  `scion/docs/experiments/v0.4/v04-proposal-headroom-launcher-repair-20260619.md`.
- Current CVRP measurement-handoff evidence:
  `scion/docs/experiments/v0.4/v04-cvrp-measurement-handoff-contract-20260619.md`.
- Current trajectory-divergent lifecycle evidence:
  `scion/docs/experiments/v0.4/v04-trajectory-divergent-open-low-signal-lifecycle-20260619.md`.
- Historical repair details remain in `scion/docs/experiments/v0.4/`; this
  page keeps only the current root pointer, launch blocker, and next action.
- WSL reference:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/RSYNC_PATHS.md`.
