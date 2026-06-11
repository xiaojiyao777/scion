# Scion v0.4 核心框架代码审查与瓶颈分析

Date: 2026-06-11
Scope: scion 核心框架代码审查 + 最新两组 8R 实验逐层审计
Governing boundary: `scion/design/scion-architecture-v3.md`
Audit discipline: `scion/reports/v04-audit-agent-experiment-guide-20260609.md`

## 0. 审查对象

- 代码：`scion/scion/` 下 core / protocol / proposal / contract / verification /
  config 各层（重点：campaign_loop、decision、features、gates、stats、
  branch_lifecycle_policy、agentic session 链路、hypothesis prompt 构造）。
- 实验（均为 2026-06-10，gpt-5.5，commit 467b58f，--rounds 8，
  --time-limit-sec 30，agentic proposal）：
  - CVRP: `v04-post-redesign-verify-cvrp-8r-gpt55-20260610T132507Z-claw`（无晋升）
  - Warehouse: `v04-post-redesign-verify-warehouse-8r-gpt55-20260610T132507Z-claw`（1 次晋升 champion_v2）

## 1. 结论摘要

1. **v3 决策边界不变量在代码层完好**。`DecisionEngine.decide()` 入口强制
   `_validate_no_free_text(features)`；`SafeFeatureExtractor` 只产出数值/枚举；
   BKS/gap 等问题域事实未进入 `DecisionFeatures`；gates 纯确定性。
   未发现 P0 级框架损坏。本次"VRP 无晋升"不是决策边界或证据链问题。
2. **CVRP 瓶颈的主因是研究对象的"效应量/噪声比≈0"**（问题包 + 协议层），
   而不是 agent 提案质量，也不是框架核心。candidate 的 pair 级
   win≈loss≈噪声（最好的候选 14W/11L/7T），case 级 win_rate 全部 0.375 左右，
   远低于 0.6 阈值。在 30s 饱和预算下 ALNS+VNS 的 run-to-run 方差与
   候选机制的真实效应同量级，screening 测的是噪声。
3. **Warehouse 晋升证明闭环成立**：screening 15W/5L → validation 16W/2L →
   frozen 12W/0L → promote。差异不在框架，在效应量：warehouse delta 以千计
   （基线弱、headroom 大），CVRP delta 以 ±50 计（基线强、预算内噪声同级）。
4. **协议层对 anytime solver 的 runtime 治理产生系统性噪声**：
   10/10 候选触发 `SCREENING_RUNTIME_BUDGET_SATURATION`（saturation≈0.99 vs
   阈值 0.9），champion 缓存使 runtime 证据降级为 low_confidence，
   触发 `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`，2 轮 fresh replay 消耗了
   round 预算。对一个设计上就用满时间预算的求解器，这套治理只产生告警噪声。
5. **上下文退化仍是真实的二级问题**：CVRP hypothesis prompt 中位数 ~190k 字符
   （warehouse ~74k），其中治理/合规 JSON（cross-branch map 23k、
   branch lesson required_response、"Do Not Claim" 块）和稠密机器格式
   telemetry dump（Runtime Feedback 12k）占比远超蒸馏后的研究洞见。
   但本轮提案质量尚可（机制多样、有依据），说明它当前主要推高成本
   （8 轮 1.25M tokens）而非直接阻塞研究。
6. **搜索形态与问题难度不匹配**：8 轮摊到 4 个分支，最大深度 3；
   4/8 轮的 hypothesis prompt 中 "Experiment History — This Branch" 为空
   （新分支首轮）。对强基线问题，浅而散的搜索几乎不可能积累出可晋升的改进。

## 2. 实验逐层审计

### 2.1 CVRP 8R（无晋升）

计数核对（status.json / campaign_summary.json / metrics 一致）：

- proposal_attempts=10, quality_blocks=0, verification_failure=0
- protocol_metric_results=10（全部 screening），validation=0, frozen=0
- effective_rounds=8，non_effective=2（fresh runtime replay）
- formal_candidate_artifacts=8（replayable patch 子集），replay_identity 全部 complete
- stopped_reason=max_rounds_exhausted，wrapper exit 0

逐候选 pair 级结果（32 pairs = 8 cases × 4 seeds，create_new 为 48）：

| metrics | 机制/目标文件 | pair W/L/T | gate | 主要 reason |
|---|---|---|---|---|
| e50502cf | capacity_slack_regret_repair (destroy_repair) | 14/11/7 | fail | WIN_RATE |
| 06d2e092 | (destroy_repair 变体) | 10/11/11 | fail | WIN_RATE |
| df27badf | route_merge_reinsertion (local_search) | 10/5/17 | fail | WIN_RATE |
| a83533f3 | local_search 变体 | 7/8/17 | fail | WIN_RATE |
| 0acbb613 | destroy_repair 变体 | 7/5/20 | fail | WIN_RATE |
| 8feba313 | route_ejection.py (create_new, 48 pairs) | 6/2/40 | fail | WIN_RATE |
| a9fd2c05 | scheduler | 2/3/27 | unclear | FRESH_CHAMPION_REQUIRED |
| a8001d5a | — | 1/0/31 | fail | WIN_RATE |
| 0fbf8bcf | — | 1/1/30 | unclear | FRESH_CHAMPION_REQUIRED |
| 9fe039bf | — | 0/2/30 | fail | WIN_RATE |

