# W16 实验结果总结

**实验周期**：2026-04-21 18:38 → 2026-04-23 03:33 UTC（约 33h）  
**协议**：2 模型 × 2 数据集 × 3 seeds = 12 campaigns，max_rounds=100，SPLITS_WEIGHT=1000

---

## 一、总览

| Campaign | 时长 | Promotions | 最终 Champion | V5 失败 | 最终 frozen md |
|----------|------|-----------|--------------|---------|--------------|
| sonnet / synthetic / s11 | 6.8h | 2 | v3 | 0 | +25000 |
| sonnet / synthetic / s29 | 7.0h | **3** | **v4** | 0 | **+40000** |
| sonnet / synthetic / s47 | 7.4h | 2 | v3 | 0 | +24500 |
| sonnet / production / s11 | 2.5h | 1 | v2 | 0 | +46800 |
| sonnet / production / s29 | 2.7h | 1 | v2 | 0 | +46450 |
| sonnet / production / s47 | 2.3h | 1 | v2 | 0 | +32300 |
| gpt / synthetic / s11 | 6.6h | 2 | v3 | 15 | +21500 |
| gpt / synthetic / s29 | 8.4h | 2 | v3 | 16 | +20500 |
| gpt / synthetic / s47 | 9.3h | 1 | v2 | 18 | +32500 |
| gpt / production / s11 | 1.9h | **0** | v1 | 27 | — |
| gpt / production / s29 | — | 1 | v2 | 25 | +9150 |
| gpt / production / s47 | 2.2h | **0** | v1 | 18 | — |

> `frozen md`：触发 promote 的最后一次 frozen 阶段 median_delta，反映 champion 对 frozen 测试集的改进幅度（SPLITS_WEIGHT=1000 单位）。

---

## 二、关键发现

### F1：Sonnet 全面优于 GPT

- **Sonnet**：所有 6 个 campaign 均取得 promotion，V5 失败 0 次
- **GPT**：2 个 production campaign（s11、s47）完全没有 promotion，3 个 production campaign 共 70 次 V5 失败

### F2：GPT 在 production 数据上基本失败

GPT production 三组：
- s11：27 次 V5 失败，0 次 promotion，仅跑 1.9h（100 轮几乎全消耗在 V5 失败上）
- s29：25 次 V5 失败，1 次 promotion（md=9150，相对较小）
- s47：18 次 V5 失败，0 次 promotion

根本原因：production 实例更复杂，GPT 生成的 operator 代码在维护 assignment 双向一致性上更容易出错，V5 失败率从 synthetic 的 ~17% 上升到 production 的 ~25%。大量 rounds 在验证阶段就被终止，没有进入 screening 评估。

### F3：Production 数据比 Synthetic 难改进

- Sonnet synthetic：平均 2.3 次 promotion
- Sonnet production：均为 1 次 promotion

但 production 的 frozen md 不低（+32300 ~ +46800），甚至高于 synthetic 部分结果。说明 production 上能找到的第一个改进往往是显著的，但后续改进空间有限，campaign 在 100 轮内无法再找到第二次。

### F4：Synthetic 结果跨 Seed 稳定，Production 有差异

Sonnet synthetic 三组都达到 v3 或更高（v2→v3→v4），表现一致。  
GPT synthetic 也相对稳定（v2→v3，除 s47 只到 v2）。  
GPT production 跨 seed 差异显著（0、1、0 次 promotion），说明 production 数据上 GPT 的改进高度依赖随机搜索路径。

### F5：Sonnet s29 是最佳单次 Campaign

3 次 promotion，最终 frozen md = +40000，7.0h 内达到 v4。这是所有 12 组中 champion 版本最高、改进幅度最大的一组。

---

## 三、V5 失败分布

| 模型 | Synthetic (s11/s29/s47) | Production (s11/s29/s47) | 合计 |
|------|------------------------|--------------------------|------|
| Sonnet | 0 / 0 / 0 | 0 / 0 / 0 | **0** |
| GPT | 15 / 16 / 18 | 27 / 25 / 18 | **119** |

GPT 全程 119 次 V5 失败，其中 production 占 70 次（59%）。  
Sonnet 全程 0 次。

