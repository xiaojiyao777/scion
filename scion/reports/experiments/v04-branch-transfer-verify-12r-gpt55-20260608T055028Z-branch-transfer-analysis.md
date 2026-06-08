# Scion 12R 分支迁移实验后验分析

实验：`v04-branch-transfer-verify-12r-gpt55-12r-gpt55-20260608T055028Z-claw`  
Run root：`/home/clawd/research/scion-experiments/v04-branch-transfer-verify-12r-gpt55-12r-gpt55-20260608T055028Z-claw`  
Campaign：`/home/clawd/research/scion-experiments/v04-branch-transfer-verify-12r-gpt55-12r-gpt55-20260608T055028Z-claw/campaign`  
报告时间：2026-06-08

## 结论先行

这次 12R 是一次有效完成的 Scion campaign，不是卡死或 hang。`run_status.json` 显示 `status=finished`、`wrapper_exit_status=0`、`ended_at=2026-06-08T07:13:49Z`；`status.json` 与 `campaign_summary.json` 显示 `valid=true`、`complete=true`、`effective_rounds_completed=12`、`requested_rounds=12`、`stopped_reason=max_rounds_exhausted`。

但它不能证明 Scion agent 已经具备足够可靠的分支内研究深度或跨分支经验利用能力。它证明的是：

- 12R 调度、协议、contract、verification、decision 链路可以跑完。
- LLM 全部使用 `gpt-5.5`，trace 全部 ok。
- 分支 lesson 已经能进入 proposal 可见上下文，并且没有进入 DecisionFeatures。
- agent 会做一些同分支 refinement 和跨分支 avoid/contrast。

它没有证明的是：

- 没有 promotion、validation、frozen，也没有 accepted champion。
- 弱正信号没有被 fresh runtime 闭环验证。
- `weak_positive_transfer_count=0`，没有真实跨分支借用弱正机制。
- `branch_lesson_usage_present/satisfied` 更接近格式合规，只有有限的 proposal target 多样化影响。
- LLM 多次提出局部启发式补丁，但没有形成足够强的算法研究脉络。

建议不要把这次结果直接升级为 20R 质量实验。应先修 P0/P1 机制问题，重跑 12R 或做短程 targeted replay 验证，再决定是否进入 20R。

## 运行有效性与全局计数

| 项 | 结果 | 判断 |
|---|---:|---|
| wrapper 状态 | `finished`, exit 0 | 有效完成 |
| run validity | `valid=true`, `complete=true` | 有效 |
| 请求轮次 | 12 | 满足 |
| 有效完成轮次 | 12 | 满足 |
| campaign total rounds / steps | 14 | 包含 2 个非有效/非计数步骤 |
| formal screened candidates | 12 | 与有效轮次一致 |
| protocol evaluated candidates | 12 | 与有效轮次一致 |
| proposal attempts total | 14 | 包含 blocked/repairable attempt |
| run_validity proposal attempts | 13 | 与 summary 总 attempt 口径不同 |
| quality blocks | 1 | 合理 block |
| failure category | `contract_boundary_failure=1` | target intent 与 formal hypothesis 绑定不一致 |
| scheduler active slot blocks | 0 | 无 scheduler slot 阻塞 |
| branch lifecycle policy blocks | 0 | 无 lifecycle policy 阻塞 |
| fresh champion required | 6 | 对弱正验证形成实质压力 |
| promoted / validation / frozen | 0 / 0 / 0 | 没有进入后段确认 |
| LLM trace | 102 | 全部 ok |
| LLM model set | `['gpt-5.5']` | 满足模型要求 |

### 为什么 proposal_attempts_total=14，但 formal_screened_candidates=12

14 个 campaign steps 中，只有 12 个是有效 formal screened candidate。差异来自两个非有效步骤：

1. 第 7 步，branch `a0c28719` 的 `adaptive_neighborhood_budget` 完成了 screening，但 telemetry guard 失败，分类为 `telemetry_repairable`，`counts_toward=false`。失败原因是预算/telemetry 字段缺失：`solver_algorithm_phase_runtime_ms.alns`。它不是 formal counted candidate。
2. 第 12 步，branch `9fa9b486` 出现 proposal block，分类为 `contract_boundary_failure`，原因是 `target_intent_binding_mismatch`：target intent 选择 `clustered_worst_activation_gate`，formal hypothesis 却落到 `clustered_worst_removal`。该 attempt 被挡在 pre-protocol / contract 边界，未进入 formal screening。

因此：

- `proposal_attempts_total=14` 是 campaign attempt 口径。
- `screening=13` 是包含 telemetry repairable screening 的 protocol 口径。
- `formal_screened_candidates=12` 是 counted/effective formal candidate 口径。
- `quality_blocks=1` 对应第 12 步 contract boundary block。

这个 block 本身合理：formal hypothesis 不应偏离已绑定的 target intent，否则后续 Contract/Verification 无法证明 agent 是在实现被批准的研究意图。但它暴露了 proposal retry 机制问题：retry 应保留 selected intent 或显式重新生成 intent，而不是让 formal mechanism 名称漂移后再由 contract 拦截。

## LLM 调用核对

`agentic_session_trace_index` 显示 27 个 agentic session、102 个 LLM trace。所有 trace 的模型均为 `gpt-5.5`，状态均为 ok。request kind 分布为：

| request kind | count |
|---|---:|
| `hypothesis_target_intent` | 14 |
| `hypothesis` | 18 |
| `tool_selection` | 55 |
| `code` | 15 |

逐 session / 逐 LLM 调用摘要如下。每行的 call sequence 表示该 session 内 LLM 调用顺序与数量。

