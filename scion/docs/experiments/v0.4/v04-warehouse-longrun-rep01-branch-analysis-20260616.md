# Scion v0.4 Warehouse Longrun Rep01 Branch Analysis

Date: 2026-06-16

Cell root: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact`

Campaign dir: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign`

Campaign database: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/scion.db`

Postrun: `/home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/v04-warehouse-longrun-regression-3x24r-postrun-20260616.md`

Acceptance artifacts: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/postrun_acceptance`

## Boundary

This analysis starts from `/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md` and preserves the v3 boundary:

- Prompt, context, transcript, trace, branch lessons, and agent output artifacts are report-only explanatory material for this document.
- Deterministic Contract, Verification, Protocol, and Decision artifacts remain the evidence source for candidate acceptance, branch state, and promotion.
- LLM proposal text is treated as tainted until it passes deterministic schema, contract, verification, protocol, and decision surfaces.
- The branch model is `1 branch = 1 research direction`; iterative hypotheses inside a branch are allowed, but branch-to-branch transfer must be mediated through structured branch evidence and deterministic gates.
- Screening, validation, and frozen are separate protocol stages with exposure control. Validation/frozen evidence is used here after the run for diagnosis; it should not be read as agent-facing evidence during earlier proposal generation unless the artifact explicitly shows it was exposed.

The branch/context audit below therefore distinguishes two questions:

1. What did the agent see and produce in prompt/output artifacts?
2. What did deterministic protocol/decision evidence actually accept, reject, promote, or park?

## Cell Summary

Campaign id: `8841ae3f-f8b4-4d1e-87e5-d5fe1a77f7d9`

Requested/effective rounds: 24 / 24. The campaign summary contains 45 campaign steps because several rounds contain retries or multi-stage protocol decisions.

Terminal campaign status: `stopped_reason=max_rounds_exhausted`, final `champion_version=2`.

Branch count: 10.

Final promoted branch: `98676170-43e4-4030-827c-4f334429aa55`, hypothesis `7aa8657e-...`, target `operators/merge_vehicles.py`, mechanism `compatible_pair_cost_guard`.

