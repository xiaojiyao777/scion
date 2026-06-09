# Scion v0.4 Sibling Advisory Warehouse 40R Analysis

Experiment root: `/home/clawd/research/scion-experiments/v04-sibling-advisory-warehouse-verify-40r-gpt55-40r-gpt55-20260608T164113Z-claw/campaign`

Report generated from `status.json`, `campaign_summary.json`, `run_status.json`, `scion.db`, `agentic_sessions/`, `llm_traces/`, `artifacts/formal_candidates/`, `champions/`, `metrics/`, and `run.log`.

Architecture anchor: I read `scion/design/scion-architecture-v3.md` first and apply these boundaries throughout: LLM output is tainted proposal visibility; promotion/abandon decisions must be based on deterministic Contract/Verification/Protocol features; Decision reads `DecisionFeatures`, not LLM free text; cross-branch lessons can guide proposal generation but must not directly drive promotion or abandon. Warehouse-specific semantics below are treated as problem-layer findings, not generic Scion core rules.

## Executive conclusion

This run is valid and complete: wrapper exit 0, `run_validity_status=valid`, `run_complete=true`, `completed_requested_rounds=true`, 40 effective rounds completed, and stop reason `max_rounds_exhausted`.

The run is stable enough as an experiment record and as evidence for champion v2. The champion promotion path is strong: one candidate, `SubcategoryPackUpgrade`, passed screening, validation, and frozen on objective evidence and produced champion version 2. It is not stable enough as a framework acceptance baseline for the next larger experiment until two framework gaps are fixed: fresh runtime replay pressure is detected but not materializable, and formal candidate artifact/accounting reconciliation is not fully clear.

Scion did effective research on this warehouse surface. It found a direct warehouse-specific improvement immediately, then explored many sibling and refinement variants around the same split/cost bottleneck. The later search entered a tie/no-effect plateau, but the branch lifecycle and proposal quality gates generally prevented silent promotion of weak text or repeated ungrounded refinements.

The strongest warehouse-specific finding is that whole-subcategory repacking is much more effective than pairwise merge, tail transfer, swap, vehicle rightsize, or strict acceptance refinements. The generic Scion conclusion is narrower: the proposal/advisory/lifecycle system can steer a search and preserve decision boundaries, but it still needs stronger replay identity materialization, dedup pressure, and clearer accounting surfaces.

## Run status and counters

`run_status.json`:

| Field | Value |
|---|---:|
| Started | `2026-06-08T16:41:14Z` |
| Ended | `2026-06-08T19:15:45Z` |
| Wrapper exit | `0` |
| Status | `finished` |
| Run validity | `valid` |
| Run completeness | `complete` |
| Last stop reason | `max_rounds_exhausted` |

`status.json` and DB reconciliation:

| Counter | Value | Interpretation |
|---|---:|---|
| requested rounds | 40 | User budget. |
| effective rounds completed | 40 | Max-round counter. |
| total loop steps | 48 | 40 effective attempts + 8 non-counted proposal blocks. |
| proposal attempts total / consumed | 48 / 48 | All loop attempts consumed proposal accounting. |
| verification consumed candidates | 40 | At or after verification; excludes proposal blocks. |
| protocol metric results | 40 | 38 screening + 1 validation + 1 frozen. |
| screening protocol results | 38 | Actual screening metric rows. |
| validation protocol results | 1 | Champion candidate validation. |
| frozen protocol results | 1 | Champion candidate frozen. |
| proposal quality blocks | 8 | 7 branch lesson usage semantic/linkage blocks + 1 grounding/follow-up policy block. |
| infra failures | 0 | No infra repair loop. |
| non-infra failures | 8 | The proposal quality blocks. |
| champion version | 2 | Promotion succeeded. |
| champion weight revision | 0 | No separate weight optimization revision. |

LLM usage is consistently `gpt-5.5`:

| Request kind | Calls |
|---|---:|
| hypothesis | 86 |
| tool_selection | 111 |
| code | 37 |
| total traces | 234 |

All 234 `llm_traces/*.json` have `model=gpt-5.5` and `ok=true`. Aggregated trace usage was 4,280,467 input tokens, 199,671 output tokens, 20,673 reasoning output tokens, and 375,424 cache-read input tokens.

## Champion v2 evidence chain

Champion table:

| Version | Snapshot hash prefix | Promotion experiment | Promoted at |
|---:|---|---|---|
| 1 | `4271a0a44c9e` | none | initial |
| 2 | `be5f3b6972b5` | `7a379176-7cd7-43bb-a3c6-99a1b81361c1` | `2026-06-08T17:08:12.973025` |

Promoted branch: `e0766555-b8b2-4fb0-8829-81f88d420f0d`.

Promoted hypothesis: `54d84d6d-b88e-4128-8de0-c799bd272a79`.

Target code: `operators/subcategory_pack_upgrade.py`.