| Session | Branch | 阶段 | Call sequence | 产出/结果 |
|---|---|---|---|---|
| S01 `e399d980` | `f401e2f0` | hypothesis | target intent -> hypothesis | 选择 `route_merge_savings_vns`，目标 `local_search.py` |
| S02 `11c2fcb7` | `f401e2f0` | code | tool_selection x4 -> code | 修改 `local_search.py`，实现 route merge savings VNS |
| S03 `efbd6e58` | `f401e2f0` | hypothesis | target intent -> hypothesis | 同分支 refine `route_merge_savings_vns` |
| S04 `a8e91da6` | `f401e2f0` | code | tool_selection x3 -> code | 收窄/门控 local search merge 逻辑 |
| S05 `067d029c` | `862e8492` | hypothesis | target intent -> hypothesis | 新分支 `route_compaction_repair`，目标 `route_compaction.py` |
| S06 `20ede1b6` | `862e8492` | code | tool_selection x3 -> code | 创建/修改 `route_compaction.py`，加入 compaction repair |
| S07 `fb230b6b` | `862e8492` | hypothesis | target intent -> hypothesis | 同分支 refine route compaction |
| S08 `4bdfadcd` | `862e8492` | code | tool_selection x3 -> code | guarded two-stage compaction |
| S09 `cfb8e7df` | `c20b3ef7` | hypothesis | target intent -> hypothesis | 新分支 `load_slack_regret_repair`，目标 `destroy_repair.py` |
| S10 `09e08184` | `c20b3ef7` | code | tool_selection x3 -> code | 修改 destroy/repair 策略 |
| S11 `1acc4a1a` | `a0c28719` | hypothesis | target intent -> hypothesis | `objective_scaled_reheating`，目标 `acceptance.py` |
| S12 `40ba7568` | `a0c28719` | code | tool_selection x6 -> code | 修改 reheating/acceptance 机制 |
| S13 `e6bc72f1` | `a0c28719` | hypothesis | target intent -> hypothesis x2 | `adaptive_neighborhood_budget`，经历一次 hypothesis retry |
| S14 `aa857992` | `a0c28719` | code | tool_selection x4 -> code x2 | 修改 `scheduler.py`，后续 telemetry guard 判为 repairable |
| S15 `9c00b814` | `16869fe7` | hypothesis | target intent -> hypothesis x2 | `route_limit_seed_diversifier`，经历一次 hypothesis retry |
| S16 `92adb823` | `16869fe7` | code | tool_selection x6 -> code | 修改 `construction.py` |
| S17 `8155e7ba` | `16869fe7` | hypothesis | target intent -> hypothesis | `bounded_interroute_2opt_bridge`，目标 `local_search.py` |
| S18 `64ddf74b` | `16869fe7` | code | tool_selection x2 -> code | 修改 bounded inter-route 2-opt bridge |
| S19 `6a406a37` | `16869fe7` | hypothesis | target intent -> hypothesis | `vns_bridge_schedule_gate`，目标 `scheduler.py` |
| S20 `c27ca3c9` | `16869fe7` | code | tool_selection x5 -> code x2 | 集成 bridge schedule gate，telemetry effect zero |
| S21 `024774a1` | `9fa9b486` | hypothesis | target intent -> hypothesis | `clustered_worst_removal`，目标 `destroy_repair.py` |
| S22 `147ad216` | `9fa9b486` | code | tool_selection x6 -> code | 修改 clustered worst removal |
| S23 `d64c7c38` | `9fa9b486` | failed hypothesis | target intent -> hypothesis x2 | blocked：`clustered_worst_activation_gate` 与 `clustered_worst_removal` 绑定不一致 |
| S24 `f6fcfdec` | `9fa9b486` | hypothesis | target intent -> hypothesis | 回到 `clustered_worst_removal` refinement |
| S25 `efccab61` | `9fa9b486` | code | tool_selection x4 -> code | 修改 `scheduler.py`，调度 clustered worst removal |
| S26 `a3b20a5c` | `c80734fb` | hypothesis | target intent -> hypothesis | `route_limit_savings_merge_filter`，目标 `construction.py` |
| S27 `8e2194bd` | `c80734fb` | code | tool_selection x6 -> code | 修改 construction savings merge filter |

工具调用总体合理：code session 先用 tool selection 读取目标文件、上下文和相关实现，再生成 patch。没有证据显示 LLM 使用非 `gpt-5.5`，也没有 code session 失败后被静默吞掉。

## 逐轮分析

### Round 1：branch `f401e2f0`，`route_merge_savings_vns`

- Hypothesis 上下文：包含 CVRP problem mechanics、baseline solver facts、`local_search.py` 目标源码、active solver map、初始 research surface；此时没有历史 screening feedback，也没有真实 branch lesson。
- 上下文充分性：对首轮足够，但偏重，包含较多通用 solver/source 信息。
- Hypothesis 产出：提出 route merge savings VNS，在 local search 后尝试 savings-driven route merge。
- 机制差异：与普通局部搜索不同，主张跨 route merge；但仍是局部启发式增量。
- Code 实现：修改 `policies/baseline_modules/local_search.py`，加入 route merge savings VNS 逻辑。
- 边界判断：修改在 solver policy/problem-owned 层，没有改 Scion generic core；没有把 CVRP 语义泄漏到 Decision/Contract core。
- Protocol/Decision：screening case 0/0/8，pair 0/0/16，median delta 0，CI 0..0，runtime high/neutral。Decision `continue_explore`，scheduler 创建后续探索。
- 评价：首轮产生中性结果，不构成可推广 lesson。

