# Scion v0.4 4R Run Tooling/Auth/Context Audit

审计对象：
`/home/clawd/research/scion-experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-claw`

输出报告：
`/home/clawd/research/or-autoresearch-agent/scion/reports/experiments/v04-mechanism-repair-verify-4r-gpt55-20260607T152217Z-tooling-auth-audit.md`

## 结论

本 run 不是一次可用于评价机制修复、context/tooling 修复或 proposal 质量的 4R validation。它在 proposal 层连续 3 个 agentic session 因 OpenAI-compatible provider/proxy 认证失败中断：

- `campaign/run_status.json`: `run_validity_status=invalid_no_effective_rounds`, `last_stop_reason=circuit_breaker`, `run_complete=false`。
- `campaign/status.json`: `requested_rounds=4`, `proposal_attempts_total=4`, `proposal_attempts_consumed=3`, `formal_screened_candidates=0`, `quality_blocks=3`。
- `campaign/campaign_summary.json`: `effective_rounds_completed=0`, `screened_experiments=0`, `run_validity.reason=invalid_no_effective_rounds`。
- `run.log`: 3 次 `agentic proposal session failed` 后 `Circuit breaker tripped after 3 consecutive LLM failures`。

根因判断：这是环境变量 / 本机 proxy API key / client 调用路径不一致导致的 provider auth failure，不是 recent context/tooling 修复本身造成的上下文缺失，也不是候选机制质量失败。当前代码把 `401 Invalid proxy API key` 归为普通 `LLMError`，最终被 session self-check 路径记成 `contract_boundary_failure`/quality block；这是会计分类误导。

## Launch/Auth Evidence

`launch.env` 记录：

- `SCION_MODEL=gpt-5.5`
- `SCION_BASE_URL=http://127.0.0.1:8080`
- `SCION_SDK_MAX_RETRIES=0`
- `SCION_LLM_MAX_RETRIES=2`
- 未记录/未设置 `SCION_API_KEY`
- 未记录/未设置 `ANTHROPIC_AUTH_TOKEN`
- 未记录/未设置 `ANTHROPIC_API_KEY`
- 未记录/未设置 `OPENAI_API_KEY`

`run.sh` 只显式导出：

```bash
export PYTHONPATH SCION_MODEL SCION_BASE_URL SCION_SDK_MAX_RETRIES SCION_LLM_MAX_RETRIES SCION_PROBLEM_DATA_ROOT
```

源码路径：

- `scion/scion/proposal/llm/client.py`: `LLMClient.__init__` 只从 constructor、`SCION_API_KEY`、`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_API_KEY` 取 `api_key`；不读取 `OPENAI_API_KEY`。
- `scion/scion/proposal/llm/config.py`: 非 `claude-` 模型走 OpenAI-compatible path；`gpt-5.5` 因此前往 OpenAI SDK。
- `scion/scion/proposal/llm/transport.py`: `_get_openai_client()` 把 `SCION_BASE_URL=http://127.0.0.1:8080` 归一化为 `http://127.0.0.1:8080/v1`，并以 `api_key=self.api_key` 初始化 `openai.OpenAI(...)`。
- 同文件 `_tool_call_once_openai()` 使用 `client.chat.completions.create(...)`，传 `tools=[...]` 和 required `tool_choice`。

因此，如果操作员以为 `OPENAI_API_KEY` 会被 Scion 使用，本 run 实际不会读它；如果外层 shell 继承了 `SCION_API_KEY` / Anthropic token，也可能是继承值无效。run artifacts 没有记录实际 key，不能判断是缺失还是错误值，但 proxy 返回明确为 `Invalid proxy API key`。

## Session/Trace Reconstruction

共有 3 个 agentic proposal session，均在 hypothesis 生成阶段失败；没有 code trace，没有正式 hypothesis row。

| session | context_profile | tool calls | observation chars | deterministic prefetch | final status |
|---|---:|---:|---:|---|---|
| `29747e7a-1d9e-44b5-bdc2-94668109eace` | `algorithm` | 12 | 124270 | `b2aadbee7fbd9a7d` | `failed`, `hypothesis_generation_failed` |
| `09c9feb8-fb05-4f7d-ba1c-d66aeac57b03` | `repair` | 12 | 124424 | `84b7ddf9231cabf3` | `failed`, `hypothesis_generation_failed` |
| `a8968fd0-b8a4-43f9-96cc-f7e9e3100f64` | `repair` | 12 | 124424 | `eeb46ee75c275f35` | `failed`, `hypothesis_generation_failed` |

每个 session 的 deterministic/local proposal tools 都成功：

