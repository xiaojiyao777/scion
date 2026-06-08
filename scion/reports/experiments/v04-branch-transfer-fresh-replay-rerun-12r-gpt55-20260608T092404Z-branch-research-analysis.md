# Scion v0.4 Branch Transfer Fresh Replay Rerun 12R GPT-5.5 实验分析报告

实验 run root:
`/home/clawd/research/scion-experiments/v04-branch-transfer-fresh-replay-verify-rerun-12r-gpt55-12r-gpt55-20260608T092404Z-claw`

报告基准:
`/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md`

写作时间: 2026-06-08

## 0. 结论摘要

这组 12R 是一次有效完成的 screening run，但不建议直接升到 20R。原因不是 LLM 完全没有形成研究方向，而是框架层有几个会放大到 20R 的硬缺口:

1. 最后一轮触发了 fresh runtime replay，但 replay 失败，`last_result` 为 `attempt_kind=fresh_runtime_replay`、`action=replay`、`reason=fresh runtime replay missing workspace,hypothesis`。这发生在 branch `52a00dbd-63a1-4742-9f4f-507544f883f7` 的 `ranked_temperature_acceptance` 之后。框架识别出需要 fresh champion runtime，但候选 workspace/hypothesis 状态没有保留下来，导致无法执行 replay。
2. 12 个 formal candidates 全部只到 screening，没有 validation/frozen，没有 promotion。case-level 结果主要是 tie，少量 weak-positive 都被 `SCREENING_FAIL_WIN_RATE`、runtime saturation 或 fresh champion required 限制住。
3. branch lesson usage 的结构化合规明显改善，`branch_lesson_usage_present_count=12`、`satisfied_count=12`，但真正改变研究方向的作用有限。多数是 avoid/contrast 的合规记录，只有少数机制真正从上一轮失败中转向。
4. runtime 证据严重受 cached champion 影响。12 个候选中 11 个 `low_cached_champion`，10 个 runtime aggregate excluded，6 个 fresh champion required。Decision 层没有把 runtime 当独立优化信号，这符合 v3 边界，但 proposal/scheduler 仍被 runtime follow-up 牵引，而 replay 无法闭环。
5. campaign summary 把 16 个 candidate intent 都统计成 `observability_candidate`，这和实际 12 个 formal hypotheses 的内容不一致。除 `alns_stagnation_probe` 明显是观测性候选外，其余多数是在改质量机制。这个统计口径会误导主会话判断本 run 的研究性质。

主建议: 先修 P0，再跑一个小规模 4R/8R replay acceptance，确认 fresh replay 可执行、candidate state 可恢复、runtime 证据闭环后，再考虑 20R。当前 12R 足够支持修框架，不足以支持扩大搜索。

## 1. v3 边界基准

本报告以 Scion v3 的以下边界作为判断标准:

- LLM 只能产生 tainted proposal，包括 hypothesis、patch、failure analysis。
- Contract Gate 负责 schema、文件边界、AST/接口、import、安全调用等结构检查。
- Verification Gate 负责候选是否还在解同一个问题，包括 syntax/interface/unit/regression/feasibility/objective/state leak/wall-clock。
- Protocol 负责 screening/validation/frozen 的统计证据。
- Decision Layer 只能读 Safe Feature Extractor 产出的结构化 `DecisionFeatures`，不能读 LLM 自由文本。
- Cross-branch lessons 可以给 proposal visibility，但不能进入 DecisionFeatures 作为决策特征。
- Screening 只是粗筛，不是 promotion 依据。Validation/Frozen 才能支撑晋升。

本 run 的大体边界表现:

- formal candidate 都经过 contract/verification/protocol，12 个 screening 的 `contract_result=passed`、`verification_result=passed`，没有 protocol failure。
- DecisionFeatures 中没有发现 branch lesson raw text 或 LLM rationale。包含的是 branch state、mechanism ids、runtime stats、reason code 等结构化枚举/数值，基本符合 v3。
- Cross-branch research observability 明确标注 `policy=proposal_observability_only`、`decision_input_policy=excluded_from_decision_features`，符合 v3。
- 但 fresh runtime replay 作为 scheduler/lifecycle 后续动作无法 materialize candidate state，这不是 v3 边界问题，而是 v0.4 retention/replay 实现缺口。

## 2. Run 级事实

证据来源:

- `campaign/status.json`
- `campaign/campaign_summary.json`
- `campaign/scion.db`
- `campaign/artifacts/formal_candidates/index.jsonl`
- `campaign/llm_traces/`
- `campaign/agentic_sessions/`
- `campaign/metrics/`

Run accounting:

| 项 | 值 |
|---|---:|
| requested_rounds | 12 |
| effective_rounds_completed | 12 |
| formal_screened_candidates | 12 |
| protocol_stage_counts | screening=12, validation=0, frozen=0 |
| proposal_attempts_total | 16 |
| quality_blocks | 3 |
| non_counted_lifecycle_steps | 1 |
| run_validity | valid, complete |
| stopped_reason | max_rounds_exhausted |
| promoted_experiments | 0 |

LLM 调用:

| request_kind | calls |
|---|---:|
| hypothesis_target_intent | 16 |
| hypothesis | 21 |
| tool_selection | 51 |
| code | 18 |
| total traces | 106 |
| agentic sessions | 29 |

Runtime/observability:

