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

- The v0.4 reporting, launcher, prepared-root, postrun-acceptance, runtime
  semantics, low-SNR continuation, prompt-context handoff, and delegated
  analysis repairs are ready for focused follow-up. These remain
  report/control-plane or problem-owned proposal signals; they do not change
  Decision, `DecisionFeatures`, promotion, scheduler state, or problem solver
  semantics.
- Prepared handoff bundles include report-only analysis brief, artifact
  inventory, launch-readiness, and `prompt_context_readiness` families. Static
  readiness now checks artifact identity, launch markers, problem-specific
  handoff coverage, prepared analysis brief contract identity, and the prompt
  bridge before any prepared root is launched. Launch-readiness reports now
  expose the problem-specific prepared handoff checks directly, instead of
  hiding them behind only `prepared_contract_complete`.
- Prepared-only analysis briefs now use launch/readiness/handoff questions,
  omit current-run branch/LLM/Protocol guidance, and defer specialist
  warehouse/CVRP review axes until post-launch current-run evidence exists.
  Launch readiness now requires those prepared analysis briefs to carry current
  structured prepared-only semantics before a root can be started.
- Postrun analysis now isolates invalid-infra-only roots as non-research
  evidence: copied or partial artifacts remain under `resume_snapshot`,
  current-run counters and Phase 4 coverage are zeroed, and warehouse/CVRP
  summaries classify them as infra-only rather than prepared-only or
  review-ready.
- Launchers now log `POSTRUN_REPORTS_EXIT_STATUS` after postrun acceptance
  rebuilds so delegated review can see whether the report-only bundle rebuild
  succeeded without treating rebuild failure as solver evidence.
- Launchers now also generate postrun acceptance readiness JSON/Markdown under
  `postrun_acceptance/readiness/` and log `POSTRUN_READINESS_EXIT_STATUS`.
  This remains report-only delegated-analysis readiness, not a Decision,
  `DecisionFeatures`, Protocol, promotion, scheduler, or solver change.
- Postrun acceptance readiness now requires the matching problem-specific
  summary for warehouse and CVRP current runs before reporting
  `current_run_analysis_ready=true`.
- Postrun readiness now also fails when the matching problem-specific summary
  exposes blocking gaps such as missing measurement/runtime/continuity inputs,
  incomplete handoff, launch-only state, infra-only state, or no protocol
  evidence. Valid negative conclusions, such as quality-blocked proposals or
  CVRP without a large two-opt mechanism signal, remain analysis-ready.
- Warehouse/CVRP postrun readiness also requires current-run
  prompt/source-visibility trace accounting in the analysis brief, including
  hypothesis target-source visibility; otherwise branch transfer and source
  grounding are not auditable enough for delegated current-run review.
- Launchers run postrun readiness JSON generation with
  `--require-current-run-ready`, so `POSTRUN_READINESS_EXIT_STATUS` now records
  whether delegated current-run analysis is actually ready.
- Launch readiness now also verifies that prepared `run.sh` contains the strict
  postrun readiness path itself, exposed as
  `run_script_strict_postrun_readiness=ok`; stale scripts that omit
  `--require-current-run-ready` cannot pass static readiness.
- The remaining v0.4 acceptance question is empirical: prove that the repaired
  framework supports effective agent research, especially warehouse follow-on
  improvement and CVRP/VRP solver-design progress.

Warehouse:

- Positive checkpoint: champion `v2` promoted in the validation-transfer rerun.
  Warehouse is not blocked on basic viability; the open question is whether
  Scion can produce additional useful research from `v2` or correctly diagnose a
  real post-v2 plateau.