1. `context.list_surfaces` from `required_context_preface`
2. `context.read_problem` from `required_context_preface`
3. `context.list_algorithm_files` from `required_context_preface`
4. `context.read_active_solver_design` from `required_context_preface`
5. `context.read_solver_call_graph` from `required_context_preface`
6. `context.read_active_solver_map` from `required_context_preface`
7. `context.read_algorithm_file` for `policies/baseline_modules/destroy_repair.py`
8. `context.read_algorithm_file` for `policies/baseline_modules/local_search.py`
9. `context.read_algorithm_file` for `policies/baseline_modules/scheduler.py`
10. `context.read_operator_registry` from `planner_map_followup_required`
11. `context.read_algorithm_slice` for `cvrp.slice.scheduler.solve`
12. `memory.query` from `deterministic_prefetch`

`transcript.json` 的 loop stop 为 `required_context_satisfied`，不是 tool loop failure。`tool_selection_ledger.entries[0].skipped=false`；`input_token_cost=null`，并注明 `unavailable_in_session; see linked llm_trace`。没有 `tool_selection` LLM trace，因为 required context 已满足，planner LLM 没有被调用。

### LLM trace 1

File: `campaign/llm_traces/20260607T152219574722_hypothesis_target_intent_7fc7f2ddaf_fbc20897.json`

- session: `29747e7a-1d9e-44b5-bdc2-94668109eace`
- model: `gpt-5.5`
- phase: `draft_hypothesis`
- request_kind: `hypothesis_target_intent`
- tool_name: `select_hypothesis_target_intent`
- request_policy: `timeout_sec=60.0`, `max_retries=2`, `transient_max_retries=1`, `sdk_max_retries=0`, `max_tokens=16384`
- prompt manifest: `api_visible_prompt_manifest_0001_hypothesis_target_intent.json`
- visibility ledger: `entry_count=31`, `full=19`, `dedicated_projection=4`, `summary=8`, `truncated=0`, `omitted=0`
- prompt/cache audit: `provider=openai_compatible`, `system_block_count=2`, `user_prompt_chars=23280`, `tool_schema_chars=1523`
- failure: after 3 attempts, `Error code: 401`, `Invalid proxy API key`
- retry ledger: two recorded retry events at attempts 1 and 2; third attempt is represented by final exhausted error.

### LLM trace 2

File: `campaign/llm_traces/20260607T152241047749_hypothesis_18024391ee_e8b867a2.json`

- session: `29747e7a-1d9e-44b5-bdc2-94668109eace`
- model: `gpt-5.5`
- phase: `draft_hypothesis`
- request_kind: `hypothesis`
- tool_name: `generate_hypothesis`
- prompt manifest: `api_visible_prompt_manifest_0002_hypothesis.json`
- visibility ledger: `entry_count=34`, `full=22`, `dedicated_projection=4`, `summary=8`, `truncated=0`, `omitted=0`
- prompt/cache audit: `provider=openai_compatible`, `user_prompt_chars=31145`
- failure: same 401 `Invalid proxy API key`

### LLM trace 3

File: `campaign/llm_traces/20260607T152301883451_hypothesis_target_intent_40c6784b4b_47bfe1c7.json`

- session: `09c9feb8-fb05-4f7d-ba1c-d66aeac57b03`
- context_profile: `repair`
- model: `gpt-5.5`
- request_kind: `hypothesis_target_intent`
- tool_name: `select_hypothesis_target_intent`
- prompt manifest: `api_visible_prompt_manifest_0001_hypothesis_target_intent.json`
- visibility ledger: `entry_count=32`, `full=20`, `dedicated_projection=4`, `summary=8`, `truncated=0`, `omitted=0`
- prompt/cache audit: `user_prompt_chars=26447`
- failure: same 401 `Invalid proxy API key`

### LLM trace 4

File: `campaign/llm_traces/20260607T152322016298_hypothesis_d60969f528_708a3ecf.json`

- session: `09c9feb8-fb05-4f7d-ba1c-d66aeac57b03`
- context_profile: `repair`
- model: `gpt-5.5`
- request_kind: `hypothesis`
- tool_name: `generate_hypothesis`
- prompt manifest: `api_visible_prompt_manifest_0002_hypothesis.json`
- visibility ledger: `entry_count=41`, `full=29`, `dedicated_projection=4`, `summary=8`, `truncated=0`, `omitted=0`
- prompt/cache audit: `user_prompt_chars=34831`
- failure: same 401 `Invalid proxy API key`

### LLM trace 5

