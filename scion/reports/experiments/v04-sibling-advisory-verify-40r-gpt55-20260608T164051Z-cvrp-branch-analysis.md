# Scion v0.4 40R CVRP Branch Analysis

Experiment root: `/home/clawd/research/scion-experiments/v04-sibling-advisory-verify-40r-gpt55-40r-gpt55-20260608T164051Z-claw/campaign`

Report target: `/home/clawd/research/or-autoresearch-agent/scion/reports/experiments/v04-sibling-advisory-verify-40r-gpt55-20260608T164051Z-cvrp-branch-analysis.md`

Architecture guardrails used for this analysis: Scion architecture v3 treats all LLM output as tainted proposal visibility; Contract, Verification, Protocol, and Safe Feature extraction are the route into deterministic Decision; Decision must read only `DecisionFeatures`, not LLM free text; cross-branch lessons may guide later proposal context but must not directly promote or abandon branches.

## 1. Run Status And Accounting

The run is complete and valid as a 40 effective-round campaign.

- `run_status.json`: wrapper status `finished`, wrapper exit `0`, campaign exit `complete`, `run_complete=true`, `run_validity_status=valid`, started `2026-06-08T16:40:52Z`, ended `2026-06-08T21:36:24Z`.
- `status.json`: `requested_rounds=40`, `effective_rounds_completed=40`, `completed_requested_rounds=true`, `stopped_reason=max_rounds_exhausted`, `max_rounds_budget_counter=effective_rounds_completed`.
- The campaign has `n_steps=53` and `n_experiments=44`, so "40R" is not equal to every campaign step. The reconciliation explains the difference: 40 effective screening attempts, 9 non-counted proposal quality blocks, and 4 non-counted fresh-runtime replay protocol rows.
- `protocol_stage_counts`: screening 44, validation 0, frozen 0. No candidate reached validation or frozen holdout.
- Champion did not change: `champion_version=1`, `champion_weight_revision=0`, frozen budget used 0 of 2.
- Verification was stable: `verification_consumed_candidates=40`, `verification_failure_consumed_candidates=0`. All counted candidates reached/passed verification before screening; pre-protocol failures were proposal/code quality blocks.
- Run integrity is clean: `evidence_integrity.status=complete`, `lineage_integrity.status=complete`, `recorded_outcome_count=44`, no evidence warnings.
- `run.log` is short and consistent with the structured artifacts: one tool timeout retry, one hypothesis target-intent binding mismatch, two rejected code-generation attempts for state/delta helper integration, then `Campaign finished`.

LLM/model accounting:

- Every LLM trace used `gpt-5.5`: 340 trace files total.
- Request-kind counts: 48 `hypothesis_target_intent`, 66 `hypothesis`, 175 `tool_selection`, 51 `code`.
- Trace usage sums: 9,069,203 input tokens and 229,093 output tokens. `total_tokens`, cached-token, and reasoning-token fields are not populated in these trace records, so accounting clarity is partial at token-subfield level.
- DB protocol rows also mark the 44 formal screening rows with `model_id=gpt-5.5`; agentic proposal-session DB rows do not carry model IDs, so the LLM trace files are the source of truth for full model usage.

## 2. Round And Step Ledger

The campaign executed 53 steps. Rows marked `effective=true` are counted toward the 40-round budget. Rows marked `effective=false` are proposal blocks or fresh-runtime replays.

