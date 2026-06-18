# Scion v0.4 Current State

Last updated: 2026-06-18

This is the operational resume point, not a run log. Replace stale conclusions
instead of appending history. Detailed evidence belongs in
`scion/docs/experiments/v0.4/`; curated milestones belong in
`scion/docs/status/v0.4-history.md`.

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

- Continuation, reporting, launcher, prepared-root, and postrun-acceptance paths
  are repaired enough for focused follow-up and delegated analysis. These paths
  remain report/control-plane work; they do not change Decision,
  `DecisionFeatures`, promotion, or problem semantics.
- Measurement integration is covered against real CVRP formal and warehouse
  production assets plus the `scion run` problem-v1 ingress path. Problem-owned
  practical deltas, runtime model, pairing validity, and reduced readiness feed
  deterministic protocol config fields; raw calibration diagnostics stay
  outside `DecisionFeatures`.
- Budget-exhausting runtime semantics are repaired for v0.4: CVRP-style time
  budget saturation is treated as expected information unless there is a real
  timeout, crash, budget violation, or quality regression.
- Low-signal research behavior is less brittle: same-branch no-effect samples
  remain scheduler-visible as `refine_active`, prior no-effect lessons become
  advisory same-branch refinement requirements, and trajectory-divergent
  all-tie screening can expand as low-SNR evidence when non-regressive.
- Phase 4 postrun inventories separately expose prompt signal-density coverage,
  source visibility, and code-source visibility guarantees as report-only
  evidence requirements.
- Warehouse postrun analysis briefs now expose a report-only
  `warehouse_followup_summary` that separates prepared-only roots,
  quality-blocked proposal behavior, protocol-evaluated evidence, and
  plateau-review readiness before any delegated analysis calls the post-v2
  behavior a real plateau.
- Research-continuity and measurement-effect briefs now project branch-depth
  distribution, active shape, mechanism-family breadth, and mechanism-family
  effect summaries plus branch-lesson semantic failure/block counts, so
  delegated review can distinguish deep follow-up from shallow branch
  scattering, family-level sub-MDE/no-effect patterns, and follow-up hypotheses
  that only mention prior evidence without semantically using it.

Warehouse:

- Warehouse has a positive v0.4 research-path checkpoint: champion `v2` promoted
  in the validation-transfer rerun, and later telemetry repairs preserve real
  cost/improving-move effects without treating zero split delta as effect-zero.
- The open warehouse question is continuous follow-on improvement, not basic
  viability.
- Prepared but not launched:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-lessondiag-b9836a6-6r-gpt55-20260618T203741Z-claw`.

CVRP/VRP:

- CVRP can now steer target intent, carry branch lessons into prompts, generate
  material solver code, complete formal screening, preserve mechanism telemetry,
  and reject weak or negative hypotheses with evidence.
- CVRP still has not met v0.4 effective-research acceptance: no current
  solver-design branch has produced continuous improvement or promotion.
- Do not repeat the rejected/default-avoid directions listed in `scion/TASK.md`
  unless the next test adds a genuinely new mechanism or direct effect
  attribution. Construction seed/portfolio mechanisms need same-run seed
  baselines or accepted same-mechanism delta; activation alone is insufficient.
- Prepared but not launched:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-lessondiag-b9836a6-1r-gpt55-20260618T203729Z-claw`.

Infrastructure:

- No LLM campaign is currently running.
- The current prepared roots were built from checkout `b9836a6`. Strict
  readiness on WSL confirms both roots remain statically ready and aligned to
  guarded source.
- Launch is still blocked by `gpt-5.5` auth. On 2026-06-18, WSL strict
  readiness for both prepared roots returned `launch_ready=false`,
  `static_ready=true`, exit `64`, HTTP `401`, classification
  `not_authenticated`, auth pool `active=0` / `refreshing=1`, and an
  `operator_action.login_url`.
- Do not launch prepared roots until `/v1/chat/completions` returns HTTP `200`
  with non-empty `gpt-5.5` output.
- Keep the WSL checkout synchronized with the branch before tests or launches.
  Use `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`.

## Next Actions

1. Refresh the WSL/local proxy login, then rerun:
   `scion/tools/check_launch_readiness.py <prepared-root>
   --require-launch-ready --format json`. `/v1/models` is not enough.
2. When launch readiness is true, run the prepared CVRP post-pivot follow-up
   first from the clean WSL checkout. Inspect target intent, hypothesis, branch
   lesson transfer, protocol effect-vs-MDE, budget-exhausting runtime feedback,
   source visibility, and postrun research-efficiency reports.
3. Keep the prepared warehouse `v2` follow-up available as the simpler
   continuous-improvement check once LLM access is stable.
4. Keep this file short. Update it only when the operating truth or next action
   changes.

## Evidence Pointers

- Core task and acceptance source: `scion/TASK.md`.
- Reset/audit basis:
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`, and
  `scion/design/scion-architecture-v3.md`.
- Current planning summary:
  `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`.
- Detailed repair, launch, and postrun evidence:
  `scion/docs/experiments/v0.4/`.
- Current launch/readiness reports:
  `scion/docs/experiments/v0.4/v04-launch-readiness-strict-launch-ready-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-prepared-handoff-rebuild-tool-20260618.md`,
  `scion/docs/experiments/v0.4/v04-prompt-signal-density-coverage-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-warehouse-followup-analysis-brief-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-research-continuity-brief-shape-projection-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-mechanism-family-effect-summary-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-branch-lesson-semantic-diagnostics-brief-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-prepared-root-runtime-guard-refresh-b9836a6-20260618.md`,
  and `scion/docs/experiments/v0.4/v04-measurement-integration-real-asset-coverage-20260618.md`.
- WSL reference:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/RSYNC_PATHS.md`.
