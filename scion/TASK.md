# Scion v0.4 Evidence Repair Task

*Branch: `codex/v04-evidence-repair-plan`*
*Status: v0.4 framework/readiness/launcher repairs are accepted enough for
focused warehouse and CVRP follow-up, but v0.4 is not closed until Scion
demonstrates stable effective research behavior. WSL `gpt-5.5` auth has
recovered. Warehouse has renewed positive movement from champion `v2` to `v3`,
and the latest warehouse APS retry root is current-run postrun-ready partial
evidence. CVRP rank-gap, route-pressure, forced-local, required-intra-two-opt,
and missing-primary roots are current-run-ready rejection or repair evidence,
not solver improvements. The CVRP missing-primary run from WSL commit
`8d28bc30` verified the feedback-tier repair but stopped after 3 of 4 requested
rounds with `last_stop_reason=scheduler_active_slot_blocked`; copied/resumed
weak-positive branches consumed all active slots while the current branch was
inactive diagnostic evidence. The clean scheduler-status validation root from
WSL commit `d0dded44`,
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-schedstatus-d0dded44-clean-missingprimary-4r-gpt55-20260623T025241Z-claw`,
is accepted current-run-ready evidence for that generic active-slot blocker:
postrun acceptance exit `0`, 4 of 4 effective rounds,
`last_stop_reason=max_rounds_exhausted`, and
`scheduler_active_slot_blocked_attempts=0`. It is framework validation, not a
solver improvement. The postweak-pressure CVRP continuity root from WSL commit
`77f4abe7`,
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-continuity-77f4abe7-postweakpressure-4r-gpt55-20260623T051921Z-claw`,
verified live `exploit_weak_positive` selection with
`scheduler_active_slot_blocked_attempts=0`, but failed before Protocol rows
because prepared target-intent required-mechanism authority conflicted with
existing branch-local protected mechanism authority. This is Design G
framework failure evidence, not solver evidence. In the current worktree,
`scion/design/v0.4-effective-research-repair-design.md` Designs A-G are
implemented and focused-tested: scheduler, active-slot inventory, and branch
cards consume one problem-neutral scheduling-status model; prepared manifests
carry typed `ResearchGuidanceContract` payloads; generic context/readiness code
validates schema and rendered-path coverage; free-form `opportunity_diagnostics`
text no longer creates actionable-loss fresh-runtime lifecycle or scheduler
pressure; lifecycle policy blocks, live campaign attempt accounting, and
agentic proposal failure routing require typed or exact machine-readable
signals; runtime-evidence completeness pressure now yields to current
weak-positive follow-up when there is no case-level loss; target-intent
authority resolves prepared required mechanisms against existing branch-local
protected/allowed mechanism authority before final hypothesis generation; and
CVRP/warehouse semantics stay in problem-owned providers/tests. Local focused
target-intent/proposal tests passed at head `ac33df06` (`121 passed`); WSL head
`542d1f99` passed the pre-tightening target-intent/proposal set (`118 passed`)
and is running the authority validation root
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-authority-542d1f99-postweakpressure-4r-gpt55-20260623T055230Z-claw`, which has crossed target intent,
branch-local formal hypothesis/code, and formal solver evaluation startup but
is not postrun-accepted evidence until it finishes.*
*Updated: 2026-06-23*

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
- Protocol-evaluated positive effects at or above MDE must be routed as
  continuous-improvement review opportunities, not mislabeled as plateau-ready
  evidence.
- Runtime configuration and observed fast completion are explained by the
  problem/runtime model rather than treated as incidental noise.
- Branch transfer and prompt context are inspected, not inferred from final
  promotion status alone.

## Experiment Defaults

- Use the local `gpt-5.5` model for Scion runs that involve LLM proposal,
  diagnosis, or code-generation calls.
- Treat copied configs, protocol/split/seed hashes, champion versions,
  workspace commits, and run directories as required evidence.
- When runtime caps are size-dependent in the formal protocol, experiment
  reports must say whether a run used the formal policy or a conservative
  approximation such as a uniform time limit.
- Do not treat aggregate win rate as sufficient evidence. Pair-level deltas,
  per-case behavior, seed/RNG sensitivity, runtime events, and branch trajectory
  must be inspected for experiments whose purpose depends on them.
- Resource policy: one or two live cells may run on the 2-core server when they
  are short acceptance checks or single-run diagnostics. Larger matrices and
  long parallel experiments should run on WSL through the reverse SSH channel,
  but only from a synchronized clean runner worktree; do not run new WSL cells
  from an unsynced dirty project tree.

## Required Reading

Every main-thread phase and every Scion subagent brief must start with the v3
architecture baseline:

1. `scion/design/scion-architecture-v3.md`

Task-specific references:

2. `scion/reports/v04-core-framework-code-review-20260611.md`
3. `scion/reports/v04-core-framework-review-20260611.md`
4. `scion/design/v0.5-evidence-uplift-roadmap.md`
5. `scion/design/v0.4-effective-research-repair-design.md`
6. `scion/reports/v04-audit-agent-experiment-guide-20260609.md`
7. `scion/docs/AGENT_ONBOARDING.md`
8. `scion/docs/status/current-state.md`
9. `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`

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

Current-status docs to update when operating truth changes:

- `scion/docs/status/current-state.md`
- `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`
- `scion/TASK.md`

Update `scion/docs/status/v0.4-history.md` only for sparse milestone changes,
not for every prepared root, wrapper failure, or repair-detail checkpoint.

Current checkpoint:

- Warehouse is again a positive v0.4 research-path checkpoint. Fresh WSL root
  `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-33f0e976-transfer-6r-gpt55-20260621T183412Z-claw`
  completed 6 effective rounds, promoted from champion `v2` to `v3`, and
  produced two promotion dossiers. Its wrapper remains postrun-unaccepted
  because the run exposed pre-repair prompt/source visibility gaps; use it as
  effective-research evidence, not final v0.4 acceptance.
- Post prompt/source-visibility warehouse probe
  `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-306fc271-postrepair-6r-gpt55-20260622T005300Z-claw`
  passed strict launch readiness and live provider prompt/source evidence under
  the patched checker, but was manually stopped after 5 effective rounds, 8
  screening rows, and 313 quality blocks because alternating proposal-quality
  failures bypassed the old consecutive-only repeat guard. Treat this as a
  framework escape finding, not a warehouse plateau conclusion.
- Warehouse APS retry root
  `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-60029d30-apsretry-6r-gpt55-20260622T014615Z-claw`
  finished naturally from WSL commit `60029d30`: wrapper exit `0`, postrun
  readiness exit `0`, postrun acceptance `ready`, `valid_partial_interrupted`,
  3 effective rounds, 3 protocol-evaluated candidates, 5 screening rows, 5
  quality blocks, 0 promotions, champion still `v2`, and
  `last_stop_reason=repeated_quality_block_signature`.
  Interpretation: the quality-loop guard and APS quality-feedback recovery are
  now verified under live provider traces. The run is current-run-ready partial
  research evidence and a plateau/quality-guidance signal, not a warehouse
  promotion result.
- CVRP/VRP continuation has current-run-ready complete post-repair evidence:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-2e1bc5ae-postrepair-4r-gpt55-20260622T021910Z-claw`.
  It launched from WSL commit `2e1bc5ae`, finished naturally with wrapper exit
  `0`, campaign wrapper exit `0`, postrun readiness exit `0`, postrun
  acceptance `ready`, validity `valid`, completeness `complete`, and
  `last_stop_reason=max_rounds_exhausted`. Campaign counters: 4 effective
  rounds, 4 proposal attempts consumed, 4 protocol-evaluated screening rows, 4
  formal screened candidates, 0 quality blocks, 0 promotions, champion still
  `v1`. Research behavior is materially improved: the branch reached depth 4
  in the `rank_gap_annealing_acceptance` family, selected same-branch
  refinement for 3 of 4 observed same-mechanism opportunities, retained
  target/source visibility, and interpreted effects against CVRP MDE
  (`mde_at_power_80=9.9`). Result quality is still not a solver improvement:
  both 32-pair positive-looking screens reversed or weakened under 48-pair
  expansion (`+142 -> -16` and `+90 -> -72` net delta), all rows had CI high
  below MDE, and CMT2/CMT3 protection was negative in the final expanded row.
  Treat this as strong evidence that the repaired framework can continue and
  reject CVRP hypotheses, but not as a promotion or v0.4 closure by itself.
  Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-rank-gap-acceptance-postrepair-20260622.md`.
- A follow-up CVRP root
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nextmech-1aae436c-postrankgap-4r-gpt55-20260622T041502Z-claw`
  launched from WSL commit `1aae436c`, resumed from the rank-gap root, and
  also finished current-run-ready: wrapper/postrun exit `0`, validity `valid`,
  completeness `complete`, 4 effective rounds, 4 protocol-evaluated screening
  rows, 0 quality blocks, 0 promotions, champion still `v1`. The agent spent
  all four current rows on `route_pressure_acceptance` rather than the
  bounded-two-opt handoff. Expanded 48-pair rows had only `+8` and `+5` net raw
  delta, protected CMT cases were neutral, all rows were below MDE, and postrun
  analysis reported `missing_large_twoopt_mechanism_signal`. Treat this as
  framework-valid CVRP rejection evidence, not a solver improvement. Detailed
  report:
  `scion/docs/experiments/v0.4/v04-cvrp-route-pressure-postrankgap-postrun-20260622.md`.