| Step | Branch | Kind | Effective | Slot | Decision | Gate/tier | Target | Practical intent |
|---:|---|---|---:|---|---|---|---|---|
| 1 | b2a15767 | screening | true | explore_new | abandon | fail / quality_regression | destroy_repair.py | Route-limit-aware insertion repair to reduce max-route rejected ALNS repairs. |
| 2 | 5bcde00c | screening | true | explore_new | abandon | fail / quality_regression | scheduler.py | Budget-aware embedded VNS gating under runtime saturation. |
| 3 | 735a1d22 | screening | true | explore_new | continue_explore | unclear / quality_regression | local_search.py | Add bounded three-route exchange VNS. |
| 4 | f11d505c | screening | true | explore_new | continue_explore | fail / marginal | route_compaction.py | Add sparse route compaction helper wired into scheduler. |
| 5 | f11d505c | proposal_block | false | refine_active | none | branch_lesson_usage mismatch | route_compaction.py | Follow-up compaction proposal blocked before code for insufficient structured lesson linkage. |
| 6 | f11d505c | screening | true | repair_diagnostic | abandon | fail / quality_regression | route_compaction.py | Payoff-gated micro-compaction refinement. |
| 7 | 5904813b | proposal_block | false | explore_new | none | branch_lesson_usage mismatch | destroy_repair.py | Slack-biased regret repair blocked before code. |
| 8 | 5904813b | screening | true | repair_diagnostic | continue_explore | unclear / quality_regression | construction.py | Route-limit seed diversification. |
| 9 | 5904813b | screening | true | repair_diagnostic | abandon | fail / quality_regression | construction.py | Seed-diversification repair with activation/effect accounting. |
| 10 | c681f423 | proposal_block | false | explore_new | none | branch_lesson_usage mismatch | acceptance.py | Rank-temperature acceptance blocked before code. |
| 11 | c681f423 | screening | true | repair_diagnostic | abandon | fail / quality_regression | acceptance.py | Rank-temperature acceptance follow-up. |
| 12 | 56224f40 | proposal_block | false | explore_new | none | branch_lesson_usage mismatch | local_search.py | Bounded two-route segment relink blocked before code. |
| 13 | 56224f40 | screening | true | repair_diagnostic | abandon | fail / quality_regression | local_search.py | Bounded two-route segment relink implementation. |
| 14 | ec461d86 | screening | true | explore_new | abandon | fail / invalid | destroy_repair.py | Biased exchange repair; got candidate runtime failure. |
| 15 | 61193272 | proposal_block | false | explore_new | none | branch_lesson_usage mismatch | scheduler.py | Scheduler telemetry bridge blocked before code. |
| 16 | 61193272 | screening | true | repair_diagnostic | continue_explore | unclear / no_effect | construction.py | Seed-pool selector. |
| 17 | 61193272 | screening | true | repair_diagnostic | continue_explore | unclear / quality_regression | construction.py | Seed-pool selector observability repair. |
| 18 | 61193272 | screening | true | repair_diagnostic | continue_explore | unclear / quality_regression | construction.py | Incumbent-preserving seed-pool selector. |
| 19 | 61193272 | screening | true | repair_diagnostic | continue_explore | unclear / no_effect | construction.py | Strict diagnostic seed-pool selector. |
| 20 | 5072010d | screening | true | explore_new | continue_explore | unclear / no_effect | local_search.py | Empty-route absorption VNS. |
| 21 | b1b170f6 | screening | true | explore_new | continue_explore | unclear / no_effect | scheduler.py | Operator-credit observability. |
| 22 | 50adbefc | screening | true | explore_new | continue_explore | unclear / no_effect | scheduler.py | Phase budget gate. |
| 23 | 6300182d | screening | true | explore_new | continue_explore | unclear / weak_positive | local_search.py | Lambda-interchange VNS. |
| 24 | 6300182d | fresh_runtime_replay | false | exploit_weak_positive | continue_explore | fail / weak_positive | local_search.py | Fresh replay of lambda-interchange; no case-level win. |
| 25 | f05a97b7 | screening | true | explore_new | continue_explore | unclear / no_effect | route_pool.py | Elite route-pool recombination. |
| 26 | fc855efe | screening | true | explore_new | abandon | fail / quality_regression | destroy_repair.py | Split-delivery-aware repair. |
| 27 | db3c1722 | screening | true | explore_new | continue_explore | unclear / quality_regression | acceptance.py | Stagnation reheat acceptance. |
| 28 | 9f4a1b5c | screening | true | explore_new | abandon | fail / quality_regression | local_search.py | Route 2-opt bridge VNS. |
| 29 | 091a9851 | screening | true | explore_new | abandon | fail / quality_regression | destroy_repair.py | Slack-biased regret repair. |
| 30 | 41f41ced | screening | true | explore_new | continue_explore | unclear / no_effect | construction.py | Route-limit seed portfolio. |
| 31 | 8e053dfe | screening | true | explore_new | abandon | fail / quality_regression | local_search.py | Inter-route 2-swap VNS. |
| 32 | 72a7d01a | screening | true | explore_new | abandon | fail / quality_regression | scheduler.py | Route-count-aware repair selection. |
| 33 | 2908e9ea | screening | true | explore_new | continue_explore | unclear / no_effect | scheduler.py | Operator-effect telemetry bridge. |
| 34 | 00c45e18 | screening | true | explore_new | continue_explore | unclear / weak_positive | acceptance.py | Threshold record-to-record acceptance. |
| 35 | 00c45e18 | fresh_runtime_replay | false | exploit_weak_positive | continue_explore | fail / weak_positive | acceptance.py | Fresh replay of threshold acceptance; active pair wins but case gate failed. |
| 36 | 00c45e18 | proposal_block | false | exploit_weak_positive | none | branch_lesson_usage mismatch | acceptance.py | Threshold acceptance repair blocked before code. |
| 37 | 00c45e18 | screening | true | repair_diagnostic | continue_explore | unclear / weak_positive | acceptance.py | Plateau-conditional threshold refinement. |
| 38 | 00c45e18 | proposal_block | false | repair_diagnostic | none | target_intent_binding_mismatch | none | Formal hypothesis target/action/mechanism drifted from selected intent. |
| 39 | 00c45e18 | screening | true | repair_diagnostic | continue_explore | unclear / no_effect | acceptance.py | One-shot success-credited threshold probe. |
| 40 | 00c45e18 | screening | true | repair_diagnostic | continue_explore | unclear / no_effect | acceptance.py | Payoff-observable threshold diagnostic gate. |
| 41 | 903852e8 | screening | true | explore_new | continue_explore | unclear / weak_positive | destroy_repair.py | Load-entropy removal. |
| 42 | 903852e8 | fresh_runtime_replay | false | exploit_weak_positive | continue_explore | fail / weak_positive | destroy_repair.py | Fresh replay of load-entropy removal; no case-level win. |
| 43 | ad1bceff | screening | true | explore_new | continue_explore | unclear / weak_positive | destroy_repair.py | Capacity-slack regret repair. |
| 44 | ad1bceff | fresh_runtime_replay | false | exploit_weak_positive | continue_explore | fail / weak_positive | destroy_repair.py | Fresh replay of capacity-slack regret repair; no case-level win. |
| 45 | 0d384e4a | screening | true | explore_new | continue_explore | unclear / no_effect | construction.py | Route-fill merge construction. |
| 46 | f6fe503b | screening | true | explore_new | continue_explore | unclear / no_effect | local_search.py | Split-route reinsertion VNS. |
| 47 | d08c64a6 | screening | true | explore_new | abandon | fail / quality_regression | destroy_repair.py | Biased distance insertion repair. |
| 48a | 0620ed64 | proposal_block | false | explore_new | none | code_generation block | state.py | Cached route-delta state rejected for private dynamic state attributes. |
| 48b | 0620ed64 | proposal_block | false | repair_diagnostic | none | code_generation block | state.py | Retry rejected for inert helper integration failure. |
| 49 | 0620ed64 | screening | true | refine_active | continue_explore | unclear / no_effect | construction.py | Route-limit seed diversifier. |
| 50 | 5047e926 | screening | true | explore_new | abandon | fail / quality_regression | local_search.py | Cross-exchange VNS. |
| 51 | c4e2ed74 | screening | true | explore_new | continue_explore | unclear / no_effect | scheduler.py | Route-limit repair retry. |
| 52 | e78e94d2 | screening | true | explore_new | continue_explore | unclear / no_effect | scheduler.py | Operator evidence bridge. |

