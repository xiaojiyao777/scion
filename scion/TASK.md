# Scion v0.4 Evidence Repair Task

*Branch: `v0.4-dev`*
*Last updated: 2026-07-08*

This is the active task definition for closing v0.4. It is not a run log.
Historical launch/root details live in focused experiment reports, sparse
milestones live in `scion/docs/status/v0.4-history.md`, and exact legacy
chronology remains available through git history.

## Basis

Primary sources:

- `scion/design/scion-architecture-v3.md`
- `scion/reports/v04-core-framework-review-20260611.md`
- `scion/reports/v04-core-framework-code-review-20260611.md`
- `scion/design/v0.5-evidence-uplift-roadmap.md`
- `scion/reports/v04-task-basis-alignment-audit-20260629.md`
- `scion/docs/status/current-state.md`

Current judgment after the basis audit and warehouse provenance clarification:
v3 boundaries and the main v0.4 framework repairs are broadly aligned, but
v0.4 is not closed. Recent successor work through successor35 leaves CVRP with
no promotion-grade solver effect.
Successor21 tested `operator_pair_destroy_size_bands`, not the intended
stagnation schedule, and stayed below MDE. Successor22b correctly targeted
`stagnation_adaptive_destroy_size_schedule`, but formal q traces showed zero
aligned q difference versus champion and both rows had median delta `0.0`.
Successor23 repaired the observable q trajectory but produced no row at or
above MDE, missed explicit q-audit fields, and parked the branch as quality
regression. Successor28 completed valid/complete/postrun-ready but tested
alternative non-seed destroy/repair clean forks, not a true protected
`route_pair_overlap_removal` continuation; both rows failed screening with
negative medians. Successor29 then forced the true protected
`route_pair_overlap_removal_protected_followup` mechanism and completed
valid/complete/postrun-ready, but both rows failed screening with negative
aggregate medians. The route-pair-overlap line should now be parked for v0.4.
Successor30 then tested the materially different
`bounded_cross_route_double_bridge_polish` local-search line, completed
valid/complete/postrun-ready, and stayed exact zero-effect in both screening
rows. Treat unchanged double-bridge polish as reviewed/default-avoid too.
Successor31 then tested the materially different
`adaptive_embedded_vns_runtime_allocation` scheduler/runtime-allocation line,
completed valid/complete/postrun-ready, observed direct mechanism runtime, and
still stayed exact zero-effect in both screening rows. Treat unchanged adaptive
embedded-VNS runtime allocation as reviewed/default-avoid too.
Successor32 then tested `post_repair_effect_credit_weighting`, an
`acceptance_or_adaptive_weighting` clean fork owned by
`policies/baseline_modules/scheduler.py`. The target-bound run completed
valid/complete/postrun-ready and proved the new target-intent-required binding
kept live proposals on the intended mechanism, but both screening rows had
median delta `0.0`, CI `[0.0, 0.0]`, `rows_at_or_above_mde=0`, and no
promotion signal. Treat unchanged post-repair operator-credit weighting as
reviewed/default-avoid too.
Successor33 then tested `neighbor_list_vns_filter` in
`policies/baseline_modules/local_search.py`. The second customer-adjacency
candidate passed screening and validation with active telemetry, but frozen
abandoned it for six candidate-side large-instance timeouts. Successor34 then
tested `frozen_safe_neighbor_list_vns_filter`; it completed valid/complete/
postrun-ready and removed the frozen timeout blocker, but stayed weak-positive
below MDE (best median `0.25`, CI high `3.25`) and CMT2 remained negative.
Treat unchanged successor34 as reviewed/default-avoid for v0.4. Successor35 is
now complete: `capacity_tightness_removal` activated, but both screening rows
were solver-negative (`median_delta=-6.0` and `-3.5`, `rows_at_or_above_mde=0`)
with CMT2 negative in both rows. Treat unchanged capacity-tight removal as
reviewed/default-avoid. Successor36 then exposed a static-quality recognizer
gap for the promoted `seed_post_optimization_selector` activation repair:
generated `seed_selector.py` candidates had direct `record_move(..., delta=...)`
telemetry, but the recognizer had not yet included `seed_selector.py`.
Successor36b reran after the recognizer repair and completed valid/complete/
postrun-ready with active direct telemetry, but both screening rows had zero
aggregate medians, no positive row at MDE, and CMT2 regressed. Treat unchanged
seed-post selector variants as reviewed/default-avoid. Successor37 then ran
the no-force clean-fork slot and completed valid/complete/postrun-ready with no
proposal-quality, model, telemetry, verification, or postrun failure.
`route_angle_aware_2opt_star` was negative and abandoned; `edge_frequency_
penalty_repair` was weak-positive below MDE, but direct-effect-zero and lost
all CMT2/CMT4 seeds. Treat both unchanged successor37 mechanisms as
reviewed/default-avoid. The proposal-control repair has now been designed and
implemented as a CVRP-owned causal-path hypothesis-quality contract before
successor38. Successor38 completed valid/complete/postrun-ready: the contract
blocked the first weak causal-path hypothesis before code generation, but the
accepted `radial_2opt_star_relink` candidate was active-no-effect, with zero
accepted mechanism moves, zero direct mechanism best delta, all case gates tied,
and `mechanism_contract_status=observed_no_effect`. Treat unchanged
`radial_2opt_star_relink` as reviewed/default-avoid and do not long-run or
same-branch follow up despite weak pair-level lifecycle noise. The next CVRP
slot should clean-fork to a materially different problem-owned causal path with
direct accepted-move/objective-effect evidence and CMT2/CMT4 protection.
Successor39 is now preregistered as `bounded_dual_repair_selector` in
`policies/baseline_modules/scheduler.py`: a proposal-only target-intent-bound
ALNS repair-choice experiment that compares the selected repair against one
bounded alternate repair before VNS, while leaving construction, destroy
operators, local search, acceptance, adaptive scoring, and embedded-VNS runtime
allocation unchanged. The first successor39 launch root
`/home/clawd/research/scion-experiments/v04-cvrp-successor39-bounded-dual-repair-selector-server-2r-gpt55-20260706T003754Z-claw`
was stopped after a stale successor32 scheduler guard blocked the correct
successor39 mechanism; it is not solver evidence. The guard was retargeted to
successor39 and the clean retry root
`/home/clawd/research/scion-experiments/v04-cvrp-successor39-bounded-dual-repair-selector-server-retry-2r-gpt55-20260706T004158Z-claw`
completed valid/complete/postrun-ready with local `gpt-5.5`, four normal model
calls, two screening rows, and no promotion. Row 1 had median delta `0.0`, CI
`[-3.5, 6.5]`; row 2 had median delta `0.75`, CI `[-6.25, 6.5]`; both CI highs
were below the 9.9 MDE. Treat unchanged `bounded_dual_repair_selector` as
reviewed below-MDE evidence, not a long-run candidate. The successor39 trace
audit exposed a prompt/context quality issue: prepared evidence obligations
were visible in broad focus context but were compressed before code generation.
The current checkout now preserves those obligations as a dedicated
`Prepared Research Obligations` prompt section and rejects truncated
target-file previews as sufficient solver-design grounding. The stale
successor36/39 file-level focus gate has been removed from the CVRP hypothesis
quality contract; current target binding now comes from prepared
`target_intent_required_mechanism_ids`, while reviewed/default-avoid and
causal-path gates still block repeated weak mechanisms. Successor40 is now
complete. The server-local target-intent-bound run
`/home/clawd/research/scion-experiments/v04-cvrp-successor40-bounded-two-for-one-exchange-server-2r-gpt55-20260706T035458Z-claw`
completed valid/complete/postrun-ready with local `gpt-5.5`, two effective
screening rows, and no promotion. Row 1 added
`bounded_two_for_one_exchange` in `policies/baseline_modules/local_search.py`
and had median delta `0.0`, CI `[-6.0, 1.0]`, pair W/L/T `9/12/11`, and
case W/L/T `1/1/6`; A-n64 was positive but CMT2 and X regressed. Row 2 refined
the same mechanism with load-imbalance and margin gating, reduced runtime and
many losses into ties, but still had median delta `0.0`, CI `[-2.0, 0.0]`,
pair W/L/T `4/8/20`, case W/L/T `1/2/5`, and residual B/CMT2 losses. Both CI
highs were below the 9.9 MDE. Treat unchanged `bounded_two_for_one_exchange`
and guarded same-mechanism threshold/gating follow-ups as reviewed below-MDE
evidence, not long-run candidates. The postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor40-bounded-two-for-one-exchange-postrun-20260706.md`.
CVRP research guidance now exposes successor40 as reviewed/default-avoid
evidence, and the hypothesis-quality default-avoid gate blocks unchanged
`bounded_two_for_one_exchange` repeats. Successor41 completed valid screening.
The server-local target-intent-bound run
`/home/clawd/research/scion-experiments/v04-cvrp-successor41-route-skeleton-regret-repair-server-claw-2r-gpt55-20260706T053608Z-claw`
completed valid/complete/postrun-ready with local `gpt-5.5`, two effective
screening rows, and no promotion. Candidate 1 activated
`route_skeleton_regret_repair` but was negative: median delta `-6.0`, pair
W/L/T `6/19/7`, with CMT2 `0/4/0` and CMT4 `1/3/0`. Candidate 2 added a
guarded same-mechanism variant and improved to marginal but still below
promotion: median delta `0.0`, pair W/L/T `13/14/5`, case winners A/B, case
losses P/CMT4, and CMT4 median `-16.0`. Treat successor41 as valid active
marginal evidence, not a long-run candidate. Do not rerun the unchanged
scheduler helper implementation. The postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor41-route-skeleton-regret-repair-postrun-20260706.md`.
Successor41b is now complete. The server-local diagnostic run
`/home/clawd/research/scion-experiments/v04-cvrp-successor41b-route-skeleton-diagnostic-server-claw-2r-gpt55-20260706T065434Z-claw`
completed valid/complete/postrun-ready with local `gpt-5.5`, two effective
screening rows, and normal model/tool accounting. Both rows screened all 48
pairs with zero failed pairs but stayed below MDE: row 1 had pair W/L/T
`17/17/14`, median delta `0.0`, mean `-0.12`; row 2 had `12/15/21`, median
`0.0`, mean `0.56`. Postrun classified max median delta as `0.0`,
effect-to-MDE as `0.0`, and no promotion signal. P/B/E-family losses remained,
and CMT2 was not forced into the measured case set even though CMT2 is present
in the split manifest. Treat `route_skeleton_regret_repair` as
diagnostic-exhausted reviewed/default-avoid evidence: no long-run, no
same-mechanism threshold tuning, and no further route-skeleton repair
optimization follow-up in v0.4. The postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor41b-route-skeleton-diagnostic-postrun-20260706.md`.
The next CVRP slot must keep the causal-path gate, surface the exact
`material_difference.changed_dimensions` / `contrast` / `evidence` schema, and
force CMT2/CMT4 protected-case coverage or record an explicit measurement
caveat before clean-forking to a materially different CVRP-owned causal path.
The successor42 prelaunch repair design is
`scion/docs/experiments/v0.4/v04-cvrp-successor42-protected-case-schema-repair-design-20260706.md`:
generic protocol selection now supports configured screening
`priority_case_ids`, CVRP formal screening declares CMT2/CMT4 as those priority
cases, and raw metrics record configured/requested/effective priority-case
coverage. This is a research-entry/protocol repair, not a solver mechanism.
The first successor42 validation root
`/home/clawd/research/scion-experiments/v04-cvrp-successor42-cleanfork-protected-schema-repair-server-claw-2r-gpt55-2r-gpt55-20260706T091154Z-claw`
on launcher commit `bb65bd47` completed invalid with zero effective protocol
rows after the CVRP causal-path quality gate repeatedly blocked hypotheses
that missed the exact `material_difference` and clean-fork diversity evidence
schema. Trace audit showed this was a prompt-contract assembly gap, not a
model, protocol-selection, or measurement failure: the exact
`material_difference.changed_dimensions` / `contrast` / `evidence` shape was
not prominent in fresh clean-fork hypothesis prompts. The CVRP-owned solver
design prompt contract has now been repaired on commit `ff2258f3` without
moving CVRP semantics into generic scheduler/decision code. Successor42b then
completed as the short server-local retry:
`/home/clawd/research/scion-experiments/v04-cvrp-successor42b-cleanfork-prompt-contract-retry-server-claw-2r-gpt55-2r-gpt55-20260706T092004Z-claw`
with local `gpt-5.5`, `--rounds 2`, `--completion-preflight`, full proposal
context, and resume-from successor41b. It was valid/complete/postrun-ready
with two effective screening rows. The exact schema appeared in the prompt,
the first hypothesis passed the causal-path gate as
`elite_route_memory_repair`, and CMT2/CMT4 priority-case coverage appeared in
effective priority ids. The framework repair is accepted. Solver evidence is
not: row 1 was marginal with median delta `0.0`, CI `[-7.5, 3.75]`, and
CMT2/CMT4 losses; row 2 expanded to 64 pairs and stayed marginal with median
delta `0.0`, CI `[-6.0, 2.0]`, pair W/L/T `29/28/7`, and case losses on
P-n101, CMT2, CMT4, and X-n110. The mechanism had direct telemetry, but the
direct signal did not produce promotion-grade or protected-case-safe evidence.
Treat unchanged `elite_route_memory_repair` and same-mechanism template/count
tuning as reviewed/default-avoid for v0.4. The postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor42b-cleanfork-prompt-contract-retry-postrun-20260706.md`.
Successor43 is now complete. The server-local target-intent-bound run
`/home/clawd/research/scion-experiments/v04-cvrp-successor43-bounded-destroy-operator-shadow-selector-server-claw-2r-gpt55-2r-gpt55-20260706T114850Z-claw`
completed valid/complete/postrun-ready with local `gpt-5.5`, two effective
screening rows, and no quality/model/telemetry/verification/postrun failure.
The raw `bounded_destroy_operator_shadow_selector` mechanism strongly activated
with direct pre-VNS selector telemetry, but stayed marginal below MDE and was
protected-case unsafe. Row 1 screened 48/48 pairs with W/L/T `28/15/5`,
median delta `2.25`, CI `[-2.25, 8.25]`; row 2 expanded to 64/64 pairs with
W/L/T `33/22/9`, median delta `2.25`, CI `[-3.5, 8.0]`. CMT2 stayed negative,
CMT4 was mixed/negative, and B/P-family cases were systematically loss-prone.
Trace audit found design-contract gaps rather than context failure: shadow
trials reused main RNG, selected alternate destroy operators were not returned
for scheduler attribution, adaptive weights/traces credited the default
destroy, and diagnostics did not fully expose default-versus-alternate state.
Treat unchanged successor43 raw shadow selection as reviewed/default-avoid.
The postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor43-bounded-destroy-operator-shadow-selector-postrun-20260706.md`.
Successor43b is now complete. The only allowed protected same-line follow-up,
`bounded_destroy_operator_shadow_selector_protected_followup`, repaired much of
the successor43 mechanism contract while staying inside the CVRP-owned
destroy-shadow selector boundary: RNG state was isolated for the alternate
shadow trial and selected destroy-operator attribution was wired back into the
scheduler. It still failed as solver evidence. The fresh server-local run
completed valid/complete/postrun-ready with local `gpt-5.5`, two effective
screening rows, and no proposal/model/telemetry/verification/postrun failure,
but both rows were below the 9.9 MDE. Row 1 was negative (formal case W/L/T
`2/4/6`, pair W/L/T `19/27/2`, median delta `-1.0`, CI `[-6.0, 1.5]`);
row 2 was low-SNR marginal below MDE (case `5/3/4`, pair `23/22/3`, median
`2.0`, CI `[-3.25, 5.5]`). Combined pair evidence was `42/49/5` with median
about `-1.0` and delta sum `-86`; CMT2, CMT4, and B-n67 remained unsafe. Trace
audit found no target binding or code-prompt truncation failure, but did find
incomplete default/alternate diagnostics and a telemetry-risk pattern where
pre-VNS selector deltas can overstate final trajectory effect. Treat
successor43b as reviewed/default-avoid optimization evidence. Do not long-run,
threshold-tune, or continue the destroy-shadow selector line in v0.4. The
postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor43b-destroy-shadow-protected-followup-postrun-20260706.md`.
The first successor43b resume launch
`/home/clawd/research/scion-experiments/v04-cvrp-successor43b-destroy-shadow-protected-followup-server-claw-2r-gpt55-2r-gpt55-20260706T133342Z-claw`
is invalid with zero experiments: the inherited campaign state filled all
three active slots and stopped at `scheduler_active_slot_blocked`. Do not treat
it as solver evidence. The valid successor43b screening root is the fresh
server-local root
`/home/clawd/research/scion-experiments/v04-cvrp-successor43b-destroy-shadow-protected-followup-fresh-server-claw-2r-gpt55-2r-gpt55-20260706T133531Z-claw`
on commit `f8383943`.
Successor44 is now complete as diagnostic evidence, not a promotion candidate.
The design repaired selector telemetry hygiene and preregistered the materially
different `post_vns_best_anchor_acceptance_guard` acceptance-policy path. The
first root
`/home/clawd/research/scion-experiments/v04-cvrp-successor44-post-vns-best-anchor-acceptance-guard-server-claw-2r-gpt55-2r-gpt55-20260706T154957Z-claw`
was stopped before solver evidence after repeated quality blocks and
scheduler-owned effect telemetry rejections. The retry root
`/home/clawd/research/scion-experiments/v04-cvrp-successor44b-post-vns-best-anchor-acceptance-guard-retry-server-claw-2r-gpt55-2r-gpt55-20260706T160018Z-claw`
launched from commit `89055c89` with local `gpt-5.5`, passed completion preflight,
and completed screening plus validation before being manually stopped. Screening
was `32/32` valid, W/L/T `19/6/7`, median delta `+4.5`; validation was `32/32`
valid, W/L/T `15/3/14`, median delta `0.0`, mean `+21.40625`. Mechanism
activation was observed, but first-candidate mechanism effect telemetry stayed
zero, so the result is best interpreted as conservative acceptance-policy
trajectory filtering. The automatic same-mechanism diagnostic follow-up was
stopped because it credited ordinary ALNS/VNS best/current improvements to the
acceptance guard, which would pollute mechanism attribution. Do not long-run or
continue that telemetry-credit repair. Any successor44 follow-up must first
redesign acceptance-policy effect attribution, otherwise clean-fork to a
materially different CVRP-owned causal path.
Successor44c implemented that attribution-contract repair in commit `2bcf831a`
and completed a valid two-row server-local screen:
`/home/clawd/research/scion-experiments/v04-cvrp-successor44c-attribution-contract-repair-server-claw-2r-gpt55-20260707T051421Z-claw`.
It produced one formal candidate and two screening rows for the same candidate.
The original row was `32/32` valid, W/L/T `17/9/6`, raw pair median `+4.5`;
the expanded row was `48/48` valid, W/L/T `28/15/5`, raw pair median `+1.5`.
Postrun max median was `+7.5` against MDE `9.9`, so no row was positive at MDE.
The attribution repair worked: activation/activity telemetry was observed and
the candidate did not add fake successor44 direct-effect `record_move` deltas.
Successor44d then implemented the CVRP-owned policy-effect warning hygiene
repair in commit `150ab7de` and completed a valid two-row server-local screen:
`/home/clawd/research/scion-experiments/v04-cvrp-successor44d-policy-effect-warning-hygiene-server-claw-2r-gpt55-20260707T070106Z-claw`.
The repair worked: both screening rows kept
`mechanism_contract_status=policy_outcome_observed`, no repair ids, no
telemetry warnings/failures, and no generic `record_move(delta=...)` repair
advice. The generated successor44d patch also did not add fake direct-effect
telemetry; it only added guard `record_iteration`/`record_phase` evidence.
Solver evidence stayed weak-positive screening only. The original row was
`32/32` valid, W/L/T `14/7/11`, raw pair median `0.0`; the expanded row was
`48/48` valid, W/L/T `27/14/7`, raw pair median `+3.0`, branch CI `[0.0, 7.25]`,
and `runtime_confidence=low_cached_champion`. CMT2 was mildly positive, CMT4
neutral, and B-family cases regressed. Do not long-run unchanged successor44d.
The next CVRP slot should be design-first: either design one explicit
successor44 follow-up with guard allow/reject trajectory evidence and a
narrower causal claim, or clean-fork to a materially different CVRP-owned path.
v0.5 governance ablation is preregistered but must not start during v0.4, and
future code work must follow the design-first modularization plan rather than
add helper/projection growth.

