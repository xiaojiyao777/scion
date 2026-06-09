# v0.4 post-40R repair verify CVRP 12R GPT-5.5 branch analysis

Date: 2026-06-09

Experiment:
`/home/clawd/research/scion-experiments/v04-post40r-repair-verify-cvrp-12r-gpt55-20260609T042719Z-claw-12r-gpt55-20260609T042719Z-claw`

Primary evidence:

- Architecture baseline: `scion/design/scion-architecture-v3.md`
- Run command/env: `command.txt`, `launch.env`, `run.log`, `exit.txt`
- Campaign state: `campaign/campaign_summary.json`, `campaign/status.json`, `campaign/scion.db`
- LLM/session evidence: `campaign/llm_traces/*.json`, `campaign/agentic_sessions/agentic_session_index.json`, `campaign/agentic_sessions/agentic_session_trace_index.json`, per-session `transcript.json` and `output.json`
- Candidate/protocol evidence: `campaign/artifacts/formal_candidates/index.jsonl`, `campaign/metrics/*.json`, `campaign/workspaces/*`

## Architectural read

I used `scion/design/scion-architecture-v3.md` as the governing boundary:

- LLM output is tainted proposal material only.
- Candidate code must pass Contract -> Verification -> Protocol.
- Decision must read deterministic `DecisionFeatures`, not free-text LLM analysis.
- Cross-branch or sibling lessons may be visible to proposal generation, but must remain advisory and excluded from DecisionFeatures.
- CVRP-specific mechanics are problem-layer evidence; they should not be generalized into core Scion framework requirements.

This run follows that boundary. The observed sibling/cross-branch material is proposal visibility only; `status.json` records `cross_branch_research_observability.policy=proposal_observability_only` and `decision_input_policy=excluded_from_decision_features`.

## Executive conclusion

The 12R CVRP run is valid and complete. Wrapper exit was normal (`WRAPPER_EXIT_STATUS:0` in `exit.txt`), `run.log` ended with "Campaign finished", and `status.json` reports `run_validity.status=valid`, `complete=true`, `requested_rounds=12`, `effective_rounds_completed=12`, `stopped_reason=max_rounds_exhausted`.

Research quality is acceptable for a repaired v0.4 branch-learning/control run. The agent generated plausible CVRP solver-design hypotheses, used solver structure, prior screening/runtime feedback, and sibling branch cards, and then allowed deterministic gates and protocol metrics to reject weak ideas. It did not find a promotable candidate: champion stayed `version=1`, accepted/promoted experiments were zero, and every effective candidate failed screening thresholds or was parked after no-effect/runtime evidence.

The framework did not block effective research. Contract, verification, canary, formal candidate persistence, lineage integrity, and evidence integrity were all usable. The main remaining weakness is not a P1 blocker: cross-branch diversity still permits repeated broad mechanism families, especially local-search and scheduler variants, even though near-duplicate diagnostics are zero. That is a P2 observability/diversity-pressure improvement before very long runs, not a reason to stop 20R/40R experiments.

## Run validity and accounting

Run setup:

- `command.txt`: `--rounds 12 --time-limit-sec 10 --agentic-session-timeout-sec 900 --disable-early-stop --agentic-proposal`
- `launch.env`: `SCION_MODEL=gpt-5.5`, `SCION_BASE_URL=http://127.0.0.1:8080`, `SCION_LLM_MAX_RETRIES=2`, `SCION_SDK_MAX_RETRIES=0`, `GIT_COMMIT=9ca839a`
- `exit.txt`: wrapper exit status 0, started `2026-06-09T04:27:19Z`, ended `2026-06-09T06:01:09Z`
- `run.log`: campaign started with `max_rounds=12`, `mock_llm=False`, and finished with `experiments: 15`, `champion ver: 1`, `active branches: 0`

LLM accounting:

- `campaign_summary.json` and `status.json` agree on `trace_file_count=106`.
- Request kind counts: `hypothesis_target_intent=12`, `hypothesis=13`, `tool_selection=65`, `code=16`.
- Provider/model counts: 106 `openai_compatible`, 106 `gpt-5.5`.
- No unknown model/provider/request-kind counts and no unreadable/no-usage traces.

