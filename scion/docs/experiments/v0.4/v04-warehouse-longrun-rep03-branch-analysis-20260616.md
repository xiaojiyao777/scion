# Scion v0.4 Warehouse Longrun rep03 Branch Analysis - 2026-06-16

## Boundary

This report analyzes only `rep03/on_compact` from:

- Cell root: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact`
- Campaign dir: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign`
- DB: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/scion.db`
- Session index: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/agentic_sessions/agentic_session_index.json`
- Trace index: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/agentic_sessions/agentic_session_trace_index.json`
- Formal candidate index: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/artifacts/formal_candidates/index.jsonl`
- Research efficiency report: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/postrun_acceptance/research_efficiency/rep03_on_compact.research_efficiency.v1.json`
- Proposal trajectory manifest: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/postrun_acceptance/manifests/rep03_on_compact.proposal_trajectory_manifest.v1.json`
- Prior postrun: `/home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/v04-warehouse-longrun-regression-3x24r-postrun-20260616.md`

Architecture boundary is preserved from `/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md`: prompt, context, transcript, trace, branch-card, branch-lesson, and free-text LLM artifacts are report-only explanatory material. The Decision path remains deterministic Contract, Verification, Protocol, and `DecisionFeatures` evidence. Branch-lesson usage can explain proposal behavior but is not promotion evidence.

This report did not mutate campaign state, source code, `TASK`, current-state, or history files.

## Cell Summary

rep03 completed the requested 24 effective rounds with 22 protocol metric rows, 2 verification-only heavy failures, and 15 proposal-quality blocks. Final champion was `v2`, promoted from branch `47ec47f1-09d9-4057-ae51-a6ba13279e40`, hypothesis `8670e9f5-6a1d-4e5b-a2b0-217bf62e1a19`, patch file `operators/cost_preserving_tail_refit.py`.

Promotion protocol chain:

| Stage | Metric ref | Cases | Case W/L/T | Gate win rate | Median delta | CI | Runtime confidence | Decision |
|---|---|---:|---:|---:|---:|---:|---|---|
| screening | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/metrics/aafc149c-ed79-42ed-a086-22f25858c263.json` | 10 | 6/0/4 | 0.600 | 850 | [200, 2050] | low_cached_champion | queue_validate |
| validation | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/metrics/5ec7634c-539a-4baa-9e8f-c05896e51a30.json` | 5 | aggregate only | n/a | 0 | [0, 1] | high | expand_validation |
| validation expand | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/metrics/dfaee2a0-5f2c-4133-b964-96d999f2635c.json` | 5 | aggregate only | n/a | 0 | [0, 1] | low_cached_champion | queue_frozen |
| frozen | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/metrics/bfd03677-66f7-4930-b597-4c0c0c2d658d.json` | 4 | aggregate only | n/a | 15000 | [12900, 25700] | high | promote |

Frozen pair-level detail from `metrics/bfd03677-66f7-4930-b597-4c0c0c2d658d.json`: 12 valid pairs, 12/12 pair wins, first pair example `instance_prod_fro_x01.json` seed 256 had `delta=12900`, decisive metric `total_cost`, runtime ratio `0.9695`, and fresh champion source. This is a robust single promotion over the active champion, but not a continuous promotion chain.

The final promoted operator exists at:

- `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/champions/champion_v2/operators/cost_preserving_tail_refit.py`
- `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/champions/champion_v2/registry.yaml`

The registry added `cost_preserving_tail_refit` with class `CostPreservingTailRefit`, category `vehicle_level`, weight `0.130435`.

## Branch Evolution Map

Protocol rows below are chronological completed Protocol metric rows only. Verification-only failures and proposal-quality blocks are listed separately because they consumed budget/attempts but did not produce Protocol metrics.

