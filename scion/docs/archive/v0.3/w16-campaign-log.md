# W16 Campaign Process Log

实验进行中的观察记录，供 W16 完成后统一分析。不对正在运行的实验做任何修改。

**记录人**：Xiao Jiyao + Claude  
**开始时间**：2026-04-21 18:38 UTC（Batch 1）  
**状态**：进行中

---

## 实验配置

| 项目 | 值 |
|------|-----|
| 模型 | claude-sonnet-4-6, gpt-5.4-mini |
| 数据集 | synthetic, production |
| Seeds | 11, 29, 47 |
| 总 campaigns | 12（2×2×3）|
| 并发 | 2 个/批，共 6 批 |
| SPLITS_WEIGHT | 1000（较原始 100000 大幅降低） |
| 最大轮次 | 100 |

---

## Batch 1 运行记录（2026-04-21）

### 基本情况（~6h 后快照，UTC 00:08）

| Campaign | 进展 | 分支数（abandon） | 验证失败 | Champion |
|----------|------|-------------------|----------|----------|
| sonnet-4-6 / synthetic / s11 | 正常运行 | ~56 生成，32 abandon | 0 | v3（20:45） |
| gpt-5.4-mini / synthetic / s11 | 正常运行 | ~70 生成，42 abandon | 13× V5 | v3（23:06） |

### GPT 生成代码长度 vs Sonnet

| 模型 | 平均长度 | 最小 | 最大 |
|------|---------|------|------|
| sonnet-4-6 | 6627 字节 | 1886 | 13786 |
| gpt-5.4-mini | 10094 字节 | 5787 | 15701 |

GPT 生成的 operator 平均比 Sonnet 长约 52%，且变异更小（集中在 8000–12000）。

---

## 观察到的问题

### O1：状态机转换 bug（已修复，不影响当前实验）

**现象**：gpt-5.4-mini campaign 在 21:01 出现一次 ERROR：
```
Branch 3b736978: apply_decision(CONTINUE_EXPLORE) from stale_weight_update failed:
  Invalid transition: state=stale_weight_update + decision=continue_explore
```

**根因**：后台权重优化线程在分支处于 `EXPLORE_EXPAND` 期间触发完成，将分支标记为 `STALE_WEIGHT_UPDATE`。随后 expand_screening 评估完毕，返回 `SCREENING_EXPAND_EXHAUSTED → CONTINUE_EXPLORE` 决策，但状态机转换表里没有 `STALE_WEIGHT_UPDATE + CONTINUE_EXPLORE` 这条路径。

**影响**：ERROR 被 catch 住，分支保持 `STALE_WEIGHT_UPDATE` 状态。下一轮走 reconcile 流程，reconcile re-screening 失败，分支被 abandon。Campaign 继续，只损失一个分支的工作量。

**修复**：`campaign.py` 中 `CONTINUE_EXPLORE` 处理路径增加 `STALE_WEIGHT_UPDATE` 豁免，不对该状态调用 `apply_decision`，让它自然流入 reconcile。修复在 Batch 1 启动后写入源码，不影响正在运行的进程，Batch 2–6 生效。

**后续思考**：这是一个并发竞态，还有多少类似的 "状态 × 决策" 组合未被覆盖？建议 W16 后对状态机做完整性检查（穷举所有合法的 state × decision 对，确认转换表无遗漏）。

---

### O2：GPT V5_solution_consistency 高频失败

**现象**：gpt-5.4-mini 在 s11 synthetic 单次 campaign 中已出现 **13 次 V5_solution_consistency 失败**，分布在 11 个不同分支（2 个分支各失败 2 次）。sonnet-4-6 同条件下 **0 次**。

**V5 检查的内容**：
- 对 canary case 运行 solver，读取输出 JSON
- 校验 `solution.assignment[order_id]` 与 `vehicle.order_ids` 的双向一致性
- 典型错误："order X in assignment but not in any vehicle" / "assignment says vehicle_A but found in vehicle_B"

**GPT 的系统性问题**：operator 移动订单时只更新了一侧数据结构（`assignment` dict 或 `vehicle.order_ids`），没有保持双向同步。Prompt 中（`schemas.py:147`）已有明确要求：
> "Maintain assignment dict consistency: update BOTH vehicle.order_ids and solution.assignment."

GPT 在生成 8000–12000 字节复杂代码时难以持续遵守。

**当前处理机制**：V5 是 `heavy` severity，无自动 fix 机会（只有 `light` 才调用 `fix_code`）。失败后 hypothesis 被 blacklist，分支继续提新假设。失败记录写入 branch history，下一轮 prompt 可见。

**待分析的问题**（post-W16）：

**Q1 — cross-branch 失败历史不共享**

