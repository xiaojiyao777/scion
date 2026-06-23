# Scion v0.4 Current State

Last updated: 2026-06-23

This file is the operational resume point, not a run log. Replace stale facts
instead of appending history. Put detailed repair evidence in focused
experiment reports, keep sparse milestones in `v0.4-history.md`, and use git
history when exact old chronology is needed.

## Operating Frame

- Branch: `codex/v04-evidence-repair-plan`.
- Boundary authority: `scion/design/scion-architecture-v3.md`.
- v0.4 closes only after Scion demonstrates effective research behavior:
  warehouse should recover useful continuous optimization from champion `v2`,
  and CVRP/VRP should produce evidence-backed solver-design follow-up.
- v0.5 is for broader experiment matrices. Do not defer v0.4 framework
  stability, prompt/context quality, runtime semantics, or effective-agent
  research to v0.5.
- Current posture: avoid broad budgets, generic truncation/compression, and
  decorative gates. Keep CVRP/warehouse semantics problem-owned and keep
  `DecisionFeatures` problem-neutral.
- Current design gate: Designs A-K in
  `scion/design/v0.4-effective-research-repair-design.md` are implemented and
  focused-tested in the current worktree. Scheduler, active-slot inventory, and
  branch cards share one problem-neutral scheduling-status model. Prepared
  manifests carry typed `ResearchGuidanceContract` payloads, generic
  context/readiness code validates schema and rendered-path coverage, and
  CVRP/warehouse guidance remains problem-owned. Free-form
  `opportunity_diagnostics` text remains proposal/reporting material and no
  longer creates actionable-loss fresh-runtime lifecycle or scheduler pressure
  without structured phase or reason-code signal. Lifecycle policy blocks, live
  attempt accounting, and agentic proposal failure routing now require typed or
  exact machine-readable signals before they affect control-plane state.
  Runtime-evidence completeness pressure now yields to current weak-positive
  follow-up when there is no case-level loss. Target-intent authority now
  resolves prepared required mechanisms against existing branch-local
  protected/allowed mechanism authority before final hypothesis generation.
  Protected and allowed mechanism ids use an ordered union, branch-local
  authority normalizes selected target intent to existing-file `modify`, and
  host transport overrides stay outside the intent body. The current worktree
  also implements the Design H/I/J/K follow-ups: typed required mechanisms now
  distinguish hard hypothesis binding from context-only rendered guidance, and
  generated launch wrappers mark root `run_status.json` as running before
  campaign execution. The duplicated CVRP/warehouse outer launcher lifecycle
  is now behind a generic typed lifecycle plan and renderer while problem
  commands and problem-owned guards remain in their launchers. Structured
  declared-mechanism runtime diagnostics now normalize through a generic
  mechanism-evidence contract: `not_evaluated/not_triggered`, wiring-suspect,
  runtime-starved, and effect-attribution cases can become branch-local
  diagnostic follow-up without becoming Protocol gates or Decision input, while
  evaluated no-effect remains no-effect evidence rather than wiring repair. No
  CVRP-specific scheduler, target-intent, launcher-lifecycle, projection, or
  mechanism-evidence exception is accepted. The Design K follow-up also carries
  contract repair ids into protected/allowed mechanism ids, branch-card
  guidance/rendering, scheduler action reasons, and lifecycle classification so
  a not-triggered declared mechanism remains a branch-local integration focus
  rather than open exploration. Local head `dcccbc43` is synced to WSL follow-up
  code commit `650d9c65`; WSL conda passed the Design K/core group
  (`54 passed`), branch/card/telemetry group (`35 passed`),
  screening/protocol group (`30 passed`), py-compile, diff checks, minimal
  launch-readiness/direct launcher entry checks, plus the earlier
  launcher/guidance (`48 passed`) and launch/postrun tool (`227 passed`) groups
  from the same synchronized code line.

## Current Decision

- Framework/readiness/launcher repairs are accepted enough for focused
  warehouse and CVRP follow-up.
- v0.4 is not closed. Warehouse now has positive movement evidence, a
  post-repair current-run-ready partial run, and a current positive-control
  rerun showing that warehouse v2 follow-up was blocked by a guidance-binding
  design mismatch rather than proving a plateau. CVRP now has multiple
  current-run-ready complete post-repair roots showing branch depth, expanded
  screening, MDE-aware rejection, forced non-acceptance target control, clean
  prompt/source evidence, accepted scheduler-status repair, and accepted
  target-intent authority repair. CVRP still lacks a solver improvement or
  promotion. The authority root's postrun actionability gaps have been traced
  to report-classifier false positives and repaired in the current worktree, so
  the next question is solver direction quality and warehouse/CVRP effective
  research behavior rather than more authority-loop or actionability-classifier
  repair. The old-checkout CVRP solver-depth root also exposed the
  mechanism-evidence contract gap: screening rows can declare the target
  mechanism while formal telemetry shows the mechanism was not evaluated or
  triggered. Treat that as integration/activation diagnostic evidence; the
  Design K repair and follow-up focus propagation are now synced to WSL and
  still require a synchronized rerun to prove branch-local diagnostic follow-up.