## Objective

v0.4 must prove that Scion can support effective agent research before v0.5
starts broad experiment matrices. Do not defer framework stability, runtime
semantics, measurement readiness, prompt/context quality, or effective research
behavior to v0.5.

Effective research means:

- agents continue, reject, park, and clean-fork based on evidence;
- low-SNR CVRP evidence is interpreted against A/A MDE and case variance;
- warehouse remains a positive effective-research control;
- CVRP/warehouse facts stay problem-owned;
- generic core stays problem-neutral and deterministic;
- `DecisionFeatures` excludes LLM prose, raw problem diagnostics, raw
  calibration rows, BKS/case-gap facts, prompt text, and branch-lesson prose.

## Operating Principles

1. Use `scion-architecture-v3.md` as the boundary authority.
2. Keep measurement declarations and opportunity diagnostics problem-owned.
3. Treat budget-exhausting runtime ratios as observational for anytime solvers
   while preserving comparative runtime evidence where valid.
4. Do not add CVRP/VRP/warehouse exceptions to generic scheduler, protocol,
   lifecycle, prompt, or runtime code.
5. Do not use broad budgets, truncation, compression, or decorative gates as a
   substitute for measurement and evidence quality.
6. Preregister v0.5 governance on/off experiments, but do not run the broad
   matrix as a v0.4 closure requirement.
