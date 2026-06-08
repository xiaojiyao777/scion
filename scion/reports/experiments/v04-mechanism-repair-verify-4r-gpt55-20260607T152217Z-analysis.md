# Scion v0.4 4R run 后验分析

Run root: `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw`

报告时间: 2026-06-07

## 1. Run verdict

| 问题 | 结论 | 关键证据 |
|---|---|---|
| 是否 valid 4R | 否 | `campaign/run_status.json` 与 run root `run_status.json` 均为 `run_validity_status=invalid_no_effective_rounds`、`run_completeness_status=interrupted_incomplete`、`completed_requested_rounds=false`、`last_stop_reason=circuit_breaker`。 |
| 是否完成 requested rounds | 否 | 命令请求 `--rounds 4`；`campaign/status.json.accounting_reconciliation.requested_rounds=4`，但 `effective_rounds_completed=0`、`total_rounds=3`。 |
| 是否有 formal screened candidates | 否 | `formal_screened_candidates=0`，`protocol_stage_counts.screening=0`、`validation=0`、`frozen=0`。 |
| 是否可用于判断算法研究质量 | 否 | 没有 hypothesis、没有 patch、没有 code 实现、没有 Contract/Verification/Protocol 结果，所有失败都发生在 proposal LLM API 调用阶段。 |
| 主要失败类型 | 实验环境 / LLM client / proxy 配置缺陷 | 所有 6 个 LLM trace 都返回 `API error: Error code: 401 ... Invalid proxy API key`；`command.txt`/`launch.env` 显示 `SCION_BASE_URL=http://127.0.0.1:8080`、`SCION_MODEL=gpt-5.5`。 |

最终判断: 这次失败不是 Scion 算法研究能力的负证据，也不是候选机制质量的负证据。它主要是 LLM client/proxy 配置失效导致 proposal 层无法产生任何 hypothesis。框架大体正确地把这些 proposal failures 排除在 max_rounds/effective rounds 之外，并触发 circuit breaker；但 failure category 被记录成 `contract_boundary_failure` 有误导性，应更精确地区分为 LLM provider/auth/config failure。

## 2. Run 输入与顶层状态

| 项 | 值 |
|---|---|
| command | `/home/clawd/miniconda3/envs/claw/bin/python -m scion.cli.main run --problem scion/problems/cvrp/problem.yaml --protocol scion/problems/cvrp/formal/protocol.yaml --split scion/problems/cvrp/formal/split_manifest.yaml --seeds scion/problems/cvrp/formal/seed_ledger.yaml --campaign-dir .../campaign --rounds 4 --time-limit-sec 10 --agentic-session-timeout-sec 900 --disable-early-stop --agentic-proposal` |
| model / base URL | `SCION_MODEL=gpt-5.5`，`SCION_BASE_URL=http://127.0.0.1:8080`，见 `command.txt` 与 `launch.env` |
| run wrapper | `WRAPPER_EXIT_STATUS:0`，但 `CAMPAIGN_EXIT_STATUS:incomplete`，见 run root `exit.txt` 与 `campaign/exit.txt` |
| started / ended | `2026-06-07T15:22:19Z` 到 `2026-06-07T15:24:22Z`，见 `campaign/run_status.json` |
| campaign id | `271c4f72-7b5a-4447-b3e4-7454d9a3ef6a` |
| branch id | `525d63a1-1a3c-460b-8b6d-83173bc006b1` |
| champion | `champion_version=1`，`champion_weight_revision=0` |
| stop reason | `campaign_summary.json.stopped_reason=circuit_breaker`，`circuit_breaker_tripped=true` |

日志文件 `run.log` 明确记录三次:

`Branch 525d63a1-1a3c-460b-8b6d-83173bc006b1: agentic proposal session failed: agentic_proposal:hypothesis_generation_failed: Tool call failed after 3 attempt(s). Last error: API error: Error code: 401 ... Invalid proxy API key`

随后:

`Circuit breaker tripped after 3 consecutive LLM failures; stopping campaign.`

## 3. 逐轮次 / attempt 表