File: `campaign/llm_traces/20260607T152342465801_hypothesis_target_intent_0b8017b1db_e3b79f6f.json`

- session: `a8968fd0-b8a4-43f9-96cc-f7e9e3100f64`
- context_profile: `repair`
- model: `gpt-5.5`
- request_kind: `hypothesis_target_intent`
- tool_name: `select_hypothesis_target_intent`
- prompt manifest: `api_visible_prompt_manifest_0001_hypothesis_target_intent.json`
- visibility ledger: `entry_count=32`, `full=20`, `dedicated_projection=4`, `summary=8`, `truncated=0`, `omitted=0`
- prompt/cache audit: `user_prompt_chars=26447`
- failure: same 401 `Invalid proxy API key`

### LLM trace 6

File: `campaign/llm_traces/20260607T152402604111_hypothesis_23a72f84f5_44fc4f9d.json`

- session: `a8968fd0-b8a4-43f9-96cc-f7e9e3100f64`
- context_profile: `repair`
- model: `gpt-5.5`
- request_kind: `hypothesis`
- tool_name: `generate_hypothesis`
- prompt manifest: `api_visible_prompt_manifest_0002_hypothesis.json`
- visibility ledger: `entry_count=43`, `full=31`, `dedicated_projection=4`, `summary=8`, `truncated=0`, `omitted=0`
- prompt/cache audit: `user_prompt_chars=35396`
- failure: same 401 `Invalid proxy API key`

## Why traces exist but tool-call stage reports 401

这里的 “tool call” 是 LLM structured tool call，不是 Scion proposal tool。链路是：

1. APS deterministic proposal tools 在本地执行，写入 `transcript.json`、`output.json`、prompt manifests；这些 tools 不需要 LLM provider API key。
2. Scion 记录 API-visible prompt manifest 和 LLM trace shell。
3. creative layer 调 `generate_hypothesis_target_intent(...)` 或 `generate_hypothesis(...)`。
4. `LLMClient.call_tool(...)` 走 OpenAI-compatible `chat.completions.create(...)` with `tools`/`tool_choice`。
5. 本机 proxy 在 HTTP 层返回 401 `Invalid proxy API key`，没有模型响应、没有 usage。
6. trace 被保存为 `ok=false` error trace；因此有 trace 文件，但没有有效 LLM output。

这解释了为什么 `hypothesis_target_intent` / `hypothesis` 有 trace，而 “Tool call failed” 出现在失败原因里：失败的 tool call 是 provider structured function/tool call。

## Context Visibility Assessment

本 run 可评价的 context/tooling 范围：

- deterministic required context preface 完成。
- active solver facts、active solver map receipts、full algorithm file reads、operator registry、algorithm slice、memory prefetch 都进入 prompt manifest。
- prompt manifest `tool_result_visibility_ledger` 每个 session 都有 12 条，均 `result_in_final_prompt=true`。
- 6 个 prompt manifest 的 `truncated=0`, `omitted=0`。
- `context.read_algorithm_file` 对 `destroy_repair.py`, `local_search.py`, `scheduler.py` 是 `dedicated_projection`，非仅摘要。
- repair sessions 的 prompt 包含 previous failure/resume context；但这个 previous failure 是 auth failure，不能视为研究负反馈。

不可评价的范围：

- LLM 是否真的读到/利用了这些 context：不可评价，因为 provider 在认证阶段失败，无模型 output。
- `hypothesis_target_intent` 质量：不可评价。
- `hypothesis` 质量：不可评价。
- code-phase targeted reads、patch generation、repair follow-up tool selection：不可评价，因为没有进入 code phase。
- screening、validation、protocol、DecisionFeatures：不可评价，因为 `formal_screened_candidates=0`。
- provider usage tokens、cache hit、actual input/output token accounting：不可评价，因为 401 没有返回 usage。trace 只有 prompt/cache audit 的 char 计数和估算性 visibility ledger。

## Stop/Skipped/Ledger Accounting

存在的 stop/skipped 口径：

- `transcript.json`: planner/tool loop stop reason 为 `required_context_satisfied`。
- `tool_selection_ledger`: 只有 deterministic `memory.query` prefetch entry；`skipped=false`；session-level `deterministic_prefetch_plan_id` 在 transcript 顶层为 `"none"`，entry 内有实际 plan id。
- `experiment_events`: 每轮有 `proposal_fail` event，`contract_passed=skipped`, `verification_passed=skipped`, `stage=proposal`。
- `campaign_summary.steps[*].contract_not_run_reason=proposal_generation_failed`。

不存在或不可用的口径：