7. Before touching oversized production/test files, write or update a
   modularization design that names ports/providers and ownership boundaries.
8. Do not accrete helper functions as the default implementation style. Design
   the module/package boundary first; keep single files short enough to audit;
   make each functional module an independent, coherent package when behavior
   is larger than a narrow local patch.

## Phase Status

| Phase | Status | Current judgment |
|---|---|---|
| Phase 0 evidence baseline | Complete enough | Detailed run history moved to experiment reports and git history. |
| Phase 1 A/A calibration | Complete enough | CVRP and warehouse A/A artifacts exist; CVRP MDE is high enough that many screening losses are measurement-power limited. |
| Phase 2 framework repairs | Mostly complete | Runtime semantics, branch depth, prepared successor focus, proposal routing, postrun readiness, and context visibility have been materially repaired. |
| Phase 3 measurement declarations | Implemented | `MeasurementConsumerView` and problem-owned measurement specs feed protocol/runtime/proposal consumers without leaking raw diagnostics into `DecisionFeatures`. |
| Phase 4 focused validation | Active | Warehouse effective-research evidence is restored; CVRP framework behavior is repaired but solver improvement remains open. |
| Phase 5 governance comparison | v0.5 handoff only | v0.4 should prepare the design and avoid starting broad governance matrices under unresolved v0.4 debt. |

## Current Acceptance State

Accepted framework evidence:

- v3 `DecisionFeatures` boundary remains intact.
- Problem-owned measurement declarations, practical deltas, runtime model, MDE,
  opportunity summaries, and postrun review summaries are wired into proposal
  and readiness paths without becoming Decision input.
- `runtime_model=budget_exhausting` suppresses meaningless comparative runtime
  pressure for CVRP-like anytime solvers while keeping raw evidence.
- CVRP can now execute evidence-backed continuation, MDE-aware rejection,
  branch parking, reviewed/default-avoid successor guidance, suppression of
  inactive mechanisms, and clean-fork behavior.
- Prepared launch research obligations now flow through target-intent,
  hypothesis, and code prompts as a first-class proposal-only contract rather
  than being left to compressed hypothesis summaries.
- Solver-design target grounding no longer accepts truncated file previews as
  sufficient source for modify/remove binding; full file content or a full
  target slice is required.
- Warehouse v2 positive-control evidence supports restored effective research
  and plateau-review readiness for v0.4 framework purposes.
- Postrun/readiness work has moved toward typed ports and problem-owned review
  providers instead of adding more generic problem semantics.

Open blockers before v0.4 closeout:

- CVRP has no promotion-grade solver improvement yet. Successor19 was valid and
  mechanism-active but below MDE. Successor20 completed on WSL as a valid,
  postrun-ready same-branch refinement of `bounded_route_segment_exchange`, but
  remained solver-negative for closeout. Successor21 completed on WSL as a
  valid scheduler destroy-size attempt, but the actual mechanism
  `operator_pair_destroy_size_bands` stayed below MDE and failed closed on the
  expanded row (`median_delta=-5.5`, CI `[-8.0, 2.75]`, CMT4 median `-2.0`).
  Successor22b completed on WSL as the intended
  `stagnation_adaptive_destroy_size_schedule`, but it was an inactive
  q-trajectory no-op: `0 / 505` aligned ALNS iterations changed q in row 1,
  `0 / 737` changed q in row 2, and both rows had median delta `0.0`.
  Successor23 then repaired the q trajectory but stayed solver-negative:
  row 1 median delta `0.0`, CI `[-2.0, 3.5]`; row 2 median delta `-0.5`,
  CI `[-3.0, 3.25]`; `rows_at_or_above_mde=0`; the branch parked as
  quality regression and did not emit explicit `baseline_q/adapted_q/q_delta`
  runtime fields. Successor24 then completed on WSL as a valid
  `lookahead_insertion_cost_repair` clean fork, but both the original and v2
  follow-up stayed solver-negative: row 1 median delta `-0.75`, CI
  `[-5.5, 0.5]`; row 2 median delta `-2.0`, CI `[-12.0, 1.5]`; v2 also
  recorded direct-effect-zero telemetry. Successor25 then completed on WSL as
  a valid `cw_sweep_seed_baseline_selector` construction clean fork, but both
  rows had median delta `0.0`, CI `[0.0, 0.0]`, and no row at or above MDE.
  Successor26 first exposed a static-quality recognizer gap, not solver
  evidence. Successor26b then completed as a valid server-local rerun of the
  repaired short-horizon construction seed trajectory selector path: both rows
  reached screening, but `short_horizon_seed_trajectory_selector` stayed at
  median delta `0.0`, CI `[0.0, 0.0]`, and
  `short_horizon_seed_trajectory_selector_v2` stayed below MDE with median
  delta `-5.0`, CI `[-8.0, 9.0]`, and CMT2/CMT4 losses. Successor27 then
  completed on the server-local runner as a valid non-seed destroy/repair
  clean fork, `route_pair_overlap_removal`. Both screening rows were positive
  but below MDE: row 1 median delta `0.75`, CI `[-4.5, 12.5]`; row 2 median
  delta `2.5`, CI `[-7.75, 7.0]`, effect/MDE `0.253`. A/B/X case medians
  showed useful gains, but CMT2/CMT4/P-family losses remained. Treat
  successor27 as an active marginal-positive signal, not promotion evidence and
  not a reason to expand unchanged. Successor28 did not answer that
  same-mechanism question because it tested adjacent destroy/repair clean
  forks, and both were negative. Successor29 then forced the required
  `route_pair_overlap_removal_protected_followup` mechanism; it completed two
  screening rows with activation observed, but both rows failed screening:
  row 1 median delta `-1.75`, CI `[-6.75, 8.5]`, win rate `0.25`; row 2
  median delta `-3.75`, CI `[-7.5, 12.0]`, win rate `0.25`, and
  direct-effect-zero telemetry. CMT2 stayed `-10.0` in both rows, CMT4 stayed
  negative, and `rows_at_or_above_mde=0`. Treat the route-pair-overlap line as
  reviewed/default-avoid for v0.4 unless a future proposal names a materially
  different causal path. Successor30 then forced
  `bounded_cross_route_double_bridge_polish` in
  `policies/baseline_modules/local_search.py` and completed
  valid/complete/postrun-ready with no postrun failures. The first proposal was
  correctly blocked before screening because it claimed a cross-route
  double-bridge mechanism while implementing a single-route operation. Two
  later screening rows reached the required mechanism, but both had median
  delta `0.0`, CI `[0.0, 0.0]`, win rate `0.0`, `rows_at_or_above_mde=0`, and
  `max_effect_to_mde_ratio=0.0`. Direct phase telemetry observed mechanism
  activation/runtime, but effect-zero diagnostics reported
  `candidate_present=64`, `candidate_positive=0`, and `candidate_zero=64`.
  Treat unchanged bounded cross-route double-bridge polish as
  reviewed/default-avoid; `continue_explore` here is lifecycle bookkeeping, not
  solver-positive v0.4 evidence. Successor31 then forced
  `adaptive_embedded_vns_runtime_allocation` in
  `policies/baseline_modules/scheduler.py` and completed
  valid/complete/postrun-ready with no quality, model, telemetry, or postrun
  failures. The required mechanism reached formal screening and phase runtime
  telemetry was present, but both rows had median delta `0.0`, CI high `0.0`,
  win rate `0.0`, `rows_at_or_above_mde=0`, and
  `max_effect_to_mde_ratio=0.0`. Treat unchanged adaptive embedded-VNS runtime
  allocation as reviewed/default-avoid; runtime-share movement and
  `continue_explore` are not solver-positive evidence. Successor32 then forced
  `post_repair_effect_credit_weighting` in
  `policies/baseline_modules/scheduler.py` after adding a proposal-only
  target-intent-required binding. The target-bound run completed
  valid/complete/postrun-ready with no proposal-quality, model, telemetry, or
  postrun failures, and both live hypotheses stayed on the intended mechanism.
  The mechanism activated and emitted direct internal effect telemetry, but
  objective evidence remained zero at the case gate: both rows had median delta
  `0.0`, CI `[0.0, 0.0]`, `rows_at_or_above_mde=0`, and
  `max_effect_to_mde_ratio=0.0`; pair evidence was only one small loss in row 1
  and one seed-level win in row 2. Treat unchanged post-repair effect credit
  weighting as reviewed/default-avoid; target binding is framework-positive,
  not solver-positive. Successor33 then forced `neighbor_list_vns_filter` in
  `policies/baseline_modules/local_search.py` and completed
  valid/complete/postrun-ready with no model, quality, telemetry, or postrun
  failure. Its first candidate was negative, but the second customer-adjacency
  filter passed screening (`20/6/6`, median `6.25`) and validation (`24/7/1`,
  median `7.75`) before frozen failed on six candidate-side timeouts across
  large X cases. Successor34 then tested `frozen_safe_neighbor_list_vns_filter`
  and completed valid/complete/postrun-ready. It removed the frozen timeout
  blocker but did not preserve enough solver signal: the best row had median
  delta `0.25`, CI `[0.0, 3.25]`, no positive-at-MDE evidence, and CMT2 median
  `-11.0`. Treat unchanged successor34 as reviewed weak-positive below MDE.
  Successor35 then clean-forked to `capacity_tightness_removal` in
  `policies/baseline_modules/destroy_repair.py` and completed
  valid/complete/postrun-ready with no proposal-quality, model, telemetry, or
  postrun failures. It was mechanism-active but solver-negative: row medians
  were `-6.0` and `-3.5`, `rows_at_or_above_mde=0`, win rate `0.125` in both
  rows, and CMT2 stayed negative. Treat unchanged capacity-tight removal as
  reviewed/default-avoid. Successor36 was a static-quality recognizer-boundary
  block rather than solver evidence. Successor36b completed the same seed-post
  selector design after the recognizer repair and is valid solver evidence, but
  it stayed zero aggregate / no-positive-at-MDE with CMT2 regression. Treat
  unchanged `seed_post_optimization_selector` as reviewed/default-avoid.
- Several production/test files remain over the 1000-line risk threshold and
  need design-first modularization before more behavior is added there.
- v0.5 governance ablation is preregistered as a clean experiment matrix, but
  it is a v0.5 task and must wait for v0.4 closeout.

## Current CVRP Direction

Do not repeat unchanged reviewed paths. The latest completed CVRP invocation
is successor44d: the CVRP-owned policy-effect warning hygiene repair for
`post_vns_best_anchor_acceptance_guard` completed valid/complete and verified
that no-direct-effect acceptance-policy evidence is summarized as
`policy_outcome_observed`, not as a generic direct-effect repair obligation.
It also produced weak-positive screening evidence, but not promotion evidence:
the expanded row was `48/48` valid with W/L/T `27/14/7`, raw pair median
`+3.0`, branch CI `[0.0, 7.25]`, `runtime_confidence=low_cached_champion`,
CMT4 neutral, and B-family regressions. Do not long-run unchanged successor44d.

