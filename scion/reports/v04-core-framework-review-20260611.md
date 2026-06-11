# Scion v0.4 核心框架代码审查与瓶颈归因（2026-06-11）

审查范围：scion 核心代码（core / protocol / proposal / config）+ 两组最新实验
- CVRP：`v04-post-redesign-verify-cvrp-8r-gpt55-20260610T132507Z-claw`（8R，无晋升）
- Warehouse：`v04-post-redesign-verify-warehouse-8r-gpt55-20260610T132507Z-claw`（8R，1 次晋升 champion_v2）

治理基线：`design/scion-architecture-v3.md`。审计方法遵循
`reports/v04-audit-agent-experiment-guide-20260609.md` 的分层归因纪律。

---

## 1. 总体结论（TL;DR）

**v3 决策边界与治理闭环在代码层是健康的，瓶颈不在框架核心。**
CVRP 无晋升的根因是一个复合的"测量仪器问题"：

> 在 30s × 4 seeds 的 screening 协议下，CVRP 候选机制的真实效应量
> （±0.1%~3% total_distance）低于配对评估的噪声地板，而 anytime
> 元启发式的运行时饱和又持续污染 runtime 证据通道。campaign 是在
> 仪器分辨率以下做搜索——agent、闸门、协议各自都正确，组合起来
> 却测不出任何东西。

按层归因：
| 层 | 状态 |
|---|---|
| 决策边界 / DecisionFeatures 守卫 | ✅ 健康，无自由文本泄漏 |
| 证据完整性 / replay identity | ✅ 完整（32/32 valid pairs，replay complete） |
| Agentic session / 提案产出 | ✅ 能产出多样、合规的机制假设 |
| **协议统计功效（CVRP）** | ❌ **主要瓶颈：效应量 < 噪声地板** |
| **Runtime 治理对 anytime 算法的适配** | ❌ 次要瓶颈：饱和诊断 + 缓存策略消耗轮次并污染反馈 |
| 分支生命周期（低信噪场景） | ⚠️ 过早 park/archive，分支深度 ≤ 3 |
| 上下文质量 | ⚠️ hypothesis 提示约 19 万字符，治理/遥测合规占比过高 |

---

## 2. 框架核心审查：v3 不变量验证

### 2.1 验证通过的不变量

1. **Decision 只读 DecisionFeatures，无自由文本**：
   `core/decision.py:42-44` 在 `decide()` 入口强制调用
   `_validate_no_free_text(features)`（`core/features.py:234`），序列化路径
   （`decision_features_serialization.py`）同样校验。失败码限定在
   `KNOWN_FAILURE_CODES` 枚举集合内。✅
2. **闸门确定性**：`protocol/gates.py` 的 screening/validation/frozen gate
   是纯函数（EvalStats + ProtocolConfig → GateResult），分层 reason codes
   清晰。✅
3. **统计单位为 case**：`protocol/experiment/feedback.py::_aggregate_pairs_to_case_level`
   按 case 跨 seed 多数投票 + median delta，与 v3 §8.2 一致。✅
4. **分层 CI（lexicographic hierarchical bootstrap）**：`protocol/stats.py`
   按 metric 优先级逐层判定 positive/negative/uncertain/tie，warehouse 实验
   中 `VALIDATION_PASS_HIERARCHICAL` / `FROZEN_PASS_HIERARCHICAL` 正常工作。✅
5. **完整晋升链路可用**：warehouse 8R 在同一代码版本下走通
   screening(3) → validation(3) → frozen(2) → promotion(1)，
   promotion dossier 完整（champion_v2，含 code_hash / patch_hash /
   promotion_experiment_id）。✅ 这是"框架闭环没有坏"的最强证据。
6. **证据与 replay**：CVRP 8 个 formal candidate artifacts 全部
   `replay_identity_status=complete`；10 个 protocol metric 文件全部
   `attempted=valid=32（或48），failed_pairs=0`；counter reconciliation
   自洽（10 screened = 8 effective + 2 fresh-runtime replay）。✅

### 2.2 代码层发现（非致命，但值得修）