- 没有 `tool_selection` LLM trace。
- 没有 tool-selection input token usage。
- 没有 code trace。
- 没有 hypothesis DB rows。
- 没有 protocol case ledger、screening metrics、validation metrics。

## Quality Block Chain

质量阻塞链路如下：

1. `LLMClient.call_tool()` 对非 transient 的 401 `LLMError` 走普通 retry，`SCION_LLM_MAX_RETRIES=2`，总共 3 次。
2. 三次失败后抛 `LLMRetryExhaustedError("Tool call failed after 3 attempt(s)...")`。
3. `agentic_failure_classification._structured_output_failure_category()` 中，只有 `is_llm_transient_api_error(exc)` 为 true 时才归 `llm_transient_api_error`；401 invalid key 不匹配。
4. session output 因 structured output exhausted 且 self-check schema invalid/未生成，进入 `contract_boundary_failure`。
5. `campaign/status.json` 和 `campaign/campaign_summary.json` 的 `quality_block_ledger[*].failure_category=contract_boundary_failure`。
6. `run_validity.failure_categories={"contract_boundary_failure": 3}`, `infra_failure_attempts=0`, `noninfra_failure_attempts=3`。

这不是 proposal quality 的真实证据。`Invalid proxy API key` 应作为 auth/infra 类 preflight failure，而不是 schema/contract/proposal quality block。

## Relation To Recent Context/Tooling Fixes

基于本 run 证据，不能说 recent context/tooling 修复导致失败。相反，可观察到的 context/tooling 修复在 deterministic 层表现为生效：

- required context preface 工具完整执行。
- active facts / active solver map / prompt visibility ledger 均被记录。
- prompt manifest 标明 tool results included，且没有 omitted/truncated。
- repair context 能把上一轮失败投影到下一轮 prompt。

但由于 provider auth 在每次 structured LLM call 前阻断，无法评价这些 context 是否改善了模型生成行为。更合理结论是：环境变量或本机 proxy key 与 Scion client API-key 读取路径不一致。特别注意：Scion 当前 client 不读 `OPENAI_API_KEY`；若本机 proxy 期望某个 proxy token，应显式放在 `SCION_API_KEY` 或当前代码实际读取的 Anthropic token env 中。

## Required Checklist Before Next 4R Rerun

1. 环境变量检查：
   - `SCION_MODEL=gpt-5.5`
   - `SCION_BASE_URL=http://127.0.0.1:8080` 或明确的 `/v1` endpoint；Scion 会自动补 `/v1`。
   - `SCION_API_KEY=<valid proxy key>` 必须在 run process 环境中可见。
   - 不要只设置 `OPENAI_API_KEY`，当前 `LLMClient` 不读取它。
   - 若使用兼容旧路径，确认 `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_API_KEY` 没有被继承为错误值。

2. 最小 provider smoke：
   - 用同一个 Python env：`/home/clawd/miniconda3/envs/claw/bin/python`
   - 同一个 cwd/PYTHONPATH：`/home/clawd/research/or-autoresearch-agent/scion`, `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion`
   - 用 Scion 的 `LLMClient.call_tool(...)` 发一个最小 structured tool call 到 `gpt-5.5`，而不是只 curl `/models` 或只测普通 text completion。必须验证 required tool output 能返回 dict。

3. 模型/接口一致性检查：
   - 确认 proxy 支持 `chat.completions.create`、`tools`、required `tool_choice`、`max_completion_tokens`、`prompt_cache_key`。
   - 若 proxy 不支持 `prompt_cache_key`，需要 smoke 覆盖该参数或在 client 中按 provider capability 关闭。
   - 确认 `gpt-5.5` 在 proxy 上对应的模型 id 与 Scion `SCION_MODEL` 完全一致。

4. 运行前 preflight：
   - 在 campaign 正式 proposal attempt 前执行 auth smoke；失败时直接停止并写 `infra/auth_preflight_failed`，不要消耗 proposal quality block。
   - 把 `invalid_api_key`, `401`, `unauthorized`, `authentication` 纳入 infra/auth failure 分类，至少从 run validity 和 proposal quality ledger 中剥离。
   - 对 401 不应做 3 次普通 retry；它不是可恢复格式错误。

5. 报告验收口径：
   - 下一次有效 run 至少应有 `effective_rounds_completed > 0` 或明确的 valid partial evidence。
   - `llm_traces` 应有 `ok=true` 的 `hypothesis` trace，并包含 provider usage 或明确 usage-unavailable reason。
   - 如果仍有 `quality_blocks`，failure reason 不应包含 auth/proxy/API-key 文本；否则继续视为 infra/auth 失败。

