# Scion 4R Retry / Quality / Agentic LLM Audit

Audit scope: narrow review of retry accounting, quality blocks, agentic sessions, and LLM call indexing.

Run root: `/home/clawd/research/scion-experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-claw`

Report path: `/home/clawd/research/or-autoresearch-agent/scion/reports/experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-retry-quality-audit.md`

All artifact paths below are relative to the run root unless an absolute path is shown.

## 1. Run Status, Model, and Accounting

Structured reads used:

```bash
jq '.run_validity, .accounting_reconciliation, .campaign_loop, .llm_request_kind_counts' \
  /home/clawd/research/scion-experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-claw/campaign/status.json

jq '.status, .campaign_exit_status, .run_complete, .run_validity_status, .completed_requested_rounds, .last_stop_reason' \
  /home/clawd/research/scion-experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-claw/campaign/run_status.json

jq -r '.sessions[] as $s | $s.traces[] | [.request_kind,.model] | @tsv' \
  /home/clawd/research/scion-experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-claw/campaign/agentic_sessions/agentic_session_trace_index.json | sort | uniq -c
```

Findings:

| Field | Value | Evidence |
|---|---:|---|
| wrapper status | `finished`, exit 0 | `campaign/run_status.json` |
| run validity | `valid` | `campaign/status.json.run_validity.status` |
| run completeness | `complete` | `campaign/status.json.run_complete=true`, `completed_requested_rounds=true` |
| stop reason | `max_rounds_exhausted` | `campaign/status.json.last_stop_reason` |
| requested rounds | 4 | `campaign/status.json.accounting_reconciliation.requested_rounds` |
| effective rounds completed | 4 | `campaign/status.json.accounting_reconciliation.effective_rounds_completed` |
| proposal attempts total | 8 | `campaign/status.json.accounting_reconciliation.proposal_attempts_total` |
| screened experiments | 6 | `campaign/status.json.accounting_reconciliation.screened_experiments` |
| screened but not effective | 2 | `campaign/status.json.accounting_reconciliation.screened_not_effective` |
| formal screened candidates | 4 | `campaign/status.json.accounting_reconciliation.formal_screened_candidates` |
| protocol evaluated candidates | 4 | `campaign/status.json.accounting_reconciliation.protocol_evaluated_candidates` |
| quality blocks | 4 | `campaign/status.json.accounting_reconciliation.quality_blocks` |
| model repair failures | 2 | `campaign/status.json.campaign_loop.failure_categories.model_repair_failed` |
| agentic sessions | 14 | `campaign/agentic_sessions/agentic_session_trace_index.json.session_count` |
| LLM traces | 116 | `campaign/agentic_sessions/agentic_session_trace_index.json.trace_count` |
| model coverage | all `gpt-5.5` | trace index and every `campaign/llm_traces/*.json` |

LLM request-kind counts are exactly:

| request_kind | count | model |
|---|---:|---|
| `tool_selection` | 94 | `gpt-5.5` |
| `hypothesis_target_intent` | 6 | `gpt-5.5` |
| `hypothesis` | 6 | `gpt-5.5` |
| `code` | 10 | `gpt-5.5` |

The run did finish, and every indexed LLM trace uses `gpt-5.5`.

## 2. SQLite / State / Step Evidence

Structured reads used:

```bash
sqlite3 /home/clawd/research/scion-experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-claw/campaign/scion.db '.tables'
sqlite3 -header -column ... "select branch_id,state,retry_count,failure_codes,branch_code_status,last_screening_feedback_tier,last_telemetry_outcome,branch_lifecycle_policy_blocks,branch_lifecycle_reroute_reason,branch_mechanism_ids_json from branches order by created_at;"
sqlite3 -header -column ... "select hypothesis_id,branch_id,action,status,target_file,parent_hypothesis_id,family_id,predicted_direction from hypotheses order by created_at;"
sqlite3 -json ... "select rowid,event_kind,branch_id,hypothesis_id,stage,patch_file,contract_passed,verification_passed,telemetry_guard_failed,decision,decision_reason,raw_metrics_ref,model_id,audit_payload_json from experiment_events order by timestamp;"
jq -r '.steps | to_entries[] | ...' campaign/campaign_summary.json
```

SQLite tables present: `branches`, `champions`, `experiment_events`, `hypotheses`, `weight_optimizations`.

Branch state ledger:

| branch_id | state | retry_count | failure_codes | branch_code_status | last feedback | telemetry outcome | mechanism_ids |
|---|---:|---:|---|---|---|---|---|
| `fd658eab-fab0-4ce2-8201-0e9aef306090` | `abandoned` | 0 | `CANDIDATE_RUNTIME_FAILURE`, `SCREENING_RUNTIME_BUDGET_SATURATION` | `quality_regression` | `invalid` | `pair_level_positive_signal` | `interroute_2opt_segment_exchange` |
| `ade67163-1aba-4eaf-89e3-95cce434ee94` | `abandoned` | 0 | `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`, `SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`, `SCREENING_RUNTIME_BUDGET_SATURATION` | `discarded` | `no_effect` | `pair_level_positive_signal` | `route_merge_2opt_bridge`, `capacity_slack_regret_repair` |
| `f5f5cbcd-5a90-4c56-86b0-dcfed912a3b1` | `parked_lineage` | 2 | `PROPOSAL`, `PROPOSAL` | `parked_lineage` | `weak_positive` | `parked_lineage` | `route_limit_repair_bias` |
| `79800905-3643-4919-91b2-19cd269f5dc3` | `explore` | 0 | none | `active_marginal` | `marginal` | `case_level_positive_signal` | `savings_seed_diversification` |

Scheduler-result accounting from SQLite:

| scheduler row | attempt kind | branch_id | hypothesis_id | counts_toward_max_rounds | scheduler_reason | scheduler_slot | result / next policy |
|---:|---|---|---|---|---|---|---|
| 5 | `screening` | `fd658eab...` | `e0dc1a90...` | true | `new_exploration_slot_available` | `explore_new` | abandon; clean fork selected |
| 10 | `screening` | `ade67163...` | `9a152fee...` | true | `new_exploration_slot_available` | `explore_new` | continue; clean fork selected |
| 15 | `screening` | `ade67163...` | `049bbf88...` | true | `same_branch_low_signal_observation_sample` | `repair_diagnostic` | abandon; terminal state released |
| 18 | `proposal_block` | `f5f5cbcd...` | `fc971dda...` | false | `new_exploration_slot_available` | `explore_new` | code generation failed |
| 22 | `screening` | `f5f5cbcd...` | `fc971dda...` | false | `pending_retry_diagnostic_followup` | `repair_diagnostic` | continue; same branch eligible |
| 25 | `proposal_block` | `f5f5cbcd...` | `b5d6037c...` | false | `effect_diagnostic_followup` | `repair_diagnostic` | code generation failed |
| 29 | `screening` | `f5f5cbcd...` | `b5d6037c...` | false | `pending_retry_diagnostic_followup` | `repair_diagnostic` | continue; parked lineage released |
| 34 | `screening` | `79800905...` | `4e24bd6b...` | true | `new_exploration_slot_available` | `explore_new` | continue; clean fork selected |

Important accounting caveat: `campaign/campaign_summary.json.steps[].screened_experiment_effective` is `true` for all six screening steps, but SQLite scheduler audit rows mark attempts 5 and 7 as `counts_toward_max_rounds=false`. The reconciled status agrees with SQLite scheduler accounting: 6 screened experiments, 2 screened-not-effective, 4 effective/formal candidates. This should be treated as an audit-field inconsistency in `campaign_summary.steps`, not as six effective rounds.

## 3. Attempt Ledger

This ledger covers all `proposal_attempts_total=8`.