- Prior CVRP missing-primary follow-up:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-missingprimary-8d28bc30-narrowavoid-4r-gpt55-20260622T171659Z-claw`
  launched from WSL commit `8d28bc30`. It passed postrun acceptance readiness
  with no postrun failures and wrapper exit `0`, but campaign completeness is
  `valid_partial_interrupted`: 3 of 4 requested effective rounds,
  `last_stop_reason=scheduler_active_slot_blocked`, 0 quality blocks,
  0 promotions, champion still `v1`. This verifies the missing-primary
  feedback repair on current evidence (`9faaf70b` is inactive rather than
  weak-positive), but exposes a generic framework blocker: copied or resumed
  weak-positive branches (`bba3d45f`, `ec052599`) can consume all active slots
  even when they are not the next useful research action.
- Current design-first framework repair is in place in the current worktree:
  scheduler, active-slot inventory, and branch cards now route through a
  problem-neutral branch scheduling-status model, and the generic
  research-guidance contract migration is implemented. CVRP and warehouse
  launchers now obtain prepared research guidance from problem-owned providers,
  write typed `research_guidance_contract` payloads, and preserve legacy
  `research_focus` for one compatibility window. Generic projection/readiness
  no longer probes CVRP/warehouse strings; it checks contract schema,
  proposal-only visibility, and rendered-path coverage. Fresh-runtime
  actionable-loss follow-up now uses a shared typed opportunity signal, so raw
  `opportunity_diagnostics` prose and stale/text-only pending replay markers
  cannot schedule replay without current pair-level or structured
  actionable-loss signal. Lifecycle policy-block state mutation now uses typed
  `BranchLifecyclePolicyBlockSignal` or exact policy-check payloads; broad
  lifecycle keyword detection remains report/run-validity compatibility only.
  Proposal/circuit-breaker accounting recognizes repair-first and
  branch-lifecycle policy blocks from exact `RepairPolicyCheck.detail` payloads,
  including agentic wrappers, not from arbitrary failure prose. Live
  `CampaignLoop` attempt accounting requires explicit `StepResult.attempt_kind`
  or existing structured scheduler/reconcile signals for lifecycle, repair,
  same-family, and schema-quality attempt classes.
- Agentic proposal failure routing is now centralized in a typed
  `AgenticFailureRoutingSignal`: typed output timeout/transient categories drive
  framework-control or infra routing, while diagnostic text that merely mentions
  legacy timeout or service keywords stays a proposal/circuit failure.
  Exact policy-check payloads still stay outside proposal streaks.
- Controlled scheduler-status validation roots:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-schedstatus-d75ed849-resume-missingprimary-4r-gpt55-20260623T014159Z-claw`
  launched from WSL commit `d75ed849` after strict readiness passed. It showed
  the intended generic scheduler behavior:
  `9faaf70b` is released from active-slot accounting with
  `inactive_current_evidence_slot_release`; branches
  `c8aa2555-62c0-4d19-b4ba-ac04cea257ea` and
  `08d996dd-8500-445d-98a5-3ded35c1a069` then entered active slots, completed
  effective protocol rows, and were also released as inactive current evidence;
  use this root only as slot-release/progress validation evidence because the
  WSL worktree was later updated while it was live. The clean active validation
  root is
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-schedstatus-d0dded44-clean-missingprimary-4r-gpt55-20260623T025241Z-claw`,
  launched from WSL commit `d0dded44` after strict readiness passed. It
  finished current-run-ready with postrun acceptance exit `0`, 4 of 4 effective
  rounds, 4 protocol-evaluated candidates, 0 quality blocks, 0 promotions,
  `last_stop_reason=max_rounds_exhausted`, and
  `scheduler_active_slot_blocked_attempts=0`. This accepts Design A for the
  generic active-slot blocker. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-scheduler-status-clean-validation-20260623.md`.
  After the same-mechanism scheduler-policy repair, local commit `10707890` was
  synced to WSL as head `09094b5c`; WSL conda `scion` passed scheduler
  runtime-pressure tests (`73 passed`), proposal-boundary/lifecycle tests
  (`68 passed`), and launch readiness (`115 passed`).