Hypothesis intent: create a vehicle-level operator that selects a high-split `vehicle_subcategory` cluster, repacks unlocked orders into the fewest feasible vehicles, allows explicit HQ40/HQ40_DG upgrade, removes emptied vehicles, and only accepts lexicographic improvement.

Evidence chain from `scion.db`:

| Event | Stage | Decision | Metrics |
|---|---|---|---|
| `746bb4df-7bde-4303-9677-782539cef59b` | screening | `queue_validate` | W/L/T 10/0/0, median_delta 3.0, CI [1.75, 9.5], runtime ratio 0.7205 |
| `c16f328e-cd02-46cd-991e-14ecbe5f0cc1` | validation | `queue_frozen` | median_delta 36.5, CI [11.0, 131.5], runtime ratio 0.6143 |
| `815fb735-a158-4e92-b645-5a11e02d0bff` | frozen budget | `allow` | frozen budget consumed |
| `7a379176-7cd7-43bb-a3c6-99a1b81361c1` | frozen | `promote` | median_delta 62.0, CI [13.0, 203.0], runtime ratio 0.6187 |
| `2a8b6ab0-b99d-480c-8ce4-5873b8fd6678` | decision | `promote` | reason `FROZEN_PASS_HIERARCHICAL` |

The promotion is compliant with the v3 boundary: LLM text supplied the candidate; Contract/Verification/Protocol produced the evidence; the deterministic Decision path promoted after frozen success.

## Fresh runtime replay and artifact accounting

Fresh runtime replay behavior is visible but incomplete:

- `fresh_champion_required_count=7`.
- `runtime_aggregate_excluded_count=33`.
- `fresh_runtime_replay_drain_status=pressure_no_replayable_candidate`.
- Drain attempts: 1.
- Drain executed: 0.
- Drain blocked/skipped: 1.
- Pressure candidates included `fc64c89a` and `84c53d18`, both `fresh_runtime_required=true` but `fresh_runtime_pending=false` and `replay_identity_status=missing`.
- The drain result says fresh champion runtime pressure existed but no structured replay-pending candidate was materializable.

This is the main framework blocker before the next experiment: the system detects stale/low-confidence runtime evidence and excludes it from DecisionFeatures, which is good, but it cannot materialize replay because replay identity is missing.

Formal candidate artifacts:

- `status.json`: `formal_screened_candidates=38`, `screening_protocol_results=38`.
- `scion.db`: 38 screening experiment rows.
- `artifacts/formal_candidates/index.jsonl`: 36 rows and 36 candidate directories.

The two-row gap does not change promotion validity because the promoted candidate has its artifact and DB chain. It is still an accounting/materialization clarity issue. The likely pattern is repeated/refinement screening rows on branches with reused or retained code, but the final summary should explicitly reconcile this instead of requiring manual cross-checking.

## Proposal quality blocks

There were 8 non-counted proposal blocks:

| Loop step | Branch | Category | Summary |
|---:|---|---|---|
| 7 | `6ae4fa7b` | proposal | `branch_lesson_usage_linkage_unrecognized`; lesson named, but target/action/mechanism linkage was not machine-recognized. |
| 8 | `6ae4fa7b` | agent grounding | weak-positive follow-up jumped from same-subcategory drain lineage to pairwise compatible cost merge without branch-local bridge. |
| 14 | `0298d5be` | proposal | `branch_lesson_usage_semantic_mismatch`. |
| 24 | `fc64c89a` | proposal | `branch_lesson_usage_semantic_mismatch`. |
| 28 | `88d2669a` | proposal | `branch_lesson_usage_semantic_mismatch`. |
| 39 | `84c53d18` | proposal | `branch_lesson_usage_semantic_mismatch`. |
| 46 | `60fe0b0b` | proposal | `branch_lesson_usage_semantic_mismatch`. |
| 47 | `60fe0b0b` | proposal | repeated `branch_lesson_usage_semantic_mismatch`. |

Judgment: these blocks are useful. They stop ungrounded or unlinked sibling lesson references before code generation, and they do not count toward max rounds. The weak point is ergonomics: 7 of 8 failures are the same structured lesson usage mismatch, which means the agent can see the lesson but frequently cannot serialize linkage in the required format.

## Per-step analysis

`Counted` means the step consumed the 40-round effective budget. `W/L/T` is case-level gate evidence when protocol metrics exist.