**F-1（P2）`min_practical_delta` 是死配置。**
`config/protocol_config.py:437` 把它硬编码为 `0.001` 的 property；
protocol.yaml 中的 `median_delta_min: practical_delta_screen` 字符串
从未被解析为 problem 定义的数值。对 CVRP（distance 量级 10³）来说
0.001 绝对值≈不存在，screening gate 实际只剩 win_rate 单阈值。
对 warehouse（delta 量级 10⁴）同样形同虚设。该旋钮应当 problem-owned
（如 gap 百分比），或者明确删除以免误导审计。

**F-2（P2）runtime 治理与 anytime 算法语义冲突。**
ALNS/VNS 是预算耗尽型算法：candidate/champion 永远跑满 time limit，
`runtime_ratio ≈ 1.0`、`saturation_ratio ≈ 0.99` 是构造性事实而非异常。
后果（见 §3.2）：每个 CVRP 候选都带 `SCREENING_RUNTIME_BUDGET_SATURATION`
警告，runtime evidence 永远 `low_cached_champion / insufficient`，
`RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` 把 2/8 个有效轮次变成 unclear 并
触发 fresh replay 重跑。runtime 治理需要 problem 包可声明
`runtime_model: budget_exhausting`，将"比快"语义换成"预算合规"语义。

**F-3（P3）screening expand 路径在低信噪场景不可达。**
`gates.py`：win_rate < 0.5 直接 fail。CVRP 平局占主导时 case 级
win_rate 系统性落在 0.3~0.4 区间，expand（0.5≤wr<threshold）几乎
永远不触发，预注册的统计扩样机制对 CVRP 实际失效。

**F-4（P3）lifecycle 策略对低信噪问题过激。**
`branch_lifecycle_policy.py` 默认 `zero_win_streak_limit=3`、
`marginal_no_effect_streak_limit=2`。当问题本身效应量低于仪器分辨率时
几乎一切候选都被归为 marginal/no_effect，分支被快速 park/archive，
实测 CVRP 4 个分支深度分别为 3/3/1/1 —— v3 设想的"分支内深度迭代"
没有发生。阈值已可配置（前次审计的 P2 项），但缺少"问题信噪比"维度的
默认值分档。

---

## 3. 两组实验对照审计

### 3.1 结果总览

| 维度 | CVRP 8R | Warehouse 8R |
|---|---|---|
| protocol rows | 10（全部 screening） | 8（3 screen + 3 valid + 2 frozen） |
| 晋升 | 0 | 1（champion_v2） |
| quality blocks | 0 | 0 |
| 候选 pair 级战绩（典型） | 14W/11L/7T、10W/11L/11T、大量 30/32 tie | 18W/1L/1T、15W/5L、16W/2L、12W/0L |
| case 级 win_rate（最好） | 0.375（阈值 0.6） | 0.83~1.0 |
| delta 量级 | ±3~57（distance ~10³，即 0.1%~3%） | ±7,000~92,000 |
| runtime 诊断 | 10 条 saturation 警告 | 0 条 |
| gate 失败原因 | 8×SCREENING_FAIL_WIN_RATE，2×unclear(RUNTIME_TIE_FRESH_CHAMPION_REQUIRED) | 1×VALIDATION_FAIL，1×FROZEN_FAIL_UNCERTAIN，其余 pass |
| hypothesis 提示规模 | ~19 万字符（中位） | ~7.4 万字符 |
| 总 token | 1.25M（4.3h） | ~0.4M（1.3h） |

### 3.2 CVRP 逐层失败分类

按审计指南的失败分层，CVRP 8 个有效候选的失败全部落在
**algorithm signal 层**——没有 proposal quality、contract、verification、
protocol evidence、runtime crash 失败：

1. **机制本体不弱**：8 个 session 产出 6 个互不相同的机制族
   （capacity_slack_regret_repair、route_merge_reinsertion、
   slack-gated donor-savings 变体、two-stage merge-polish、
   scheduler 级 compaction pass、route_ejection_reinsert），目标面覆盖
   destroy_repair / local_search / scheduler，符合 cross-branch lesson
   的对比维度要求，且能消费上一轮 screening 反馈做 refinement。
   **"VNS 抹掉一切"的强主张再次不成立**：存在大量非平局 pair
   （最强者 14W/11L），机制确实改变了搜索轨迹。
