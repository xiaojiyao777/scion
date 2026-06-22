# Scion v0.4 Current State

Last updated: 2026-06-22

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

## Current Decision

- Framework/readiness/launcher repairs are accepted enough for focused
  warehouse and CVRP follow-up.
- v0.4 is not closed until the latest current-run-ready evidence is reviewed
  against the effective-research gate. Warehouse now has both positive movement
  evidence and a post-repair current-run-ready partial run. CVRP now has three
  current-run-ready complete post-repair roots showing branch depth, expanded
  screening, MDE-aware rejection, forced non-acceptance target control, and
  clean prompt/source evidence, but still lacks a solver improvement or
  promotion.
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
  was insufficient, schema-preview default-avoid enforcement now blocks
  repeated acceptance-family proposals before Protocol rows, and the launcher
  forced-surface pass-through now reaches the generated `run.sh` execution
  block. The forced-local root from WSL commit `eb2627e5` finished
  current-run-ready with 4 effective screening rows, 0 quality blocks, 0
  promotions, champion still `v1`, and postrun acceptance `ready`. It recovered
  non-acceptance solver research by generating, coding, expanding, refining, and
  rejecting local-search mechanisms in
  `policies/baseline_modules/local_search.py`. The solver evidence is negative:
  all rows were below MDE, all CI highs were below MDE, the refined
  `bounded_interroute_2opt_bridge` regressed, and
  `cmt_slack_aware_segment_swap` was abandoned. Older acceptance sessions in
  its agentic index come from the resumed route-pressure campaign and are not
  current forced-target failures. The launcher prepared focus now carries the
  failed local-search mechanisms as proposal-visible default-avoid directions,
  and schema preview blocks repeated `bounded_interroute_2opt_bridge`
  hypotheses before Protocol rows. The immediate next-local relaunch from WSL
  commit `6f40ebcb` verified that guard but failed before Protocol rows after
  three default-avoid proposal blocks; positive target selection still needs
  repair before another identical forced-local relaunch. The current launcher
  focus now narrows the next required prepared direction to
  `large_instance_intra_route_two_opt_seed` as a deadline-aware bounded
  local-search mechanism instead of leaving that seed as one optional direction
  among many. A launch from WSL commit `4b7e78b7` proved that this
  natural-language positive focus still was not enough: the run failed closed
  before Protocol rows after default-avoid repeats. The current repair now adds
  structured `required_mechanism_ids` and a proposal schema-preview guard that
  requires the hypothesis to declare `large_instance_intra_route_two_opt_seed`
  in `mechanism_changes`.
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
  rows and a fail-closed plateau/quality-guidance stop.

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
- Next question: whether further warehouse work should refine the
  validation-transfer quality guidance (`runtime_bounded_acceptance` /
  `bounded_candidate_policy`) or accept this as a post-v2 plateau/quality
  guidance signal while CVRP remains the v0.4 closure blocker.
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
- Next CVRP work should use the completed forced-local evidence to choose a
  materially different follow-up. Avoid unchanged
  `bounded_interroute_2opt_bridge`, its high-asymmetric-promise refinement, and
  `cmt_slack_aware_segment_swap` unless the causal path is changed. Prefer a
  different bounded local-search or destroy/repair mechanism with direct
  activation-to-objective telemetry and CMT2/CMT4 protection; the prepared
  launcher focus now enforces those avoid directions before Protocol rows. The
  failed next-local and intra-two-opt relaunches show that negative guardrails
  and natural-language positive focus are not enough; the prepared focus now
  has a structured required-mechanism schema-preview guard before spending
  another live root.

## Next Actions

1. Choose the next CVRP mechanism from the completed forced-local evidence.
   Treat the original bridge, its refinement, and the CMT slack segment swap as
   rejected/default-avoid unless a proposal changes the causal mechanism and
   explains the observed A/B/E/P/CMT/X case pattern.
2. Relaunch CVRP only after a clean synchronized WSL commit verifies the
   structured `required_mechanism_ids` schema-preview guard for
   `large_instance_intra_route_two_opt_seed`. The latest next-local and
   intra-two-opt relaunches proved the default-avoid guard works but also
   exposed a default-avoid proposal loop that ignores prompt-only positive
   focus.
3. Do not return to unchanged rank-gap, route-pressure, or generic
   acceptance/adaptive-weight variants unless the prepared research focus is
   explicitly changed. The next CVRP root should keep the forced or otherwise
   audited non-acceptance target-control path until unaided target selection is
   demonstrably reliable.
4. Keep warehouse as current-run-ready partial evidence unless a targeted
   follow-up is needed to refine validation-transfer quality guidance around
   `runtime_bounded_acceptance` / `bounded_candidate_policy`.
5. Update this file and `scion/TASK.md` only when operating truth changes; keep
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
