# Scion v0.4 CVRP 12R 分支研究质量分析

实验路径：`/home/clawd/research/scion-experiments/v04-branch-learning-transfer-verify-12r-gpt55-12r-gpt55-20260608T110808Z-claw/campaign`

分析时间：2026-06-08

架构边界基准：已先阅读 `scion/design/scion-architecture-v3.md`。本报告按 v3 边界解释实验：LLM 只产生 tainted proposal/code；Decision 只应读取 Contract/Verification/Protocol 后的 `DecisionFeatures`；cross-branch lessons 只能影响 proposal visibility/observability，不应进入 Decision。

## 1. 证据范围与运行完整性

读取证据：

- `scion.db`：`branches`、`hypotheses`、`experiment_events`
- `campaign_summary.json`、`status.json`、`run_status.json`
- `agentic_sessions/*/output.json` 与 trace index
- `metrics/*.json`
- `artifacts/formal_candidates/*/candidate.diff`
- `champions/champion_v1/active_solver_facts.py` 与 active solver code

运行完整性：

- run valid: `requested_rounds=12`，`effective_rounds_completed=12`，`run_complete=true`
- 协议阶段：12 个 screening，0 个 validation，0 个 frozen
- Contract/Verification：12 个有效候选均 `contract_passed=True`、`verification_passed=True`
- Infra/model repair：无 infra failure，无 model repair，无 verification failure
- Promotion：0 accepted，0 promoted
- evidence/lineage：`evidence_integrity.status=complete`，`lineage_integrity.status=complete`

因此，本次不是“候选晋升验证”实验，而是“12 次 screening 下分支学习/探索路线是否有效”的实验。

## 2. 基线求解器与活跃问题事实

active solver 是 ALNS+VNS：

- construction：大实例用 sweep，小实例用 Clarke-Wright；route cap 超限时 capacity-balanced；不可行时 nearest-neighbor fallback；可选 initial VNS。
- ALNS：destroy operators = random/worst/shaw/route；repair operators = greedy/regret2/regret3；adaptive weights。
- loop 中先 destroy/repair，再可选 embedded VNS；之后检查 feasibility 和 `max_routes`；最后按 best/better/SA 接受并记录 move。
- VNS active neighborhoods 包括 intra two-opt、relocate、Or-opt 1/2/3、swap、two-opt-star。
- objective semantics 是 declared lexicographic：fleet violation 高优先级，total_distance 是本次实际可动目标。

这组 proposal 大多抓住了真实 mechanics：route cap 之后的 repair rejection、repair 插入策略、VNS neighborhood 表达能力、acceptance plateau、construction seed、scheduler telemetry。问题不在“LLM 完全乱猜”，而在 screening 信号很弱，且很多机制虽然可运行但没有带来可操作 objective effect。

## 3. 12 轮逐轮次时间线