One recorded campaign "round" value is reused for the two 0620ed64 proposal blocks, so the table labels them `48a` and `48b`.

## 3. Branch Analysis

The run explored 32 branch rows. No branch produced validation-ready evidence. Most positive-looking signals were pair-level or runtime/telemetry observations, not case-level gate evidence.

| Branch | Final state | Mechanism | Path and code changes | Result and lifecycle judgment |
|---|---|---|---|---|
| b2a15767 | abandoned | route_limit_aware_repair | Modified destroy/repair and scheduler; added route-limit-aware insert and displacement logic. | Case 0/1/7, pair 1/3/12, median 0.0. Activated but no reliable final-objective effect. Abandon was reasonable. |
| 5bcde00c | abandoned | budget_aware_vns_gating | Scheduler-only VNS gating. | Case 0/2/6, pair 0/8/8, median -2.5. Clear regression; abandon was correct. |
| 735a1d22 | explore | three_exchange_vns | Local-search three-route cyclic exchange. | Case 0/0/8, pair 0/1/15. Runtime evidence required fresh champion. Keeping as unresolved was defensible, but it did not justify validation. |
| f11d505c | abandoned | route_compaction_repair | New route_compaction helper, then payoff-gated refinement. | Initial marginal case 1/1/10 in larger create-new screen; follow-up failed with case 0/0/8 and pair losses. Refinement made sense, abandonment after no translation was reasonable. |
| 5904813b | abandoned | route_limit_seed_diversification | Construction seed diversification after blocked repair-family proposal. | Both attempts tied at case level with pair losses; abandonment after repair diagnostic was reasonable. |
| c681f423 | abandoned | rank_temperature_acceptance | Acceptance schedule changes. | Case 0/0/8, pair 0/2/14. No positive signal; abandon was reasonable. |
| 56224f40 | abandoned | bounded_2route_segment_relink | Added bounded two-route segment relink to local search. | Case 0/1/7, pair 2/5/9. Pair positives did not offset case loss; abandon was reasonable. |
| ec461d86 | abandoned | biased_exchange_repair | Destroy/repair biased exchange. | Tier `invalid`, candidate runtime failure, case 1/1/6. Abandon was necessary. |
| 61193272 | explore | seed_pool_selector | Four construction selector variants, including observability/guard refinements. | All case-level ties; final no-effect with fresh champion required. Branch-internal follow-up was reasonable at first, but four near-identical selector refinements consumed too much budget without objective movement. |
| 5072010d | parked_lineage | empty_route_absorption_vns | Added local-search empty-route absorption. | Pure tie 0/0/8, pair 0/0/16. Parking to free active slot was reasonable. |
| b1b170f6 | parked_lineage | operator_credit_observability | Scheduler observability bridge. | Pure tie, observability candidate intent not promoted. Parking was reasonable. |
| 50adbefc | parked_lineage | phase_budget_gate | Scheduler phase budget gate. | Pure tie. Parking was reasonable; no validation signal. |
| 6300182d | parked_lineage | lambda_interchange_vns | Local-search lambda interchange plus fresh replay. | Initial weak positive only at pair level; replay also case 0/0/8. Parking after replay failure was correct. |
| f05a97b7 | parked_lineage | elite_route_pool_recombination | New route_pool plus scheduler integration. | Create-new 12-case screen tied 0/0/12. Parking was reasonable. |
| fc855efe | abandoned | split_delivery_aware_repair | Destroy/repair split-delivery-style displacement under CVRP constraints. | Case 1/0/7 but low/cached runtime, median 0.0 and non-positive CI; abandon reflects quality-regression classification. This branch shows pair/case ambiguity but not validation-quality evidence. |
| db3c1722 | explore | stagnation_reheat_acceptance | Acceptance reheat schedule. | Case tie, one pair loss, fresh champion required. Continuing as unresolved was defensible but weak. |
| 9f4a1b5c | abandoned | route_2opt_bridge | Local-search inter-route edge bridge. | Case 0/1/7, pair 2/3/11. Abandon was reasonable. |
| 091a9851 | abandoned | slack_biased_regret_repair | Repair insertion variants and scheduler wiring. | Case 0/1/7, pair 1/3/12. This repeated the earlier blocked/abandoned slack-regret family with better structure but no result. |
| 41f41ced | parked_lineage | route_limit_seed_portfolio | Construction seed portfolio and scheduler integration. | Pure tie. Parking was reasonable. |
| 8e053dfe | abandoned | inter_route_2swap | Local-search two-customer inter-route swap. | Case 0/1/7, pair 0/2/14. Abandon was reasonable. |
| 72a7d01a | abandoned | route_count_aware_repair_selection | Scheduler repair-selection probe. | Case 0/0/8 but pair 2/4/10 and median -0.25. Abandon was reasonable. |
| 2908e9ea | parked_lineage | operator_effect_telemetry_bridge | Scheduler effect telemetry bridge. | Pure tie. Parking was reasonable; observability was not decision evidence. |
| 00c45e18 | explore | threshold_record_to_record_acceptance | Acceptance threshold branch plus several refinements and replay. | Weak pair-positive first result, replay failed case gate, later refinements became no-effect. Branch-internal research was coherent, but the run over-refined after replay failure. |
| 903852e8 | parked_lineage | load_entropy_removal | Destroy/repair removal heuristic plus replay. | Pair-positive weak signal, replay failed case gate. Parking was correct. |
| ad1bceff | parked_lineage | capacity_slack_regret_repair | Destroy/repair capacity-slack regret plus replay. | Pair 1/1/14, replay failed case gate. Parking was correct. |
| 0d384e4a | parked_lineage | route_fill_merge_construction | Construction route-fill merge. | Pure tie. Parking was reasonable. |
| f6fe503b | parked_lineage | split_route_reinsertion_vns | Local-search split-route reinsertion. | Pure tie. Parking was reasonable. |
| d08c64a6 | abandoned | biased_distance_insertion_repair | Destroy/repair insertion bias. | Case 1/2/5, pair 3/5/8. Abandon was reasonable. |
| 0620ed64 | parked_lineage | route_limit_seed_diversifier | State caching proposal blocked twice; rerouted to construction seed diversifier. | The blocks were useful: private dynamic state and inert helpers were caught pre-protocol. Final construction attempt tied 0/0/8. Parking was reasonable. |
| 5047e926 | abandoned | cross_exchange_vns | Local-search cross-exchange. | Case 0/0/8 but pair 0/2/14 and negative CI. Abandon was reasonable. |
| c4e2ed74 | parked_lineage | route_limit_repair_retry | Scheduler route-limit repair retry and telemetry. | Pure tie. Parking was reasonable. |
| e78e94d2 | explore | operator_evidence_bridge | Scheduler operator evidence bridge. | Pure tie, active no-effect, fresh champion required but no replay identity available. Continuing is only a bookkeeping residual, not a strong research signal. |