2. **但效应量在噪声地板之下**：以 e50502cf 为例，pair 级 14W/11L/7T，
   配对符号检验 p≈0.7 —— 统计上与零效应不可区分。case 级多数投票后
   3W/2L/3T = 0.375，远低于 0.6。关键机制：**对 solver_design 类编辑，
   "同 seed 配对"的方差缩减失效** —— 任何代码改动都会改变 RNG 消费
   序列，candidate 与 champion 在第一个分歧点之后就是两条独立轨迹，
   配对比较退化为非配对比较，承受全量 inter-run 方差。Warehouse 的
   operator-pool 编辑效应量大 3 个数量级，淹没同样的噪声，所以闸门照常
   工作。
3. **runtime 通道二次伤害**：champion result cache 命中（7/10 个候选
   全 cached）→ runtime_confidence=low_cached_champion →
   2 个近全平局候选 gate=unclear → 触发 fresh-runtime replay 重跑
   （fresh_runtime_replay_protocol_results=2）→ 消耗真实墙钟时间
   但产生 0 信息增量。同时 10 条 saturation 诊断进入 proposal feedback，
   agent 把注意力浪费在"runtime 证据低置信"这种对 anytime 算法
   永真的告警上。

### 3.3 上下文质量

最后一轮 CVRP hypothesis 提示分解（154K chars 总量）：

- 算法源码/事实/工具观测：~7.7 万 chars（Active Solver Map receipts 2.1 万、
  Full Algorithm File Reads 3.05 万、Tool Observations 2.2 万、facts 0.66 万）
- 治理/合规/lesson 协议：~4.5 万 chars（Cross-Branch Research Map 2.3 万
  ——其中大半是 `required_response`/`reason_codes` 等合规模板字段、
  Branch Lesson Usage 0.6 万、Do-Not-Claim 0.37 万、Analysis Steps 0.3 万、
  telemetry 契约 0.15 万）
- **蒸馏后的研究信号**：Runtime Feedback 1.2 万 chars 是未蒸馏的
  telemetry 统计 dump；Experiment History 对新分支恒为空；
  Objective Opportunity Profile 仅 914 chars。

对照 warehouse（同结构，总量 2.3+2.0+2.5 万），CVRP 的提示
被源码与合规材料放大约 2.5 倍，而真正帮助"选对杠杆"的问题域诊断
（per-case gap-to-BKS、case 难度画像、机制效应排行）几乎缺席。
这正是 v3 风险 4"context 退化为日志堆"的现行实例——不是 token 数
问题，而是信号密度问题。

---

## 4. 根因模型

```
强 ALNS+VNS champion（成熟基线）
    → LLM 可提案的局部机制效应量 0.1%~3%
        → 30s 预算 + RNG 轨迹分歧 → 配对失效，噪声同量级
            → case 多数投票 → win_rate 卡在 0.3~0.4
                → 全部 SCREENING_FAIL_WIN_RATE
                    → lifecycle 判定 no_effect/marginal → park/archive
                        → 分支深度 ≤3，cross-branch lesson 只能说"避开"
                            → 下一轮换机制族重来 → 循环
（旁路）anytime 满预算 → saturation + cached champion →
        2 轮 unclear + fresh replay 空耗 + 反馈污染
```

每个环节局部正确：闸门按规范拒绝了统计上不显著的候选；lifecycle
按规范处置了无信号分支；agent 按规范提出了有差异的机制。系统层面
却构成一个"永远测不出效应"的闭环。**这是研究对象-协议-仪器匹配问题，
不是 v3 架构或 v0.4 实现的缺陷。**

---

## 5. 改进建议（按优先级）

### P0：先标定仪器，再继续搜索（problem 包 + 协议层）

1. **A/A 噪声地板测量**：用当前 champion 对自身（不同 RNG 流）在
   16 个 screening case × 8~12 seeds 跑 A/A 实验，量化每个 case 的
   seed 方差与该协议下的最小可检测效应（MDE）。如果 MDE > 1% 而
   目标机制效应 ~0.3%，任何 gate 调参都无济于事——必须增加 seeds、
   延长预算或换统计量。这一步成本低（纯 champion 重放），且结果是
   problem-owned 诊断，不触碰 Decision 边界。