说明: 本 run 没有进入 effective screening round。下表的 `loop_step/round` 是 framework 记录的 proposal attempt / campaign step，不是有效 screened round。

| loop_step / round | branch_id | agentic session | LLM trace 文件 | 调用类型 | 模型 | 输入上下文是否包含必要信息 | LLM 输出假设 | 进入 code | 进入 protocol | framework 记录 |
|---:|---|---|---|---|---|---|---|---|---|---|
| 1 | `525d63a1-1a3c-460b-8b6d-83173bc006b1` | `29747e7a-1d9e-44b5-bdc2-94668109eace` | `llm_traces/20260607T152219574722_hypothesis_target_intent_7fc7f2ddaf_fbc20897.json`; `llm_traces/20260607T152241047749_hypothesis_18024391ee_e8b867a2.json` | `hypothesis_target_intent` then `hypothesis` | `gpt-5.5` | 是。manifest 含 problem summary、research surfaces、objective policy、champion code、active facts、active solver map receipts、full reads of `destroy_repair.py`/`local_search.py`/`scheduler.py`、tool observations；0 omitted / 0 truncated。 | 无。`hypothesis=null`，`selected_surface=null`，`target_file=null`。 | 否 | 否 | `attempt_kind=proposal_block`，`failure_stage=proposal`，`counts_toward_max_rounds=false`，`scheduler_slot=explore_new`，`scheduler_reason=new_exploration_slot_available`。 |
| 2 | `525d63a1-1a3c-460b-8b6d-83173bc006b1` | `09c9feb8-fb05-4f7d-ba1c-d66aeac57b03` | `llm_traces/20260607T152301883451_hypothesis_target_intent_40c6784b4b_47bfe1c7.json`; `llm_traces/20260607T152322016298_hypothesis_d60969f528_708a3ecf.json` | `hypothesis_target_intent` then `hypothesis` | `gpt-5.5` | 是。repair profile 额外包含 `agentic_resume_context`、`agent_quality_feedback`、failure warning；prompt manifest 仍为 0 omitted / 0 truncated。 | 无。`hypothesis=null`，`patch=null`。 | 否 | 否 | `attempt_kind=proposal_block`，`failure_stage=proposal`，`counts_toward_max_rounds=false`，`scheduler_slot=repair_diagnostic`，`scheduler_reason=pending_retry_diagnostic_followup`。 |
| 3 | `525d63a1-1a3c-460b-8b6d-83173bc006b1` | `a8968fd0-b8a4-43f9-96cc-f7e9e3100f64` | `llm_traces/20260607T152342465801_hypothesis_target_intent_0b8017b1db_e3b79f6f.json`; `llm_traces/20260607T152402604111_hypothesis_23a72f84f5_44fc4f9d.json` | `hypothesis_target_intent` then `hypothesis` | `gpt-5.5` | 是。repair profile；`api_visible_prompt_manifest_0002_hypothesis.json` 有 31 sections、111460 chars、0 omitted、0 truncated。 | 无。`hypothesis=null`，`self_check.schema_valid=false`。 | 否 | 否 | 第 3 个 `quality_block_ledger` 条目；随后 circuit breaker。 |
| requested round 4 | 同上 | 未创建 | 无 | 无 | 无 | 未执行 | 无 | 否 | 否 | 未执行，因为三次 consecutive LLM failures 触发 circuit breaker。 |

`campaign/status.json.accounting_reconciliation` 还记录:

- `max_rounds_budget_counter=effective_rounds_completed`
- `max_rounds_semantics=requested_rounds limits effective_rounds_completed; proposal, repair, lifecycle, and active-slot scheduler attempts are reported separately`
- `quality_blocks=3`
- `formal_screened_candidates=0`
- `protocol_evaluated_candidates=0`

这说明 proposal block 没有消耗 requested effective rounds，符合 v3 边界。

## 4. 每个 agentic session 行为

三次 session 的 deterministic prefetch 基本一致。每次都先完成 12 个 proposal tool observations，全部 `status=ok`:

| step | tool | 结果摘要 | 作用 |
|---:|---|---|---|
| tool-0001 | `context.list_surfaces` | `Returned 1 declared research surface(s).` | 发现 research surface。 |
| tool-0002 | `context.read_problem` | `Returned adapter/spec-rendered problem summary.` | 提供 problem/spec 摘要。 |
| tool-0003 | `context.list_algorithm_files` | `Returned allowlisted solver_design algorithm files.` | 提供 solver_design 文件列表。 |
| tool-0004 | `context.read_active_solver_design` | `Returned active solver_design snapshot with entrypoint, call graph, mechanisms, provenance, and legacy exclusions.` | 提供 active algorithm snapshot。 |
| tool-0005 | `context.read_solver_call_graph` | `Returned active solver_design call graph with provenance.` | 提供调用图。 |
| tool-0006 | `context.read_active_solver_map` | `Returned provider-declared active solver map with read receipt.` | 建立 active facts anchor。 |
| tool-0007 | `context.read_algorithm_file` | `Returned allowlisted solver_design file policies/baseline_modules/destroy_repair.py.` | 完整读取算法文件。 |
| tool-0008 | `context.read_algorithm_file` | `Returned allowlisted solver_design file policies/baseline_modules/local_search.py.` | 完整读取算法文件。 |
| tool-0009 | `context.read_algorithm_file` | `Returned allowlisted solver_design file policies/baseline_modules/scheduler.py.` | 完整读取算法文件。 |
| tool-0010 | `context.read_operator_registry` | `Returned provider-declared operator registry with read receipt.` | active solver map follow-up。 |
| tool-0011 | `context.read_algorithm_slice` | `Returned provider-declared algorithm slice with read receipt.` | scheduler solve slice。 |
| tool-0012 | `memory.query` | `Returned tainted proposal/search memory safe view.` | branch-local tainted feedback/memory。 |

各 session 的 `tool_budget_used`:

| session | context_profile | tool_calls | tool_steps | observation_chars | status | termination_reason |
|---|---|---:|---:|---:|---|---|
| `29747e7a-1d9e-44b5-bdc2-94668109eace` | `algorithm` | 12 | 12 | 124270 | `failed` | `hypothesis_generation_failed` |
| `09c9feb8-fb05-4f7d-ba1c-d66aeac57b03` | `repair` | 12 | 12 | 124424 | `failed` | `hypothesis_generation_failed` |
| `a8968fd0-b8a4-43f9-96cc-f7e9e3100f64` | `repair` | 12 | 12 | 124424 | `failed` | `hypothesis_generation_failed` |

各 session 的 active facts anchor 相同:

- `fact_packet_digest=2cfe98de174b5f615c07da173aa7843631621ccc807a46d0c47bdba320a8f531`
- `snapshot_digest=703914d3edaf27a46f3adb7d419a6dcd5cc7154ae6fd01c66ae8e50cf9842761`
- `source_tool_name=context.read_active_solver_map`
- fact ids 包括 `cvrp.construction.diverse_feasible_seed`、`cvrp.destroy_repair.shaw_related_removal`、`cvrp.local_search.vns_operator_registry`、`cvrp.local_search.cross_route_tail_exchange` 等 15 个 CVRP adapter-owned facts。

这符合 onboarding 中的 active-facts anchor 要求: proposal agent 与后续 gates 应共享 adapter-owned fact packet，而不是由 generic core 合成 CVRP 事实。这里 CVRP-specific 信息作为 problem/provider context 暴露给 proposal，未作为 core 设计原则。

## 5. 每一次 LLM 调用逐个分析

所有 trace 都有相同错误形态:

- `ok=false`
- `model=gpt-5.5`
- `provider=openai_compatible`
- `error=Tool call failed after 3 attempt(s). Last error: API error: Error code: 401 ... Invalid proxy API key`
- `llm_retry_summary.event_count=2`
- `request_policy.max_retries=2`
- `request_policy.sdk_max_retries=0`
- `llm_retry_events` 只记录前两次失败与重试；第三次最终失败体现在 trace 顶层 `error`。