## 4. LLM Calls, Sessions, Context, And Implemented Proposals

The agentic proposal pattern was consistent:

- Hypothesis target intent calls selected a target/action/mechanism.
- Hypothesis calls formalized the proposal.
- Tool-selection calls chose context reads, feedback reads, branch state reads, and memory/lesson queries.
- Code calls generated full-file or multi-file patches. Formal diffs confirm that screened candidates were materialized as concrete code.

The context was generally enough for the agent to avoid blind edits. Session outputs show repeated use of:

- public spec: surface list, problem summary, interface/contract previews;
- champion code: active solver design, call graph, active solver map, operator registry, target algorithm file;
- screening detail: `feedback.query_screening` and `feedback.query_runtime`;
- tainted memory: proposal/search memory safe view;
- branch state: for refinements and same-branch follow-up.

Context sufficiency caveats:

- It was enough to generate syntactically and contract-valid code for 40 verification-consuming candidates with zero verification failures.
- It was not enough to consistently enforce structured lesson usage without quality blocks: six proposal blocks came from `branch_lesson_usage_semantic_mismatch`.
- It was not enough to avoid human-level near-duplicates: construction seed selectors, local-search exchange variants, destroy/repair insertion variants, scheduler telemetry bridges, and threshold acceptance refinements recurred even though the formal near-duplicate counter stayed at 0.
- It was not enough to materialize all fresh-runtime pressure candidates: final drain found three active pressure candidates but no `replay_identity`.

