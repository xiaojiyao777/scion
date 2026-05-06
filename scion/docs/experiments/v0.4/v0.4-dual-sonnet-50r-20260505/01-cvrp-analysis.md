# CVRP Analysis

Run root:

```text
/home/clawd/research/scion-experiments/v04-dual-sonnet-50r-20260505T023113Z/cvrp
```

Campaign directory:

```text
/home/clawd/research/scion-experiments/v04-dual-sonnet-50r-20260505T023113Z/cvrp/campaign
```

## Completion

| Field | Value |
| --- | --- |
| Exit | `EXIT_CODE:0` |
| Stop reason | `max_rounds_exhausted` |
| Rounds | `50/50` |
| Protocol experiments | `40` |
| Final champion | `v1_r0` |
| Promotions | `0` |
| Frozen budget | `0/2` used |
| Active branches | `1` |

All 50 rounds are represented in `campaign_summary.json`. All 40 evaluated
metrics refs exist and are complete. The final active branch is a lifecycle
cleanup anomaly, not evidence loss.

## Aggregate Evidence

| Metric | Value |
| --- | ---: |
| Referenced metric files | 40 |
| Attempted pairs | 952 |
| Valid pairs | 951 |
| Failed pairs | 1 |
| Candidate failed pairs | 1 |
| Champion failed pairs | 0 |
| Pair wins | 53 |
| Pair losses | 42 |
| Pair ties/no metric delta | 857 |
| Candidate operator attempts | 956 |
| Accepted candidate operator moves | 21 |
| Skipped/no-improvement operator moves | 935 |

The run was not a pure no-op or infrastructure failure. Generated operators and
the policy surface loaded. But the signal was overwhelmingly tie-dominated and
screening never produced a validation candidate.

## Surface Coverage

| Surface | Count | Interpretation |
| --- | ---: | --- |
| `route_local` | 21 | Most attempts were local route polishers after the baseline. |
| `route_pair` | 17 | Inter-route relocation/swap attempts were explored but failed screening. |
| `ruin_recreate` | 7 | Destroy/repair attempts were present but often weak or contract-rejected. |
| `search_policy` | 5 | Surface was exposed; only one policy modification reached screening. |

The surface model worked mechanically. The problem is that the current CVRP
surface set is still too narrow: most candidate code is appended after an
already strong ALNS+VNS baseline, so generated operators often have no
remaining accepted move.

## Per-Round Validity

Columns:

- `input`: `surface/action/target`.
- `stage`: first decisive gate or protocol stage.
- `wr`: protocol win rate when present.
- `med`: median delta on the decisive objective when present.
- `rt`: median candidate/champion runtime ratio when present.
- `fail`: failed pair count.
- `decision`: deterministic framework decision.

