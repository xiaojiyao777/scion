# v0.4 Boundary Provider Smoke, Sonnet 3R, 2026-05-19

## 1. 实验总览

实验路径：

`/home/clawd/research/scion-experiments/v04-boundary-provider-smoke-sonnet-3r-20260519T012328Z/campaign`

目标是验证 v3 边界：Scion core/framework 保持问题无关，CVRP 语义只能经 problem adapter/provider 进入；刚修复的
`scion/scion/proposal/mechanism_novelty.py` 应只做通用 dispatch，CVRP 机制判断应在
`scion/scion/problems/cvrp/mechanism_novelty.py`；`core/stagnation.py` 的 object-model markers 应由 adapter 提供。

结果：

- `total_rounds=3`
- `stopped_reason=max_rounds_exhausted`
- `champion_version=1`
- `n_active_branches=0`
- 没有 candidate 进入正式 Contract/Verification/Protocol；全部在 agentic proposal preview/self-check 阶段 fail-closed。
- Campaign step 数为 4：round 2 对同一个 `cross_route_segment_relocation` hypothesis 跑了两个 code session。
- `circuit_breaker_tripped=false`，`balance_exhausted=false`，`stagnation_signals=[]`。
- `action_locus_coverage={"modify/solver_design": 4}`，说明 active boundary 没有漂移到 legacy component surfaces。

总体判断：

- v3 边界的主体方向是对的：hypothesis/code prompts 都把 `solver_design` 作为 problem-object boundary；tooling 没有让 LLM 直接改 adapter、solver、protocol、data 或 runtime gate；CVRP 机制语义没有出现在 core novelty gate。
- 这轮不是健康的 3 轮 solver-quality smoke：0 个候选进入 screening，主要消耗在 telemetry guard 和机制重复/语义判断问题上。
- 不建议现在直接继续跑 6 轮。先修 P1 项，再跑 6 轮更有信息量。

## 2. Session / Round 逐项分析

### Round 1 hypothesis: `aaa002c6-e06a-4d18-a4b5-453d3123cd21`

阶段：

- `partial_hypothesis_only`
- 先生成 `segment_chain_repair`，被 mechanism novelty gate 拒绝。
- 随后生成并暂停等待 approval 的 hypothesis 为 `route_merge_split`。

LLM 调用：

- Tool selection traces:
  - `20260519T012348465622_tool_selection_...`: 读 `policies/baseline_modules/local_search.py`
  - `20260519T012355705205_tool_selection_...`: 读 `policies/baseline_modules/destroy_repair.py`
  - `20260519T012400313517_tool_selection_...`: 读 `policies/baseline_modules/acceptance.py`
  - `20260519T012414568435_tool_selection_...`: 试图读 `construction.py`，framework 因 solver-design file read budget 保留而跳过
- Hypothesis traces:
  - `20260519T012420220745_hypothesis_...`: `segment_chain_repair`
  - `20260519T012447580284_hypothesis_...`: `route_merge_split`

上下文合理性：

- 必要 preface 工具完整：`context.list_surfaces`、`context.read_problem`、`context.list_algorithm_files`、`context.read_active_solver_design`、`context.read_solver_call_graph`。
- 选择 `local_search.py`、`destroy_repair.py`、`acceptance.py` 很合理；`construction.py` 作为第四个 read 被预算策略拦截也合理。
- `context.read_problem` 是 adapter/spec-rendered problem summary，CVRP 语义来自 problem package，不是 core 硬编码。

输出合理性：

- 初始 `segment_chain_repair` 指向 `destroy_repair.py`，但陈述“Shaw-related 等现有 destroy operators 都是 individual customer removal，没有 segment-chain locality”。CVRP provider 将其判为与已有 `_shaw_removal`/related removal 前提冲突。
- 这个拒绝有边界价值：拒绝来自 CVRP provider，不来自 generic proposal gate。
- 但内容上疑似过宽：该 hypothesis 并未声称 Shaw/removal 缺失，而是声称“contiguous segment as unit”缺失。provider 的 Shaw-related regex 可能把 “Shaw-related” + “missing cluster locality” 误判成 “Shaw related removal missing”。

失败点：