| 指标 | 值 |
|---|---:|
| runtime_budget_diagnostic_count | 12 |
| fresh_champion_required_count | 6 |
| runtime_aggregate_excluded_count | 10 |
| low_cached_champion_count | 11 |
| standalone_optimization_signal_false_count | 12 |
| decision_features_excluded_count(runtime policy) | 12 |

Cross-branch:

| 指标 | 值 |
|---|---:|
| branch_lesson_record_count | 36 |
| branch_lesson_usage_requirement_count | 15 |
| branch_lesson_usage_present_count | 12 |
| branch_lesson_usage_satisfied_count | 12 |
| branch_lesson_usage_semantic_mismatch_block_count | 1 |
| borrowed_lesson_count | 1 |
| avoided_lesson_count | 23 |
| contrasted_lesson_count | 13 |
| preserved_same_branch_lesson_count | 3 |
| weak_positive_transfer_count | 0 |
| cross_branch_map_seen_count | 12 |

## 3. 逐轮 formal candidate 分析

### R01, branch 8e213e1b, interroute_2swap

- Hypothesis: 在 `local_search.py` 增加跨路线连续 2-customer block swap。目标是补足现有 relocate/Or-opt/single swap/tail exchange 无法直接交换两个紧凑片段的缺口。
- Target: `policies/baseline_modules/local_search.py`
- Code: 在 VNS portfolio 中插入 `_interroute_2swap`，新增 64 行左右。遍历两条 route 的长度为 2 的 block，检查容量，计算两条 route 新距离，严格 `delta < -EPS` 才提交，并记录 `context.record_iteration/move/phase`。
- Contract/Verification: passed/passed。
- Protocol/Decision: screening case `1/0/7`，pair `4/2/10`，median delta `0.0`，CI `[0.0,0.0]`，decision `continue_explore`。reason codes 包含 `SCREENING_FAIL_WIN_RATE`、`SCREENING_WEAK_SIGNAL_CONTINUE`、runtime saturation。
- Result: weak-positive retained，但 case-level 不够。E-n101-k8 有后续记忆中的正信号，整体仍是 tie-dominated。
- Research quality: 假设合理，code 和机制匹配，telemetry 有机制路径。问题是新增局部搜索进一步挤占 runtime，且首轮没有先证明机会空间足够。

### R02, branch 8e213e1b, capped interroute_2swap

- Hypothesis: 保留 R01 的 block exchange，但改成 late/capped/slack-filtered probe，减少 full scan runtime saturation。
- Target: `local_search.py`
- Code: 仍新增 `_interroute_2swap`，约 88 行，加入更多 no-op 和 cap/filter 路径，目标是晚触发、有限扫描。
- Contract/Verification: passed/passed。
- Protocol/Decision: case `0/0/8`，pair `2/2/12`，median `0.0`，CI `[0.0,0.0]`，decision `continue_explore`。reason codes 为 `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`、runtime saturation。
- Result: no effect。runtime 证据是 `low_cached_champion`，fresh champion required。
- Research quality: 这是合格的 same-branch refinement，确实回应了 R01 的 runtime/budget 问题。但 code 仍主要是同一机制的扫描改造，没有突破 tie-dominated 的根因。

### R03, branch 8e213e1b, route_merge_repair

- Hypothesis: 从 local search 转向 repair，在 `destroy_repair.py` 加 route merge biased repair，避免继续添加昂贵 VNS neighborhood。
- Target: `policies/baseline_modules/destroy_repair.py`
- Code: 新增 `_route_merge_repair`，约 73 行新增、2 行删除，并注册进 repair family。优先把 removed customers 插回 existing routes，失败 fallback 到 regret2/new route。
- Contract/Verification: passed/passed。
- Protocol/Decision: case `0/1/7`，pair `2/3/11`，median `0.0`，CI `[0.0,0.0]`，decision `abandon`。branch lifecycle archive lineage，soft abandon loss without win。
- Result: branch 8e213e1b 终局为 abandoned。最终 branch evidence: case positive E-n101-k8 `+10.0`，negative B-n52-k7 `-3.5`，总体 regression。
- Research quality: 转向 repair 是合理的，说明 branch lessons 改变了 target/mechanism。code 符合假设，但效果仍不稳定，且 branch 内从 R01/R02 的 local-search weak positive 跳到 repair 后没有形成足够 deep local analysis。

### R04, branch e4b00114, route_compaction_postrepair create_new

- Hypothesis: 新建 route compaction module，postrepair 或 construction 后尝试 evacuate sparse routes，减少 depot legs/改善 packing。
- Target: `policies/baseline_modules/route_compaction.py`
- Code: 新增新文件约 104 行，并在 scheduler/相关 wiring 中调用 `_route_compaction_postrepair`。选择 sparsest 1-3 routes，尝试 cheapest feasible insertion，只有 route count 降低或同 route count 严格降距才 commit。
- Contract/Verification: passed/passed。
- Protocol/Decision: create_new screening total pairs 24，case `0/0/12`，pair `1/1/22`，median `0.0`，CI `[0.0,0.0]`，decision `continue_explore`。reason 包含 active pair wins but case fail、runtime saturation diagnostic。
- Result: weak-positive retained，但没有 case-level win。
- Research quality: 作为 clean fork 合理，和之前 local search/repair 区分明确。问题是 route compaction 的机会空间偏窄，pair-level 信号没有升到 case-level。

### R05, branch e4b00114, multi-order route compaction