- Latest accepted prompt/source visibility repair: local commit `774c981d` /
  WSL commit `a9a537c4` removes active-subject code-constraint prompt
  truncation, classifies cross-branch/branch-lesson prompt sections as
  `cross_branch_lesson`, and conditions hypothesis target-source trace
  requirements on actual target-intent/source requirements. This is
  proposal/postrun audit material only and remains excluded from Decision.
- Latest accepted quality-loop guard repair: local commit `11ba7898` / WSL
  commit `7bd1a42c` keeps proposal quality-loop budgets disabled when set to
  exact `0`, but stops repeated quality-block signatures by global signature
  count rather than consecutive-only repetition. This prevents alternating
  quality-block loops without reintroducing broad research headroom caps.
- Latest accepted APS recovery repair: local commit `621b9604` / WSL commit
  `43ac9935` keeps normal waiting-approval partial-hypothesis recovery, but
  skips stale `partial_hypothesis_only` reuse when the current request carries
  agentic quality-block feedback. This forces a fresh proposal after
  problem-quality rejection instead of replaying the same old hypothesis.
- Latest CVRP direction-control repair: prompt-only default-avoid guidance was
  not enough; a WSL relaunch from commit `443b1a51` still selected
  `policies/baseline_modules/acceptance.py` / `distance_scaled_sa_reheat` and
  was stopped before Protocol rows. The local worktree now carries a
  `proposal.schema_preview` default-avoid guard that consumes proposal-only
  `launch_research_focus` and fails hypotheses matching prepared
  `default_avoid_directions`. The first guarded WSL relaunch from commit
  `24b609de` failed closed before Protocol rows but exposed over-broad
  narrative phrase matching, now tightened so multi-token avoid phrases must
  hit candidate identity fields. A tightened-guard relaunch from WSL commit
  `93a3b3c8` then failed closed on repeated acceptance-family default-avoid
  blocks without Protocol rows. The CVRP launcher now exposes the existing
  `scion run` forced-surface diagnostic path so the next root can force
  `solver_design` / `modify` /
  `policies/baseline_modules/local_search.py`; the launcher template now
  passes those force args in the actual generated `run.sh` execution block, not
  only in command metadata. This remains excluded from Decision, Protocol,
  scheduler, promotion, and solver semantics. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-default-avoid-preview-guard-20260622.md`.
- Latest CVRP forced-local checkpoint:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-forced-local-eb2627e5-postroutepressure-4r-gpt55-20260622T081704Z-claw`
  launched from WSL commit `eb2627e5` with `--force-surface solver_design`,
  `--force-action modify`, and
  `--force-target-file policies/baseline_modules/local_search.py`. The root
  resumes the route-pressure campaign, so its agentic session index includes
  older construction/acceptance sessions; do not treat those as current forced
  target failures. The live forced-local proposal/code path produced
  `bounded_interroute_2opt_bridge` and `cmt_slack_aware_segment_swap` in
  `policies/baseline_modules/local_search.py`, passed schema/target/static
  preview, completed code generation, and finished naturally with wrapper exit
  `0`, postrun readiness exit `0`, postrun acceptance `ready`, validity
  `valid`, completeness `complete`, and
  `last_stop_reason=max_rounds_exhausted`. Campaign counters: 4 effective
  screening rounds, 0 quality blocks, 0 proposal quality blocks, 0 promotions,
  champion still `v1`. The result is effective negative research, not solver
  progress: `bounded_interroute_2opt_bridge` produced two marginal/negative
  rows (`-59` and `-82` net raw delta), its refinement regressed (`-87` net raw
  delta, 0 case wins, CMT2 loss), and `cmt_slack_aware_segment_swap` was
  abandoned (`-132` net raw delta). All rows were below MDE and had CI high
  below MDE. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-forced-local-postroutepressure-postrun-20260622.md`.
  Follow-up launcher focus now carries these failed local-search mechanisms as
  proposal-visible default-avoid directions, with tests covering prepared
  manifest propagation and schema-preview blocking for
  `bounded_interroute_2opt_bridge`. The immediate next-local relaunch from WSL
  commit `6f40ebcb` then failed closed before Protocol rows after three
  default-avoid proposal blocks (`pure ALNS/no-polish`, `cross-route 2-opt
  reconnect`, and unchanged `bounded_interroute_2opt_bridge`), proving the
  guard works but the prepared focus was still too broad. The current launcher
  focus repair narrows the next required prepared direction to
  `large_instance_intra_route_two_opt_seed` as a deadline-aware bounded
  local-search mechanism. Detailed loop report:
  `scion/docs/experiments/v0.4/v04-cvrp-nextlocal-default-avoid-loop-20260622.md`.
- The required-intra-two-opt control chain progressed from natural-language
  focus failure (`4b7e78b7`), through structured required-id guard/retry and
  target-intent binding repairs (`1e4c2dde`, `f75cd321`, `7382a090`), then two
  default-avoid false-positive repairs (`76d02567`, `f80d990f`). The latest WSL
  root
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-avoididentity-f80d990f-postweakid-4r-gpt55-4r-gpt55-20260622T144637Z-claw`
  finally carried `large_instance_intra_route_two_opt_seed` through proposal,
  target intent, code generation, and Protocol. It finished valid/complete with
  postrun acceptance `ready`, 4 effective screening rows, 0 quality blocks, 0
  promotions, and champion still `v1`. Dense intra-two-opt seed evidence was
  direct-telemetry negative and correctly abandoned after expansion. Sparse
  refinement evidence exposed a feedback semantics bug: raw metrics showed the
  declared primary mechanism was not evaluated or triggered, but the old run
  left the branch as `weak_positive`. Local commit `e9ec3635` / WSL commit
  `01b1abb4` now treats missing primary telemetry as inactive feedback before
  pair-level noise. Detailed report:
  `scion/docs/experiments/v0.4/v04-cvrp-intratwoopt-required-direction-loop-20260622.md`.