- Current prepared root, prepared from WSL checkout `f1ee04e`:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-f1ee04e-6r-gpt55-20260619T025919Z-claw`.
- The handoff exposes the warehouse v2 checkpoint, plateau question,
  default-avoid directions, required evidence, and decision-boundary coverage.
  Because the root is prepare-only, required answers focus on
  launch/readiness/handoff rather than research-quality or plateau conclusions;
  the warehouse specialist review axes are marked deferred until post-launch
  current-run evidence exists.
- Postrun warehouse plateau review readiness now requires substantive
  research-continuity evidence, such as branch depth, same-mechanism follow-up,
  branch-lesson transfer, or weak-positive transfer. A shallow continuity block
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
- Current prepared root, prepared from WSL checkout `f1ee04e`:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-f1ee04e-1r-gpt55-20260619T025920Z-claw`.
- The handoff exposes the large-instance two-opt seed only as proposal guidance
  and now carries structured `large_instance_two_opt_constraints`: derive an
  explicit deadline/remaining-time guard, avoid unbounded `two_opt_intra`/VNS,
  preserve feasibility/route-count evidence, and require pair-level objective,
  feasibility, route-count, and wall-clock evidence. Because the root is
  prepare-only, required answers focus on launch/readiness/handoff rather than
  research-quality or bounded-twoopt conclusions; the CVRP specialist review
  axes are marked deferred until post-launch current-run evidence exists.
- Postrun bounded two-opt review readiness now requires a large/two-opt
  protocol-effect row signal in measurement evidence. Research-continuity family
  mentions remain context only and cannot by themselves make the two-opt
  follow-up review-ready.

Infrastructure:

- No LLM campaign is currently running.
- WSL strict launch-readiness for both current prepared roots reports
  `static_ready=true`, `launch_ready=false`, exit `64`,
  `prepared_analysis_brief_current=ok`,
  `prompt_context_readiness_complete=ok`,
  `problem_specific_prepared_handoff=ok`, `postrun_families_complete=ok`,
  `run_script_strict_postrun_readiness=ok`, `git_runtime_consistent=ok`, and
  completion preflight `failed`. Both current root `run.sh` files include
  `tools/check_postrun_acceptance.py`, `--require-current-run-ready`, and
  `POSTRUN_READINESS_EXIT_STATUS`.
  The prepared analysis brief contract
  identity matches the prepared manifest, including the manifest git commit.
  Later docs-only commits may make the checkout differ from a prepared manifest
  commit; readiness remains acceptable only when runtime guard paths are
  unchanged.
- The current blocker is external `gpt-5.5` auth, not Scion static readiness:
  `/v1/chat/completions` returns HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`, with proxy auth pool `active=0`, `expired=1`,
  `refreshing=0`, `total=1`.
- Do not launch prepared roots until
  `scion/tools/check_launch_readiness.py <prepared-root> --require-launch-ready --format json`
  reports `launch_ready=true`.

## Next Actions

1. Refresh the WSL/local proxy login, then rerun strict launch readiness on the
   prepared root to be started. `/v1/models` is not enough.
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
  `scion/docs/experiments/v0.4/v04-launch-readiness-strict-postrun-readiness-guard-20260619.md`.
  It supersedes older prepared-root pointers after launch readiness began
  checking strict postrun readiness markers in generated `run.sh`.
- Current repair context:
  `scion/docs/experiments/v0.4/v04-launch-readiness-strict-postrun-readiness-guard-20260619.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-twoopt-protocol-signal-postrun-guard-20260619.md`,
  `scion/docs/experiments/v0.4/v04-warehouse-continuity-substance-postrun-guard-20260619.md`,
  `scion/docs/experiments/v0.4/v04-postrun-readiness-blocking-summary-gaps-20260619.md`,
  `scion/docs/experiments/v0.4/v04-postrun-readiness-prompt-source-visibility-guard-20260619.md`,
  `scion/docs/experiments/v0.4/v04-invalid-infra-postrun-evidence-isolation-20260619.md`,
  `scion/docs/experiments/v0.4/v04-postrun-report-status-marker-20260619.md`,
  `scion/docs/experiments/v0.4/v04-postrun-acceptance-readiness-checker-20260619.md`,
  `scion/docs/experiments/v0.4/v04-postrun-problem-summary-readiness-guard-20260619.md`,
  `scion/docs/experiments/v0.4/v04-postrun-readiness-exit-status-guard-20260619.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-large-twoopt-postrun-summary-guard-20260619.md`,
  `scion/docs/experiments/v0.4/v04-warehouse-plateau-review-inputs-guard-20260619.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-large-twoopt-bounded-handoff-repair-20260619.md`,
  `scion/docs/experiments/v0.4/v04-prepared-only-minimum-analysis-guidance-20260619.md`,
  and `scion/docs/experiments/v0.4/v04-prepared-only-specialist-axes-deferred-20260619.md`.
- WSL reference:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/RSYNC_PATHS.md`.