- Hypothesis: R04 只试单一 evacuation order，改为 bounded multi-order route evacuation，包括 current order、insertion difficulty、demand order。
- Target: `route_compaction.py`
- Code: 约 152 行新版本文件，加入 `_evacuation_orders`、`_recipient_count`，对 top sparse routes 尝试多个 ordering。
- Contract/Verification: passed/passed。
- Protocol/Decision: case `0/0/8`，pair `0/0/16`，median `0.0`，CI `[0.0,0.0]`，decision `continue_explore`。fresh champion required + runtime saturation。
- Result: no effect。
- Research quality: 这是 branch-local deepening，但没有解决 R04 的关键问题: compaction 是否真的触发并改变 objective。更像扩大搜索路径而不是基于 activation/effect 的机制诊断。

### R06, branch e4b00114, capacity_tight_regret_repair

- Hypothesis: 从 route compaction 转向 repair ordering。对 hard-to-place/high-demand/feasible-route-scarce customers 提高 regret priority，减少 late new-route/distance-expensive insertions。
- Target: `destroy_repair.py`
- Code: 新增 `_capacity_tight_regret_repair` 和 `_regret_choice(... tight=True)`，修改 repair selection，约 +118/-30。记录 `capacity_tight_regret_repair` telemetry。
- Contract/Verification: passed/passed。
- Protocol/Decision: case `1/0/7`，pair `3/1/12`，median `0.0`，CI `[0.0,1.0]`，decision `continue_explore`。weak signal continue。
- Result: weak-positive retained。branch evidence 后续显示 positive A-n54-k7 `+2.0`、E-n101-k8 `+14.5`，但 B-n52-k7 `-2.5`。
- Research quality: 这是本 run 中较好的机制转向之一。它避开了 compaction/local-search runtime-heavy 路线，改变 repair ordering，source-grounded，且出现更明显 pair/case positive。但仍未过 screening win-rate。

### R07, branch e4b00114, scarcity-triggered capacity repair schedule

- Hypothesis: R06 的 weak positive 可能来自 tight-capacity cases，损失来自非稀缺场景过度激活；在 scheduler 中只在 scarcity trigger 时启用 capacity_tight repair。
- Target: `policies/baseline_modules/scheduler.py`
- Code: 加 `_use_capacity_tight_repair`，在 removed high-demand/few feasible insertion/high fill 等条件下触发，否则回到 standard regret portfolio。约 +33/-2。
- Contract/Verification: passed/passed。
- Protocol/Decision: case `0/1/7`，pair `3/3/10`，median `0.0`，CI `[-0.5,1.0]`，decision `abandon`。branch lifecycle archive lineage。
- Result: e4b00114 abandoned。最终 branch evidence 是 quality_regression，positive A-n54-k7/E-n101-k8，negative B-n52-k7。
- Research quality: 假设很合理，直接回应 R06 的弱正/损失分布，code 也符合“激活条件”假设。但结果说明 trigger 没有稳定区分正负 case，branch abandon 合理。

### R08, branch da22cb9e, plateau_reheat_acceptance

- Hypothesis: 不再增加 neighborhood，改 SA acceptance，在 stagnation segment 后 bounded reheat，帮助逃离 distance plateau。
- Target: `policies/baseline_modules/acceptance.py`
- Code: 给 `_SimulatedAnnealing` 增加 `observe_segment` 和 `record_improvement` 等接口，scheduler 调用 acceptance observe/record，约 +49。
- Contract/Verification: passed/passed。
- Protocol/Decision: case `0/0/8`，pair `0/0/16`，median `0.0`，CI `[0.0,0.0]`，decision `continue_explore`。fresh champion required + runtime saturation。
- Result: no effect。后续同 branch 尝试 construction 方案在 code smoke 阶段失败，branch 保持 explore/discarded。
- Research quality: 机制方向合理，能避开 local-search/runtime 重负。但 code 改动引入新接口，需要 scheduler 正确观测 segment。R08 protocol 没有效果，后续 failed code session 暴露 object model/acceptance interface 上下文仍不够稳。

### R09, branch c2d10bb6, route_limit_seed_selection

- Hypothesis: 不再只把 route-limit fallback 当 emergency，改为 route-limited instances 的 bounded seed selector，在 primary 与 capacity-balanced variant 中选 feasible 低 distance seed。
- Target: `policies/baseline_modules/construction.py`
- Code: 加 `_route_limit_seed_selection` 并在 construction/scheduler wiring 中记录 telemetry，约 +35。
- Contract/Verification: passed/passed。
- Protocol/Decision: case `0/0/8`，pair `0/0/16`，median `0.0`，CI `[0.0,0.0]`，decision `continue_explore`。
- Result: no effect。
- Research quality: 方向是干净的 clean fork，避开 repair/local-search/acceptance。缺点是 code 改动太轻，且没有证明 seed selector 实际改变了 starting basin。

### R10, branch c2d10bb6, alns_stagnation_probe

- Hypothesis: 作为 observability bridge，记录 tie-dominated run 的 ALNS stagnation cause，包括 no removals、repair/VNS infeasible、route-limit rejection、SA rejection、no best-improving move。
- Target: `scheduler.py`
- Code: 加少量 `record_iteration/record_phase` 和 counters，约 +22，不改变搜索语义。
- Contract/Verification: passed/passed。
- Protocol/Decision: case `0/0/8`，pair `0/0/16`，median `0.0`，CI `[0.0,0.0]`，decision `continue_explore`。
- Result: no effect，但作为观测候选本来不期待直接提升 objective。branch 保留 best checkpoint，current head discarded。
- Research quality: 研究意图合理，但 framework 将它作为 formal screening candidate 与 quality candidate 同等计数，导致 12R 中有一轮花在“应当服务下一轮”的观测，而没有形成后续使用闭环。