- Clean-root same-mechanism audit: the accepted scheduler-status root is not
  solver progress, and it exposed a generic scheduler-policy gap instead of a
  CVRP heuristic gap. Same-mechanism follow-up was observed 4 times and selected
  once. Local replay of the clean root's database after the runtime-pressure
  repair selects an existing weak-positive branch for
  `weak_positive_signal_followup` / `exploit_weak_positive` instead of a clean
  fork. This repair is problem-neutral: weak-positive branches with case losses
  still prefer a clean fork, while current weak-positive branches without case
  loss can receive bounded follow-up. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-weak-positive-runtime-pressure-scheduler-repair-20260623.md`.
- Target-intent authority checkpoint: the postweak-pressure continuity root
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-continuity-77f4abe7-postweakpressure-4r-gpt55-20260623T051921Z-claw`
  remains accepted Design G failure evidence, not solver evidence. It verified
  live `exploit_weak_positive` selection but failed before Protocol because
  prepared `required_mechanism_ids` conflicted with branch-local protected
  mechanism authority. The validation root
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-authority-542d1f99-postweakpressure-4r-gpt55-20260623T055230Z-claw`
  is now accepted Design G framework evidence. It finished with wrapper/postrun
  exit `0`, postrun acceptance `ready`, validity `valid`, completeness
  `complete`, 4 of 4 effective Protocol rows, 0 proposal quality blocks,
  0 active-slot blocks, and `last_stop_reason=max_rounds_exhausted`. Current
  campaign rows show evidence-backed `abandon`, `expand_screening`, and
  `continue_explore`, including branch-local weak-positive follow-up through
  target intent, formal hypothesis/code generation, canary/formal evaluation,
  and screening. This is not solver evidence: champion remained `v1`, there
  were 0 promotions, and all four current rows had median effect at or below
  0 with CI high below the CVRP MDE. The follow-up actionability audit found
  report-classifier noise rather than missing prompt/context evidence:
  accepted clean-fork policy choices no longer count as missed same-mechanism
  opportunities, voluntary branch-lesson usage no longer creates semantic
  gaps, and a temporary postrun acceptance rebuild of this root reports
  `actionability_gaps=[]`, `same_mechanism_missed=0`,
  `branch_lesson_semantic_gap_count=0`, and
  `accepted_clean_fork_policy_choice_count=1`. Detailed reports:
  `scion/docs/experiments/v0.4/v04-cvrp-target-intent-authority-conflict-20260623.md`
  and
  `scion/docs/experiments/v0.4/v04-cvrp-target-intent-authority-validation-20260623.md`.
- WSL `gpt-5.5` auth is no longer the active blocker. Strict readiness passed
  for the latest warehouse and CVRP reruns before launch, and live
  prompt/source evidence passed under the patched postrun checker.
- Latest accepted prompt/source visibility repair: local commit `774c981d` /
  WSL commit `a9a537c4` removes active-subject code-constraint prompt
  truncation, counts cross-branch/branch-lesson sections as
  `cross_branch_lesson` signal, and requires hypothesis target-source
  visibility only when a target-intent preflight or required target source is
  actually present. This stays in proposal/postrun audit paths and does not
  change Decision, scheduler, promotion, or Protocol inputs.
- Existing protected-case and calibration guards remain in force: CVRP
  CMT2/CMT4 review-ready evidence must carry numeric objective/distance deltas,
  and calibration provenance remains proposal-visible summary material, not
  Decision input.
- Latest CVRP direction-control checkpoint: prompt-only default-avoid guidance
  was insufficient, so the current path uses proposal-only schema-preview
  guards, structured `required_mechanism_ids`, target-intent binding, and the
  forced or otherwise audited `local_search.py` target-control path. The
  forced-local root from WSL commit `eb2627e5` finished current-run-ready and
  recovered non-acceptance local-search research, but produced only negative
  solver evidence. The follow-up identity-supported default-avoid repair was
  verified by the WSL commit `f80d990f` root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-avoididentity-f80d990f-postweakid-4r-gpt55-4r-gpt55-20260622T144637Z-claw`.
  That run finished valid/complete with wrapper exit `0`, postrun acceptance
  `ready`, 4 effective screening rows, 0 quality blocks, 0 proposal quality
  blocks, 0 promotions, and champion still `v1`. It crossed the
  proposal/code/Protocol boundary for `large_instance_intra_route_two_opt_seed`.
  The dense candidate (`1d630ce3`) had direct mechanism telemetry and failed
  closed after expansion: 0 case wins, 4 losses, 8 ties, pair result
  9/14/25, median delta `0`, CI `[-0.5, 0]`. The sparse refinement
  (`ec052599`) exposed a framework feedback bug rather than a solver signal:
  raw metrics `5914c858` and `8a325037` showed the declared primary mechanism
  was not evaluated or triggered, but the old feedback tier still preserved it
  as `weak_positive` from pair-level tie noise. Local commit `e9ec3635` and WSL
  commit `01b1abb4` now classify missing primary telemetry as inactive feedback
  before pair-level positive noise. Future relaunches must not treat the stale
  `ec052599` weak-positive branch state as accepted evidence.
- Latest accepted quality-loop guard repair: local commit `11ba7898` / WSL
  commit `7bd1a42c` keeps exact `0` proposal quality-loop budgets disabled, but
  stops repeated quality-block signatures by global signature count instead of
  consecutive-only repetition. This is a fail-closed escape guard, not a broad
  research budget.
- Latest accepted APS recovery repair: local commit `621b9604` / WSL commit
  `43ac9935` keeps normal waiting-approval partial-hypothesis recovery, but
  skips stale `partial_hypothesis_only` reuse whenever current hypothesis
  context carries agentic quality-block feedback. A quality-blocked branch must
  get a fresh proposal attempt instead of replaying the old hypothesis.

## Active WSL Roots

Use WSL for launches and postrun checks:

- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- WSL Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- WSL experiment root: `/home/xjy-ubuntu/research/scion-experiments`

Warehouse evidence root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-33f0e976-transfer-6r-gpt55-20260621T183412Z-claw`
- Campaign completed 6 effective rounds from champion `v2`, reached champion
  `v3`, and produced two promotion dossiers. Campaign status is valid and
  stopped by `max_rounds_exhausted`.
- Wrapper/postrun status is intentionally not accepted as current-run-ready:
  the run exposed pre-repair prompt visibility failures
  (`active_subject_code_constraints` truncation and missing cross-branch
  signal accounting). Treat it as positive research evidence, not final v0.4
  postrun-acceptance proof.

Warehouse post prompt/source-visibility probe root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-306fc271-postrepair-6r-gpt55-20260622T005300Z-claw`
- Strict launch readiness passed from WSL commit `306fc271`; the run produced
  live provider prompt/source evidence sufficient for the patched
  prompt-source visibility check.
- The run was manually stopped with SIGTERM after 5 effective rounds, 8
  screening rows, 5 protocol-evaluated candidates, 0 validation/frozen rows,
  and 313 quality blocks. The run is not accepted as postrun-ready because the
  wrapper status is intentionally failed by the operator stop.
- Interpretation: the result exposed an alternating proposal-quality loop
  between repeated quality-block signatures. The follow-up fix is WSL commit
  `7bd1a42c`; rerun warehouse from that commit or later before drawing a
  plateau conclusion.

Warehouse quality-loop guard root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-84a6d0d0-qloopfix-6r-gpt55-20260622T013700Z-claw`
- Strict launch readiness passed from WSL commit `84a6d0d0`.
- The repaired repeated-signature guard stopped the run after 3 quality blocks
  with `last_stop_reason=repeated_quality_block_signature`, rather than
  repeating hundreds of blocked attempts. Campaign validity is
  `invalid_no_effective_rounds`: 0 effective rounds, 0 screened experiments,
  champion still `v2`.
- Interpretation: guard behavior is fixed, but the run exposed a separate APS
  recovery bug. A quality-rejected waiting-approval partial hypothesis was
  recovered repeatedly instead of allowing quality feedback to drive a fresh
  proposal. The fix is WSL commit `43ac9935`.

Warehouse APS retry evidence root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-60029d30-apsretry-6r-gpt55-20260622T014615Z-claw`
- Strict launch readiness passed from WSL commit `60029d30`.
- The run finished naturally with `wrapper_exit_status=0`,
  `campaign_wrapper_exit_status=0`, `postrun_readiness_exit_status=0`, and
  `postrun_acceptance_status=ready`.