Protocol/accounting reconciliation:

- `effective_rounds_completed=12`; this is the max-round budget counter.
- `screened_rounds=15` / `protocol_metric_results=15` because there are 12 effective screenings plus 3 non-counted fresh-runtime replay protocol rows.
- `formal_candidates/index.jsonl` has 12 entries, one for each replayable effective patch candidate.
- `verification_consumed_candidates=12`, `verification_failure_consumed_candidates=0`.
- `proposal_quality_blocks=0`, `quality_block_ledger_count=0`.
- `telemetry_repair_attempts=0`, `telemetry_failed_experiments=0`.

Accounting anomalies are explainable:

- `proposal_attempts_total=13` vs `effective_rounds_completed=12`: there were 12 effective candidate hypotheses, but session `1ba6053a-f15a-4c45-bbe5-b6c69dc319da` had one hypothesis schema retry for `route_limit_seed_diversification`; trace index shows that hypothesis session had 1 `hypothesis_target_intent` and 2 `hypothesis` calls. The retry was repaired inside the session, so it did not become a quality block.
- `code=16`: 12 completed code sessions plus 4 extra code attempts. Session `2564d51f-88cb-40c0-ba82-3500a4e8b3cb` recorded 3 code retry failures from `algorithm_smoke_failure`; session `1190e8b8-d03b-4d58-8701-d5b8f4f4ccf8` recorded 1 retry from `contract_boundary_failure`. Both sessions completed with final passing candidates.
- `tool_selection=65`: this is the sum of tool-selection planner calls in the 12 code sessions: 8, 3, 3, 7, 4, 5, 6, 6, 6, 5, 6, 6. It reflects diagnosis/context-gathering depth, not 65 candidate attempts.
- No quality blocks: despite one hypothesis schema retry and four code retry failures, every effective candidate that reached protocol passed schema/contract/verification/canary; retries were internal repair loops with successful final artifacts.

## Round-by-round analysis

The table below treats DB experiment rows 1,2,3,4,5,6,8,9,10,11,12,13 as the 12 effective rounds. DB rows 7,14,15 are non-counted fresh-runtime replay rows and are listed separately.