### R11, branch d3f1fa68, cross_route_2opt_reconnect

- Hypothesis: VNS 缺少跨路线 interior segment 2-opt reconnect，新增 bounded first-improvement operator，交换中段而非 customer/block/suffix。
- Target: `local_search.py`
- Code: 新增 `_cross_route_2opt_reconnect`，约 +111，扫描 cut pairs、测试 segment orientation、容量可行且距离下降才 commit。
- Contract/Verification: passed/passed。
- Protocol/Decision: case `0/0/8`，pair `1/3/12`，median `0.0`，CI `[-1.5,0.0]`，decision `abandon`。soft abandon non-positive CI。
- Result: branch abandoned。negative B-n52-k7 `-1.5`、E-n101-k8 `-2.0`。
- Research quality: 机制 novelty 有，但它回到了 runtime-heavy local-search family，和前面 interroute_2swap 的失败模式相似。branch lessons 有 avoid/contrast，但真正方向变化不足。

### R12, branch 52a00dbd, ranked_temperature_acceptance

- Hypothesis: 改 SA acceptance 为 rolling quantile/rank-aware temperature，不 reheat，不改 scheduler trigger，接受浅层 uphill plateau move，拒绝大回退。
- Target: `acceptance.py`
- Code: 改 `_SimulatedAnnealing.accept`，记录 positive deltas window、rank/heat calibrated acceptance，并在 scheduler 记录 `ranked_temperature_acceptance` phase/move，约 +52/-5。
- Contract/Verification: passed/passed。
- Protocol/Decision: case `0/0/8`，pair `3/1/12`，median `0.0`，CI `[0.0,1.5]`，decision `continue_explore`。reason codes: `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`、`TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`、runtime saturation。
- Result: weak-positive，但 telemetry effect zero: `solver_algorithm_phase_best_delta.ranked_temperature_acceptance` 和 `solver_algorithm_phase_improvement_counts.ranked_temperature_acceptance` 都 present 但 zero。fresh runtime follow-up required。
- Research quality: 候选方向合理，code 不改 feasibility/route-limit，符合 v3 problem boundary。但 objective 仍 case-level tie，telemetry 表明机制没有直接 best-delta/effect，弱正主要来自 pair-level 和 low-confidence runtime，需要 fresh replay 确认。replay 随后失败，是本 run 的关键框架缺陷。

## 4. 逐个 LLM 调用和上下文质量

本 run 的 agentic session 基本是“两段式”:

- hypothesis/target_intent session: 先选 target intent，再产出 formal hypothesis。通常可见 problem summary、active solver design/map、operator registry、solver call graph、target/neighbor algorithm slices、screening/runtime feedback、branch lesson usage。
- code session: 对 approved hypothesis 再执行 tool-selection，读取 branch state、surface interface、target algorithm file、active solver facts、screening/runtime feedback，然后生成 patch，做 schema/contract preview 和 algorithm smoke。

按 session 顺序摘要:

| 时间 | session | branch | 类型/状态 | target/mechanism | context/tool 重点 | 质量判断 |
|---|---|---|---|---|---|---|
| 09:24:05 | a866d370 | 8e213e1b | hypothesis partial | `local_search.py` `interroute_2swap` | problem, active solver, local/destroy/scheduler source, memory | source-grounded，初始 novelty 合理 |
| 09:24:34 | 3c5be5b4 | 8e213e1b | code completed | `interroute_2swap` | branch state, surface, baseline_algorithm, local_search, state, screening empty | code 读目标和接口，patch 匹配 |
| 09:32:05 | dfcff473 | 8e213e1b | hypothesis retry partial | interroute schedule refine | screening/runtime feedback, same-branch weak lesson | 第一次因 branch_lesson_usage mismatch 被 quality block，说明 guard 生效 |
| 09:32:52 | c7481160 | 8e213e1b | hypothesis partial | capped interroute | preserved/contrasted same-branch lesson | 结构化 lesson 修正后通过 |
| 09:33:20 | 3a8e5b38 | 8e213e1b | code completed | capped interroute | feedback + target source read receipt | code 仍同机制，deepening 合理但突破有限 |
| 09:38:03 | 66fc766a | 8e213e1b | hypothesis partial | route_merge_repair | runtime/screening feedback, rejected weak-positive interroute | target 从 local search 转 repair，lesson 真正改变方向 |
| 09:38:38 | 5f812842 | 8e213e1b | code completed | route_merge_repair | branch state, destroy/local source refs | code 与转向匹配 |
| 09:43:46 | 08d2938c | e4b00114 | hypothesis partial | create `route_compaction.py` | avoided interroute/route_merge, clean fork diversity | clean fork 合理 |
| 09:44:22 | 5c3929bd | e4b00114 | code completed | route_compaction | route_compaction/destroy/local source, surface | 新文件和 scheduler wiring 可审计 |
| 09:53:41 | c31d9706 | e4b00114 | hypothesis failed | route compaction schedule | target intent binding mismatch | guard 阻止 formal hypothesis 背离 selected intent |
| 09:54:30 | 8f4e4477 | e4b00114 | hypothesis partial | route_compaction modify | screening/runtime feedback | same-mechanism refine 合理 |
| 09:54:59 | baece04d | e4b00114 | code completed | multi-order compaction | route_compaction target source | code 扩大尝试路径，但没有先验证 activation/effect |
| 10:00:02 | f8f6258a | e4b00114 | hypothesis partial | capacity_tight_regret_repair | route compaction no-effect feedback, runtime | target 转 repair ordering，质量较好 |
| 10:00:35 | 5f04c571 | e4b00114 | code completed | capacity_tight_regret | destroy/scheduler/route_compaction source | code 符合 hypothesis |
| 10:07:03 | bda63bc4 | e4b00114 | hypothesis failed | capacity activation schedule | same mechanism only violation | guard 要求不越过 protected mechanism/clean fork policy |
| 10:08:10 | 92ecbb10 | e4b00114 | hypothesis partial | capacity_tight scheduler refine | R06 weak positive and loss feedback | 研究上最合理的 follow-up 之一 |
| 10:08:39 | 4e363c4a | e4b00114 | code completed | scarcity trigger | branch state, destroy/scheduler source | code 符合 but trigger 未奏效 |
| 10:13:39 | c3561de1 | da22cb9e | hypothesis partial | plateau_reheat_acceptance | cross-branch failures, acceptance source | 避开 local/repair，方向合理 |
| 10:14:22 | 84c92267 | da22cb9e | code completed | plateau reheat | acceptance/scheduler/state source | code 引入接口，smoke passed |
| 10:19:23 | 19ea0318 | da22cb9e | hypothesis partial | route_limit_seed_diversification | no-effect feedback | clean direction but与 branch plateau mechanism 连续性弱 |
| 10:20:01 | 1ded0027 | da22cb9e | code failed | construction diversification | smoke failure: `_SimulatedAnnealing` lacks `observe_segment` | repair guidance 指向 object model/interface context，pre-protocol block |
| 10:24:35 | 646eef57 | c2d10bb6 | hypothesis partial | route_limit_seed_selection | active solver/source/runtime | construction branch clean |
| 10:25:37 | 1a736fda | c2d10bb6 | code completed | seed selector | construction/scheduler/state source | code 小，effect 未观测 |
| 10:31:08 | 09567826 | c2d10bb6 | hypothesis partial | alns_stagnation_probe | borrowed runtime evidence bridge lesson | 观测候选合理，但应服务后续而非当作质量轮 |
| 10:32:02 | 0abbdb34 | c2d10bb6 | code completed | stagnation probe | scheduler/construction source | code 不改变 solver 质量 |
| 10:37:59 | 88d5f998 | d3f1fa68 | hypothesis partial | cross_route_2opt | avoid scheduler/compaction lessons | novelty 有，但回到失败的 local-search cluster |
| 10:38:31 | 4d3bca93 | d3f1fa68 | code completed | cross_route_2opt | local_search/scheduler/state source | code 符合但 runtime-heavy 风险高 |
| 10:44:10 | 4f0b4f18 | 52a00dbd | hypothesis partial | ranked_temperature_acceptance | avoid local/compaction, contrast seed/probe lessons | acceptance family 转向合理 |
| 10:44:43 | bfd4ee4f | 52a00dbd | code completed | ranked temperature | acceptance/scheduler/state source | code 符合，触发 fresh replay 缺口 |

上下文是否包含要求中的关键信息:

- Problem mechanics: 是。hypothesis/code sessions 的 observation ledger 包含 problem summary、active solver design/map、operator registry、solver call graph。
- Active solver facts: 是。大多数 session 包含 `active_solver_design`、`active_solver_map`、`solver_algorithm_file_list`。
- 目标 source: 是。hypothesis 阶段通常看目标/邻近 source slices，code 阶段读取 target algorithm file 或 read receipt。
- Screening/runtime feedback: repair/后续 session 基本都有 `feedback.query_screening` 和 `feedback.query_runtime`。
- Cross-branch lessons: 是。12 个 formal candidate 都满足 branch_lesson_usage；但如第 6 节所述，真实研究方向改变有限。

主要上下文问题:

1. Hypothesis 阶段 source grounding 足够，但对“机制是否有 opportunity”判断仍弱，导致多轮在 activation/effect 不足的机制上扩展。
2. Code 阶段能读目标文件，但有时只读 read receipt 或 reused observation，可能不足以避免 object model/API 错误。`route_limit_seed_diversification` 的 smoke failure 暴露了这一点。
3. Runtime feedback 可见，但多为 low cached champion，LLM 仍围绕 runtime saturation 规划，实际不能把 runtime 作为优化信号。

## 5. 分支维度分析

### Branch 8e213e1b: interroute_2swap -> capped interroute -> route_merge_repair

- 研究脉络: 先补 VNS block swap 缺口，再降低该机制 runtime，最后从 local search 转到 repair-stage consolidation。
- 有效假设: R01、R02、R03 都是合理假设。R03 的 target/mechanism 转移说明 lesson usage 不只是统计。
- Code 质量: 三个候选都 contract/verification passed，telemetry wiring 有记录。
- 结果: R01 weak positive，R02 no effect，R03 regression。branch final abandoned，best checkpoint retained 为 R01/R02 系列之一，但 current head discarded。
- Rollback/abandon: 没有 rollback；R03 后 soft abandon 合理，因为 case loss 出现且 win-rate 失败。
- 研究深度: 中等。做了 same-mechanism refine 和 mechanism-family 转换，但没有对 opportunity/activation 做足诊断。