### Round 2：branch `f401e2f0`，refine `route_merge_savings_vns`

- Hypothesis 上下文：看到了 Round 1 的 neutral/runtime saturation 反馈、同分支机制、目标源码和 branch lesson usage context。
- 上下文充分性：足够；feedback 可见，但上下文开始包含较多框架约束文本。
- Hypothesis 产出：继续 route merge savings VNS，加入更保守的 slack/endpoint gate。
- 机制差异：同一机制的收窄 refine，不是新方向。
- 是否借鉴历史：借鉴同分支 neutral，试图降低破坏性；没有跨分支可借鉴对象。
- Code 实现：继续修改 `local_search.py`，更保守地触发 merge。
- Framework 行为：screening case 0/0/8，pair 0/2/14，median 0，CI -0.5..0；Decision `abandon`，branch lifecycle archive/soft abandon。
- 评价：分支内 depth 有一次真实 refine，但第二步变差，abandon 合理。

### Round 3：branch `862e8492`，`route_compaction_repair`

- Hypothesis 上下文：包含前一分支失败 lesson、active solver facts、target candidates/source map、runtime feedback，能看到 route merge VNS 已无效/变差。
- 上下文充分性：足够，且比前两轮更有 branch context。
- Hypothesis 产出：创建 `route_compaction.py`，提出 route compaction repair。
- 机制差异：从 local search merge 转到 repair/compaction，方向有差异。
- 是否借鉴：主要 avoid 上一分支 route merge failure，换到 repair surface；不是 borrow。
- Code 实现：新增/修改 `route_compaction.py`，实现 compact overloaded/fragmented route 的 repair pass。
- Framework 行为：screening case 0/0/12，pair 2/2/20，median 0，CI 0..0；Decision `continue_explore`，标记 weak positive retained。
- 评价：出现 pair-level weak positive，但 case-level 全 tie。值得 follow-up，但不够 promotion。

### Round 4：branch `862e8492`，refine `route_compaction_repair`

- Hypothesis 上下文：看到了 Round 3 weak positive、runtime low/cached、branch lesson usage context。
- 上下文充分性：足够，但 weak-positive 的具体“哪些实例/哪些机制有效”可见度仍偏弱。
- Hypothesis 产出：guarded two-stage compaction refinement。
- 机制差异：同机制内 refine，尝试让 compaction 更保守/分阶段。
- 是否借鉴：有同分支 preserve/refine，但未跨分支 borrow。
- Code 实现：继续修改 `route_compaction.py`。
- Framework 行为：screening case 0/0/8，pair 0/0/16，median 0，CI 0..0；`fresh_champion_required=true`；Decision `continue_explore`，scheduler 走 weak-positive follow-up。
- 评价：弱正没有被放大；fresh champion requirement 使结果不能作为强信号落定。

### Round 5：branch `c20b3ef7`，`load_slack_regret_repair`

- Hypothesis 上下文：包含 route merge abandon、route compaction weak/no-effect、cross-branch map。
- 上下文充分性：足够；branch lessons 可见。
- Hypothesis 产出：转向 `destroy_repair.py`，提出 load slack regret repair。
- 机制差异：从 compaction 转到 destroy/repair regret 插入/修复，属于不同算法 surface。
- 是否借鉴：主要 contrast/avoid 前面 merge/compaction；没有 borrow weak-positive compaction。
- Code 实现：修改 `destroy_repair.py`。
- Framework 行为：screening case 0/1/7，pair 1/4/11，median 0，CI -11..0；Decision `abandon`，质量回归。
- 评价：branch 立即失败，abandon 合理。

### Round 6：branch `a0c28719`，`objective_scaled_reheating`

- Hypothesis 上下文：看到了 local_search、compaction、destroy_repair 的历史；包含 acceptance target/source。
- 上下文充分性：足够；上下文偏重但能支撑换 surface。
- Hypothesis 产出：修改 acceptance reheating，使温度/接受率按 objective scale 调整。
- 机制差异：从结构改造转到搜索接受策略，差异明确。
- 是否借鉴：更多是 avoid 结构修复失败，换到 acceptance；没有直接借用弱正。
- Code 实现：修改 `acceptance.py`。
- Framework 行为：screening case 0/0/8，pair 0/0/16，median 0，CI 0..0；`fresh_champion_required=true`；Decision `continue_explore`。
- 评价：无效但未伤害，继续探索可接受。

### Round 7：branch `a0c28719`，`adaptive_neighborhood_budget`

- Hypothesis 上下文：包含 Round 6 no-effect/fresh-required、scheduler surface、runtime budget/telemetry guidance。
- 上下文充分性：足够；但 telemetry contract 风险没有被 LLM/框架提前挡住。
- Hypothesis 产出：调度层 adaptive neighborhood budget。
- 机制差异：从 acceptance 转 scheduler/budget，差异明确。
- 是否借鉴：尝试利用 runtime/scheduler 反馈，属于 framework-guided proposal。
- Code 实现：修改 `scheduler.py`，加入 adaptive neighborhood budget。
- Framework 行为：screening case 0/1/7，pair 1/5/10，median -0.5，CI -9..0；telemetry guard failed，`telemetry_repairable`，missing `solver_algorithm_phase_runtime_ms.alns`，`counts_toward=false`。
- 评价：这是一次工程/telemetry 失败，不应计为有效候选。repairable 处理合理，但说明 telemetry declaration 与 runtime surface 仍有一致性风险。

### Round 8：branch `16869fe7`，`route_limit_seed_diversifier`