| # | trace 文件 | session | call / tool | prompt/context | 输出是否合理 | 工具调用 / 工具结果 | 失败点 |
|---:|---|---|---|---|---|---|---|
| 1 | `campaign/llm_traces/20260607T152219574722_hypothesis_target_intent_7fc7f2ddaf_fbc20897.json` | `29747e7a-...` | `hypothesis_target_intent` / `select_hypothesis_target_intent` | `api_visible_prompt_manifest_0001_hypothesis_target_intent.json`: 19 sections、95466 chars、0 omitted、0 truncated；含 active facts、active solver map receipts、full algorithm file reads、tool observations。 | 没有模型输出，不能评价 hypothesis intent 质量。 | LLM 调用前已有 12 个 deterministic proposal tool observations，均 `ok`。 | API auth: 401 invalid proxy key；target-intent preflight failed，框架 fallback 到 hypothesis flow。 |
| 2 | `campaign/llm_traces/20260607T152241047749_hypothesis_18024391ee_e8b867a2.json` | `29747e7a-...` | `hypothesis` / `generate_hypothesis` | `api_visible_prompt_manifest_0002_hypothesis.json`: 22 sections、104368 chars、0 omitted、0 truncated；含 `solver_design_boundary_control`、analysis steps、task。 | 没有模型输出；`output.json.hypothesis=null`。 | 无 LLM tool result；pre-LLM context tools已成功。 | 401 invalid proxy key；session finalize 为 `hypothesis_generation_failed`。 |
| 3 | `campaign/llm_traces/20260607T152301883451_hypothesis_target_intent_40c6784b4b_47bfe1c7.json` | `09c9feb8-...` | `hypothesis_target_intent` / `select_hypothesis_target_intent` | repair profile manifest: 20 sections、99154 chars、0 omitted、0 truncated；新增 `agentic_resume_context`。 | 没有模型输出。 | 12 个 prefetch tools 全部 `ok`；observation ledger 记录 active fact anchor。 | 401 invalid proxy key；target-intent preflight failed 后 fallback。 |
| 4 | `campaign/llm_traces/20260607T152322016298_hypothesis_d60969f528_708a3ecf.json` | `09c9feb8-...` | `hypothesis` / `generate_hypothesis` | repair profile manifest: 29 sections、109509 chars、0 omitted、0 truncated；含 `agent_quality_feedback`、failure warning、experiment history。 | 没有模型输出；`selected_surface=null`、`target_file=null`。 | 无 LLM tool result；pre-LLM tools已成功。 | 401 invalid proxy key；session `failure_category=structured_output_retry_exhausted`。 |
| 5 | `campaign/llm_traces/20260607T152342465801_hypothesis_target_intent_0b8017b1db_e3b79f6f.json` | `a8968fd0-...` | `hypothesis_target_intent` / `select_hypothesis_target_intent` | repair profile manifest: 20 sections、100333 chars、0 omitted、0 truncated；experiment history 增长到 1151 chars。 | 没有模型输出。 | 12 个 prefetch tools 全部 `ok`。 | 401 invalid proxy key；target-intent preflight failed 后 fallback。 |
| 6 | `campaign/llm_traces/20260607T152402604111_hypothesis_23a72f84f5_44fc4f9d.json` | `a8968fd0-...` | `hypothesis` / `generate_hypothesis` | repair profile manifest: 31 sections、111460 chars、0 omitted、0 truncated；含 `failure_pattern_warning`、`agent_quality_feedback`、完整 task。 | 没有模型输出；`self_check.schema_valid=false` 是缺少 structured hypothesis 的后果。 | 无 LLM tool result；pre-LLM tools已成功。 | 401 invalid proxy key；第三个 consecutive LLM failure 触发 circuit breaker。 |

结论: prompt/context 本身从 manifest 看是完整且合理的，至少包含 v3 所要求的 problem spec 摘要、champion/current algorithm context、branch/history feedback、active facts anchor 和 allowed solver_design source context。失败发生在外部 LLM API 调用授权阶段，早于任何模型推理或 structured output 解析。

## 6. 为什么没有 code 实现 / 没有实验结果

没有 code 实现的直接原因:

- Proposal phase 未产生 `HypothesisProposal`。
- 三个 `agentic_sessions/*/output.json` 均为 `hypothesis=null`、`patch=null`、`selected_surface=null`、`target_file=null`。
- `self_check.schema_valid=false`，但不是模型输出格式差，而是根本没有可解析输出。
- `agentic_session_trace_index.json` 中三次 session 的 `code_trace_ids=[]`。

没有实验结果的直接原因:

- DB `experiment_events` 中 proposal session 事件均为 `contract_result=not_run` 或 proposal_fail `contract_result=skipped`、`verification_result=skipped`、`canary_result=skipped`。
- `campaign/status.json.accounting_reconciliation.protocol_stage_counts` 为 `screening=0`、`validation=0`、`frozen=0`。
- `campaign_summary.json.screened_experiments=0`、`effective_rounds_completed=0`、`telemetry_failed_experiments=0`。

因此不能把“没有提升”解释为算法失败；候选根本没有存在过。

## 7. Framework 行为是否符合设计

### 7.1 Proposal block 不计入 max_rounds

符合。`campaign/status.json.accounting_reconciliation` 明确记录:

- `max_rounds_budget_counter=effective_rounds_completed`
- `max_rounds_semantics=requested_rounds limits effective_rounds_completed; proposal, repair, lifecycle, and active-slot scheduler attempts are reported separately`
- 三个 `quality_block_ledger` 条目均为 `counts_toward_max_rounds=false`
- `effective_rounds_completed=0`

这符合 v3: LLM proposal 是 tainted creative layer，未通过 Contract/Verification/Protocol 前不能成为 DecisionFeatures，也不应被当作 formal screened round。

### 7.2 Quality block 记录

部分符合。符合点:

- 三个 pre-protocol proposal failures 都进入 `quality_block_ledger`。
- 每条都有 `attempt_kind=proposal_block`、`failure_stage=proposal`、`pre_protocol=true`、`hypothesis_id=null`。
- DB `branches.failure_codes=["PROPOSAL","PROPOSAL","PROPOSAL"]`，branch 仍为 `state=explore`、`branch_code_status=clean`。

问题点:

- `quality_block_ledger.failure_category=contract_boundary_failure` 不够准确。
- `campaign_summary.steps[].secondary_observations[].category=contract_boundary_failure`，但实际 root cause 是 LLM provider auth 401，不是 proposal 内容越界、schema 越界、文件白名单越界或 Contract gate 失败。
- 更好的分类应类似 `llm_provider_auth_failure` / `llm_client_config_failure` / `infrastructure_llm_auth_failure`，并保留 `proposal_block` 作为 lifecycle/attempt 类型。

### 7.3 Circuit breaker

合理。`run.log` 与 `campaign_summary.json` 共同显示连续三次 LLM failure 后停止:

- `circuit_breaker_tripped=true`
- `stopped_reason=circuit_breaker`
- wrapper `last_stop_reason=circuit_breaker`

因为错误是稳定的 401 配置错误，继续尝试第 4 个 requested round 只会浪费预算；circuit breaker 停止是合理的。

### 7.4 run_validity 是否准确

准确。`invalid_no_effective_rounds` 是正确结论。虽然 wrapper exit code 是 0，但 campaign exit status 是 incomplete，run validity 已明确标 invalid，没有把“命令正常返回”误判成有效 4R。

### 7.5 Decision 边界

符合。没有任何 protocol result，也没有 DecisionFeatures。DB `experiment_events.decision_features_json` 对 proposal/session 事件为空字符串或 null；proposal visibility 记录为 `proposal_visibility_only=true`、`decision_features_excluded=true`。这符合“Decision 只读 DecisionFeatures，不读 LLM 自由文本”的设计边界。

## 8. 这次失败的归因