Successor45, `bounded_repair_placement_tournament`, is now complete and is
reviewed/default-avoid evidence. It was a CVRP-owned clean fork in the
destroy/repair placement boundary, not a new VRP solver. The short
server-local run launched from commit `a0df42bf` with local `gpt-5.5`,
healthy completion preflight, and resume-from successor44d:
`/home/clawd/research/scion-experiments/v04-cvrp-successor45-repair-placement-tournament-server-claw-2r-gpt55-2r-gpt55-20260707T091750Z-claw`.
It finished valid/complete/postrun-ready with no quality/model/telemetry/
postrun failure and one formal candidate. The mechanism activated and showed
local pre-VNS repair-placement effect, but final objective evidence was not
promotion-grade: expanded median delta `-2.75`, CI `[-6.5, 3.25]`, case-gate
W/L/T `5/4/3`, CMT2 `-3.5`, CMT4 `-7.0`, and P-family/CMT3 losses. Trace
audit found no target-binding or code-prompt truncation failure; the main
lesson is that local same-removed-set repair-placement gains did not preserve
final ALNS/VNS trajectory quality. Do not long-run, threshold-tune, or continue
unchanged repair-placement tournament variants. The postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor45-repair-placement-tournament-postrun-20260707.md`.

Successor46 is now complete and reviewed/default-avoid as unchanged solver
evidence. The target-intent-bound server-local run launched from commit
`593d4320` with local `gpt-5.5`, healthy completion preflight, and resume-from
successor45:
`/home/clawd/research/scion-experiments/v04-cvrp-successor46-best-solution-ruin-recreate-intensification-server-claw-2r-gpt55-2r-gpt55-20260707T115720Z-claw`.
It finished valid/complete/postrun-ready with two screening rows, no
quality/model/postrun failure, and all eight current-run LLM calls on
`gpt-5.5`. Target intent, formal hypothesis, and code stayed bound to
`best_solution_ruin_recreate_intensification`, but final objective evidence was
zero: both rows had median delta `0.0`, CI `[0.0, 0.0]`, case-gate W/L/T
`0/0/28`, pair W/L/T `4/4/104`, and `rows_at_or_above_mde=0`. Row 1 did not
activate the mechanism; row 2 observed only sparse runtime (`62 ms`) and zero
final best-solution effect. Trace audit found no provider, target binding, or
code-context failure. The generated implementation failed the intended contract
by consuming the main RNG on rejected attempts, triggering too rarely, and not
separating rejected/budget/infeasible/no-improvement outcomes. Do not long-run,
threshold-tune, or repeat unchanged successor46. Postrun report:
`scion/docs/experiments/v0.4/v04-cvrp-successor46-best-solution-ruin-recreate-intensification-postrun-20260707.md`.

Successor46b is complete and reviewed/default-avoid:
`best_solution_ruin_recreate_intensification_activation_repair` repaired
activation visibility but did not produce promotion-grade solver evidence. The
server-local `claw` run launched from commit `1f121f3b` with local `gpt-5.5`,
completion preflight `ok: true`, and resume-from successor46:
`/home/clawd/research/scion-experiments/v04-cvrp-successor46b-best-solution-activation-contract-repair-server-claw-2r-gpt55-2r-gpt55-20260707T150022Z-claw`.
It finished valid/complete/postrun-ready with seven `gpt-5.5` LLM calls, no
schema/model/quality/telemetry failure, row medians `0.0`, CI highs `0.5` and
`1.0`, aggregate pair W/L/T `20/10/82`, aggregate case W/L/T `5/0/23`, and
`rows_at_or_above_mde=0`. Activation improved to `29/48` and `41/64`, but CMT2
remained unsafe with median `-3.5` in both rows and CMT4 tied without
mechanism-level proof. Park the best-solution ruin/recreate line for v0.4.
Postrun:
`scion/docs/experiments/v0.4/v04-cvrp-successor46b-best-solution-activation-contract-repair-postrun-20260708.md`.

Successor47 is complete and reviewed/default-avoid:
`bounded_giant_tour_split_recombination` preserved the intended CVRP module
boundary in `policies/baseline_modules/giant_tour_split.py`, but did not
produce promotion-grade solver evidence. The short server-local run launched
from commit `00bfeb60` with local `gpt-5.5`, completion preflight `ok: true`,
and resume-from successor46b:
`/home/clawd/research/scion-experiments/v04-cvrp-successor47-bounded-giant-tour-split-recombination-server-claw-2r-gpt55-2r-gpt55-20260708T021541Z-claw`.
It finished valid/complete/postrun-ready with seven successful current-run
LLM calls, aggregate pair W/L/T `49/50/13`, official aggregate case W/L/T
`12/11/5`, row medians `0.0`, current-head median `0.5`, CI `[-6.0, 4.5]`,
and no promotion. Mechanism runtime was observed, but direct positive
mechanism best delta appeared in only `1/64` expanded-row candidate runs, and
CMT2/CMT4 were unsafe. Trace audit found no fatal prompt truncation, model
call, target-binding, or v3-boundary failure. Park contiguous giant-tour split
recombination for v0.4; do not long-run, threshold-tune, or create an
unchanged successor47b. Postrun:
`scion/docs/experiments/v0.4/v04-cvrp-successor47-bounded-giant-tour-split-recombination-postrun-20260708.md`.

Successor48 is now designed as the next materially different CVRP-owned
recombination clean fork:
`bounded_route_pool_set_partition_recombination` in the new module
`policies/baseline_modules/route_pool_recombination.py`, with minimal scheduler
wiring only. It should build a small ephemeral route pool from complete
feasible routes already seen in the current solve, select whole routes through
a bounded exact-cover/set-partitioning subproblem, and accept only strict
final `total_distance` improvement while preserving feasibility and route
count. Required evidence includes route-pool source counts, exact-cover
candidate count, accepted set-partition delta, separated reject/budget counts,
and CMT2/CMT4 priority-case safety. Design:
`scion/docs/experiments/v0.4/v04-cvrp-successor48-route-pool-set-partition-recombination-design-20260708.md`.
The short server-local validation run launched from commit `eba0c565` with
local `gpt-5.5`, completion preflight `ok: true`, and resume-from successor47:
`/home/clawd/research/scion-experiments/v04-cvrp-successor48-route-pool-set-partition-recombination-server-claw-2r-gpt55-2r-gpt55-20260708T060446Z-claw`.
Initial PID is `1742335`. In-flight:
`scion/docs/experiments/v0.4/v04-cvrp-successor48-route-pool-set-partition-recombination-inflight-20260708.md`.

Legacy direction details below are retained as reviewed-history context.

The latest completed CVRP attempt is
successor22b: a WSL scheduler destroy-size clean fork constrained to
`solver_design` / `modify` / `policies/baseline_modules/scheduler.py`. It
correctly targeted and recorded `stagnation_adaptive_destroy_size_schedule`,
but the candidate q trajectory was identical to the champion in aligned ALNS
traces and objective evidence was all case-level ties. Treat unchanged
successor22b-style stagnation q scheduling as an inactive no-op, not as
solver-positive evidence.

The latest completed CVRP attempt is successor24:
`lookahead_insertion_cost_repair`, a bounded destroy/repair insertion-cost
lookahead repair. It completed on WSL:
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor24-lookahead-insertion-repair-2r-gpt55-20260630T073830Z-claw`.
It targeted the intended owner file and produced replayable formal candidates,
but objective evidence stayed below MDE and the v2 follow-up had direct-effect
zero telemetry. Treat unchanged successor24-style insertion-cost lookahead
repair as reviewed/default-avoid evidence, not as a telemetry-only fix. The
postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor24-lookahead-insertion-repair-postrun-20260630.md`.

The latest completed CVRP attempt is successor25:
`cw_sweep_seed_baseline_selector`, a construction seed-baseline selector owned
by `policies/baseline_modules/construction.py`, with scheduler edits limited
to invoking the selector and recording same-run selected-seed versus baseline
objective telemetry. It completed on WSL:
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-2r-gpt55-20260630T101601Z-claw`;
the postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-postrun-20260630.md`.
It observed a direct seed delta on `B-n67-k10`, but that effect did not survive
downstream search and aggregate objective evidence stayed below MDE.
The problem-owned CVRP guidance/catalog still emits no hard
`required_mechanism_ids`, and now treats unchanged successor25-style raw seed
selection as reviewed/default-avoid evidence.

Successor26 targeted `short_horizon_seed_trajectory_selector`, owned by
`policies/baseline_modules/scheduler.py`. The design compared a small existing
seed set after a strictly bounded short-horizon trajectory, recorded baseline
versus selected post-trajectory objective delta before full ALNS/VNS, and kept
generic core and `DecisionFeatures` unchanged. The design plan is
`scion/docs/experiments/v0.4/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-plan-20260630.md`.
It ran on the server-local `claw` environment at
`/home/clawd/research/scion-experiments/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-server-2r-gpt55-20260630T132452Z-claw`
with commit `6896451f` and completion preflight passed, but it ended invalid:
`run_validity_status=invalid_no_effective_rounds`,
`run_completeness_status=interrupted_incomplete`, stop reason
`repeated_quality_block_signature`, `proposal_quality_blocks=3`, and
`protocol_metric_results=0`. All proposals were blocked before effective
screening by `agent_quality_blocked:cvrp_construction_seed_direct_effect_missing`
because the candidate patches did not satisfy the required direct
`context.record_move("short_horizon_seed_trajectory_selector", ...)` effect
telemetry. This is not solver-negative evidence. The in-flight record is
`scion/docs/experiments/v0.4/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-inflight-20260630.md`.
The postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-postrun-20260630.md`.
The first WSL launch attempt failed before campaign execution because WSL HTTPS
TLS handshakes failed; treat that WSL root as an environment preflight failure,
not campaign evidence.

