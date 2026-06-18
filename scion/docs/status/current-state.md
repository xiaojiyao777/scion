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
  that only mention prior evidence without semantically using it. Postrun briefs
  also include a report-only `research_context_actionability_summary` joining
  prompt block-family signal with continuity gaps, so reviewers can audit
  whether failed prior-evidence transfer lines up with missing research or
  cross-branch context. That actionability summary now carries branch-lesson
  semantic failure/block reason mixes, so reviewers can separate metadata-only
  payloads, unrecognized linkage aliases, and true semantic mismatches.
- Live hypothesis prompts now receive a compact proposal-only
  `research_shape_diagnostics` signal derived from the cross-branch research
  map, so branch depth, shallow scatter, and repeated non-positive family shape
  are visible before broader rules without entering `DecisionFeatures`.
- Prepared handoff bundles now include a report-only
  `prompt_context_readiness` family. It audits prepared research focus, copied
  campaign summary/status, problem-specific handoff fields, and the
  `research_shape_diagnostics` prompt path before launch without rendering raw
  provider prompts or changing runtime decisions. Launch readiness now requires
  this prompt/context artifact and independently rechecks the bridge source and
  launch markers plus artifact identity before reporting `static_ready=true`.
- Prepared contract/inventory coverage now requires the CVRP large-instance
  two-opt seed and its unbounded-fallback default-avoid line, so future prepared
  roots fail static handoff coverage if that guidance is dropped. These also
  appear as named problem-specific coverage items in prepared briefs and
  inventories.

Warehouse:

- Warehouse has a positive v0.4 research-path checkpoint: champion `v2` promoted
  in the validation-transfer rerun, and later telemetry repairs preserve real
  cost/improving-move effects without treating zero split delta as effect-zero.
- The open warehouse question is continuous follow-on improvement, not basic
  viability.
- Prepared but not launched:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-identityguard-7f3028a-6r-gpt55-20260618T224522Z-claw`.

CVRP/VRP:

- CVRP can now steer target intent, carry branch lessons into prompts, generate
  material solver code, complete formal screening, preserve mechanism telemetry,
  and reject weak or negative hypotheses with evidence.
- CVRP active solver context now marks the existing size70 two-opt fallback as
  an active fact and readable scheduler slice, so follow-up agents should not
  propose it as a missing mechanism.
- A direct WSL external-control replay found a strong large-instance
  intra-route two-opt signal above the VNS threshold (`8/8` feasible wins on
  four XL cases x two seeds), but the tested unbounded fallback is not accepted
  and is not present in the clean checkout because `two_opt_intra` has no
  deadline and can violate the nominal solver budget. Treat it as a
  problem-owned research-focus seed, not Scion evidence or a baseline solver
  update.
- The current CVRP prepared root now exposes that seed as proposal-only
  `research_focus`: agents must pursue it only as a deadline-aware bounded
  local-search mechanism and must avoid the unbounded fallback diff.
- Prepared `research_focus` now enters hypothesis prompt compact research
  signals as proposal-only launch focus. Prepared handoff readiness audits this
  bridge through `prepared_research_focus_prompt_bridge`; the signal remains
  excluded from `DecisionFeatures`.
- CVRP still has not met v0.4 effective-research acceptance: no current
  solver-design branch has produced continuous improvement or promotion.
- Do not repeat the rejected/default-avoid directions listed in `scion/TASK.md`
  unless the next test adds a genuinely new mechanism or direct effect
  attribution. Construction seed/portfolio mechanisms need same-run seed
  baselines or accepted same-mechanism delta; activation alone is insufficient.
- Prepared but not launched:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-seed-ready-ece0256-1r-gpt55-20260618T231842Z-claw`.

Infrastructure:

- No LLM campaign is currently running.
- The current CVRP prepared root was refreshed from checkout `ece0256` after
  the large-instance two-opt launch-focus repair. The warehouse prepared root
  remains the identity-guard root from checkout `7f3028a`; under the current
  checkout it is still statically ready because runtime guard paths are
  unchanged.
  The CVRP root's prepared handoff artifacts have been rebuilt with checkout
  `c34c0ff`, so its prepared brief and inventory expose the named
  `cvrp_large_twoopt_seed_handoff` and
  `cvrp_large_twoopt_unbounded_default_avoid_handoff` coverage items.
  WSL readiness confirms both roots are statically ready, not started,
  runtime-guard valid, and `prompt_context_readiness_complete=ok`.
- Both current prepared roots have regenerated `prompt_context_readiness`
  handoff artifacts with `ready_for_launch_prompt_audit=true` and
  `missing_required=[]`. They also report
  `prepared_research_focus_prompt_bridge.available=true`,
  `required=true`, source markers true, and launch markers true. Launch markers
  require the prepared manifest file, `launch.env` assignment, and `run.sh`
  export of `PREPARED_RUN_MANIFEST`. Strict WSL readiness reports
  `git_runtime_consistent=ok`; after documentation-only refreshes, a checkout
  mismatch is acceptable only when runtime guard paths are unchanged.
- Launch is still blocked by `gpt-5.5` auth. On 2026-06-18, WSL strict
  readiness for the new CVRP prepared root returned `launch_ready=false`,
  `static_ready=true`, exit `64`, HTTP `401`, classification
  `not_authenticated`, and no active authenticated account in the proxy auth
  pool. The non-active pool state may appear as expired or refreshing.
- Do not launch prepared roots until `/v1/chat/completions` returns HTTP `200`
  with non-empty `gpt-5.5` output.
- Keep the WSL checkout synchronized with the branch before tests or launches.
  Use `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`.

## Next Actions

1. Refresh the WSL/local proxy login, then rerun:
   `scion/tools/check_launch_readiness.py <prepared-root>
   --require-launch-ready --format json`. `/v1/models` is not enough.
2. Before starting a prepared root, require the same launch-readiness report to
   include `launch_ready=true` and
   `checks.prompt_context_readiness_complete.status=ok`.
3. When launch readiness is true, run the prepared CVRP post-pivot follow-up
   first from the clean WSL checkout. Inspect target intent, hypothesis, branch
   lesson transfer, protocol effect-vs-MDE, budget-exhausting runtime feedback,
   source visibility, and postrun research-efficiency reports.
4. Keep the prepared warehouse `v2` follow-up available as the simpler
   continuous-improvement check once LLM access is stable.
5. Keep this file short. Update it only when the operating truth or next action
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
  `scion/docs/experiments/v0.4/v04-research-context-actionability-brief-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-branch-lesson-actionability-reason-mix-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-research-shape-prompt-signal-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-prepared-prompt-context-readiness-handoff-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-size70-active-solver-context-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-vrp-large-instance-two-opt-seed-evidence-20260618.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-large-twoopt-launch-focus-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-large-twoopt-contract-coverage-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-prepared-research-focus-prompt-bridge-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-launch-readiness-prompt-context-guard-repair-20260618.md`,
  and `scion/docs/experiments/v0.4/v04-measurement-integration-real-asset-coverage-20260618.md`.
- WSL reference:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/RSYNC_PATHS.md`.