| Step | Counted | Branch | Hypothesis / target | Protocol result | Decision |
|---:|:---:|---|---|---|---|
| 1 | yes | `e0766555` | create `operators/subcategory_pack_upgrade.py`; direct high-split subcategory repack/upgrade. | screening pass, W/L/T 10/0/0, median 3.0, CI [1.75, 9.5]. | `queue_validate` |
| 2 | yes | `e0766555` | same candidate validation. | validation pass, median 36.5, CI [11.0, 131.5]. | `queue_frozen` |
| 3 | yes | `e0766555` | same candidate frozen. | frozen pass, median 62.0, CI [13.0, 203.0]. | `promote` |
| 4 | yes | `4680d42d` | modify `subcategory_pack_upgrade.py`; locked-anchor fill refinement. | screening fail, W/L/T 1/3/2, median -1.25, CI [-6.25, 0.75]. | `abandon` |
| 5 | yes | `6ae4fa7b` | create `same_subcategory_drain_move.py`; order-level drain of same subcategory. | screening expand, W/L/T 5/0/5, median 0.0, CI [0.0, 0.75]. | `expand_screening` |
| 6 | yes | `6ae4fa7b` | same branch expanded screening. | screening expand, W/L/T 8/1/7, median 0.0, CI [0.0, 0.5]. | `continue_explore` |
| 7 | no | `6ae4fa7b` | modify `subcategory_pack_upgrade.py`; bounded whole-cluster repack. | blocked before protocol: lesson usage linkage unrecognized. | none |
| 8 | no | `6ae4fa7b` | proposed pairwise compatible cost merge. | blocked before protocol: weak-positive follow-up lacked branch-local bridge. | none |
| 9 | yes | `6ae4fa7b` | modify `move_order.py`; same-subcategory fallback before random move. | screening fail, W/L/T 0/0/6, median -0.25, CI [-1.0, 0.25]. | `abandon` |
| 10 | yes | `4bcce8f4` | create `cost_preserving_compatible_merge.py`; compatible merge. | screening fail, W/L/T 0/4/6, median -0.5, CI [-2.0, 0.0]. | `abandon` |
| 11 | yes | `5fe7cfe4` | create `subcategory_fragment_absorb.py`. | screening fail/marginal, W/L/T 2/3/5, median 0.0, CI [-0.5, 0.5]. | `continue_explore` |
| 12 | yes | `5fe7cfe4` | refine `subcategory_fragment_absorb.py` with lexicographic cost cap. | screening unclear/no-effect, W/L/T 0/0/6, median 0.0. | `continue_explore` |
| 13 | yes | `0298d5be` | create `donor_vehicle_evacuation.py`. | screening fail/marginal, W/L/T 3/3/4, median 0.0, CI [-0.75, 0.25]. | `continue_explore` |
| 14 | no | `0298d5be` | refine donor evacuation. | blocked before protocol: lesson usage semantic mismatch. | none |
| 15 | yes | `0298d5be` | pre-certify complete evacuation plan. | screening unclear/no-effect, W/L/T 0/0/6, median 0.0. | `continue_explore` |
| 16 | yes | `0298d5be` | allow bounded receiver upgrades in donor evacuation. | screening unclear/no-effect, W/L/T 0/0/6, median 0.0. | `continue_explore` |
| 17 | yes | `fbab8da0` | modify `merge_vehicles.py`; split-neutral compatible merger. | screening fail, W/L/T 0/4/2, median -3.0, CI [-6.5, -0.25]. | `abandon` |
| 18 | yes | `ea43363f` | modify `move_order.py`; split-aware insertion. | screening fail/marginal, W/L/T 1/1/4, median 0.0. | `continue_explore` |
| 19 | yes | `ea43363f` | conservative split-aware insertion refinement. | screening fail/marginal, W/L/T 2/2/2, median 0.0. | `continue_explore` |
| 20 | yes | `ea43363f` | repair split-aware insertion schema/guard. | screening expand, W/L/T 3/1/2, median 0.0. | `expand_screening` |
| 21 | yes | `ea43363f` | expanded split-aware insertion evidence. | screening fail/marginal, W/L/T 2/1/7, median 0.0, CI [-1.0, 0.25]. | `continue_explore` |
| 22 | yes | `8e347bb3` | create `city_category_bin_repack.py`. | screening fail, W/L/T 1/4/5, median -0.25, CI [-1.5, 0.25]. | `abandon` |
| 23 | yes | `fc64c89a` | create `anchor_vehicle_absorb.py`. | screening fail/marginal, W/L/T 1/1/8, median 0.25, CI [0.0, 1.0]. | `continue_explore` |
| 24 | no | `fc64c89a` | strict cost-nondegrading absorb refinement. | blocked before protocol: lesson usage semantic mismatch. | none |
| 25 | yes | `fc64c89a` | strict cost-nondegrading absorb refinement. | screening unclear/no-effect, W/L/T 0/0/6, median 0.0. | `continue_explore` |
| 26 | yes | `fc64c89a` | relax over-strict cost-prefix pruning. | screening unclear/no-effect, W/L/T 0/0/6, median 0.0. | `continue_explore` |
| 27 | yes | `88d2669a` | modify `swap_orders.py`; complementary subcategory swap. | screening fail/marginal, W/L/T 1/1/4, median 0.0. | `continue_explore` |
| 28 | no | `88d2669a` | complementary swap refinement. | blocked before protocol: lesson usage semantic mismatch. | none |
| 29 | yes | `88d2669a` | complementary swap with better target selection. | screening fail/marginal, W/L/T 2/1/3, median 0.25, CI [-0.25, 1.25]. | `continue_explore` |
| 30 | yes | `88d2669a` | complementary swap activation refinement. | screening fail, W/L/T 0/3/3, median -0.5, CI [-1.0, 0.0]. | `abandon` |
| 31 | yes | `ea869429` | create `residual_subcategory_pair_repack.py`. | screening fail, W/L/T 0/3/7, median -0.25, CI [-1.25, 0.0]. | `abandon` |
| 32 | yes | `1a78a307` | modify `change_vehicle_type.py`; fleet rightsize pass. | screening fail/marginal, W/L/T 2/1/3, median 0.0. | `continue_explore` |
| 33 | yes | `1a78a307` | refine fleet rightsize. | screening fail/marginal, W/L/T 1/1/4, median 0.0. | `continue_explore` |
| 34 | yes | `1a78a307` | repair fleet rightsize conservatively. | screening fail/marginal, W/L/T 2/1/3, median 0.0. | `continue_explore` |
| 35 | yes | `57bcdb73` | create `pairwise_slack_fill_move.py`. | screening fail, W/L/T 1/3/6, median -0.5, CI [-1.5, 0.25]. | `abandon` |
| 36 | yes | `4244ff90` | create `single_subcategory_tail_insert.py`. | screening fail, W/L/T 1/1/8, median 0.0, CI [-0.5, 0.0]. | `abandon` |
| 37 | yes | `d888b151` | create `cost_neutral_bin_compactor.py`. | screening fail, W/L/T 1/4/5, median -0.75, CI [-1.5, 0.0]. | `abandon` |
| 38 | yes | `84c53d18` | create `locked_anchor_subcategory_repack.py`. | screening fail/weak-positive, W/L/T 4/1/5, median 0.0, CI [0.0, 1.0]. | `continue_explore` |
| 39 | no | `84c53d18` | stricter locked-anchor acceptance gate. | blocked before protocol: lesson usage semantic mismatch. | none |
| 40 | yes | `84c53d18` | stricter precheck and gate. | screening unclear/no-effect, W/L/T 0/0/6, median 0.0. | `continue_explore` |
| 41 | yes | `84c53d18` | recover lost weak-positive activation. | screening unclear/no-effect, W/L/T 0/0/6, median 0.0. | `continue_explore` |
| 42 | yes | `4c829d96` | modify `merge_vehicles.py`; objective-guarded compatible pair. | screening fail, W/L/T 0/3/3, median -0.25, CI [-1.5, 0.0]. | `abandon` |
| 43 | yes | `27665e6d` | create `cost_safe_tail_transfer.py`. | screening fail, W/L/T 2/3/5, median -0.25, CI [-0.5, 0.25]. | `abandon` |
| 44 | yes | `4099ad01` | create `cost_preserving_hetero_merge.py`. | screening fail, W/L/T 0/5/5, median -0.75, CI [-1.25, 0.0]. | `abandon` |
| 45 | yes | `60fe0b0b` | modify `move_order.py`; guarded empty-source drain. | screening fail/marginal, W/L/T 2/0/4, median 0.0, CI [-0.5, 0.75]. | `continue_explore` |
| 46 | no | `60fe0b0b` | guarded empty-source refinement. | blocked before protocol: lesson usage semantic mismatch. | none |
| 47 | no | `60fe0b0b` | repeated guarded empty-source refinement. | blocked before protocol: lesson usage semantic mismatch. | none |
| 48 | yes | `60fe0b0b` | refined guarded empty-source drain. | screening expand, W/L/T 3/1/2, median 0.25, CI [-1.75, 1.0]. | `expand_screening` |