- Latest accepted postrun guard repair: local commit `5bc93f16` / WSL commit
  `13abbbef` requires CVRP CMT2/CMT4 protected-case summary evidence to include
  numeric objective/distance delta evidence. Feasibility-only, route-count,
  case-name, or free-text continuity payloads cannot make a bounded two-opt
  summary review-ready.
- Latest accepted readiness/status repair: local commit `7f64b381` / WSL
  commit `a7237c88` exposes compact calibration evidence depth
  (`summary_only`, `pair_evidence`, `full_replay`) in measurement readiness
  without leaking replay rows or calibration paths into status consumers.
- Latest accepted handoff compactness repair: local commit `23f2296a` / WSL
  commit `37ff1f45` keeps prepared and live proposal
  `measurement_readiness` compact: no calibration refs or replay rows in the
  readiness subobject, with calibration provenance kept in the sibling
  `calibration` block.
- Latest accepted focused-launch runtime repair: local commit `9b29245e` / WSL
  commit `2b2cd351` exposes both `fresh_runtime_replay_drain_limit` and
  `stage_transition_drain_limit` through `scion run`, campaign composition,
  launcher artifacts, and launch readiness. Current focused roots set
  fresh-runtime replay drain to exact `0` and stage-transition drain to
  explicit `4`, removing hidden post-budget drain behavior inherited from
  core/env defaults while preserving a bounded drain for already queued
  validation/frozen stage work.