---

## 四、效率对比

| 指标 | Sonnet synthetic | Sonnet production | GPT synthetic | GPT production |
|------|-----------------|-------------------|--------------|----------------|
| 平均时长 | 7.1h | 2.5h | 8.1h | ~2.0h |
| 平均 promotions | 2.3 | 1.0 | 1.7 | 0.3 |
| V5 失败率 | 0% | 0% | ~17% | ~23% |
| 有效轮次占比* | ~100% | ~100% | ~83% | ~75% |

*有效轮次 = 进入 screening 评估的轮次（排除 V5 等早期失败）

---

## 五、MILP Gap 分析

### 5.1 方法

对每个 campaign 的最终 champion，提取其在 frozen gate 实例上的求解结果（splits, cost），与 Sprint F4 的 MILP exact 解对比。

MILP 参考值：

| 实例 | splits | cost | status |
|------|--------|------|--------|
| v3_fro_l02 | 77 | 262100 | optimal |
| v3_fro_x01 | 160 | 473800 | optimal |
| v3_fro_x02 | 199 | 510700 | optimal |
| prod_fro_x01 | 2 | 178100 | optimal |
| prod_fro_x03 | 1 | 196900 | optimal |
| prod_fro_x04 | 2 | 214100 | optimal |
| prod_fro_xx01 | 4 | 300900 | optimal |

> v3_fro_l01 为 feasible（非 exact），不参与 gap 计算。

### 5.2 Case 级别对比（sonnet/synthetic/s29，v1 → final → MILP 全链）

以最佳 campaign (sonnet/s29, final=v4) 为例。✓ = MILP exact，~ = MILP feasible。

**完整 20 实例逐例对比：**

| 实例 | orders | v1 | final | MILP | Δ(v1→f) | Δ(f→M) |
|------|--------|-----|-------|------|---------|--------|
| v3_scr_m01 | 54 | 11 | 8 | 5✓ | +3 | +3 |
| v3_scr_m03 | 60 | 12 | 9 | 8✓ | +3 | +1 |
| v3_scr_m05 | 61 | 17 | 15 | 14✓ | +2 | +1 |
| v3_scr_m02 | 62 | 14 | 12 | 12✓ | +2 | 0 |
| v3_scr_m04 | 62 | 25 | 20 | 17✓ | +5 | +3 |
| v3_scr_m06 | 66 | 17 | 14 | 10✓ | +3 | +4 |
| v3_scr_l01 | 108 | 23 | 14 | 10✓ | +9 | +4 |
| v3_scr_l02 | 116 | 32 | 22 | 33✓ | +10 | -11 |
| v3_val_l01 | 122 | 33 | 13 | 31✓ | +20 | -18 |
| v3_scr_l03 | 130 | 56 | 41 | 50✓ | +15 | -9 |
| v3_scr_l04 | 134 | 48 | 38 | 46✓ | +10 | -8 |
| v3_val_l02 | 143 | 39 | 21 | 39✓ | +18 | -18 |
| v3_val_l03 | 168 | 69 | 49 | 68✓ | +20 | -19 |
| v3_val_l04 | 175 | 74 | 20 | 74✓ | +54 | -54 |
| v3_fro_l01 | 188 | 64 | 26 | 67~ | +38 | -41 |
| v3_fro_l02 | 215 | 80 | 58 | 77✓ | +22 | -19 |
| v3_val_x01 | 258 | 95 | 44 | 91✓ | +51 | -47 |
| v3_val_x02 | 293 | 130 | 68 | 134✓ | +62 | -66 |
| v3_fro_x01 | 349 | 159 | 70 | 160✓ | +89 | -90 |
| v3_fro_x02 | 408 | 198 | 88 | 199✓ | +110 | -111 |

> v1 = 初始 champion，final = 最终 champion (v4)，MILP = Sprint F4 exact 解。
> Δ(v1→f) = Scion 改进量（正 = 更优），Δ(f→M) = 与 MILP 的差距（负 = champion 优于 MILP）。

**按规模汇总（exact MILP only）：**