## Branch-by-branch analysis

| Branch | State | Hypothesis path | Result and lifecycle judgment |
|---|---|---|---|
| `e0766555` | promoted | New `SubcategoryPackUpgrade`. | Strong direct problem-layer mechanism. Passed screening, validation, frozen. Follow-up not needed before promotion. |
| `4680d42d` | abandoned | Modify promoted operator with locked-anchor fill. | Reasonable first refinement, but it damaged objective evidence. Abandon was correct. |
| `6ae4fa7b` | abandoned | Same-subcategory drain, then attempted sibling/repair variants. | Initial weak-positive/expand was reasonable. Later pairwise bridge was correctly blocked; final MoveOrder fallback became no-effect. Abandon was reasonable. |
| `4bcce8f4` | abandoned | Cost-preserving compatible merge. | Near duplicate of pairwise/merge family; screening loss-heavy. Abandon was correct. |
| `5fe7cfe4` | parked_lineage | Subcategory fragment absorb, then cost-cap refinement. | Marginal to no-effect. Parking retained evidence and freed active slot; reasonable, but fresh replay identity later missing. |
| `0298d5be` | parked_lineage | Donor vehicle evacuation, then stricter evacuation refinements. | First marginal; refinements no-op. Parking was reasonable. Structured lesson block helped prevent bad refinement. |
| `fbab8da0` | abandoned | Split-neutral compatible merge in `merge_vehicles.py`. | Clear regression, negative median and CI. Abandon was correct. |
| `ea43363f` | parked_lineage | Split-aware MoveOrder insertion with multiple refinements. | Repeated marginal/noisy evidence. Expansion did not mature. Parking was reasonable. |
| `8e347bb3` | abandoned | City/category bin repack. | Negative case evidence. Abandon was correct. |
| `fc64c89a` | explore | Anchor vehicle absorb with strict/relaxed refinements. | Branch remains active but current head is no-effect and fresh runtime required. Needs replay materialization or closure, not more refinement. |
| `88d2669a` | abandoned | Complementary subcategory swap refinements. | Some marginal signal, then negative refinement. Abandon was correct. |
| `ea869429` | abandoned | Residual subcategory pair repack. | Pairwise family again failed; abandon correct. |
| `1a78a307` | parked_lineage | Fleet rightsize pass in `change_vehicle_type.py`. | Repeated marginal zero-median evidence. Parking was reasonable. |
| `57bcdb73` | abandoned | Pairwise slack fill. | Loss-heavy, no sufficient positive signal. Abandon correct. |
| `4244ff90` | abandoned | Single subcategory tail insert. | Tie-heavy with lower CI <= 0 and weak evidence. Abandon acceptable. |
| `d888b151` | abandoned | Cost-neutral bin compactor. | Loss-heavy. Abandon correct. |
| `84c53d18` | explore | Locked-anchor subcategory repack and stricter refinements. | First weak-positive, then refinements became no-effect. Active state should be resolved through replay/closure. |
| `4c829d96` | abandoned | Objective-guarded compatible merge. | Another pairwise merge variant; negative. Abandon correct. |
| `27665e6d` | abandoned | Cost-safe tail transfer. | Loss-heavy. Abandon correct. |
| `4099ad01` | abandoned | Cost-preserving hetero merge. | Worst W/L/T among late branches, 0/5/5. Abandon correct. |
| `60fe0b0b` | explore_expand | Guarded empty-source drain with repeated blocked refinements. | Current expanded signal is marginal/uncertain; repeated lesson-usage blocks show advisory serialization friction. Needs either materialized expansion or closure. |

