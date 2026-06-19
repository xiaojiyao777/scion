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
- Prepared roots are static-ready only when launch readiness proves the current
  prepared contract, prepared analysis brief, prompt-context bridge,
  problem-specific handoff, postrun families, runtime guard coverage,
  executable runtime guard markers, `gpt-5.5` model routing, active-checkout
  `PYTHONPATH`, executable `launch.env` sourcing, exact no-early-stop launch
  semantics, executable completion preflight, executable preflight-failure
  status writer, executable pre-campaign failure markers, executable postrun
  report function, executable strict postrun readiness, and postrun-reportable
  campaign/pre-campaign exit paths.
- Current-run delegated review readiness for warehouse/CVRP requires matching
  problem summaries, rebuild-manifest identity and declared outputs,
  prompt/source visibility traces, research-context/signal-density/failure
  taxonomy/review-input summaries, and consistency between those summaries and
  the problem-specific conclusion. Missing review inputs fail readiness; valid
  negative conclusions can still be analysis-ready.
- Adapter-owned diagnostics are redacted before prompt exposure for raw
  pair/calibration rows, BKS/gap details, holdout/case details, prompt ratios,
  and LLM text. Problem-owned proposal diagnostics may guide proposal context
  and readiness checks only through deterministic, schema-validated,
  report-only fields.

Warehouse:

- Positive checkpoint: champion `v2` promoted in the validation-transfer rerun.
  Warehouse is not blocked on basic viability; the open question is whether
  Scion can produce additional useful research from `v2` or correctly diagnose a
  real post-v2 plateau.
- Current prepared root, prepared from WSL runtime commit `a019ee9`:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-inputcheck-a019ee9-6r-gpt55-20260619T113828Z-claw`.
- The handoff exposes the warehouse v2 checkpoint, plateau question,
  default-avoid directions, required evidence, and decision-boundary coverage.
  Static readiness also verifies the
  `warehouse_active_subject_code_constraints_prompt_bridge` source/provider
  markers.
  Because the root is prepare-only, required answers focus on
  launch/readiness/handoff rather than research-quality or plateau conclusions;
  the warehouse specialist review axes are marked deferred until post-launch
  current-run evidence exists.
- Postrun warehouse plateau review readiness now requires substantive
  realized research-continuity evidence, such as branch depth, selected
  same-mechanism follow-up, satisfied branch-lesson transfer, or accepted
  weak-positive transfer. A shallow continuity block or unrealized opportunity
  is not enough to call a protocol-evaluated run plateau-review-ready.

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
- Current prepared root, prepared from WSL runtime commit `a019ee9`:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-inputcheck-a019ee9-1r-gpt55-20260619T113829Z-claw`.
- The handoff exposes the large-instance two-opt seed only as proposal guidance
  and now carries structured `large_instance_two_opt_constraints`: derive an
  explicit deadline/remaining-time guard, avoid unbounded `two_opt_intra`/VNS,
  preserve feasibility/route-count evidence, and require pair-level objective,
  feasibility, route-count, and wall-clock evidence. The code-generation prompt
  receives the same bounded/deadline/evidence constraints through CVRP active
  subject code constraints, and static readiness verifies the
  `cvrp_active_subject_code_constraints_prompt_bridge` source/provider markers.
  Because the root is prepare-only, required answers focus on
  launch/readiness/handoff rather than research-quality or bounded two-opt
  conclusions; the CVRP specialist review axes are marked deferred until
  post-launch current-run evidence exists.
- Postrun bounded two-opt review readiness now requires both a qualifying
  large/two-opt protocol-effect row signal in measurement evidence and direct
  activation/effect/phase telemetry co-located on the same matching top effect
  row, and postrun acceptance recomputes that signal from review inputs before
  accepting a problem-summary `bounded_twoopt_review_ready` claim. Generic,
  cross-route, unbounded/fallback, VNS, or two-opt-star family labels are listed
  as rejected two-opt-like families instead of making the follow-up
  review-ready. Research-continuity family mentions remain context only.

Infrastructure:

- No LLM campaign is currently running.
- The active prepared roots were generated from WSL runtime commit `a019ee9`.
  Current local/WSL checkouts may include later documentation-only commits;
  launch readiness reports `git_runtime_consistent=ok` because runtime guard
  paths are unchanged.
- WSL strict launch readiness for both current prepared roots reports
  `static_ready=true`, `launch_ready=false`, exit `64`. Static checks include
  prepared contract/brief identity, prompt-context handoff,
  problem-specific handoff, postrun family coverage, executable runtime guards,
  active checkout import path, exact no-early-stop semantics, model-route
  consistency, executable `launch.env` source, executable completion
  preflight, executable preflight-failure status writer, executable
  pre-campaign failure markers, executable postrun report function, executable
  strict postrun readiness, and postrun-reportable campaign/pre-campaign exit
  paths.
- The current blocker is external WSL `gpt-5.5` provider auth, not Scion static
  readiness. With `SCION_API_KEY=pwd`, `/v1/models` lists `gpt-5.5` but real
  `/v1/chat/completions` preflight returns HTTP `401`,
  `classification=not_authenticated`, `code=invalid_api_key`, with auth pool
  `active=0`, `expired=1`, `refreshing=0`, `total=1`, and no launch-usable
  account.
- Do not launch prepared roots until
  `scion/tools/check_launch_readiness.py <prepared-root> --require-launch-ready --format json`
  reports `launch_ready=true`.

## Next Actions

1. Refresh the WSL/local proxy login, then rerun strict launch readiness on the
   prepared root to be started, with `SCION_API_KEY=pwd` or the current proxy
   key set in the WSL launch environment. `/v1/models` is not enough.
2. Once auth is stable, run the warehouse `v2` follow-up as the simpler
   continuous-improvement proof, then run the CVRP large-two-opt follow-up.
3. For warehouse postrun review, distinguish quality-blocked proposals from
   protocol-evaluated no-effect evidence and require measurement-effect,
   runtime-feedback, and substantive research-continuity signals before calling
   evidence plateau-review-ready.
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
- Detailed repair, launch, and postrun evidence:
  `scion/docs/experiments/v0.4/`.
- Current launch/readiness evidence:
  `scion/docs/experiments/v0.4/v04-launch-readiness-run-script-no-early-stop-20260619.md`.
  Earlier launch/readiness guard details remain in
  `scion/docs/experiments/v0.4/`; this page keeps only the current root
  pointer and launch blocker.
- Current CVRP postrun evidence-accounting repair:
  `scion/docs/experiments/v0.4/v04-cvrp-large-twoopt-direct-evidence-row-coherence-20260619.md`.
- Current CVRP postrun acceptance consistency repair:
  `scion/docs/experiments/v0.4/v04-cvrp-large-twoopt-readiness-input-consistency-20260619.md`.
- Current warehouse postrun evidence-accounting repair:
  `scion/docs/experiments/v0.4/v04-warehouse-continuity-realized-signal-20260619.md`.
- Current repair context lives in `scion/docs/experiments/v0.4/`; keep this
  status page focused on operating truth rather than repair chronology.
- WSL reference:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/RSYNC_PATHS.md`.