| 规模 | #实例 | avg Δ(v1→final) | avg Δ(final→MILP) | avg Δ(v1→MILP) | Scion 填补率 |
|------|-------|----------------|-------------------|----------------|-------------|
| Medium (54-66) | 6 | **+3.0** | +2.0 | +5.0 | **60%** |
| Large (108-293) | 11 | **+26.5** | -24.1 | +2.4 | **>100%** |
| XLarge (349-408) | 2 | **+99.5** | -100.5 | -1.0 | **>100%** |

关键解读：

- **Medium**：v1 比 MILP 差 5 splits，Scion 改进 3 splits（填补 60%），剩余 2 splits 是 VNS 随机误差。MILP exact 在此规模是有效下界，**Scion 优化有效但未达最优**。
- **Large**：v1 ≈ MILP（平均只差 2.4 splits，因为 MILP warm start 就是同一个 VNS），Scion 改进 26.5 splits 后远超 MILP。**Scion 的 evolved operators 找到了 MILP 模型无法表达的解**。
- **XLarge**：v1 与 MILP 几乎相同（v3_fro_x01: v1=159, MILP=160），Scion 改进约 100 splits。改进完全来自进化出的新 operator。

**Medium（54-66 orders）— MILP 有效**

| 实例 | orders | MILP_sp | Champ_sp | gap | 胜者 |
|------|--------|---------|----------|-----|------|
| v3_scr_m01 | 54 | 5✓ | 8 | +3 | MILP |
| v3_scr_m03 | 60 | 8✓ | 9 | +1 | MILP |
| v3_scr_m05 | 61 | 14✓ | 15 | +1 | MILP |
| v3_scr_m02 | 62 | 12✓ | 12 | 0 | TIE |
| v3_scr_m04 | 62 | 17✓ | 20 | +3 | MILP |
| v3_scr_m06 | 66 | 10✓ | 14 | +4 | MILP |

MILP 赢 5/6，平均 gap = +2.0。VNS 差 1-4 splits，属元启发式正常误差。MILP exact 在此规模有效。

**Large（108-293 orders，12 instances）— Champion 大幅领先**

| 实例 | orders | MILP_sp | Champ_sp | gap | 胜者 |
|------|--------|---------|----------|-----|------|
| v3_scr_l01 | 108 | 10✓ | 14 | +4 | MILP |
| v3_scr_l02 | 116 | 33✓ | 22 | -11 | CHAMP |
| v3_val_l01 | 122 | 31✓ | 13 | -18 | CHAMP |
| v3_scr_l03 | 130 | 50✓ | 41 | -9 | CHAMP |
| v3_scr_l04 | 134 | 46✓ | 38 | -8 | CHAMP |
| v3_val_l02 | 143 | 39✓ | 21 | -18 | CHAMP |
| v3_val_l03 | 168 | 68✓ | 49 | -19 | CHAMP |
| v3_val_l04 | 175 | 74✓ | 20 | -54 | CHAMP |
| v3_fro_l01 | 188 | 67~ | 26 | -41 | CHAMP |
| v3_fro_l02 | 215 | 77✓ | 58 | -19 | CHAMP |
| v3_val_x01 | 258 | 91✓ | 44 | -47 | CHAMP |
| v3_val_x02 | 293 | 134✓ | 68 | -66 | CHAMP |

Champion 赢 11/12，平均 gap = -25.5。在 ≥116 orders 的 exact 实例上全部超越 MILP "最优"。

**XLarge（349-408 orders，2 instances）**

| 实例 | orders | MILP_sp | Champ_sp | gap | 胜者 |
|------|--------|---------|----------|-----|------|
| v3_fro_x01 | 349 | 160✓ | 70 | -90 | CHAMP |
| v3_fro_x02 | 408 | 199✓ | 88 | -111 | CHAMP |

平均 gap = -100.5。Champion 比 MILP 少 56% 的 splits。

**Crossover 总结**：

| 规模 | orders | #实例 | MILP 赢 | Champion 赢 | 平均 gap_sp |
|------|--------|-------|---------|------------|------------|
| Medium | 54-66 | 6 | **5** | 0 | +2.0 |
| Large | 108-293 | 12 | 1 | **11** | -25.5 |
| XLarge | 349-408 | 2 | 0 | **2** | -100.5 |