Promotion dossier: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/artifacts/promotions/champion_v2_promotion_dossier.json`

Protocol stage counts from postrun/campaign artifacts:

| Stage / outcome | Count / evidence |
| --- | ---: |
| Screening metric rows | 22 |
| Validation metric rows | 2 |
| Frozen metric rows | 1 |
| Total protocol experiments | 25 |
| Champion promotions | 1 |
| Screening case wins/losses/ties | 22 / 3 / 131 |
| Screening pass rate | 0.0556 |
| Proposal-quality blocks | 21 |
| Verification failures | 1 |
| Code generation failures | 1 |
| Fresh runtime replay attempts / executed | 1 / 0 |

Main failure modes:

- Proposal-quality loop: repeated `proposal` failures, mostly `branch_lesson_usage_semantic_mismatch` or `branch_lesson_usage_linkage_unrecognized`.
- C11 telemetry schema failures: `order_level` or `vehicle_level` expected telemetry not declared by `surface.evidence`.
- One stale edit failure: `old_string_not_found in operators/merge_vehicles.py`.
- One verification-heavy failure: `V5_solution_consistency`, `AttributeError: 'Solution' object has no attribute 'instance'` in `operators/consolidate_subcategory.py` line 171.
- Many no-effect/tie continuations: deterministic screening frequently reported 0 objective effect and demanded fresh runtime evidence.
- Fresh runtime replay pressure: unresolved closure for `268be87d-e742-4b14-8500-849c7649bfee` with `pressure_no_schedulable_replay_candidate`; non-replayable materialization also affected `579465a8-5425-46fd-a076-7c4cda5de296`.

The rep01 result is therefore an isolated promotion plus many failed or no-effect branches, not a continuous chain of promotions.

## Branch Evolution Map

### Overview Table

| Branch | Base champion | Terminal state | Classification | Main path |
| --- | ---: | --- | --- | --- |
| `ccf8f4f4-74dd-41b2-92de-0c8cff533a11` | 1 | abandoned | clean fork, then weak branch churn | verification-heavy create-new failure, two proposal blocks, screening loss |
| `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74` | 1 | parked_lineage | same-mechanism depth | tail-fill weak positive, repeated lesson-linkage proposal blocks, final no-effect |
| `b31289b9-f4dd-481d-9662-6cb2e61d9890` | 2 | abandoned | clean fork plus same-mechanism prune depth | marginal prune signal, repeated no-effect, stale rescreen abandon |
| `98676170-43e4-4030-827c-4f334429aa55` | 1 | promoted | clean fork informed by prior lessons | edit failure recovered, screening expansion, validation, frozen promote |
| `5f31e5dc-5d96-4a25-a37e-cda04b960e6b` | 2 | parked_lineage | sibling-nearby / clean fork after promotion | proposal linkage blocks, hazard demote no-effect, C11, final tie |
| `943c0d2f-5ca7-41af-8f06-99e6dde40255` | 2 | explore | clean fork plus same-mechanism depth | light-tail weak signal, two no-effect refinements |
| `9c36a33a-0903-491f-999f-e6275fa5c12d` | 2 | abandoned | sibling-nearby weak-positive transfer | same-subcategory merge ties, runtime-regression abandon |
| `579465a8-5425-46fd-a076-7c4cda5de296` | 2 | explore | weak-positive transfer plus same-mechanism depth | cost-safe evacuate weak signal, C11, no-effect, fresh replay materialization gap |
| `bd88a729-c6ab-4c0f-955e-60911a66cef9` | 2 | abandoned | clean fork / nearby repack | proposal block, destroy-rebuild loss |
| `268be87d-e742-4b14-8500-849c7649bfee` | 2 | explore | same-mechanism marginal depth | cost-balanced swap marginal repeated signal, unresolved replay pressure |

Narrative tables below use short hypothesis ids only for readability. Full hypothesis lineage from `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/scion.db` is:

| Branch | Hypothesis | Parent | Action | Target |
| --- | --- | --- | --- | --- |
| `ccf8f4f4-74dd-41b2-92de-0c8cff533a11` | `4af51906-9f70-488c-84f9-30f9c6c942fb` | n/a | create_new | `operators/consolidate_subcategory.py` |
| `ccf8f4f4-74dd-41b2-92de-0c8cff533a11` | `bd1b4f6d-2cb0-4ab3-b3c8-cccb2fd335dd` | `4af51906-9f70-488c-84f9-30f9c6c942fb` | modify | `operators/move_order.py` |
| `ccf8f4f4-74dd-41b2-92de-0c8cff533a11` | `503e7145-3f16-4ee8-9e7e-f29591222624` | `bd1b4f6d-2cb0-4ab3-b3c8-cccb2fd335dd` | remove | `operators/split_vehicle.py` |
| `ccf8f4f4-74dd-41b2-92de-0c8cff533a11` | `e2088cf7-5eb3-4113-b2ec-d3cbe8e5f095` | `503e7145-3f16-4ee8-9e7e-f29591222624` | modify | `operators/merge_vehicles.py` |
| `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74` | `5a2d9a5f-ce43-4dc9-b93b-de8e205662b8` | n/a | modify | `operators/change_vehicle_type.py` |
| `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74` | `519da9b5-294f-4020-9469-3d5ccb39515d` | `5a2d9a5f-ce43-4dc9-b93b-de8e205662b8` | create_new | `operators/tail_fill_same_subcategory.py` |
| `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74` | `6a8eb12b-25e2-4110-bed9-4d664e5366a5` | `519da9b5-294f-4020-9469-3d5ccb39515d` | modify | `operators/tail_fill_same_subcategory.py` |
| `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74` | `5f52772c-d2cc-48c7-b66b-8325de5ee246` | `6a8eb12b-25e2-4110-bed9-4d664e5366a5` | modify | `operators/tail_fill_same_subcategory.py` |
| `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74` | `c1d6013b-e13b-401a-9cd7-722fc2009a17` | `5f52772c-d2cc-48c7-b66b-8325de5ee246` | modify | `operators/tail_fill_same_subcategory.py` |
| `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74` | `a7e88dc9-8cac-4c7a-b2ce-da0df741c854` | `c1d6013b-e13b-401a-9cd7-722fc2009a17` | modify | `operators/tail_fill_same_subcategory.py` |
| `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74` | `7ed08d25-3797-4e5a-8315-af064f37aee3` | `a7e88dc9-8cac-4c7a-b2ce-da0df741c854` | modify | `operators/tail_fill_same_subcategory.py` |
| `b31289b9-f4dd-481d-9662-6cb2e61d9890` | `621dd2ed-4df7-4d99-a391-fa71fc9a94e5` | n/a | modify | `operators/merge_vehicles.py` |
| `b31289b9-f4dd-481d-9662-6cb2e61d9890` | `0d825308-53ba-4617-a0b5-c5c043789fae` | `621dd2ed-4df7-4d99-a391-fa71fc9a94e5` | create_new | `operators/empty_redundant_vehicle.py` |
| `b31289b9-f4dd-481d-9662-6cb2e61d9890` | `2d90fbfb-06bd-407e-828f-c777d40f134d` | `0d825308-53ba-4617-a0b5-c5c043789fae` | create_new | `operators/prune_redundant_vehicle.py` |
| `b31289b9-f4dd-481d-9662-6cb2e61d9890` | `a76f2297-0cc0-45c2-bf9d-3a653850aef4` | `2d90fbfb-06bd-407e-828f-c777d40f134d` | modify | `operators/prune_redundant_vehicle.py` |
| `b31289b9-f4dd-481d-9662-6cb2e61d9890` | `ea5e8885-e92f-467f-a13f-faf612e779ae` | `a76f2297-0cc0-45c2-bf9d-3a653850aef4` | modify | `operators/prune_redundant_vehicle.py` |
| `98676170-43e4-4030-827c-4f334429aa55` | `7aa8657e-1fa3-4f46-af44-5aaf848c7fc5` | n/a | modify | `operators/merge_vehicles.py` |
| `5f31e5dc-5d96-4a25-a37e-cda04b960e6b` | `370179e6-5b88-47b0-bd15-7a5f74218ea1` | n/a | modify | `operators/swap_orders.py` |
| `5f31e5dc-5d96-4a25-a37e-cda04b960e6b` | `815de496-ca7b-41c4-8b9b-3155ab365eac` | `370179e6-5b88-47b0-bd15-7a5f74218ea1` | create_new | `operators/tail_empty_cheapest.py` |
| `5f31e5dc-5d96-4a25-a37e-cda04b960e6b` | `38f0f352-2677-49ad-905f-288ff6c9221b` | `815de496-ca7b-41c4-8b9b-3155ab365eac` | create_new | `operators/hazard_demote_repack.py` |
| `5f31e5dc-5d96-4a25-a37e-cda04b960e6b` | `49ace39a-7aa5-4004-bcfb-2acfad578348` | `38f0f352-2677-49ad-905f-288ff6c9221b` | modify | `operators/hazard_demote_repack.py` |
| `943c0d2f-5ca7-41af-8f06-99e6dde40255` | `9d8c0459-c95b-4b5c-ac06-6bd44c1af873` | n/a | remove | `operators/split_vehicle.py` |
| `943c0d2f-5ca7-41af-8f06-99e6dde40255` | `eaa3d907-f6b6-4491-b180-5efa9cf68e72` | `9d8c0459-c95b-4b5c-ac06-6bd44c1af873` | create_new | `operators/empty_tail_vehicle.py` |
| `943c0d2f-5ca7-41af-8f06-99e6dde40255` | `07feb645-d76e-4dc4-b84a-d780ba7ef28b` | `eaa3d907-f6b6-4491-b180-5efa9cf68e72` | create_new | `operators/light_tail_evacuate.py` |
| `943c0d2f-5ca7-41af-8f06-99e6dde40255` | `6cea2ea9-af0e-4fe0-8795-cda54a720fcb` | `07feb645-d76e-4dc4-b84a-d780ba7ef28b` | modify | `operators/light_tail_evacuate.py` |
| `943c0d2f-5ca7-41af-8f06-99e6dde40255` | `89096453-c653-4307-87ff-6548e9d29b2c` | `6cea2ea9-af0e-4fe0-8795-cda54a720fcb` | modify | `operators/light_tail_evacuate.py` |
| `9c36a33a-0903-491f-999f-e6275fa5c12d` | `b7b0db88-0e63-4b63-a3a0-34595f26c098` | n/a | modify | `operators/merge_vehicles.py` |
| `579465a8-5425-46fd-a076-7c4cda5de296` | `a16fae12-5ffc-4a1a-a048-4aa001b7bc69` | n/a | modify | `operators/move_order.py` |
| `579465a8-5425-46fd-a076-7c4cda5de296` | `5b807e51-ca0c-44b1-ae2d-a97b51f326a8` | `a16fae12-5ffc-4a1a-a048-4aa001b7bc69` | modify | `operators/move_order.py` |
| `579465a8-5425-46fd-a076-7c4cda5de296` | `ae188026-e3ea-4dd3-89af-d5042f1e59f6` | `5b807e51-ca0c-44b1-ae2d-a97b51f326a8` | modify | `operators/move_order.py` |
| `579465a8-5425-46fd-a076-7c4cda5de296` | `cd25a9bd-5acd-49a2-817e-73efe91a5521` | `ae188026-e3ea-4dd3-89af-d5042f1e59f6` | modify | `operators/move_order.py` |
| `579465a8-5425-46fd-a076-7c4cda5de296` | `06bb1071-e4e3-4348-8023-c9c7f51f05a9` | `cd25a9bd-5acd-49a2-817e-73efe91a5521` | modify | `operators/move_order.py` |
| `bd88a729-c6ab-4c0f-955e-60911a66cef9` | `3e1310e6-1612-4d0a-b790-404b9c133c1b` | n/a | modify | `operators/move_order.py` |
| `bd88a729-c6ab-4c0f-955e-60911a66cef9` | `fac6066e-81da-465b-9075-d6a292a04757` | `3e1310e6-1612-4d0a-b790-404b9c133c1b` | modify | `operators/destroy_rebuild.py` |
| `268be87d-e742-4b14-8500-849c7649bfee` | `c43c92a3-729d-4e95-847e-ba59899a17f1` | n/a | modify | `operators/swap_orders.py` |
| `268be87d-e742-4b14-8500-849c7649bfee` | `bbcfe1c4-941e-4647-b61f-6db75d92b729` | `c43c92a3-729d-4e95-847e-ba59899a17f1` | modify | `operators/swap_orders.py` |

### Branch `ccf8f4f4-74dd-41b2-92de-0c8cff533a11`

Lineage and terminal state:

- Base champion: 1.
- Terminal state: `abandoned`.
- Last feedback tier: `quality_regression`.
- Last telemetry outcome: `pair_level_positive_signal`, but deterministic branch lifecycle archived it because case-level screening failed.
- Classification: clean fork at first, then failed sibling/nearby attempts. It did not become same-mechanism depth because the first mechanism failed verification and later mechanisms changed target/action.

Evolution:

| Round | Hypothesis / step | Target | Mechanism | Protocol / decision | Evidence |
| ---: | --- | --- | --- | --- | --- |
| 1 | `4af51906-...` | `operators/consolidate_subcategory.py` | `subcategory_consolidation_repack` | verification failure | `V5_solution_consistency`; `AttributeError: 'Solution' object has no attribute 'instance'` at line 171 |
| 2 | `bd1b4f6d-...` | `operators/move_order.py` | `same_subcategory_pull_forward` | proposal blocked | `branch_lesson_usage_semantic_mismatch` |
| 3 | `503e7145-...` | `operators/split_vehicle.py` | `remove_random_splitter` | proposal blocked | `branch_lesson_usage_semantic_mismatch` |
| 4 | `e2088cf7-...` | `operators/merge_vehicles.py` | `compatible_pair_merge` | abandon | screening 0W / 2L / 4T / 6, median delta -3450, CI [-10050, 100] |

Context and outputs:

- First hypothesis session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/a9f5.../output.json`
  - The agent initially encountered C11-style telemetry repair pressure and produced a schema-valid create-new hypothesis after reducing expected telemetry.