- Latest accepted launch-readiness audit repair: local commit `6771a6a4` / WSL
  commit `6b4c70d6` exposes compact prepared prompt-context evidence summaries
  directly in launch readiness. Current roots show prepared renderer evidence,
  not live provider-prompt evidence, and expose the CVRP CMT2/CMT4,
  bounded-two-opt, resume-continuity, CVRP required-evidence, warehouse
  champion-v2, warehouse required-evidence, and active code-constraint checks
  without changing Decision, scheduler, promotion, or Protocol inputs.
- Latest accepted prepared calibration-provenance prompt-bridge repair: local
  commit `ceaf339c` / WSL commit `26a03547` keeps
  `measurement_readiness` reduced and ref-free while surfacing compact
  calibration provenance in the sibling `calibration` block: source artifact
  `sha256` plus whitelisted `calibration_run` summary fields. Prepared
  prompt-context readiness also proves that provenance is rendered into the
  proposal-only research-focus bridge. Raw pair rows and full calibration replay
  details remain out of status and `DecisionFeatures`.
- Scheduler-depth repair is accepted at local commit `e39300f4` / WSL commit
  `896b9c06`: ordinary active no-effect/marginal low-signal branches remain
  schedulable for same-mechanism follow-up, and scheduler-origin park/reclaim
  is not written for ordinary low-signal branches without a Decision-origin
  park marker. Quality-regression slot release and Decision-origin parked
  lineage reclaim remain fail-closed.