| 轮次 | 分支 | 机制 | 文件 | screening 结果 | lifecycle/decision | 研究判断 |
|---:|---|---|---|---|---|---|
| 1 | `554f27f5` | `route_count_penalized_repair` | `destroy_repair.py` | 1W/0L/7T, median 0, CI [-0.25, 0.5], pair 3W/3L/10T | continue, marginal | 合理起点。有 E-n101-k8 正信号，但 pair 层正负相抵。 |
| 2 | `554f27f5` | same refinement: slack-aware top-k | `destroy_repair.py` | 1W/1L/6T, median 0, CI [0, 2.5], pair 4W/2L/10T | continue, marginal | 吸收第 1 轮弱正，做同机制 refinement；但 B-n52-k7 明确 loss。 |
| 3 | `554f27f5` | same refinement: conditional distance-first slack | `destroy_repair.py` | 1W/1L/6T, median 0, CI [0, 0], pair 3W/3L/10T | continue, marginal | 针对第 2 轮 compact loss 缩窄触发，科学上合理；结果仍未改善 win rate。 |
| 4 | `8d706f9c` | `route_merge_lookahead_vns` | `local_search.py` | 0W/0L/8T, pair 0W/1L/15T | continue, fresh runtime replay pending | 换到 local-search 全路由吸收，机制互补；但实际无 case-level 正信号，且有 E-n33-k4 pair loss。 |
| 5 | `992bc9d5` | `stagnation_reheat_acceptance` | `acceptance.py` + scheduler | 0W/0L/8T, pair 0W/1L/15T | continue, fresh runtime replay pending | acceptance plateau 假设合理但间接，结果无 objective effect，B-n31-k5 pair loss。 |
| 6 | `07efe6aa` | `search_observability_bridge` | new `telemetry.py` + scheduler | 0W/0L/12T, pair 0W/0L/24T | continue, parked later | 纯观测桥；符合 v3 的 proposal observability 思路，但不应占用与质量候选同等解释权。 |
| 7 | `c8153cba` | `quota_repair_activation_bridge` | `scheduler.py` | 0W/0L/8T, pair 0W/0L/16T | continue, parked later | pre-rejection salvage 假设贴近 scheduler mechanics；telemetry 显示 activation observed 但 effect zero。 |
| 8 | `ed9c31c0` | `route_limit_seed_diversification` | `construction.py` | 0W/0L/8T, pair 0W/0L/16T | continue, parked later | 换到 construction seed portfolio，避免重复 repair/VNS；实际完全 tie。 |
| 9 | `16fafdc4` | `operator_effect_observability_bridge` | `scheduler.py` | 0W/0L/8T, pair 0W/1L/15T | continue, diagnostic_repair | 比第 6 轮更接近决策边界的观测桥；但本应行为等价，却出现 E-n101-k8 pair loss，说明观测插桩也可能扰动搜索预算/随机路径。 |
| 10 | `ee49d575` | `three_route_ejection_chain_vns` | `local_search.py` | 0W/1L/7T, median -0.75, CI [-3, 0], pair 1W/5L/10T | abandon/archive | 机制新颖且直接作用 total_distance，但损失明显，soft abandon 合理。 |
| 11 | `3fb8782b` | `demand_clustered_seed_construction` | `construction.py` | 0W/0L/8T, pair 0W/0L/16T | continue, active_no_effect | 与第 8 轮同属 construction，但差异是 demand/geographic clustering；结果仍完全 tie。 |
| 12 | `3331f7c7` | `bounded_slack_regret_repair` | `destroy_repair.py` + scheduler | 0W/2L/6T, median 0, CI [-10, 0], pair 2W/6L/8T | abandon/archive | 从第 1-3 轮弱正抽象出 capacity-slack repair，但结果更差；abandon 合理。 |

## 4. 按分支研究脉络

### 4.1 `554f27f5` - route-count-aware repair 主线

假设质量：

- 第 1 轮指出 repair 会在 scheduler route-cap rejection 之前创建多余 route，导致 ALNS/VNS 预算浪费。这个 weakness 直接来自 active solver facts，合理。
- 第 2 轮没有换题，而是根据第 1 轮边际正信号继续做 slack-aware tie-break，试图改善“容量过早被便宜插入吃掉”的 problem mechanics。
- 第 3 轮再根据第 2 轮 compact-case loss，将 slack tie-break 缩窄为 conditional/distance-first，属于有效分支内迭代，而不是随机换 patch。

代码机制：

- 第 1 轮改 `_greedy_insertion` / `_regret_insertion`，传入 `max_routes`，对 new route fallback 加 guard/penalty；scheduler 调 repair 时传 route cap。与 hypothesis 一致。
- 第 2 轮增加 `_median_removed_demand`、`_slack_aware_insertion` 类逻辑，让 existing-route insertion 不只看最小 delta。与 hypothesis 一致，但会真实改变距离选择。
- 第 3 轮缩窄 slack bias 的触发条件，试图保持距离优先。与 hypothesis 一致，不是形式化改动。

结果：

- 三轮都没有过 screening gate。case-level win rate 最高仅 1/8；第 2、3 轮都有 1 个 case-level loss。
- 正信号集中在 E-n101-k8，负信号集中在 B-n52-k7 / B-n31-k5；说明机制可能只对大实例或 route-pressure 形态有效，不是普适改善。
- lifecycle 保留为 `active_marginal`，`best_quality_checkpoint_id` 指向第 3 轮 checkpoint，合理但证据很弱。

判断：

- 这是本次最像“有效研究”的分支：假设来自真实 mechanics，分支内会根据上一轮结果缩窄机制。
- 但 weak positive 不足以 validate；更适合做 targeted diagnostic/subgroup 分析，而不是继续盲目加轮次。

### 4.2 `8d706f9c` - route merge lookahead VNS

假设质量：

- 分支从 repair route-count 转向 local_search route absorption，明确 contrast：不是 repair scoring，而是 VNS whole-route absorption。
- 目标是 total_distance，同时不增加 route count，符合 lexicographic boundary。

代码机制：

- 在 `local_search.py` 加 whole-route absorption/lookahead operator，并加入 `_default_vns_operators`。
- 机制真实改变搜索空间，不是单纯重命名。

结果：