| attempt | branch_id | hypothesis_id / session_id | attempt_kind | formal? | effective? | quality block? | retry / repair failure? | later protocol / decision |
|---:|---|---|---|---|---|---|---|---|
| 1 | `fd658eab-fab0-4ce2-8201-0e9aef306090` | hyp `e0dc1a90-87a4-4e5c-b817-69cec302523f`; hypothesis session `6eed833b-3a81-4a16-bc37-996bab29f9cb`; code session `39a9b6a4-8ddf-4f72-85cf-f68080a5b758` | `screening` | yes | yes | no | no | Contract/Verification pass; protocol `metrics/1c080ebf-95a9-4700-ba8f-bbb847c52c39.json`; decision `abandon`; reason `CANDIDATE_RUNTIME_FAILURE`, `SCREENING_RUNTIME_BUDGET_SATURATION` |
| 2 | `ade67163-1aba-4eaf-89e3-95cce434ee94` | hyp `9a152fee-8c79-4fb3-a89d-3378e8531400`; hypothesis session `4a576ee6-3958-4d28-983a-0a764c33452b`; code session `248826e0-84d9-43a1-b9b7-b71c019471b2` | `screening` | yes | yes | no | no | Contract/Verification pass; protocol `metrics/8c909b17-f57c-4265-9aeb-9d5ee556de37.json`; decision `continue_explore`; reason `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, `SCREENING_RUNTIME_BUDGET_SATURATION` |
| 3 | `ade67163-1aba-4eaf-89e3-95cce434ee94` | hyp `049bbf88-7d57-4388-9fe0-e8602eeb2ccc`; hypothesis session `8e73f152-5546-48f5-a2bc-856fa0f773a6`; code session `c3b61158-74d2-4979-a2a4-ca3f9223cd10` | `screening` | yes | yes | no | no | Contract/Verification pass; protocol `metrics/8cc59f7e-bacc-4619-855f-ffdd4c9e687c.json`; decision `abandon`; reason includes `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_RUNTIME_BUDGET_SATURATION` |
| 4 | `f5f5cbcd-5a90-4c56-86b0-dcfed912a3b1` | hyp `fc971dda-2b60-4f33-bcbf-4b310451b43a`; inherited hypothesis session `776585fe-6a28-4058-8ece-927ca2f45169`; code session `1b8d18d9-59c5-4428-a496-091a78b93bb2` | `proposal_block` | no | no | yes | yes: `model_repair_failed`; code-stage telemetry identity mismatch on `alns` vs protected `route_limit_repair_bias` | no Contract/Verification/Protocol; scheduler row 18 `counts_toward_max_rounds=false`; next action continued/retried same hypothesis/code line |
| 5 | `f5f5cbcd-5a90-4c56-86b0-dcfed912a3b1` | hyp `fc971dda-2b60-4f33-bcbf-4b310451b43a`; retry code session `295e2bc5-839c-48ca-a24a-c1b4244f0801` | `screening` | no, per reconciled accounting | no, per SQLite scheduler row 22 | no | yes: retry after attempt 4 proposal block | Contract/Verification pass; protocol `metrics/366ea896-7f68-437c-82c7-022bab5036e0.json`; decision `continue_explore`; scheduler `pending_retry_diagnostic_followup`, `counts_toward_max_rounds=false` |
| 6 | `f5f5cbcd-5a90-4c56-86b0-dcfed912a3b1` | hyp `b5d6037c-ec2a-441b-a400-326622b643a8`; hypothesis session `120bf410-15db-40eb-a544-c332186d492f`; code session `48c73d42-dec0-4329-a9eb-3da692441980` | `proposal_block` | no | no | yes | yes: `model_repair_failed`; same telemetry identity mismatch pattern | no Contract/Verification/Protocol; scheduler row 25 `counts_toward_max_rounds=false`; same branch remained eligible for diagnostic retry |
| 7 | `f5f5cbcd-5a90-4c56-86b0-dcfed912a3b1` | hyp `b5d6037c-ec2a-441b-a400-326622b643a8`; retry code session `2d0469e6-306e-417c-b69b-845a1dd3066a` | `screening` | no, per reconciled accounting | no, per SQLite scheduler row 29 | no | yes: retry after attempt 6 proposal block | Contract/Verification pass; protocol `metrics/8bd78ef5-ae61-490e-8f9c-a354e7e2ef64.json`; decision `continue_explore` but lifecycle parked lineage; scheduler `counts_toward_max_rounds=false` |
| 8 | `79800905-3643-4919-91b2-19cd269f5dc3` | hyp `4e24bd6b-1cb0-4bc5-8082-6d11149e2aa4`; hypothesis session `f268ae96-2177-4ecd-b038-09e12e177234`; code session `68e399fe-65c9-4e99-942d-0a9c4c44dab1` | `screening` | yes | yes | no | no | Contract/Verification pass; protocol `metrics/beca6321-0883-4718-afdb-aa731dd0acad.json`; decision `continue_explore`; final retained active marginal branch |

Conclusion from ledger: the 8-vs-4 delta is consistent with Scion accounting if the authoritative source is `status.json` plus SQLite scheduler audit rows: 2 proposal-block attempts and 2 screened-but-not-effective repair-diagnostic attempts are excluded from effective/formal round budget. The ambiguity is that `campaign_summary.steps[].screened_experiment_effective` overstates attempts 5 and 7.

## 4. LLM Call Ledger

Source: `campaign/agentic_sessions/agentic_session_trace_index.json` plus each `campaign/llm_traces/*.json`.

Each call entry is `trace file | request kind | input/output/cache_read tokens | tool/result`. `cache_read` is `llm_usage.cache_read_input_tokens`.

| session_id | branch_id | final status | all indexed LLM calls |
|---|---|---|---|
| `6eed833b-3a81-4a16-bc37-996bab29f9cb` | `fd658eab...` | `partial_hypothesis_only`, hypothesis awaiting approval | `campaign/llm_traces/20260607T062921460472_tool_selection_037ea9bdf0_641da385.json` `tool_selection` 19725/41/0 -> `memory.query`; `campaign/llm_traces/20260607T062927580703_tool_selection_7bd0342bc8_1ef4dbe6.json` `tool_selection` 19835/42/15744 -> `feedback.query_screening`; `campaign/llm_traces/20260607T062929142640_tool_selection_674a982727_848cdbe9.json` `tool_selection` 19984/41/0 -> `feedback.query_runtime`; `campaign/llm_traces/20260607T062931760670_tool_selection_c9e04c9d56_0ac1e3ab.json` `tool_selection` 20129/30/0 -> stop/no tool; `campaign/llm_traces/20260607T062933338649_hypothesis_target_intent_0becec1e87_4122112c.json` `hypothesis_target_intent` 24511/169/0 -> `modify`; `campaign/llm_traces/20260607T062938983674_hypothesis_f8ec639d2b_b5ef9939.json` `hypothesis` 29955/895/0 -> `modify` |
| `39a9b6a4-8ddf-4f72-85cf-f68080a5b758` | `fd658eab...` | `completed` | `20260607T062957968456_tool_selection_f1bf2f922c_2e16d5ed.json` `tool_selection` 10935/32/0 -> `memory.query`; `20260607T062959543910_tool_selection_50e9d6c0bf_a9702ca9.json` 11063/34/0 -> `context.read_branch_state`; `20260607T063003538578_tool_selection_4c9e483483_f4e259d8.json` 11173/56/0 -> `context.read_surface`; `20260607T063005627384_tool_selection_98a7b9455f_7f711625.json` 11381/54/0 -> `context.read_algorithm_file`; `20260607T063007640960_tool_selection_e6c88eca8c_86afe2c8.json` 11509/42/0 -> `feedback.query_screening`; `20260607T063009618894_tool_selection_adb0147366_16a0e9dd.json` 11660/41/0 -> `feedback.query_runtime`; `20260607T063011496911_tool_selection_0422752eaa_db063e22.json` 11803/21/0 -> stop/no tool; `20260607T063012940374_tool_selection_6aa4edbe8c_e0acd6e3.json` 13438/70/3456 -> `context.read_surface`; `20260607T063015211448_tool_selection_2b9321af9b_93ba0a33.json` 13580/56/0 -> `context.read_algorithm_file`; `20260607T063020198541_tool_selection_956aac6140_c96a13f5.json` 13924/55/0 -> `context.read_algorithm_file`; `20260607T063022945172_tool_selection_d5187577cb_d1a3da3d.json` 14247/25/0 -> stop/no tool; `20260607T063025644615_code_b923289dd7_3e97ae00.json` `code` 29156/1969/0 -> `modify` |
| `4a576ee6-3958-4d28-983a-0a764c33452b` | `ade67163...` | `partial_hypothesis_only` | `20260607T064009742024_tool_selection_3cd045d668_71f8103d.json` 19777/41/0 -> `memory.query`; `20260607T064011785550_tool_selection_1f14472953_6928f10f.json` 19898/37/3456 -> `feedback.query_screening`; `20260607T064013647746_tool_selection_bb771ad9c4_7151cc7f.json` 20775/36/0 -> `feedback.query_runtime`; `20260607T064016193077_tool_selection_e0bfc777af_72b76e63.json` 20880/30/0 -> stop/no tool; `20260607T064018015442_hypothesis_target_intent_58cd5c6ef9_90952c2d.json` `hypothesis_target_intent` 25488/182/0 -> `modify`; `20260607T064022318309_hypothesis_7e8ef0689f_14e3bf46.json` `hypothesis` 32611/918/0 -> `modify` |
| `248826e0-84d9-43a1-b9b7-b71c019471b2` | `ade67163...` | `completed` | `20260607T064043521688_tool_selection_1fb26cc6f3_e3ca53ca.json` 10981/41/0 -> `memory.query`; `20260607T064045103334_tool_selection_911a5d111b_6bcfc219.json` 11098/37/0 -> `feedback.query_screening`; `20260607T064047124109_tool_selection_5a128ff70e_6679063b.json` 11264/36/0 -> `feedback.query_runtime`; `20260607T064049468039_tool_selection_c75b6f6a68_de49c8bb.json` 11392/56/0 -> `context.read_algorithm_file`; `20260607T064052133633_tool_selection_0eb66a0d89_e0564909.json` 11535/34/0 -> `context.read_branch_state`; `20260607T064053782293_tool_selection_e7ac160761_842b5c82.json` 11677/30/0 -> stop/no tool; `20260607T064055600502_tool_selection_2039b2ef4f_51825d3d.json` 13138/30/0 -> stop/no tool; `20260607T064057576627_code_de42b53836_bed53152.json` `code` 26723/2537/0 -> `modify` |
| `8e73f152-5546-48f5-a2bc-856fa0f773a6` | `ade67163...` | `partial_hypothesis_only` | `20260607T064830773048_tool_selection_1612239b00_75b3d1a4.json` 19848/41/0 -> `memory.query`; `20260607T064832859614_tool_selection_7edb2b49a0_29559aa4.json` 19968/37/0 -> `feedback.query_screening`; `20260607T064835398578_tool_selection_c1b4534bfb_adfc124a.json` 20864/36/3456 -> `feedback.query_runtime`; `20260607T064837688422_tool_selection_dce6f0081e_7b06338c.json` 20967/21/0 -> stop/no tool; `20260607T064839715041_hypothesis_target_intent_0ac4522f9e_758a8d0c.json` `hypothesis_target_intent` 29371/189/0 -> `modify`; `20260607T064844339749_hypothesis_692146d5f3_f19bb942.json` `hypothesis` 39402/912/0 -> `modify` |
| `c3b61158-74d2-4979-a2a4-ca3f9223cd10` | `ade67163...` | `completed` | `20260607T064904484368_tool_selection_7d19da715d_211f732a.json` 11220/41/3456 -> `memory.query`; `20260607T064908595597_tool_selection_653b2e263a_c29660c9.json` 11338/37/0 -> `feedback.query_screening`; `20260607T064910576528_tool_selection_cdbd15ea23_a122b788.json` 11459/36/3456 -> `feedback.query_runtime`; `20260607T064912170350_tool_selection_ee493549df_5702b9b5.json` 11562/30/0 -> stop/no tool; `20260607T064913756271_tool_selection_522c8c0dc4_cb764040.json` 13547/34/3456 -> `context.read_branch_state`; `20260607T064915402470_tool_selection_3f03ef30c5_e5d1c083.json` 13699/21/0 -> stop/no tool; `20260607T064916840939_code_68341f20a5_02b5f31a.json` `code` 30294/2426/0 -> `modify` |
| `776585fe-6a28-4058-8ece-927ca2f45169` | `f5f5cbcd...` | `partial_hypothesis_only` | `20260607T065646765602_tool_selection_a4bcc37d26_edbdce30.json` 19770/41/0 -> `memory.query`; `20260607T065648864534_tool_selection_a41b312a3e_c107b668.json` 19887/37/3456 -> `feedback.query_screening`; `20260607T065653967458_tool_selection_46295de216_53d24544.json` 20769/36/0 -> `feedback.query_runtime`; `20260607T065655613420_tool_selection_5dcf422aba_88617230.json` 20871/30/0 -> stop/no tool; `20260607T065658371651_hypothesis_target_intent_3ba509ff2f_9411c96d.json` `hypothesis_target_intent` 27159/164/0 -> `modify`; `20260607T065702464976_hypothesis_ab6d071777_893c7d20.json` `hypothesis` 36199/936/0 -> `modify` |
| `1b8d18d9-59c5-4428-a496-091a78b93bb2` | `f5f5cbcd...` | `partial_hypothesis_only`, `code_generation_failed` | `20260607T065722213863_tool_selection_84ad387e0e_53a673e0.json` 10997/41/3456 -> `memory.query`; `20260607T065724223065_tool_selection_aa83523ffc_20b81ff6.json` 11114/37/3456 -> `feedback.query_screening`; `20260607T065726230516_tool_selection_6b37c56cfe_9be143f2.json` 11365/36/0 -> `feedback.query_runtime`; `20260607T065728287812_tool_selection_ec5dcfcb79_7476c797.json` 11511/56/0 -> `context.read_algorithm_file`; `20260607T065732391955_tool_selection_b386b38ca5_c2a9479c.json` 11664/58/0 -> `context.read_algorithm_file`; `20260607T065734905487_tool_selection_9c464f0291_e7510ffe.json` 11793/34/3456 -> `context.read_branch_state`; `20260607T065736606545_tool_selection_e4101fb40e_c34f0b91.json` 11938/21/3456 -> stop/no tool; `20260607T065738383651_tool_selection_3ad668bbc8_21152a07.json` 13773/70/3456 -> `context.read_surface`; `20260607T065740697435_tool_selection_19dfc57240_247f4be2.json` 13914/30/0 -> stop/no tool; `20260607T065742500970_code_db3e914a05_bee3555a.json` `code` 26860/2707/0 -> `modify`; `20260607T065832245630_code_acb7bad299_e5e44833.json` `code` 29132/4384/0 -> `modify` |
| `295e2bc5-839c-48ca-a24a-c1b4244f0801` | `f5f5cbcd...` | `completed` | `20260607T065953074202_tool_selection_bd052b3437_424112bb.json` 19789/41/15744 -> `memory.query`; `20260607T065955104493_tool_selection_37ea979b7a_de712fe3.json` 19904/37/0 -> `feedback.query_screening`; `20260607T065957071694_tool_selection_1ba212c4c1_1e2dc53e.json` 20785/36/15744 -> `feedback.query_runtime`; `20260607T070000103035_tool_selection_d6bf9986e9_a029d90a.json` 20886/30/0 -> stop/no tool; `20260607T070002578708_tool_selection_55f1dbbcf4_47b94325.json` 16908/34/3456 -> `context.read_branch_state`; `20260607T070005803604_tool_selection_984ce79266_1d94af3d.json` 17053/54/0 -> `context.read_algorithm_file`; `20260607T070008533708_tool_selection_f49b8dc8ea_75ae7ce5.json` 17366/55/3456 -> `context.read_algorithm_file`; `20260607T070011234566_tool_selection_101ecd15e4_ed083859.json` 17688/21/3456 -> stop/no tool; `20260607T070014099520_code_5619c94c54_1432264a.json` `code` 36637/2338/0 -> `modify` |
| `120bf410-15db-40eb-a544-c332186d492f` | `f5f5cbcd...` | `partial_hypothesis_only` | `20260607T070743834765_tool_selection_c04fc2669d_67f52cad.json` 19736/41/0 -> `memory.query`; `20260607T070746521441_tool_selection_bab0efd915_2248d37a.json` 19857/37/3456 -> `feedback.query_screening`; `20260607T070749800405_tool_selection_bb1ecd65e4_6e7fa4b7.json` 20740/36/0 -> `feedback.query_runtime`; `20260607T070751508817_tool_selection_25f1b9002a_753cff34.json` 20846/34/0 -> `context.read_branch_state`; `20260607T070753393573_tool_selection_aa8bc2326d_97353d76.json` 20992/30/0 -> stop/no tool; `20260607T070754975573_hypothesis_target_intent_8e6c37829f_a185bb5e.json` `hypothesis_target_intent` 30776/173/0 -> `modify`; `20260607T070800369396_hypothesis_b96745c768_692529b1.json` `hypothesis` 41585/929/0 -> `modify` |
| `48c73d42-dec0-4329-a9eb-3da692441980` | `f5f5cbcd...` | `partial_hypothesis_only`, `code_generation_failed` | `20260607T070821573884_tool_selection_af4bc84f58_4ed7de9e.json` 11209/41/3456 -> `memory.query`; `20260607T070824458575_tool_selection_0966059c61_0ef3ef6f.json` 11333/37/3456 -> `feedback.query_screening`; `20260607T070826941696_tool_selection_377d989494_0517eed6.json` 11621/36/3456 -> `feedback.query_runtime`; `20260607T070831556438_tool_selection_51c3781d2f_2b9dfbb1.json` 11772/56/0 -> `context.read_algorithm_file`; `20260607T070833614689_tool_selection_76a3bec456_53b53b6b.json` 11919/58/3456 -> `context.read_algorithm_file`; `20260607T070835763940_tool_selection_525ea23fc7_f937ebfb.json` 12048/30/3456 -> stop/no tool; `20260607T070837631248_tool_selection_bd7e642049_5c120614.json` 13794/34/3456 -> `context.read_branch_state`; `20260607T070839262459_tool_selection_7b9b0ba996_a73db91a.json` 13940/21/3456 -> stop/no tool; `20260607T070840778971_code_d9c9e45fc9_bdf9ffb0.json` `code` 28221/3200/0 -> `modify`; `20260607T070940050188_code_9195abe588_0ea35638.json` `code` 31165/3276/0 -> `modify` |
| `2d0469e6-306e-417c-b69b-845a1dd3066a` | `f5f5cbcd...` | `completed` | `20260607T071040995206_tool_selection_25d81e52b4_f537ecf0.json` 19750/41/0 -> `memory.query`; `20260607T071043946845_tool_selection_f82ef4159a_25a416f2.json` 19867/42/0 -> `feedback.query_screening`; `20260607T071045687133_tool_selection_89de13a7ae_f04d690b.json` 20749/36/3456 -> `feedback.query_runtime`; `20260607T071047382056_tool_selection_36accdef02_4c93e831.json` 20854/30/15744 -> stop/no tool; `20260607T071049856631_tool_selection_d01b592c11_8a94988a.json` 17303/34/0 -> `context.read_branch_state`; `20260607T071052299136_tool_selection_c9d2a89783_04b07227.json` 17447/70/3456 -> `context.read_surface`; `20260607T071055619033_tool_selection_e67daeecaf_f0cb1d88.json` 17592/54/0 -> `context.read_algorithm_file`; `20260607T071057618093_tool_selection_935fd4de99_b577225b.json` 17907/55/0 -> `context.read_algorithm_file`; `20260607T071059875907_tool_selection_37e5434a01_e1fb67c9.json` 18230/21/3456 -> stop/no tool; `20260607T071101764175_code_18468bf8fe_8829c06c.json` `code` 38695/2424/0 -> `modify` |
| `f268ae96-2177-4ecd-b038-09e12e177234` | `79800905...` | `partial_hypothesis_only` | `20260607T071836794308_tool_selection_d7eb25fab1_14a9e221.json` 19769/41/0 -> `memory.query`; `20260607T071838653250_tool_selection_e6b615d1fc_c8bb14d0.json` 19887/37/3456 -> `feedback.query_screening`; `20260607T071842166668_tool_selection_aa22c924db_8611862d.json` 20766/36/3456 -> `feedback.query_runtime`; `20260607T071843752732_tool_selection_7d5f26a2b7_4af9b284.json` 20871/30/3456 -> stop/no tool; `20260607T071846425258_hypothesis_target_intent_b6fe9c73c8_a5902ff7.json` `hypothesis_target_intent` 28053/182/0 -> `modify`; `20260607T071851477636_hypothesis_eeeffa979a_19b06e29.json` `hypothesis` 41916/864/0 -> `modify` |
| `68e399fe-65c9-4e99-942d-0a9c4c44dab1` | `79800905...` | `completed` | `20260607T071911023214_tool_selection_f738d0c80e_84cf0dc8.json` 10987/41/3456 -> `memory.query`; `20260607T071913693876_tool_selection_5984931cc5_831ce4d6.json` 11108/37/3456 -> `feedback.query_screening`; `20260607T071916525075_tool_selection_ce26a1073e_81daebd7.json` 11444/36/0 -> `feedback.query_runtime`; `20260607T071918563569_tool_selection_1fad9ff54e_99ff7066.json` 11605/56/0 -> `context.read_algorithm_file`; `20260607T071920675753_tool_selection_fef973eced_ecb9291f.json` 11762/58/0 -> `context.read_algorithm_file`; `20260607T071922918800_tool_selection_fc4c09ab62_3a94b979.json` 11908/56/0 -> `context.read_algorithm_file`; `20260607T071924956196_tool_selection_cf74e73403_28056559.json` 12043/34/3456 -> `context.read_branch_state`; `20260607T071926876966_tool_selection_f601783e0b_ce019880.json` 12190/55/3456 -> `context.read_surface`; `20260607T071931134547_tool_selection_53bc640f33_f5766954.json` 12418/54/3456 -> `context.read_algorithm_file`; `20260607T071934499469_tool_selection_33535d9a00_7d34d4b2.json` 12537/30/3456 -> stop/no tool; `20260607T071936289519_tool_selection_eaf9c4f000_70eb4307.json` 14523/21/3456 -> stop/no tool; `20260607T071937721031_code_51265b816e_d505ec1d.json` `code` 27255/2821/0 -> `modify` |

### Real Tools Versus Tool-Selection Traces

The 94 `tool_selection` LLM traces are planning calls to `plan_proposal_tool_call`. They are not themselves tool execution records. Real tool execution appears in each session transcript as `Proposal tool observation: <tool>`.

Transcript evidence command:

```bash
for f in campaign/agentic_sessions/*/transcript.json; do
  jq -r '(.session_id) as $sid | [.compact_transcript[] | select(.message|startswith("Proposal tool observation:")) | .metadata.tool_name] as $tools | [$sid, ($tools|length), ($tools|unique|join(","))] | @tsv' "$RUN_ROOT/$f"