- Campaign status is current-run-ready partial evidence:
  `valid_partial_interrupted`, 3 effective rounds, 3 protocol-evaluated
  candidates, 5 screening rows, 5 quality blocks, 0 promotions, champion still
  `v2`, and `last_stop_reason=repeated_quality_block_signature`.
- Interpretation: the prompt/source visibility checker, repeated quality-block
  guard, and APS quality-feedback recovery are now verified under live provider
  traces. The run is not a promotion result; it is a valid partial warehouse
  research result showing no positive effect at or above MDE in the screened
  rows and a fail-closed plateau/quality-guidance stop. A temporary postrun
  acceptance rebuild with the current actionability classifier reports
  `actionability_gaps=[]`, `same_mechanism_missed=0`,
  `branch_lesson_semantic_gap_count=0`, and
  `accepted_clean_fork_policy_choice_count=4`, so the old same-mechanism
  actionability gap is not a live warehouse blocker.

Warehouse current positive-control root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-positive-65115459-current-8r-gpt55-20260623T084049Z-claw`
- Launched from WSL commit `65115459` after strict readiness passed, resuming
  from the accepted champion-`v2` validation-transfer source campaign.
- The run finished wrapper/postrun-ready with no postrun required failures, but
  it is not warehouse promotion or plateau evidence: campaign validity is
  `valid_partial_interrupted`, with 1 effective round, 1 protocol-evaluated
  screening row, 0 promotions, champion still `v2`, 5 proposal quality blocks,
  and `last_stop_reason=repeated_quality_block_signature`.
- Interpretation: this root exposed a problem-owned guidance binding mismatch.
  Warehouse v2/validation-transfer/runtime typed guidance ids are context and
  evidence axes, while modify-existing operator telemetry must use concrete
  export ids such as `move_order`. Treat the root as accepted trigger evidence
  for the current Design H repair, not as a real plateau conclusion. Detailed
  report:
  `scion/docs/experiments/v0.4/v04-warehouse-guidance-binding-launcher-status-20260623.md`.

CVRP solver-depth old-checkout root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-solverdepth-65115459-postauthority-6r-gpt55-20260623T084213Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-solverdepth-65115459-postauthority-6r-gpt55-20260623T084213Z-claw`.
  WSL postrun acceptance is the authority for this old-checkout run; the local
  mirror preserves artifacts for audit, but local postrun identity checks see
  the WSL `run_root` embedded in rebuild manifests.
- Prepared from WSL commit `65115459` after strict launch readiness passed and
  resumed from the accepted authority validation campaign. It finished before
  the local Design H/I/J/K repairs were synced to WSL.
- The run finished current-run-ready with wrapper/postrun exit `0`, postrun
  acceptance `ready`, validity `valid`, completeness `complete`, 6 of 6
  effective Protocol rows, 6 protocol-evaluated candidates, 0 proposal quality
  blocks, 0 active-slot blocks, champion still `v1`, and
  `last_stop_reason=max_rounds_exhausted`.
- Evidence interpretation: this is framework/integration evidence, not solver
  progress. The postrun brief reports all six rows below CVRP MDE, 0 promotions,
  research continuity `wide_shallow`, max branch depth 1, and no
  large-two-opt direct mechanism signal. The final current screening rows
  declared `large_instance_intra_route_two_opt_seed` while structured telemetry
  showed `not_evaluated/not_triggered` and no matching phase bucket. Interpret
  those rows as Design K trigger evidence: declared mechanisms that are not
  reached by the formal runtime path should create branch-local integration
  follow-up pressure rather than clean-fork breadth or solver-quality
  conclusions. The run has been mirrored locally; the next CVRP solver-depth
  check should launch only from the current clean WSL runner after the tested
  follow-up commit `650d9c65`.

CVRP evidence root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-2e1bc5ae-postrepair-4r-gpt55-20260622T021910Z-claw`
- Launched from WSL commit `2e1bc5ae`; local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-2e1bc5ae-postrepair-4r-gpt55-20260622T021910Z-claw`.
- The run finished naturally with `wrapper_exit_status=0`,
  `campaign_wrapper_exit_status=0`, `postrun_readiness_exit_status=0`,
  `postrun_acceptance_status=ready`, `run_validity_status=valid`,
  `run_completeness_status=complete`, and
  `last_stop_reason=max_rounds_exhausted`.
- Campaign status: 4 effective rounds, 4 consumed proposal attempts, 4
  protocol-evaluated screening rows, 4 formal screened candidates, 0 quality
  blocks, 0 promotions, champion still `v1`.