| R | Input | Stage | Decision | wr | med | rt | fail | Validity |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `route_local/create_new/operators/intra_route_2opt.py` | patch_contract | `-` | - | - | - | - | Rejected by `C9c_complexity_bound` for uncapped while loop. |
| 2 | `route_pair/create_new/operators/inter_route_relocate.py` | screening | `abandon` | 0.000 | 0.0 | 1.003 | 0 | Complete screening, no signal. |
| 3 | `route_local/create_new/operators/intra_route_2opt.py` | screening | `abandon` | 0.000 | 0.0 | 1.001 | 0 | Complete screening, no signal. |
| 4 | `ruin_recreate/create_new/operators/ruin_recreate_cluster.py` | verification | `-` | - | - | - | - | Rejected by `V5_solution_consistency`. |
| 5 | `route_pair/create_new/operators/inter_route_2opt_star.py` | screening | `abandon` | 0.000 | 0.0 | 1.004 | 0 | Complete screening, no signal. |
| 6 | `search_policy/modify/policies/search_policy.py` | screening | `abandon` | 0.125 | 0.0 | 1.145 | 0 | Policy loaded, but weak wins plus runtime regression. |
| 7 | `route_local/create_new/operators/intra_route_or_opt.py` | screening | `abandon` | 0.000 | 0.0 | 1.001 | 0 | Complete screening, no signal. |
| 8 | `ruin_recreate/create_new/operators/ruin_recreate_regret2.py` | patch_contract | `-` | - | - | - | - | Rejected by `C9c_complexity_bound`. |
| 9 | `ruin_recreate/create_new/operators/ruin_recreate_random_cheapest.py` | screening | `abandon` | 0.000 | 0.0 | 1.002 | 0 | Complete screening, no signal. |
| 10 | `route_pair/create_new/operators/inter_route_customer_swap.py` | screening | `abandon` | 0.000 | 0.0 | 1.001 | 0 | Complete screening, no signal. |
| 11 | `search_policy/modify/policies/search_policy.py` | hypothesis_contract | `-` | - | - | - | - | Blocked by coarse `C10_novelty` duplicate key. |
| 12 | `route_local/create_new/operators/intra_route_segment_relocate.py` | screening | `abandon` | 0.000 | 0.0 | 1.012 | 0 | Complete screening, no signal. |
| 13 | `route_local/create_new/operators/intra_route_3opt.py` | screening | `abandon` | 0.000 | 0.0 | 1.013 | 0 | Complete screening, no signal. |
| 14 | `route_pair/create_new/operators/inter_route_or_opt.py` | screening | `abandon` | 0.000 | 0.0 | 0.997 | 0 | Complete screening, no signal. |
| 15 | `route_local/create_new/operators/intra_route_node_reinsertion.py` | screening | `abandon` | 0.000 | 0.0 | 1.000 | 0 | Complete screening, no signal. |
| 16 | `route_local/create_new/operators/intra_route_reversed_segment_reinsert.py` | screening | `abandon` | 0.000 | 0.0 | 0.993 | 0 | Complete screening, no signal. |
| 17 | `route_pair/create_new/operators/inter_route_genius_insert.py` | patch_contract | `-` | - | - | - | - | Rejected by `C9c_complexity_bound`. |
| 18 | `ruin_recreate/create_new/operators/ruin_recreate_proximity.py` | screening | `abandon` | 0.000 | 0.0 | 0.999 | 0 | Complete screening, no signal. |
| 19 | `route_pair/create_new/operators/inter_route_genius_coordinated.py` | screening | `abandon` | 0.000 | 0.0 | 1.007 | 0 | Complete screening, no signal. |
| 20 | `search_policy/modify/policies/search_policy.py` | hypothesis_contract | `-` | - | - | - | - | Blocked by coarse `C10_novelty` duplicate key. |
| 21 | `route_pair/create_new/operators/inter_route_double_bridge.py` | screening | `abandon` | 0.000 | 0.0 | 0.996 | 0 | Complete screening, no signal. |
| 22 | `route_pair/create_new/operators/inter_route_3opt_star.py` | screening | `abandon` | 0.000 | 0.0 | 1.006 | 0 | Complete screening, no signal. |
| 23 | `ruin_recreate/create_new/operators/ruin_recreate_worst_removal.py` | screening | `abandon` | 0.000 | 0.0 | 1.000 | 0 | Complete screening, no signal. |
| 24 | `route_pair/create_new/operators/inter_route_double_bridge_v2.py` | screening | `abandon` | 0.000 | 0.0 | 0.999 | 0 | Complete screening, no signal. |
| 25 | `route_pair/create_new/operators/inter_route_chain_relocate.py` | screening | `abandon` | 0.000 | 0.0 | 1.009 | 0 | Complete screening, no signal. |
| 26 | `route_pair/create_new/operators/inter_route_ejection_chain.py` | screening | `abandon` | 0.000 | 0.0 | 1.014 | 0 | Complete screening, no signal. |
| 27 | `route_local/create_new/operators/intra_route_2opt_nn.py` | screening | `abandon` | 0.000 | 0.0 | 1.003 | 0 | Complete screening, no signal. |
| 28 | `ruin_recreate/create_new/operators/ruin_recreate_shaw_regret2.py` | screening | `abandon` | 0.000 | 0.0 | 1.002 | 0 | Complete screening, no signal. |
| 29 | `route_local/create_new/operators/intra_route_detour_reinsert.py` | screening | `abandon` | 0.000 | 0.0 | 1.000 | 0 | Complete screening, no signal. |
| 30 | `route_local/create_new/operators/intra_route_batch_oropt.py` | screening | `abandon` | 0.000 | 0.0 | 1.002 | 0 | Complete screening, no signal. |
| 31 | `route_pair/create_new/operators/inter_route_boundary_relocate.py` | screening | `abandon` | 0.000 | 0.0 | 1.000 | 0 | Complete screening, no signal. |
| 32 | `route_local/create_new/operators/intra_route_savings_oropt1.py` | screening | `abandon` | 0.000 | 0.0 | 0.999 | 0 | Complete screening, no signal. |
| 33 | `route_pair/create_new/operators/inter_route_load_balance_swap.py` | screening | `abandon` | 0.000 | 0.0 | 1.001 | 0 | Complete screening, no signal. |
| 34 | `route_local/create_new/operators/intra_route_double_bridge.py` | screening | `abandon` | 0.000 | 0.0 | 0.999 | 0 | Complete screening, no signal. |
| 35 | `ruin_recreate/create_new/operators/ruin_recreate_segment_extraction.py` | screening | `abandon` | 0.000 | 0.0 | 1.001 | 0 | Complete screening, no signal. |
| 36 | `route_local/create_new/operators/intra_route_global_best_oropt1.py` | screening | `abandon` | 0.000 | 0.0 | 1.002 | 0 | Complete screening, no signal. |
| 37 | `route_local/create_new/operators/intra_route_perturb_repair.py` | screening | `abandon` | 0.000 | 0.0 | 1.001 | 0 | Complete screening, no signal. |
| 38 | `route_pair/create_new/operators/inter_route_tiered_relocate.py` | screening | `abandon` | 0.000 | 0.0 | 1.009 | 0 | Complete screening, no signal. |
| 39 | `route_pair/create_new/operators/inter_route_sector_relocate.py` | verification | `-` | - | - | - | - | Rejected by `V5_solution_consistency`. |
| 40 | `route_pair/create_new/operators/inter_route_demand_gap_oropt2.py` | screening | `abandon` | 0.000 | 0.0 | 1.006 | 0 | Complete screening, no signal. |
| 41 | `search_policy/modify/policies/search_policy.py` | hypothesis_contract | `-` | - | - | - | - | Blocked by coarse `C10_novelty` duplicate key. |
| 42 | `route_local/create_new/operators/intra_route_depot_dist_oropt1.py` | screening | `abandon` | 0.000 | 0.0 | 0.994 | 1 | One candidate timeout; DB reason records runtime failure while summary still shows screening fail. |
| 43 | `route_local/create_new/operators/intra_route_depot_monotone_oropt1.py` | screening | `abandon` | 0.000 | 0.0 | 1.003 | 0 | Complete screening, no signal. |
| 44 | `route_local/create_new/operators/intra_route_annealed_oropt1.py` | screening | `abandon` | 0.083 | 0.0 | 0.997 | 0 | Weak positive signal, not enough for validation. |
| 45 | `route_pair/create_new/operators/inter_route_worst_route_relocate.py` | screening | `abandon` | 0.000 | 0.0 | 1.000 | 0 | Complete screening, no signal. |
| 46 | `route_local/create_new/operators/intra_route_best_improvement_oropt1.py` | patch_contract | `-` | - | - | - | - | Rejected by `C6_ast_syntax`. |
| 47 | `route_local/create_new/operators/intra_route_segment_swap.py` | screening | `abandon` | 0.000 | 0.0 | 1.002 | 0 | Complete screening, no signal. |
| 48 | `route_local/create_new/operators/intra_route_centroid_outlier_oropt1.py` | screening | `abandon` | 0.000 | 0.0 | 1.000 | 0 | Complete screening, no signal. |
| 49 | `route_local/create_new/operators/intra_route_parity_oropt.py` | screening | `abandon` | 0.000 | 0.0 | 1.002 | 0 | Complete screening, no signal. |
| 50 | `search_policy/modify/policies/search_policy.py` | hypothesis_contract | `-` | - | - | - | - | Blocked by coarse `C10_novelty` duplicate key. |