done
```

Actual proposal tool observation counts by session:

| session | observation count | executed tool families |
|---|---:|---|
| `6eed833b...` | 18 | context, feedback, memory, proposal schema/permission previews |
| `39a9b6a4...` | 21 | context, feedback, memory, schema/permission, contract preview, algorithm smoke |
| `4a576ee6...` | 18 | context, feedback, memory, schema/permission |
| `248826e0...` | 17 | context, feedback, memory, schema/permission, contract preview, algorithm smoke |
| `8e73f152...` | 19 | context, feedback, memory, schema/permission |
| `c3b61158...` | 18 | context, feedback, memory, schema/permission, contract preview, algorithm smoke |
| `776585fe...` | 18 | context, feedback, memory, schema/permission |
| `1b8d18d9...` | 18 | context, feedback, memory, schema/permission |
| `295e2bc5...` | 24 | context, feedback, memory, schema/permission, contract preview, algorithm smoke |
| `120bf410...` | 19 | context, feedback, memory, schema/permission |
| `48c73d42...` | 17 | context, feedback, memory, schema/permission |
| `2d0469e6...` | 25 | context, feedback, memory, schema/permission, contract preview, algorithm smoke |
| `f268ae96...` | 20 | context, feedback, memory, schema/permission |
| `68e399fe...` | 21 | context, feedback, memory, schema/permission, contract preview, algorithm smoke |

Thus the run did execute real proposal tools, but those executions are transcript events, not the `tool_selection` traces. The trace index only records the LLM calls that selected the next tool.

## 5. Four Quality Blocks

`status.json.campaign_loop.proposal_quality_blocks_consumed=4` and `status.json.accounting_reconciliation.quality_blocks=4`. Direct itemization is weaker than the aggregate count:

| quality-block accounting slot | direct itemization status | evidence path | interpretation |
|---|---|---|---|
| QB-1 | directly itemized | `campaign/campaign_summary.json.steps[3]`, SQLite scheduler row 18, `campaign/agentic_sessions/1b8d18d9-59c5-4428-a496-091a78b93bb2/output.json`, `.../scratch/code_retry_failure_detail_0001.json` | attempt 4 proposal/code block, telemetry identity mismatch |
| QB-2 | not directly itemized as its own campaign step; inferred from repair failure inside same blocked session | `campaign/agentic_sessions/1b8d18d9-59c5-4428-a496-091a78b93bb2/output.json`, two code traces in trace index, final `failure_category=model_repair_failed` | attempt 4 model repair also failed; evidence sufficient for failure, insufficient for an independent first-class quality-block row |
| QB-3 | directly itemized | `campaign/campaign_summary.json.steps[5]`, SQLite scheduler row 25, `campaign/agentic_sessions/48c73d42-dec0-4329-a9eb-3da692441980/output.json`, `.../scratch/code_retry_failure_detail_0001.json` | attempt 6 proposal/code block, telemetry identity mismatch |
| QB-4 | not directly itemized as its own campaign step; inferred from repair failure inside same blocked session | `campaign/agentic_sessions/48c73d42-dec0-4329-a9eb-3da692441980/output.json`, two code traces in trace index, final `failure_category=model_repair_failed` | attempt 6 model repair also failed; evidence sufficient for failure, insufficient for an independent first-class quality-block row |

So: two quality blocks are directly itemized as `proposal_block` attempts. The other two are not directly itemized as separate rows; they are reconstructed from the two failed code sessions each having an initial code self-check failure, one code repair attempt, and final `model_repair_failed`. Evidence insufficient to prove the aggregate counter's exact internal increment rule beyond this reconstruction.

### QB-1: Attempt 4 Initial Code Self-Check Block

| Field | Evidence |
|---|---|
| trigger stage | code-stage draft patch / agentic code self-check |
| attempt / session | attempt 4, session `1b8d18d9-59c5-4428-a496-091a78b93bb2` |
| trace | `campaign/llm_traces/20260607T065742500970_code_db3e914a05_bee3555a.json` |
| target | `policies/baseline_modules/scheduler.py` |
| declared/protected mechanism | `route_limit_repair_bias` |
| offending output | generated `new_string` contains repeated `self.context.record_move("alns", attempted=1, accepted=0)` while adding `_route_limit_repair_bias(...)` |
| block artifact | `campaign/agentic_sessions/1b8d18d9-59c5-4428-a496-091a78b93bb2/scratch/code_retry_failure_detail_0001.json` |
| reason | `code_stage_telemetry_identity_mismatch`: generated telemetry for undeclared mechanism `alns` |

Why Scion blocked it: the patch was for the protected mechanism `route_limit_repair_bias`, but new/increased generated telemetry would attribute mechanism evidence to `alns`. This would corrupt downstream mechanism evidence and DecisionFeatures attribution.

Reasonableness: reasonable. Blocking is aligned with the v3 rule that LLM output is tainted and deterministic evidence attribution must remain controlled. Possible false positive risk is low for the gate itself; baseline `alns` telemetry may exist, but the failure text explicitly allows unchanged baseline telemetry and rejects only new or increased generated mechanism evidence.

### QB-2: Attempt 4 Repair Code Self-Check Block

| Field | Evidence |
|---|---|
| trigger stage | code-stage model repair / second generated patch |
| attempt / session | attempt 4, session `1b8d18d9-59c5-4428-a496-091a78b93bb2` |
| trace | `campaign/llm_traces/20260607T065832245630_code_acb7bad299_e5e44833.json` |
| output artifact | `campaign/agentic_sessions/1b8d18d9-59c5-4428-a496-091a78b93bb2/output.json` |
| failure category | `model_repair_failed` |
| final failure | same telemetry identity mismatch; final output reports offending generated telemetry in `scheduler.py` around generated line 178 |
| schema retry | `schema_retry_feedback_count=0`; this was not a proposal/schema JSON repair |

Why Scion blocked it: the repair failed to remove the identity mismatch. Because the repaired patch still introduced/increased `alns` mechanism telemetry, the session terminated before Contract, Verification, Protocol, or Decision.

Reasonableness: reasonable. The model had explicit repair guidance in the failure detail: replace with approved protected mechanism id or remove the new mechanism-evidence call. It did not do so. Possible false positive risk remains low; the stronger risk is framework guidance/repair weakness because the model repeated a predictable nearby-telemetry copying error.

### QB-3: Attempt 6 Initial Code Self-Check Block

| Field | Evidence |
|---|---|
| trigger stage | code-stage draft patch / agentic code self-check |
| attempt / session | attempt 6, session `48c73d42-dec0-4329-a9eb-3da692441980` |
| trace | `campaign/llm_traces/20260607T070840778971_code_d9c9e45fc9_bdf9ffb0.json` |
| target | `policies/baseline_modules/scheduler.py` |
| declared/protected mechanism | `route_limit_repair_bias` |
| offending output | generated `new_string` contains multiple `self.context.record_move("alns", attempted=1, accepted=0)` calls while modifying route-limit repair bias scheduling |
| block artifact | `campaign/agentic_sessions/48c73d42-dec0-4329-a9eb-3da692441980/scratch/code_retry_failure_detail_0001.json` |
| reason | `code_stage_telemetry_identity_mismatch`; artifact records generated `record_move("alns"...` at normalized lines 166 and 194 |

Why Scion blocked it: same as QB-1. The approved hypothesis mechanism was `route_limit_repair_bias`; the generated patch created evidence under `alns`.

Reasonableness: reasonable. There is also a non-blocking novelty warning in `campaign_summary.steps[5].proposal_session_ref.novelty_warnings`: `duplicate_risk` for `route_limit_repair_bias`, `blocking=false`, `quality_block=false`. The actual block was not novelty; it was telemetry identity.

### QB-4: Attempt 6 Repair Code Self-Check Block

| Field | Evidence |
|---|---|
| trigger stage | code-stage model repair / second generated patch |
| attempt / session | attempt 6, session `48c73d42-dec0-4329-a9eb-3da692441980` |
| trace | `campaign/llm_traces/20260607T070940050188_code_9195abe588_0ea35638.json` |
| output artifact | `campaign/agentic_sessions/48c73d42-dec0-4329-a9eb-3da692441980/output.json` |
| failure category | `model_repair_failed` |
| final failure | final output reports generated `record_move("alns", attempted=1, accepted=0)` around lines 173, 180, 186 and another `record_move(` around line 212 |
| schema retry | `schema_retry_feedback_count=0`; this was not a proposal/schema JSON repair |

Why Scion blocked it: the second generated patch still failed the same mechanism identity rule.

Reasonableness: reasonable, but this is the second repeated failure on the same branch/mechanism. It shows a repair-path problem: the framework correctly detects the issue, but the repair instruction was not strong enough to stop repeated `alns` copying from scheduler context.

Potential false-positive impact on valid research: the gate may have blocked potentially interesting route-limit scheduling research, but the blocked artifacts cannot be treated as valid research evidence because their telemetry identity would make audit and branch-memory attribution unreliable. The likely missed opportunity is not an over-strict gate; it is inadequate targeted repair guidance for a repairable patch.

## 6. Retry / Follow-up Ledger

Retry/follow-up categories observed:

| event | from attempt | to attempt | category | evidence | interpretation |
|---|---:|---:|---|---|---|
| protocol follow-up | 2 | 3 | protocol after `continue_explore` | SQLite scheduler row 10: `decision=continue_explore`, `counts_toward_max_rounds=true`; row 15 later samples same branch with `same_branch_low_signal_observation_sample` | Not a quality-block retry; it is protocol-driven continuation/follow-up after tie-dominated screening |
| code-stage repair retry | 4 initial -> 4 repair | same attempt/session | model repair inside code session | session `1b8d18d9...` has two `code` traces and `code_retry_failure_count=1` | Initial patch failed telemetry identity; model repair attempted; repaired patch failed |
| proposal-block follow-up | 4 | 5 | retry after proposal/code quality block | scheduler row 18 `attempt_kind=proposal_block`; row 22 `screening`, same hyp `fc971dda...`, `scheduler_reason=pending_retry_diagnostic_followup`, `counts_toward_max_rounds=false` | Fresh code session `295e2bc5...` retried same hypothesis line and screened, but was non-effective/formal-excluded in reconciled accounting |
| protocol diagnostic follow-up | 5 | 6 | protocol after `continue_explore` | row 22 result `CONTINUE_EXPLORE`; row 25 proposal block has `scheduler_reason=effect_diagnostic_followup` | Not schema/proposal JSON repair; it is same-branch diagnostic continuation after weak/tie screening |
| code-stage repair retry | 6 initial -> 6 repair | same attempt/session | model repair inside code session | session `48c73d42...` has two `code` traces and `code_retry_failure_count=1` | Initial patch failed telemetry identity; model repair attempted; repaired patch failed |
| proposal-block follow-up | 6 | 7 | retry after proposal/code quality block | scheduler row 25 `attempt_kind=proposal_block`; row 29 `screening`, same hyp `b5d6037c...`, `scheduler_reason=pending_retry_diagnostic_followup`, `counts_toward_max_rounds=false` | Fresh code session `2d0469e6...` retried same hypothesis line and screened, but was non-effective/formal-excluded |
| protocol lifecycle follow-up | 7 | no same-branch next attempt | protocol after `continue_explore` plus lifecycle park | scheduler row 29 result says `park_lineage`; branch `f5f5cbcd...` state `parked_lineage` | Not a retry consumed later in this 4R run; branch was parked and later run moved to clean fork/new branch |
| protocol follow-up at end | 8 | no next attempt | protocol after `continue_explore` | scheduler row 34 `continue_explore`, final stop `max_rounds_exhausted` | Not a retry in this run; final branch remains active marginal |

No evidence found for proposal/schema JSON quality-block retries: both failed sessions have `schema_retry_feedback_count=0`, and their failure category is `model_repair_failed` from code self-check. The concrete retries are code-stage repair attempts and same-branch diagnostic follow-ups after protocol/quality-block outcomes.

## 7. Conclusions

1. `proposal_attempts_total=8` versus `effective_rounds_completed=4` is consistent with Scion accounting if `campaign/status.json` and SQLite scheduler audit rows are treated as authoritative. Attempts 1, 2, 3, and 8 count toward max rounds. Attempts 4 and 6 are pre-protocol proposal/code blocks. Attempts 5 and 7 screened but are repair-diagnostic follow-ups with `counts_toward_max_rounds=false`.

2. The four quality blocks do not indicate that the quality gate is semantically overblocking valid research. They indicate two repeated code-stage telemetry identity failures, each with one failed repair. The gate is appropriate because mechanism evidence under `alns` would be wrong for `route_limit_repair_bias`.

3. The framework control plane does show operational overhead: 94 tool-selection LLM calls versus 6 hypothesis calls and 10 code calls, plus repeated code repair failures on the same predictable telemetry mistake. This is control-plane cost/repair friction, not proof that deterministic gates are conceptually too strict.

4. Telemetry identity mismatch needs P1 treatment for the repair path. The blocking rule is correct, but repeated failures on `scheduler.py` suggest the code prompt or repair prompt should make allowed telemetry identities more explicit, possibly with a structured diff lint and targeted rewrite instruction before re-querying the model.

5. Evidence gaps:
   - `campaign_summary.steps[].screened_experiment_effective=true` conflicts with SQLite scheduler rows and reconciled status for attempts 5 and 7.
   - `quality_blocks=4` is aggregate accounting; there is no standalone first-class quality-block ledger with four rows keyed by attempt/session/trace/rule. The four-block explanation above is reconstructed from two failed sessions with two code traces each.
   - The trace index records LLM tool-selection calls, while actual tool execution lives in transcripts. A future audit would be easier with a normalized joined table: `session_id`, `trace_id`, selected tool, executed tool observation id, status, and artifact ref.
   - The failed code self-check artifacts point to normalized/generated line numbers, not stable source file line numbers in a retained patch, because the patch was blocked before retention.
