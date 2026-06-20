# Scion v0.4 Current State

Last updated: 2026-06-20

This is the operational resume point, not a run log. Replace stale conclusions
instead of appending history. Detailed commands, repair evidence, counters, and
failed intermediate roots belong in `scion/docs/experiments/v0.4/`; sparse
milestones belong in `scion/docs/status/v0.4-history.md`.

## Operating Frame

- Active branch: `codex/v04-evidence-repair-plan`.
- Boundary authority: `scion/design/scion-architecture-v3.md`.
- v0.4 closeout goal: Scion must be stable enough for warehouse to recover
  continuous useful research and for CVRP/VRP to produce evidence-backed
  solver-design hypotheses before v0.5 broad experiment matrices.
- Current posture: do not add broad budgets, generic truncation/compression, or
  meaningless gates. Keep CVRP/warehouse semantics problem-owned and keep
  `DecisionFeatures` problem-neutral.

## Current Decision

- Framework/readiness/launcher repairs are accepted enough for focused
  warehouse and CVRP follow-up, but v0.4 is not closed until live runs show
  effective research behavior.
- No LLM campaign is currently running.
- The current blocker is external WSL `gpt-5.5` provider auth, not Scion static
  readiness. `/v1/models` can list `gpt-5.5`, but the strict completion
  preflight currently fails with HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`; latest auth pool has `active=0`, no launch-usable
  account, and may report the sole account as `expired` or `refreshing`.
- Do not launch a prepared root until:
  `scion/tools/check_launch_readiness.py <prepared-root> --require-launch-ready --format json`
  reports `launch_ready=true`.

## Prepared Roots

The active prepared roots were generated on WSL after CVRP postrun readiness
began rejecting seed-only large two-opt evidence as a bounded two-opt review
conclusion. WSL static readiness passes; launch readiness fails only at
completion preflight auth.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-seedguard-2d0db1b6-preflight-6r-gpt55-20260620T004921Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-seedguard-2d0db1b6-preflight-4r-gpt55-20260620T004921Z-claw`

Prepared manifests record:

- Proposal headroom: `max_attempts=64`, `max_quality_loops=64`.
- APS headroom: `agentic_session_timeout_sec=3600`,
  `agentic_tool_max_steps=240`, `agentic_tool_max_calls=200`,
  `agentic_code_tool_max_calls=200`, `agentic_observation_max_chars=2000000`.
- Runtime commits: warehouse `2d0db1b6`; CVRP `2d0db1b6`.
- Rounds: warehouse `6`; CVRP `4` so the bounded two-opt follow-up can inspect
  more than a one-off branch attempt.
- Problem-owned measurement source:
  `problem_v1.measurement.calibration_ref`.
- Absolute WSL `SCION_DIR`/`PYTHONPATH`, clean runtime guard paths, and strict
  postrun rebuild/readiness reporting in `run.sh`.

## Framework Guarantees

- Current repair signals remain report-only, control-plane, or problem-owned
  proposal diagnostics. They must not enter Decision, `DecisionFeatures`,
  promotion, scheduler state, or solver semantics.
- Launch readiness is the operator-facing authority for prepared roots. It now
  checks prepared contract/brief identity, prompt-context bridge, problem
  handoff, runtime guards, model route, absolute launch paths, completion
  preflight, strict postrun rebuild/readiness, and prepared/postrun
  rebuild-manifest identity. It also emits top-level failed-check summaries so
  operators can distinguish static failures from the completion preflight.
- Launch readiness recomputes committed drift for the prepared
  `runtime_guard_paths`: test/docs-only commit drift is allowed, but committed
  changes to runtime/control-plane/problem paths fail readiness before launch.
- Launch readiness also verifies the effective wrapper runtime guard contract:
  manifest `git.commit` and `runtime_guard_paths` must match `launch.env` and
  any executable pre-guard `run.sh` override before static readiness can pass.
- CVRP and warehouse prepared measurement handoffs are derived from
  `problem-v1.yaml` declarations and the declared A/A `calibration_ref`; stale
  or undeclared MDE/practical-delta values fail readiness.
- Prepared prompt context carries problem-owned active-subject code constraints,
  and readiness verifies the current provider payload summary before static
  readiness can pass.
- Prepared handoff rebuild and launch readiness self-locate the current
  checkout's `scion/` package path before importing problem-owned providers, so
  static readiness does not depend on ambient `PYTHONPATH`.
- Code-phase source visibility has two protections: final code prompts include
  approved target source as full `target_file_code`, and prompt manifests audit
  target, integration, and full algorithm-read visibility before postrun
  delegated review accepts source-grounding conclusions. Current CVRP declared
  integration full files are `baseline_algorithm.py`, `scheduler.py`, and
  `state.py`; the active champion sizes fit inside the dedicated integration
  prompt budget. Solver-design target file and code-phase surface reads now use
  `96000` char headroom, while bounded algorithm slices remain capped at
  `24000`.
- Solver subprocesses normalize inherited relative `PYTHONPATH` entries before
  entering solver workspaces, so smoke/protocol runs load the active checkout
  rather than an older installed package.
