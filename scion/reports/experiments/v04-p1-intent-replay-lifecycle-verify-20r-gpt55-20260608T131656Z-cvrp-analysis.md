# CVRP/VRP 20R 后验分析

实验路径：`/home/clawd/research/scion-experiments/v04-p1-intent-replay-lifecycle-verify-20r-gpt55-20r-gpt55-20260608T131656Z-claw/campaign`

分析基准：按 `scion/design/scion-architecture-v3.md` 解释实验边界。LLM 输出视为 tainted proposal；Contract/Verification/Protocol 产出结构化证据；Decision 只能读取 `DecisionFeatures`；cross-branch lessons 只能作为后续 proposal 的 visibility/observability，不能作为 promotion/scheduling 的直接证据。

## 结论摘要

- run 是 finished/complete/valid，20 个有效 rounds 完成；没有 promotion，champion 停在 v1。没有 evidence 表明 Decision 读取了 LLM 自由文本或 cross-branch lesson 来晋升/淘汰。
- 22 个 protocol evaluated candidates = 20 个有效 screening + 2 个 in-loop fresh runtime replay 复评；24 个 proposal attempts = 22 个进入 protocol 的候选/复评 + 2 个 contract preview 阻断的 code generation failure。`run.log experiments: 22` 与 status 的 `effective_rounds_completed=20` 是 accounting 口径差异，不是 run invalid。
- 2 个 quality/code_generation_failed block 都来自同一分支试图改 `policies/baseline_modules/state.py` 并写入 private dynamic state attrs；Contract preview 因 `_Solution`/`_Route` 使用 `__slots__` 而拒绝，拒绝合理，且未计入有效 rounds。
- 研究质量中等偏弱：机制大多符合 CVRP/ALNS/VNS mechanics，但大量结果是 zero/negative median、runtime saturation 或 telemetry zero；两个较有研究价值的 weak-positive 路线是 `route_pair_alns_kick` 与 `elite_route_pool_recombination`，都被 replay 后 park，没有达到 validation/frozen。
- P1 修复在本实验中基本按预期暴露状态：`candidate_intent_counts` 不再全归 observability，fresh replay drain 显式给出 `pressure_no_replayable_candidate` 和 `decision_features_excluded=true`。但 final drain 仍暴露 pending/materialization 缺口：存在 fresh runtime pressure candidates，却没有 materializable replay candidate。
- 不建议仅凭本 20R 直接升到 40R/50R；可以做一轮 40R 小规模验证，但应先优化 proposal 去重、fresh replay materialization、route-pool/route-limit follow-up 聚焦策略。

## 证据边界与数据源

读取的数据源包括 `status.json`、`campaign_summary.json`、`run_status.json`、`run.log`、`scion.db`、`agentic_sessions/`、`llm_traces/`、`artifacts/formal_candidates/`、`champions/`。未修改源码。

v3 边界检查：

- LLM hypothesis/tool/code 输出只进入 agentic proposal session 与候选 patch，不作为 Decision 的直接依据。
- 22 条 experiment 均有 Contract/Verification/Canary 结果并进入 screening；没有 validation/frozen。
- `champions/` 只有 `champion_v1`，`scion.db.champions` 只有 version 1；没有 promotion event。
- fresh replay drain 的 `last_result` 标注 `counts_toward_max_rounds=false` 与 `decision_features_excluded=true`。
- cross-branch sections 出现在 prompt manifest 中，属于 proposal visibility；没有发现其进入 DecisionFeatures 或 champion 证据链。

## Run 与 Accounting