| 候选根因 | 判断 | 证据 |
|---|---|---|
| Scion 算法研究缺陷 | 否，无法支持 | 没有 hypothesis、没有 patch、没有 screening/validation/frozen 结果；模型没有完成任何算法设计输出。 |
| Framework 机制缺陷 | 次要 | 框架正确做了 prefetch、prompt manifest、proposal block 记账、max_rounds 排除、circuit breaker、run_validity 标 invalid；主要问题是 failure category 把 provider 401 包进 `contract_boundary_failure`，分类不精确。 |
| 实验环境 / LLM client / proxy 配置缺陷 | 是，主因 | 所有 trace 都是 `API error: Error code: 401 ... Invalid proxy API key`；环境使用 `SCION_BASE_URL=http://127.0.0.1:8080` 与 `SCION_MODEL=gpt-5.5`；失败发生在 OpenAI-compatible provider auth 阶段。 |

更具体地说，本 run 验证了 framework 的“失败后可审计”能力，而没有验证算法研究能力。它可以作为 LLM/proxy 故障处理和 accounting/reporting 的测试样本，不能作为 solver-quality 或 research-quality 样本。

## 9. 是否可以开始更长轮次实验

不建议开始更长轮次实验。按本 run 的证据，先决条件至少包括:

1. 修复并验证 `SCION_BASE_URL=http://127.0.0.1:8080` 对 `SCION_MODEL=gpt-5.5` 的 API key/proxy 认证配置。要求单次 `hypothesis_target_intent` 与 `generate_hypothesis` LLM trace 至少返回 `ok=true` 或可解析的 provider response。
2. 先重跑同配置的 4R 或更短 smoke run，要求 `formal_screened_candidates > 0` 或至少有一个 candidate 进入 Contract/Verification/Protocol。否则仍无法判断算法质量。
3. 修正或至少在报告层标注 failure category: provider 401 不应主要呈现为 `contract_boundary_failure`，否则后续实验汇总会误导为 proposal/contract 质量问题。
4. 若要评估 framework 机制，应补充断言: repeated provider auth failure 应进入 infra/config 类 failure，并可触发 circuit breaker；不应污染 agent-quality block 的算法质量解释。
5. 在重跑前确认 `campaign_summary.json`、`campaign/status.json`、DB `experiment_events` 对 proposal attempts 的计数一致性。目前 `campaign_summary.proposal_attempts=3`，但 `status.json.accounting_reconciliation.attempt_breakdown.proposal_attempts_total=4`，需要确认这个 4 是否包含非-session campaign step，避免后续报告误读。

在这些条件满足前，扩大到更长轮次只会放大同一个配置问题，不能产生有效研究证据。

## 10. 文件引用清单

主要证据文件:

- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/command.txt`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/launch.env`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/run.log`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/run_status.json`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/status.json`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/campaign_summary.json`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/scion.db`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/agentic_sessions/agentic_session_index.json`
- `/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw/campaign/agentic_sessions/agentic_session_trace_index.json`

Session artifacts:

- `campaign/agentic_sessions/29747e7a-1d9e-44b5-bdc2-94668109eace/output.json`
- `campaign/agentic_sessions/29747e7a-1d9e-44b5-bdc2-94668109eace/transcript.json`
- `campaign/agentic_sessions/09c9feb8-fb05-4f7d-ba1c-d66aeac57b03/output.json`
- `campaign/agentic_sessions/09c9feb8-fb05-4f7d-ba1c-d66aeac57b03/transcript.json`
- `campaign/agentic_sessions/a8968fd0-b8a4-43f9-96cc-f7e9e3100f64/output.json`
- `campaign/agentic_sessions/a8968fd0-b8a4-43f9-96cc-f7e9e3100f64/transcript.json`

LLM traces:

- `campaign/llm_traces/20260607T152219574722_hypothesis_target_intent_7fc7f2ddaf_fbc20897.json`
- `campaign/llm_traces/20260607T152241047749_hypothesis_18024391ee_e8b867a2.json`
- `campaign/llm_traces/20260607T152301883451_hypothesis_target_intent_40c6784b4b_47bfe1c7.json`
- `campaign/llm_traces/20260607T152322016298_hypothesis_d60969f528_708a3ecf.json`
- `campaign/llm_traces/20260607T152342465801_hypothesis_target_intent_0b8017b1db_e3b79f6f.json`
- `campaign/llm_traces/20260607T152402604111_hypothesis_23a72f84f5_44fc4f9d.json`

设计边界参考:

- `/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/AGENT_ONBOARDING.md`