### Branch e4b00114: route_compaction -> multi-order compaction -> capacity_tight repair -> scarcity schedule

- 研究脉络: clean fork 避开 local-search/route_merge，尝试 postrepair sparse route evacuation；失败后转 repair ordering；再用 scheduler trigger refine weak-positive repair。
- 有效假设: R06/R07 是本 run 中最好的 branch-local deep research。R07 直接解释 R06 的正负 case 分布。
- Code 质量: 全部 formal candidate passed。另有 proposal blocks: target intent binding mismatch、same-mechanism/clean-fork policy block，说明 guard 对 target/action/mechanism 绑定有效。
- 结果: R04 weak-positive pair only，R05 no effect，R06 weak-positive with case signals，R07 regression。branch abandoned，lifecycle_blocks=1，reroute reason `clean_fork_after_branch_lifecycle_policy_block`。
- Abandon 合理性: 合理。最终 evidence quality_regression，case positive A-n54/E-n101，但 B-n52 loss，CI 低端负。
- 研究深度: 较好，但仍受 runtime low-confidence 与 tie-dominated screening 约束。

### Branch da22cb9e: plateau reheat acceptance -> failed construction diversification

- 研究脉络: clean branch 从 acceptance diversification 开始，避免继续增加 neighborhood；随后试图转 construction seed diversification。
- 有效假设: R08 acceptance reheat 合理，但 R08 no effect 后没有继续围绕 acceptance telemetry 做深挖，而是跳到 construction，branch coherence 弱。
- Code 质量: R08 passed；后续 construction diversification 在 code generation smoke 失败，原因是候选算法调用 `_SimulatedAnnealing.observe_segment` 时 object/interface 不一致。
- 结果: formal 只有 R08，case/pair 全 tie，branch 仍 explore/discarded。
- Follow-up 合理性: 不应继续直接同分支探索，除非先明确 acceptance telemetry/segment observation 是否真实工作。
- 研究深度: 弱到中等。方向多样，但 branch-local 深度不足。

### Branch c2d10bb6: route_limit_seed_selection -> alns_stagnation_probe

- 研究脉络: 从 construction seed basin selection 开始，no effect 后转 scheduler observability probe。
- 有效假设: R09 是 clean mechanism；R10 是观测性候选，目标是解释 tie/no-effect，而非直接提升。
- Code 质量: 两轮都 passed，R10 不改 semantics，符合观测意图。
- 结果: 两轮全 tie。branch 保留 best checkpoint，但 current head discarded；runtime pressure count=2，plateau gate threshold met。
- Follow-up 合理性: R10 应产生下一轮 actionable bottleneck，但 run 在 12R 内没有形成利用该 probe 的后续 quality candidate。把 observability candidate 计入 formal screening 会稀释搜索效率。
- 研究深度: 对“为什么 tie”有意识，但闭环未完成。

### Branch d3f1fa68: cross_route_2opt_reconnect

- 研究脉络: clean branch 回到 VNS geometry move，新增 cross-route segment reconnect。
- 有效假设: 机制有 novelty，但它和早期 interroute_2swap 都属于 local-search runtime-heavy family。
- Code 质量: passed，telemetry wiring 完整。
- 结果: pair `1/3/12`，case no wins，negative B-n52/E-n101，branch abandoned。
- Abandon 合理性: 合理，CI `[-1.5,0.0]`，soft abandon non-positive CI。
- 研究深度: 低。branch 是单轮清洁探索，没有形成 deep research。

### Branch 52a00dbd: ranked_temperature_acceptance

- 研究脉络: clean branch 避开 local-search/compaction，回到 acceptance，但区别于 R08 的 reheat，改为 rank/quantile-aware uphill acceptance。
- 有效假设: 合理。保持 feasibility/route-limit，改变 acceptance distribution。
- Code 质量: passed，scheduler 记录 phase/move。
- 结果: pair `3/1/12`，case `0/0/8`，CI `[0.0,1.5]`。Telemetry effect zero diagnostic: acceptance phase present，但 improvement/best_delta 为 zero。
- Follow-up 合理性: fresh runtime follow-up required 是合理的，因为 objective tie + low cached runtime + pair-level signal 不能直接判断。问题是 replay 失败。
- 研究深度: 本可以形成下一步，但被 candidate-state retention 缺口打断。

## 6. 跨分支信息传递质量

框架层统计显示 branch lesson usage 已经比早期版本成熟:

- 12 个 formal candidate 都有 structured branch lesson usage，并满足 required linkage。
- 1 次 semantic mismatch 被 block，说明 guard 有效。
- avoid/contrast/preserve 都有 target_file/action/mechanism linkage。
- Cross-branch lessons 明确 proposal-only，不进入 DecisionFeatures，符合 v3。

但从研究效果看，信息传递更多是“合规可见”，不是“强研究转向”:

有效改变方向的例子:

- R03 从 `interroute_2swap` 转 `route_merge_repair`，明确 reject local-search runtime saturation。
- R04 clean fork 到 `route_compaction.py`，避开 interroute/route_merge。
- R06 从 route compaction 转 `capacity_tight_regret_repair`，避开 postrepair evacuation/local-search。
- R10 借用 runtime evidence bridge，提出 `alns_stagnation_probe`。
- R12 避开 local-search/compaction cluster，选择 acceptance rank-scaling。