- Active WSL roots:
  - Warehouse evidence root:
    `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-33f0e976-transfer-6r-gpt55-20260621T183412Z-claw`
    completed 6 effective rounds and reached champion `v3`, but was generated
    before the latest prompt/source visibility repair and is not final
    postrun-accepted evidence.
  - Warehouse quality-loop guard root:
    `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-84a6d0d0-qloopfix-6r-gpt55-20260622T013700Z-claw`
    launched from WSL commit `84a6d0d0`, passed strict launch readiness, and
    stopped after 3 repeated quality blocks with
    `last_stop_reason=repeated_quality_block_signature`. This proves the
    runaway guard, but produced 0 effective rounds because stale partial
    hypothesis recovery replayed a quality-rejected warehouse hypothesis before
    the APS recovery repair.
  - Warehouse APS retry evidence root:
    `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-60029d30-apsretry-6r-gpt55-20260622T014615Z-claw`
    launched from WSL commit `60029d30`, passed strict launch readiness, and
    finished with wrapper/postrun exit `0`. It is current-run-ready partial
    evidence: 3 effective rounds, 5 screening rows, 0 promotions,
    `champion_version=2`, and fail-closed stop on repeated quality-block
    signature after fresh APS retry behavior was observed.
  - CVRP post-repair evidence root:
    `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-2e1bc5ae-postrepair-4r-gpt55-20260622T021910Z-claw`
    launched from WSL commit `2e1bc5ae`, passed strict launch readiness, and
    finished current-run-ready: wrapper/postrun exit `0`, validity `valid`,
    completeness `complete`, 4 effective rounds, 4 screening rows, 0 quality
    blocks, 0 promotions, and `champion_version=1`. It demonstrates repaired
    CVRP research continuity and fail-closed evidence interpretation, but the
    `rank_gap_annealing_acceptance` mechanism family produced no positive
    effect at or above MDE.
  - CVRP route-pressure follow-up root:
    `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nextmech-1aae436c-postrankgap-4r-gpt55-20260622T041502Z-claw`
    launched from WSL commit `1aae436c`, passed strict launch readiness, and
    finished current-run-ready: wrapper/postrun exit `0`, validity `valid`,
    completeness `complete`, 4 effective rounds, 4 screening rows, 0 quality
    blocks, 0 promotions, and `champion_version=1`. It confirms that another
    acceptance-family path is insufficient: `route_pressure_acceptance` had no
    positive-at-MDE effect and no large-two-opt signal.
  - Latest CVRP missing-primary follow-up root:
    `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-missingprimary-8d28bc30-narrowavoid-4r-gpt55-20260622T171659Z-claw`
    launched from WSL commit `8d28bc30`, passed postrun acceptance readiness,
    and produced current-run partial evidence: wrapper exit `0`, postrun
    failures `0`, `valid_partial_interrupted`, 3 effective screening rows,
    0 quality blocks, 0 promotions, champion still `v1`, and
    `last_stop_reason=scheduler_active_slot_blocked`. The feedback-tier repair
    held: current missing-primary evidence on `9faaf70b` was classified as
    inactive. The remaining blocker is generic active-slot semantics: copied or
    resumed weak-positive branches (`bba3d45f`, `ec052599`) still consumed
    active slots and prevented the fourth round.
  - Clean scheduler-status validation root:
    `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-schedstatus-d0dded44-clean-missingprimary-4r-gpt55-20260623T025241Z-claw`
    launched from WSL commit `d0dded44` and finished current-run-ready:
    postrun acceptance exit `0`, validity `valid`, completeness `complete`,
    4 effective screening rounds, 4 protocol-evaluated candidates,
    0 quality blocks, 0 proposal quality blocks, 0 promotions, champion still
    `v1`, `last_stop_reason=max_rounds_exhausted`, and
    `scheduler_active_slot_blocked_attempts=0`. This accepts Design A for the
    active-slot blocker. The result is not solver progress: all rows were
    below MDE and non-positive. Detailed report:
    `scion/docs/experiments/v0.4/v04-cvrp-scheduler-status-clean-validation-20260623.md`.
  - Design B migration is implemented in the current worktree: CVRP and
    warehouse prepared research guidance live in problem-owned providers,
    launchers write typed `research_guidance_contract` payloads while retaining
    legacy `research_focus`, and generic projection/readiness now checks
    contract schema, proposal-only visibility, and rendered-path coverage
    without interpreting CVRP or warehouse content. Generic schema preview no
    longer turns legacy `default_avoid_directions` free-form text into a hard
    gate, and ordinary pre-protocol patch/contract failures do not create hard
    branch-lesson usage requirements.
  - Design C cleanup is implemented in the current worktree: fresh-runtime
    actionable-loss follow-up now uses a typed
    `FreshRuntimeOpportunitySignal`, free-form `opportunity_diagnostics` prose
    is recorded only as ignored proposal/reporting text, and stale/text-only
    pending replay markers do not materialize scheduler replay without current
    pair-level or structured actionable-loss signal.
  - Lifecycle policy-block cleanup is implemented in the current worktree:
    branch state mutation now requires typed `BranchLifecyclePolicyBlockSignal`
    or exact machine policy-check payloads, while broad keyword classification
    remains report/run-validity compatibility only.
    Proposal/circuit-breaker policy-block accounting now uses exact
    `RepairPolicyCheck.detail` violation parsing, including agentic wrappers,
    so repair-first/lifecycle policy blocks remain structured but free-form
    keyword prose does not suppress failures.
  - Live CampaignLoop attempt accounting is implemented in the current
    worktree: non-counting steps no longer infer lifecycle, repair,
    same-family, or schema-quality control kinds from `StepResult.reason`
    prose. Producers must set typed `attempt_kind`; reason text remains
    reporting material.
  - Agentic proposal-boundary failure routing is implemented in local commit
    `10707890` / WSL head `09094b5c`: typed `AgenticProposalOutput`
    termination/category fields drive timeout and transient-service routing,
    while diagnostic text that merely mentions legacy control-plane keywords
    remains a proposal failure and circuit-breaker event. Exact
    `RepairPolicyCheck.detail` payloads still stay outside proposal/circuit
    streaks.
  - Weak-positive runtime-pressure follow-up is implemented in local commit
    `10707890` / WSL head `09094b5c`: runtime-evidence completeness pressure
    still prefers clean fork for weak-positive branches with case-level losses,
    but it is suppressed for current weak-positive/no-case-loss branches so the
    scheduler can select `weak_positive_signal_followup`. Local replay of the
    clean scheduler-status validation database now selects existing
    weak-positive branch `bba3d45f` for `exploit_weak_positive` instead of a
    clean fork. Detailed repair report:
    `scion/docs/experiments/v0.4/v04-cvrp-weak-positive-runtime-pressure-scheduler-repair-20260623.md`.
  - Target-intent authority resolution is implemented in the current worktree:
    prepared launch-focus `required_mechanism_ids` still bind target intent for
    non-conflicting open/clean-fork contexts, but existing branch-local
    follow-up now resolves authority against protected/allowed branch mechanism
    ids before final hypothesis generation. Protected and allowed ids form an
    ordered authority set, branch-local authority normalizes selected target
    intent to existing-file `modify`, and host transport overrides stay outside
    the intent body. Disjoint prepared ids are recorded as deferred
    proposal-layer diagnostics rather than remaining hard schema requirements
    that conflict with same-mechanism guards. The postweak-pressure continuity
    root is the failure evidence, not solver evidence:
    `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-continuity-77f4abe7-postweakpressure-4r-gpt55-20260623T051921Z-claw`.
    Local head `ac33df06` focused target-intent/proposal tests passed
    (`121 passed`); WSL head `542d1f99` passed the pre-tightening focused set
    (`118 passed`) and is running authority validation root
    `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-authority-542d1f99-postweakpressure-4r-gpt55-20260623T055230Z-claw`.
    The active validation root has crossed target-intent preflight,
    branch-local formal hypothesis binding, code generation, and formal solver
    evaluation startup with no proposal quality blocks or active-slot blocks so
    far, but it is not postrun-accepted evidence until it finishes. Detailed
    failure report:
    `scion/docs/experiments/v0.4/v04-cvrp-target-intent-authority-conflict-20260623.md`.
  - Latest clean WSL authority validation sync before local tightening:
    local commit `43c090fe` was applied to WSL as head `542d1f99`; do not sync
    local head `ac33df06` until the active validation root finishes.