## Branch-to-branch differences and sibling advisory

Useful avoided/contrasted patterns:

- Pairwise merge/repack families repeatedly failed: `4bcce8f4`, `fbab8da0`, `ea869429`, `4c829d96`, `4099ad01`. The advisory system did not eliminate all repeats, but later proposals increasingly tried to claim material differences such as hetero merge, cost-preserving merge, or residual pair repack.
- Strict guard refinements often became all-ties/no-effect: `5fe7cfe4`, `0298d5be`, `fc64c89a`, `84c53d18`. Sibling lessons correctly surfaced this as a risk, but the agent still frequently responded by tightening gates rather than changing mechanism family.
- Order-level MoveOrder variants (`6ae4fa7b`, `ea43363f`, `60fe0b0b`) produced marginal or weak-positive signals but did not mature. The framework allowed branch-local follow-up, blocked one ungrounded cross-mechanism jump, and parked/reclaimed saturated branches.
- Warehouse-specific whole-cluster repacking was uniquely strong. The best candidate directly targeted the primary objective surface; later pairwise/tail variants only approximated that mechanism.

Sibling advisory helped auditability and stopped some repeated waste, but it did not fully prevent near-duplicates. The `cross_branch_research_observability` summary says branch lessons were proposal-only and excluded from decision features; it also reports 59 avoided lessons, 73 contrasted lessons, 16 preserved same-branch lessons, 35 branch-lesson usage requirements, 33 satisfied, and 5 present-but-not-semantic cases. That is the right boundary, but the next optimization should turn repeated lesson-usage serialization failures into a simpler schema or deterministic repair.

## LLM session inventory

There were 80 agentic sessions: hypothesis sessions generally end as `partial_hypothesis_only` because APS waits for deterministic approval; code sessions end as `completed`. The table lists each session, trace-kind counts, and the main context/tools. Full trace ids are in `agentic_sessions/agentic_session_trace_index.json`.