- screening 0W/0L/8T，pair 0W/1L/15T；无 case-level 正信号。
- lifecycle 标成 `active_quality_regression` / `diagnostic_repair`，candidate code discarded，fresh runtime pending。

判断：

- 机制互补性合格，但其“路线吸收”可能过于保守或激活后不产生可接受 improvement。
- 不应继续深挖同一 route-merge 形式，除非先证明 activation opportunity：哪些 case 存在可全路由吸收但 baseline VNS 表达不到。

### 4.3 `992bc9d5` - stagnation reheat acceptance

假设质量：

- 从前面 route-count/VNS 的弱信号转向 acceptance schedule，避免重复同一文件。
- 假设是 ALNS plateau 后 SA 过冷，接受 uphill move 不足。这个 mechanics 可能成立，但比 repair/VNS 更间接。

代码机制：

- `acceptance.py` 增加 reheat state；scheduler 追踪 `iterations_since_best` 并在 plateau 时触发短 reheat。
- 代码与 hypothesis 一致，不是形式化改动。

结果：

- 0W/0L/8T，pair 0W/1L/15T，B-n31-k5 有 loss。
- 没有证明 acceptance 是 bottleneck。

判断：

- 该分支是合理的 breadth exploration，但证据不支持继续。
- 后续应避免把“tie-dominated”直接解释为需要更高 acceptance；需要先看 rejected candidate 的质量分布。

### 4.4 `07efe6aa` - search observability bridge

假设质量：

- 该分支承认前面结果 tie-dominated 且 attribution 弱，转向 mechanism-specific telemetry。
- 这符合 v3 中 Context/observability 可服务后续 proposal 的边界，但它本身不是 quality mechanism。

代码机制：

- 新增 `telemetry.py` helper，并在 scheduler loop 周围记录 bridge iteration/phase/improvement。
- 行为目标是 no-op，主要产生观测。

结果：

- create_new screening N=12，0W/0L/12T，pair 0W/0L/24T。
- code retained/checkpoint retained，但 lifecycle 后续 parked。

判断：

- 作为“研究基础设施”有价值，但不应与 solver quality candidate 混合计为同类 improvement attempt。
- 本次 summary 的 `candidate_intent_counts` 把 12 个都标成 `observability_candidate`，暴露出 intent taxonomy 可能过宽：真正质量机制和纯 telemetry 候选在报告上没有区分清楚。

### 4.5 `c8153cba` - scheduler pre-rejection quota salvage

假设质量：

- 指向 scheduler route-cap rejection 之前的 salvage，和 active solver loop 精确相关。
- 与 repair-file route-count penalty 的区别明确：不是改变 repair 选择，而是在 rejection 前尝试 collapse excess route。

代码机制：

- 在 scheduler route-cap check 前调用 `_quota_repair_activation_bridge`，尝试清空小/excess route。
- 加入 telemetry 记录 salvage activation/effect。

结果：

- 0W/0L/8T，pair 0W/0L/16T。
- campaign_summary 中有 `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`：candidate present，但 positive effect 0；activation observed，effect zero。

判断：

- 假设合理，结果很有诊断价值：说明当前 screening 下这个 salvage path 没有带来 objective effect。
- 适合 park；除非能从 raw telemetry 找出大量 over-quota-but-salvageable candidates，否则不应继续。

### 4.6 `ed9c31c0` - route-limit seed diversification

假设质量：

- 从 repair/local_search/acceptance 转向 construction seed，多样性上合格。
- 目标是 route-limit-valid construction portfolio，减少 ALNS/VNS 后续负担，符合 CVRP mechanics。

代码机制：

- `construction.py` 加 rotated sweep / balanced variant portfolio；scheduler 初始解阶段在 budget 内尝试更低 cost seed。
- 真实改变 construction，但受“只在更好且可行时替换”保护。

结果：

- 0W/0L/8T，pair 0W/0L/16T。

判断：

- 完全 tie 表明要么 portfolio 很少替换 incumbent，要么替换后被后续 ALNS/VNS 抹平。
- 后续需要记录“seed replaced count / initial_delta / final_delta”，否则无法判断机制是 inactive 还是 downstream erased。

### 4.7 `16fafdc4` - scheduler operator-effect observability bridge

假设质量：

- 从第 6 轮“单独 telemetry module 无 effect”升级为 scheduler outcome boundary 观测，说明有吸收 sibling lesson。
- 目标是区分 inactive/no-removal/route-limit rejection/accepted/best-improving，问题定位合理。

代码机制：

- 在 ALNS loop 记录 `operator_effect_observability_bridge` iteration/move/phase。
- 声称 behavior no-op，但实际增加 per-iteration context calls。

结果：