- Current framework guarantees, all report-only/control-plane or problem-owned
  unless explicitly part of Protocol:
  - Measurement declarations and A/A calibration are problem-owned and excluded
    from `DecisionFeatures`.
  - Budget-exhausting runtime semantics suppress stale fresh-runtime replay
    markers/pressure and comparative runtime-ratio slowdown blockers for
    low-SNR follow-up, including the protocol gate and Decision preflight
    paths. Low-SNR trajectory-divergent lifecycle continuation and hard-negative
    fail-closed behavior are covered by focused tests. Postrun runtime budget
    diagnostics preserve saturated-side and repairable counts so delegated
    review can distinguish candidate repair signals from champion-only or
    observational saturation.
  - Launch readiness rejects low nonzero proposal and APS headroom caps while
    accepting exact `0` as disabled, so focused v0.4 roots do not quietly carry
    research truncation through prepared handoff. It also requires the
    fresh-runtime replay drain limit to be explicit across `launch.env`,
    manifest execution, manifest command, and `run.sh`; current focused roots
    set it to `0`. It now also surfaces compact prompt-context renderer-summary
    evidence in the top-level check detail, keeping live provider prompt traces
    as postlaunch evidence.
  - Screening gate reporting and Decision routing agree on marginal evidence:
    high-win-rate, non-negative, sub-practical-delta screening evidence is a
    diagnostic validation candidate (`SCREENING_PASS_MARGINAL_DELTA`) and is
    recorded in proposal feedback/search memory as marginal rather than
    promotable. Search memory uses hard-failure counts for global AVOID and
    does not exhaust ordinary repeated no-effect/tie screening memory, while
    high-win-rate negative median effect remains inconclusive/fail-closed.
  - Active no-effect branch cards now agree with same-mechanism follow-up
    policy: ordinary no-effect/tie evidence keeps same-mechanism diagnostic,
    tune, integrate, repair, parameterize, telemetry-wiring, or observability
    actions visible and does not emit runtime-saturated diversity or clean-fork
    guidance. Cross-branch repeated-signature pressure preserves current
    active no-effect diagnostic follow-up, and portfolio no-effect plateau
    lessons expose the same current-branch diagnostic allowance while still
    blocking unchanged sibling copies; true runtime regression or saturation
    still gets runtime diversity guidance. Scheduler policy keeps those
    ordinary low-signal follow-ups schedulable and does not create
    scheduler-origin parked-lineage blocks unless the branch is truly
    ineligible, quality-regressive, or already parked by Decision.
  - Runtime telemetry summaries distinguish explicit inactive activation
    evidence from numeric zero counters. `candidate_false` and activation
    status `inactive` keep delegated review and proposal feedback from
    confusing a non-triggered mechanism with a no-effect mechanism or
    zero/sub-ms runtime budget evidence.
  - Code-phase prompts preserve target/integration/algorithm source visibility;
    `context.read_algorithm_file`, `context.read_algorithm_symbol`, and
    `context.read_surface` can carry the current 96k source window without
    registry result-cap rejection, shallow-preview symbol misses, code-prompt
    projection shrinkage, symbol-read receipt-only visibility, or unstable
    retry-block placement. Non-solver/operator code prompts also retain
    cacheable active algorithm facts and problem-owned active code constraints
    in the stable system block; prepared readiness verifies the active
    constraint provider payload and actual code prompt rendering by item count,
    version/subject identity, problem-specific guard markers, and
    `DecisionFeatures` exclusion. Current-run postrun readiness audits
    prompt/source visibility, branch state, champion progress, failure
    taxonomy, research-context actionability, signal density, runtime drain
    readiness, and interpretation-specific review inputs.
    Hypothesis prompts render cross-branch maps and branch-lesson context as
    mechanism-level distilled signals with lesson ids, signatures, maturity,
    evidence counts/statuses, and explicit `omitted_*`/digest audit markers
    instead of default-visible raw long lesson prose, raw rows, or large
    branch/case enumerations. Runtime feedback in hypothesis prompts is also
    rendered as bounded screening/verification proposal guidance with explicit
    omitted-line/omitted-char digest markers, so long runtime or telemetry-like
    strings cannot dominate the formal hypothesis prompt while remaining
    excluded from `DecisionFeatures`.
  - Warehouse positive-at-or-above-MDE evidence routes to
    `protocol_evaluated_positive_effect_review_ready`; plateau conclusions
    require plateau-consistent measurement, review-ready runtime feedback, and
    substantive continuity evidence without fully missed same-mechanism
    follow-up opportunities. Quality-blocked no-protocol negative conclusions
    require matching current-run failure-taxonomy evidence.
  - CVRP bounded two-opt review readiness requires a qualifying bounded or
    deadline-aware large two-opt protocol-effect signal plus co-located
    activation/effect/intra-large-two-opt phase telemetry on a matching top
    effect row; seed-only guidance labels, generic/intra-only two-opt-like
    labels, `two_opt_star`/cross-route phases, VNS, unbounded, fallback,
    `size70_two_opt_*` fallback telemetry, unrelated mechanism evidence, and
    continuity-only mentions are not sufficient. Ready summaries must also
    match recomputed direct-evidence counters, mechanism-family lists,
    rejection counts, and top-row signal count from the current
    measurement/continuity inputs. CMT2/CMT4 protected-case evidence must carry
    numeric objective/distance delta evidence; route-count or feasibility-only
    protected-case payloads are rejected.
  - Current-run warehouse/CVRP problem summaries must carry an explicit
    `evidence` payload before delegated review can accept protocol-evaluated,
    plateau, positive-effect, or bounded two-opt conclusions; free-text summary
    claims alone remain insufficient evidence. Their `current_run_evidence`
    flag must also match the analysis brief lifecycle and Phase 4 current-run
    evidence state.
  - Protocol-evaluated warehouse/CVRP problem summaries must match current
    protocol-accounting detail: formal-screened candidates, protocol metric
    rows, formal candidate artifact rows, and stage-row distribution.
  - Current-run warehouse/CVRP measurement evidence must match current
    measurement-effect interpretation counts and `max_effect_to_mde_ratio`; CVRP
    bounded two-opt ready summaries must also match current mechanism-family
    mapped/unmapped row counts.
  - Current-run warehouse/CVRP problem-summary runtime evidence must match
    runtime-feedback raw availability, drain/review readiness, runtime model
    counts, and runtime budget diagnostic counts before delegated review can
    accept the summary as current-run analysis evidence.
  - Current-run warehouse/CVRP problem-summary `interpretation`,
    `evidence_gaps`, `review_axes_actionability`, and launch-required flags
    must match the recomputed problem-specific summary from current
    review-input summaries. Readiness rejects stale or overly optimistic
    delegated-review conclusions even when an omitted gap would otherwise be
    nonblocking.
  - Quality-blocked no-protocol warehouse/CVRP conclusions must match the
    current failure-taxonomy quality-block counts, reports-with-quality-blocks,
    and reason-count distribution; matching only the aggregate blocked count is
    insufficient evidence.
  - Current-run warehouse/CVRP failure-taxonomy summaries must be recomputable
    from the current research-efficiency reports, including aggregate failure
    counts, proposal-quality counts, run-status counts, entries, and top
    examples; entry paths must match current artifact identity through a
    local/WSL-safe path-tail signature. A shape-correct but stale taxonomy
    summary is not delegated-review evidence.
  - Current-run warehouse/CVRP review-input summaries must be current-run when
    required by the interpretation or when present in the brief, so optional
    measurement/runtime/continuity summaries cannot carry stale report-only
    material or stale entry path identity into delegated review.
  - Current-run warehouse/CVRP research-context actionability must be a fresh
    projection of prompt visibility and research-continuity inputs; stale
    prompt token, continuity, gap, recommendation, or prompt-context entry-path
    projections fail postrun readiness before delegated review.
    Human-readable postrun briefs must expose missed same-mechanism follow-up
    directly in continuity/actionability and problem-specific review summaries,
    so plateau or bounded two-opt review cannot depend on a reviewer manually
    subtracting selected from observed opportunities.
  - Agentic proposal recovery can reuse a persisted
    `partial_hypothesis_only` / `hypothesis_awaiting_approval` artifact for the
    same branch and code-phase idempotency key, avoiding duplicate hypothesis
    LLM calls after restart while still rerunning normal anchor, problem
    quality, follow-up, lineage, and ContractGate approval checks. Persisted
    pre-approval patches are never restored.
  - Current-run warehouse/CVRP research-context readiness requires a formal
    hypothesis-generation prompt trace. Code-only prompt manifests and
    target-intent prompts cannot prove that branch-depth, continuity, or
    cross-branch research signals reached the next proposal prompt. When
    current continuity signals exist, readiness now also requires the formal
    hypothesis-generation trace itself, not only aggregate prompt manifests, to
    carry research or cross-branch lesson signal. Formal trace accounting is an
    explicit allowlist of hypothesis generation and retry prompt call kinds;
    unknown `hypothesis_*` labels cannot bypass this requirement.
  - Prepared prompt-context readiness now checks the deterministic
    `research_focus` projection path and required nested projected paths, so
    problem-owned launch guidance such as CVRP CMT2/CMT4 protected cases,
    rules, and required evidence cannot pass only as manifest/report data while
    being absent from proposal prompt focus. It also renders the compact
    hypothesis prompt summary in memory and stores only safe boolean/count/path
    evidence. Exact rendered-path counts live in the prepared readiness
    artifacts; the durable guarantee is `missing_rendered_paths=[]` for the
    required problem-owned `research_focus` projection.
    Prepared prompt-context readiness now also verifies that copied
    campaign-status research-shape diagnostics render into default-visible
    compact research signals with branch-depth, mechanism-family, and
    `DecisionFeatures` exclusion evidence, rather than accepting only source
    marker presence. Active subject code-constraint readiness likewise must
    prove the provider payload reaches the actual code prompt, not only that
    source markers and provider hooks exist.
  - CVRP prepared-run contract checks the same protected cases against the
    configured split manifest's formal screening set; the current root reports
    CMT2 and CMT4 in `screening`, preventing prompt-only CMT2/CMT4 protection
    from becoming a false-ready launch state.
  - CVRP prepared-run handoff now includes proposal-only
    `resume_continuity_requirements`; launch readiness verifies the field is
    projected and rendered into the prepared hypothesis prompt summary. Sparse
    resumes with zero branch cards must use copied target-intent or hypothesis
    trace evidence rather than being treated as empty campaigns.
  - Launch readiness guards the active checkout, absolute WSL `SCION_DIR` /
    `PYTHONPATH`, prepared-handoff identity, completion preflight, model route,
    private `launch.env` permissions, campaign-execution marker placement after
    completion-preflight failure handling with top-level marker status/failure
    evidence, no-early-stop semantics, strict postrun rebuild/readiness,
    committed runtime-guard drift, and wrapper/manifest runtime-guard contract
    consistency.
  - Launcher wrappers now promote strict postrun rebuild/readiness failure to
    an effective wrapper failure and annotate top-level `run_status.json`, so a
    campaign that finishes but lacks current-run-ready postrun acceptance cannot
    look like a successful analysis-ready launch.
  - Postrun inventory fails closed when root launcher `run_status.json` is
    missing or unreadable, or when launcher status exists but campaign execution
    `run_status.json`/`status.json`/`campaign_summary.json` artifacts are all
    missing or unreadable: prepared-only roots remain `prepared_only` resume
    snapshots, missing/unreadable/stale execution artifacts are marked
    invalid-infra-only, and lifecycle/Phase 4 current-run evidence is false in
    both cases before delegated review can treat them as research evidence.
    Launch wrappers write a current campaign-execution marker after
    pre-campaign checks, and launch readiness rejects wrappers that omit that
    marker, place it before completion-preflight failure handling can exit, or
    place it after the campaign command. When the marker exists, stale copied
    resume-campaign documents older than the marker are rejected as
    `campaign_execution_artifacts_stale_resume_snapshot`. Postrun rebuild
    consumes the same lifecycle source and skips
    current-run summary, failure, research-efficiency, and manifest report
    families whenever current-run evidence is false.
  - Current-run postrun readiness also fails closed on missing or nonzero root
    wrapper exit status, nonzero campaign wrapper exit status, top-level
    postrun acceptance failure markers, and nonzero postrun readiness/report
    exit status before delegated review. It also rejects launcher status-writer
    failure markers in `run.log`, postrun acceptance/readiness/report failure
    markers in `exit.txt`, and effective wrapper-exit markers in `exit.txt`, so
    a failed or interrupted status annotation cannot leave a stale clean
    `run_status.json` looking review-ready.