- transcript 记录 “Mechanism novelty gate rejected hypothesis; retrying with structured semantic feedback”。
- 但两次 hypothesis trace 的实际 prompt 完全相同：拼接 `system_blocks + user_prompt` 长度均为 `68305`，SHA-256 前 16 位均为 `e9a1ac7afa0ae997`，trace prompt hash 也相同。
- `api_visible_prompt_manifest_0002_hypothesis_semantic_retry.json` 声称 `agentic_hypothesis_semantic_rejections` section 已 included，实际 llm trace 中没有可见的 rejection/semantic feedback 内容。
- 这是框架问题：semantic retry 的 manifest 与实际发送给 LLM 的 prompt 不一致，反馈没有真正进入调用上下文。

### Round 1 code: `8aea7e06-071d-482a-9e2b-0b81606987ff`

目标文件：

- `policies/baseline_modules/local_search.py`

Hypothesis：

- 添加 `route_merge_split` VNS phase：尝试合并短 route 或拆分长 route，目标为 `fleet_violation` + `total_distance`。

LLM 调用：

- Tool selection traces: `012518`、`012524`、`012529`、`012534`、`012541`
- Code traces:
  - `20260519T012548818534_code_...`
  - `20260519T012644600027_code_...`
  - `20260519T012741136272_code_...`

工具调用合理性：

- 读了 `local_search.py`、`destroy_repair.py`、`acceptance.py`；第四/重复 read 被预算拦截或去重。
- Code phase 使用已读 target file、压缩 `context.read_surface`、读取 `context.read_branch_state`；没有越界工具调用。

Code 输出摘要：

- 三次 code 都完整替换 `local_search.py`，在 `_default_vns_operators()` 中加入 `_route_merge_split`。
- 使用 `_Solution.routes` / `_Route.customers` / `route.recalculate()` / `solution.remove_empty_routes()`，整体对象模型使用比后续 round 2 更稳。
- 都声明 `mechanism_changes=[route_merge_split]`，并尝试记录 `context.record_iteration("route_merge_split", 1)` 与 `context.record_move(...)`。

失败点：

- 三次 Contract preview 均通过。
- 三次 `proposal.algorithm_smoke` 均失败：
  - `TELEMETRY_EFFECT_NOT_OBSERVED`
  - field: `solver_algorithm_fleet_violation`
- 分类应为 candidate quality / hypothesis-evidence mismatch。该 hypothesis 明确把 `fleet_violation` 放入 target/effect，并期待 route merge 降低 fleet violation；smoke 没有观察到该字段正向变化，framework fail-closed 合理。

### Round 2 hypothesis: `ada2d987-0b7e-4eab-bd23-04b767a6f498`

阶段：

- `partial_hypothesis_only`

目标文件：

- `policies/baseline_modules/destroy_repair.py`

Hypothesis：

- `cross_route_segment_relocation`：把 2-3 个连续 customer segment 从一条 route 搬到另一条 route。

LLM 调用：

- Tool selection traces:
  - `012840`: `destroy_repair.py`
  - `012848`: `local_search.py`
  - `012854`: `acceptance.py`
  - `012900`: `construction.py`
- Hypothesis trace:
  - `20260519T012905627965_hypothesis_...`

上下文与工具合理性：

- 工具选择合理，面向 destroy/repair + local-search 机制判断。
- 输出保留 `change_locus=solver_design`，没有漂到 inactive legacy surface。

输出合理性：

- 该 hypothesis 明确说 existing VNS 有 or-opt moves，但“不系统评估 moving ordered segments of 2 or 3 customers across different routes”。
- 这与 active solver snapshot 中 `_or_opt_2` / `_or_opt_3`、`_or_opt` skipping same-route destinations、local_search “intra and cross-route moves” 高度重叠。

失败点：

- CVRP novelty provider 没有拦截。用同一类 active snapshot facts 复核当前 provider，`cross_route_segment_relocation` 返回 `None`。
- 这是 CVRP provider 的 false negative：`_describes_existing_or_opt_improvement`/Or-Opt regex 过宽或过窄，导致“承认已有 or-opt 但声称缺少 2/3 cross-route segment relocation”的矛盾前提逃过 gate。

### Round 2 code A: `898829de-8433-4a64-b1fb-d909ffe79dad`

目标文件：

- Primary: `policies/baseline_modules/destroy_repair.py`
- Additional: `policies/baseline_modules/scheduler.py`

LLM 调用：