Formal code-change coverage by screened candidate:

| Branch | Candidate | Files | Added/removed | Main code introduced or modified |
|---|---|---|---|---|
| b2a15767 | 07d1b13a | destroy_repair.py, scheduler.py | +102/-16 | route-limit-aware insert, displacement repair. |
| 5bcde00c | a46199fe | scheduler.py | +48/-11 | budget-aware VNS gating. |
| 735a1d22 | 4e3f7dc4 | local_search.py | +129/-0 | three-exchange VNS helpers. |
| f11d505c | b6eed8f2 | route_compaction.py, scheduler.py | +155/-0 | route-compaction repair helper. |
| f11d505c | faba1e5d | route_compaction.py | +174/-0 | payoff-gated compaction refinement. |
| 5904813b | d0f05d76 | construction.py, scheduler.py | +70/-3 | route-limit seed diversification. |
| 5904813b | 8d021699 | construction.py | +57/-2 | seed-diversification repair. |
| c681f423 | 68b11206 | acceptance.py, scheduler.py | +46/-1 | rank-temperature acceptance. |
| 56224f40 | 1659961c | local_search.py | +152/-0 | bounded two-route segment relink. |
| ec461d86 | fd175f89 | destroy_repair.py, scheduler.py | +107/-2 | biased exchange repair. |
| 61193272 | 04dc169c | construction.py, scheduler.py | +49/-5 | seed-pool selector. |
| 61193272 | 84418a9f | construction.py | +59/-0 | selector activation/budget evidence. |
| 61193272 | a7b862d4 | construction.py | +55/-0 | incumbent-preserving selector guard. |
| 61193272 | d00632d9 | construction.py | +61/-0 | diagnostic selector parameterization. |
| 5072010d | ad1b21ed | local_search.py | +84/-0 | empty-route absorption VNS. |
| b1b170f6 | 298785ef | scheduler.py | +51/-1 | operator-credit observability. |
| 50adbefc | f16eef51 | scheduler.py | +82/-3 | phase budget gate. |
| 6300182d | 26cd756c | local_search.py | +109/-0 | lambda-interchange VNS. |
| f05a97b7 | ade5ddce | route_pool.py, scheduler.py | +162/-0 | elite route-pool recombination. |
| fc855efe | aca33e2f | destroy_repair.py, scheduler.py | +123/-0 | split-delivery-aware repair. |
| db3c1722 | e3c53cb9 | acceptance.py, scheduler.py | +58/-5 | stagnation reheat acceptance. |
| 9f4a1b5c | d61afcfd | local_search.py | +91/-0 | route 2-opt bridge. |
| 091a9851 | 66f98f9f | destroy_repair.py, scheduler.py | +65/-17 | slack-biased regret insertion. |
| 41f41ced | 2ba158a4 | construction.py, scheduler.py | +47/-1 | route-limit seed portfolio. |
| 8e053dfe | f2be8e55 | local_search.py | +81/-0 | inter-route 2-swap. |
| 72a7d01a | 070d493e | scheduler.py | +69/-2 | route-count-aware repair selection. |
| 2908e9ea | 19a38cff | scheduler.py | +56/-0 | operator-effect telemetry bridge. |
| 00c45e18 | d2709f22 | acceptance.py, scheduler.py | +35/-3 | threshold record-to-record acceptance. |
| 00c45e18 | 25989e96 | acceptance.py, scheduler.py | +81/-3 | plateau-conditional threshold refinement. |
| 00c45e18 | 48aa6797 | acceptance.py, scheduler.py | +100/-3 | success-credited threshold probe. |
| 00c45e18 | d378dee2 | acceptance.py | +92/-2 | payoff-observable threshold diagnostic. |
| 903852e8 | ca869df1 | destroy_repair.py, scheduler.py | +84/-1 | load-entropy removal. |
| ad1bceff | 1f575a24 | destroy_repair.py, scheduler.py | +81/-1 | capacity-slack regret repair. |
| 0d384e4a | 1396c9d3 | construction.py, scheduler.py | +115/-3 | route-fill merge construction. |
| f6fe503b | 4527698a | local_search.py | +73/-0 | split-route reinsertion VNS. |
| d08c64a6 | efe9982d | destroy_repair.py, scheduler.py | +87/-2 | biased distance insertion repair. |
| 0620ed64 | c3c1ffc7 | construction.py, scheduler.py | +127/-1 | route-limit seed diversifier. |
| 5047e926 | 56fadf1f | local_search.py | +114/-0 | cross-exchange VNS. |
| c4e2ed74 | f9da9e35 | scheduler.py | +79/-5 | route-limit repair retry. |
| e78e94d2 | 78a3100a | scheduler.py | +38/-0 | operator evidence bridge. |