Successor26 follow-up inspection selected a static-quality recognizer repair,
not a relaxation of the gate. The direct-effect requirement remains unchanged,
but the recognizer now accepts the legitimate Python shape where a module-level
mechanism-id constant is used inside a solver class method, while still
rejecting local dynamic alias shadowing. Retry guidance now asks for same-run
seed/trajectory-vs-baseline objective effect, matching the short-horizon
trajectory-selector design. Targeted CVRP tests pass in the local `claw`
environment.

Successor26b reran after that repair on the server-local `claw` runner:
`/home/clawd/research/scion-experiments/v04-cvrp-successor26b-short-horizon-seed-trajectory-selector-static-recognizer-server-2r-gpt55-20260630T134339Z-claw`.
It completed two effective screening rows with local `gpt-5.5`, no quality
blocks, no postrun failures, and postrun readiness ready. This time the result
is valid solver-negative evidence: row 1
`short_horizon_seed_trajectory_selector` had median delta `0.0`, CI
`[0.0, 0.0]`, win rate `0.0`; row 2
`short_horizon_seed_trajectory_selector_v2` had median delta `-5.0`, CI
`[-8.0, 9.0]`, win rate `0.25`, CMT2 median `-8.0`, and CMT4 median `-19.0`.
The postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor26b-short-horizon-seed-trajectory-selector-postrun-20260630.md`.
Treat unchanged construction seed trajectory selection as
reviewed/default-avoid. The next CVRP solver slot should clean-fork to a
materially different non-seed path, with no hard `required_mechanism_ids`.

Successor27 completed as that non-seed clean fork, forced to `solver_design` /
`modify` / `policies/baseline_modules/destroy_repair.py` on the server-local
`claw` runner:
`/home/clawd/research/scion-experiments/v04-cvrp-successor27-non-seed-clean-fork-server-2r-gpt55-20260630T151408Z-claw`.
It launched from commit `5241eb22`, passed healthy `gpt-5.5` completion
preflight, and finished valid/complete/postrun-ready with no quality, model,
telemetry, or postrun failures. The mechanism was
`route_pair_overlap_removal`, a destroy/repair route-pair-overlap removal
operator. Row 1 median delta was `0.75`, CI `[-4.5, 12.5]`; row 2 median
delta was `2.5`, CI `[-7.75, 7.0]`; rows at/above MDE remained `0`. Positive
case medians included A-n64 `14.5`, A-n80 `10.0`, B-n63 `4.0`, CMT3 `6.0`,
and X-n110 `12.5`; losses included CMT2 `-3.0` in row 1, CMT4 `-16.0` in row
2, and P-family medians down to `-14.0`. The in-flight record is
`scion/docs/experiments/v0.4/v04-cvrp-successor27-non-seed-clean-fork-inflight-20260630.md`.
The postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor27-route-pair-overlap-postrun-20260701.md`.
The successor28 plan is
`scion/docs/experiments/v0.4/v04-cvrp-successor28-route-pair-overlap-protected-followup-plan-20260701.md`.
Successor28 completed on the server-local `claw` runner:
`/home/clawd/research/scion-experiments/v04-cvrp-successor28-route-pair-overlap-protected-followup-server-2r-gpt55-20260701T001959Z-claw`.
It launched from commit `ed051d93` with healthy `gpt-5.5` completion preflight
and the same forced target, then finished valid/complete/postrun-ready with no
quality, model, telemetry, or postrun failures. It did not test a true protected
same-mechanism `route_pair_overlap_removal` continuation. Row 1 tested
`boundary_spoke_outlier_removal` and failed screening with median delta `-1.5`,
CI `[-7.25, 13.0]`, win rate `0.25`, CMT2 `-5.5`, and CMT4 `-8.0`. Row 2 tested
`edge_conflict_endpoint_removal` and failed screening with median delta `-2.5`,
CI `[-8.0, 2.0]`, win rate `0.25`, CMT2 `-8.0`, CMT4 `-12.0`, and X-n110
`-6.0`. Treat both mechanisms as reviewed/default-avoid unless a future
proposal changes the causal path materially.
The in-flight record is
`scion/docs/experiments/v0.4/v04-cvrp-successor28-route-pair-overlap-protected-followup-inflight-20260701.md`.
The postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor28-route-pair-overlap-protected-followup-postrun-20260701.md`.

Successor29 completed on the server-local `claw` runner:
`/home/clawd/research/scion-experiments/v04-cvrp-successor29-route-pair-overlap-required-followup-server-2r-gpt55-20260701T031419Z-claw`.
It launched from commit `9cfee8e3` with healthy `gpt-5.5` completion preflight,
the same forced target, and a single-run prepared-manifest override requiring
`route_pair_overlap_removal_protected_followup` in both the typed research
guidance contract and legacy `research_focus.required_mechanism_ids`. It
finished valid/complete/postrun-ready with no quality, model, telemetry, or
postrun failures. Unlike successor28, the live candidates did keep the required
mechanism through formal screening. Both rows were abandoned: row 1 median
delta `-1.75`, CI `[-6.75, 8.5]`, win rate `0.25`; row 2 median delta `-3.75`,
CI `[-7.5, 12.0]`, win rate `0.25`, and direct-effect-zero telemetry. CMT2 was
`-10.0` in both rows, CMT4 stayed negative, and `rows_at_or_above_mde=0`.
The plan is
`scion/docs/experiments/v0.4/v04-cvrp-successor29-route-pair-overlap-required-followup-plan-20260701.md`;
the in-flight record is
`scion/docs/experiments/v0.4/v04-cvrp-successor29-route-pair-overlap-required-followup-inflight-20260701.md`;
the postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor29-route-pair-overlap-required-followup-postrun-20260701.md`.

