# Warehouse Analysis

Run root:

```text
/home/clawd/research/scion-experiments/v04-dual-sonnet-50r-20260505T023113Z/warehouse
```

Campaign directory:

```text
/home/clawd/research/scion-experiments/v04-dual-sonnet-50r-20260505T023113Z/warehouse/campaign
```

## Completion

| Field | Value |
| --- | --- |
| Exit | `EXIT_CODE:0` |
| Stop reason | `max_rounds_exhausted` |
| Rounds | `50/50` |
| Protocol experiments | `42` |
| Final champion | `v4_r2` |
| Code promotions | `3` |
| Persisted weight revisions | `2` |
| Frozen budget | `3/3` used |
| Active branches | `0` |

The earlier observed `49/50` state was transient. The final artifacts show
`50/50`, `run.log` ends with `Campaign finished`, and no campaign/solver
process remains.

## Aggregate Evidence

| Metric | Value |
| --- | ---: |
| Referenced metric files | 42 |
| Attempted pairs | 786 |
| Valid pairs | 786 |
| Failed pairs | 0 |
| Candidate failed pairs | 0 |
| Champion failed pairs | 0 |
| Pair wins | 466 |
| Pair losses | 259 |
| Pair ties | 61 |
| Screening metric rounds | 30 |
| Validation metric rounds | 9 |
| Frozen metric rounds | 3 |

Warehouse failures were mostly proposal/governance quality issues, not solver
runtime failures.

## Per-Round Validity

Columns:

- `input`: `locus/action/target`.
- `stage`: first decisive gate or protocol stage.
- `wr`: protocol win rate when present.
- `med`: median delta on the decisive objective when present.
- `rt`: median candidate/champion runtime ratio when present.
- `fail`: failed pair count.