There are 40 formal candidate diffs for 40 distinct screened hypotheses. The 44 screening metric rows include 4 fresh-runtime replays of already-screened candidates.

Session-level accounting:

- 90 agentic proposal sessions were recorded.
- Typical successful candidates had two sessions: a `partial_hypothesis_only` session ending at `hypothesis_awaiting_approval`, then a `completed` code session.
- Quality-blocked candidates ended as partial or failed sessions and did not produce verification/protocol metrics.
- Session statuses: mostly `partial_hypothesis_only` and `completed`, with failed sessions for the 00c45e18 target-intent mismatch and the two 0620ed64 code-generation blocks.
- Every session was marked tainted and exposure-controlled; this is compliant with the architecture as long as only post-protocol deterministic features are used by Decision.

## 5. Branch-To-Branch Differences And Lesson Use

The run did real breadth across solver layers: destroy/repair, local search, scheduler, construction, acceptance, route compaction, and route pool. It also exploited same-branch refinements when a branch showed marginal, weak-positive, or diagnostic value.

What was avoided or contrasted:

- The proposal system repeatedly named prior route-limit repair, scheduler gating, route compaction, three-exchange, acceptance, and construction attempts in later hypotheses.
- `cross_branch_research_observability` reports 81 branch lesson records, 45 lesson-usage requirements, 40 present usages, 38 satisfied usages, 76 avoided lessons, 93 contrasted lessons, and 8 preserved same-branch lessons.
- Six quality blocks stopped proposals that did not provide machine-readable branch lesson usage. That is useful: weak narrative references were not allowed to proceed as if they were structured contrast.

