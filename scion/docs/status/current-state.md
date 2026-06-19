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
- Problem-owned proposal diagnostics now expose the current CVRP large-instance
  bounded two-opt opportunity and warehouse post-v2 follow-up/plateau evidence
  requirement outside prepared-only roots. These remain tainted proposal
  diagnostics and stay out of `DecisionFeatures`.
- CVRP solver-design code generation now receives provider-owned active subject
  code constraints for the large-instance two-opt follow-up: derive an explicit
  deadline/remaining-time guard, avoid unbounded `_two_opt_intra`/full-VNS
  fallback, preserve feasibility/route-count, and emit activation, budget, and
  direct effect telemetry for postrun pair-level review. CVRP launch readiness
  now requires the prepared prompt-context handoff to prove that this
  code-constraint bridge is present before a prepared root can be static-ready.
- Warehouse code generation also receives provider-owned active subject code
  constraints for the champion-v2 follow-up: preserve/export validation-transfer
  diagnostics, honor lexicographic and bounded-scan guards, and avoid
  unbounded full vehicle-pair scans. Warehouse launch readiness now requires
  the prepared prompt-context handoff to prove that this code-constraint bridge
  is present before a prepared root can be static-ready.
- Current-run postrun analysis can now audit whether actual code prompt traces
  carried active subject code constraints. The manifest/trajectory/brief path
  records section status, required/full-visible/not-full-visible counts,
  payload digest, and constraint/forbidden-pattern counts without storing raw
  prompt text or adding Decision input. CVRP and warehouse current-run
  delegated-analysis readiness now require this trace to be present and
  full-visible whenever a matching code trace exists. Code traces also require
  protected target/integration/algorithm source visibility; missing required
  source paths and partial required hypothesis target-source visibility prevent
  delegated current-run review readiness.
- Adapter-owned measurement/opportunity diagnostics are redacted before prompt
  exposure for raw pair/calibration rows, BKS/gap details, holdout/case details,
  prompt ratios, and LLM text.
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
  evidence. Valid negative conclusions, such as quality-blocked proposals, CVRP
  without a qualifying large two-opt mechanism signal, or CVRP without direct
  two-opt activation/effect/phase telemetry, remain analysis-ready.
- Postrun readiness also rejects stale problem-specific summary contracts:
  `warehouse_followup_summary` and `cvrp_large_twoopt_summary` must use the
  current schema, match the prepared problem family, and use a current
  delegated-review interpretation.
- Warehouse/CVRP postrun readiness also requires current-run
  prompt/source-visibility trace accounting in the analysis brief, including
  hypothesis target-source visibility; otherwise branch transfer and source
  grounding are not auditable enough for delegated current-run review.
- Postrun readiness now binds the selected analysis brief to
  `postrun_acceptance/rebuild/rebuild_manifest.v1.json` and checks both
  rebuild-manifest and analysis-brief run identity, so stale or lexically later
  brief artifacts cannot make delegated current-run review ready.
- Postrun readiness also validates the output files declared by the rebuild
  manifest. A stale directory count or replacement file in the same report
  family no longer makes delegated current-run review ready if the
  manifest-declared artifact is missing.
- Postrun readiness also requires current-run
  `research_context_actionability_summary`, prompt block-family accounting, and
  prompt signal-density token accounting for warehouse/CVRP delegated review.
  This makes branch-transfer and same-mechanism gaps auditable without turning
  research-context quality into Decision, Protocol, scheduler, or promotion
  input.
- Postrun readiness also requires current-run `failure_taxonomy_summary`
  evidence for warehouse/CVRP delegated review. Missing, stale, non-current, or
  empty failure taxonomy now prevents `current_run_analysis_ready=true`, even
  when the hand-written problem summary, prompt/source visibility, and research
  context summaries look actionable.
- Postrun readiness also requires current-run protocol accounting,
  measurement-effect, runtime-feedback, and research-continuity summaries for
  warehouse/CVRP delegated review. A hand-written problem-specific summary no
  longer bypasses missing review-input summaries; runtime feedback must still
  be review-ready with drain status complete.
- Postrun readiness also cross-checks the problem-specific summary's protocol,
  measurement, runtime, continuity, and quality-block evidence against those
  input summaries. A stale or hand-written problem summary can no longer claim a
  protocol-evaluated conclusion when the input summaries disagree.
- Runtime feedback is review-ready only when raw runtime feedback exists and
  both fresh-runtime replay drain status and stage-transition drain status are
  present. Budget diagnostics remain useful for investigation, but they do not
  by themselves make protocol-evaluated warehouse/CVRP postrun review ready.
- Launchers run postrun readiness JSON generation with
  `--require-current-run-ready`, so `POSTRUN_READINESS_EXIT_STATUS` now records
  whether delegated current-run analysis is actually ready.
- Launch readiness now also verifies that prepared `run.sh` contains the strict
  postrun readiness path itself, exposed as
  `run_script_strict_postrun_readiness=ok`; stale scripts that omit
  `--require-current-run-ready` cannot pass static readiness.
- Launch readiness also verifies that the normal campaign-exit path calls
  `write_postrun_acceptance_reports` after `STATUS=$?` and before
  `exit "$STATUS"`, exposed as
  `run_script_postrun_reports_after_campaign=ok`; stale scripts that only
  define the postrun function cannot pass static readiness.