- Hypothesis 上下文：包含前面 branch failures、telemetry repairable、cross-branch lessons、construction target/source。
- 上下文充分性：足够；上下文偏重。
- Hypothesis 产出：construction route-limit seed diversifier。
- 机制差异：转到初始解/seed 多样性，差异明确。
- 是否借鉴：主要 avoid 前面 scheduler/repair 失败，换 surface。
- Code 实现：修改 `construction.py`。
- Framework 行为：screening case 0/0/8，pair 0/0/16，median 0；`fresh_champion_required=true`；Decision `continue_explore`。
- 评价：没有效果。

### Round 9：branch `16869fe7`，`bounded_interroute_2opt_bridge`

- Hypothesis 上下文：看到了 construction no-effect、早期 local_search merge failure、compaction weak positive。
- 上下文充分性：足够。
- Hypothesis 产出：bounded inter-route 2-opt bridge。
- 机制差异：回到 local search，但不是 route merge savings，而是 bounded 2-opt bridge。
- 是否借鉴：有 contrast：避免 Round 1/2 大幅 merge，保留 bounded bridge 思路；不是直接 borrow。
- Code 实现：修改 `local_search.py`。
- Framework 行为：screening case 0/0/8，pair 2/2/12，median 0，CI 0..0；`fresh_champion_required=true`；Decision `continue_explore`，weak-positive。
- 评价：出现第二个 pair-level weak positive，但没有 case-level 改善。

### Round 10：branch `16869fe7`，`vns_bridge_schedule_gate`

- Hypothesis 上下文：看到了 Round 9 weak positive、fresh required、local_search bridge 机制、scheduler target。
- 上下文充分性：足够；对 weak-positive 的实例级解释仍不足。
- Hypothesis 产出：scheduler gate，使 VNS bridge 更有选择地触发。
- 机制差异：同 branch 从 local_search implementation 转 scheduler activation gate。
- 是否借鉴：同分支 preserve/refine，尝试让弱正机制更可控。
- Code 实现：修改 `scheduler.py`。
- Framework 行为：screening case 0/0/8，pair 0/0/16，median 0；`fresh_champion_required=true`；telemetry effect zero diagnostic；Decision `continue_explore`。
- 评价：refine 没有放大弱正，activation 可能未真正改变执行路径。

### Round 11：branch `9fa9b486`，`clustered_worst_removal`

- Hypothesis 上下文：包含多个 no-effect/abandon、两个 weak positive、cross-branch map、destroy_repair target/source。
- 上下文充分性：足够，且有明确历史失败可 avoid。
- Hypothesis 产出：clustered worst removal。
- 机制差异：回到 destroy/repair，但避开 Round 5 的 load slack regret repair，改用 cluster-aware worst removal。
- 是否借鉴：真实 contrast 了 Round 5 destroy_repair 失败；没有 borrow Round 9 weak positive。
- Code 实现：修改 `destroy_repair.py`。
- Framework 行为：screening case 0/0/8，pair 3/2/11，median 0，CI -0.5..0.5；Decision `continue_explore`，weak-positive。
- 评价：这是本次最强弱正之一，pair wins 多于 losses，但 case-level 仍未胜出。

### Round 12：branch `9fa9b486`，proposal block

- Hypothesis 上下文：看到了 Round 11 weak-positive follow-up 需求。
- Hypothesis 产出：target intent 选中 `clustered_worst_activation_gate`，formal hypothesis 却绑定到 `clustered_worst_removal`。
- 机制差异：formal 与 selected intent 不一致，因此不能进入 code/protocol。
- Framework 行为：Contract/quality block，`contract_boundary_failure=1`，`target_intent_binding_mismatch`；`counts_toward=false`。
- 评价：block 合理，说明 contract 边界有效。但 proposal retry 没能稳定保持 target intent，是 P1 机制问题。

### Round 13：branch `9fa9b486`，refine `clustered_worst_removal`

- Hypothesis 上下文：包含 Round 11 weak positive、Round 12 contract block、same-branch follow-up 需求。
- 上下文充分性：足够。
- Hypothesis 产出：继续 clustered worst removal，但把改动放到 scheduler/activation 调度层。
- 机制差异：同分支从 removal implementation 转 activation/scheduling refine。
- 是否借鉴：同分支 preserve/refine；没有跨分支 borrow。
- Code 实现：修改 `scheduler.py`，调度 clustered worst removal。
- Framework 行为：screening case 0/0/8，pair 3/2/11，median 0，CI -0.5..0.75；Decision `continue_explore`，scheduler 后续 parked lineage/pending retry diagnostic。
- 评价：弱正保持但仍未过 case gate，也未触发 fresh validation。

### Round 14：branch `c80734fb`，`route_limit_savings_merge_filter`

- Hypothesis 上下文：包含全部历史、cross-branch map、多个 weak positives、多个 no-effect/abandon。
- 上下文充分性：足够但偏重。此时 prompt 中历史很多，但转化成具体机制借用的证据有限。
- Hypothesis 产出：construction route-limit savings merge filter。
- 机制差异：转回 construction/savings filter，试图避免 route merge failure 的过激 merge。
- 是否借鉴：有 avoid/contrast，但不是 borrow weak positive。
- Code 实现：修改 `construction.py`。
- Framework 行为：screening case 0/0/8，pair 0/0/16，median 0，CI 0..0；`fresh_champion_required=true`；Decision `continue_explore`；达到 max rounds。
- 评价：无效收尾。

## 逐轮结果表

