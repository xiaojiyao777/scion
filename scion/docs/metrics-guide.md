# Scion 核心指标详解

*理解 Scion 决策引擎的两个核心输入：Win Rate 和 Median Delta。*

---

## Win Rate (wr)

### 定义

Candidate 算子 vs Champion 算子的**胜率**。

### 计算方式

每个实验 pair 的流程：

1. 用**同一个实例 + 同一个 seed**，分别跑 champion solver 和 candidate solver
2. 按**字典序**比较结果：
   - 先比 **splits**（子类拆分数，越少越好）
   - splits 相同再比 **cost**（物流成本，越低越好）
3. candidate 更优 → **win**，更差 → **loss**，完全一样 → **tie**

```
wr = wins / total_pairs
```

### 阈值配置

| 阶段 | 阈值 | 含义 |
|------|------|------|
| Screening | wr ≥ 0.60 | 宽松，快速淘汰明显差的 |
| Validation | wr ≥ 0.66 | 严格，2/3 以上才放行 |
| Frozen Holdout | wr ≥ 0.66 | 与 Validation 一致 |

### 怎么看

| 值 | 含义 |
|----|------|
| wr = 1.00 | 每次都赢，碾压级改善 |
| wr = 0.95 | 几乎全赢，偶尔因随机性输一次 |
| wr = 0.70 | 大部分赢，但有稳定的败场 |
| wr = 0.667 | 恰好 2/3，边界情况（可能触发 expand_validation） |
| wr = 0.60 | 刚过 screening 线，改善不 robust |
| wr = 0.50 | 跟 champion 没区别，随机水平 |
| wr < 0.50 | 比 champion 更差 |

---

## Median Delta (md)

### 定义

所有 pair 中，candidate 相对 champion 的**改善幅度的中位数**。

### 计算方式

每个 pair 产出一个 delta 值，映射规则：

**如果 decisive 维度是 splits（字典序第一优先级）**：

```
delta = (champ_splits - cand_splits) × 100,000
```

例：champion 60 splits，candidate 55 splits → delta = 5 × 100,000 = **500,000**

**如果 splits 相同，decisive 维度是 cost**：

```
delta = champ_cost - cand_cost
```

例：champion 成本 213,100，candidate 成本 213,000 → delta = **100**

然后取所有 pairs 的 delta，排序取中位数。

> **为什么用中位数？** 相比均值，中位数对极端值不敏感。一个 pair 上的巨大改善不会掩盖其他 pair 上的退化。

### 阈值配置

```yaml
min_practical_delta: 0.001  # 当前设置很宽松，基本只看 wr
```

### 怎么看

| 值 | 含义 |
|----|------|
| md = 5,150,000 | 中位改善 ~51.5 个 splits，巨大的结构性改善 |
| md = 2,200,000 | 中位改善 ~22 个 splits，显著 |
| md = 750,000 | 中位改善 ~7.5 个 splits，明显 |
| md = 100,000 | 中位改善 1 个 split，微弱 |
| md = 52,900 | 中位改善不到 1 个 split，靠 cost 微调赢的 |
| md < 0 | 中位数上 candidate 反而更差（即使 wr > 0.5 也可能） |

---

## 两个指标的关系

**wr 告诉你"赢不赢"，md 告诉你"赢多少"。**

好的算子两个都高。但更重要的是要看**两者的组合模式**：

| wr | md | 含义 |
|----|----|------|
| 高 + 大 | wr=0.95, md=750K | 稳定赢且赢得多，强改善 ✅ |
| 高 + 小 | wr=0.70, md=52K | 经常赢但赢的幅度小，可能只是 cost 微调 ⚠️ |
| 低 + 大 | wr=0.50, md=500K | 输赢参半但赢的时候赢很多——说明改善在某些实例上有效，另一些上有害 ❌ |
| 低 + 小 | wr=0.44, md=-9K | 输多赢少且中位是亏的，没有改善 ❌ |

---

## 实际案例：v0.1 Campaign

### Branch 1（★ Promoted）—— SubcatMergeSafe

```
Screening:  wr=0.95  md=750,000    → 小/中实例上几乎全赢，平均改善 7.5 个 splits
Validation: wr=1.00  md=2,200,000  → 大/超大实例上全赢，平均改善 22 个 splits  
Frozen:     wr=1.00  md=5,150,000  → 最大实例上全赢，平均改善 51.5 个 splits
```

两个规律：
1. **wr 从 0.95 → 1.00**：实例越大，算子优势越稳定（小实例偶有随机波动）
2. **md 从 750K → 5.15M**：实例越大，改善幅度越大（结构性改进在大规模上放大）

**这就是"结构性改善"的标志**——不是碰巧赢，而是越难的问题赢越多。

### Branch 3（✗ Abandoned after expand_validation）—— PurifyMixedVehicle

```
Screening:     wr=0.60  md=52,900   → 勉强过线，改善幅度很小
Validation:    wr=0.667 md=100,000  → 边界，触发 expand_validation
Expanded(36p): wr=0.611 md=100,000  → 扩大样本后跌破 0.66，ABANDON
```

特点：
- wr 始终在 0.60 附近晃，md 也很小
- 说明这个算子改善不 robust，在某些 seed 上碰巧赢了
- **expand_validation 揭穿了边界侥幸**——初始 18 pairs 的 wr=0.667 是统计噪声

### Branch 4（✗ Abandoned）—— ExtractMinoritySubcat

```
Screening:  wr=0.70  md=100,000  → 看起来不错
Validation: wr=0.44  md=-9,000   → 暴跌，中位数为负
```

**Screening 过关 ≠ Validation 过关**：小实例上的表现骗了 screening，大实例上彻底暴露。这就是三级验证存在的意义。

---

*参见 `glossary.md` 获取更多术语定义，`design/scion-architecture-v3.md` 获取完整架构设计。*