- Tool selection traces:
  - `012940`: `destroy_repair.py`
  - `012951`: `local_search.py`
  - `013001`: `acceptance.py`
  - `013014`: `construction.py`
  - `013023`: `state.py`，被 file-read budget 拦截
- Code traces:
  - `013035`
  - `013200`
  - `013320`

工具调用合理性：

- 读 `state.py` 的选择是合理的，因为 patch 要操作 `_Solution` / `_Route`；framework 因预算跳过也符合预览预算保护。
- Code prompt 本身已包含对象模型摘要，因此没有完全失去 object-model context。

Code 输出摘要：

- 在 `destroy_repair.py` 增加 `cross_route_segment_relocation(...)`，scheduler 在每次 ALNS repair 后调用该 phase 并记录 phase runtime。
- 不是放入 repair_ops，而是作为独立 post-repair phase 调用；这仍在 active scheduler call chain 内。

失败点：

- 第 1、2 次 patch：Contract preview 通过，algorithm smoke 因 `solver_algorithm_fleet_violation` effect 无正证据失败。
- 第 3 次 patch：Contract preview 失败：
  - `C9e_solver_design_integration`
  - inert helper: `_segment_load`
- 这个 contract 拦截正确：新 helper 未接入 active path，属于 patch graph / candidate construction failure。

Telemetry 分类：

- 此 hypothesis 的 `target_objectives=["total_distance"]`，`protected_objectives=["fleet_violation"]`，但 `expected_telemetry.effect` 仍包含 `solver_algorithm_fleet_violation`，语义上更像 protected/no-regression probe。
- 当前 telemetry guard 对所有 non-budget expected fields 都要求 `candidate_positive > 0`。因此它要求 fleet_violation 产生正向 runtime evidence，这对 protected objective “保持不变”不合适。
- 这里一半是 candidate schema 质量问题，一半暴露 framework/prompt 问题：expected telemetry 没有“protected/no-regression”类别，且 repair guidance 说“Ensure positive runtime evidence via solver_algorithm_fleet_violation”，会把 code agent 带向错误目标。

### Round 2 code B: `fe471879-1b33-46b5-b454-5fb4455a80b7`

目标文件：

- Primary: `policies/baseline_modules/destroy_repair.py`
- Additional: `policies/baseline_modules/scheduler.py`

LLM 调用：

- Tool selection traces:
  - `013437`: `destroy_repair.py`
  - `013450`: `local_search.py`
  - `013457`: `acceptance.py`
  - `013505`: `construction.py`
  - `013516`: 试图再读 `destroy_repair.py`，跳过
- Code traces:
  - `013528`
  - `013647`
  - `013803`

工具调用合理性：

- 与 code A 相同，选择目标/支持文件合理。
- 仍未实际获得 `state.py` full read；不过 code prompt 已明确 `_Solution` / `_Route` API。

Code 输出摘要：

- 继续实现同一 `cross_route_segment_relocation`，scheduler 仍在 ALNS repair 后调用。
- 第 2 次 repair 中出现 runtime audit error，说明 patch 在对象模型或 route index 刷新上仍不稳。

失败点：

- 第 1 次：Contract preview 通过；algorithm smoke 因 `solver_algorithm_fleet_violation` effect 无正证据失败。
- 第 2 次：Contract preview 通过；algorithm smoke 报 `solver_algorithm_errors=1`，repair guidance 明确给出 `_Solution` / `_Route` 对象模型约束。
- 第 3 次：Contract preview 通过；algorithm smoke 再次因 `solver_algorithm_fleet_violation` effect 无正证据失败。
- 这里 object-model failure 只出现一次，不满足 stagnation object-model loop 阈值；没有触发 stagnation signal 是合理的。

### Round 3 hypothesis: `b9048f7d-66fe-40b2-9dad-95a067de7d61`

阶段：

- `partial_hypothesis_only`

目标文件：

- `policies/baseline_modules/local_search.py`

Hypothesis：

- `route_pair_3opt`：route-pair 3-opt tail reconnection，top-6 route pairs，split positions capped at 12。

LLM 调用：

- Tool selection traces:
  - `013925`: `local_search.py`
  - `013931`: `destroy_repair.py`
  - `013938`: `acceptance.py`
  - `013953`: `construction.py`
- Hypothesis trace:
  - `20260519T014001714581_hypothesis_...`