| R | Branch | Mechanism | Target | Effective | Signal | Case W/L/T | Pair W/L/T | Decision / lifecycle |
|---:|---|---|---|---|---|---|---|---|
| 1 | `f401e2f0` | `route_merge_savings_vns` | `local_search.py` | yes | runtime_regression/neutral | 0/0/8 | 0/0/16 | continue_explore |
| 2 | `f401e2f0` | `route_merge_savings_vns` refine | `local_search.py` | yes | quality_regression | 0/0/8 | 0/2/14 | abandon |
| 3 | `862e8492` | `route_compaction_repair` | `route_compaction.py` | yes | weak_positive | 0/0/12 | 2/2/20 | continue_explore |
| 4 | `862e8492` | compaction refine | `route_compaction.py` | yes | no_effect | 0/0/8 | 0/0/16 | continue_explore |
| 5 | `c20b3ef7` | `load_slack_regret_repair` | `destroy_repair.py` | yes | quality_regression | 0/1/7 | 1/4/11 | abandon |
| 6 | `a0c28719` | `objective_scaled_reheating` | `acceptance.py` | yes | no_effect | 0/0/8 | 0/0/16 | continue_explore |
| 7 | `a0c28719` | `adaptive_neighborhood_budget` | `scheduler.py` | no | telemetry_repairable | 0/1/7 | 1/5/10 | non-counted repair |
| 8 | `16869fe7` | `route_limit_seed_diversifier` | `construction.py` | yes | no_effect | 0/0/8 | 0/0/16 | continue_explore |
| 9 | `16869fe7` | `bounded_interroute_2opt_bridge` | `local_search.py` | yes | weak_positive | 0/0/8 | 2/2/12 | continue_explore |
| 10 | `16869fe7` | `vns_bridge_schedule_gate` | `scheduler.py` | yes | no_effect | 0/0/8 | 0/0/16 | continue_explore |
| 11 | `9fa9b486` | `clustered_worst_removal` | `destroy_repair.py` | yes | weak_positive | 0/0/8 | 3/2/11 | continue_explore |
| 12 | `9fa9b486` | intent mismatch | n/a | no | contract_boundary_failure | n/a | n/a | quality block |
| 13 | `9fa9b486` | clustered worst scheduling refine | `scheduler.py` | yes | weak_positive | 0/0/8 | 3/2/11 | continue_explore / park |
| 14 | `c80734fb` | `route_limit_savings_merge_filter` | `construction.py` | yes | no_effect | 0/0/8 | 0/0/16 | max rounds |

## Contract / Verification / Protocol / Decision / Lifecycle / Scheduler

### Contract

Contract 边界总体有效。唯一 quality block 是 Round 12 的 target-intent binding mismatch。该 block 阻止了 formal hypothesis 与 selected intent 不一致的 proposal 进入 code/protocol，符合 Scion 的 proposal governance 边界。

问题不在 Contract 判断，而在 proposal retry：同一 session 内 target intent 与 formal hypothesis 机制名称漂移，说明 hypothesis 生成器没有稳定服从 target-intent binding。

### Verification

Verification 层成功筛掉了 telemetry repairable 的 non-counted candidate。Round 7 的 runtime/telemetry 字段缺失没有污染 formal counted 结果。

仍有风险：telemetry declaration 与 runtime observation 的字段一致性不足，会让 agent 在 scheduler/budget 类 proposal 上浪费有效实验时间。

### Protocol

Protocol 执行 13 次 screening，其中 12 次 counted formal screened candidate，1 次 telemetry repairable non-counted。没有 validation/frozen stage：

- `screening=13` 是 protocol 操作口径。
- `formal_screened_candidates=12` 是 counted 口径。
- `validation=0`、`frozen=0`。

Protocol 没有异常终止；但它没有为 weak positive 提供足够明确的 fresh runtime replay 闭环。

### Decision

Decision 没有读取 branch lessons 作为决策输入，保持了 DecisionFeatures 边界。runtime evidence policy 中所有 runtime evidence 均 `decision_features_excluded_count=13`，cross-branch observability 也标记 `proposal_observability_only` / `excluded_from_decision_features`。

Decision 的保守性合理：所有 effective candidates 的 case-level wins 都是 0，没有候选达到 promotion 条件。pair-level weak positives 被保留/跟进，而不是直接 promote。

### Lifecycle

Lifecycle 行为基本合理：

- `f401e2f0` 在第二轮变差后 abandon。
- `c20b3ef7` 单轮质量回归后 abandon。
- `862e8492` 与 `9fa9b486` 弱正后被保留/park。
- 没有 `branch_lifecycle_policy_blocks`。

主要不足是 weak-positive branch 被 park 前没有完成 fresh replay/validation closure。

### Scheduler

Scheduler 没有 active slot block。它能在 abandon 后开新分支，也能对 weak positive 做 same-branch follow-up。

但 scheduler 对 `fresh_champion_required` 的响应偏弱：多次记录 fresh requirement，却继续产生 proposal，而不是安排明确的 fresh champion replay 或 validation probe。

## Fresh champion 对 promotion / validation 的影响

`fresh_champion_required_count=6` 有实质影响，但不是“错杀强候选”的证据。

它影响了：

- Round 4、6、8、9、10、14 等 no-effect/tie 或 weak-positive screening 的 runtime confidence。
- `runtime_aggregate_excluded_count=11`、`low_cached_champion_count=12` 表明大多数 runtime evidence 只能作为 guidance/audit，不能作为独立优化信号。
- weak positive branch 无法从 pair-level signal 升级到 validation/frozen。

它没有影响到：

- 没有任何候选拥有 case-level positive 胜出后被 fresh champion 挡住。
- promotion 为 0 的主因仍是算法效果不足：case wins 全为 0，CI 大多覆盖 0 或偏负。