| # | Session | Branch | Status | Target | Trace kinds | Context/tools used |
|---:|---|---|---|---|---|---|
| 1 | `6501ba6d` | `e0766555` | partial_hypothesis_only | `operators/subcategory_pack_upgrade.py` | hypothesis:2 | memory, proposal memory, champion surface interface |
| 2 | `6695b154` | `e0766555` | completed | `operators/subcategory_pack_upgrade.py` | tool_selection:4, code:1 | branch state, screening/runtime feedback, surface interface |
| 3 | `bb8e1e84` | `4680d42d` | partial_hypothesis_only | `operators/subcategory_pack_upgrade.py` | tool_selection:2, hypothesis:2 | memory, screening/runtime feedback; flagged `tool_budget_exhausted` but produced hypothesis |
| 4 | `6d537b79` | `4680d42d` | completed | `operators/subcategory_pack_upgrade.py` | tool_selection:2, code:1 | branch state and feedback |
| 5 | `999ada7f` | `6ae4fa7b` | partial_hypothesis_only | `operators/same_subcategory_drain_move.py` | hypothesis:2 | memory and screening/runtime feedback |
| 6 | `281daf89` | `6ae4fa7b` | completed | `operators/same_subcategory_drain_move.py` | tool_selection:3, code:1 | branch state, surface, feedback |
| 7 | `5e76c46e` | `6ae4fa7b` | partial_hypothesis_only | `operators/subcategory_pack_upgrade.py` | hypothesis:2 | repair context and sibling lessons |
| 8 | `ddc2d2d6` | `6ae4fa7b` | partial_hypothesis_only | `operators/pairwise_compatible_cost_merge.py` | hypothesis:2 | repair context; later blocked for missing branch-local bridge |
| 9 | `da3183f7` | `6ae4fa7b` | partial_hypothesis_only | `operators/move_order.py` | hypothesis:2 | repair context and feedback |
| 10 | `6a0a924c` | `6ae4fa7b` | completed | `operators/move_order.py` | tool_selection:2, code:1 | branch state and feedback |
| 11 | `6f18b046` | `4bcce8f4` | partial_hypothesis_only | `operators/cost_preserving_compatible_merge.py` | hypothesis:2 | memory and screening/runtime feedback |
| 12 | `b215a6e3` | `4bcce8f4` | completed | same | tool_selection:2, code:1 | branch state and feedback |
| 13 | `c95ecb55` | `5fe7cfe4` | partial_hypothesis_only | `operators/subcategory_fragment_absorb.py` | hypothesis:2 | memory and feedback |
| 14 | `7d2d89ec` | `5fe7cfe4` | completed | same | tool_selection:2, code:1 | branch state and feedback |
| 15 | `3b0a40b5` | `5fe7cfe4` | partial_hypothesis_only | `operators/subcategory_fragment_absorb.py` | hypothesis:2 | repair context |
| 16 | `ee3c6bd0` | `5fe7cfe4` | completed | same | tool_selection:4, code:1 | branch state, active solver design, algorithm files |
| 17 | `4f9d74c3` | `0298d5be` | partial_hypothesis_only | `operators/donor_vehicle_evacuation.py` | hypothesis:2 | memory and feedback |
| 18 | `65042d66` | `0298d5be` | completed | same | tool_selection:3, code:1 | branch state, surface, feedback |
| 19 | `bf6b7d43` | `0298d5be` | partial_hypothesis_only | same | hypothesis:2 | repair context; later blocked |
| 20 | `9ba46822` | `0298d5be` | partial_hypothesis_only | same | hypothesis:2 | repair context |
| 21 | `206cfb12` | `0298d5be` | completed | same | tool_selection:2, code:1 | branch state and feedback |
| 22 | `2271fad3` | `0298d5be` | partial_hypothesis_only | same | hypothesis:2 | repair context |
| 23 | `88a999a2` | `0298d5be` | completed | same | tool_selection:3, code:1 | branch state, active solver design |
| 24 | `0d4e8c19` | `fbab8da0` | partial_hypothesis_only | `operators/merge_vehicles.py` | hypothesis:2 | memory and feedback |
| 25 | `2522643e` | `fbab8da0` | completed | same | tool_selection:1, code:1 | surface and feedback |
| 26 | `e45c43b2` | `ea43363f` | partial_hypothesis_only | `operators/move_order.py` | hypothesis:2 | memory and feedback |
| 27 | `275775a0` | `ea43363f` | completed | same | tool_selection:4, code:1 | branch state, active solver design, algorithm files |
| 28 | `3a25924c` | `ea43363f` | partial_hypothesis_only | same | hypothesis:2 | repair context |
| 29 | `a91dfb8f` | `ea43363f` | completed | same | tool_selection:5, code:1 | branch state, solver design, algorithm file list |
| 30 | `bce889ea` | `ea43363f` | partial_hypothesis_only | same | hypothesis:2 | repair context |
| 31 | `3029b787` | `ea43363f` | completed | same | tool_selection:2, code:1 | branch state and feedback |
| 32 | `33dd52fb` | `8e347bb3` | partial_hypothesis_only | `operators/city_category_bin_repack.py` | hypothesis:2 | memory and feedback |
| 33 | `e1925e1a` | `8e347bb3` | completed | same | tool_selection:3, code:1 | branch state, surface |
| 34 | `b11376aa` | `fc64c89a` | partial_hypothesis_only | `operators/anchor_vehicle_absorb.py` | hypothesis:2 | memory and feedback |
| 35 | `ed1b49a4` | `fc64c89a` | completed | same | tool_selection:3, code:1 | branch state, surface |
| 36 | `c45c0927` | `fc64c89a` | partial_hypothesis_only | same | hypothesis:2 | repair context; later blocked |
| 37 | `c7a3fd5e` | `fc64c89a` | partial_hypothesis_only | same | hypothesis:2 | repair context |
| 38 | `dc251415` | `fc64c89a` | completed | same | tool_selection:5, code:1 | branch state, solver design, algorithm file list |
| 39 | `e5bfaeca` | `fc64c89a` | partial_hypothesis_only | same | hypothesis:2 | repair context |
| 40 | `2a67efdb` | `fc64c89a` | completed | same | tool_selection:5, code:1 | branch state, solver design, algorithm file list |
| 41 | `6048e644` | `88d2669a` | partial_hypothesis_only | `operators/swap_orders.py` | hypothesis:2 | memory and feedback |
| 42 | `3e247313` | `88d2669a` | completed | same | tool_selection:1, code:1 | memory and feedback |
| 43 | `4432ef89` | `88d2669a` | partial_hypothesis_only | same | hypothesis:2 | repair context; later blocked |
| 44 | `9fd98709` | `88d2669a` | partial_hypothesis_only | same | hypothesis:2 | repair context |
| 45 | `c4aa2944` | `88d2669a` | completed | same | tool_selection:5, code:1 | branch state, solver design, algorithm file list |
| 46 | `325c2405` | `88d2669a` | partial_hypothesis_only | same | hypothesis:1 | repair context |
| 47 | `116d258e` | `88d2669a` | completed | same | tool_selection:4, code:1 | branch state, algorithm files |
| 48 | `bd72a80d` | `ea869429` | partial_hypothesis_only | `operators/residual_subcategory_pair_repack.py` | hypothesis:2 | memory and feedback |
| 49 | `8fb46ca6` | `ea869429` | completed | same | tool_selection:4, code:1 | branch state, solver design, operator read |
| 50 | `326cade1` | `1a78a307` | partial_hypothesis_only | `operators/change_vehicle_type.py` | hypothesis:2 | memory and feedback |
| 51 | `5538e577` | `1a78a307` | completed | same | tool_selection:1, code:1 | memory and feedback |
| 52 | `41d736a7` | `1a78a307` | partial_hypothesis_only | same | hypothesis:2 | repair context |
| 53 | `378fd305` | `1a78a307` | completed | same | tool_selection:5, code:1 | branch state, solver design, algorithm file list |
| 54 | `5031e367` | `1a78a307` | partial_hypothesis_only | same | hypothesis:2 | repair context |
| 55 | `588e68d8` | `1a78a307` | completed | same | tool_selection:5, code:1 | branch state, solver design, algorithm file list |
| 56 | `9ab36630` | `57bcdb73` | partial_hypothesis_only | `operators/pairwise_slack_fill_move.py` | hypothesis:2 | memory and feedback |
| 57 | `2aaea26e` | `57bcdb73` | completed | same | tool_selection:2, code:1 | branch state and feedback |
| 58 | `37ee1328` | `4244ff90` | partial_hypothesis_only | `operators/single_subcategory_tail_insert.py` | hypothesis:2 | memory and feedback |
| 59 | `81eebabc` | `4244ff90` | completed | same | tool_selection:2, code:1 | branch state and feedback |
| 60 | `3bb19f24` | `d888b151` | partial_hypothesis_only | `operators/cost_neutral_bin_compactor.py` | hypothesis:2 | memory and feedback |
| 61 | `72ad43e7` | `d888b151` | completed | same | tool_selection:4, code:2 | branch state, surface, active solver design |
| 62 | `4462d8e2` | `84c53d18` | partial_hypothesis_only | `operators/locked_anchor_subcategory_repack.py` | hypothesis:2 | memory and feedback |
| 63 | `3c5847ab` | `84c53d18` | completed | same | tool_selection:2, code:1 | branch state and feedback |
| 64 | `9fec4710` | `84c53d18` | partial_hypothesis_only | same | hypothesis:2 | repair context; later blocked |
| 65 | `389fd969` | `84c53d18` | partial_hypothesis_only | same | hypothesis:2 | repair context |
| 66 | `37e5dd93` | `84c53d18` | completed | same | tool_selection:6, code:1 | branch state, solver design, algorithm reads |
| 67 | `7fa5e5d5` | `84c53d18` | partial_hypothesis_only | same | hypothesis:1 | repair context |
| 68 | `6abca9cf` | `84c53d18` | completed | same | tool_selection:2, code:1 | branch state and feedback |
| 69 | `5e591586` | `4c829d96` | partial_hypothesis_only | `operators/merge_vehicles.py` | hypothesis:2 | memory and feedback |
| 70 | `19032aab` | `4c829d96` | completed | same | tool_selection:2, code:1 | branch state and feedback |
| 71 | `4d577090` | `27665e6d` | partial_hypothesis_only | `operators/cost_safe_tail_transfer.py` | hypothesis:2 | memory and feedback |
| 72 | `de9792cd` | `27665e6d` | completed | same | tool_selection:2, code:1 | branch state and feedback |
| 73 | `effc0d9d` | `4099ad01` | partial_hypothesis_only | `operators/cost_preserving_hetero_merge.py` | hypothesis:2 | memory and feedback |
| 74 | `4924acfd` | `4099ad01` | completed | same | tool_selection:2, code:1 | branch state and feedback |
| 75 | `76d07a11` | `60fe0b0b` | partial_hypothesis_only | `operators/move_order.py` | hypothesis:2 | memory and feedback |
| 76 | `76407c7c` | `60fe0b0b` | completed | same | tool_selection:2, code:1 | branch state, surface |
| 77 | `2dc3a6d2` | `60fe0b0b` | partial_hypothesis_only | same | hypothesis:2 | repair context; later blocked |
| 78 | `db3b6193` | `60fe0b0b` | partial_hypothesis_only | same | hypothesis:2 | repair context; later blocked |
| 79 | `78623b9e` | `60fe0b0b` | partial_hypothesis_only | same | hypothesis:2 | repair context |
| 80 | `5a1d04eb` | `60fe0b0b` | completed | same | tool_selection:3, code:1 | branch state, active solver design |