| R | Input | Stage | Decision | wr | med | rt | fail | Validity |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `vehicle_level/create_new/operators/subcategory_consolidate.py` | screening | `expand_screening` | 0.500 | 0.0 | 0.950 | 0 | Borderline evidence, expanded correctly. |
| 2 | `vehicle_level/create_new/operators/subcategory_consolidate.py` | screening | `continue_explore` | 0.500 | 0.5 | 0.938 | 0 | Still borderline; branch kept exploring. |
| 3 | `vehicle_level/modify/operators/subcategory_consolidate.py` | screening | `abandon` | 0.000 | 0.0 | 1.008 | 0 | Complete screening failure. |
| 4 | `order_level/create_new/operators/subcategory_cross_move.py` | screening | `queue_validate` | 0.600 | 1.75 | 0.784 | 0 | Valid promotion path start. |
| 5 | `order_level/create_new/operators/subcategory_cross_move.py` | validation | `queue_frozen` | 1.000 | 12.0 | 0.810 | 0 | Validation pass. |
| 6 | `order_level/create_new/operators/subcategory_cross_move.py` | frozen | `promote` | 1.000 | 15.0 | 0.869 | 0 | Promoted to `v2_r0`. |
| 7 | `vehicle_level/create_new/operators/subcategory_merge_chain.py` | screening | `abandon` | 0.200 | 0.0 | 0.851 | 0 | Complete screening failure. |
| 8 | `order_level/modify/operators/subcategory_cross_move.py` | screening | `continue_explore` | 0.333 | 0.25 | 0.933 | 0 | Weak evidence, continued. |
| 9 | `vehicle_level/create_new/operators/subcategory_intra_repack.py` | screening | `queue_validate` | 0.600 | 1.0 | 0.828 | 0 | Valid second promotion path start. |
| 10 | `vehicle_level/create_new/operators/subcategory_intra_repack.py` | validation | `queue_frozen` | 0.833 | 7.0 | 0.837 | 0 | Validation pass. |
| 11 | `vehicle_level/create_new/operators/subcategory_intra_repack.py` | frozen | `promote` | 1.000 | 11.5 | 0.877 | 0 | Promoted to `v3_r0`. |
| 12 | `vehicle_level/modify/operators/subcategory_intra_repack.py` | code_generation | `-` | - | - | - | - | LLM code generation timeout. |
| 13 | `vehicle_level/modify/operators/subcategory_intra_repack.py` | code_generation | `-` | - | - | - | - | LLM code generation timeout, retry rejected. |
| 14 | `vehicle_level/modify/operators/subcategory_intra_repack.py` | hypothesis_contract | `-` | - | - | - | - | `C10_novelty` duplicate. |
| 15 | `order_level/create_new/operators/subcategory_targeted_swap.py` | screening | `abandon` | 0.000 | -0.5 | 1.032 | 0 | Complete screening failure. |
| 16 | `order_level/create_new/operators/subcategory_order_exchange.py` | screening | `abandon` | 0.200 | -0.25 | 1.021 | 0 | Complete screening failure. |
| 17 | `vehicle_level/create_new/operators/subcategory_full_consolidate.py` | screening | `abandon` | 0.000 | -4.25 | 0.665 | 0 | Faster but worse objective. |
| 18 | `vehicle_level/modify/operators/merge_vehicles.py` | screening | `continue_explore` | 0.333 | 0.5 | 0.942 | 0 | Weak evidence, continued. |
| 19 | `vehicle_level/modify/operators/destroy_rebuild.py` | screening | `queue_validate` | 0.667 | 1.25 | 0.965 | 0 | Passed screening. |
| 20 | `vehicle_level/modify/operators/destroy_rebuild.py` | validation | `expand_validation` | 0.667 | 3.0 | 1.059 | 0 | Uncertain validation, expanded. |
| 21 | `vehicle_level/modify/operators/destroy_rebuild.py` | validation | `queue_frozen` | 0.800 | 4.0 | 1.099 | 0 | Marginal pass to frozen path. |
| 22 | `vehicle_level/modify/operators/destroy_rebuild.py` | screening | `continue_explore` | 0.333 | 0.5 | 1.070 | 0 | Later branch evidence weakened. |
| 23 | `order_level/modify/operators/move_order.py` | screening | `abandon` | 0.167 | 0.25 | 1.030 | 0 | Complete screening failure. |
| 24 | `order_level/create_new/operators/subcategory_greedy_reassign.py` | screening | `abandon` | 0.200 | 0.0 | 0.884 | 0 | Complete screening failure. |
| 25 | `vehicle_level/create_new/operators/subcategory_bin_pack.py` | screening | `abandon` | 0.100 | -0.75 | 0.822 | 0 | Complete screening failure. |
| 26 | `vehicle_level/modify/operators/destroy_rebuild.py` | hypothesis_contract | `-` | - | - | - | - | `C10_novelty` duplicate. |
| 27 | `order_level/create_new/operators/subcategory_anchor_upgrade.py` | screening | `abandon` | 0.200 | -0.25 | 0.922 | 0 | Complete screening failure. |
| 28 | `order_level/modify/operators/move_order.py` | hypothesis_contract | `-` | - | - | - | - | `C10_novelty` duplicate. |
| 29 | `vehicle_level/create_new/operators/subcategory_isolation_split.py` | screening | `abandon` | 0.200 | 0.0 | 0.982 | 0 | Complete screening failure. |
| 30 | `order_level/modify/operators/swap_orders.py` | screening | `abandon` | 0.167 | 0.0 | 0.909 | 0 | Complete screening failure. |
| 31 | `vehicle_level/modify/operators/destroy_rebuild.py` | hypothesis_contract | `-` | - | - | - | - | `C10_novelty` duplicate. |
| 32 | `vehicle_level/create_new/operators/subcategory_downgrade_repack.py` | screening | `abandon` | 0.200 | -0.5 | 1.047 | 0 | Complete screening failure. |
| 33 | `vehicle_level/create_new/operators/subcategory_rightsize_offload.py` | screening | `expand_screening` | 0.500 | 0.25 | 0.995 | 0 | Borderline start of third promotion path. |
| 34 | `vehicle_level/create_new/operators/subcategory_rightsize_offload.py` | screening | `queue_validate` | 0.563 | 0.5 | 1.028 | 0 | Expanded screening passed. |
| 35 | `vehicle_level/create_new/operators/subcategory_rightsize_offload.py` | validation | `expand_validation` | 0.833 | 5.5 | 0.987 | 0 | Strong but uncertain validation. |
| 36 | `vehicle_level/create_new/operators/subcategory_rightsize_offload.py` | validation | `queue_frozen` | 0.900 | 4.0 | 0.944 | 0 | Expanded validation passed. |
| 37 | `vehicle_level/create_new/operators/subcategory_rightsize_offload.py` | frozen | `promote` | 1.000 | 2.5 | 0.985 | 0 | Promoted to `v4_r1`. |
| 38 | `vehicle_level/create_new/operators/subcategory_vehicle_eliminate.py` | screening | `queue_validate` | 0.700 | 1.5 | 0.775 | 0 | Passed screening after frozen budget was nearly exhausted. |
| 39 | `vehicle_level/create_new/operators/subcategory_vehicle_eliminate.py` | validation | `expand_validation` | 0.833 | 10.5 | 0.863 | 0 | Strong but uncertain validation. |
| 40 | `vehicle_level/create_new/operators/subcategory_vehicle_eliminate.py` | validation | `queue_frozen` | 0.900 | 3.5 | 0.946 | 0 | Would enter frozen. |
| 41 | `vehicle_level/create_new/operators/subcategory_vehicle_eliminate.py` | frozen_budget | `abandon` | 0.000 | 0.0 | - | 0 | Correctly blocked by exhausted frozen budget. |
| 42 | `vehicle_level/create_new/operators/subcategory_pairwise_swap_consolidate.py` | screening | `abandon` | 0.100 | 0.0 | 1.004 | 0 | Complete screening failure. |
| 43 | `vehicle_level/create_new/operators/subcategory_vehicle_eliminate2.py` | screening | `queue_validate` | 0.700 | 1.5 | 0.862 | 0 | Passed screening, but no frozen budget left downstream. |
| 44 | `vehicle_level/create_new/operators/subcategory_vehicle_eliminate2.py` | validation | `queue_frozen` | 0.833 | 9.5 | 0.868 | 0 | Validation pass; later path constrained by budget/search state. |
| 45 | `vehicle_level/create_new/operators/subcategory_vehicle_eliminate2.py` | screening | `continue_explore` | 0.300 | 0.5 | 0.949 | 0 | Weak evidence, continued. |
| 46 | `proposal/create_new/-` | proposal | `-` | - | - | - | - | Proposal schema error; target/protected objectives emitted as strings. |
| 47 | `vehicle_level/modify/operators/subcategory_vehicle_eliminate2.py` | screening | `abandon` | 0.000 | 0.0 | 0.998 | 0 | Complete screening failure. |
| 48 | `vehicle_level/create_new/operators/subcategory_chain_move.py` | screening | `continue_explore` | 0.300 | 0.0 | 1.037 | 0 | Weak evidence, continued. |
| 49 | `vehicle_level/modify/operators/subcategory_intra_repack.py` | screening | `abandon` | 0.000 | 0.0 | 0.969 | 0 | Complete screening failure. |
| 50 | `vehicle_level/create_new/operators/subcategory_vehicle_eliminate3.py` | screening | `abandon` | 0.100 | 0.0 | 0.899 | 0 | Final round completed normally. |

