# Scion v0.4 P1 Warehouse 20R 后验分析

实验目录：`/home/clawd/research/scion-experiments/v04-p1-intent-replay-lifecycle-warehouse-verify-rerun-20r-gpt55-20r-gpt55-20260608T131951Z-claw/campaign`

分析锚点：已先读 `scion/design/scion-architecture-v3.md`。本文按 v3 边界解释结果：LLM 输出均为 tainted proposal；Decision 只应读取 Contract/Verification/Protocol 后提取的 `DecisionFeatures`；cross-branch lessons 只能作为 proposal visibility/observability，不作为晋升或淘汰的决策输入。

## 结论概览

这组 run 是 valid 且完成 20 个 effective round。它证明 warehouse problem 上 Scion agent 能做有效研究：第一条候选 `ConsolidateSubcategory` 从 v1 champion 晋升为 v2，并且 screening/validation/frozen 三阶段全通过；后续分支能从失败、弱正、runtime pressure 中调整路线，不是纯随机生成。但这个结论不能直接等价迁移到 CVRP：warehouse 的目标结构、oracle、局部算子空间和 `subcategory_splits -> total_cost` 字典序反馈比 CVRP 更直接，搜索空间更容易被 LLM 读懂和命中。

最重要的 caveat 是 accounting 和 fresh runtime replay。`run.log` 的 `experiments : 19` 是旧展示口径，基本对应 DB 中 `event_kind=experiment` 的 19 行；status 的 `effective_rounds_completed=20` 还包括一次 V9 heavy verification failure。`formal_screened_candidates=18` 在 status 里与严格 artifact/DB 口径有轻微语义不一致：formal candidate artifact 只有 17 个，另 1 个是 `pair_exchange_cost_guard` 的 verification-heavy blocked candidate。fresh runtime replay 已按 P1 目标暴露为 `pressure_no_replayable_candidate`，没有静默吞掉，但仍需要后续调度/物化修复。

## 数据源与运行状态

- `run_status.json`: wrapper exit 0，`run_validity_status=valid`，`run_complete=true`，开始 `2026-06-08T13:19:52Z`，结束 `2026-06-08T14:57:26Z`。
- `status.json`: `effective_rounds_completed=20`，`proposal_attempts_total=21`，`quality_blocks=1`，`protocol_stage_counts={screening:18, validation:1, frozen:1}`，`champion_version=2`，`fresh_runtime_replay_drain_status=pressure_no_replayable_candidate`。
- `campaign_summary.json`: `counted_experiment_steps=19`，`screened_experiments=17`，`candidate_intent_counts.algorithm_quality_candidate=20`，`repair_or_infra_candidate=1`，LLM trace totals 109 calls。
- `scion.db`: 99 total events；`event_kind=experiment` has 19 rows: 17 screening, 1 validation, 1 frozen；`event_kind=verification_fail` has 1 row；scheduler counted 20 max-round attempts and 1 non-counted proposal block.
- `run.log`: only prints the failed proposal and final summary, not the full reconciliation.

## 逐轮次表

说明：`counted` 是 scheduler accounting 是否消耗 max-round budget。`Protocol` 只在通过 verification 后产生 metrics；V9 heavy failure 没有 protocol metrics。`W/L/T` 是 case-level gate。