弱或表层的例子:

- R02 结构上 preserve/contrast R01，但仍是同一 local-search family 的扫描策略调整，实际 no effect。
- R05 对 R04 做 multi-order 扩展，但没有先验证 compaction opportunity，导致更复杂但仍 no effect。
- R11 虽然 avoided/contrasted 多个 lesson，但又回到 local-search geometry move，和早期 runtime-heavy risk 相似。

关键判断:

Cross-branch lessons 已经能阻止一部分重复和 schema mismatch，但没有足够强地驱动“机制机会验证优先”。后续应该把 lessons 从“我避免/对比了某机制”推进到“上一机制失败的可观测因果是什么，本机制改变哪个 causal variable，如何在 telemetry 中验证”。

## 7. Fresh runtime replay 缺陷分析

最后状态:

```json
{
  "action": "replay",
  "attempt_kind": "fresh_runtime_replay",
  "branch_id": "52a00dbd-63a1-4742-9f4f-507544f883f7",
  "reason": "fresh runtime replay missing workspace,hypothesis",
  "scheduler_reason": "fresh_champion_runtime_replay_followup",
  "scheduler_slot": "exploit_weak_positive",
  "formal_protocol_evaluated": false,
  "counts_toward_max_rounds": false
}
```

发生条件:

- 触发候选是 R12 `0737548d-00a2-4545-9312-b40213ed268a`，target `policies/baseline_modules/acceptance.py`，mechanism `ranked_temperature_acceptance`。
- Screening evidence: case `0/0/8`，pair `3/1/12`，median `0.0`，CI `[0.0,1.5]`。
- Runtime evidence: `low_cached_champion`，`fresh_champion_required=true`，runtime aggregate excluded。
- Telemetry diagnostic: `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`，activation observed，但 best_delta/improvement_counts zero。
- Branch evidence generated `fresh_runtime_followup` with `followup_required=true` and `queue_intent=fresh_champion_runtime_replay`。
- Scheduler selected `exploit_weak_positive` + `replay_existing`。
- Finalizer found `post_finalizer_branch_code_status=discarded` and closure `blocked_missing_candidate_state` with missing `workspace,hypothesis`。

这代表的框架缺陷:

1. Candidate state retention 不完整。formal candidate artifact 有 patch ref 和 hypothesis id，但 replay 需要的 materialized workspace/hypothesis object 没有在 scheduler/finalizer 可恢复路径中保留。
2. Fresh runtime replay 的计划和执行之间缺少 closure contract。scheduler 可以选择 replay，但没有先验证 replay dependencies 是否 present 或可 rematerialize。
3. Branch code retention policy 与 replay policy 冲突。candidate code status 已 discarded，但 fresh runtime replay 又要求 candidate workspace。这两套 policy 没有握手。
4. status 中 `fresh_runtime_pending=false` 且 `scheduler_marker=fresh_champion_runtime_replay_closed`，但 closure 是 blocked，不是真正 replay completed。主会话若只看 pending=false 可能误判 replay 已处理。
5. 这不是 LLM 问题。LLM 已提交 candidate，Contract/Verification/Protocol 都过了，fresh replay 是 deterministic lifecycle/scheduler 的责任。

最低修复要求:

- formal candidate 必须持久化足以 rematerialize 的 state: hypothesis record、patch artifact、base champion hash、worktree snapshot/ref 或 deterministic materializer inputs。
- scheduler 选择 `fresh_champion_runtime_replay_followup` 前必须检查 candidate-state dependencies；缺失时应转为 explicit framework error，不应静默关闭 follow-up。
- branch finalizer 不得在 fresh replay required 的同一候选上先 discard 唯一 workspace，除非 replay 可从 artifact deterministic rebuild。
- status 应区分 `fresh_runtime_replay_closed_success`、`blocked_missing_candidate_state`、`not_attempted`，并把 blocked 计入 framework acceptance blocker。

## 8. v3/v0.4 设计符合性检查

符合项:

- LLM 输出没有直接进入 Decision。Hypothesis/code/lesson usage 都保存在 tainted artifacts 和 proposal/session 输出中。
- 12 个 formal candidates 的 Contract/Verification 都通过后才进入 Protocol。
- Decision reason 是结构化 reason codes，DecisionFeatures 没有自由文本 hypothesis 或 branch_lesson_usage。
- Cross-branch lesson observability 标记为 proposal-only，`decision_input_policy=excluded_from_decision_features`。
- Runtime evidence policy 标记 `standalone_optimization_signal=false`，低可信 runtime 没有作为独立 promotion signal。

不符合或有风险项:

- Candidate intent accounting 不可信。`candidate_intent_counts` 把 16 个都标为 observability_candidate，但实际 R01/R02/R03/R04/R05/R06/R07/R08/R09/R11/R12 都是质量机制改动，只有 R10 明显是 observability probe。
- Screening/runtime pressure 正确阻止 promotion，但 proposal/scheduler 被大量 low-cached runtime feedback 牵引，fresh replay 又无法执行，形成“看见问题但不能闭环”。
- Branch code status 和 evidence retention 的语义在 branch cards/status 中容易混淆。某些 branch 有 best checkpoint/last_valid，但 current head discarded；fresh replay 需要明确 candidate-state retention，而不是只保留 evidence summary。
- Observability candidate 若计入 max rounds，需要有独立价值判定。R10 这类 probe 不应该用 quality screening pass/fail 语义评价。