| 字段 | 值 | 解释 |
|---|---:|---|
| `requested_rounds` | 20 | 用户请求的有效 round 数 |
| `effective_rounds_completed` | 20 | 计入 max rounds 的 screening |
| `formal_screened_candidates` | 22 | 包含 2 次 fresh runtime replay 复评 |
| `protocol_evaluated_candidates` | 22 | 同 formal screened |
| `proposal_attempts_total` | 24 | 22 个 protocol 候选/复评 + 2 个 proposal/code block |
| `quality_blocks` | 2 | 同一 state.py 候选的 preview reject 与 retry reject |
| `branch_lifecycle_policy_blocks` | 0 | 顶层 lifecycle policy block 计数为 0；分支 row 中仍记录了 park/reclaim 状态 |
| `champion_version` | 1 | 没有 promotion |
| `run.log experiments` | 22 | CLI 展示 protocol experiments，不等同 effective rounds |

`status.json` 里两个 `non_effective_screenings` 是 aggregate reconciliation：`screened_formal_results_excluded_from_effective_rounds`。对应 DB 中 step 15 与 step 18 的 `attempt_kind=fresh_runtime_replay`，scheduler 标注 `counts_toward_max_rounds=false`，但它们仍有 formal screening metrics，所以会进入 protocol/formal screened 计数。

## 逐轮次 / 逐分支表