上下文与工具合理性：

- 工具选择合理，重点读 local_search 和相关支持模块。
- Hypothesis 没有被 CVRP novelty provider 拦截。这个不明显重复已有 `_two_opt_star` / `_or_opt_2/3`，放行可接受。

输出合理性：

- 机制 ID `route_pair_3opt` 清晰，复杂度与 caps 明确。
- `expected_telemetry.effect` 主要落在 mechanism-specific phase fields、best delta、improving moves、total distance，语义上合理。

失败点：

- 无；该 session 按设计暂停等待 code approval。

### Round 3 code: `020982ac-50e9-4380-9902-c9ad0afb373a`

目标文件：

- `policies/baseline_modules/local_search.py`

LLM 调用：

- Tool selection traces:
  - `014034`: `local_search.py`
  - `014042`: `destroy_repair.py`
  - `014049`: `acceptance.py`
  - `014055`: `construction.py`
  - `014106`: 重复 `local_search.py`，跳过
- Code traces:
  - `014116`
  - `014213`
  - `014313`

工具调用合理性：

- 目标文件与支持文件选择合理；重复 target read 被 skip。

Code 输出摘要：

- 三次 code 都完整修改 `local_search.py`，增加 `_route_pair_3opt` 并接入 `_default_vns_operators()`。
- 三次均声明 `mechanism_changes=[route_pair_3opt]`。
- Code agent 根据 feedback 明确尝试让 smoke 看到 `solver_algorithm_phase_improvement_counts.route_pair_3opt` 和 `solver_algorithm_phase_best_delta.route_pair_3opt`。

失败点：

- 三次 Contract preview 均通过。
- 三次 algorithm smoke 均失败：
  - `TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED`
  - mechanism: `route_pair_3opt`
  - paths: `solver_algorithm_phase_improvement_counts.route_pair_3opt`, `solver_algorithm_phase_best_delta.route_pair_3opt`
- 这是 candidate quality / smoke evidence failure：机制被调用或可被审计，但没有产生 accepted improving movement。framework 拦截符合 v3 设计。

## 3. 符合 v3 设计的地方

- `scion/scion/proposal/mechanism_novelty.py` 现在是通用 dispatcher：只定义 `MechanismNoveltyResult`、provider protocol、统一 rejection shape，并通过 `context.adapter.mechanism_novelty_provider()` 或 adapter fallback 分发；没有 CVRP regex 或 CVRP file/mechanism 名称。
- CVRP 机制语义在 `scion/scion/problems/cvrp/mechanism_novelty.py`，adapter 通过 `mechanism_novelty_provider()` 返回 `CvrpMechanismNoveltyProvider()`。
- 实验产物中的 `champions/champion_v1/mechanism_novelty.py` 与 repo 内 CVRP provider 一致；campaign 使用的是 problem package provider 语义。
- `core/stagnation.py` 不再硬编码 CVRP object-model markers；`campaign_composition.py` 从 adapter 读取 `stagnation_object_model_markers()`，CVRP adapter 提供 `_solution`、`_route`、`from_public`、`solver_algorithm_errors=` 等 markers。
- 所有 hypothesis 都保持 `change_locus=solver_design`，没有选择 inactive/legacy component surface 作为研究目标。
- Tool selection prompt 明确“Scion is a framework: use only provided context and tool specs, without assuming any particular problem domain”；CVRP 细节来自 `context.read_problem` / surface metadata / active solver snapshot。
- Contract preview 正确拦截 inert helper `_segment_load`，没有让 patch graph 问题进入 runtime。
- Algorithm smoke / telemetry guard failures 被记录为 `agent_quality_blocked` 或 proposal-session self-check failure；campaign 没有把它们升级为 infra/circuit breaker。
- No-op / preview budget 行为合理：重复 read 被跳过，code phase surface read 被压缩以保留 self-check budget。

## 4. 需要继续修复的问题

### P0

无确定 P0。没有发现 CVRP 语义重新进入 core/proposal dispatcher，也没有发现 frozen adapter/protocol/runtime 被候选编辑。

### P1