- 0W/0L/8T，pair 0W/1L/15T，E-n101-k8 有 loss。
- 被标为 quality_regression/fresh runtime pending。

判断：

- 这是一个重要负例：观测桥可能扰动 runtime budget 或 context side effects，不能默认“插桩无害”。
- 如果要继续 observability，应在不进入 solver hot loop 或更严格 budget-equivalence 的条件下实现。

### 4.8 `ee49d575` - three-route ejection-chain VNS

假设质量：

- 明确指出 baseline VNS 缺少三路补偿 relocation，目标直接是 total_distance。
- 与 route_count repair、route_merge、scheduler quota、acceptance 均有 contrast，机制互补性好。

代码机制：

- `local_search.py` 增加 `_three_route_ejection_chain_vns` 并注册到 VNS operators。
- 搜索 top source/removal/insert candidates，要求 capacity-feasible 和 route-count preserving。

结果：

- 0W/1L/7T，median -0.75，CI [-3, 0]，pair 1W/5L/10T。
- B-n31-k5、B-n52-k7、E-n33-k4 多个 loss，E-n101-k8 mixed。
- Decision `abandon`，reason 包含 loss without win / non-positive CI / negative delta。

判断：

- Abandon 正确。该机制真实但方向不佳，可能因为局部链动作破坏当前 VNS 已优化的结构，或 top-k chain 选择过粗。
- 不建议在同形态上继续深挖，除非先做 offline oracle 检测存在三路负 delta move 的 case。

### 4.9 `3fb8782b` - demand-clustered construction seed

假设质量：

- 与第 8 轮 construction diversification 形成 nearby but distinct：高需求客户 + 地理聚类，而不是 rotated sweep/balanced variant。
- 使用 active solver facts 说明已有 sweep/CW/capacity-balanced/nearest-neighbor，novelty 表述合格。

代码机制：

- `construction.py` 加 `_demand_clustered_construction`，scheduler 中仅在 feasible、route-limit 内、lexicographically no worse 时替换。
- 机制真实，但 guard 很强，可能经常不替换。

结果：

- 0W/0L/8T，pair 0W/0L/16T，active_no_effect。

判断：

- 合理但无效。与第 8 轮共同说明 construction seed 类在当前 screening/time budget 下没有可见 final objective 贡献。
- 后续除非拆分 initial-cost 和 final-cost，否则继续 construction seed 的边际信息很低。

### 4.10 `3331f7c7` - bounded slack regret repair

假设质量：

- 该分支试图从 `554f27f5` 的弱正中抽象出 capacity-slack repair，而不是 route-count soft proxy。
- 这是一次弱正“变体迁移”，但 cross-branch summary 中 `weak_positive_transfer_count=0`，说明系统并未把它登记为有效 transfer，只是 contrast/reject weak positive。

代码机制：

- 新增 `_bounded_slack_regret_repair`，注册到 scheduler repair_ops。
- scoring 使用 regret、move_delta、residual slack penalty；fallback 到 regret insertion。

结果：

- 0W/2L/6T，CI [-10, 0]，pair 2W/6L/8T。
- B-n31-k5、E-n101-k8 case-level loss；P-n101 mixed。
- Decision abandon/archive。

判断：

- Abandon 正确。该结果反证了“slack balance”从 route-count weak positive 中可迁移这一假设。
- 也说明 Scion 需要更强的 weak-positive abstraction：区分“same mechanism weak refine”与“new mechanism transfer”，后者风险明显更高。

## 5. 分支间信息传递质量

可确认的有效点：

- cross-branch observability policy 是 `proposal_observability_only`，`decision_input_policy=excluded_from_decision_features`，符合 v3 边界。
- 12/12 proposal 都有 `branch_lesson_usage`，且 summary 记录 `branch_lesson_usage_satisfied_count=12`、`semantic_mismatch_count=0`。
- 后续分支确实避免了近重复：从 repair -> VNS route merge -> acceptance -> telemetry -> scheduler salvage -> construction -> scheduler observability -> three-route VNS -> demand construction -> slack repair。
- near duplicate count 为 0，说明 novelty/contrast gate 起作用。
- 第 2、3 轮保留了同分支弱正并 refinement；第 4 轮以后多次显式 contrast route_count repair、route_merge、acceptance、observability-only 等 lesson。

不足：