| Step | 计数 | Branch / Hyp | Hypothesis 与 target | Code 实现 | Protocol 结果 | Decision / Lifecycle |
|---:|---|---|---|---|---|---|
| 1 | effective | `a8247367` / `d1607ca6` | cross-route 2-opt reconnect；`local_search.py` | 新增 `_cross_route_2opt_reconnect`，交换两条 route 的 suffix/continuation，检查 capacity 与距离改进 | 8 cases W/L/T 0/0/8，pairs 1/2/13，median 0，CI [-0.5,0] | `abandon`；quality regression，runtime saturation |
| 2 | effective | `4ae2a2c2` / `e190b048` | route-limit biased repair；`destroy_repair.py` | regret/greedy repair 在 route limit 下优先插入现有 route，把新 route 作为 last resort | 0/0/8，pairs 0/1/15，median 0，CI [0,0] | `continue_explore`；active_quality_regression，fresh runtime pending/required |
| 3 | effective | `73a6c8f2` / `c19826a0` | ALNS operator telemetry bridge；`scheduler.py` | 记录 destroy/repair attempts、accepted、best delta；不改搜索行为 | 0/0/8，pairs 0/0/16，median 0 | `continue_explore` 后被 active-slot reclaim park；observability/no effect |
| 4 | effective | `8b8b4309` / `bece1190` | VNS budget telemetry bridge；`telemetry_budget.py` + scheduler hook | 新增 phase budget helper/records，主要是 budget observability | 12 cases 0/0/12，pairs 0/0/24，median 0 | `continue_explore` 后 park；no effect |
| 5 | effective | `8166cf31` / `690c6bd9` | rank-gap acceptance；`acceptance.py` | SA 对非改进 move 加 normalized rank gap 限制 | 0/0/8，pairs 1/2/13，median 0，CI [-0.5,0] | `abandon`；quality regression/runtime saturation |
| 6 | effective | `7df931ae` / `227f6ec1` | route-limit seed diversification；`construction.py` | 需求降序、polar sector、far-from-depot tie-break 等 seed ordering | 0/0/8，pairs 0/1/15，median 0 | `continue_explore`；active_quality_regression，fresh runtime pending |
| 7 | effective | `b1b7659f` / `078d8ab9` | bounded intra-route 3-opt；`local_search.py` | 新增 `_intra_route_three_opt`，受 time reserve 限制 | 0/0/8，pairs 1/4/11，median -0.25，CI [-3,0] | `abandon`；negative delta |
| 8 | effective | `4aba4b15` / `943b684c` | demand/locality cluster repair；`destroy_repair.py` | 改 customer selection 与 regret insertion，偏向需求/空间 cluster | 1/2/5，pairs 2/6/8，median -0.25，CI [-4.5,0] | `abandon`；有 case win 但整体 regression |
| 9 | effective | `24f43b74` / `14d014d7` | route-pair 2-opt relink；`local_search.py` | 新增 `_route_pair_2opt_relink`，两 route edge relinking | 0/1/7，pairs 1/5/10，median 0，CI [-4.5,0] | `abandon`；loss without win |
| 10a | no | `91f3d47a` / `2f3ed9cf` | route compaction state helper；`state.py` | Code preview 试图写 private dynamic attrs | 未进入 protocol；Contract preview 拒绝 | quality block；`code_generation_failed` |
| 10b | no | `91f3d47a` / `2f3ed9cf` | 同上 retry | retry 仍触碰 private dynamic state attrs | 未进入 protocol；Contract preview 再拒绝 | quality block；`contract_boundary_failure` |
| 11 | effective | `91f3d47a` / `914fc3a6` | seed distance polish；`construction.py` | route 内 nearest ordering + 2-opt polish | 0/0/8，pairs 1/2/13，median 0，CI [-1,0] | `abandon`；分支带 PROPOSAL + screening fail |
| 12 | effective | `495f4472` / `8ddf8362` | lexicographic reheat acceptance；`acceptance.py` | stagnation 后提高非改进 move 温度，再冷却 | 0/0/8，pairs 0/1/15，median 0 | `continue_explore`；active_quality_regression，fresh pending |
| 13 | effective | `a71405b1` / `6c53b3ec` | route merge repair bridge；`destroy_repair.py` | repair 后把 sparse/low-load route 尝试吸收到 slack route，要求非劣 | 0/0/8，pairs 0/1/15，median 0 | `continue_explore`；telemetry effect zero，fresh pending |
| 14 | effective | `2bd861ea` / `4c16b9b2` | route-pair ALNS kick；`scheduler.py` | stagnation 时选 route pairs、remove clusters、regret repair | 0/0/8，pairs 1/1/14，median 0 | `continue_explore`；weak/neutral signal，触发 fresh replay |
| 15 | no | `2bd861ea` / `4c16b9b2` | fresh runtime replay of step 14 | 无新 diff；复用候选做 fresh champion runtime follow-up | 0/0/8，pairs 1/1/14，median 0 | `continue_explore` 但 `attempt_kind=fresh_runtime_replay` 不计 round；parked_lineage weak_positive |
| 16 | effective | `957b3b8d` / `a1074662` | elite route pool recombination；`route_pool.py` | 新增 `_EliteRoutePool`，从 elite routes 组装非重叠 feasible routes，再 repair uncovered customers | 12 cases 1/0/11，pairs 3/0/21，median 0，CI [0,0] | `continue_explore`；最强弱正信号 |
| 17 | effective | `957b3b8d` / `959cf111` | earlier route-pool trigger；`scheduler.py` | 在 ALNS stagnation/neutral acceptance 前更早触发 route-pool recombination | 0/0/8，pairs 1/0/15，median 0 | `continue_explore`；weak-positive follow-up |
| 18 | no | `957b3b8d` / `959cf111` | fresh runtime replay of step 17 | 无新 diff；复用候选复评 | 0/0/8，pairs 1/1/14，median 0 | `continue_explore` 但不计 round；parked_lineage weak_positive |
| 19 | effective | `7e532771` / `f832375c` | ALNS destroy size adaptation；`scheduler.py` | q/destroy size controller 随 accepted/improved 信号调整 | 0/1/7，pairs 0/3/13，median 0，CI [-1.5,0] | `abandon`；loss signal |
| 20 | effective | `65b0fe29` / `af956609` | route-limit compaction seed；`construction.py` | transfer sparse/high-detour customers into feasible nondegrading buckets | 0/0/8，pairs 0/0/16，median 0 | `continue_explore`；active_no_effect，fresh runtime required but pending false |
| 21 | effective | `025339e2` / `ce501bcf` | intra-route segment reinsertion；`local_search.py` | 新增 length 2/3 contiguous segment reinsertion | 1/1/6，pairs 3/4/9，median 0，CI [-1.5,0] | `abandon`；mixed but non-positive |
| 22 | effective | `74a3a5af` / `c79a2204` | elite route pool recombination repeat；`route_pool.py` | 再次创建 route-pool helper，机制接近 step 16 | 12 cases 0/0/12，pairs 0/0/24，median 0 | `continue_explore`；active_no_effect，telemetry zero |
| 23 | effective | `3e4afca3` / `4d5e597e` | cross-route 2-opt reconnect repeat；`local_search.py` | 再次实现 cross-route reconnect，机制接近 step 1 | 0/1/7，pairs 1/6/9，median -1.75，CI [-8,0] | `abandon`；明确 regression |