| Step | Counted | Branch | Hypothesis / target | Mechanics and code implementation | Gate / Protocol result | Decision / lifecycle |
|---:|:---:|---|---|---|---|---|
| 1 | yes | `ece037a3` | `bf8b4c5f` create `operators/consolidate_subcategory.py` | 新增 vehicle-level `ConsolidateSubcategory`，选择分散的 `vehicle_subcategory`，按 pickup city/category 将 unlocked orders 重新装箱到尽量少车辆；保留 locked orders，检查容量、hazard、pickup 限制和 assignment consistency；只接受 split 降低或 split 持平且 cost 降低。 | Contract/Verification/Canary all passed. Screening 10 cases, W/L/T=9/0/1, pair=18/1/1, win_rate=0.9, median_delta=3.0, CI [2.5, 8.0]. | `queue_validate`; 新机制强正，进入 validation。 |
| 2 | yes | `ece037a3` | same candidate validation | 同一 code hash/replay identity；不再读 LLM 文本决策。 | Validation 6 cases, win_rate=1.0, median_delta=34.5, CI [12.0, 110.0], runtime high/sufficient. | `queue_frozen`。 |
| 3 | yes | `ece037a3` | same candidate frozen | 同一候选在 frozen holdout 上验证。 | Frozen 4 cases, win_rate=1.0, median_delta=60.5, CI [13.0, 220.0], runtime sufficient and supporting only. | `promote`; champion v2 created from `db5cf7a5-0e29-40a6-b730-c90166f63ee5`。 |
| 4 | yes | `dc3bc791` | `320d2788` modify `operators/merge_vehicles.py` | 把随机 merge 改成 split-preserving compatible-pair merger，扫描同城/同类兼容车辆对，只在 cost 降低且不增加 splits 时合并。 | Passed gates. Screening 6 cases, W/L/T=0/4/2, pair=1/9/2, median_delta=-0.75, CI [-2.25, 0.0]. | `abandon`; archive lineage，负面证据明确。 |
| 5 | yes | `40b0429c` | `48d6c1fc` create `tail_evacuate_subcategory.py` | 新增 order-level tail evacuation：把某 subcategory 的轻载 tail vehicle 中 unlocked orders 搬到已有同 subcategory 的 sibling vehicles，删除空车；split 优先、cost tie-break。 | Passed gates. Screening 10 cases, W/L/T=4/1/5, pair=12/6/2, median_delta=0.25, CI [0.0, 2.5]. | `continue_explore`; weak-positive retained as checkpoint。 |
| 6 | no | `40b0429c` | proposal block | 试图继续 order-level proposal，但 hypothesis/target preview 被 C11 拦截。 | Pre-protocol quality block: `order_level` surface did not declare telemetry fields in `surface.evidence`。 | 不计 max_rounds；作为 quality block ledger 记录。 |
| 7 | yes | `40b0429c` | `ac6b31b3` modify `tail_evacuate_subcategory.py` | 加 strict cost-aware trigger 和 destination ordering，避免 equal-split cost increase。 | Passed gates. Screening 6 cases, W/L/T=0/0/6, pair=0/0/12, median_delta=0.0, runtime low_cached. | `continue_explore`; current head no effect，保留 step 5 best checkpoint，lineage parked/clean fork required。 |
| 8 | yes | `d3306c15` | `f467505c` create `exact_subcategory_pack.py` | 新增 vehicle-level bounded exact bin-packing，针对 high-split subcategory group 做小规模 branch-and-bound/greedy fallback，lexicographic accept。 | Passed gates. Screening 10 cases, W/L/T=2/4/4, pair=7/12/1, median_delta=0.0, CI [-0.5, 0.75]. | `continue_explore`; marginal retained, clean fork。 |
| 9 | yes | `d3306c15` | `ab335530` modify `exact_subcategory_pack.py` | 加 lower-bound split forecast 和 incumbent-cost gate，只在预计减少 bin 或同 bin 更低 cost 时重排。 | Passed gates. Screening 6 cases all ties, runtime evidence status `fresh_champion_required`, aggregate excluded. | `continue_explore`; no effect/current head，runtime pressure。 |
| 10 | yes | `29f2df58` | `6d6e6c8e` create `split_neutral_cost_compact.py` | split-neutral cost compaction：小 bucket 同城同类车辆重装箱，要求 `subcategory_splits` 完全不变且 `total_cost` 降低。 | Passed gates. Screening 10 cases, W/L/T=2/2/6, pair=8/8/4, median_delta=-0.25, CI [-1.25, 0.0]. | `abandon`; negative/non-positive CI。 |
| 11 | yes | `a587587a` | `9779ceef` create `split_safe_cost_compact.py` | split-safe bucket repack，要求 subcategory vehicle sets 不扩散，试图产生 cost wins。 | Passed gates. Screening 10 cases, W/L/T=1/3/6, pair=6/10/4, median_delta=-0.25, CI [-1.0, 0.0]. | `abandon`; loss-heavy follow-up。 |
| 12 | yes | `82495cff` | `eaff892d` modify `operators/move_order.py` | 将随机 MoveOrder 换成 same-subcategory gap-fill move，仅移动已有 split 中的 unlocked order 到同 subcategory compatible vehicle。 | Passed gates. Screening 6 cases, W/L/T=0/1/5, pair=4/5/3, median_delta=-0.25, CI [-0.75, 0.25]. | `abandon`; no case wins and loss。 |
| 13 | yes | `673a1cb8` | `2c2ef890` modify `change_vehicle_type.py` | 将随机 vehicle downgrade 换成 deterministic best-normalization，保持 order set 和 splits，降低 vehicle type cost。 | Passed gates. Screening 6 cases, W/L/T=0/1/5, pair=3/5/4, median_delta=0.0, CI [-0.75, 0.25]. | `abandon`; no wins/loss present。 |
| 14 | yes | `74b38633` | `9414e042` create `purify_subcategory_vehicle.py` | 新增 mixed-vehicle impurity removal：把少数 subcategory order set 迁入已有同 subcategory vehicles，为后续 consolidation 打开空间；lexicographic no-op guard。 | Passed gates. Screening 10 cases, W/L/T=2/1/7, pair=10/8/2, median_delta=0.5, CI [0.0, 0.5]. | `continue_explore`; weak-positive retained。 |
| 15 | yes | `74b38633` | `778ceb96` modify `purify_subcategory_vehicle.py` | 加 split-preserving cost guard 和 activation pre-score，避免 purification 造成 tie cost loss。 | Passed gates. Screening 6 cases all ties, runtime `fresh_champion_required`, aggregate excluded. | `continue_explore`; no effect/current head，checkpoint retained。 |
| 16 | yes | `0eab5d17` | `00241066` create `split_guarded_cost_compress.py` | 新增 split-guarded splitter，把高成本车辆拆成两个 split-neutral compatible bins，要求不增加 splits，并争取 cost 降低。 | Passed gates. Screening 10 cases, W/L/T=1/3/6, pair=7/11/2, median_delta=0.0, CI [-1.0, 0.5]. | `continue_explore`; marginal but weak。 |
| 17 | yes | `0eab5d17` | `ff6cf97b` modify `split_guarded_cost_compress.py` | 收紧为 strict cost-compression-only splitter，要求 global splits exactly unchanged and cost strictly decreases。 | Passed gates. Screening 6 cases all ties, runtime `fresh_champion_required`, aggregate excluded. | `continue_explore`; no effect/current head，runtime pressure count reaches 2。 |
| 18 | yes | `baa6368a` | `5c308de6` create `pair_exchange_cost_guard.py` | order-level pair exchange / one-for-one swap，试图在 preserving splits 下解锁 vehicle downsizing。 | Contract passed, verification failed at `V9_perf_guard` heavy. No protocol metrics, no formal candidate artifact. | Scheduler records counted screening attempt; clean fork selected. Hypothesis status `blacklisted`。 |
| 19 | yes | `baa6368a` | `af7d3f5a` create `targeted_vehicle_elimination.py` | vehicle-level targeted low-load source evacuation，删除一个 tail vehicle，允许 destination type upgrades only if net fleet cost falls and splits non-increase。 | Passed gates. Screening 10 cases, W/L/T=4/2/4, pair=12/6/2, median_delta=0.25, CI [-0.5, 1.0]. | `continue_explore`; marginal retained, same-branch refinement。 |
| 20 | yes | `baa6368a` | `d92d1abb` modify `targeted_vehicle_elimination.py` | 加 per-subcategory split-delta prefilter 和 stricter destination batching，避免 tail deletion 扰动 topology。 | Passed gates. Screening 6 cases all ties, runtime `fresh_champion_required`, aggregate excluded. | `continue_explore`; no effect/current head，runtime pressure。 |
| 21 | yes | `fb57fb03` | `5a9a8777` create `tail_fill_cost_reducer.py` | order-level tail-fill cost reducer：清空 nearly empty single-subcategory source vehicle 到已有同 subcategory vehicles，删除/downsizing，以 cost 为主但保护 splits。 | Passed gates. Screening 10 cases, W/L/T=1/1/8, pair=9/7/4, median_delta=0.0, CI [-0.5, 1.0]. | `continue_explore`; active marginal。 |