- Postrun inventory infers missing legacy launched-run problem family only from
  deterministic artifacts such as `run.log` `Starting campaign` markers or the
  warehouse `campaign/weight_opt_v2` tree. It keeps the prepared contract
  incomplete, but forces warehouse/CVRP delegated-review checks instead of
  silently skipping problem-specific summaries.
- Postrun acceptance readiness emits top-level failed-check summaries, so
  delegated reviewers can distinguish missing current-run analysis inputs from
  optional markers without scanning the full check table.
- CVRP bounded two-opt postrun review readiness requires co-located positive
  effect, activation, objective-effect, and two-opt-specific phase telemetry on
  the same matching top effect row. Activation/effect evidence must be
  attributed to a matching bounded or deadline-aware large two-opt mechanism;
  unrelated `mechanism_evidence`, generic/intra-only two-opt labels, and the
  external `large_instance_intra_route_two_opt_seed` guidance label cannot
  satisfy direct evidence.
- Warehouse protocol-evaluated follow-up review distinguishes positive
  at-or-above-MDE effects from plateau-consistent no-positive-MDE effects.
  Plateau-ready summaries require the measurement signal to be
  plateau-consistent, meaning all protocol effect rows have available CI high
  below MDE; positive or measurement-inconclusive effects route out of plateau
  review instead of being mislabeled as plateau.

## Warehouse

- Positive checkpoint: champion `v2` promoted in the validation-transfer rerun.
  Warehouse is not blocked on basic viability.
- The next warehouse run must test whether Scion can produce useful follow-up
  research from `v2` or correctly diagnose a real post-v2 plateau.
- The prepared handoff exposes the `v2` checkpoint, plateau question,
  default-avoid directions, required evidence, decision-boundary coverage, and
  problem-owned measurement/runtime diagnostics. Prepare-only roots do not yet
  have current-run specialist review evidence.

## CVRP/VRP

- CVRP can now steer target intent, carry branch lessons into prompts, generate
  material solver code, complete formal screening, preserve mechanism
  telemetry, and reject weak or negative hypotheses with evidence.
- CVRP has still not met v0.4 effective-research acceptance because no current
  solver-design branch has produced continuous improvement or promotion.
- The current follow-up seed is the external-control large-instance intra-route
  two-opt result. The prepared handoff treats it only as proposal guidance and
  requires a bounded, deadline-aware implementation with pair-level objective,
  feasibility, route-count, wall-clock, and CMT2/CMT4 protection evidence.
- Generic, cross-route, unbounded/fallback, VNS, and two-opt-star family labels
  are not enough for bounded two-opt review readiness; current-run protocol
  effect and co-located activation/effect/phase telemetry are required.

## Next Actions

1. Refresh the WSL/local proxy login, then rerun strict launch readiness on the
   prepared root to be started. `/v1/models` is not enough; the completion
   preflight must pass.
2. Run warehouse `v2` follow-up first as the simpler continuous-improvement
   proof. Then run the CVRP large-two-opt follow-up.
3. After warehouse launch, classify the result as taxonomy-backed
   quality-blocked, protocol-evaluated positive-effect opportunity,
   protocol-evaluated no-effect/plateau, or missed continuity opportunity.
   Only protocol-evaluated plateau conclusions can use measurement-effect,
   runtime-feedback, and substantive continuity as plateau evidence.
4. After CVRP launch, inspect target intent, bounded two-opt mechanism design,
   branch-lesson transfer, effect-vs-MDE, runtime budget behavior, source
   visibility, and research-efficiency artifacts.
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
  `scion/docs/experiments/v0.4/v04-postrun-launch-required-flag-guard-20260619.md`,
  `scion/docs/experiments/v0.4/v04-prepared-root-refresh-after-proxy-format-alias-20260619.md`,
  `scion/docs/experiments/v0.4/v04-legacy-run-problem-family-inference-20260619.md`,
  `scion/docs/experiments/v0.4/v04-launch-readiness-failed-check-summary-20260619.md`,
  `scion/docs/experiments/v0.4/v04-postrun-readiness-failed-check-summary-20260619.md`,
  `scion/docs/experiments/v0.4/v04-launch-readiness-runtime-guard-commit-drift-20260620.md`,
  `scion/docs/experiments/v0.4/v04-launch-readiness-runtime-guard-contract-consistency-20260620.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-seed-only-twoopt-readiness-guard-20260620.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-twoopt-phase-and-prepared-import-readiness-20260619.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-twoopt-mechanism-bound-direct-evidence-20260619.md`,
  `scion/docs/experiments/v0.4/v04-warehouse-positive-effect-plateau-readiness-20260619.md`,
  `scion/docs/experiments/v0.4/v04-warehouse-measurement-note-root-readiness-20260619.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-phase4-four-round-root-readiness-20260619.md`
  and
  `scion/docs/experiments/v0.4/v04-solver-source-read-headroom-readiness-20260619.md`.
- Current WSL access:
  `ssh -i ~/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes -o StrictHostKeyChecking=no xjy-ubuntu@127.0.0.1`.
  WSL repo is `/home/xjy-ubuntu/research/or-autoresearch-agent`, WSL
  experiments root is `/home/xjy-ubuntu/research/scion-experiments`, and the
  Scion Python is `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`.