Where repeated waste still occurred:

- Construction seed-selection variants recurred across 5904813b, 61193272, 41f41ced, 0d384e4a, and 0620ed64.
- Local-search exchange/bridge variants recurred across 735a1d22, 56224f40, 6300182d, 9f4a1b5c, 8e053dfe, f6fe503b, and 5047e926.
- Destroy/repair insertion or slack variants recurred across b2a15767, 091a9851, ad1bceff, d08c64a6, c4e2ed74, and related blocked proposals.
- Scheduler telemetry/observability variants recurred across b1b170f6, 2908e9ea, c4e2ed74, e78e94d2, and the blocked 61193272 telemetry bridge.
- 00c45e18 received four same-mechanism acceptance refinements after a replay failed case-level evidence. That was excessive.

The striking mismatch is that the formal observability object reports `near_duplicate_count=0` and `saturated_signature_count=0`, while human inspection shows multiple near families. The advisory behavior helped enforce explicit lesson mentions, but it did not yet provide strong search-space throttling.

## 6. Framework Behavior Judgment

Proposal quality blocks:

- Strong positive. Nine blocks consumed proposal attempts but not max-round budget or protocol metrics.
- Six blocks enforced branch lesson usage semantics; one blocked target-intent binding drift; two blocked code-generation/contract preview issues.
- The blocks prevented contaminated or structurally invalid proposals from entering Decision or screening. This is aligned with architecture v3.

Lesson-to-action and sibling advisory gate:

- Partly effective. The gate forced explicit structured lesson usage, and most attempts satisfied it.
- The advisory gate did not prevent broad family repetition. It produced auditability more than optimization of search allocation.
- The framework should add a stronger generic novelty/family saturation mechanism that remains proposal-layer only and affects scheduler/proposal eligibility through deterministic metadata, not CVRP-specific prompt rules.