- Evidence interpretation: this is current-run-ready complete evidence that
  repaired CVRP can perform same-mechanism solver-design follow-up and
  fail-closed rejection. The `rank_gap_annealing_acceptance` branch reached
  depth 4 and selected 3 of 4 same-branch refinement opportunities, but all
  rows remained below MDE and the two positive-looking 32-pair screens reversed
  or weakened under 48-pair expansion (`+142 -> -16` and `+90 -> -72` net
  delta). The final expansion had negative CMT2/CMT3 behavior, so it is not a
  promotion or solver-improvement result. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-rank-gap-acceptance-postrepair-20260622.md`.

CVRP route-pressure follow-up root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nextmech-1aae436c-postrankgap-4r-gpt55-20260622T041502Z-claw`
- Launched from WSL commit `1aae436c` after the rank-gap run; local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-nextmech-1aae436c-postrankgap-4r-gpt55-20260622T041502Z-claw`.
- The run finished naturally with wrapper/postrun exit `0`,
  postrun acceptance `ready`, validity `valid`, completeness `complete`, and
  `last_stop_reason=max_rounds_exhausted`.
- Campaign status: 4 effective rounds, 4 consumed proposal attempts, 4
  protocol-evaluated screening rows, 0 quality blocks, 0 promotions, champion
  still `v1`.
- Evidence interpretation: the run is framework-valid current-run evidence but
  not an effective solver improvement. Despite bounded two-opt being the
  highest-opportunity handoff, all four current rows stayed in
  `route_pressure_acceptance`; 48-pair expanded rows had only `+8` and `+5`
  net raw delta, protected CMT cases were neutral, all rows were below MDE, and
  postrun analysis reported `missing_large_twoopt_mechanism_signal`. Detailed
  report:
  `scion/docs/experiments/v0.4/v04-cvrp-route-pressure-postrankgap-postrun-20260622.md`.

CVRP default-avoid guard probe root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nonaccept-443b1a51-postroutepressure-4r-gpt55-20260622T073501Z-claw`
- Strict launch readiness passed from WSL commit `443b1a51`, but the first
  proposal still selected the acceptance-family target
  `policies/baseline_modules/acceptance.py` with mechanism
  `distance_scaled_sa_reheat`.
- The run was manually stopped before protocol evaluation:
  `last_stop_reason=signal:SIGTERM`, `run_validity_status=invalid_no_experiments`,
  0 effective rounds, and 0 protocol rows.
- Interpretation: this is not solver evidence. It shows that prepared
  default-avoid guidance must be enforced by schema preview before the next
  launch. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-default-avoid-preview-guard-20260622.md`.

CVRP first guarded relaunch root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nonaccept-guard-24b609de-postroutepressure-4r-gpt55-20260622T075205Z-claw`
- Strict launch readiness passed from WSL commit `24b609de`.
- The run failed closed before Protocol rows:
  `last_stop_reason=circuit_breaker`,
  `run_validity_status=invalid_no_effective_rounds`, 0 effective rounds, and 3
  proposal quality blocks.
- Interpretation: schema-preview default-avoid enforcement works as a
  pre-Protocol blocker, but the first matcher was too broad over narrative
  route/seed/VNS terms. The local follow-up patch requires multi-token avoid
  phrases to hit candidate identity fields before matching. Relaunch from the
  synchronized follow-up commit, not `24b609de`.

CVRP tightened-guard relaunch root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nonaccept-tightguard-93a3b3c8-postroutepressure-4r-gpt55-20260622T080005Z-claw`
- Strict launch readiness passed from WSL commit `93a3b3c8`.
- The run failed closed before Protocol rows:
  `last_stop_reason=repeated_quality_block_signature`,
  `run_validity_status=invalid_no_effective_rounds`, 0 effective rounds, 0
  protocol rows, and 3 proposal quality blocks.
- Interpretation: tightened default-avoid matching works and blocks repeated
  acceptance-family proposals pre-Protocol, but the agent still does not choose
  bounded local search unaided. Use the launcher forced-target pass-through for
  the next root instead of another unconstrained relaunch. Do not use the
  discarded forced-local prepared/aborted root created before the generated
  `run.sh` execution block carried `FORCE_ARGS`.

CVRP forced-local-search root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-forced-local-eb2627e5-postroutepressure-4r-gpt55-20260622T081704Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-forced-local-eb2627e5-postroutepressure-4r-gpt55-20260622T081704Z-claw`
- Launched from WSL commit `eb2627e5` with `--force-surface solver_design`,
  `--force-action modify`, and
  `--force-target-file policies/baseline_modules/local_search.py`.
- The root resumes the route-pressure campaign, so its agentic session index
  contains older construction/acceptance sessions. The current forced-local
  path starts at the `local_search.py` sessions and should be interpreted from
  there.
- The restarted run finished naturally with wrapper/postrun exit `0`,
  postrun acceptance `ready`, validity `valid`, completeness `complete`, and
  `last_stop_reason=max_rounds_exhausted`.
- Campaign status: 4 effective rounds, 4 protocol-evaluated screening rows, 4
  formal screened candidates, 0 quality blocks, 0 proposal quality blocks, 0
  validation/frozen/fresh-runtime replay rows, 0 promotions, champion still
  `v1`.
- Evidence interpretation: the framework direction-control path worked. The
  live agent generated and coded local-search mechanisms, Protocol collected
  case-level evidence, mechanism telemetry activated, and Decision/lifecycle
  rejected weak or negative rows. The solver result is negative: the original
  `bounded_interroute_2opt_bridge` had two marginal/negative rows (`-59` and
  `-82` net raw delta), its refinement regressed (`-87` net raw delta, 0 case
  wins, CMT2 loss), and `cmt_slack_aware_segment_swap` was abandoned (`-132`
  net raw delta). All rows were below MDE and had CI high below MDE.
- Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-forced-local-postroutepressure-postrun-20260622.md`.

CVRP next-local default-avoid loop root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nextlocal-6f40ebcb-postforcedlocal-4r-gpt55-20260622T122048Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-nextlocal-6f40ebcb-postforcedlocal-4r-gpt55-20260622T122048Z-claw`
- Launched from WSL commit `6f40ebcb`, resumed from the completed
  forced-local root, and kept the forced target at
  `policies/baseline_modules/local_search.py`.
- Strict launch readiness passed with `launch_ready=true`; completion preflight
  was healthy and the prepared default-avoid count was `18`.
- The run failed closed before Protocol rows:
  `last_stop_reason=circuit_breaker`,
  `run_validity_status=invalid_no_effective_rounds`, 0 effective rounds, 0
  screening rows, 3 proposal quality blocks, wrapper exit `64`, and postrun
  acceptance `failed`.