- Code session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/20c366.../output.json`
  - The code artifact passed local static contract preview and smoke checks, but deterministic verification later failed with `V5_solution_consistency`.
- Later code session for the screened candidate: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/35f2a69a.../output.json`
  - The output for `compatible_pair_merge` showed no prior screening/runtime feedback rows available for that mechanism, so the branch lesson material was more present as guardrail context than as a successful semantic transfer.

Failure/success points:

- Proposal: rounds 2 and 3 failed before code because branch lesson usage did not provide machine-recognized target/action/mechanism linkage.
- Code/edit: first create-new code generated successfully, but failed verification; later merge code generated successfully.
- Verification: first candidate failed heavy verification.
- Protocol: final screened candidate lost at case level and was abandoned.
- Measurement: pair-level signs were insufficient; deterministic case-level screening was negative.

### Branch `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74`

Lineage and terminal state:

- Base champion: 1.
- Terminal state: `parked_lineage`.
- Last feedback tier: `no_effect`.
- Last telemetry outcome: `checkpoint_retained`.
- Classification: same-mechanism depth after the successful `tail_fill_same_subcategory` creation. The branch repeatedly tried to refine the same target and mechanism family.

Evolution:

| Round | Hypothesis / step | Target | Mechanism | Protocol / decision | Evidence |
| ---: | --- | --- | --- | --- | --- |
| 5 | `5a2d9a5f-...` | `operators/change_vehicle_type.py` | `best_safe_downgrade` | proposal blocked | semantic mismatch |
| 6 | `519da9b5-...` | `operators/tail_fill_same_subcategory.py` | `tail_fill_same_subcategory` | continue_explore | screening 4W / 0L / 6T / 10, median delta 425, CI [0, 1275] |
| 7-10 | `6a8eb12b-...`, `5f52772c-...`, `c1d6013b-...`, `a7e88dc9-...` | `operators/tail_fill_same_subcategory.py` | `tail_fill_same_subcategory` | proposal blocked | repeated semantic mismatch; some missing `target_file`/`action` |
| 11 | failed hypothesis | create-new, no accepted target | n/a | proposal failed | `C11_expected_telemetry`: `order_level` surface lacks requested telemetry fields |
| 12 | `7ed08d25-...` | `operators/tail_fill_same_subcategory.py` | `tail_fill_same_subcategory` | continue_explore, then parked | screening 0W / 0L / 6T / 6, median delta 0, CI [0, 0] |

Context and outputs:

- Successful hypothesis session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/497b.../output.json`
- Successful code session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/3d2ff.../output.json`
- C11 failed session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/e5aba.../output.json`
- Final code session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/96dd5c7e.../output.json`

Failure/success points:

- Proposal: this branch is one of the clearest proposal-quality-loop examples. The branch had a weak-positive checkpoint, but four subsequent same-target refinements were blocked because the branch lesson usage did not satisfy structured linkage requirements.
- Code/edit: accepted code sessions completed.
- Verification: no heavy verification failure after accepted code.
- Protocol: initial weak-positive retained, but final deterministic screening showed exact no-effect and parked the lineage.
- Transfer: same-branch lesson material was available, but several blocked hypotheses show that presence was not enough; the agent did not repeatedly express the linkage in the machine-required structure.
- Measurement: the first signal had positive wins but a CI touching zero; later exact ties suggest the mechanism was either exhausted or noise-dominated.

### Branch `b31289b9-f4dd-481d-9662-6cb2e61d9890`

Lineage and terminal state:

- Base champion: 2, created after the promoted branch became champion.
- Terminal state: `abandoned`.
- Last feedback tier: `no_effect`.
- Last telemetry outcome: `no_objective_effect`.
- Classification: clean fork into prune/empty-vehicle family, followed by same-mechanism prune depth.

Evolution:

| Round | Hypothesis / step | Target | Mechanism | Protocol / decision | Evidence |
| ---: | --- | --- | --- | --- | --- |
| 13 | `621dd2ed-...` | `operators/merge_vehicles.py` | `compatible_cost_merge` | proposal blocked | semantic mismatch; missing target/action linkage |
| 14 | `0d825308-...` | `operators/empty_redundant_vehicle.py` | `empty_redundant_vehicle` | proposal blocked | linkage unrecognized |
| 15 | `2d90fbfb-...` | `operators/prune_redundant_vehicle.py` | prune redundant vehicle | continue_explore | screening 3W / 0L / 7T / 10, median delta 200, CI [-400, 2275] |
| 16 | `a76f2297-...` | `operators/prune_redundant_vehicle.py` | prune refinement | continue_explore | 0W / 0L / 6T, `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` |
| 17 | `ea5e8885-...` | `operators/prune_redundant_vehicle.py` | prune refinement | continue_explore | 0W / 0L / 6T |
| 23 | `ea5e8885-...` stale rescreen | `operators/prune_redundant_vehicle.py` | prune refinement | abandon | stale rescreen failed after champion context changed |

Context and outputs:

- Accepted prune code: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/e47b9e57.../output.json`
- First no-effect refinement: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/18c46b67.../output.json`
- Second no-effect/stale refinement: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/c8853757.../output.json`

Failure/success points:

- Proposal: first two hypotheses could not pass branch lesson linkage checks.
- Code/edit: accepted prune candidates completed.
- Verification: no heavy verification failure.
- Protocol: initial marginal signal did not survive repeated no-effect checks and stale rescreen.
- Transfer: prior lessons were exposed, but early proposal blocks show the agent did not cleanly link those lessons to the new target/action/mechanism. Later same-branch prune refinement used the branch direction semantically but failed to create objective effect.
- Measurement: the initial 3W/0L/7T result had a CI spanning negative to positive. Later all-tie screens make the initial result likely weak/noise-sensitive.

### Branch `98676170-43e4-4030-827c-4f334429aa55`

Lineage and terminal state:

- Base champion: 1.
- Terminal state: `promoted`.
- Branch code status: `clean`.
- Classification: clean fork from previous failed/weak branches, with effective semantic use of prior lessons. This is the only branch whose branch lessons appear to have been used in a way that survived proposal, code, screening, validation, and frozen.

Evolution:

| Round | Hypothesis / step | Target | Mechanism | Protocol / decision | Evidence |
| ---: | --- | --- | --- | --- | --- |
| 18 | `7aa8657e-...` | `operators/merge_vehicles.py` | `compatible_pair_cost_guard` | code_generation failed, then expand_screening | first code attempt `old_string_not_found`; recovered candidate screening 3W / 0L / 3T / 6, median delta 950, CI [0, 9525] |
| 19 | same | `operators/merge_vehicles.py` | same | queue_validate | expanded screening 8W / 0L / 6T / 14, median delta 950, CI [400, 4500] |
| 20 | same | same | same | expand_validation | validation hierarchical uncertainty, median delta 0, CI [0, 1] |
| 21 | same | same | same | queue_frozen | validation exhausted marginal pass |
| 22 | same | same | same | promote | frozen 4W / 0L / 0T, median delta 50400, CI [46200, 58000] |

Context and outputs:

- Hypothesis session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/350ea5c9.../output.json`
- Failed code session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/9f46dd73-e6c9-4093-8d28-f32190f09e80/output.json`
  - Failure ledger: attempt 1 `exact_replace_not_serializable` because the `exact_replace old_string does not match content after prior same-file edits`; attempt 2 `old_string_not_found in operators/merge_vehicles.py`.
  - Prompt manifest: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/9f46dd73-e6c9-4093-8d28-f32190f09e80/scratch/api_visible_prompt_manifest_0004_code.json`
  - The manifest included `previous_attempt_failed` and `agentic_resume_context`, so the retry did see repair context but still failed exact edit matching.
- Successful code session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/7ce4059c-6073-4c1a-b235-2f8fd11b4138/output.json`
  - Agent hypothesis text: replace random-compatible pair merge with a bounded compatible-pair cost guard.
  - Structured `branch_lesson_usage` included avoided lesson `lesson:ba91...`, contrasted lessons `lesson:86d6...` and `lesson:cec9...`, and rejected weak-positive lesson `lesson:f443...`.
  - Evidence used included public spec, tainted memory, screening detail, runtime feedback, champion code, branch state, schema/target/static contract preview, and smoke check.
- Successful code prompt manifest: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/7ce4059c-6073-4c1a-b235-2f8fd11b4138/scratch/api_visible_prompt_manifest_0002_code.json`
  - Sections included `research_surface_interface_specification`, `current_champion_research_code`, `previous_attempt_failed`, and `evidence_diagnosis_behind_this_hypothesis`.

Failure/success points:

- Proposal: the hypothesis passed the structured branch lesson requirements after earlier branches had generated contrast/reject lessons.
- Code/edit: first code attempt failed due stale `old_string`; second completed.
- Verification: no heavy verification failure after successful code.
- Protocol: screening expanded, validation remained marginal/uncertain, frozen confirmed strongly enough to promote.
- Transfer: this is the strongest evidence of semantic prior-branch influence. The agent did not merely receive lessons; the successful output named avoided/contrasted/rejected lessons with target/action/mechanism linkage, and the proposal changed mechanism to a cost-guarded compatible pair merge rather than repeating earlier unguarded merge/prune patterns.
- Measurement: screening and validation had cached-champion complications. The promotion is mainly credible because frozen had fresh/high runtime evidence and strong case-level deltas.

Noise notes:

- Expanded screening raw metrics at `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/metrics/5f8b19f2-...json` had `runtime_confidence=low_cached_champion` but `runtime_evidence_status=sufficient`.
- Validation raw metrics at `metrics/21802ef1-...json` had `runtime_confidence=low_cached_champion` and `runtime_evidence_status=insufficient`; decision was `queue_frozen`, not promote.
- Frozen raw metrics at `metrics/8c0e8c98-...json` had `runtime_confidence=high`, `runtime_evidence_status=sufficient`, 12/12 pair wins, and no runtime regression. This is the deterministic evidence that resolves earlier cached/noisy evidence.

### Branch `5f31e5dc-5d96-4a25-a37e-cda04b960e6b`

Lineage and terminal state:

- Base champion: 2.
- Terminal state: `parked_lineage`.
- Last feedback tier: `no_effect`.
- Last telemetry outcome: `active_slot_reclaimed_for_new_branch`.
- Classification: sibling-nearby / clean fork after promotion. It tried a demote/repack family and then same-mechanism refinement.

Evolution:

| Round | Hypothesis / step | Target | Mechanism | Protocol / decision | Evidence |
| ---: | --- | --- | --- | --- | --- |
| 24 | `370179e6-...` | `operators/swap_orders.py` | `guarded_cost_swap` | proposal blocked | linkage unrecognized |
| 25 | `815de496-...` | `operators/tail_empty_cheapest.py` | `tail_empty_cheapest` | proposal blocked | linkage unrecognized |
| 26 | `38f0f352-...` | `operators/hazard_demote_repack.py` | `hazard_demote_repack` | continue_explore | 0W / 0L / 10T; active pair wins but case fail; runtime evidence incomplete |
| 27 | failed hypothesis | create-new, no accepted target | n/a | proposal failed | C11: `vehicle_level` surface lacks expected telemetry |
| 28 | `49ace39a-...` | `operators/hazard_demote_repack.py` | hazard demote refinement | continue_explore, parked | 0W / 0L / 6T; `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` |

Context and outputs:

- Accepted create-new code: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/30308e5b.../output.json`
- C11 failed session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/cc8d8b0f.../output.json`
- Final refinement code: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/f5c2f8a3.../output.json`

Failure/success points:

- Proposal: two linkage-unrecognized blocks before an accepted hazard-demote proposal.
- Code/edit: accepted candidates completed.
- Protocol: both accepted candidates were no-effect at case level.
- Transfer: prompt/context artifacts exposed lessons, but the first two attempts failed machine linkage. The accepted hazard demote proposal was a new direction rather than a successful transfer of prior weak positives.
- Measurement: active pair wins did not translate into case-level wins. The branch was parked because repeated ties created replay pressure without objective evidence.

### Branch `943c0d2f-5ca7-41af-8f06-99e6dde40255`

Lineage and terminal state:

- Base champion: 2.
- Terminal state: `explore`.
- Last feedback tier: `active_no_effect`.
- Last telemetry outcome: `no_objective_effect`.
- Classification: clean fork into light-tail evacuation, followed by same-mechanism depth.

Evolution:

| Round | Hypothesis / step | Target | Mechanism | Protocol / decision | Evidence |
| ---: | --- | --- | --- | --- | --- |
| 29 | `9d8c0459-...` | `operators/split_vehicle.py` | `destructive_split_prune` | proposal blocked | semantic mismatch |
| 30 | `eaa3d907-...` | `operators/empty_tail_vehicle.py` | `empty_tail_vehicle` | proposal blocked | linkage unrecognized |
| 31 | `07feb645-...` | `operators/light_tail_evacuate.py` | `light_tail_evacuate` | continue_explore | 1W / 0L / 9T / 10, median delta 0, CI [0, 0] |
| 32 | `6cea2ea9-...` | `operators/light_tail_evacuate.py` | refinement | continue_explore | 0W / 0L / 6T; `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` |
| 33 | `89096453-...` | `operators/light_tail_evacuate.py` | refinement | continue_explore | 0W / 0L / 6T; `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` |

Context and outputs:

- Accepted code session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/e8da11ba.../output.json`
- Refinement sessions: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/8fb59f47.../output.json`, `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/4a05f384.../output.json`

Failure/success points:

- Proposal: initial clean-fork attempts failed linkage/semantic checks.
- Code/edit: accepted light-tail code completed.
- Protocol: weak/no-effect followed by repeated ties.
- Transfer: branch lesson context was visible in prompt manifests, but the first two blocked attempts show poor structured transfer. Later same-mechanism refinements were semantically aligned with the branch but did not improve objective evidence.
- Measurement: the only win occurred with zero median delta and CI [0, 0], making it a weak signal rather than a robust improvement.

### Branch `9c36a33a-0903-491f-999f-e6275fa5c12d`

Lineage and terminal state:

- Base champion: 2.
- Terminal state: `abandoned`.
- Last feedback tier: `active_weak_positive`.
- Last telemetry outcome: `pair_level_positive_signal`.
- Classification: sibling-nearby weak-positive transfer in the merge family.

Evolution:

| Round | Hypothesis / step | Target | Mechanism | Protocol / decision | Evidence |
| ---: | --- | --- | --- | --- | --- |
| 34 | `b7b0db88-...` | `operators/merge_vehicles.py` | `same_subcat_multibin` | continue_explore | 0W / 0L / 6T, median delta 0, CI [0, 50]; fresh runtime tie |
| 35 | same | `operators/merge_vehicles.py` | same | abandon | 0W / 0L / 6T, median delta 0, CI [0, 50]; soft abandon due runtime regression rate |

Context and outputs:

- Hypothesis session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/efad8e5f.../output.json`
- Code session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/758c9a5e.../output.json`
- Fresh runtime closure in branch evidence recorded `fresh_evidence_recorded`, `runtime_evidence_status=sufficient`, and `decision_features_excluded=true`, meaning it was diagnostic/report evidence rather than direct decision material.

Failure/success points:

- Proposal/code: passed.
- Verification: passed.
- Protocol: no case-level wins; runtime regression rate caused abandonment.
- Transfer: the branch stayed in the merge family and likely drew from prior merge evidence, but it did not preserve the successful `compatible_pair_cost_guard` effect. This is sibling-nearby transfer that failed to reproduce the promoted mechanism's benefit.
- Measurement: the CI upper bound of 50 with zero median delta is too small to justify continued exploration once runtime regression pressure appears.

### Branch `579465a8-5425-46fd-a076-7c4cda5de296`

Lineage and terminal state:

- Base champion: 2.
- Terminal state: `explore`.
- Last feedback tier: `active_weak_positive`.
- Last telemetry outcome: `pair_level_positive_signal`.
- Classification: weak-positive transfer plus same-mechanism depth around `cost_safe_evacuate`.

Evolution:

| Round | Hypothesis / step | Target | Mechanism | Protocol / decision | Evidence |
| ---: | --- | --- | --- | --- | --- |
| 36 | `a16fae12-...` | `operators/move_order.py` | `cost_safe_evacuate` | continue_explore | 1W / 0L / 5T / 6, median delta 0, CI [0, 200] |
| 37 | `5b807e51-...` | `operators/move_order.py` | `cost_safe_evacuate` | proposal blocked | semantic mismatch |
| 38 | `ae188026-...` | `operators/move_order.py` | `cost_safe_evacuate` | continue_explore | 0W / 0L / 6T, median delta 0, CI [0, 150] |
| 39 | failed hypothesis | create-new, no accepted target | n/a | proposal failed | C11: `order_level` surface lacks expected telemetry |
| 40 | `cd25a9bd-...` | `operators/move_order.py` | `cost_safe_evacuate` | continue_explore | 0W / 0L / 6T, median delta 0, CI [0, 50]; replay materialization missing |
| 41 | `06bb1071-...` | `operators/move_order.py` | tradeoff variant | proposal blocked | semantic mismatch; missing mechanism linkage |

Context and outputs:

- Initial accepted sessions: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/40d742.../output.json`, `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/b99195.../output.json`
- No-effect refinement: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/30f33.../output.json`
- C11 failure: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/7030.../output.json`
  - The failed session observed memory/query output, 8 of 16 screening feedback rows, runtime feedback, and truncated code preview, then failed schema/target preview with two retry feedback artifacts under the session scratch directory.
- Later code session: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/b78ef54.../output.json`

Failure/success points:

- Proposal: two semantic mismatch blocks plus one C11 schema failure.
- Code/edit: accepted move-order candidates completed.
- Protocol: repeated no-effect/tie outcomes after an initial weak positive.
- Replay/materialization: branch evidence recorded `fresh_runtime_non_replayable` because the formal candidate patch ref existed at `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/artifacts/formal_candidates/579465a8/screening-cd25a9bd-5acd-49a2-817e-73efe91a5521-d40fddba5bcbff71/candidate.patch.json`, but replay materialization was unavailable.
- Transfer: the branch saw saturated cross-branch no-effect lessons and attempted to stay in a weak-positive move-order direction. The lesson content appears semantically present in some successful sessions, but blocked steps show fragile linkage and the resulting code did not escape no-effect behavior.
- Measurement: upper CI shrank from 200 to 150 to 50 while median delta stayed zero. The direction was probably noise-dominated or exhausted.

### Branch `bd88a729-c6ab-4c0f-955e-60911a66cef9`

Lineage and terminal state:

- Base champion: 2.
- Terminal state: `abandoned`.
- Last feedback tier: `quality_regression`.
- Last telemetry outcome: `loss_signal`.
- Classification: clean fork / nearby repack after several no-effect branches.

Evolution:

| Round | Hypothesis / step | Target | Mechanism | Protocol / decision | Evidence |
| ---: | --- | --- | --- | --- | --- |
| 42 | `3e1310e6-...` | `operators/move_order.py` | `same_subcat_tail_fill` | proposal blocked | semantic mismatch |
| 43 | `fac6066e-...` | `operators/destroy_rebuild.py` | `compatible_cost_repack` | abandon | screening 0W / 1L / 5T / 6, median delta 0, CI [-200, 0] |

Context and outputs:

- Accepted destroy/rebuild sessions: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/c865de85.../output.json`, `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/7e3dda15.../output.json`

Failure/success points:

- Proposal: first target failed semantic linkage.
- Code/edit: accepted destroy/rebuild candidate completed.
- Protocol: deterministic screening produced one loss and no wins, so branch was abandoned.
- Transfer: this was more a clean fork than useful transfer; it did not preserve the successful merge cost-guard mechanism or the weak-positive move-order branches.
- Measurement: CI was non-positive and included a loss, so abandonment is well supported.

### Branch `268be87d-e742-4b14-8500-849c7649bfee`

Lineage and terminal state:

- Base champion: 2.
- Terminal state: `explore`.
- Last feedback tier: `active_marginal`.
- Last telemetry outcome: `case_level_positive_signal`.
- Classification: same-mechanism marginal depth around `cost_balanced_swap`.

Evolution:

| Round | Hypothesis / step | Target | Mechanism | Protocol / decision | Evidence |
| ---: | --- | --- | --- | --- | --- |
| 44 | `c43c92a3-...` | `operators/swap_orders.py` | `cost_balanced_swap` | continue_explore | screening 1W / 0L / 5T / 6, median delta 0, CI [-50, 150] |
| 45 | `bbcfe1c4-...` | `operators/swap_orders.py` | `cost_balanced_swap` | continue_explore | screening 1W / 0L / 5T / 6, median delta 0, CI [-50, 150] |

Context and outputs:

- Initial sessions: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/0a55cf5a.../output.json`, `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/f321967a.../output.json`
- Same-mechanism refinement sessions: `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/45d1db6b.../output.json`, `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/d66831dc.../output.json`
  - These outputs used order-level surface context, memory, screening feedback, runtime feedback, and branch state. The second code output preserved same-branch lesson usage, so this is one of the better semantic same-branch refinements.

Failure/success points:

- Proposal/code: both accepted.
- Verification: passed.
- Protocol: marginal repeated signal, not promotion-grade.
- Transfer: stronger than most non-promoted branches at the semantic level because it preserved same-branch lesson usage, but the measured effect stayed marginal.
- Measurement: both rows repeated exactly 1W/0L/5T with CI crossing negative. The unresolved campaign closure says fresh runtime replay pressure found no schedulable replay candidate, so the branch remained active/marginal rather than resolved.

## Context And Output Audit

The branch sessions used a common context stack:

- `context.list_surfaces`
- `context.read_problem`
- `memory.query`
- `feedback.query_screening`
- `feedback.query_runtime`
- `context.read_surface`
- `context.read_branch_state`
- `proposal.schema_preview`
- `proposal.target_permission_preview`
- static contract preview and smoke checks in code phase

The postrun proposal trajectory manifest at `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/postrun_acceptance/manifests/rep01_on_compact.proposal_trajectory_manifest.v1.json` reports:

- `session_count=60`
- `trace_count=130`
- `prompt_manifest_loaded_count=130`
- `formal_candidate_count=21`
- `usage_present_count=60`
- `semantic_projection_present_count=60`
- `unrecognized_usage_present_count=0`
- `branch_lesson_context_truncated_trace_count=44`

This means branch lesson material was nearly always visible in agent contexts, but often compact/truncated and not always structurally usable. The distinction is important:

- Successful transfer example: branch `98676170...`, session `7ce4059c...`, where `branch_lesson_usage` contained concrete avoided/contrasted/rejected lesson records and the candidate promoted.
- Failed transfer example: branch `6a7632b1...` rounds 7-10, where the same branch lesson direction was available but proposal quality blocked repeated same-target refinements.
- Schema pressure example: branch `579465a8...`, session `7030...`, where the agent had memory, screening, runtime, and branch context but still requested undeclared `order_level` telemetry and failed C11.
- Edit pressure example: branch `98676170...`, session `9f46dd73...`, where the code retry saw `previous_attempt_failed` and resume context but failed `old_string_not_found`.

Prompt manifests are therefore useful to explain what the agent saw, but under the v3 boundary they do not become decision evidence.

Exact session evidence paths for main-thread verification:

| Branch | Session role | Exact artifact path |
| --- | --- | --- |
| `ccf8f4f4-74dd-41b2-92de-0c8cff533a11` | first hypothesis | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/a9f5aa46-a239-4f13-a23a-a62839c565cf/output.json` |
| `ccf8f4f4-74dd-41b2-92de-0c8cff533a11` | first code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/20c3663c-8185-4bca-89a7-7ebf01f7a925/output.json` |
| `ccf8f4f4-74dd-41b2-92de-0c8cff533a11` | screened merge code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/35f2a69a-8f14-4c35-9947-3a3e653f898d/output.json` |
| `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74` | tail-fill hypothesis | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/497b6752-b012-40bf-99a8-8fb5567fb232/output.json` |
| `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74` | tail-fill code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/3d2ff034-3389-4b7d-8066-7093d102bdd4/output.json` |
| `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74` | C11 failure | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/e5aba35d-92f7-48a0-ac17-fb973189beeb/output.json` |
| `6a7632b1-e84a-4f5a-a3ba-ec02ffc14f74` | final no-effect code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/96dd5c7e-e8dc-4dbf-b3ff-7269f09daebd/output.json` |
| `b31289b9-f4dd-481d-9662-6cb2e61d9890` | prune code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/e47b9e57-4f1a-42a9-a7b3-148ef0a00025/output.json` |
| `b31289b9-f4dd-481d-9662-6cb2e61d9890` | no-effect refinement | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/18c46b67-2415-4875-b10c-befbc1a44295/output.json` |
| `b31289b9-f4dd-481d-9662-6cb2e61d9890` | stale refinement | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/c8853757-c08b-4e1f-8784-3554bb694bb7/output.json` |
| `98676170-43e4-4030-827c-4f334429aa55` | hypothesis | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/350ea5c9-997e-4cd1-a6f3-ce2ad6693e90/output.json` |
| `98676170-43e4-4030-827c-4f334429aa55` | failed code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/9f46dd73-e6c9-4093-8d28-f32190f09e80/output.json` |
| `98676170-43e4-4030-827c-4f334429aa55` | failed code prompt manifest | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/9f46dd73-e6c9-4093-8d28-f32190f09e80/scratch/api_visible_prompt_manifest_0004_code.json` |
| `98676170-43e4-4030-827c-4f334429aa55` | successful code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/7ce4059c-6073-4c1a-b235-2f8fd11b4138/output.json` |
| `98676170-43e4-4030-827c-4f334429aa55` | successful code prompt manifest | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/7ce4059c-6073-4c1a-b235-2f8fd11b4138/scratch/api_visible_prompt_manifest_0002_code.json` |
| `5f31e5dc-5d96-4a25-a37e-cda04b960e6b` | hazard-demote code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/30308e5b-6def-4548-9b4e-58c23340e2a5/output.json` |
| `5f31e5dc-5d96-4a25-a37e-cda04b960e6b` | C11 failure | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/cc8d8b0f-0e7b-4a63-8e1f-86977522def0/output.json` |
| `5f31e5dc-5d96-4a25-a37e-cda04b960e6b` | final refinement | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/f5c2f8a3-571c-44f7-9463-c8c4c1065b8e/output.json` |
| `943c0d2f-5ca7-41af-8f06-99e6dde40255` | light-tail code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/e8da11ba-07fb-4f11-9a17-62fe0399e63e/output.json` |
| `943c0d2f-5ca7-41af-8f06-99e6dde40255` | refinement | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/8fb59f47-00c4-4c43-9e24-3845479cdeb9/output.json` |
| `943c0d2f-5ca7-41af-8f06-99e6dde40255` | refinement | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/4a05f384-77d5-4b26-8cb3-63926b5b3ef5/output.json` |
| `9c36a33a-0903-491f-999f-e6275fa5c12d` | hypothesis | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/efad8e5f-ebf4-4c10-b896-cdb496f8d84e/output.json` |
| `9c36a33a-0903-491f-999f-e6275fa5c12d` | code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/758c9a5e-7319-47b3-bc54-78033d9efbda/output.json` |
| `579465a8-5425-46fd-a076-7c4cda5de296` | initial hypothesis | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/40d742c0-ffee-437c-a24c-0ab7b2fdc6ea/output.json` |
| `579465a8-5425-46fd-a076-7c4cda5de296` | initial code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/b99195b5-1bb0-4e77-bc4b-d2b826ffd948/output.json` |
| `579465a8-5425-46fd-a076-7c4cda5de296` | no-effect refinement | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/30f33b50-4f18-4e87-b204-0f476195ac2b/output.json` |
| `579465a8-5425-46fd-a076-7c4cda5de296` | C11 failure | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/7030be39-eafe-489a-9f50-c8531c27bc33/output.json` |
| `579465a8-5425-46fd-a076-7c4cda5de296` | later code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/b78ef54f-8512-40fb-9f97-d7f8de3622ee/output.json` |
| `bd88a729-c6ab-4c0f-955e-60911a66cef9` | accepted destroy/rebuild | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/c865de85-d53c-48a4-9476-85fbec818f76/output.json` |
| `bd88a729-c6ab-4c0f-955e-60911a66cef9` | accepted destroy/rebuild | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/7e3dda15-a356-4d95-a326-0c2109d765d6/output.json` |
| `268be87d-e742-4b14-8500-849c7649bfee` | initial hypothesis | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/0a55cf5a-e3e5-410c-a046-f465565b17f2/output.json` |
| `268be87d-e742-4b14-8500-849c7649bfee` | initial code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/f321967a-90d7-4ee9-bbaa-aa0f800bc5c6/output.json` |
| `268be87d-e742-4b14-8500-849c7649bfee` | refinement hypothesis | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/45d1db6b-ede0-4497-9e67-274c9c26b604/output.json` |
| `268be87d-e742-4b14-8500-849c7649bfee` | refinement code | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/d66831dc-22fe-4a7e-a1b4-1841968e57e9/output.json` |

Exact metric and replay paths for main-thread verification:

| Evidence | Exact artifact path |
| --- | --- |
| ccf final screening loss | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/metrics/de0c35ff-5e7f-4484-b2d8-811d6ffad78d.json` |
| 6a tail-fill weak positive | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/metrics/2165b345-3442-48f7-9de4-a4e154cd9ab2.json` |
| 6a tail-fill no-effect | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/metrics/78533d4c-07b5-4bf2-9ae7-0d061bfc5800.json` |
| b312 prune marginal | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/metrics/b4e3082f-9674-41e1-8518-3deaa4113d20.json` |
| b312 prune no-effect | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/metrics/bcc38d15-b402-44e4-97c8-6e86e6e0d18d.json` |
| b312 stale rescreen | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/metrics/eaac6b7f-63e9-4df0-93be-e5db2a4efa95.json` |
| 986 first screening | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/metrics/7ca212fa-81bb-4e11-8f74-90c4fac1d90b.json` |
| 986 expanded screening | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/metrics/5f8b19f2-b138-4292-b72d-68fc4087284f.json` |
| 986 validation 1 | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/metrics/ce5f7c74-96f6-45cc-b125-646e7d4fee2a.json` |
| 986 validation 2 | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/metrics/21802ef1-fad7-44ff-8edf-75de9b128e1f.json` |
| 986 frozen | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/metrics/8c0e8c98-3562-4388-a23f-eeb99a9c9dd7.json` |
| 579 replay patch ref | `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/artifacts/formal_candidates/579465a8/screening-cd25a9bd-5acd-49a2-817e-73efe91a5521-d40fddba5bcbff71/candidate.patch.json` |