| Eff. round | DB event | Branch / hypothesis | Agent calls and tool use | Hypothesis and code change | Gates/protocol/decision | Scion v3 assessment |
|---:|---:|---|---|---|---|---|
| 1 | 1 | `109a1e2e` / `c5f1bf05` | Hypothesis session `88ffbd11`: target-intent + hypothesis; 12 observations over active solver design, solver map, file list, call graph, local-search files/slices, memory. Code session `0cbdc54e`: 8 tool-selection calls; tools included `memory.query`, `context.read_branch_state`, `context.read_surface`, `context.read_algorithm_file`, `feedback.query_screening`, `feedback.query_runtime`. | `route_merge_local_search`: add sparse-route absorption VNS in `policies/baseline_modules/local_search.py`; patch summary `+97/-0`. | Contract/verification/canary passed. Screening 8 cases, 16 pairs: case `0W/0L/8T`, pair `0W/0L/16T`, median/CI `0/0/0`, metrics `metrics/ba12992b-7748-4e84-9ca8-34e3ae5e791c.json`, decision `continue_explore`. | Correct: creative route-merge proposal was gated; no-effect result stayed in screening and did not promote. |
| 2 | 2 | `33c0b75f` / `6261784c` | Hypothesis `c3b1356e`: target-intent + hypothesis; used screening/runtime feedback from round 1. Code `c706090a`: 3 tool-selection calls; read target file, branch state, screening/runtime feedback. | `granular_slack_regret_repair`: add slack-scarcity regret repair in `destroy_repair.py`, plus scheduler integration; patch summaries include `destroy_repair.py +72/-0`, later `+41/-0`, `scheduler.py +12/-0`. | Passed all gates. Screening 8 cases: case `1W/0L/7T`, pair `5W/0L/11T`, median `0.25`, CI `0..4.5`, metrics `metrics/b4742b6e-a8a3-4269-9163-e9dedcea926d.json`, decision `continue_explore`. | Correct: weak positive was retained for branch follow-up but not promoted; screening is not promotion. |
| 3 | 3 | `33c0b75f` / `65a39c67` | Hypothesis `45efa83d`: target-intent + hypothesis with prior weak-positive branch evidence; code `ee5766ba`: 3 tool-selection calls. | Refine `granular_slack_regret_repair` with bounded two-mode activation/scoring; patch summaries `destroy_repair.py +32/-17`, `+25/-2`. | Passed all gates. Screening: case `0W/1L/7T`, pair `1W/2L/13T`, median/CI `0/0/0`, metrics `metrics/c35a807a-60b8-4461-916f-e3fceb288ebf.json`, decision `abandon`. Branch ended `abandoned`, code `discarded`, reason includes `SCREENING_FAIL_WIN_RATE` and `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`. | Correct: same-branch weak-positive follow-up was allowed, then archived after loss/no-win evidence. |
| 4 | 4 | `ae995084` / `d97e20ef` | Hypothesis `ffe5aa4f`: target-intent + hypothesis; 13 observations. Code `3b7f717f`: 7 tool-selection calls and target/scheduler reads. | `slack_aware_route_compaction`: create `policies/baseline_modules/route_compaction.py` and integrate into scheduler; patch summaries `route_compaction.py +89/-0`, scheduler `+12/-0`. | Passed all gates. Create-new screening used 12 cases/24 pairs: `0W/0L/12T`, pair `0W/0L/24T`, median/CI `0/0/0`, runtime ratio median about `1.0044`, metrics `metrics/efb70f5b-fa2b-439a-b0a2-14212b2fe512.json`, decision `continue_explore`. Telemetry effect-zero diagnostics recorded for compaction. | Correct: create-new got larger screening; telemetry was diagnostic/proposal guidance, not promotion evidence. |
| 5 | 5 | `ae995084` / `546ef713` | Hypothesis `567a5e66`: target-intent + hypothesis; code `6a7b66cd`: 4 tool-selection calls. | Refine compaction into gated slack-surplus bridge; patch summaries `route_compaction.py +19/-9`, `+36/-4`. | Passed all gates. Screening: `0W/0L/8T`, pair `0W/0L/16T`, median/CI `0/0/0`, metrics `metrics/7b02a328-e115-406b-8498-d9cd25a4957c.json`, decision `continue_explore`; later fresh-runtime replay row 14 confirmed no effect. Branch finally parked after no-effect follow-up exhaustion. | Correct: branch was allowed one material redirect, then parked after repeated no-objective-effect. |
| 6 | 6 | `1a2c1ee4` / `596146f8` | Hypothesis `2ff18665`: target-intent + hypothesis; code `1536284d`: 5 tool-selection calls. | `bandit_phase_budget_scheduler`: alter scheduler to allocate phase budget away from unpromising ALNS/VNS usage; patch summaries include `scheduler.py +1/-0`, `+0/-13`, `+52/-0`. | Passed all gates. Initial screening: case `0W/0L/8T`, pair `1W/1L/14T`, median/CI `0/0/0`, metrics `metrics/acf07ac6-b260-4a94-a9ef-107eaab0dacb.json`, decision `continue_explore`. Fresh-runtime replay row 7 later closed runtime evidence with metrics `metrics/4f72e31e-d32f-4d88-838b-a4e2e1524074.json`. | Correct: pair-level weak signal was not promoted; fresh champion runtime replay was explicitly excluded from max-round and decision features. |
| 7 | 8 | `5297b2f2` / `141466aa` | Hypothesis `819c499b`: target-intent + hypothesis; code `53072737`: 6 tool-selection calls. | `reheat_on_stagnation_acceptance`: bounded stagnation-aware reheating in `acceptance.py`, plus scheduler telemetry/integration; patch summaries `acceptance.py +36/-1`, scheduler `+22/-0`. | Passed all gates. Screening: `0W/0L/8T`, pair `0W/0L/16T`, median/CI `0/0/0`, metrics `metrics/e8b543bf-fc8e-4f45-8495-0cbd3acfe27a.json`, decision `continue_explore`; row 15 replay later showed runtime ratio about `1.0007` and branch became parked/runtime_regression. | Correct: acceptance idea was tested but not promoted; runtime evidence stayed supporting/diagnostic. |
| 8 | 9 | `1719cbca` / `3321f899` | Hypothesis `1ba6053a`: target-intent + two hypothesis calls due one schema retry; code `2564d51f`: 6 tool-selection calls and 4 code traces total because 3 smoke-failure retries. | `route_limit_seed_diversification`: bounded construction seed portfolio in `construction.py`, scheduler integration; final patch summaries `construction.py +95/-2`, scheduler small changes. | Final candidate passed all gates after retries. Screening: case `0W/0L/8T`, pair `0W/2L/14T`, median `0`, CI `-8..0`, metrics `metrics/fa2d3da4-1110-4cae-9e21-87c0f7bf1abe.json`, decision `abandon`. Branch code discarded. | Correct: internal repair succeeded but protocol found quality regression; deterministic abandon was appropriate. |
| 9 | 10 | `ecb6a8c2` / `a0f3be84` | Hypothesis `219b794e`: target-intent + hypothesis; code `cfd71daa`: 6 tool-selection calls. | `guided_intraroute_reinsertion`: add low-cost intraroute VNS neighborhood in `local_search.py`; patch summaries `+1/-0`, `+66/-0`. | Passed all gates. Screening: case `1W/1L/6T`, pair `3W/5L/8T`, median `-0.5`, CI `-3..0`, metrics `metrics/9c49b890-6d93-413f-9f0a-d19a176d080f.json`, decision `abandon`. | Correct: despite one case win, negative median/loss evidence blocked continuation. |
| 10 | 11 | `099df361` / `320e6127` | Hypothesis `6625bc28`: target-intent + hypothesis; code `1190e8b8`: 5 tool-selection calls and 1 extra code retry from `contract_boundary_failure`. | `route_count_pressure_repair_gate`: scheduler-level gate after destroy/repair; patch summaries `scheduler.py +18/-0`, `+60/-0`. | Final candidate passed all gates. Screening: case `0W/1L/7T`, pair `4W/4L/8T`, median `0`, CI `-5..0.5`, metrics `metrics/da459adf-b31f-4242-9879-52b61840719a.json`, decision `abandon`. | Correct: pair-level activity did not overcome case-level loss and CI risk. |
| 11 | 12 | `19603174` / `5a02b3ac` | Hypothesis `23e58b1e`: target-intent + hypothesis; code `81b73dde`: 6 tool-selection calls. | `interroute_2node_exchange`: add inter-route two-node exchange VNS in `local_search.py`; patch summaries `+1/-0`, `+90/-0`. | Passed all gates. Screening: case `0W/0L/8T`, pair `2W/4L/10T`, median `0`, CI `-2..0`, metrics `metrics/f709f9d0-c47f-4ce7-b8c8-a8066e7c870a.json`, decision `abandon`. | Correct: no case-level gains and pair losses justify abandonment. |
| 12 | 13 | `5b8f7b28` / `8db24300` | Hypothesis `0e6794c6`: target-intent + hypothesis; code `b2b41e92`: 6 tool-selection calls. | `radial_cluster_removal`: add angular/radial ALNS destroy in `destroy_repair.py`, scheduler integration; patch summaries include `destroy_repair.py +42/-0` and scheduler changes. | Passed all gates. Screening: case `0W/0L/8T`, pair `1W/2L/13T`, median `0`, CI `-1..0`, metrics `metrics/98007bce-9f78-471e-9167-c3c6e8264721.json`, decision `abandon`. | Correct: weak/negative pair signal without case wins was rejected. |