因此 fresh champion 是“弱正闭环缺失”的核心机制问题，而不是本次无 promotion 的唯一原因。

## 分支维度分析

### Branch `f401e2f0`：route merge savings VNS

研究脉络：从 route merge savings VNS 开始，第二轮做更保守的 merge gate refine。

分支内深度：有一次真实 refine，且 refine 明确针对首轮 neutral/潜在 regression。但第二轮 pair loss 增加，说明 refine 没有解决机制问题。

生命周期：Round 2 abandon 合理。

弱正信号：无。

判断：这是一个失败分支，提供了“避免激进 route merge/local_search merge”的 lesson。后续分支确实有一些 avoid/contrast，但没有精细利用失败原因。

### Branch `862e8492`：route compaction repair

研究脉络：从 route compaction repair 创建新 file/surface，Round 4 做 guarded two-stage refine。

分支内深度：有效但有限。Round 3 有 pair-level weak positive，Round 4 refine 变成 no-effect，没有转化。

生命周期：保留 best checkpoint 后 park/slot reclaim 合理。

弱正信号：Round 3 pair 2/2/20，case all tie，属于弱正而不是 promotion signal。

判断：这是第一个有研究价值的 branch，但缺少 fresh replay 与实例级诊断，导致 weak positive 无法变成后续可借用机制。

### Branch `c20b3ef7`：load slack regret repair

研究脉络：从 compaction 转向 destroy/repair 的 load slack regret repair。

分支内深度：单轮失败，无深度。

生命周期：Round 5 quality regression 后 abandon 合理。

弱正信号：无。

判断：失败分支。它对后续 `clustered_worst_removal` 有 contrast 意义：后者仍走 destroy/repair，但避开 load-slack regret。

### Branch `a0c28719`：acceptance / adaptive budget

研究脉络：Round 6 改 acceptance reheating；Round 7 转 scheduler adaptive neighborhood budget。

分支内深度：机制跨度较大，不是围绕同一算法假设逐步深入。Round 7 更像换 surface，而不是 refinement。

生命周期：Round 7 telemetry repairable 后进入 diagnostic/repair 状态合理。

弱正信号：无。

判断：算法研究价值弱，工程诊断价值高。它暴露 scheduler/budget telemetry 字段一致性问题。

### Branch `16869fe7`：construction seed / local-search bridge / scheduler gate

研究脉络：从 construction seed diversifier 到 bounded inter-route 2-opt bridge，再到 VNS bridge schedule gate。

分支内深度：中等。Round 9 的 bounded bridge 弱正后，Round 10 尝试 scheduler activation gate，是一次合理的同分支 follow-up。

生命周期：继续探索后未能提升，最终无 promotion。

弱正信号：Round 9 pair 2/2/12，case all tie。Round 10 no-effect 且 telemetry effect zero。

判断：有研究脉络，但 weak-positive 机制没有被定位清楚，scheduler gate 可能没有实际改变执行路径。

### Branch `9fa9b486`：clustered worst removal

研究脉络：Round 11 提出 clustered worst removal，Round 12 proposal retry 失败，Round 13 回到同一机制并转 scheduler refine。

分支内深度：本次最好。它在 destroy/repair surface 上避开了 Round 5 的失败方式，pair-level wins 多于 losses，并在 follow-up 中保持信号。

生命周期：weak-positive follow-up 合理；Round 12 block 合理；Round 13 后 park 也可解释为 runtime evidence exhausted。

弱正信号：Round 11 与 Round 13 均 pair 3/2/11，case all tie。

判断：这是最接近可研究方向的 branch。但没有 fresh replay/validation，因此不能证明真实算法提升。

### Branch `c80734fb`：route limit savings merge filter

研究脉络：最后一轮 clean fork，回到 construction savings filter。

分支内深度：单轮，无深度。

生命周期：max rounds exhausted。

弱正信号：无。

判断：更多像为了覆盖新 surface/满足 novelty pressure 的 proposal，而不是对前面弱正机制的延展。

## 跨分支 lesson 影响分析

campaign_summary 的最终 cross-branch observability 计数：

| 指标 | 值 | 解读 |
|---|---:|---|
| `branch_lesson_record_count` | 30 | summary 基于 step history 记录丰富 |
| `branch_lesson_usage_requirement_count` | 14 | 每个 attempt 基本都有 usage 要求 |
| `branch_lesson_usage_present_count` | 12 | formal proposals 多数填写了 usage |
| `branch_lesson_usage_satisfied_count` | 12 | 形式检查通过 |
| `borrowed_lesson_count` | 0 | 没有跨分支 borrow |
| `avoided_lesson_count` | 27 | 大量 avoid |
| `contrasted_lesson_count` | 12 | 有 contrast |
| `preserved_same_branch_lesson_count` | 3 | 少量同分支 preserve |
| `weak_positive_transfer_count` | 0 | 弱正没有跨分支迁移 |
| `cross_branch_map_seen_count` | 12 | proposal 端可见 |

### 是否是真实使用

结论：部分真实，主要是 broad avoid/contrast；不是强意义上的经验迁移。

真实影响证据：

- `route_merge_savings_vns` 失败后，后续没有继续大规模 route merge，而是转向 compaction、destroy/repair、acceptance、construction 等不同 surface。
- `load_slack_regret_repair` 失败后，后续 `clustered_worst_removal` 仍走 destroy/repair，但换成 cluster-aware worst removal，具有 contrast。
- `bounded_interroute_2opt_bridge` 弱正后，同 branch 尝试 scheduler gate，这属于 same-branch preserve/refine。
- `clustered_worst_removal` 弱正后，Round 13 继续同一 branch refine。