- Interpretation: the guard is working, including the new
  `bounded_interroute_2opt_bridge` default-avoid entry, but agent target
  selection is still poor. The three blocked attempts matched `pure
  ALNS/no-polish`, `cross-route 2-opt reconnect`, and unchanged
  `bounded_interroute_2opt_bridge`. Do not relaunch the same prepared focus
  unchanged; strengthen positive mechanism targeting first. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-nextlocal-default-avoid-loop-20260622.md`.

CVRP intra-two-opt required-direction loop root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-intratwoopt-4b7e78b7-postavoidloop-4r-gpt55-20260622T123924Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-intratwoopt-4b7e78b7-postavoidloop-4r-gpt55-20260622T123924Z-claw`
- Launched from WSL commit `4b7e78b7`, resumed from the completed forced-local
  root, and kept the forced target at
  `policies/baseline_modules/local_search.py`.
- Strict launch readiness passed with `launch_ready=true`,
  `cvrp_next_required_direction_present=true`, authenticated completion
  preflight, and clean runtime guard.
- The run still failed closed before Protocol rows:
  `last_stop_reason=circuit_breaker`,
  `run_validity_status=invalid_no_effective_rounds`, 0 effective rounds, 0
  screening rows, 3 proposal quality blocks, wrapper exit `64`, and postrun
  acceptance `failed`.
- Interpretation: positive natural-language focus was visible but insufficient.
  The three blocked attempts repeated unchanged `bounded_interroute_2opt_bridge`,
  `cross-route 2-opt reconnect`, and unchanged `bounded_interroute_2opt_bridge`.
  The current repair makes the required mechanism structured:
  `required_mechanism_ids=["large_instance_intra_route_two_opt_seed"]` plus a
  schema-preview guard on `mechanism_changes`. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-intratwoopt-required-direction-loop-20260622.md`.

CVRP required-mechanism schema-guard loop root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-requiredmech-1e4c2dde-postintratwoopt-4r-gpt55-20260622T124949Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-requiredmech-1e4c2dde-postintratwoopt-4r-gpt55-20260622T124949Z-claw`
- Launched from WSL commit `1e4c2dde`, resumed from the completed forced-local
  root, and kept the forced target at
  `policies/baseline_modules/local_search.py`.
- Strict launch readiness passed with `launch_ready=true`, authenticated
  completion preflight, clean runtime guard, and the structured required
  mechanism present in prepared prompt readiness.
- The run failed closed before Protocol rows:
  `last_stop_reason=repeated_quality_block_signature`,
  `run_validity_status=invalid_no_effective_rounds`, 0 effective rounds, 0
  screening rows, 3 proposal quality blocks, wrapper exit `64`, and postrun
  acceptance `failed`.
- Interpretation: this is not solver evidence. The schema-preview guard is
  correctly blocking hypotheses that omit
  `large_instance_intra_route_two_opt_seed`, but the agentic hypothesis session
  was not turning that guard payload into full in-session retry feedback. The
  follow-up retry-feedback repair was synchronized and tested from WSL commit
  `f75cd321`.

CVRP required-mechanism retry target-intent mismatch root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-requiredmechretry-f75cd321-postguard-4r-gpt55-4r-gpt55-20260622T130938Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-requiredmechretry-f75cd321-postguard-4r-gpt55-4r-gpt55-20260622T130938Z-claw`
- Launched from WSL commit `f75cd321`, resumed from the completed forced-local
  root, and kept the forced target at
  `policies/baseline_modules/local_search.py`.
- Strict launch readiness passed with `ready=true`, `static_ready=true`,
  `launch_ready=true`, no failed required checks, and authenticated completion
  preflight.
- The run failed closed before Protocol rows:
  `last_stop_reason=circuit_breaker`,
  `run_validity_status=invalid_no_effective_rounds`, 0 effective rounds, 0
  screening rows, 3 proposal quality blocks, wrapper effective exit `64`, and
  postrun acceptance `failed`.
- Interpretation: the retry-feedback repair partly worked. The first two
  formal hypotheses were rewritten to
  `large_instance_intra_route_two_opt_seed`, but target-intent preflight had
  selected different mechanisms (`intra_route_relocate_polish` and
  `capacity_slack_segment_exchange`), so target-intent binding blocked them
  before code generation. The third attempt again omitted the required id and
  was blocked by the schema-preview guard. This exposed a target-intent
  projection gap, not solver evidence. The follow-up repair projected prepared
  `required_mechanism_ids` into the target-intent prompt and
  deterministically rebinds a non-required preflight mechanism id to the
  prepared id before formal hypothesis binding.

CVRP required-mechanism default-avoid latest root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-deadlinescope-76d02567-postavoidfp-4r-gpt55-4r-gpt55-20260622T134246Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-deadlinescope-76d02567-postavoidfp-4r-gpt55-4r-gpt55-20260622T134246Z-claw`
- Launched from WSL commit `76d02567`, resumed from the completed forced-local
  root, and kept the forced target at
  `policies/baseline_modules/local_search.py`.
- Strict launch readiness passed with `ready=true`, `static_ready=true`,
  `launch_ready=true`, no failed required checks, and authenticated completion
  preflight.
- The run failed closed before Protocol rows:
  `last_stop_reason=repeated_quality_block_signature`,
  `run_validity_status=invalid_no_effective_rounds`, 0 effective rounds, 0
  screening rows, 3 proposal quality blocks, campaign wrapper exit `0`,
  wrapper effective exit `64`, and postrun acceptance `failed`.