当前的失败历史是 per-branch 的。一个分支遇到 V5 失败、被 abandon 后，这个失败经验对新分支不可见。新分支又从零开始犯同样的错误。GPT 的 V5 失败率在整个 campaign 中没有随时间下降，印证了这一点。

可能的改进方向：
- 在 hypothesis prompt 中注入 campaign 级别的失败摘要（"过去 N 次 V5 失败都是因为 assignment 双向更新问题"）
- 在 campaign journal 里维护一个 verification failure blacklist，新分支提假设前先过滤

**Q2 — V5 应该是 light 还是 heavy？**

V5 的失败通常是代码逻辑错误（忘记双向更新），而不是根本性架构问题。这类错误理论上可以通过 fix_code 修复：
- 如果 V5 降为 `light`，模型可以看到具体的 consistency issue JSON 并修复
- 但 fix_code 也消耗 token，且 fix 不一定成功

问题是：对 GPT 而言，在 fix prompt 里看到具体 issue 是否比在 history 里看到更有效？需要对比数据。

**Q3 — FIX_TOOL description 过时**

`schemas.py:168` 仍然写的是：
```
"- V5_state_mutation: operator modified input solution (use deep_copy())."
```

实际 V5 在 v0.3 已改名为 `V5_solution_consistency`，检查的是 assignment 一致性，而不是输入 mutation。`deep_copy()` 的提示对当前 V5 失败无效。即使 V5 不触发 fix，这条描述也会通过 context 影响模型对 V5 的认知。

**Q4 — 代码长度与失败率的关系**

GPT 生成的 operator 平均 10094 字节 vs Sonnet 6627 字节。更长的代码 = 更多的状态变更逻辑 = 更多机会出错。这个相关性需要用多个 campaign 的数据验证（单个 campaign 样本量不足）。

---

### O3：stagnation 信号 — subcategory_consolidation 机制主导

**现象**：两个模型都出现了"All 5 recent steps use 'subcategory_consolidation' mechanism with flat win_rate"的 plateau 信号。GPT 出现 2 次 plateau，Sonnet 出现 1 次，同时两者都触发了"15 consecutive T4 soft-abandons → forcing locus diversification"。

**观察**：stagnation 检测和强制 locus 切换机制在工作。但 plateau 后 GPT 的 V5 失败率是否也升高（新方向尝试更复杂的 operator 导致代码更长更容易出错）？这个关联值得分析。

---

### O4：SPLITS_WEIGHT 变更对 delta 分布的影响

SPLITS_WEIGHT 从实验设计阶段的 100000 改为 1000，目的是让 1 个 split 差距不再压倒性地主导 delta。

实际观测到的 delta 分布（sonnet s11，前 80 步截样）：
- delta 范围：-15300 ～ +6300
- `decisive=cost` 的情况出现（splits 相等时 cost 可成为决胜因素），符合预期

但也观测到几个 delta=±12000 的大跳跃，例如：
```
instance_v3_scr_l04.json: loss delta=-12000 (splits=37 vs splits=25)
```

说明 splits 差距 12 × SPLITS_WEIGHT=1000 = 12000。在 splits 差距较大时，SPLITS_WEIGHT=1000 仍然主导，cost 几乎不参与决策。这是合理的（大幅 splits 增加当然应该被惩罚），但需要在分析时区分"splits 差距大"和"splits 差距小但 cost 差距大"两种情形。

---

## 后续批次启动计划

| Batch | 命令 | 模型 | 数据 | Seeds |
|-------|------|------|------|-------|
| 2 | `./scion/launch_w16.sh 2` | sonnet + gpt | synthetic | 29 |
| 3 | `./scion/launch_w16.sh 3` | sonnet + gpt | synthetic | 47 |
| 4 | `./scion/launch_w16.sh 4` | sonnet + gpt | production | 11 |
| 5 | `./scion/launch_w16.sh 5` | sonnet + gpt | production | 29 |
| 6 | `./scion/launch_w16.sh 6` | sonnet + gpt | production | 47 |

---

## W16 完成后的分析 checklist

- [ ] V5 失败率：各 campaign 汇总，是否随 campaign 进展下降（学习效果）
- [ ] 代码长度 vs 失败率相关分析（O2-Q4）
- [ ] cross-branch 失败历史隔离的代价估计：损失了多少轮次在已知错误上
- [ ] FIX_TOOL V5 描述修正（O2-Q3）
- [ ] 状态机转换表完整性检查（O1 后续）
- [ ] SPLITS_WEIGHT=1000 的 delta 分布分析：cost 在多少比例的 pair 中起到决胜作用
- [ ] GPT vs Sonnet champion 改进量对比（主要 RQ）
- [ ] stagnation 触发次数 vs 实际 locus 切换有效性