1. Semantic retry 没有把 structured semantic feedback 送入实际 LLM prompt。
   - 证据：round 1 两次 hypothesis trace (`012420...` 与 `012447...`) 的实际 prompt 完全一致，长度 `68305`，SHA-256 前 16 位 `e9a1ac7afa0ae997`，trace prompt hash 也相同。
   - transcript 和 manifest 声称 `agentic_hypothesis_semantic_rejections` included，但 llm trace 中没有 rejection reason。
   - 影响：mechanism novelty gate 虽然能拒绝，但 retry 不是基于拒绝原因修复，可能靠采样随机换题。

2. CVRP mechanism novelty provider 对 Or-Opt 2/3 cross-route segment relocation 有 false negative。
   - `cross_route_segment_relocation` 明确声称缺少 2-3 customer cross-route segment relocation，但 active snapshot 已显示 `_or_opt_2/_or_opt_3` 和 cross-route moves。
   - 当前 provider 对该 hypothesis 返回 `None`，导致重复机制进入 code 阶段并消耗两个 code sessions。
   - 建议收紧 `_describes_existing_or_opt_improvement` 与 `_claims_missing_or_opt_2_3` 的互斥逻辑：承认“existing or-opt exists”不应自动豁免“missing length-2/3 cross-route segment relocation”的矛盾陈述。

3. CVRP provider 对 Shaw-related removal 可能有 false positive。
   - 首个 `segment_chain_repair` hypothesis 承认已有 Shaw-related destroy，但主张缺少 contiguous segment-chain repair。
   - Provider 将其判成 `shaw_related_removal` premise contradiction。这个拦截不一定错误到会放坏候选，但语义过宽，容易误杀“改进已有 related removal 或添加 segment repair”的候选。

4. Telemetry guard / expected_telemetry guidance 缺少 protected/no-regression 语义。
   - 对 `cross_route_segment_relocation`，hypothesis target 是 `total_distance`，`fleet_violation` 是 protected objective；但 `expected_telemetry.effect` 中包含 `solver_algorithm_fleet_violation`。
   - 当前 guard 对所有 expected fields 要求 positive evidence，因此要求 protected field 产生正向变化，并给出“Ensure positive runtime evidence via solver_algorithm_fleet_violation”的 repair guidance。
   - 建议至少在 prompt/schema 中明确：protected objective 不要放入 `effect`，除非声称会改善；或新增/映射 `protection`/`no_regression` telemetry category，在 smoke 中检查不变或不恶化，而不是 positive movement。

### P2

1. Hypothesis output/session output 缺少 round/stage 显式字段，需要从 `campaign_summary` + `agentic_session_index` + trace timestamp 反推 session 属于哪一轮。

2. `proposal.algorithm_smoke` 工具 observation 的 `status=ok`，但 `result_summary` 是 “found issues”。这符合“工具执行成功但候选失败”的模型，但 trace review 时容易误读；可以增加 `preview_outcome=failed` 之类的 compact metadata。

3. Tool planner 仍经常在预算边界上请求第 4/5 个 full algorithm file read，然后由 framework 跳过。当前不错误，但可通过 compact API/symbol read 降低无效 planner calls。

4. Round 2 object-model repair guidance 很有用，但没有沉淀到下一轮 hypothesis/code context 的高层诊断里；如果同类 `solver_algorithm_errors=1` 连续出现，应更早提示读取 `state.py` 或使用 symbol/API summary。

## 5. 是否建议继续跑 6 轮

不建议现在直接继续跑 6 轮。

原因：

- 这 3 轮没有任何 candidate 进入 screening，继续跑大概率继续消耗在 telemetry/providernovelty 循环上。
- Round 2 已经暴露明显 provider false negative，重复机制能绕过 novelty gate。
- Semantic retry feedback 没有真正进入 prompt，继续跑不能有效验证“LLM 根据 CVRP provider feedback 改题”。
- Telemetry guard 对 protected objective 的 positive-evidence 要求会持续误导 code repair。

建议修完 P1 后再跑 6 轮。下一次 6 轮的验收条件应至少包括：

- semantic retry trace 的 actual prompt 与 initial prompt 不同，并包含具体 rejection reason；
- `cross_route_segment_relocation` 这类 duplicate Or-Opt 2/3 hypothesis 被 CVRP provider 拦截；
- protected objective 不再被 telemetry guard 要求 positive movement；
- 至少 1 个 candidate 进入 screening，或者失败都能归因到明确 candidate-quality/contract-quality，而不是边界/provider/feedback plumbing。