Context judgment: the agent generally had enough context for each phase. Hypothesis sessions saw tainted memory plus screening/runtime summaries; code sessions read branch state and either surface/interface or algorithm files. The failures were not caused by missing raw context; they were caused by weak research hypotheses, over-conservative refinements, or structured lesson-linkage schema failures.

## Framework judgment

Proposal quality blocks: effective. They prevented unlinked sibling lessons and an ungrounded weak-positive jump from reaching code/protocol. The repeated semantic mismatch class should be made easier to satisfy or deterministically repair.

Lesson-to-action/advisory gate: mostly effective and boundary-compliant. Lessons were visible to proposal generation and excluded from DecisionFeatures. The advisory system helped contrast/avoid previous failures, but it still allowed a lot of pairwise-merge and over-strict-refinement near-duplicates.

Fresh runtime replay materialization: not acceptable yet. The framework detected stale runtime evidence, excluded runtime as standalone decision evidence, and surfaced `fresh_champion_required`, but replay identity was missing for pressure candidates. This is the top framework fix.

Accounting clarity: improved but still not fully clean. Status, DB, and run wrapper reconcile for max-round/effective/protocol counts. Formal candidate artifact count does not exactly match the 38 screening metric rows, which should be explained in summary output.

Lifecycle decisions: generally sound. Strong candidate was promoted only after validation/frozen. Loss-heavy branches were abandoned. Marginal/no-effect lineages were parked or left in explore/expand with follow-up pressure. Active branches at the end (`fc64c89a`, `84c53d18`, `60fe0b0b`) need deterministic closure or materialized replay before the next run.