Successor30 completed on the server-local `claw` runner:
`/home/clawd/research/scion-experiments/v04-cvrp-successor30-bounded-cross-route-double-bridge-server-2r-gpt55-20260701T052131Z-claw`.
It launched from commit `9cfee8e3`, passed completion preflight with local
`gpt-5.5`, forced `solver_design` / `modify` /
`policies/baseline_modules/local_search.py`, and used a single-run
prepared-manifest override requiring `bounded_cross_route_double_bridge_polish`
in both legacy and typed launch guidance. The design plan is
`scion/docs/experiments/v0.4/v04-cvrp-successor30-bounded-cross-route-double-bridge-plan-20260701.md`:
a bounded cross-route internal-fragment cyclic bridge distinct from reviewed
two-customer exchange, Or-opt, 3-opt, ejection-chain, route-segment exchange,
CMT slack segment swap, and two-route tail bridge mechanisms. The first
proposal was correctly blocked before screening because the patch drifted to a
single-route double bridge despite the cross-route mechanism claim. Two formal
screening rows then completed under the required mechanism, but both had median
delta `0.0`, CI `[0.0, 0.0]`, win rate `0.0`, and no row at or above MDE.
Telemetry showed the mechanism was active and consumed runtime, but direct
effect-zero diagnostics reported `candidate_present=64`,
`candidate_positive=0`, and `candidate_zero=64`. Treat unchanged
`bounded_cross_route_double_bridge_polish` as reviewed/default-avoid for v0.4.
The in-flight record is
`scion/docs/experiments/v0.4/v04-cvrp-successor30-bounded-cross-route-double-bridge-inflight-20260701.md`;
the postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor30-bounded-cross-route-double-bridge-postrun-20260701.md`.

The successor31 design review is
`scion/docs/experiments/v0.4/v04-cvrp-successor31-design-review-20260701.md`.
Do not launch an automatic same-mechanism rerun. Route-segment, scheduler-q,
insertion repair, construction seed, route-pair-overlap, double-bridge
local-search/destroy-repair, and adaptive embedded-VNS runtime-allocation lines
have all failed to produce promotion-grade evidence.

Successor31 completed on the server-local `claw` runner:
`/home/clawd/research/scion-experiments/v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-server-2r-gpt55-20260701T111631Z-claw`.
It forced `solver_design` / `modify` /
`policies/baseline_modules/scheduler.py`, passed live launch readiness with
local `gpt-5.5`, and used a run-root-only prepared-manifest override requiring
`adaptive_embedded_vns_runtime_allocation` in both legacy and typed launch
guidance. The first target-intent/hypothesis binding kept the required
mechanism and target file, and the final run completed
valid/complete/postrun-ready with no quality, model, telemetry, or postrun
failures. Both screening rows used the required mechanism and observed direct
phase runtime telemetry. Objective evidence stayed exact zero-effect: median
delta `0.0`, CI high `0.0`, win rate `0.0`, `rows_at_or_above_mde=0`, and
`max_effect_to_mde_ratio=0.0`. Case-level evidence was also flat: CMT2/CMT4
showed no positive median, and P-n101-k4 was `-0.5` in the expanded row. Treat
unchanged `adaptive_embedded_vns_runtime_allocation` as reviewed/default-avoid.
The in-flight record is
`scion/docs/experiments/v0.4/v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-inflight-20260701.md`;
the postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-postrun-20260701.md`.

The successor32 design is
`scion/docs/experiments/v0.4/v04-cvrp-successor32-post-repair-effect-credit-weighting-design-20260701.md`.
It selects `post_repair_effect_credit_weighting`, a narrow
`acceptance_or_adaptive_weighting` clean fork in
`policies/baseline_modules/scheduler.py`. Problem-owned guidance/catalog now
places this mechanism in the top opportunity recipe and parks unchanged
route-pair-overlap, bounded double-bridge, and adaptive embedded-VNS runtime
allocation follow-ups.
The successor32 in-flight record is
`scion/docs/experiments/v0.4/v04-cvrp-successor32-post-repair-effect-credit-weighting-inflight-20260701.md`.
The successor32 postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor32-post-repair-effect-credit-weighting-postrun-20260701.md`.
The first successor32 run root was
`/home/clawd/research/scion-experiments/v04-cvrp-successor32-post-repair-effect-credit-weighting-server-2r-gpt55-20260701T135711Z-claw`.
It was stopped before any effective round because the live hypothesis drifted
to `pair_failure_cooldown_selection` instead of
`post_repair_effect_credit_weighting`. Treat that root as an aborted
pre-screen guard event, not successor32 solver evidence. A CVRP problem-owned
`cvrp_successor32_focus` hypothesis quality gate now blocks scheduler.py
successor32 proposals unless the formal hypothesis names the required
operator-credit mechanism. A guarded-live relaunch at
`/home/clawd/research/scion-experiments/v04-cvrp-successor32-post-repair-effect-credit-weighting-server-guarded-live-2r-gpt55-20260701T141225Z-claw`
was also stopped before screening after three fail-closed quality blocks
(`elite_current_restart`, `repair_failure_pair_filter`, and
`runtime_normalized_pair_credit`). That root proves the formal guard catches
drift, but it is also not solver evidence. The follow-up repair adds a generic
proposal-only `target_intent_required_mechanism_ids` binding so successor32
binds target intent to `post_repair_effect_credit_weighting` while leaving hard
`required_mechanism_ids` empty for prepared-successor arbitration.
The target-bound relaunch then completed at
`/home/clawd/research/scion-experiments/v04-cvrp-successor32-post-repair-effect-credit-weighting-server-target-bound-2r-gpt55-20260701T142821Z-claw`.
It finished valid/complete/postrun-ready with two formal screening rows, no
proposal-quality blocks, and `gpt-5.5` model calls all accounted. Both
target-intent calls and both formal hypothesis bindings stayed on
`post_repair_effect_credit_weighting`, but objective evidence stayed below
closeout needs: both rows had median delta `0.0`, CI `[0.0, 0.0]`,
`rows_at_or_above_mde=0`, and `max_effect_to_mde_ratio=0.0`. The clean row had
one seed-level `X-n110-k13` win (`+70.0`) but no case-gate win; the quality
regression row had one `E-n101-k14` loss (`-6.0`). Mechanism telemetry showed
activation and internal effect, while postrun summarized objective effect as
`zero_objective_effect`. Treat unchanged `post_repair_effect_credit_weighting`
as reviewed/default-avoid.

Reviewed or suppressed paths include the large two-opt seed line, cross
exchange, Or-opt reinsertion, 3-opt, ejection-chain relocation, several
destroy/repair variants, granular savings seed portfolio, exact short-route
polish, and unchanged seed-post selector activation. Use problem-owned
successor review evidence, row-local `mechanism_family`, direct
`mechanism_evidence.primary_mechanism`, and phase telemetry as the current
source of truth.

## Current Warehouse Direction

Warehouse is a positive effective-research control. Do not launch another
warehouse campaign by default. Run one narrow repeat only if an independent
solver-level plateau confirmation is explicitly needed.

The warehouse A/A calibration artifact is checked in at
`surrogate/calibration/aa_noise_floor.json`. Both warehouse spec copies set
`root_dir` to `surrogate`, so their `calibration/aa_noise_floor.json` refs
resolve to that canonical artifact and measurement readiness is reproducible
from the current checkout.

## Execution Environment

- Server-local validation and small/single experiment runs use the local conda
  `claw` environment.
- WSL is the high-resource runner for large or concurrent experiment batches.
  Its conda environment is named `scion` and lives under
  `/home/xjy-ubuntu/miniconda3/envs/scion`.
- Do not assume WSL is launch-ready. Recheck the reverse SSH path and local
  `gpt-5.5` completion preflight before assigning work there. The successor24
  root above passed completion preflight on 2026-06-30 with model `gpt-5.5`,
  base URL `http://127.0.0.1:8080`, and completed successfully.

## Next Actions

1. Treat successor26b as valid solver-negative evidence for unchanged
   short-horizon construction seed trajectory selection. Do not relaunch
   unchanged `short_horizon_seed_trajectory_selector` or
   `short_horizon_seed_trajectory_selector_v2`.
2. Park unchanged successor23-style scheduler q scheduling, successor24-style
   insertion-cost lookahead repair, successor25 construction seed-baseline
   selection, and successor26b construction seed trajectory selection.
3. Treat successor28 as valid negative evidence for unchanged
   `boundary_spoke_outlier_removal` and `edge_conflict_endpoint_removal`; do not
   treat it as a completed protected `route_pair_overlap_removal` follow-up.
4. Treat successor29 as valid negative evidence for the true protected
   `route_pair_overlap_removal_protected_followup` follow-up. Park the
   route-pair-overlap line for v0.4 unless a future proposal names a materially
   different causal path.
5. Treat successor30 as valid zero-effect solver-negative evidence for
   unchanged `bounded_cross_route_double_bridge_polish`. Keep the first static
   quality block as useful fail-closed framework evidence, but do not treat
   `continue_explore` as solver-positive.