Non-counted fresh-runtime replay rows:

- DB event 7: `1a2c1ee4` / `596146f8`, metrics `metrics/4f72e31e-d32f-4d88-838b-a4e2e1524074.json`; `0W/0L/8T`, pair `1W/1L/14T`, runtime ratio median `0.999274`.
- DB event 14: `ae995084` / `546ef713`, metrics `metrics/1f6071d2-f9b1-4988-b6bf-16920b55d3b8.json`; `0W/0L/8T`, pair all ties, runtime ratio median `0.999969`.
- DB event 15: `5297b2f2` / `141466aa`, metrics `metrics/9e4641b9-48f5-4e3f-a117-1fbb4f31256a.json`; `0W/0L/8T`, pair all ties, runtime ratio median `1.000723`.

These rows are visible in protocol metrics but excluded from `effective_rounds_completed`; `status.json` states `fresh_runtime_replay_protocol_results=3` and `fresh_runtime_replay_protocol_results_semantics=non-counted fresh-runtime replay attempts`.

## Branch-level reconstruction

`109a1e2e` / `route_merge_local_search`:

- Research line: first local-search/VNS route absorption idea.
- Evidence: one effective screening, `0W/0L/8T`, runtime slightly faster median (`0.9978` ratio) but no objective movement.
- Handling: retained checkpoint, then `parked_lineage` by active-slot reclaim. This is correct: no promotion, no hard failure, but no reason to spend active slots.