关键观察：

- **非 tie 对确实存在**（VNS 全吸收的强命题再次被否定），但 win≈loss，
  delta 范围 ±~50（champion total_distance 量级 ~1000–1500，即 <0.5–3%），
  与 seed 间方差同量级。case 级多数票后 win_rate≈0.375，无一接近 0.6。
- 同 case 同 seed 的 pair（A-n64-k9, seed 11）：candidate 与 champion
  total_distance 同为 1453.0 → tie。配对（共用 seed）无法抵消 ALNS/VNS
  轨迹混沌：微小代码改动即令搜索轨迹分岔，配对方差缩减失效。
- 所有 10 个候选均带 runtime saturation 告警；champion 结果 7/10 来自缓存
  → runtime_confidence=low_cached_champion → 2 轮 fresh replay 重测。
- 4 个分支的假设机制各异且合理（slack-aware regret repair、route merge
  reinsertion、scheduler 限路压缩、route ejection polish），target intent
  preflight、grounding、telemetry 契约全部正常工作。
  **提案层不是本轮的约束因素。**

### 2.2 Warehouse 8R（1 次晋升）

- 8 protocol rows：screening 3（全 pass）、validation 3（2 pass 1 fail）、
  frozen 2（1 pass→champion_v2，1 fail HIERARCHICAL_UNCERTAIN）。
- 典型 delta：screening -15594…+7801，frozen 12W/0L delta 最高 +92054。
  效应量比 CVRP 大 3 个数量级（不同 objective 量纲，但 W/L 分离度才是关键）。
- 晋升 dossier 完整（promotion_experiment_id、patch_hash、code_snapshot_hash）。
- 假设质量同样合理（subcategory consolidation、compatibility-scored merge），
  与 CVRP 同一套 agent 链路。

### 2.3 对照结论

同一框架、同一模型、同一轮数：warehouse 走完 screening→validation→frozen→promote
全链路；CVRP 全部死在 screening 的 win_rate 上。失败层分类：
**10/10 属 "algorithm signal / research object" 层**，0 例 proposal quality、
0 例 contract、0 例 verification、0 例 infra。

## 3. 代码层审查发现

### 3.1 核实为健康的部分

- `core/decision.py`：纯确定性；入口校验无自由文本；runtime veto 先于
  阶段判定；lifecycle policy 与 Decision 分离。
- `core/features.py`：失败码两层枚举白名单；UUID/metric id 正则校验。
- `protocol/gates.py` + `protocol/stats.py`：case 级统计单位（majority vote
  跨 seed + median delta + bootstrap CI + 层级字典序 statistical_status），
  与 v3 §7/§8 一致。
- `protocol/experiment/feedback.py::_aggregate_pairs_to_case_level`：实现正确。
- 证据链：metrics 文件含 per-pair 完整 runtime/telemetry/objective、
  case path resolution、time limit policy；formal candidate artifacts 带
  replay_identity；两实验计数自洽。

### 3.2 问题发现（按优先级）

**F1 [P1, 协议×问题包] screening 对 CVRP 无统计功效，且无功效自检。**
gates 只看 win_rate/median_delta/CI，框架没有任何机制回答
"在当前 (cases, seeds, time_limit, 求解器方差) 下，多大的真实改进才能以
多大概率通过 screening"。CVRP 当前配置下答案接近"几乎任何现实的局部机制
改进都过不了"。这不是 gate 写错，而是协议层缺一个 **A/A 噪声底盘标定**
（champion vs champion 不同 rng 流）作为问题包上线/重设计的 readiness 检查。
6/9 的 case 重设计（去饱和、扩 seed）解决了"无 BKS 空间"问题，
但没有解决"30s 预算内方差淹没效应"的问题。

**F2 [P1, 协议] runtime 治理对满预算 anytime solver 产生系统性摩擦。**
`RuntimeGovernanceConfig.champion_runtime_policy=fresh_required_for_runtime_tie`
+ champion result cache 的组合，使每个 tie 倾向的候选都要求 fresh champion
重放（本次消耗 2 轮）；saturation 告警 10/10 触发但无信息量
（BASELINE_TIME_FRACTION=0.8 设计上就饱和）。建议：问题包可声明
`expected_budget_saturation: true` 时抑制 saturation 告警；champion fresh
runtime 在每个 champion 版本预热一次，而非占用候选轮次。

**F3 [P2, 调度] 分支深度与问题难度不匹配。**
8 轮 / 4 分支 / 最大深度 3，且每个新分支首轮 branch history 为空。
v3 §11.1 的本意是"分支内深度探索"；当前 lifecycle policy
（zero_win_streak_limit=3、no_effect_followup_limit=2 等）在低信号问题上
倾向于 park/archive 后开新分支，造成浅而散。对 CVRP 这类强基线问题，
应考虑：减少并发分支数、提高同机制 follow-up 配额、或把"轮"预算改为
"分支深度"预算。