- Warehouse launchers also run postrun report/readiness generation for
  data-root-missing pre-campaign failures, and launch readiness exposes this as
  `run_script_data_root_failure_reports=ok`; infra-only warehouse failures
  should leave delegated-analysis artifacts instead of only `exit.txt`.
- Warehouse and CVRP launchers also run postrun report/readiness generation for
  API-key-env-missing pre-campaign failures, and launch readiness exposes this as
  `run_script_api_key_env_failure_reports=ok`; missing env-var configuration
  should leave delegated-analysis artifacts instead of only `exit.txt`.
- Launch readiness also requires runtime guard coverage for `scion/tools`, the
  postrun/report package subtrees `scion/scion/cli`, `scion/scion/core`, and
  `scion/scion/lineage`, and the matching problem runtime paths
  (`scion/scion/problems/cvrp`, `scion/problems/cvrp`, `vrp` for CVRP;
  `scion/scion/problems/warehouse_delivery`,
  `scion/problems/warehouse_delivery`, `surrogate` for warehouse). Runtime
  guard excludes such as `:(exclude)scion/scion/core` now prevent coverage
  instead of being ignored.
- The remaining v0.4 acceptance question is empirical: prove that the repaired
  framework supports effective agent research, especially warehouse follow-on
  improvement and CVRP/VRP solver-design progress.

Warehouse:

- Positive checkpoint: champion `v2` promoted in the validation-transfer rerun.
  Warehouse is not blocked on basic viability; the open question is whether
  Scion can produce additional useful research from `v2` or correctly diagnose a
  real post-v2 plateau.
- Current prepared root, prepared from WSL checkout `423cf5a`:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-summaryinputguard-6r-gpt55-20260619T082204Z-claw`.
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
- Current prepared root, prepared from WSL checkout `423cf5a`:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-summaryinputguard-1r-gpt55-20260619T082218Z-claw`.
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
  activation/effect/phase telemetry on a matching top effect row. Generic,
  cross-route, unbounded/fallback, VNS, or two-opt-star family labels are listed
  as rejected two-opt-like families instead of making the follow-up review-ready.
  Research-continuity family mentions remain context only.

Infrastructure:

- No LLM campaign is currently running.
- WSL strict launch-readiness for both current prepared roots reports
  `static_ready=true`, `launch_ready=false`, exit `64`,
  `prepared_analysis_brief_current=ok`,
  `prompt_context_readiness_complete=ok`,
  `problem_specific_prepared_handoff=ok`, `postrun_families_complete=ok`,
  `run_script_strict_postrun_readiness=ok`, `git_runtime_consistent=ok`,
  `run_script_runtime_guard_enforced=ok`,
  `run_script_postrun_reports_after_campaign=ok`,
  `run_script_data_root_failure_reports=ok`,
  `run_script_api_key_env_failure_reports=ok`,
  `runtime_guard_paths_cover_launch_tools=ok` with required coverage for
  `scion/tools`, `scion/scion/cli`, `scion/scion/core`, and
  `scion/scion/lineage`, `runtime_guard_paths_cover_problem_runtime=ok` with
  required coverage for the matching problem package/assets/data paths, and
  completion preflight
  `failed`. The warehouse root exposes
  `warehouse_active_subject_code_constraint_source_markers`, and the CVRP root
  exposes `cvrp_active_subject_code_constraint_source_markers`; code prompt,
  context, and provider markers are all true in both roots. Both current root
  `run.sh` files
  execute git dirty/head-mismatch
  runtime guards before `scion.cli.main run`, call postrun report/readiness
  generation after campaign exit and before `exit "$STATUS"`, preserve
  warehouse data-root-missing and API-key-env-missing failures as
  postrun-reportable infra-only roots,
  and include `tools/check_postrun_acceptance.py`,
  `--require-current-run-ready`, and `POSTRUN_READINESS_EXIT_STATUS`.
  The prepared analysis brief contract identity matches the prepared manifest,
  whose git commit is `423cf5a`; after later non-runtime status/test commits,
  strict readiness reports `git_runtime_consistent=ok` with
  `checkout differs, but runtime guard paths are unchanged`. Older prepared
  roots before the summaryinputguard roots above are not current. Exact
  supersession
  details belong in launch/readiness evidence docs, not this operational
  snapshot.
- The current blocker is external WSL `gpt-5.5` provider auth, not Scion static
  readiness. With `SCION_API_KEY=pwd`, `/v1/models` lists `gpt-5.5` but real
  `/v1/chat/completions` preflight returns HTTP `401`,
  `classification=not_authenticated`, `code=invalid_api_key`, with auth pool
  `active=0`, `total=1`, and no launch-usable account.
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
  `scion/docs/experiments/v0.4/v04-launch-readiness-strict-postrun-readiness-guard-20260619.md`,
  `scion/docs/experiments/v0.4/v04-warehouse-data-root-preflight-postrun-report-20260619.md`,
  and
  `scion/docs/experiments/v0.4/v04-api-key-env-preflight-postrun-report-20260619.md`.
  They supersede older prepared-root pointers after launch readiness began
  checking strict postrun readiness markers, campaign-exit postrun calls, and
  warehouse data-root/API-key-env failure report paths in generated `run.sh`.
- Current repair context lives in `scion/docs/experiments/v0.4/`; keep this
  status page focused on operating truth rather than repair chronology.
- WSL reference:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/RSYNC_PATHS.md`.