## 9. 是否升 20R

判断: 不应直接升 20R。

理由:

1. 12R 没有 validation/frozen/promotion，已足够显示搜索质量瓶颈，不需要用 20R 再证明。
2. fresh runtime replay 失败是 P0。20R 会增加更多 weak-positive/fresh-required 候选，但 replay 仍无法闭环。
3. runtime saturation 每轮都有，且大多 low_cached_champion，20R 可能主要放大 cached-runtime-driven planning。
4. Branch lesson usage 已经过 schema/semantic guard，但真实 causal transfer 不够强，20R 会产出更多 avoid/contrast 合规记录，而未必改善机制选择。
5. Candidate intent accounting 错误会污染 run-level 判断，影响主会话对“研究质量 vs 观测候选”的理解。

更合适的路径:

1. 修 P0 fresh replay/candidate retention。
2. 跑一个小规模 4R replay acceptance run，只验证 fresh runtime replay 能成功从 formal candidate artifact rematerialize。
3. 修 P1 runtime/observability accounting 后跑 8R，检查 weak-positive 是否能变成 actionable follow-up。
4. 只有当 replay closure 成功、runtime confidence 有 fresh champion evidence、observability candidate 不再污染 quality candidate 计数，再升 20R。

## 10. P0/P1/P2 建议

### P0: 修 fresh runtime replay 和 candidate-state retention

Acceptance criteria:

- 当 screening 产生 `fresh_runtime_required=true` 时，scheduler replay 能找到或重建 candidate workspace/hypothesis。
- `formal_candidate_patch_artifact_ref` + `hypothesis_id` + base champion hash 足以 deterministic rematerialize candidate。
- replay 成功时产生新的 protocol/runtime evidence ref；失败时状态为 explicit framework failure，不得标记为普通 closed。
- branch finalizer 的 discard policy 不会破坏 pending fresh replay。
- 增加测试覆盖: candidate discarded 后仍能 replay；missing hypothesis/workspace 时 status 明确 blocked，不吞掉。

### P0: 修 run/status 对 replay closure 的表达

Acceptance criteria:

- `fresh_runtime_pending=false` 不能单独表示成功关闭；必须有 `closure_status=completed|blocked_missing_candidate_state|not_applicable`。
- campaign_summary/status 明确列出 replay blocked count。
- 主会话能一眼看到: 本 run valid complete，但 fresh runtime replay blocked 是 framework blocker。

### P1: 修 candidate intent accounting

Acceptance criteria:

- quality candidate、observability candidate、diagnostic candidate 分开统计。
- R10 这类 `predicted_direction=exploratory`/probe candidate 不与 quality screening candidate 混同。
- run summary 的 `candidate_intent_counts` 与 formal hypothesis 内容一致，不能把全部 16 个都归为 observability。

### P1: 强化 branch lesson causal linkage

Acceptance criteria:

- lesson usage 不只要求 target/action/mechanism linkage，还要求 `changed_causal_variable` 和 `expected_observable_change`。
- same-branch refinement 必须说明上一轮失败是 activation 不足、effect zero、runtime budget、case subset loss、还是 opportunity poor。
- clean fork 必须说明和失败机制相比，改变的是 move family、activation trigger、search stage、budget profile 或 observability path 中哪一个。

### P1: Runtime evidence replay policy 前置化

Acceptance criteria:

- 当 `runtime_evidence_status=fresh_champion_required` 且 candidate 有 weak-positive/pair signal 时，优先 replay，而不是继续 proposal。
- replay dependency missing 时，不消耗 proposal attempt，并记录 framework repair required。
- Runtime aggregate excluded 时，LLM prompt 可以看 proposal guidance，但不能把 runtime 当优化目标。

### P2: Observability candidate 独立生命周期

Acceptance criteria:

- `alns_stagnation_probe` 这类候选跑完后必须产生可被下一轮使用的 structured bottleneck summary。
- Observability candidate 不按 quality win-rate 判断成功，而按 telemetry coverage/diagnostic usefulness 判断。
- 观测候选最多占固定比例预算，避免 12R 中占用 formal quality round 却没有后续使用。

### P2: 更细的 case-subset learning

Acceptance criteria:

- Weak-positive candidate 的 positive/negative cases 形成结构化 case subset lesson，例如 B-n52 loss 与 E-n101 win 的机制差异。
- 后续 hypothesis 必须显式选择 preserve/reject case subset signal，而不是只写 generic avoid/contrast。

## 11. 主会话可用决策

本 run 可以作为以下决策依据:

- 不升 20R，先修 P0/P1。
- 把 `52a00dbd/ranked_temperature_acceptance` 作为 fresh replay blocker 的复现对象。
- 把 `e4b00114/capacity_tight_regret_repair` 作为 branch-local weak-positive 研究样例，用于测试 lesson causal linkage。
- 把 `c2d10bb6/alns_stagnation_probe` 作为 observability candidate 生命周期测试对象。
- 把 `candidate_intent_counts` 统计修复列为报告接受条件，否则后续 run summary 仍会误导研究质量判断。

最终判断:

这组 12R 的 LLM 研究质量是“有方向、有结构化 lesson、有若干合理机制转向，但未形成可晋升候选”。框架质量是“v3 决策边界大体守住，但 fresh replay 和 candidate retention 没闭环”。因此当前最有价值的不是继续加轮数，而是修 replay/retention/intent accounting，然后用小 run 验证修复。