- Current operational truth lives in `scion/docs/status/current-state.md`.
  Detailed repair evidence lives in `scion/docs/experiments/v0.4/`; do not read
  historical experiment reports by default unless the current task explicitly
  needs one.

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

## Current Historical Index

The previous append-only status log has been intentionally removed from this
active task file. It duplicated experiment reports, stale run roots, and older
interpretations that no longer define the v0.4 operating truth.

Use these sources instead:

- Current operational truth: `scion/docs/status/current-state.md`.
- Curated milestone index: `scion/docs/status/v0.4-history.md`.
- Detailed launch, postrun, and repair evidence: `scion/docs/experiments/v0.4/`.
- Exact legacy chronology when needed: git history for this file.

Keep this section short. New facts should update the Current checkpoint above or
the relevant status/experiment report, not recreate an append-only log here.

## Status Cadence

The main thread updates status when the active operating truth changes:

- Phase gate pass/fail decision.
- Experiment result that changes current interpretation or the next action.
- Accepted or rejected subagent work that changes current interpretation or the
  next action.
- Commit that changes task scope, protocol behavior, measurement behavior,
  context composition, runtime governance, or lifecycle policy.

Do not record every launch, rerun, intermediate failure, or subagent exchange in
status docs. Detailed run facts, counters, commands, wrapper status, and
artifact-level caveats belong in launch/postrun reports. `current-state.md`
should stay a short operational snapshot that replaces stale conclusions, and
`v0.4-history.md` should stay a sparse milestone index rather than an
append-only event stream.

Status docs to keep aligned:

- `scion/TASK.md`
- `scion/docs/status/current-state.md`
- `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`

`scion/docs/status/v0.4-history.md` is a sparse milestone index; update it only
when the milestone interpretation changes, not for ordinary current-root refreshes.

## Git Hygiene

- Keep commits sliced by phase or repair surface.
- Do not mix experiment reports, framework repairs, and unrelated cleanup in one
  commit unless explicitly accepted.
- Do not revert user or subagent changes unless explicitly instructed.
- Before each commit, record tests and experiment artifacts used for acceptance.