`33c0b75f` / `granular_slack_regret_repair`:

- Research line: moved from high-cost route-merge local search to bounded destroy/repair ordering using slack scarcity.
- Evidence: first candidate had the best signal in the run (`1W/0L/7T`, pair `5W/0L/11T`, median `0.25`), but not enough for screening pass. Follow-up refinement regressed (`0W/1L/7T`).
- Handling: weak positive was allowed a same-branch follow-up, then the branch was abandoned/discarded after loss/no-win. This is good branch lifecycle behavior.

`ae995084` / `slack_aware_route_compaction`:

- Research line: create a scheduler-invoked route-compaction helper, then refine it into a gated bridge.
- Evidence: create-new screening got 12 cases and all tied; telemetry activation was observed but effect was zero. Refine and fresh replay also tied.
- Handling: branch parked after no-effect follow-up exhaustion and runtime-budget pressure. This is correct; telemetry was used diagnostically, not as promotion evidence.

`1a2c1ee4` / `bandit_phase_budget_scheduler`:

- Research line: scheduler budget allocation away from weak ALNS/VNS attempts.
- Evidence: case-level all ties, pair `1W/1L/14T`; fresh runtime replay made runtime evidence sufficient but did not show objective benefit.
- Handling: parked lineage, clean fork required. Correct: pair-level weak positive did not override case-level screening failure.

`5297b2f2` / `reheat_on_stagnation_acceptance`:

- Research line: acceptance temperature/reheat adaptation after no-effect route compaction/scheduler lines.
- Evidence: all tied in objective; fresh runtime replay recorded slight runtime regression (`runtime_ratio_median=1.000723`) and branch classified `runtime_regression`.
- Handling: parked, clean fork required. Correct.

Single-shot abandoned branches:

- `1719cbca` / `route_limit_seed_diversification`: construction diversification repaired through schema/code retries but had pair losses and CI low `-8`; abandoned.
- `ecb6a8c2` / `guided_intraroute_reinsertion`: one case win and one loss, negative median `-0.5`; abandoned.
- `099df361` / `route_count_pressure_repair_gate`: contract-boundary retry repaired, but case-level loss and CI low `-5`; abandoned.
- `19603174` / `interroute_2node_exchange`: case all ties, pair losses; abandoned.
- `5b8f7b28` / `radial_cluster_removal`: case all ties, pair weak/negative; abandoned.

Overall branch governance looks healthy: failed or weak branches were not promoted, no abandoned code remained active, and remaining reportable branches are classified as parked with `next_action=clean_fork`.

## Cross-branch transfer and sibling lessons

Observed visibility:

- Every hypothesis session had prompt manifest sections named `cross_branch_research_map` and `sibling_branches`.
- `status.json` reports `cross_branch_map_seen_count=12`, `branch_lesson_usage_present_count=12`, `branch_lesson_usage_satisfied_count=10`.
- It also reports `avoided_lesson_count=19`, `contrasted_lesson_count=20`, `borrowed_lesson_count=2`, `preserved_same_branch_lesson_count=2`, `near_duplicate_count=0`.
- The policy is explicitly `proposal_observability_only`; `decision_input_policy=excluded_from_decision_features`.

Concrete examples:

- Round 2 contrasted against the round-1 route-merge local-search lesson and moved work into bounded destroy/repair, which is a useful advisory transfer.
- Round 3 preserved same-branch learning by refining the weak-positive `granular_slack_regret_repair`, then abandoned it after the follow-up lost.
- Rounds 6-7 shifted into scheduler and acceptance controls after compaction/local-search no-effect and runtime-saturation signals.
- Later local-search and destroy/repair variants still occurred, but they were not exact duplicates: intraroute reinsertion, two-node exchange, and radial cluster removal target different mechanisms.

Concern:

- Cross-branch transfer is visible and advisory, but diversity pressure is still coarse. `avoid_signature_count=0`, `novelty_pressure_seen_count=0`, and `saturated_signature_count=0`, while the run still spent multiple attempts in repeated broad families: local search (`route_merge`, `guided_intraroute`, `interroute_2node`), scheduler (`bandit_phase_budget`, `route_count_pressure_gate`), and destroy/repair (`granular_slack_regret`, `radial_cluster_removal`).
- This is not a v3 boundary violation, because Decision did not consume sibling lesson text. It is a P2 research-efficiency issue: longer runs would benefit from stronger mechanism-family saturation summaries or explicit "spent family" pressure in proposal visibility.

## Research quality

Strengths:

- Hypotheses were CVRP-plausible and mostly targeted known weak areas: route packing, repair insertion order, scheduler budget, acceptance stagnation, construction seed diversity, and local-search neighborhoods.
- The agent used actual solver artifacts and feedback, not only generic CVRP intuition. Observation ledgers show active solver maps, solver algorithm files, call graph/slices, operator registry, screening feedback, runtime feedback, and proposal memory.
- The run respected problem/core boundaries: CVRP mechanics stayed in problem-layer files such as `policies/baseline_modules/*.py`; the reportable framework behavior is gating/accounting/lineage, not any one CVRP operator idea.
- Deterministic gates and protocol were effective: all 12 final candidates passed structural/semantic checks, then screening metrics made the reject/park decisions.

Weaknesses:

- The search was conservative but somewhat tie-dominated. Most candidates produced no case-level movement; only `granular_slack_regret_repair` had a clean case win, and its follow-up regressed.
- Runtime evidence often served as pressure/diagnostic rather than a standalone optimization signal. `campaign_summary.json` records 15 runtime-budget diagnostics and `runtime_evidence_policy_counts.standalone_optimization_signal_false_count=15`, which is appropriate but means the research did not find robust quality gains.
- Hypothesis-level parent pointers are not very informative (`parent_hypothesis_id` is null in the DB rows), even though branch IDs preserve lineages. For audits, branch-level lineage is enough here, but exact hypothesis parentage would be useful in longer same-branch refinement chains.

## P1/P2 repair assessment

No P1 blocker is indicated by this run:

- Validity/completeness are clean.
- Wrapper/accounting/model tracing are reconciled.
- All LLM traces are `gpt-5.5`.
- Contract/verification/canary gates passed for all effective protocol candidates.
- Formal candidate index has 12 replayable patch artifacts.
- Lineage/evidence integrity are complete.
- Cross-branch lessons are explicitly excluded from DecisionFeatures.

Recommended P2 improvements before much longer experiments:

- Add stronger cross-branch family-saturation visibility: not just near-duplicate detection, but "we have already spent N attempts in local-search/scheduler/destroy-repair with no case-level gains".
- Preserve explicit hypothesis parent links for same-branch refinements so audit can distinguish clean fork, same-mechanism refinement, and branch-level continuation without inferring from branch ID and mechanism.
- Make fresh-runtime replay identity more directly visible in DB rows or status `non_effective_screenings` with branch/hypothesis IDs; current aggregate reconciliation is correct, but the three replay rows require joining event timing and duplicate hypothesis IDs.

## Recommendation

This CVRP 12R run supports moving to longer experiments. It validates the post-40R repair state for campaign completion, GPT-5.5 tracing, proposal/code retry accounting, formal candidate persistence, and branch lifecycle behavior.

For a longer 20R/40R CVRP run, I would proceed with the current framework but track the P2 diversity/lineage improvements above. The expected risk is research efficiency, not invalid promotion or framework control failure.