所有进入 protocol 的候选均为 screening stage，Contract/Verification/Canary passed；没有 validation/frozen。

## LLM 调用维度

`agentic_session_trace_index.json` 与 `llm_traces/` 显示：

| request kind | 次数 | model | 状态 | token 观察 |
|---|---:|---|---|---|
| `hypothesis_target_intent` | 21 | 全部 `gpt-5.5` | ok | avg total 36,715；max 41,068 |
| `hypothesis` | 24 | 全部 `gpt-5.5` | ok | avg total 50,517；max 57,443 |
| `tool_selection` | 114 | 全部 `gpt-5.5` | ok | avg total 13,144；max 18,093 |
| `code` | 28 | 全部 `gpt-5.5` | ok | avg total 32,419；max 43,946 |

session status：43 sessions = 21 partial hypothesis only + 20 completed + 2 failed。2 个 failed session 对应同一 branch 的 code generation failure，不是模型调用失败，而是 code phase 产物被 contract preview 拒绝。

Context 检查：

- 21 个 `hypothesis_target_intent` prompt 无 section truncation。
- 20 个 `hypothesis` 与 3 个 `hypothesis_preview_retry` prompt 截断了 `branch_lesson_usage_context`，但 `cross_branch_research_map` 与 material difference requirement 大体可见。
- 28 个 code prompt 中 26 个无截断，2 个截断 `previous_patch_attempt`。
- 没看到明显 context 过载造成的错误；主要风险是 branch lessons 被压缩，导致后期仍出现近重复。

Quality block 细节：

- Branch `91f3d47a` 的 `route_compaction_state_helper` 试图修改 `policies/baseline_modules/state.py`，写入 private dynamic state attrs。
- Contract preview 报：`_Solution` and `_Route` use `__slots__` and must not rely on dynamic private attrs；违规行 `[23, 102, 103]`，rule `solver_design_no_dynamic_state_private_attrs`。
- 第一次记录为 `code_generation_failed`，第二次 retry 记录为 `contract_boundary_failure`。两次均 `counts_toward_max_rounds=false`。
- 判断：阻断合理，保护了 problem policy state boundary；但 repair retry 没有有效避开同一边界，说明 code repair prompt 对 schema/slots 错误的吸收还可以加强。它没有阻塞有效研究，因为分支随后改走 `construction.py` 的 `seed_distance_polish` 并完成 screening。

## 分支内研究质量

有效研究分支：

- `957b3b8d`：route-pool recombination 是本轮 CVRP 最有研究含量的方向。它从 elite routes 中重组 feasible non-overlap routes，符合 CVRP 的 route decomposition mechanics；first candidate 有 1/0/11 cases 与 3/0/21 pairs 的弱正，后续调度触发时机也合理。但 median/CI 仍为 0，fresh replay 后 pair loss 增加到 1，未满足 promotion。
- `2bd861ea`：route-pair ALNS kick 针对 ALNS stagnation 与 route-pair neighborhood，机制合理，fresh replay 后保持 neutral。被 park 是合理的弱正处理。
- `4ae2a2c2`、`7df931ae`、`65b0fe29`：都围绕 route-limit / construction feasibility pressure，符合 CVRP mechanics，但没有 objective improvement。它们更像“问题约束修复方向”的探索，不是强质量提升。
- `a71405b1`：route merge repair bridge 机制合理，但 telemetry zero，说明实现触发或效果不足。