Crossover 在 ~110 orders 附近。Medium 以下 MILP exact 有效；Large 以上 MILP 模型的决策变量空间无法表达 evolved operator 的解（如 vehicle merge/split/destroy 重构车辆编组），"optimal" 是受限最优。

### 5.3 Production Case 级别对比（sonnet/s29）

Production 上 splits gap = 0（双方均达到最低 splits），差异在 cost。

| 规模 | #实例 | Champion cost 更优 | MILP cost 更优 | TIE | 平均 cost gap |
|------|-------|-------------------|---------------|-----|-------------|
| Micro/Small | 10 | 1 | 4 | 5 | +0.6% |
| Medium | 3 | 2 | 1 | 0 | -4.7% |
| Medium-Large | 2 | 2 | 0 | 0 | -13.7% |
| Large/XLarge | 10 | 10 | 0 | 0 | **-19.6%** |

与 synthetic 相同的规模 crossover 模式：小实例 MILP 有效（cost gap 0-2%），大实例 champion 大幅领先（cost -14% 到 -27%）。

### 5.4 Frozen Gate 跨 Campaign 汇总

Synthetic frozen（exact 实例 l02、x01、x02）— splits gap：

| Campaign | l02 | x01 | x02 | 平均 gap |
|---------|-----|-----|-----|---------|
| sonnet/s11 | -23 (-14%) | -34 (-16%) | -30 (-11%) | **-29** |
| sonnet/s29 | -19 (-6%) | -90 (-27%) | -111 (-23%) | **-73** |
| sonnet/s47 | -26 (-22%) | -45 (-10%) | -34 (-10%) | **-35** |
| gpt/s11 | -24 (-14%) | -62 (-23%) | -65 (-18%) | **-50** |
| gpt/s29 | -12 (-6%) | -26 (-7%) | -27 (-8%) | **-22** |
| gpt/s47 | -23 (-19%) | -39 (-24%) | -37 (-22%) | **-33** |

Production frozen（splits = 0 gap）— cost gap：

| Campaign | fro_x01 | fro_x03 | fro_x04 | fro_xx01 | 平均 |
|---------|---------|---------|---------|----------|------|
| sonnet/s11 | -25.2% | -20.9% | -21.5% | -20.7% | **-22.1%** |
| sonnet/s29 | -27.0% | -20.9% | -21.9% | -21.5% | **-22.8%** |
| sonnet/s47 | -16.7% | -14.8% | -15.6% | -13.8% | **-15.2%** |
| gpt/s29 | -3.4% | -4.4% | -3.8% | -5.1% | **-4.2%** |

> gpt/production/s11 和 s47 无 promote，无法对比。

### 5.5 MILP Gap 分析结论

1. **Medium 规模（≤~100 orders）**：MILP exact 有效，champion 比 MILP 差 1-4 splits（VNS 随机误差），cost 差距 ≤2%。MILP 可作为 ground truth。

2. **Large+ 规模（≥~110 orders）**：Champion 全面超越 MILP "optimal"。根因是 MILP 模型使用固定车辆集合 + 订单分配变量，不能表达 evolved operator 的车辆重构策略（merge/split/destroy）。MILP 的 "optimal" 是其受限决策空间内的最优，非实际问题下界。

3. **RQ4 需要重新定义**：对于 medium 规模实例，gap = champion − MILP 是有意义的（正值 1-4，表示 VNS 离最优的距离）；对于 large+ 实例，gap 为负值不能解释为"champion 超越最优"，而应理解为 MILP 模型不完备。

4. **后续建议**：若要为 large 实例建立有效下界，需要扩展 MILP 模型——引入车辆创建/合并/销毁变量，或使用 column generation 等方法建模可变车辆编组。

---

## 六、Sonnet 表现评估

### 6.1 对照预注册成功标准

| RQ | 标准 | 结果 |
|----|------|------|
| RQ1 | ≥1 promotion，final champion > initial | ✅ 全部 6 个 Sonnet campaign 均达成 |
| RQ2 | 模型间存在可观测差异 | ✅ 极显著（0 vs 119 次 V5 失败；promote rate 2.3 vs 0.3） |
| RQ3 | Synthetic vs production 差异记录 | ✅ 详见第二、三章 |
| RQ4 | Champion 距离 MILP gap | ⚠️ MILP bounds 无效，见第五章 |
| RQ5 | Early-stop 触发条件 | ❌ 全部 12 个 campaign 均未触发 |