## 关键分支叙事

`ece037a3` 是唯一晋升分支。它的机制非常贴合 warehouse mechanics：greedy baseline 会把同一 `vehicle_subcategory` 分散在多辆车上，而现有随机 merge/destroy 只能碰运气修复。`ConsolidateSubcategory` 直接把 split-count 作为搜索 key，把可移动订单按 city/category 重装箱，并以 `subcategory_splits` 优先、`total_cost` 次之接受。screening 的 9/0/1 已经足够强；validation/frozen 继续全胜，因此晋升可信。

`dc3bc791` 代表早期局部改造失败。它试图改 `MergeVehicles` 为 compatible-pair merger，方向看似合理，但没有重建单一 subcategory group，实际 W/L/T=0/4/2，说明 whole-vehicle absorption 对 primary split 目标不够直接，且可能损害成本/拓扑。该失败随后被 branch lessons 用于避免继续走 split-preserving pair merge lineage。

`40b0429c` 是弱正后 refinement 退化案例。`TailEvacuateSubcategory` 首轮 W/L/T=4/1/5，有实际 split signal；后续 cost-aware refinement 变成 0/0/6，说明过度收紧触发条件会把有效动作 no-op 掉。lifecycle 正确保留了 best checkpoint，而不是把失败 head 当作活跃基础。