形式合规证据：

- `usage_present=12`、`usage_satisfied=12` 主要说明 prompt/schema 字段填写，不等于 algorithmic influence。
- `borrowed_lesson_count=0` 说明没有跨分支把弱正机制作为可复用资产。
- `weak_positive_transfer_count=0` 说明弱正只停留在本分支 follow-up，没有成为 clean fork 的 proposal seed。
- 很多新 branch 只是换 target file 或换算法 surface，并没有把之前 lesson 转化为明确的机制约束。

### 为什么 weak_positive_transfer_count=0

原因不是 Decision 没看到 lesson。Decision 正确地只读 DecisionFeatures，lesson 被排除在 DecisionFeatures 外。

更可能的原因是 proposal visibility 到 hypothesis/code 的转化不足：

- weak-positive records 被 LLM 当作“可提及历史”，而不是“必须 borrow/preserve/validate 的机制资产”。
- scheduler 能做 same-branch follow-up，但 clean fork 没有强制从 weak-positive branch 中 borrow 一个具体 activation/effect path。
- branch lesson verifier 对 present/satisfied 的要求偏 schema 合规，没有要求 code 层体现 borrow/preserve。
- weak-positive 本身没有 fresh runtime closure，LLM 也缺少实例级因果解释，因此很难被安全迁移。

这符合本实验观察：avoid/contrast 多，borrow 为 0，weak-positive transfer 为 0。

## 上下文充分性与过重程度

Hypothesis 阶段普遍能看到：

- problem mechanics：CVRP objective、route/capacity/solver 机制。
- active solver facts：baseline solver pipeline、active algorithm facts、allowed research surfaces。
- target files/source：目标 file 的源码或摘要、source receipts、active solver map。
- screening/runtime feedback：从 Round 2 起可见上一轮/同分支/跨分支 screening feedback。
- branch lessons/cross-branch lessons：从有历史后，proposal 端能看到 branch lesson usage context 与 cross-branch map。

因此“上下文不足”不是主要失败原因。更准确的判断是：上下文足够但偏重，且 lesson 的语义强度不足。LLM 能看到很多信息，但 prompt/schema 没有强迫它把 weak-positive lesson 转化为具体 borrow/preserve 的机制和代码约束。

Code 阶段普遍能看到：

- approved hypothesis。
- code quality rules。
- target file 当前内容。
- branch-current integration files。
- telemetry identity rules。
- repair attribution / typed edit 规范。

Code tool usage 合理。主要问题不是 code session 不会改，而是 hypothesis 的算法机制多数弱，且 weak-positive 后续缺乏 fresh replay 和可迁移化。

## Generic Scion 边界与 CVRP 语义泄漏

本次 candidate code 只修改 solver/baseline policy 层文件：

- `policies/baseline_modules/local_search.py`
- `policies/baseline_modules/route_compaction.py`
- `policies/baseline_modules/destroy_repair.py`
- `policies/baseline_modules/acceptance.py`
- `policies/baseline_modules/scheduler.py`
- `policies/baseline_modules/construction.py`

没有证据显示 CVRP 语义被写入 Scion generic governance core，例如 Contract、Decision、Protocol、Scheduler core policy 的通用判定层。Decision 仍只读 DecisionFeatures，branch lessons 是 proposal observability only。

这点是本次 run 的正面结果：问题域算法修改与 Scion 框架治理边界基本分离。

## 框架问题、算法难度、LLM 行为问题的区分

### 框架问题

- Fresh champion required 记录了 6 次，但没有形成明确 fresh replay/validation closure。
- branch lesson usage satisfied 不足以证明真实 borrow/preserve。
- weak-positive transfer 为 0，说明跨分支迁移机制未激活。
- proposal retry 可能漂移 target intent，导致 contract boundary block。
- telemetry declaration/runtime surface 在 scheduler budget 类 proposal 上有一致性风险。

### 问题域算法难度

- CVRP baseline 上的小启发式修改很容易变成 tie/no-effect。
- 本次所有 counted candidates 的 case wins 都是 0，说明没有候选产生足够稳定的实例级改善。
- pair-level wins 偶尔出现，但 CI 和 case-level gate 不支持 promotion。

### LLM 行为问题

- LLM 能生成机制名、目标文件和代码，但很多 proposal 是局部启发式探索，缺少明确因果实验设计。
- 面对弱正信号，LLM 更倾向继续“相邻改动”或换 surface，而不是隔离变量、提出验证 probe、或把机制抽象成可迁移 lesson。
- branch lesson usage 多数是文字层面的 avoid/contrast，代码层体现有限。

## 是否说明 Scion 分支内研究和跨分支经验利用有改善

### 分支内研究

有改善，但不充分。

改善点：

- 多个 branch 能做 same-branch follow-up。
- 弱正 branch 会被保留或 park，而不是立刻丢弃。
- `f401e2f0`、`862e8492`、`16869fe7`、`9fa9b486` 都出现了不同程度的 refine。

不足：

- refine 很少转化为更强信号。
- 没有 validation/frozen。
- weak positive 主要停在 pair-level，没有实例级解释。
- 有些 branch 内第二步其实是换 surface，不是围绕同一 hypothesis 深挖。

### 跨分支经验利用

有 observability 改善，但没有证明有效 transfer。

改善点：

- branch lessons 确实进入 proposal 可见上下文。
- avoid/contrast 计数和目标选择显示 LLM 没有完全无视历史。
- DecisionFeatures 边界保持正确，lesson 没有污染 deterministic decision。