- `weak_positive_transfer_count=0`，说明 cross-branch lessons 主要用于 avoid/contrast，不善于把弱正机制抽象为可验证的 preserve pattern。
- 多数新分支以“fleet_violation stable, total_distance bottleneck, runtime pressure/tie-dominated”为共同开头，但缺少更具体的 subgroup/mechanism opportunity 证据，容易形成“看似多样、实际低命中”的探索。
- runtime 证据在第 1 轮后大量来自 champion cache；summary 多次把 aggregate runtime exclude 为 `low_cached_champion`，因此 runtime pressure 对路线选择只能作 proposal guidance，不能当作强研究事实。
- 观测类分支进入 hot loop 后可能产生 pair loss，说明“observability-only”也需被当成会扰动实验的候选，而不是天然安全的记录层。

## 6. Scion 是否做出了有效研究

结论：做出了部分有效研究，但本次 12R 不足以支持升级到更长轮次直接扩大搜索。

有效性：

- 架构边界基本守住：LLM 文本没有直接驱动 promotion；cross-branch lesson 被标为 proposal visibility only；Decision 仍基于 screening feature/reason code。
- 假设大多来自 active solver mechanics，而非空泛算法口号。
- 分支内 refinement 在 `554f27f5` 上成立：它识别弱正、识别 compact loss、尝试缩窄触发。
- 分支间学习避免了明显近重复，形成了 repair/local_search/acceptance/telemetry/scheduler/construction 的互补探索。
- negative results 被正确处理：three-route VNS 和 bounded slack repair 均被 soft abandon/archive。

限制：

- 12 个 screening 没有任何候选进入 validation，说明当前 proposal/search hit rate 低。
- 唯一边际正信号仍是 `route_count_penalized_repair`，但 case-level 只有 1W/1L/6T，无法支持继续验证。
- 多个分支完全 tie，且没有足够机制级 opportunity 指标解释“没激活、激活无效、被 downstream 抹平、还是 screening 噪声太大”。
- runtime evidence cache 与 low confidence 导致后续路线频繁围绕 runtime pressure 叙述，但这部分证据被系统正确排除在 decision features 外，研究上也不应高估。
- observability 分支消耗了 screening 轮次，却没有产生本轮内可用的下一步诊断闭环。

## 7. 是否适合升级到更长轮次

不建议直接升级为更长轮次。建议先优化后再做更长 run。

优先优化项：

1. 将 quality candidate 与 observability/diagnostic candidate 分账。纯 telemetry 不应按同一 screening success 逻辑解释，也不应污染 improvement hit-rate。
2. 对 tie-dominated 分支增加机制机会诊断：activation count、accepted move count、best_delta positive count、candidate rejected by route cap count、seed replacement count、initial_delta vs final_delta。
3. 对 weak positive 建立 transfer policy：同分支 refine 可继续；跨机制 transfer 必须明确 preserve/avoid 的可检验签名，并要求更小的 diagnostic replay，而不是直接新增完整机制。
4. 修复/降低 runtime cache 对 proposal guidance 的误导：当 champion runtime cached 导致 aggregate runtime excluded 时，proposal 应把 runtime pressure 降级为不确定，而不是继续当主叙事。
5. 对 observability hot-loop 插桩加 budget-equivalence check；如果插桩本身可能改变路径，应走 diagnostic protocol，不应假设 behavior no-op。
6. 在进入更长 run 前，对 `route_count_penalized_repair` 做 targeted subgroup replay：特别比较 E-n101-k8 的正信号与 B-n52-k7/B-n31-k5 的负信号，判断是否存在可条件化的 instance feature。

适合保留的研究路线：

- `route_count_penalized_repair`：只适合做 targeted diagnostic，不适合直接 validate。
- `quota_repair_activation_bridge`：可保留为 zero-effect diagnostic 样本，用于验证 route-cap rejection 机会是否真实存在。
- construction seed 类：除非增加 initial-vs-final attribution，否则暂时 park。

应 abandon/避免重复的路线：

- `three_route_ejection_chain_vns` 当前形态。
- `bounded_slack_regret_repair` 当前形态。
- 未做 budget-equivalence 的 scheduler hot-loop observability。

## 8. 最关键结论

Scion 在本次 12R 中展示了“研究过程治理”是有效的：能基于真实 solver mechanics 生成假设、能按分支吸收 sibling failure/weak signals、能避免近重复、能把负结果 archive/park，并且 cross-branch lessons 没有越界进入 Decision。

但“研究产出质量”还不够：12 个 screening 无一进入 validation，唯一弱正分支仍有对称负例；后续分支多为 no-effect/tie-dominated。当前最需要优化的是机制级 attribution、弱正迁移策略、runtime evidence 置信度处理、observability 与 quality 分账。完成这些优化前，不建议直接拉长轮次；否则更长 run 很可能只是产生更多形式上多样、实质上低信号的分支。