## Why There Were No Promotions

The immediate gate reason is straightforward:

```text
40 evaluated candidates
40 screening decisions
39 screening win-rate failures
1 candidate runtime failure in DB decision lineage
0 validation attempts
0 frozen attempts
```

The deeper reason is architectural: Scion's current CVRP package exposes
post-baseline local operators plus one narrow policy surface. The external
`vrp/src` ALNS+VNS baseline consumes most of the useful search and already
returns a strong incumbent. Generated operators then run as bounded polishers.
Most produce no accepted improvement, and a few produce weak or local changes
that cannot clear screening.

This matches the v0.4 research-surface design claim: Scion's object is the
heuristic algorithm research surface, not only "operator files". Operator
optimization remains useful, but CVRP needs broader algorithm surfaces:
construction, destroy/repair portfolio, acceptance/restart policy, budget
allocation, and potentially neighborhood scheduling.

## CVRP Framework Findings

1. `search_policy` is real but underused.
   Round 6 modified `policies/search_policy.py` and metrics recorded
   `baseline_time_fraction=0.92`, `operator_round_limit=8`,
   `policy_loaded=true`, and `policy_errors=0`. It failed because win rate was
   only `0.125` and runtime regression rate was `1.0`.

2. `C10_novelty` is too coarse for singleton policy files.
   Rounds 11, 20, 41, and 50 were blocked as duplicates even though policy
   modifications can be semantically different while sharing the same target
   file. The novelty key needs a policy-specific semantic signature.

3. Runtime governance is mostly correct.
   The one timeout failed closed. However, summary reason codes should expose
   `CANDIDATE_RUNTIME_FAILURE` directly instead of making the user compare DB
   rows and raw metrics.

4. Branch lifecycle cleanup is incomplete.
   The campaign stopped at max rounds with one active `explore` branch. This
   does not invalidate the metrics, but it violates the expectation that final
   campaign state is cleanly closed or explicitly marked as max-round residual.

5. CVRP remains not formal-ready.
   `campaign_summary.formal_readiness` is false because final evidence refs are
   absent. The run is a framework validation, not final quality evidence.