`d3306c15`、`74b38633`、`0eab5d17`、`baa6368a` 都显示同一模式：create-new 有弱正或 marginal，modify-refinement 常退化为 all ties，并触发 runtime/fresh champion pressure。这不是 LLM 完全无效，而是当前 search 已进入 tie-dominated plateau，refinement 主要在 guard 上收紧，缺少新的 objective opportunity。

`baa6368a` 还有一个工程层信号：`pair_exchange_cost_guard` 因 V9 perf guard heavy 失败，被 blacklisted。后续 `targeted_vehicle_elimination` 明显借鉴了这个失败，改用 bounded whole-vehicle deletion，报告了 target runtime effect “避免 slow exhaustive pair-exchange pattern”。这说明 cross-branch lessons 影响了路线，而不是只在文本中出现。

## LLM 调用与上下文质量

Trace index 显示 37 agentic sessions、109 LLM traces，全部 model 为 `gpt-5.5`：

| request_kind | calls | input_tokens | output_tokens | max_input | max_output |
|---|---:|---:|---:|---:|---:|
| hypothesis | 35 | 936,899 | 39,978 | 35,591 | 1,794 |
| tool_selection | 55 | 461,239 | 1,981 | 9,312 | 65 |
| code | 19 | 381,564 | 55,774 | 23,734 | 3,910 |
| total | 109 | 1,779,702 | 97,733 | - | - |

所有 trace `ok=true`，没有模型混用。session status 为 18 `partial_hypothesis_only`、18 `completed`、1 `failed`。`partial_hypothesis_only` 是 APS 两段流程中的 hypothesis-awaiting-approval，不等于失败；唯一真正 quality block 是 step 6 的 contract/schema target preview failure。

上下文总体足够：agentic outputs 记录了 required context preface、surface listing、branch state、feedback、registry/provider 读取；后续 hypothesis 中普遍包含 `branch_lesson_usage` 和 `material_difference`。最大 hypothesis input 约 35.6k tokens，code 最大约 23.7k tokens，没有看到上下文溢出、空输出或错误 schema 洪泛。风险是 prompt tokens 较高且 cache hit rate 低（overall 约 2.85%），但没有证据显示上下文过载导致错误路线。step 6 的 quality block 反而说明 schema/target preview gate 在拦截 surface telemetry 声明不一致。

## Cross-branch lessons 是否真的影响路线

有影响，但影响边界符合 v3：proposal visibility only，DecisionFeatures excluded。

证据包括：

- Branch evidence 中记录 `branch_lesson_usage_requirement`，字段明确 `proposal_visibility_only=true`、`proposal_guidance_only=true`、`decision_features_excluded=true`。
- Agentic output 里每个 session 都能递归找到 `hypothesis.branch_lesson_usage`。例子包括避免 `split_preserving_merge_lineage`、避免 `tail_evacuate` 过窄 refinement、避免 same-subcategory random move、避免 split-neutral negative lineage。
- 路线实际发生变化：从 `MergeVehicles` pair merge 失败，转向 `TailEvacuateSubcategory`；tail refinement no-op 后转向 exact subcategory pack；exact/compact 系列无效后转向 purification、split-guarded cost compression、targeted vehicle elimination；pair exchange perf failure 后转向 bounded vehicle elimination。
- 这些 lessons 没有直接导致晋升或淘汰；晋升仍只发生在 `ConsolidateSubcategory` 的 deterministic protocol evidence 上。

## 晋升分析

Champion v2 来源：