## Information Transfer Between Branches

Evidence of effective semantic transfer:

- Branch `98676170...` used prior branch lessons semantically:
  - Avoided `lesson:ba91...` from the failed `consolidate_subcategory.py` direction.
  - Contrasted `lesson:86d6...` and `lesson:cec9...` from prior compatible-cost/no-effect merge evidence.
  - Rejected weak-positive `lesson:f443...` from the prune-redundant family as `not_prune_redundant_family`.
  - Produced a different mechanism, `compatible_pair_cost_guard`, that constrained merge selection rather than repeating random merge, broad prune, or unrelated evacuation.

Evidence of lesson presence without effective transfer:

- `6a7632b1...` had a real weak-positive tail-fill checkpoint, but four rounds of same-target refinement failed before code because structured branch lesson linkage was wrong or incomplete.
- `b31289b9...` had prior lessons available but early prune/empty-vehicle proposals failed semantic/linkage checks, and accepted prune refinements became no-effect.
- `5f31e5dc...` and `943c0d2f...` show the same pattern: branch lesson context was present, yet clean fork/sibling-nearby proposals frequently used unrecognized linkage fields.
- `579465a8...` shows partial transfer: the branch stayed in a weak-positive move-order direction, but proposal blocks and shrinking zero-median evidence suggest the branch did not convert historical lessons into a new effective mechanism.
- `268be87d...` is a better same-branch transfer case than most non-promoted branches: the second swap refinement preserved same-branch lesson usage, but the measured signal remained marginal and unresolved.

Net: rep01 had broad lesson exposure and one successful semantic transfer, but most branches suffered a gap between natural-language lesson awareness and machine-checkable `branch_lesson_usage` linkage.

## Noise And Measurement

Screening vs validation/frozen:

- Screening was noisy and tie-heavy: 22 wins, 3 losses, 131 ties across screening rows.
- Most non-promoted branches showed weak positives with median delta 0 or small positive CI upper bounds, then repeated exact ties.
- The promoted branch did not promote directly from noisy screening. It required expanded screening, validation, and frozen.

Cached champion/runtime confidence:

- Promoted branch screening and validation included cached-champion complications.
- Promotion dossier stage chain:
  - Screening pass: `metrics/5f8b19f2-...json`, 8W / 0L / 6T, median delta 950, CI [400, 4500], `runtime_confidence=low_cached_champion`, `runtime_evidence_status=sufficient`.
  - Validation: `metrics/21802ef1-...json`, 5W / 0L / 0T at case aggregation but median delta 0, CI [0, 1], `runtime_confidence=low_cached_champion`, `runtime_evidence_status=insufficient`.
  - Frozen: `metrics/8c0e8c98-...json`, 4W / 0L / 0T, median delta 50400, CI [46200, 58000], `runtime_confidence=high`, `runtime_evidence_status=sufficient`.

Fresh replay behavior:

- Fresh runtime replay attempts: 1.
- Executed fresh replays: 0.
- Drain status: `pressure_no_schedulable_replay_candidate`.
- Unresolved branch: `268be87d-e742-4b14-8500-849c7649bfee`.
- Non-replayable branch: `579465a8-5425-46fd-a076-7c4cda5de296`, blocked because replay materialization was unavailable despite a formal candidate patch ref.

Likely noise-dominated candidates:

- `6a7632b1...` round 6: weak positive 4W/0L/6T with CI touching zero, followed by exact 0W/0L/6T.
- `b31289b9...` round 15: 3W/0L/7T but CI [-400, 2275], followed by repeated ties and stale rescreen abandon.
- `943c0d2f...` round 31: 1W/0L/9T with median and CI both zero.
- `579465a8...` rounds 36/38/40: CI upper bounds shrank while median stayed zero.
- `268be87d...` rounds 44/45: repeated 1W/0L/5T with CI crossing negative.

The promoted branch is less likely to be noise-dominated because frozen used high-confidence runtime evidence and a large positive CI. Validation remained weak, so the frozen gate is the decisive evidence.

## Failure/Quality Taxonomy

Proposal quality blocks:

- Count: 21 from acceptance manifest/research efficiency artifacts.
- Main reasons:
  - `branch_lesson_usage_semantic_mismatch`
  - `branch_lesson_usage_linkage_unrecognized`
  - `C11_expected_telemetry`
- Most affected branches: `6a7632b1...`, `579465a8...`, `5f31e5dc...`, `943c0d2f...`, plus early `ccf8f4f4...` and `b31289b9...`.
- Concrete repeated snippet from campaign steps: structured `branch_lesson_usage` was required from `branch.branch_evidence_summary`; the rejected proposal had to regenerate compact lesson ids and generic dimensions, and clean fork/sibling-nearby/weak-positive transfer required target/action/mechanism linkage.

Branch lesson semantic mismatch/linkage failures:

- Root cause: the agent often saw branch lessons but did not express them in fields the deterministic quality gate could recognize.
- Impact: consumed proposal attempts before code, especially in same-mechanism depth branches where the run should have been refining instead of repeatedly failing proposal shape.

C11 expected telemetry:

- `6a7632b1...` round 11: `order_level` requested undeclared telemetry.
- `5f31e5dc...` round 27: `vehicle_level` requested undeclared telemetry.
- `579465a8...` round 39: `order_level` requested undeclared telemetry.
- These are proposal/schema failures, not protocol evidence. They indicate the agent over-specified telemetry requirements beyond the declared research surface.

Old-string/code edit failure:

- Branch `98676170...`, round 18, session `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/rep01/on_compact/campaign/agentic_sessions/9f46dd73-e6c9-4093-8d28-f32190f09e80/output.json`
- Failure ledger:
  - `exact_replace_not_serializable`
  - `old_string_not_found in operators/merge_vehicles.py`
- The next code session recovered, so this was a local edit robustness failure, not a research-direction failure.

Verification-heavy failure:

- Branch `ccf8f4f4...`, round 1.
- Candidate `operators/consolidate_subcategory.py` passed agent/static previews but failed deterministic verification with `V5_solution_consistency`.
- Error: `AttributeError: 'Solution' object has no attribute 'instance'` at line 171.
- This shows why v3 cannot let prompt/static preview success substitute for verification.

No-effect loops:

- Branches `6a7632b1...`, `b31289b9...`, `5f31e5dc...`, `943c0d2f...`, `579465a8...`, and `268be87d...` all produced one weak/marginal result followed by ties or repeated marginal evidence.
- No-effect loops were often accompanied by fresh-runtime replay pressure.

Tool timeouts:

- Research efficiency artifact records two tool-timeout events from campaign run log lines 7 and 8.
- These do not define a branch terminal state, but they contribute to agentic session fragility and proposal/code loop latency.

Fresh-runtime replay pressure:

- `fresh_runtime_replay_attempts=1`, `executed=0`, `blocked=1`.
- Branch `268be87d...` remained unresolved because no schedulable replay candidate was available.
- Branch `579465a8...` had candidate evidence but lacked replay materialization.

## Interpretation

Rep01 achieved one real promotion, but it does not show a continuous promotion process.

Compared cautiously with the v0.3 reference:

- v0.3 production Sonnet reportedly promoted 3/3 after fixes.
- The strongest synthetic reference reportedly had 4 continuous promotions.
- Rep01 has exactly one promotion, from branch `98676170...`, and most later branches either parked, abandoned, or remained marginal/no-effect.

Therefore rep01 shows isolated continuity in the sense that prior branch lessons helped produce one successful clean fork, but it does not show sustained branch-to-branch improvement. The run's main bottleneck is not only aggregate candidate weakness; it is branch-level transfer quality. Lessons were present in contexts, but only one branch converted them into a machine-valid, semantically useful proposal and then into frozen-confirmed improvement.

## Concrete Repair Hypotheses

1. Make `branch_lesson_usage` repair deterministic before invoking code generation.
   - Add a pre-code normalizer/checker that maps lesson ids, target_file, action, mechanism, changed dimensions, and reject reason into the accepted schema.
   - Acceptance: proposal-quality-loop branches like `6a7632b1...` should not spend four consecutive same-target attempts on linkage shape errors.

2. Separate lesson visibility from lesson usability in reports and gates.
   - Current manifest says usage was present in all 60 sessions, but quality blocks prove present context was often not semantically usable.
   - Acceptance: postrun should count `semantic_linkage_valid`, not only `semantic_projection_present`.

3. Harden C11 expected telemetry repair.
   - When a surface does not declare telemetry fields, force `{}` or declared-only telemetry before retry.
   - Acceptance: failures like `order_level`/`vehicle_level` undeclared telemetry should terminate in one repair retry, not consume later branch depth.

4. Replace fragile exact-string edit flows for repeated same-file code retries.
   - Branch `98676170...` recovered after `old_string_not_found`, but only after consuming a failed code attempt.
   - Acceptance: if prior same-file edits occurred, the code phase should switch to an AST-aware or full-file checked patch path with deterministic diff validation.

5. Materialize fresh replay candidates at formal-candidate creation time.
   - Branch `579465a8...` had a formal candidate patch ref but no replay materialization; branch `268be87d...` had replay pressure but no schedulable candidate.
   - Acceptance: every candidate that triggers `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` should either have a replayable patch artifact or a deterministic non-replayable reason before the branch consumes more rounds.

6. Add no-effect saturation limits by mechanism family.
   - Same-mechanism branches repeatedly produced exact ties after weak positives.
   - Acceptance: after N no-effect screens with median delta 0 and CI touching/crossing zero, require a mechanism change or park the branch without more same-family proposal attempts.

7. Treat cached-champion validation as non-final by policy.
   - Rep01 did the right thing by relying on frozen for promotion; the report should preserve that distinction.
   - Acceptance: validation rows with `runtime_confidence=low_cached_champion` and `runtime_evidence_status=insufficient` can queue frozen but cannot be summarized as robust validation success.

8. Add branch-level replay summaries to postrun acceptance.
   - The required diagnosis had to join `campaign_summary.json`, `scion.db`, session outputs, prompt manifests, metrics, and postrun summaries manually.
   - Acceptance: postrun should emit one branch dossier per branch with lineage, hypothesis ids, sessions, gates, terminal state, lesson linkage verdicts, and replay status.