6. Treat successor31 as valid zero-effect solver-negative evidence for
   unchanged `adaptive_embedded_vns_runtime_allocation`. The run is
   postrun-ready and activation/runtime telemetry was present, but both rows
   had median delta `0.0`, CI high `0.0`, and no positive-at-MDE evidence.
7. Treat successor32 as valid solver-negative evidence for unchanged
   `post_repair_effect_credit_weighting`. The target-bound run proves the
   proposal target binding works and the mechanism can activate, but it did not
   produce positive-at-MDE or case-gate objective evidence. Do not relaunch the
   unchanged operator-credit mechanism.
8. Treat successor34 as valid weak-positive below-MDE evidence for
   `frozen_safe_neighbor_list_vns_filter`: no model/quality/telemetry/postrun
   failure and no frozen timeout blocker, but no positive-at-MDE row and CMT2
   remained negative. Do not continue the unchanged neighbor-list filter line
   in the next slot.
9. Treat successor35 as valid solver-negative evidence for unchanged
   `capacity_tightness_removal`: mechanism activation and direct telemetry were
   present, but both rows failed screening with negative aggregate medians,
   `rows_at_or_above_mde=0`, and CMT2 negative. Do not expand the unchanged
   capacity-tight removal line.
10. Treat successor36 as a static-quality recognizer boundary gap and
   successor36b as valid solver-negative evidence for unchanged
   `seed_post_optimization_selector`: the recognizer repair worked, activation
   and direct telemetry were visible, but aggregate medians were zero,
   `rows_at_or_above_mde=0`, and CMT2 regressed. The next slot should not use
   `target_intent_required_mechanism_ids` or force `seed_selector.py`; it
   should not repeat unchanged construction seed selector variants.
11. Treat successor37 as valid solver-negative/candidate-quality evidence:
   `route_angle_aware_2opt_star` is reviewed negative default-avoid, and
   `edge_frequency_penalty_repair` is reviewed weak-positive below MDE but
   direct-effect-zero with CMT2/CMT4 all-seed losses. Do not long-run or repeat
   unchanged successor37 mechanisms.
12. Treat successor38 as proposal-control positive but solver-negative. The
   causal-path contract blocked the first weak hypothesis, but the accepted
   `radial_2opt_star_relink` candidate produced zero accepted mechanism moves,
   zero direct mechanism best delta, all case gates tied, and
   `observed_no_effect` mechanism contract status. Do not long-run or repeat
   unchanged `radial_2opt_star_relink`; the next slot must clean-fork to a
   materially different CVRP-owned causal path.
13. Treat successor39 as valid current-run but solver-negative below-MDE
   evidence for unchanged `bounded_dual_repair_selector`. It activated and
   showed local positive selector telemetry, but both screening rows stayed
   below MDE and CMT4/B/P-family losses remain. Do not long-run or extend the
   unchanged mechanism; use the prompt/context repair before the next CVRP
   design.
14. Treat successor40 as valid current-run but solver-negative below-MDE
   evidence for `bounded_two_for_one_exchange`. The added local-search operator
   activated and produced direct objective telemetry, but row 1 was mixed and
   loss-prone while the guarded follow-up mostly collapsed to ties with
   residual B/CMT2 losses. Do not long-run or extend unchanged two-for-one
   exchange gating variants; the next CVRP slot should clean-fork to a
   materially different CVRP-owned causal path with direct objective-effect
   telemetry and CMT2/CMT4 protection. The CVRP guidance/prompt payload has
   already been updated so successor40 is reviewed/default-avoid rather than a
   live target-intent-required mechanism.
15. Treat successor41b as complete, valid, and below MDE. Park
   `route_skeleton_regret_repair` as diagnostic-exhausted
   reviewed/default-avoid evidence; do not long-run, threshold-tune, rerun, or
   continue the same mechanism as an optimization candidate in v0.4.
16. Treat successor42/42b as a successful framework repair and a failed solver
   line. The schema/protected-case prompt and protocol repair worked, but
   `elite_route_memory_repair` stayed marginal below MDE and failed CMT2/CMT4
   protection. Do not long-run or same-mechanism tune it; the next CVRP slot
   must clean-fork to a materially different problem-owned causal path while
   keeping the exact material-difference prompt contract and CMT2/CMT4
   priority coverage.
17. Treat successor43b as complete, valid, and reviewed/default-avoid. Its
   protected follow-up repaired much of the RNG and selected-operator
   attribution contract, but both rows stayed below MDE and CMT2/CMT4/B
   remained unsafe. Do not long-run, threshold-tune, or continue the
   destroy-shadow selector line.
18. Treat successor44d as a successful policy-effect warning hygiene repair and
   weak-positive screening evidence, not promotion-grade evidence. The contract
   now stays `policy_outcome_observed` with no direct-effect repair follow-up,
   and the candidate did not add fake `record_move(delta=...)` telemetry. Do
   not long-run unchanged successor44d.
19. Treat successor45 `bounded_repair_placement_tournament` as complete,
   valid, and reviewed/default-avoid. It produced local pre-VNS repair-
   placement effect, but final objective evidence regressed below MDE and
   failed CMT2/CMT4 protection. Do not long-run, threshold-tune, or continue
   unchanged repair-placement tournament variants; the next CVRP slot should
   clean-fork to a materially different problem-owned causal path.
20. Treat successor46 `best_solution_ruin_recreate_intensification` as
   complete, valid, and reviewed/default-avoid. It target-bound correctly but
   activated sparsely and produced zero final best-solution objective effect.
   Do not long-run or repeat unchanged best-solution ruin/recreate.
21. Treat successor46b
   `best_solution_ruin_recreate_intensification_activation_repair` as complete,
   valid, and reviewed/default-avoid. It finished on the server-local `claw`
   runner at
   `/home/clawd/research/scion-experiments/v04-cvrp-successor46b-best-solution-activation-contract-repair-server-claw-2r-gpt55-2r-gpt55-20260707T150022Z-claw`.
   It improved activation but stayed below MDE and left CMT2 unsafe; park the
   best-solution ruin/recreate line for v0.4.
22. Treat successor47 `bounded_giant_tour_split_recombination` as complete,
   valid, and reviewed/default-avoid. It preserved the module boundary and
   model/context behavior was normal, but direct split-reconstruction effect
   was nearly absent and CMT2/CMT4 were unsafe. Do not long-run or continue
   unchanged contiguous giant-tour split variants.
23. Monitor successor48
   `bounded_route_pool_set_partition_recombination`, now running on the
   server-local `claw` runner at
   `/home/clawd/research/scion-experiments/v04-cvrp-successor48-route-pool-set-partition-recombination-server-claw-2r-gpt55-2r-gpt55-20260708T060446Z-claw`.
   It must stay problem-owned in `route_pool_recombination.py`, use minimal
   scheduler wiring, and prove route-pool source counts, exact-cover
   candidates, accepted final-distance delta, separated reject/budget counts,
   and CMT2/CMT4 safety.
24. Use the new large-file modularization plan before further behavior changes
   in oversized core/postrun/proposal/problem files.
25. Keep the v0.5 governance ablation frozen as a preregistered design; do not
   start the broad matrix as v0.4 work.
26. Keep `TASK.md` and `current-state.md` compact. New detailed run facts belong
   in focused experiment reports.

## Status Cadence

Update current docs only when operating truth changes:

- phase gate pass/fail;
- experiment result that changes interpretation or next action;
- accepted/rejected repair that changes framework behavior;
- commit that changes task scope, protocol, measurement, context composition,
  runtime governance, or lifecycle policy.

Do not record every launch, rerun, intermediate failure, or subagent exchange
here. Detailed counters, commands, wrapper status, and artifact caveats belong
in launch/postrun reports.

Docs to keep aligned:

- `scion/TASK.md`
- `scion/docs/status/current-state.md`
- `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`
- `scion/docs/planning/v0.5/governance-ablation-preregistration-20260629.md`

## Git Hygiene

- Keep commits sliced by repair surface or documentation purpose.
- Do not mix experiment reports, framework repairs, and unrelated cleanup in
  one commit unless explicitly accepted.
- Do not revert user or subagent changes unless explicitly instructed.
- Before each non-doc commit, record tests and experiment artifacts used for
  acceptance.