- Branch: `ece037a3-f2d0-45a0-9f37-8467cc5f6e91`
- Hypothesis: `bf8b4c5f-b799-4f90-b11f-7da7e462e6ad`
- Promotion experiment: `db5cf7a5-0e29-40a6-b730-c90166f63ee5`
- Patch file: `operators/consolidate_subcategory.py`
- Code hash: `010ec37d370caf18e88d66e7e094986c62c3d18fa7430b1e7e84d7a78b481d41`
- Champion v2 snapshot hash: `082f20aef515c2e94006951b6b4193d5044745fec083ca2ba5934c67242fbcd7`

Evidence chain:

| Stage | Cases / seeds | Result | Runtime policy |
|---|---|---|---|
| Screening | 10 cases x seeds 42,137 = 20 pairs | W/L/T=9/0/1, median_delta=3.0, CI [2.5,8.0], decision `queue_validate` | Runtime sufficient, supporting only. |
| Validation | 6 cases x seeds 7,19,83 = 18 pairs | win_rate=1.0, median_delta=34.5, CI [12.0,110.0], decision `queue_frozen` | Runtime high/sufficient. |
| Frozen | 4 cases x seeds 256,512,1024 = 12 pairs | win_rate=1.0, median_delta=60.5, CI [13.0,220.0], decision `promote` | Runtime high/sufficient; still excluded as standalone optimization signal. |

Contract/Verification/Canary 全部 passed；metrics 里 strict case path resolution 显示 champion 和 candidate 都解析到各自 workspace；`replay_identity.status=complete`，包含 code hash、patch digest、problem spec hash、seed ledger hash、split manifest hash、protocol version、raw metrics ref。v3/v0.4 边界上，这次 promotion 是合规的：LLM 只产生候选，真正晋升由 protocol evidence 和 DecisionFeatures 触发。

Champion v2 operator pool 增加 `consolidate_subcategory`，权重 0.259259；原六个 baseline operators 权重相应下调。没有看到 validation/frozen 泄漏回 proposal 决策；后续分支以 v2 为 base champion 继续搜索。

## Accounting 分析

关键数字可以统一如下：

| 口径 | 数值 | 解释 |
|---|---:|---|
| `proposal_attempts_total` | 21 | campaign step 级尝试，包含 1 个 proposal block。 |
| scheduler counted attempts | 20 | max-round budget 的 effective attempts；step 6 proposal block 不计。 |
| DB `event_kind=experiment` | 19 | 17 screening protocol metrics + 1 validation + 1 frozen；这正好解释 `run.log experiments : 19`。 |
| DB `event_kind=verification_fail` | 1 | `pair_exchange_cost_guard` V9 perf heavy failure；计入 effective rounds，但没有 protocol metrics。 |
| formal candidate artifacts | 17 | 与 17 个成功进入 screening protocol 的候选一致。 |
| status `formal_screened_candidates` | 18 | 应理解为 screening-stage formal/verification-consumed candidate attempts；若按 status 文案 “screening-stage protocol results” 严格解释，则多算了 V9 heavy failure。 |
| status `protocol_evaluated_candidates` | 20 | 实际等于 17 screening protocol rows + validation + frozen + 1 verification-heavy candidate attempt；status 的 `protocol_stage_counts.screening=18` 把 V9 heavy failure 归入 screening bucket。 |

判断：run.log 的 19 是正常展示差异，不影响 run validity；但 status 里 `formal_screened_candidates_semantics` 和 `protocol_evaluated_candidates_semantics` 对 V9 heavy failure 的描述不够精确。这是框架 reporting/terminology 问题，不是本次实验证据链断裂。建议后续把 “protocol evaluated” 拆成 `protocol_metric_results` 和 `verification_consumed_candidates`，并让 run.log 打印 `effective_rounds_completed` 与 `quality_blocks`。

## Fresh runtime replay 分析

`fresh_runtime_replay_drain_status=pressure_no_replayable_candidate` 的来源很清楚：

- Drain attempts: 1
- Executed: 0
- Blocked: 1
- Closure status: `pressure_no_replayable_candidate`
- Detail: “fresh champion runtime pressure exists but no structured replay pending candidate is materializable”
- Pressure candidates: `0eab5d17` and `baa6368a`
- Both candidates had `runtime_evidence_status=fresh_champion_required`, `fresh_runtime_required=true`, `runtime_evidence_pressure_count=2`, but `fresh_runtime_pending=false` and no scheduler marker.