2. **换检验统计量**：对 budget-exhausting 求解器，case 级多数投票 +
   win_rate 阈值的功效太低。候选方案（保持确定性、保持在 protocol 层）：
   - case 级用 per-case mean gap delta（跨 seed 平均）替代多数投票，
     再做跨 case 的 Wilcoxon/bootstrap；
   - 或把 win_rate 阈值换成"配对 delta 的分层 bootstrap CI"单判据
     （validation 已经这么做了，screening 还在用 win_rate 硬阈值）。
3. **practical delta problem-owned 化**（修 F-1）：以 gap 百分比定义
   （如 screening 0.2%、validation 0.1%），由 problem 包声明并在
   protocol 加载时解析，删除硬编码 0.001。

### P1：runtime 治理 anytime 适配（框架核心，通用改动）

4. 在 `ProblemSpecV1` 增加 `runtime_model: comparative | budget_exhausting`
   声明（修 F-2）。`budget_exhausting` 模式下：
   - saturation 诊断降级为 info，不进 gate reason、不进 proposal feedback；
   - `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` 路径禁用（runtime tie 在该
     模式下无意义），不再触发 fresh replay 空耗；
   - V9 perf guard 语义改为"预算合规 + 无 timeout/crash"。

### P1：让分支变深（lifecycle + 调度，通用改动）

5. lifecycle 阈值按"问题信噪比档位"分默认值：低信噪问题
   `zero_win_streak_limit` 提到 4~5、`marginal_no_effect_streak_limit`
   提到 3，并允许同分支同机制的**证据累积**（sequential testing：
   2~3 轮 screening 证据合并判定，而非每轮一次性 32-pair 定生死）。
   8R 预算对 CVRP 太薄；标定 MDE 后建议直接跑 40R+。

### P2：上下文减脂与信号增密（proposal 层）

6. hypothesis 阶段砍掉 telemetry 契约细节（移到 code 阶段）、压缩
   cross-branch lesson 的合规模板字段（只保留 signature + 一句话
   guidance + maturity），Runtime Feedback 蒸馏为 per-case 一行摘要。
7. 注入 problem-owned 机会画像作为提案引导（符合 v3：诊断可见、
   不进 Decision）：champion 在每个 screening case 的 gap-to-BKS、
   跨候选的机制族-效应排行。让 agent 知道"哪里还有肉"，而不是只知道
   "上一个机制没用"。
8. 修复重复 session 浪费：8 个 completed session 对应 16 个
   hypothesis 调用（每个假设生成了两遍，partial_hypothesis_only →
   重新生成 completed），检查 `hypothesis_awaiting_approval` 之后的
   restart 是否可以复用已批准的 hypothesis 而非重新调用 LLM。

### P3：观测性小修

9. screening expand 区间（0.5≤wr<0.6）对平局主导问题不可达（F-3），
   若保留 win_rate 闸门，考虑把 expand 触发条件改为
   "非平局 pair 中 win 占比 ≥ 0.5 且 ties ≥ 50%"。
10. 把"分支深度分布""机制族 × 效应量矩阵"加入 campaign summary，
    便于直接审计 explore 形态。

---

## 6. 对"扩展为通用框架"的判断

v0.4 的泛化方向（ProblemAdapter + research_surfaces + agentic session）
在结构上是成功的：同一份核心代码同时跑通了两个 problem 包，决策边界
无泄漏，warehouse 闭环完整。真正暴露的通用化缺口不是"再加一个抽象"，
而是：**问题包目前只声明了"能改什么"（surfaces/objectives/telemetry），
还没有声明"这个问题的测量学特性"（噪声模型、效应量纲、runtime 模型、
信噪档位）。** 下一个版本的通用化重点建议放在这个"problem 测量学
声明层"上——它决定协议参数、lifecycle 档位与 runtime 治理语义的
自动适配，而这恰好是 CVRP 与 warehouse 之间所有行为差异的共同根源。