不足：

- `borrowed_lesson_count=0`。
- `weak_positive_transfer_count=0`。
- weak-positive branch 没有成为 clean fork 的机制种子。
- usage satisfied 更像 schema/checklist 成功，而不是算法研究成功。

## 是否进入 20R

不建议直接进入 20R。

理由：

- 12R 虽有效完成，但 0 promotion、0 validation、0 frozen。
- 本实验名义上验证 branch transfer，但 `weak_positive_transfer_count=0`。
- Fresh champion 要求重复出现，却没有被闭环。
- 继续拉长到 20R 很可能只增加 no-effect/avoid 计数，不会解决 weak-positive 验证和 transfer 机制。

建议先修 P0/P1 后重跑 12R。若修复成本需要分阶段，可以先做 4-6R targeted campaign，只验证 weak-positive replay/transfer，再做完整 12R，最后再考虑 20R。

## 修复建议

### P0：fresh champion replay/closure

当 candidate 触发 `fresh_champion_required` 且存在 weak-positive/tie evidence 时，scheduler 应安排明确的 non-proposal fresh replay 或 validation probe，而不是继续生成新 proposal。fresh replay 后必须给出三态结论：

- 升级到 validation。
- 保留为 weak-positive transferable lesson。
- 降级为 no-effect/park。

验收标准：12R 中 fresh-required weak positive 至少产生 fresh replay record；不会只留下 repeated fresh-required diagnostic。

### P0：weak-positive transfer 机制

branch-transfer 实验应要求 clean fork 至少尝试一次 weak-positive borrow/preserve，或写出可机读 reject reason。weak-positive lesson 需要包含：

- 触发机制。
- 有效实例/失败实例。
- 代码入口。
- activation 条件。
- 禁止复用的边界。

验收标准：`weak_positive_transfer_count` 在有 weak-positive source branch 时不能长期为 0；borrow/preserve 必须能在 hypothesis 和 code patch 中追踪到。

### P0：branch_lesson_usage 语义校验

`usage_present/satisfied` 不应只检查字段存在。需要验证 lesson 是否改变了 proposal：

- target 是否因 lesson 改变。
- mechanism 是否 preserve/avoid/contrast 了具体历史机制。
- code patch 是否实现了声明的 borrow/avoid/contrast。
- 如果只是泛泛提及，应计为 present but not semantically satisfied。

验收标准：usage satisfied 与 borrowed/avoided/contrasted/preserved 的代码证据绑定。

### P1：proposal target-intent binding retry

Round 12 的 block 合理，但 retry 机制应修：

- formal hypothesis 必须继承 selected target intent。
- 若需要换 mechanism，必须重新生成 target intent。
- contract mismatch 后的 retry 不应消耗过多 campaign 预算。

验收标准：target intent 与 formal hypothesis mechanism/action/target file 一致性在生成端被约束，而不是主要靠 Contract 后验拦截。

### P1：telemetry declaration/runtime consistency

Round 7 暴露 `solver_algorithm_phase_runtime_ms.alns` 缺失。需要统一 telemetry guard declaration 与 runtime emitter：

- scheduler/budget 类 proposal 的 required telemetry 字段应可达。
- 缺失字段要在 preflight 暴露。
- repairable screening 要保持 non-counted，不污染 effective candidate。

验收标准：budget/scheduler proposal 不再因已知字段漂移进入 repairable screening。

### P1：weak-positive validation threshold

当前所有 weak positives 都停在 pair-level。需要明确弱正到 validation/fresh replay 的阈值，例如：

- pair wins 多于 losses 且 CI 不显著负。
- 同一机制两次 pair-level weak positive。
- case-level all-tie 但 runtime/activation 显示真实触发。

验收标准：`clustered_worst_removal` 这类重复 weak-positive branch 不会只被 park，而是得到 fresh replay 或明确 reject reason。

### P2：上下文瘦身

Hypothesis prompt 上下文足够但偏重。应减少与当前 target 无关的全量源码/框架说明，把 token 留给：

- 实例级 screening diff。
- weak-positive causality。
- previous code delta。
- branch lesson materiality。

验收标准：不能以 tool call/input token 下降作为成功；必须观察 proposal 是否更具体、更可验证。

### P2：附带工程风险

早期主会话曾误判 hang，Helmholtz 后续核对证明这不是本次 run 的失败根因。本次 run 正常完成。但当时发现的 generic runtime subprocess timeout/cleanup 风险仍应作为工程 hardening 项保留：

- 主进程 sleep/poll 时应能区分 evaluator 子进程缺失、socket CLOSE_WAIT、pipe read 等状态。
- wrapper/status 更新应更快暴露 protocol 落账延迟。
- long-running campaign 应提供 heartbeat 与 child process inventory。

该风险不是本次 12R 的 root cause，不应把本次 run 定性为 hang。

## 最终判断

这组 12R 是有效的框架运行验证，不是有效的 20R 前算法研究能力证明。

可以确认：

- gpt-5.5 全链路调用正常。
- Contract/Verification/Protocol/Decision/Lifecycle/Scheduler 没有出现致命中断。
- Decision 仍只读 DecisionFeatures，branch lessons 只作为 proposal visibility。
- branch 内 follow-up 与 cross-branch avoid/contrast 已经具备基础形态。

不能确认：

- Scion agent 已能稳定做深度算法研究。
- weak-positive lesson 已能跨分支迁移。
- fresh runtime/validation 闭环已经可用。
- branch lesson usage satisfied 代表真实机制影响。

因此建议：先修 P0/P1，重跑 12R 或 targeted replay，再决定是否进入 20R。