弱信号或形式化分支：

- `73a6c8f2`、`8b8b4309` 是 observability/budget telemetry 候选；它们对研究系统有价值，但在本 run 的 `candidate_intent_counts` 被归为 algorithm quality candidate 且 observability value not applicable。作为质量搜索，它们没有 objective effect。
- `a8247367` 与 `3e4afca3`、`957b3b8d` 与 `74a3a5af` 是明显近重复。后者尤其说明 cross-branch lessons 没有完全阻止 route_pool helper 的重做。
- `b1b7659f`、`4aba4b15`、`24f43b74`、`7e532771`、`025339e2` 都有局部 pair/case wins，但 median/CI 或 losses 不支持继续加码；abandon 合理。

失败处理：

- 负向 local search/repair 分支大多被 abandon，没有继续消耗 active slots。
- weak-positive 分支被 fresh replay 后 park，符合“弱正需要 fresh runtime 复核但不足以 promotion”的 lifecycle。
- no-effect 分支仍有若干保持 explore active，最终 drain 暴露 fresh runtime pressure 但 pending false，这部分链路需要改进。

## 分支间信息传递

prompt manifest 中有 `cross_branch_research_map` 与 `branch_lesson_usage_context`，说明后续 proposal 看到了跨分支历史。实质影响有三类：

- 避免部分失败路线：早期 intra-route/local-search 负向后，中段转向 construction、repair bridge、route-pool recombination，说明路线选择不只是随机重复。
- 跟进弱正：`route_pair_alns_kick` 触发 fresh replay，`elite_route_pool_recombination` 先做 helper、再做 scheduler trigger、再 fresh replay，说明 weak-positive signal 被用来安排 follow-up。
- 去重不足：后期再次出现 `elite_route_pool_recombination` create-new 与 `cross_route_2opt_reconnect`，说明 lesson visibility 对 proposal 有影响但约束力不够；它没有直接进入 Decision，这是符合 v3 边界的，但研究效率受影响。

本报告只评估 CVRP 内部信息传递；warehouse 的经验不作为本实验 proposal/Decision 证据。

## 晋升与 Evidence Boundary

没有晋升：

- `champions/` 只有 `champion_v1`。
- `scion.db.champions` 只有 version 1。
- protocol stage counts：screening 22，validation 0，frozen 0。
- 没有候选通过 validation/frozen 形成 v2 所需证据链。

因此 champion v1 停留不是 promotion failure，而是 screening evidence 不足。Decision 的行为与 v3/v0.4 证据边界一致：弱正未越过 screening gate，没有被 LLM narrative 或 branch lesson 直接推成 champion。

## P1 修复验收

1. `candidate_intent_counts`：`algorithm_quality_candidate=24`，`observability_candidate=0`，`repair_or_infra_candidate=0`，`unknown=0`。不再出现所有候选误归 observability 的问题。
2. `observability_value_counts`：24 个均为 `OBSERVABILITY_VALUE_NOT_APPLICABLE_TO_QUALITY_SEARCH`，且 `decision_features_excluded_count=24`。这符合“quality search 不把 observability value 当 Decision 证据”的边界，但也暴露 telemetry-only 候选在 intent 分类上仍被当作 algorithm quality。
3. lifecycle last_result：final fresh replay drain 的 last_result 是 drain/scheduler result，不是顶层二次 Decision；字段含 `action=skip`、`attempt_kind=other`、`scheduler_action=create_new`、`scheduler_reason=new_exploration_slot_available`、`decision_features_excluded=true`。
4. fresh replay pressure：状态不再静默吞掉，而是输出 `pressure_no_replayable_candidate` 与 unresolved closure。