**F4 [P2, 上下文] 治理/合规负载仍然主导 prompt。**
最后一轮 CVRP hypothesis prompt 分解（字符数）：
sys0 69k（30k 全量算法文件读取 + 21k solver map receipts + 6.5k facts），
sys1 46k（23k cross-branch map——大部分是 required_response/reason_codes
合规 JSON，12k Runtime Feedback——稠密不可读的 telemetry 串），
user 39k（21.6k tool observations + 3.9k "Do Not Claim" + 3k analysis steps）。
蒸馏后的研究信号（"哪个机制在哪些 case 上为什么输"）需要模型自己从
telemetry 串里挖。建议把 cross-branch lesson 渲染为机制级一句话结论 +
证据计数，把 Runtime Feedback 渲染为紧凑表格。token 成本对比：
CVRP 8 轮 1.25M tokens vs warehouse 8 轮 ~0.4M。

**F5 [P3, 配置] `min_practical_delta` 硬编码 0.001（protocol_config.py:437）。**
protocol.yaml 的 `median_delta_min: practical_delta_screen` 字符串从未被
解析为问题包数值，所有问题共用 0.001 绝对值。对 CVRP（distance 量纲千级）
等价于无实际效应过滤；对未来量纲更小的问题可能反向过严。应实现
problem.yaml 键引用解析，或至少在文档中标明该字段当前不生效。

**F6 [P3, 观测] `runtime_regression_rate=0.53` 这类指标在饱和预算下无意义**
（candidate elapsed 与 champion elapsed 都≈time_limit，比较的是毫秒级抖动），
却被写入 runtime_stats 并渲染进 feedback。建议在饱和场景下标记为
not_applicable。

## 4. 瓶颈归因（按层）

| 层 | 判定 | 依据 |
|---|---|---|
| 框架核心（决策边界/证据/lineage） | 健康，非瓶颈 | §3.1；两实验证据链自洽；warehouse 全链路晋升 |
| 提案层（agentic session/假设质量） | 工作正常，非本轮约束 | 10 个假设机制多样、有 grounding、0 quality block |
| 问题包（CVRP 研究对象） | **主要瓶颈** | 30s 饱和预算下效应/噪声比≈0；case 级 wr≈0.375 全军覆没 |
| 协议层 | **次要瓶颈（放大器）** | 无功效标定；runtime 治理摩擦消耗 2/10 轮；8R 预算远低于问题难度 |
| 上下文层 | 二级问题（成本+潜在质量上限） | 治理 JSON 与 telemetry dump 主导 prompt |
| 调度/生命周期 | 二级问题 | 浅而散，分支深度不足 |

核心一句话：**框架能正确地测量，但 CVRP 当前研究对象给不出可测量的梯度；
agent 在做真研究，protocol 在诚实地告诉它"信号不显著"，而这两者之间缺的是
一个有统计功效的实验设计。**

## 5. 建议行动（优先级序）

1. **A/A 标定（先做）**：champion vs champion（同 seed 集、不同 rng 流或
   重复运行）跑一次 screening 协议，量化每个 case 的 pair 级噪声分布与
   "假阳性 win_rate"。以此回答：当前 split/seeds/time_limit 下，
   多大的真实 Δdistance 能以 ≥80% 功效通过 0.6 win_rate 门。
   这是问题包 readiness 检查，结果留在问题域诊断层，不进 DecisionFeatures。
2. **基于标定重设计 CVRP screening 测量**，候选方向（按侵入性排序）：
   减少 case 数、加 seed 数（majority vote 在 4 seeds 上量化粒度太粗）；
   把 case 级 majority vote 改为问题包可声明的连续聚合（如 mean relative
   delta + CI），保留 v3 case 统计单位语义；提高 time_limit 降低方差
   （已有 time-limit diagnostic 报告支持）；或缩小实例规模使 30s 相对充裕。
3. **runtime 治理豁免**：问题包声明 expected-saturation；champion fresh
   runtime 按 champion 版本预热，不占轮次。
4. **调度向深度倾斜**：CVRP campaign 限 2 个并发分支、放宽同机制 follow-up；
   下一次正式跑 ≥40R。
5. **上下文蒸馏**（独立 workstream，按 6/9 报告的分类法量化前后对比）：
   cross-branch map 改为机制级结论行；Runtime Feedback 表格化；
   合并重复的 governance 指令块。
6. **修 F5**（practical_delta 键解析）并补 F6 的 not_applicable 标记。

## 6. 有效性边界

- 本审计基于 8R 短程实验；CVRP 在 40R+ 深分支下的行为未被本次数据覆盖。
- "效应/噪声比≈0" 的定量结论依赖 pair delta 分布的目测量级（±50 vs ~1453），
  精确功效数字需要建议 1 的 A/A 标定。
- 上下文负载与提案质量的因果关系本轮无法分离（提案质量尚可），
  需要蒸馏前后的对照实验。