Fresh runtime replay materialization:

- Mixed. Four fresh replays executed for weak-positive candidates and correctly did not count toward max rounds.
- All four replays failed to produce case-level support, so they were useful checks against cached-runtime false positives.
- Final drain is incomplete in an important way: it found runtime pressure on active branches 61193272, 00c45e18, and e78e94d2, but `executed=0` because no structured `replay_identity` was materializable and the scheduler was capacity-blocked. This is a framework durability problem, not a CVRP algorithm problem.

Accounting clarity:

- Much improved. The reconciliation separates effective rounds, proposal blocks, formal screening candidates, protocol metric rows, fresh-runtime replay rows, validation/frozen rows, and legacy counter semantics.
- Remaining gap: model/token accounting is split between DB rows and trace files, and token subfields are incomplete. A stable top-level accounting summary should include request-kind token totals, cache/reasoning/total fields when available, and clear null semantics.

Lifecycle decisions:

- Conservative and mostly correct. No validation/frozen promotion happened because no branch met case-level evidence thresholds.
- Abandon decisions for quality regressions and invalid/runtime-failure candidates were reasonable.
- Parking no-effect branches to reclaim slots was reasonable.
- The weak spot is over-continuation of unresolved tie branches under low cached runtime confidence. A fresh-runtime-required state without replay identity should not remain an attractive active exploration sink.

Decision boundary compliance:

- The artifacts are consistent with Decision boundary compliance. Candidate intent, observability value, runtime policy, cross-branch lessons, and proposal guidance are repeatedly marked `proposal_visibility_only` and `decision_features_excluded`.
- Runtime evidence policy reports 44 of 44 protocol rows with `standalone_optimization_signal=false` and `decision_features_excluded_count=44`; 39 rows were audit/proposal guidance only.
- I found no evidence that cross-branch lesson text directly promoted or abandoned a branch. Decisions were tied to screening gate outcomes, lifecycle policy, runtime diagnostics, and deterministic reason codes.

## 7. Concrete Conclusion

The run is stable enough as an auditable Scion v0.4 experiment. It completed the requested 40 effective rounds, used `gpt-5.5`, preserved evidence/lineage, avoided validation/frozen overreach, and kept LLM proposal material out of Decision features.

It did not do effective algorithmic research in the sense of finding a credible CVRP improvement. The research was broad and mostly reasonable, but the objective evidence was tie-dominated. Weak positives were pair-level or low-confidence runtime artifacts; fresh replays removed rather than confirmed those signals. No branch earned validation, no champion changed, and no frozen budget was used.

Specific framework optimizations needed before the next experiment:

1. Make replay identity durable for every candidate that can enter `fresh_champion_required`, and fail closed if replay materialization is missing. Do not leave active branches with runtime pressure but no replay identity.
2. Add deterministic family/novelty saturation across generic mechanism metadata: target file, action, mechanism family, activation path, effect path, and runtime-budget strategy. Keep this as proposal/scheduler metadata, not CVRP-specific algorithm prompting.
3. Convert repeated no-effect tie branches into stricter lifecycle outcomes. After a bounded number of same-family ties with low cached runtime confidence and no materializable replay, park or abandon instead of continuing to refine.
4. Strengthen sibling advisory from "must mention structured lesson usage" to "must show material difference against saturated generic dimensions." The current gate enforces syntax and auditability but allows repeated search in equivalent neighborhoods.
5. Unify LLM/model accounting at campaign-summary level: model counts, request-kind counts, input/output/total/reasoning/cache token fields, and explicit null/unavailable semantics.
6. Preserve the Decision boundary as implemented here: proposal visibility and cross-branch lessons should continue to guide only proposal generation and audit, while promotion/abandon remains based on deterministic post-gate features.

Do not treat these as CVRP-specific prompt fixes. The needed changes are framework-level controls around replay durability, generic novelty accounting, lifecycle pressure, and accounting clarity.
