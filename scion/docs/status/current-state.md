# Scion v0.4 Current State

Last updated: 2026-06-18

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

- The v0.4 reporting, launcher, prepared-root, postrun-acceptance, runtime
  semantics, low-SNR continuation, and prompt-context handoff repairs are ready
  for focused follow-up. These remain report/control-plane or problem-owned
  proposal signals; they do not change Decision, `DecisionFeatures`, promotion,
  scheduler state, or problem solver semantics.
- Prepared handoff bundles include report-only analysis brief, artifact
  inventory, launch-readiness, and `prompt_context_readiness` families. Static
  readiness now checks artifact identity, launch markers, problem-specific
  handoff coverage, and the prompt bridge before any prepared root is launched.
- The remaining v0.4 acceptance question is empirical: prove that the repaired
  framework supports effective agent research, especially warehouse follow-on
  improvement and CVRP/VRP solver-design progress.

Warehouse:

- Positive checkpoint: champion `v2` promoted in the validation-transfer rerun.
  Warehouse is not blocked on basic viability; the open question is whether
  Scion can produce additional useful research from `v2` or correctly diagnose a
  real post-v2 plateau.
- Current prepared root, rebuilt report-only from WSL checkout `9660c10` with
  prepared manifest commit `7f3028a`:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-identityguard-7f3028a-6r-gpt55-20260618T224522Z-claw`.
- The handoff exposes the warehouse v2 checkpoint, plateau question,
  default-avoid directions, required evidence, and decision-boundary coverage.

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
- Current prepared root, rebuilt report-only from WSL checkout `9660c10` with
  prepared manifest commit `ece0256`:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-seed-ready-ece0256-1r-gpt55-20260618T231842Z-claw`.
- The handoff exposes the large-instance two-opt seed only as proposal guidance:
  pursue a deadline-aware bounded local-search mechanism and avoid the
  unbounded fallback diff.

Infrastructure:

- No LLM campaign is currently running.
- WSL strict launch-readiness for both current prepared roots reports
  `static_ready=true`, `launch_ready=false`, exit `64`,
  `prompt_context_readiness_complete=ok`, `git_runtime_consistent=ok`, and
  completion preflight `failed`.
- The current blocker is external `gpt-5.5` auth, not Scion static readiness:
  `/v1/chat/completions` returns HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`, with proxy auth pool `active=0`, `refreshing=1`,
  `total=1`.
- Do not launch prepared roots until
  `scion/tools/check_launch_readiness.py <prepared-root> --require-launch-ready --format json`
  reports `launch_ready=true`.

## Next Actions

1. Refresh the WSL/local proxy login, then rerun strict launch readiness on the
   prepared root to be started. `/v1/models` is not enough.
2. Once auth is stable, run the warehouse `v2` follow-up as the simpler
   continuous-improvement proof, then run the CVRP large-two-opt follow-up.
3. For warehouse postrun review, distinguish quality-blocked proposals from
   protocol-evaluated no-effect evidence and do not call plateau before current
   run evidence exists.
4. For CVRP postrun review, inspect target intent, bounded two-opt mechanism
   design, branch-lesson transfer, effect-vs-MDE, runtime budget behavior,
   source visibility, and research-efficiency artifacts.
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
- Current launch/readiness reports:
  `scion/docs/experiments/v0.4/v04-prepared-handoff-rebuild-tool-20260618.md`,
  `scion/docs/experiments/v0.4/v04-launch-readiness-strict-launch-ready-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-vrp-large-instance-two-opt-seed-evidence-20260618.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-large-twoopt-launch-focus-repair-20260618.md`,
  and `scion/docs/experiments/v0.4/v04-cvrp-large-twoopt-contract-coverage-repair-20260618.md`.
- WSL reference:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/RSYNC_PATHS.md`.