验收结论：P1 的主要状态暴露与 DecisionFeatures 排除生效；剩余问题在 replay materialization 和 proposal intent 更细分类。

## Fresh Runtime Replay 分析

本 run 有两种 replay 相关现象，必须分开：

- In-loop fresh runtime replay：step 15 对 `2bd861ea/4c16b9b2` 复评，step 18 对 `957b3b8d/959cf111` 复评。两者有 formal metrics，进入 22 个 protocol evaluated candidates，但 scheduler 标 `counts_toward_max_rounds=false`。
- Final drain：run 结束时 `fresh_runtime_replay_drain_executed=0`，`blocked_count=1`，状态 `pressure_no_replayable_candidate`。

final drain 的 `last_result`：

- `branch_id=null`
- `scheduler_action=create_new`
- `scheduler_slot=explore_new`
- `scheduler_reason=new_exploration_slot_available`
- detail：fresh champion runtime pressure exists but no structured replay pending candidate is materializable

pressure candidates 是 `65b0fe29` 与 `74a3a5af`，均为 active_no_effect，`fresh_runtime_required=true`，但 `fresh_runtime_pending=false`。这解释了为什么 `branch_id` 是 None：drain 没有选中一个 `replay_existing` 分支，只看到 pressure，但没有 materializable pending replay candidate。

判断：P1 修复按预期暴露了问题；仍需要后续修复 pending/materialization 链路，使 active_no_effect/quality_regression 中带 fresh runtime pressure 的候选能明确转成 replay candidate，或明确声明不应 replay 的结构化理由。

## 是否支持升到 40R/50R

不建议直接把这组 CVRP 20R 当作充分升轮次依据。

支持升轮次的正面信号：

- 20R 完整有效，Contract/Verification/Protocol/Decision 链路稳定。
- code boundary 能拦住非法 state mutation。
- weak-positive 分支能触发 in-loop fresh replay，并且没有越界 promotion。
- 研究路线覆盖了 construction、repair、acceptance、local search、scheduler、route pool。

限制升轮次的负面信号：

- 没有 validation/frozen，没有 champion v2。
- 22 个 formal candidates 中绝大多数 median/CI 为 0 或负，许多是 runtime saturation/no objective effect。
- near-duplicate 仍发生，尤其 route_pool helper 与 cross-route 2-opt reconnect。
- final drain 暴露 fresh runtime pressure 无法 materialize。
- telemetry-only 候选 intent 仍被归 algorithm quality，后续研究预算可能被形式化 observability 消耗。

建议：可以先做一个 40R 试运行用于压力测试，但若目标是研究效率，应先修 proposal de-dup、fresh replay materialization、telemetry-only intent 分类，以及对 weak-positive route-pool/route-limit 方向的 follow-up policy。

## 与 Warehouse 20R 对照

Warehouse 20R 产生 champion v2，而 CVRP 保持 champion v1。这个差异主要来自两层：

- 问题难度/surface 差异：warehouse 的 mechanics 更局部，候选更容易形成可检测的 objective 改善；CVRP 的 ALNS/VNS/route-pool 改动更容易被现有 baseline、runtime budget、case variance 稀释，screening median 常为 0。
- Scion 框架差异信号：两组都暴露 fresh runtime replay pressure；CVRP 还显示 near-duplicate 与 pending/materialization 缺口更影响长程研究效率。warehouse v2 说明框架能完成 promotion；CVRP v1 说明在更难的 VRP surface 上，仅靠当前 proposal/lifecycle policy 不一定能持续产出强候选。

可迁移到 CVRP 的 warehouse 结论：P1 状态暴露有价值，promotion 应继续坚持 screening/validation/frozen 边界。不可直接迁移的结论：warehouse 的晋升率不能推断 CVRP 在 20R 内也应晋升；CVRP 需要更强的问题特定 search guidance 和去重/复评机制。