- Interpretation: this is not solver evidence, but it validates the previous
  target-intent repair and the deadline-scope default-avoid repair. Current
  target-intent sessions selected `large_instance_intra_route_two_opt_seed`,
  formal binding stayed aligned, and the unbounded/no-deadline fallback was no
  longer the blocker. The remaining blocker is a default-avoid phrase
  false-positive: branch-lesson contrast text carried `route_merge` /
  `cross_route`, and weak identity overlap through generic `route`/`opt` terms
  caused `route-merge absorption` / `cross-route 2-opt reconnect` to block the
  required same-route two-opt seed before code generation.

CVRP required-mechanism Protocol evidence root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-avoididentity-f80d990f-postweakid-4r-gpt55-4r-gpt55-20260622T144637Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-avoididentity-f80d990f-postweakid-4r-gpt55-4r-gpt55-20260622T144637Z-claw`
- Launched from WSL commit `f80d990f`, resumed from the completed forced-local
  root, and kept the forced target at
  `policies/baseline_modules/local_search.py`.
- The run finished naturally with wrapper exit `0`, postrun acceptance
  `ready`, validity `valid`, completeness `complete`, and
  `last_stop_reason=max_rounds_exhausted`.
- Campaign status: 4 effective screening rounds, 4 protocol metric rows, 0
  quality blocks, 0 proposal quality blocks, 0 promotions, champion still `v1`.
- Evidence interpretation: the weak-identity default-avoid repair worked and
  the required direction finally reached code generation and Protocol. Dense
  `large_instance_intra_route_two_opt_seed` was direct-telemetry negative and
  correctly abandoned after expansion. The sparse refinement is not accepted as
  a weak-positive mechanism: raw metrics show its declared primary mechanism was
  not evaluated or triggered in either screening row. Local commit `e9ec3635`
  and WSL commit `01b1abb4` fix the proposal/lifecycle feedback semantics so
  missing primary telemetry outranks pair-level positive noise.

CVRP target-intent authority validation root:

- `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-authority-542d1f99-postweakpressure-4r-gpt55-20260623T055230Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-authority-542d1f99-postweakpressure-4r-gpt55-20260623T055230Z-claw`
- Launched from WSL commit `542d1f99`, resumed from the accepted clean
  scheduler-status campaign.
- The run finished naturally with wrapper/postrun exit `0`, postrun acceptance
  `ready`, validity `valid`, completeness `complete`, and
  `last_stop_reason=max_rounds_exhausted`.
- Campaign status: 4 effective Protocol rows, 4 protocol-evaluated candidates,
  0 proposal quality blocks, 0 active-slot blocks, 0 promotions, champion
  still `v1`.
- Evidence interpretation: Design G is accepted as generic framework evidence.
  Live weak-positive follow-up can now reach branch-local target intent,
  formal hypothesis/code, Protocol screening, expansion, and same-branch
  continuation instead of cycling between target-intent binding and
  same-mechanism guards. This is not solver progress: all current rows are
  below MDE. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-target-intent-authority-validation-20260623.md`.

Before launching any new prepared root, require strict launch readiness from
the same WSL checkout:

```bash
PY=/home/xjy-ubuntu/miniconda3/envs/scion/bin/python
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  "$PY" /home/xjy-ubuntu/research/or-autoresearch-agent/scion/tools/check_launch_readiness.py \
  <prepared-root> --require-launch-ready --format json
```

After a run, inspect `exit.txt`, `run_status.json`, and
`postrun_acceptance/readiness/` on WSL, then mirror the WSL root back to the
server. For WSL-origin roots, WSL postrun acceptance is authoritative; the
local mirror keeps WSL absolute paths in postrun artifacts, so use
`--skip-postrun-check` during mirror-only sync:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  python scripts/sync_wsl_run_root.py <wsl-run-root> \
  --execute --skip-postrun-check --format json