Decision boundary compliance: no violation found. Candidate intent, runtime guidance, observability value, and cross-branch lessons are explicitly marked proposal visibility only / DecisionFeatures excluded. Promotion came from protocol evidence.

## Needed optimizations before next experiment

1. Fix fresh runtime replay identity persistence.
   Acceptance: every branch with `fresh_runtime_required=true` has a materializable `replay_identity` or an explicit non-replayable terminal reason recorded at the branch head and in summary.

2. Reconcile formal candidate artifact counts with protocol rows.
   Acceptance: `formal_screened_candidates`, DB screening rows, and `artifacts/formal_candidates/index.jsonl` either match or status reports a clear `artifact_omitted_reason` per missing row.

3. Add deterministic repair for `branch_lesson_usage`.
   Acceptance: semantic/linkage mismatch blocks should include a compact corrected skeleton or be auto-normalized when only field aliases differ.

4. Strengthen near-duplicate pressure.
   Acceptance: repeated pairwise merge/repack or over-strict guard refinements should be flagged before hypothesis approval unless the proposal changes mechanism family, trigger, target surface, or measurable effect path.

5. Close active no-effect branches at max-round exhaustion.
   Acceptance: final summary should classify remaining `explore` branches as active-with-required-follow-up, parked, abandoned, or replay-blocked, with one next action per branch.

## Warehouse-specific vs generic conclusions

Warehouse-specific:

- Direct same-subcategory cluster repack/upgrade is highly effective on this benchmark.
- Pairwise vehicle merge, hetero merge, pair exchange, tail transfer, and strict guard refinements are much weaker on this surface.
- Many later branches hit a tie/no-effect plateau because they protect `subcategory_splits` but do not create enough opportunity to reduce it.

Generic Scion conclusions:

- The Proposal -> Contract -> Verification -> Protocol -> Decision pipeline can produce a valid promotion chain with tainted LLM outputs kept out of Decision.
- Cross-branch lessons are useful as advisory visibility but need better schema ergonomics and stronger dedup pressure.
- Runtime evidence handling is correctly conservative but operationally incomplete until replay identities are durable and materializable.