### 6.2 Sonnet 正面表现

- 0 次 V5 失败（全 6 campaign，~500 轮评估）：代码质量稳定
- Synthetic 平均 2.3 次 promote（s29 达 v4）：搜索能力有效
- Production frozen md +32300 ~ +46800：单次改进显著
- 进化出的 `SubcategoryMergePairBySplitCount` 突破了 surrogate 上界

### 6.3 Sonnet 受限表现

- Production 均只有 1 次 promote，之后 75-92 轮空转
- 原因不是代码质量（V5=0），而是搜索策略在 production 上快速耗尽
- 与早停未触发的问题叠加，浪费了大量运算

---

## 七、系统级问题清单（供 W17 前处理）

### P1：早停完全未触发，75-92 轮空转

`EarlyStopController` 的两条规则均无法触发：
- `all_hard`：要求所有 objective 均为 `saturation_type=="hard"` → cost 永远不是 hard
- `saturated_stagnant`：要求所有 objective 的 improvement ratio > 70% + plateau 信号 → cost 很难达到 70%

Plateau 信号实际频繁触发（production 12+ 次），但缺少 cost saturation 条件。

**影响**：浪费 50-90% 运算轮次。

### P2：W15 ProblemAdapter 未完成

框架中遗留 9+ 处 warehouse 硬编码：`saturation.py`、`context_manager.py`（"splits > cost ALWAYS"）、`campaign.py` stagnation handler（`order_level ↔ vehicle_level` 强制切换）、`models.py`、`search_memory.py`、`classifier.py`、`evaluation.py`、`verification/feasibility.py` 等。

**影响**：框架无法复用到其他优化问题。

### P3：`abs_min_constraint` 在 production 上误触发

`saturation.py` 的 `_AT_MINIMUM_THRESHOLD = 1.0` 检查 `baseline_val`（v1 初始 champion 的 screening splits 均值）。Production baseline splits 均值 = 0.3（很多小实例 splits=0），`0.3 < 1.0` → `at_absolute_minimum=True`。

这让 context_manager 注入 "COST-only" 约束，但 v1 时 splits 并非真正已达绝对最小。

**根因**：threshold 检查 baseline（固定值）而非 current champion metrics。

### P4：`FIX_TOOL` 描述过时

`schemas.py:168` 仍写 `"V5_state_mutation: use deep_copy()"`，实际 V5 已改为 `V5_solution_consistency`（assignment 双向一致性检查）。

### P5：状态机转换表不完整

Batch 1 出现 `STALE_WEIGHT_UPDATE + CONTINUE_EXPLORE` 无效转换。已修复（Batch 2+ 生效），但其他 state × decision 组合可能仍有遗漏。需要穷举检查。

### P6：GPT V5 失败率极高且无修复机会

GPT 全程 119 次 V5 失败，Sonnet 0 次。V5 是 `heavy` severity → 无 `fix_code` 重试，直接 blacklist hypothesis。

改为 `light` 后模型可以看到具体 consistency issue 并修复。需先分析 119 次失败，判断是否为可修复的机械错误。

### P7：cross-branch 失败历史不共享

V5 失败记录是 per-branch 的。新分支无法从旧分支的 V5 失败中学习，GPT 的 V5 失败率在整个 campaign 中没有下降趋势。

**改进方向**：campaign-level 失败摘要注入 hypothesis prompt。

### P8：MILP bounds 不是有效下界

详见第五章。Sprint F4 MILP bounds 是 surrogate model 的精确解，不是实际问题的下界。预注册 RQ4 需要重新定义。

### P9：Production campaign 轮次利用率极低

Sonnet production 在前 8-25 轮完成唯一一次 promote，剩余 75-92 轮空转。GPT production 更差（2/3 seeds 完全无 promote）。

是 production 本身改进空间有限，还是搜索策略不适配 production？需要在修复早停问题后重新评估。