```

Prepared-only mirrors skip current-run postrun acceptance and should return the
rsync/local-status result with `postrun_check_skip_reason=prepared_only_not_launched`;
postrun acceptance remains required on the launch host after an actual launch.

## Preserved Guarantees

Keep this list compact. Detailed field-level evidence lives in `scion/TASK.md`,
the v0.4 planning summary, focused tests, and experiment reports.

- v3 boundary stays hard: LLM output, prompt ratios, branch lessons, repair
  diagnostics, and problem-owned research diagnostics remain proposal/control
  material and excluded from Decision, `DecisionFeatures`, promotion, scheduler
  state, and solver semantics unless explicitly part of Protocol.
- Launch readiness is the operator-facing authority for prepared roots. It
  checks prepared-contract identity, prompt-context bridge, runtime paths,
  model route, completion preflight, private `launch.env` permissions,
  wrapper/campaign marker consistency, and strict postrun rebuild/readiness
  behavior before launch. Low nonzero proposal/APS caps fail readiness; use
  exact `0` when the intended v0.4 behavior is no research-headroom cap. The
  same explicit-disabled convention applies to focused fresh-runtime replay
  drain. Stage-transition drain must also be explicit and positive for the
  current focused launch shape. Prompt-context readiness now exposes compact
  renderer-summary evidence in launch readiness; live provider-prompt evidence
  remains a postlaunch trace requirement.
- Problem-owned diagnostics may guide proposal context, protocol
  configuration, runtime governance, lifecycle policy, and readiness only
  through deterministic, schema-validated fields.
- Measurement readiness records calibration evidence depth as a compact status
  field. Current packaged CVRP and warehouse calibration refs are
  `summary_only`; richer external A/A artifacts must prove replay metadata
  before being labeled `full_replay`.
- Code-phase prompts must retain direct champion/current-branch/target source
  visibility and active problem-owned code constraints. Compression may remove
  boilerplate, not research-object source or active contracts.
- Hypothesis prompts should receive compact mechanism-level branch lessons,
  research-shape diagnostics, and bounded runtime/protocol feedback with
  omission/digest audit markers, not raw long prose or telemetry dumps.
- Active no-effect branch cards, sibling projections, and scheduler policy must
  agree with same-mechanism follow-up policy: ordinary no-effect/tie evidence
  remains schedulable for same-mechanism follow-up and does not emit
  runtime-saturated diversity, clean-fork guidance, or scheduler-origin
  parked-lineage blocks without a Decision-origin park marker. Cross-branch
  repeated-signature pressure preserves current active no-effect diagnostic
  follow-up, portfolio plateau lessons still block unchanged sibling copies,
  and true quality/runtime regression remains fail-closed.
- Runtime semantics must not turn budget-exhausting solver saturation, cached
  ties, comparative runtime-ratio slowdown, or inactive mechanism activation
  into meaningless replay pressure, lifecycle churn, or proposal feedback
  noise. Nominal no-effect/tie runtime summaries remain report-only; generic
  bounded/top-k runtime guidance requires actual comparative slowdown,
  runtime failure, or runtime budget saturation.
- Postrun acceptance must fail closed on missing current-run evidence, stale
  copied resume artifacts, wrapper/postrun status failures, absent source
  visibility, missing interpretation-specific review inputs, or CVRP bounded
  two-opt claims without current-run CMT2/CMT4 protection evidence.
- Screening gate, Decision, proposal feedback, and search memory must agree on
  marginal evidence: high-win-rate, non-negative, sub-practical-delta screening
  evidence is diagnostic follow-up material, not promotable proof. Global
  search-memory AVOID is driven by hard failures, not ordinary repeated
  no-effect/tie diagnostics.

## Problem Frontiers

Warehouse:

- Positive checkpoint: champion `v2` promoted in the validation-transfer rerun.
- Current post-repair checkpoint: APS retry from champion `v2` produced
  current-run-ready partial evidence and correctly stopped on repeated
  quality-block signature after fresh proposal recovery.
- Current positive-control rerun: the champion-`v2` path is still not a plateau
  conclusion. The latest root exposed that context-only warehouse guidance ids
  were being projected as hard hypothesis mechanism ids, conflicting with
  concrete operator telemetry identities. The current local repair separates
  rendered context from hard mechanism binding.
- Next question: rerun the warehouse champion-`v2` positive-control path from
  the current clean WSL runner after the tested follow-up commit `650d9c65` to
  test whether valid operator ids can now pass proposal quality and recover
  useful continuous optimization.
- Accept a plateau conclusion only with protocol evidence below MDE,
  review-ready runtime evidence, and substantive continuity evidence without
  fully missed same-mechanism follow-up opportunities.

CVRP/VRP:

- CVRP now has better target intent, branch-lesson transfer, material solver
  code generation, formal screening, mechanism telemetry, and evidence-backed
  rejection of weak/negative hypotheses under current-run-ready postrun
  acceptance.
- The repaired CVRP framework behavior is much healthier, and the forced-local
  root has now recovered non-acceptance solver research: local-search
  mechanisms were proposed, coded, instrumented, expanded/refined, and rejected
  from complete postrun-ready evidence. This is effective negative research,
  not solver progress; v0.4 still lacks continuous CVRP improvement or
  promotion.
- The required-mechanism root reached Protocol for
  `large_instance_intra_route_two_opt_seed`; the following missing-primary
  repair root from WSL commit `8d28bc30` verified that missing declared primary
  telemetry is now inactive feedback, not weak-positive pair noise.
- The active-slot blocker exposed by the missing-primary root is now repaired
  and accepted by the clean scheduler-status validation root. Do not treat the
  accepted clean root as solver progress: it produced no promotion and all
  available protocol effects were below MDE.
- The clean root's actionability gap was same-mechanism follow-up selection
  (`same_mechanism_followup.selection_rate=0.25`). The generic scheduler-policy
  repair now keeps current weak-positive branches with no case-level loss in
  the weak-positive follow-up lane instead of forcing a clean fork. The next
  exposed blocker was target-intent authority ordering, now repaired and
  accepted by the authority validation root. The follow-up actionability
  classifier audit is also repaired: accepted clean-fork policy choices and
  voluntary branch-lesson usage are report-only diagnostics, not missed
  research-context opportunities. The remaining gap is solver direction quality
  and positive-control effective research, not a need for CVRP-specific
  scheduler, target-intent authority, actionability, or projection exceptions.

## Next Actions

1. Treat the clean scheduler-status validation root and the target-intent
   authority validation root as accepted framework evidence; do not relaunch
   either validation shape unless a later run regresses the generic behavior.
2. Launch the next CVRP solver-depth check only from the current clean WSL
   runner after the tested follow-up commit `650d9c65`; continue CVRP as
   problem-owned solver research, interpret effects against MDE, and do not add
   VRP/CVRP exceptions to generic scheduler,
   proposal authority, actionability, projection, or `DecisionFeatures`.
3. Rerun warehouse from champion `v2` as the simpler positive-control path from
   the same synchronized WSL head. Do not accept the latest quality-blocked
   positive-control root as plateau evidence.
4. Update this file and `scion/TASK.md` only when operating truth changes; keep
   detailed run evidence in focused experiment reports.

## Pointers

- Task and acceptance source: `scion/TASK.md`.
- Current planning summary:
  `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`.
- Boundary and audit basis:
  `scion/design/scion-architecture-v3.md`,
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`, and
  `scion/design/v0.5-evidence-uplift-roadmap.md`.
- Detailed repair/postrun evidence: `scion/docs/experiments/v0.4/`.
- Sparse milestone index: `scion/docs/status/v0.4-history.md`.
- WSL SSH:
  `ssh -i ~/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes -o StrictHostKeyChecking=no xjy-ubuntu@127.0.0.1`.
- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`.
- WSL experiments root: `/home/xjy-ubuntu/research/scion-experiments`.
- WSL Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`.