| Protocol row | Branch | Hypothesis | Stage | Action/target | Case W/L/T | Median delta | Decision/reason | Metric ref |
|---:|---|---|---|---|---:|---:|---|---|
| P01 | `fa5d75b4` | `7f34bef6` | screening | create `operators/subcategory_pack_upgrade.py` | 2/2/6 | 0 | continue, marginal | `metrics/26ef4a95-53e1-407d-85f0-cc3b45349940.json` |
| P02 | `fa5d75b4` | `68c3feb0` | screening | modify same file | 0/0/6 | 0 | continue, neutral/runtime pressure | `metrics/5328d051-d3bb-4aed-b67d-3885ee9b8892.json` |
| P03 | `9931c959` | `fe0b896c` | screening | modify `operators/move_order.py` | 1/2/3 | 0 | continue, marginal | `metrics/4b79f064-d6fa-4232-b678-d60771beadbe.json` |
| P04 | `9931c959` | `61cc108c` | screening | modify same file | 1/2/3 | 0 | continue, marginal | `metrics/943765d3-ce31-4062-85f2-60eab7beea7e.json` |
| P05 | `9931c959` | `bf3cb4f4` | screening | modify same file | 1/2/3 | 0 | continue, marginal | `metrics/f56853ce-edc0-4161-abb4-a381ac5716ad.json` |
| P06 | `da55dd68` | `dd3ead76` | screening | create `operators/empty_tail_absorb.py` | 2/0/8 | 575 | continue, marginal | `metrics/94bdeeca-4d40-4599-a610-2a0d08b55c73.json` |
| P07 | `da55dd68` | `8ad22622` | screening | modify same file | 0/0/6 | 0 | continue, fresh runtime required | `metrics/963e2bdc-b00c-4aba-88a4-82ccefdd354d.json` |
| P08 | `5f83d92b` | `903ab93c` | screening | modify `operators/swap_orders.py` | 3/1/2 | 400 | expand_screening | `metrics/60f21db9-ee71-454b-a517-4c15d3f156c6.json` |
| P09 | `5f83d92b` | `903ab93c` | screening expand | same candidate | 5/1/8 | 450 | continue, weak signal but fail win rate | `metrics/4d1aed8a-9a8f-44cc-a8f1-29c37c06975c.json` |
| P10 | `5f83d92b` | `aecb6611` | screening | modify same file | 2/1/3 | 0 | continue, marginal | `metrics/66a6ad3b-138c-4f4b-a5e1-cad46d11bb34.json` |
| P11 | `e19e39e5` | `a75e2942` | screening | create `operators/region_category_binpack_cost.py` | 0/2/8 | -25 | abandon, loss without win/negative delta | `metrics/49b45402-9bd8-4bf2-9d4f-91938d00ce68.json` |
| P12 | `a31b6330` | `b9a45ea2` | screening | create `operators/redundant_carrier_eliminate.py` | 4/0/6 | 425 | continue, weak signal | `metrics/d322ce19-2d24-48b9-8bf5-01f553be778a.json` |
| P13 | `a31b6330` | `4794892f` | screening | modify same file | 0/0/6 | 0 | continue, fresh runtime required | `metrics/ddf63efc-34a4-4ac4-96d8-3ad4cbccd6b4.json` |
| P14 | `68e9cd7e` | `c6159286` | screening | create `operators/locked_cluster_coalesce.py` | 1/1/8 | 0 | continue, marginal | `metrics/ddb529d2-cbf9-4d41-bc65-7c088e8e905c.json` |
| P15 | `68e9cd7e` | `56c38375` | screening | modify same file | 0/0/6 | 0 | continue, fresh runtime required | `metrics/47782d6e-9988-4ca9-945c-e87deecc1656.json` |
| P16 | `461dc035` | `762b4e26` | screening | create `operators/suffix_load_cost_trim.py` | 3/1/6 | 275 | continue, marginal | `metrics/f48c28c3-5bc0-42c2-a48a-3f918e17c2c6.json` |
| P17 | `461dc035` | `d0001f56` | screening | modify same file | 0/0/6 | 0 | continue, fresh runtime required | `metrics/c80d8bb0-1741-45a6-8b7c-a5ebfbd2b3bb.json` |
| P18 | `461dc035` | `06de17e8` | screening | modify same file | 0/0/6 | 0 | continue, fresh runtime required | `metrics/f3d8f5bf-5769-43f1-9d4f-a030e45fa10d.json` |
| P19 | `47ec47f1` | `8670e9f5` | screening | create `operators/cost_preserving_tail_refit.py` | 6/0/4 | 850 | queue_validate, screening pass | `metrics/aafc149c-ed79-42ed-a086-22f25858c263.json` |
| P20 | `47ec47f1` | `8670e9f5` | validation | same candidate | aggregate | 0 | expand_validation, uncertain | `metrics/5ec7634c-539a-4baa-9e8f-c05896e51a30.json` |
| P21 | `47ec47f1` | `8670e9f5` | validation expand | same candidate | aggregate | 0 | queue_frozen, marginal pass | `metrics/dfaee2a0-5f2c-4133-b964-96d999f2635c.json` |
| P22 | `47ec47f1` | `8670e9f5` | frozen | same candidate | aggregate | 15000 | promote, frozen pass | `metrics/bfd03677-66f7-4930-b597-4c0c0c2d658d.json` |

Verification-heavy failures:

| Effective event | Branch | Hypothesis | Target | Failure | Evidence |
|---|---|---|---|---|---|
| VF1, around 2026-06-16T17:10:31 | `da55dd68` | `a32229a2` | remove `operators/split_vehicle.py` | `V5_solution_consistency`, heavy. Candidate removed the module but `operators/__init__.py` still imported `SplitVehicle`; import failed before solver run. | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/campaign_summary.json` shows `ModuleNotFoundError: No module named 'operators.split_vehicle'`; DB event has `verification_fail`, `verification_result=V5_solution_consistency`. |
| VF2, around 2026-06-16T17:56:29 | `47ec47f1` | `94824c98` | modify `operators/swap_orders.py` | `V5_solution_consistency`, heavy. Modified `execute` could return `None`; `vns.py` then passed `None` into `oracle.check_feasibility`, causing `AttributeError: 'NoneType' object has no attribute 'vehicles'`. | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/campaign_summary.json`; trace `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T175516763840_code_10df4d8393_8b6bb83b.json`. |

Proposal-quality blocks:

- Total: 15 proposal blocks, all pre-Protocol.
- Source: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/postrun_acceptance/research_efficiency/rep03_on_compact.research_efficiency.v1.json`, `quality_block_ledger`.
- Loop steps by branch: `9931c959` loops 4-5; `da55dd68` loop 8; `5f83d92b` loops 14-18; `e19e39e5` loop 20; `a31b6330` loops 23-25; `461dc035` loops 30-31; `47ec47f1` loop 35.
- Dominant reason: `branch_lesson_usage_semantic_mismatch`, plus two `branch_lesson_usage_linkage_unrecognized` cases. The repeated machine requirement was target/action/mechanism linkage with compact lesson IDs and changed dimensions; raw lesson text, repeated hypothesis prose, or broad mechanism-family tokens were insufficient.

## Context And Output Audit

Common Scion agent context across important sessions:

- Controlled problem and surface context through `context.list_surfaces`, `context.read_problem`, and `context.read_surface`.
- Tainted proposal/search memory through `memory.query`.
- Screening feedback through `feedback.query_screening`, usually bounded to 8 rows.
- Runtime feedback through `feedback.query_runtime`, often warning that runtime evidence was low-confidence because champion runtime was cached.
- Prompt visibility ledgers in `llm_traces/*.json` repeatedly show full `problem_summary`, `research_surfaces`, `objective_policy`, `current_champion_research_code`, and branch/sibling summaries. For hypothesis traces that mattered most, `compact_research_signals` and `branch_lesson_usage_context` were present but truncated.
- Code-generation traces are smaller and usually untruncated, consistent with architecture v3's two-round proposal split.

The following branch-by-branch replay uses DB rows, session outputs, and trace paths. Session outputs are report-only; decisions came from Contract/Verification/Protocol/Decision rows.

### Branch `fa5d75b4-915c-4862-bbde-858b66be2cf1`

Direction: `vehicle_level` `subcategory_pack_upgrade`. Parent/lineage: root lineage `fa5d75b4`; base champion `v1`.

Evolution:

- H1 `7f34bef6`: create `operators/subcategory_pack_upgrade.py`, candidate `ddab2fee5451dfbd`, P01 screening 10 cases, W/L/T 2/2/6, median delta 0, CI [-450, 725], decision `continue_explore`.
- H2 `68c3feb0`: modify same file, candidate `0d7aaf40c82f4fb5`, P02 screening 6 cases, W/L/T 0/0/6, median delta 0, decision `continue_explore`, reason included neutral signal and runtime evidence incomplete pressure.
- Terminal state: `parked_lineage`, branch code status `parked_lineage`, last screening tier `no_effect`.

Agent context and output:

- H1 sessions: `dbe23605-b740-4d7f-8f02-5912e392c0ca/output.json` (partial hypothesis) and `6b87356e-aeb3-48fb-b201-2ca9677cdcdc/output.json` (completed code).
- H2 sessions: `86f43e63-362b-4bec-99f6-b19a8eaeab71/output.json` and `609556af-d420-4633-88ed-b0ae8df7b3f0/output.json`.
- Trace index records H1 hypothesis trace `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T165048949970_hypothesis_1829e31e8b_66921124.json` and H1 code trace `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T165134515053_code_3dec6b8275_17cb7f09.json`.

Interpretation:

- This was a clean fork into a new vehicle-level subcategory-consolidation operator, then same-mechanism depth.
- Branch lessons were present and semantically projected in session summaries, but the effect was mostly report-only: it helped express avoided/contrasted lessons but did not create objective effect.
- Measurement/noise: H1 had mixed 2/2/6 screening and low practical effect; H2 all ties. Runtime comments were not decisive and were low-confidence/cached. The branch was parked correctly rather than promoted.

### Branch `9931c959-1c6e-4e04-8b6f-6bf0a0256ac2`

Direction: `order_level` `split_neutral_cost_compress` on `operators/move_order.py`. Parent/lineage: root lineage `9931c959`; base champion `v1`.

Evolution:

- H1 `fe0b896c`: modify `operators/move_order.py`, candidate `e31b32301d1b35b4`, P03 W/L/T 1/2/3, median delta 0, decision continue.
- H2 `f41ab870`: rejected before Protocol by proposal-quality block, loop 4.
- H3 `26f607aa`: rejected before Protocol by proposal-quality block, loop 5.
- H4 `61cc108c`: modify same file, candidate `6b7683d2bf1178d4`, P04 W/L/T 1/2/3, median delta 0, decision continue.
- H5 `bf3cb4f4`: modify same file, candidate `0ad1f9307a694a6a`, P05 W/L/T 1/2/3, median delta 0, decision continue.
- Terminal state: `parked_lineage`, branch code status `parked_lineage`, last tier `marginal`, failure codes `PROPOSAL`, `PROPOSAL`.

Agent context and output:

- Completed code sessions: `d89fe818-190a-4018-83a9-4c16da5a5194/output.json`, `49c07d30-a21c-43bb-a526-59987e12ea8e/output.json`, `1e821395-0c8c-4db4-b726-d41e0aee1f11/output.json`.
- Blocked/partial sessions: `e6b349d1-fa51-42b7-b4b3-ddad561073d3/output.json`, `3b1a742c-c503-40a2-81d7-78b90e41c249/output.json`, `4f6e199e-cd4d-4d9d-8ea1-2fda33ffd537/output.json`, `dbcb00ea-7fab-462f-b419-356bfe16d05d/output.json`.
- H1 completed output says the agent saw 2 of 2 screening feedback rows and runtime feedback, then produced a split-neutral order relocation replacing random `MoveOrder`.
- H5 completed output uses branch lessons with `borrowed_lessons=1`, `contrasted_lessons=3`, `preserved_same_branch_lesson=1`, `rejected_weak_positive_lessons=1`.

Interpretation:

- This branch was mainly same-mechanism depth, with a sibling-nearby order-level fork from earlier vehicle-level no-effect attempts.
- Evidence from prior branches was present in memory/screening/runtime feedback and branch lessons. It was semantically visible in successful sessions, but the two blocked hypotheses show linkage still failed when target/action/mechanism fields were absent or not machine-recognized.
- Measurement/noise: repeated 1/2/3 screening rows with zero median delta point to a stable weak/no-effect path, not a hidden positive. Continued exploration consumed attempts without changing the empirical pattern.

### Branch `da55dd68-488d-4f15-92be-7a6b7ef37308`

Direction ended as `vehicle_level` `empty_tail_absorb`; branch also attempted `guarded_cost_merge` and removal of `split_vehicle`. Parent/lineage: root lineage `da55dd68`; base champion `v1`.

Evolution:

- H1 `8f011000`: modify `operators/merge_vehicles.py` with `guarded_cost_merge`; rejected/pre-Protocol path, no Protocol metric row.
- H2 `a32229a2`: remove `operators/split_vehicle.py`; VF1 heavy verification failure, `V5_solution_consistency`.
- H3 `dd3ead76`: create `operators/empty_tail_absorb.py`, candidate `1843f993aaa0b2ee`, P06 W/L/T 2/0/8, median delta 575, decision continue.
- H4 `8ad22622`: modify same file, candidate `292875c2c2f06184`, P07 W/L/T 0/0/6, median delta 0, decision continue, reason `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`.
- Terminal state: `stale` after champion promotion, branch code status `active_no_effect`, last telemetry outcome `no_objective_effect`, failure codes `PROPOSAL`, `VERIFICATION_HEAVY`.

Agent context and output:

- Remove-session code output: `3f5e79e1-aee9-48f7-9f01-10c9857cea38/output.json`; code trace `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T170940874476_code_9f2125660a_bed8e7d0.json` and retry `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T171013991507_code_f6352be5e7_b57a671c.json`.
- Empty-tail completed sessions: `8b3d6417-bb06-4568-a8d6-aeb2e786ff68/output.json`, `4b5c4a02-45c5-4f12-aaab-d37359287e73/output.json`.
- The remove hypothesis used `contrasted_lessons=3` and appeared clean-fork aware, but the produced edit was structurally incomplete: deleting/removing a target operator needed registry/import cleanup, not only pool removal semantics.

Interpretation:

- This branch is a mixed clean-fork branch that changed mechanisms too often inside one lineage. It did not behave as a clean same-direction deep branch until `empty_tail_absorb`.
- Prior evidence influenced proposals semantically through branch lessons, but not enough to prevent an unsafe remove edit. This is an example where proposal-layer structure looked semantically plausible while Verification correctly intercepted runtime breakage.
- Measurement/noise: H3 looked weak-positive by case score (2 wins, no losses, median 575), but H4 collapsed to all ties. Low cached champion runtime made runtime pressure advisory only. The branch should not be considered a near-miss promotion.

### Branch `5f83d92b-1ab6-4ac3-ba63-ae362e5ed2f1`

Direction: `order_level` `threshold_swap` on `operators/swap_orders.py`. Parent/lineage: root lineage `5f83d92b`; base champion `v1`. This is the deepest failed branch: 7 hypotheses.

Evolution:

- H1 `903ab93c`: modify `operators/swap_orders.py`, candidate `d67178f1cb6092d5`, P08 W/L/T 3/1/2, median delta 400, decision `expand_screening`; P09 expanded to 14 cases, W/L/T 5/1/8, median delta 450, CI [100, 1450], decision continue because win-rate failed.
- H2-H6 `a90cdef8`, `0540e8aa`, `c19687a8`, `853dc3c9`, `62ee6bf3`: proposal-quality blocks at loop steps 14-18, all before code/protocol.
- H7 `aecb6611`: candidate `f5b49b2dc3fc7340`, P10 W/L/T 2/1/3, median delta 0, decision continue.
- Terminal state: `parked_lineage`, last tier `marginal`, failure codes five `PROPOSAL`.

Agent context and output:

- Initial completed output: `b2c86bd6-9adb-47fb-a174-f852bd6b2a33/output.json`; code trace `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T171715396067_code_df778e98e3_ce306de1.json`.
- Deep blocked sessions: `d2a5fcd4-9f49-4cc7-8916-1dc9e7fbdf27/output.json`, `2defeecb-dea1-4ac3-b7ea-acd4a1fa9a15/output.json`, `36cf836e-960e-4d7e-a2d8-1d4da9fe8829/output.json`, `f79830e5-7401-409b-afc0-115ec2e3cc83/output.json`, `68cb7d29-f607-47b9-95b3-18ae159703d7/output.json`, `101e5f57-67b1-449e-b07e-5ed89894fbb7/output.json`.
- The final completed output `6ed693a7-0837-459f-9f0f-52fa6adaf4c3/output.json` preserves the branch-local lesson and proposes a high-threshold loss guard. The key hypothesis trace `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T172527419774_hypothesis_cf662d0f21_e3f1a0c6.json` had full prompt sections except truncated `compact_research_signals` and `branch_lesson_usage_context`.

Interpretation:

- This is a same-mechanism depth branch with one real weak-positive transfer opportunity from H1's expanded screening. The agent attempted to preserve the weak-positive lesson but repeatedly failed the branch-lesson semantic/linkage gate before code generation.
- Evidence from prior branches was present and did influence the target: the later hypothesis explicitly targeted "small or seed-sensitive swaps" and raised activation quality. However, the effect was mostly semantic at proposal level; Protocol did not validate an improved version.
- Measurement/noise: H1 improved pair/case deltas but failed gate win-rate; expansion reduced ambiguity but not enough for validation. Later H7 degraded to zero median. This branch shows weak-positive signal but not robust promotion evidence.

### Branch `e19e39e5-9203-449c-b5bb-4198b0b2baa0`

Direction: vehicle-level merge/binpack alternatives. Parent/lineage: root lineage `e19e39e5`; base champion `v1`.

Evolution:

- H1 `6c837a1b`: modify `operators/merge_vehicles.py` with `same_signature_cost_merge`; pre-Protocol/proposal-block path.
- H2 `a75e2942`: create `operators/region_category_binpack_cost.py`, P11 W/L/T 0/2/8, median delta -25, decision `abandon`, reasons included `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN` and `SCREENING_SOFT_ABANDON_NEGATIVE_DELTA`.
- Formal candidate index has two artifacts for H2: candidate IDs `61fd7341703cfee7` and `a741b0976dc58c25`, both branch code status `discarded`. This duplication should be treated as artifact/replay bookkeeping, not two independent successful protocol rows.
- Terminal state: `abandoned`, discarded.

Agent context and output:

- H1 partial: `1b03c80d-efdf-4d36-a133-86d3f95bb4b5/output.json`.
- H2 completed code: `398ba3cd-9ba2-4094-9d39-b3a6ebb51add/output.json` and trace refs around `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T172933088746_tool_selection_86ba5f52dc_c805328c.json` and `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T172938179539_code_cf48b9f246_2a348742.json`.
- Quality block loop 20 was `branch_lesson_usage_linkage_unrecognized`: branch_lesson_usage named a lesson and contrast dimensions but missed recognized target/action/mechanism linkage.

Interpretation:

- This was intended as a clean fork/sibling-nearby contrast from previous no-effect subcategory consolidation attempts.
- Branch lessons were present but mechanically insufficient at loop 20. The eventual region/category binpack candidate had a real Protocol row and failed cleanly.
- Measurement/noise: P11 had no case wins and negative median delta, so abandonment was substantive, not noise-driven.

### Branch `a31b6330-19a5-4824-8118-600be8a9c2ee`

Direction: `vehicle_level` `redundant_carrier_eliminate`. Parent/lineage: root lineage `a31b6330`; base champion `v1`.

Evolution:

- H1 `b9a45ea2`: create `operators/redundant_carrier_eliminate.py`, candidate `72a201f331fc5721`, P12 W/L/T 4/0/6, median delta 425, CI [0, 1275], decision continue, weak signal.
- H2-H4 `8c802818`, `bb32d9bc`, `8db465ca`: proposal-quality blocks at loop steps 23-25.
- H5 `4794892f`: modify same file, candidate `e1f688920f97f58a`, P13 W/L/T 0/0/6, median delta 0, decision continue, fresh runtime required.
- Terminal state: `parked_lineage`, last tier `no_effect`, branch code status `parked_lineage`.

Agent context and output:

- H1 completed output: `2534eceb-da05-49b5-b195-74b427c8be18/output.json`.
- H5 completed output: `d9f61ad0-f9ed-4ccf-ae9f-f5c6cd1b984a/output.json`; it saw 8 of 12 screening rows and runtime feedback, preserved same-branch lesson, and proposed bounded regret-ranked evacuation.
- H5 trace `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T173814665548_code_b06a25061f_7974320d.json` completed code generation.

Interpretation:

- This is a weak-positive transfer branch: H1 had 4 wins and no losses but many ties. The agent tried same-mechanism depth, but proposal-quality gates blocked three intermediate refinements.
- Evidence from H1 was semantically present in H5 via `preserved_same_branch_lesson`, but the actual refined candidate lost the weak-positive signal and became all ties.
- Measurement/noise: H1 may reflect sparse activation or case-specific opportunity; H5 suggests the refined gate was too conservative/no-op. Low cached runtime means runtime improvement was not a reliable differentiator.

### Branch `68e9cd7e-2a5a-4bde-8975-8abdd9af54ee`

Direction: `vehicle_level` `locked_cluster_coalesce`. Parent/lineage: root lineage `68e9cd7e`; base champion `v1`.

Evolution:

- H1 `c6159286`: create `operators/locked_cluster_coalesce.py`, candidate `8ddbbb811ce3b9c9`, P14 W/L/T 1/1/8, median delta 0, decision continue.
- H2 `56c38375`: modify same file, candidate `93f03526cde7e7cc`, P15 W/L/T 0/0/6, median delta 0, decision continue, fresh runtime required.
- Terminal state: `parked_lineage`, last tier `no_effect`.

Agent context and output:

- Completed sessions: `f96ec30a-a464-46e1-8c18-0b16e145bcf3/output.json` for H1 code and `d46565c5-862b-435d-911e-5281fbe71f43/output.json` for H2 code.
- Trace refs include `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T174103653745_tool_selection_f5bd660939_f9ccc91e.json` and `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T174105924251_code_acc3554d5d_45fd06fc.json`.

Interpretation:

- Clean fork into a new locked-order consolidation mechanism, followed by same-mechanism refinement.
- Branch lessons were present, but no later branch appears to successfully borrow a specific positive lesson from this branch. It mostly contributed no-effect/sibling contrast evidence.
- Measurement/noise: initial 1/1/8 was neutral; follow-up all ties. This is substantive no-effect under screening.

### Branch `461dc035-5206-4a74-a776-934c5181556c`

Direction: `vehicle_level` `suffix_load_cost_trim`. Parent/lineage: root lineage `461dc035`; base champion `v1`.

Evolution:

- H1 `762b4e26`: create `operators/suffix_load_cost_trim.py`, candidate `a18aa20dd4395d50`, P16 W/L/T 3/1/6, median delta 275, decision continue.
- H2 `e5572626`: proposal-quality block, loop 30.
- H3 `099162e7`: proposal-quality block, loop 31.
- H4 `d0001f56`: modify same file, candidate `86745cc04a63f035`, P17 W/L/T 0/0/6, median delta 0, decision continue, fresh runtime required.
- H5 `06de17e8`: modify same file, candidate `f1d795b775e18209`, P18 W/L/T 0/0/6, median delta 0, decision continue, fresh runtime required.
- Terminal state: `stale` after champion promotion, branch code status `active_no_effect`, last telemetry outcome `no_objective_effect`.

Agent context and output:

- Initial completed output: `e18e0bc8-d83d-46d0-b30c-7961078b1302/output.json`.
- Late partial: `5531be74-542f-496d-9074-3e9758dd6d33/output.json`; trace `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T175229886582_hypothesis_b5c3653153_24a36000.json` shows the agent saw truncated `compact_research_signals` and `branch_lesson_usage_context`, then proposed a repair clearing unsupported telemetry declarations.
- Completed repair output: `b1d7378a-46fd-46f0-be38-484a03028ffd/output.json`; branch_lesson_usage had `avoided_lessons=1`, `contrasted_lessons=2`, `preserved_same_branch_lesson=1`.

Interpretation:

- This branch started as a clean fork with a marginal positive result, then attempted same-mechanism depth. It became a late plateau/drain branch: proposal blocks plus repeated no-effect/fresh-runtime-tie outcomes.
- Evidence transfer was partially semantic: the agent explicitly responded to unsupported telemetry declarations and preserved the same branch mechanism, but the refined Protocol rows stayed all ties.
- Measurement/noise: H1 had 3/1/6 and median 275, too weak for validation. H4/H5 all ties make the plateau substantive. Runtime pressure was low-confidence and did not produce a schedulable replay candidate before terminal drain.

### Branch `47ec47f1-09d9-4057-ae51-a6ba13279e40`

Direction: eventually `vehicle_level` `cost_preserving_tail_refit`; parent/lineage root `47ec47f1`; base champion `v1`. This is the promoted branch.

Evolution:

- H1 `94824c98`: modify `operators/swap_orders.py` with `split_neutral_cost_swap`; VF2 heavy verification failure. The branch then effectively abandoned that order-level edit.
- H2 `7a4f8113`: create `operators/single_subcategory_upgrade_pack.py`; proposal-quality block at loop 35 due `branch_lesson_usage_linkage_unrecognized`.
- H3 `8670e9f5`: create `operators/cost_preserving_tail_refit.py`, candidate `1370e3f2faa829c1`. P19 screening pass, P20/P21 validation marginal pass after expansion, P22 frozen pass, promoted to champion `v2`.
- Terminal state: `promoted`.

Agent context and output:

- H1 partial and code: `efb493ae-bcad-4095-b125-c7e17812fe57/output.json` and `d2f6bc3e-e4fd-4c5c-be5d-6a23a47f699e/output.json`. The H1 hypothesis trace recorded a schema preview retry for unsupported telemetry (`C11_expected_telemetry`) before passing; code trace `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T175516763840_code_10df4d8393_8b6bb83b.json` produced an exact replace edit that later failed V5.
- H2 partial: `d79b144a-01e9-4383-bd0d-74e7cb79f65b/output.json`; quality block loop 35 reported missing recognized linkage fields for `operators/single_subcategory_upgrade_pack.py`.
- H3 partial and code: `5770d632-2593-4e9c-8574-5cee58689c5e/output.json` and `02b1fcef-a153-4e2a-86e3-05c35bcbe6ce/output.json`.
- H3 hypothesis traces:
  - `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T175744314647_hypothesis_942735d37d_bb3c4909.json`
  - `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T175811991123_hypothesis_6a7a7a203d_fd9b7d25.json`
  Both traces show provider-visible prompt ledgers with 31-32 full sections and two truncated sections: `compact_research_signals` and `branch_lesson_usage_context`.
- H3 code trace:
  - `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/campaign/llm_traces/20260616T175852092614_code_fc1795aaf1_030afdb0.json`
  It has all 17 prompt sections full, no truncation, and output `premise_check=supported`, `file_path=operators/cost_preserving_tail_refit.py`, `action=create`, `edit_intent=full_file`.

What the agent saw:

- `compact_research_signals` included global blacklist entries `vehicle_level/remove -> operators/split_vehicle.py` and `order_level/modify -> operators/swap_orders.py`.
- Branch history visible to the successful H3 trace included Round 34 failed verification on `operators/swap_orders.py` and Round 35 proposal block on `operators/single_subcategory_upgrade_pack.py`.
- Sibling branches visible in prompt context included no-effect `empty_tail_absorb` and `suffix_load_cost_trim`, including fresh-runtime-required notes and low cached champion runtime advisory.
- Branch lesson records included no-effect/bridge lessons from `a31b6330`, `68e9cd7e`, `e19e39e5`, `461dc035`, `da55dd68`, and `fa5d75b4`.

What the agent produced:

- A full-source evacuation operator: choose an under-filled non-empty source vehicle, move all unlocked orders into compatible existing vehicles, preserve subcategory membership counts, resize affected vehicles, delete the emptied source, and no-op unless cost strictly decreases.
- This was materially different from suffix trimming, empty-tail absorption, and swap-based local edits because it attempted whole-source evacuation while preserving splits.

Interpretation:

- This branch is a clean fork after one verification-heavy failure and one proposal-quality block. It is also the best example of semantic branch-lesson transfer: the successful proposal contrasts prior no-effect mechanisms and changes mechanism family, activation path, and effect path.
- Evidence from prior branches influenced the proposal semantically, but not as Decision input. The Decision path remains valid because promotion came through screening, validation, and frozen Protocol rows.
- Measurement/noise: screening used cached champion runtime and had only 6 case wins with 4 ties, so screening alone would be insufficient. Validation was marginal and needed expansion. Frozen was high-confidence, fresh, 12/12 pair wins, median delta 15000, and runtime ratio below 1.0 in the sampled pair evidence. The promotion is robust as a single promotion.

## Information Transfer Between Branches

Branch-lesson usage was always present at the session level in the proposal trajectory manifest:

- `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/postrun_acceptance/manifests/rep03_on_compact.proposal_trajectory_manifest.v1.json`
- `usage_present_count=55`, `semantic_projection_present_count=55`, `usage_missing_count=0`.
- Field counts: `contrasted_lessons=97`, `avoided_lessons=78`, `preserved_same_branch_lesson=30`, `rejected_weak_positive_lessons=29`, `borrowed_lessons=3`.
- Prompt visibility: `branch_lesson_context_truncated_trace_count=52`.

Interpretation by branch:

- `fa5d75b4`: lessons present, mainly avoidance/contrast, but produced no objective effect.
- `9931c959`: cross-branch lessons drove a clean fork into order-level `move_order`, but linkage failures at loops 4-5 show the model could mention lessons without satisfying machine-readable target/action/mechanism semantics.
- `da55dd68`: lessons did not prevent an unsafe remove operation; Verification, not semantic memory, protected correctness.
- `5f83d92b`: same-branch weak-positive preservation was semantically attempted, but five proposal blocks prevented most refinements from reaching code.
- `e19e39e5`: clean-fork contrast was attempted but one linkage-unrecognized block and one negative Protocol row ended the branch.
- `a31b6330`: weak-positive signal was preserved in later proposal output, but the follow-up became a no-effect candidate.
- `68e9cd7e`: contributed no-effect bridge lessons for later branches.
- `461dc035`: contributed no-effect and fresh-runtime-pressure lessons; later promoted branch explicitly contrasted suffix trimming.
- `47ec47f1`: the successful cost-preserving-tail-refit proposal was the only branch where historical lessons appear to have produced a materially different, validated mechanism.

The transfer layer is therefore partially effective but noisy. It reliably exposed prior branch information; it did not reliably convert that exposure into valid proposals. The strongest transfer happened when lessons were used as contrast/avoidance rather than as a direct mechanism template.

## Noise And Measurement

Screening vs validation/frozen consistency:

- Most screening rows were tie-heavy. Across the cell summary, screening case totals were 31 wins, 15 losses, 104 ties. Tie dominance made weak positives easy to over-read.
- The promoted branch was the exception: screening 6/0/4, validation pass only after expansion, frozen 12/12 pair wins. That sequence supports promotion only after frozen, not at screening.
- Weak-positive non-promoted branches did not survive refinement:
  - `5f83d92b` expanded from 3/1/2 to 5/1/8 but stayed below win-rate gate; later H7 became 2/1/3 with median 0.
  - `a31b6330` started 4/0/6 but follow-up was 0/0/6.
  - `461dc035` started 3/1/6 but follow-ups were 0/0/6.

Cached champion/runtime confidence:

- Many screening rows had `runtime_confidence=low_cached_champion`, visible in metrics and feedback. Runtime advisories were correctly report-only/low-confidence and should not be treated as promotion evidence.
- Runtime pressure still influenced proposals semantically, causing repeated "fresh champion required" and "runtime tie" planning. The terminal drain reported pressure but no schedulable replay candidate.

Fresh replay behavior:

- Research efficiency report: `fresh_runtime_replay_drain.attempts=1`, `blocked=1`, `executed=0`, stopped reason `pressure_no_schedulable_replay_candidate`.
- No fresh replay Protocol rows were available to clear late runtime pressure for no-effect branches.

No-effect loops:

- `da55dd68`, `68e9cd7e`, `461dc035`, and parts of `a31b6330` repeatedly returned 0/0/6 ties.
- These are not decisive losses, but they are substantive search drain because the mechanisms did not activate or did not create objective movement on screening cases.

Robustness of promotion:

- The promotion is robust as a single active-champion improvement because frozen was high-confidence and fresh.
- It is not evidence of sustained search continuity because no follow-up champion `v3` was found and all active branches were stale or parked after champion change.

## Failure/Quality Taxonomy

Proposal quality blocks:

- Count: 15.
- Primary mechanism: branch_lesson_usage semantic mismatch or linkage unrecognized.
- Evidence path: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/postrun_acceptance/research_efficiency/rep03_on_compact.research_efficiency.v1.json`.
- Concrete examples:
  - Loop 4 and 5, branch `9931c959`: missing target/action linkage for `operators/move_order.py`, `split_neutral_cost_compress`.
  - Loop 14-18, branch `5f83d92b`: repeated semantic mismatch while trying to refine `threshold_swap`.
  - Loop 35, branch `47ec47f1`: `branch_lesson_usage_linkage_unrecognized` for `operators/single_subcategory_upgrade_pack.py`; missing recognized linkage fields.

Code/edit/verification failures:

- No old-string failures in rep03.
- No non-fatal agentic code-generation failures reported.
- Two heavy verification failures:
  - `da55dd68/a32229a2`: remove `split_vehicle` broke import consistency.
  - `47ec47f1/94824c98`: `swap_orders.py` could return `None`, violating operator semantics.

Tool timeout:

- `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep03/on_compact/run.log` line 3: `Tool call timeout (attempt 1/2)`.
- The run recovered; no wrapper/cell crash occurred.

Proposal-quality stagnation:

- Same run log: `STAGNATION [proposal_quality_loop] failure_code='proposal' repeated 5 consecutive times; ... suggested: inspect_agent_trace`.
- This maps to the deepest `5f83d92b` block cluster, where five consecutive blocked threshold-swap refinements did not reach Protocol.

No-effect loops and stale branches:

- After champion promotion, `da55dd68` and `461dc035` were left `stale`, active no-effect.
- Parked lineages (`fa5d75b4`, `9931c959`, `5f83d92b`, `a31b6330`, `68e9cd7e`) indicate budget moved away from weak or no-effect mechanisms rather than proving them invalid under fresh replay.

## Interpretation

rep03 shows one valid production warehouse promotion, not continuous promotion continuity. The promoted operator was not a random aggregate artifact: it survived screening, validation expansion, and frozen with high-confidence pair wins. However, most branch-level search was inefficient. The cell spent many proposal attempts on mechanisms that either did not activate, produced all ties, or failed branch-lesson semantic gates before code.

Compared cautiously to the v0.3 reference:

- v0.3 production Sonnet reference: 3/3 campaigns promoted after evidence/runtime fixes.
- Strongest v0.3 synthetic reference: 4 continuous promotions.
- rep03: 1 promotion in this repeat, final champion `v2`, no `v3` chain.

Therefore rep03 demonstrates isolated promotion capability under v0.4 warehouse longrun, not v0.3-style continuity. It does show that compact measurement diagnostics can carry enough cross-branch information for a successful clean fork, but only after multiple blocked and failed branches. The branch-lesson layer is useful as report/proposal context, but it is currently too strict or too hard for the model to satisfy consistently, causing search drain.

## Concrete Repair Hypotheses

1. Add a branch-lesson usage canonicalizer before quality gating.
   - Evidence: 15 proposal blocks; most failures ask for target/action/mechanism linkage that the model often intends but encodes incorrectly.
   - Repair: normalize aliases and populate target/action/mechanism from the formal hypothesis when unambiguous, while still requiring explicit lesson IDs and changed dimensions.
   - Acceptance: reduce proposal-quality blocks on a comparable 24-round cell by at least 50% without increasing invalid Contract/Verification pass-through.

2. Separate weak-positive refinement from clean-fork contrast requirements.
   - Evidence: `5f83d92b` had a real weak-positive screening expansion but five blocked refinements. Same-branch refinement should not need the same contrast burden as sibling clean forks.
   - Repair: for same-branch follow-up, require `preserved_same_branch_lesson` plus concrete mechanism delta; do not require clean-fork contrast fields unless the target/mechanism changes.
   - Acceptance: threshold/suffix/redundant-carrier weak-positive branches should produce at least one valid code candidate after a weak-positive row.

3. Add a remove-operation structural checklist.
   - Evidence: `da55dd68/a32229a2` removed `operators/split_vehicle.py` but left import/registry dependencies.
   - Repair: Contract or pre-Verification should require registry and `operators/__init__.py` consistency for remove operations.
   - Acceptance: no remove candidate reaches V5 with `ModuleNotFoundError` for the removed operator.

4. Add operator `execute` return-type invariant tests before heavy Verification.
   - Evidence: `47ec47f1/94824c98` returned `None`, then oracle crashed with `NoneType`.
   - Repair: lightweight semantic check: execute must return a `Solution` on no-op and success paths for each modified operator.
   - Acceptance: catch `None` returns as a cheap verification failure with targeted repair feedback.

5. Make fresh-runtime replay schedulable for runtime-tie branches.
   - Evidence: terminal drain had fresh runtime pressure but `executed=0`, blocked by `pressure_no_schedulable_replay_candidate`.
   - Repair: when a branch has repeated `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` and retained candidate identity, materialize a structured replay candidate before branch parking.
   - Acceptance: at least one no-effect/runtime-tie branch receives a fresh replay row or a machine-readable reason why replay identity is incomplete.

6. Promote contrast-over-template transfer in context.
   - Evidence: direct same-mechanism refinements usually drained; the promoted `cost_preserving_tail_refit` succeeded by contrasting suffix trim, empty-tail absorb, swap, and redundant-carrier lessons.
   - Repair: branch lesson summaries should rank "avoid/contrast these failure shapes" above "borrow this mechanism" unless the source branch has validation/frozen evidence.
   - Acceptance: new branches after plateau should more often change effect path and activation path, not just rename the same subcategory-consolidation family.

7. Treat low cached champion runtime as planning uncertainty, not branch priority.
   - Evidence: many branches entered fresh-runtime pressure after all-tie screening; runtime did not close because no replay candidate was scheduled.
   - Repair: explicit branch state `objective_no_effect_runtime_uncertain` with two routes only: fresh replay candidate if replayable, or clean fork away from mechanism.
   - Acceptance: fewer same-mechanism no-effect continuations after two all-tie rows with cached runtime.