## Promotion Paths

### Promotion 1: `v2_r0`

| Round | Stage | Decision | Win rate | Median delta | CI |
| ---: | --- | --- | ---: | ---: | --- |
| 4 | screening | `queue_validate` | 0.600 | 1.75 | `[0.0, 6.0]` |
| 5 | validation | `queue_frozen` | 1.000 | 12.0 | `[4.0, 21.5]` |
| 6 | frozen | `promote` | 1.000 | 15.0 | `[7.0, 42.0]` |

Operator:

```text
operators/subcategory_cross_move.py
```

### Promotion 2: `v3_r0`

| Round | Stage | Decision | Win rate | Median delta | CI |
| ---: | --- | --- | ---: | ---: | --- |
| 9 | screening | `queue_validate` | 0.600 | 1.0 | `[0.0, 4.0]` |
| 10 | validation | `queue_frozen` | 0.833 | 7.0 | `[1.0, 19.0]` |
| 11 | frozen | `promote` | 1.000 | 11.5 | `[1.0, 23.0]` |

Operator:

```text
operators/subcategory_intra_repack.py
```

### Promotion 3: `v4_r1`

| Round | Stage | Decision | Win rate | Median delta | CI |
| ---: | --- | --- | ---: | ---: | --- |
| 33 | screening | `expand_screening` | 0.500 | 0.25 | `[-0.5, 2.0]` |
| 34 | screening | `queue_validate` | 0.563 | 0.5 | `[0.0, 2.0]` |
| 35 | validation | `expand_validation` | 0.833 | 5.5 | `[-1.5, 13.0]` |
| 36 | validation | `queue_frozen` | 0.900 | 4.0 | `[1.0, 8.5]` |
| 37 | frozen | `promote` | 1.000 | 2.5 | `[1.0, 10.0]` |

Operator:

```text
operators/subcategory_rightsize_offload.py
```

## Weight Optimization

| Champion | Operators | Evaluations | Baseline score | Best score | Improved | Elapsed |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 7 | 25 | 0.0 | 2.0 | yes | 4819.5s |
| 3 | 8 | 25 | 0.0 | 1.0 | yes | 3545.6s |
| 4 | 9 | 25 | 0.0 | 2.0 | yes | 3416.4s |

The `v2_r1` optimization was discarded because the current champion had already
advanced to `v3_r0`; this is expected stale async behavior. Persisted final
state is `v4_r2`.

## Warehouse Framework Findings

1. The branch-governed loop is functional on the v0.3 problem.
   The run produced three full screening -> validation -> frozen -> promotion
   paths with complete metrics and no failed pairs.

2. Frozen budget governance worked.
   Round 41 passed toward frozen but was blocked by exhausted campaign-level
   frozen budget. This is a correct governance result, not a solver failure.

3. Async weight optimization worked, but observability can improve.
   Stale optimization discard is expected, but it should be easier to see from
   summary artifacts without reading logs.

4. Evidence lineage still has gaps.
   Promoted champion rows have `promotion_experiment_id=NULL`; promotion paths
   can be reconstructed from summaries and events, but the champion table
   should carry the direct lineage key.

5. Warehouse is also not formal-ready.
   The campaign has strong promotion evidence, but `final_evidence_refs` are
   absent, so the summary remains `formal_ready=false`.