为什么不可物化：这些 branch 的 current head 是 `active_no_effect`，runtime aggregate 因 low cached champion / fresh champion required 被排除，但系统没有结构化 pending replay candidate，也没有选择 `replay_existing`。最后一次 scheduler action 是 `run_existing` / `refine_active` / `same_branch_low_signal_observation_sample`，drain 因 “scheduler did not select replay_existing” skip。

P1 修复是否按预期：是，至少没有把 pressure 静默吞掉。status 里有 closure、unresolved closure、候选列表和 `decision_features_excluded=true`。还需要后续修复：让 runtime pressure 到 replay materialization 之间有明确状态转换，例如当 `fresh_runtime_required=true` 且 replay identity complete 时自动生成 `fresh_runtime_pending`，或明确记录为什么 replay identity 不可用；同时不要把 replay pressure 当作 DecisionFeatures。

## 是否说明 Scion agent 能做有效研究

能，但要限定在 warehouse 20R 的证据范围内。

支持点：

- 20 effective attempts 中出现 1 个强晋升，且三阶段 evidence 完整。
- 后续候选大多符合 warehouse mechanics，没有明显把 problem semantics 弄错：都围绕 split/cost、锁单、容量、hazard、pickup/category/region compatibility、no-op guard。
- Agent 能从失败调整方向：pair merge 失败后不继续硬推 merge；tail weak-positive 后尝试 refinement；refinement no-op 后清洁分叉；pair exchange perf failure 后转向 bounded vehicle elimination。
- Contract/Verification/Protocol 边界基本工作：1 个 proposal 被 quality gate 拦截，1 个 slow candidate 被 V9 perf guard 拦截，晋升没有读 LLM 自由文本。

限制点：

- 晋升主要来自第一轮强命中，后续 16+ attempts 多为 weak/marginal/no-effect/regression，说明 search after promotion 进入 plateau。
- `fresh_runtime_replay` 还只是暴露 pressure，未能自动物化 replay。
- Accounting terminology 需要收紧，否则后验报告容易误读 formal screened / protocol evaluated。
- Warehouse 的 objective 是强结构化、局部算子容易解释；CVRP 的路线结构、算子交互和 benchmark variance 更难。

是否可作为升轮次依据：可以作为“P1 修复后 agent loop 没有坏、且 warehouse 可扩到更高轮次”的依据；不应单独作为 CVRP 大规模升轮次依据。更合理的下一步是 warehouse 40R/60R 验证 replay materialization 和 plateau handling，同时用 CVRP 小批量对照确认 lessons/reporting 在更难问题上不退化。

## 可迁移到 CVRP 与不可迁移结论

可迁移：

- v3 边界有效：LLM proposal -> gates -> protocol -> DecisionFeatures 的链路能保护晋升。
- Cross-branch lessons 作为 proposal visibility 有实际路线影响，且不会污染 Decision。
- Accounting 必须区分 proposal block、verification failure、protocol metric result、validation/frozen。
- Runtime evidence 应保持 supporting/audit only，fresh champion pressure 要有结构化 replay 闭环。

只属于 warehouse 或较弱迁移：

- `ConsolidateSubcategory` 的成功依赖 warehouse 的 `vehicle_subcategory` split objective；CVRP 没有同构目标。
- Warehouse feasibility/oracle 对局部重排给出强反馈，CVRP 的距离、route capacity、time/window 或 neighborhood effects 可能更噪、更慢。
- 这次 champion v2 的巨大 frozen delta 不能推断 CVRP 会有同样首轮强命中。

## 后续建议

1. 修 accounting 文案和指标：`run.log` 打印 effective/protocol/verification/proposal block 四类；status 将 V9 heavy failure 从 “protocol result” 文案中拆出。
2. 修 fresh runtime replay materialization：当 pressure candidate 有 complete replay identity 或可重建 patch 时，生成 `fresh_runtime_pending`；否则记录不可物化的具体缺失 key。
3. Warehouse 可升到 40R/60R，但应重点看 promotion after v2、plateau exit、fresh runtime replay 是否执行，而不是只看 champion_version。
4. CVRP 对照建议先做小轮次 verified rerun，重点比较 proposal mechanics 是否仍贴合问题，而不是直接用 warehouse 的晋升率推断 CVRP 搜索能力。
