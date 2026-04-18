# Sprint F3 实验深度分析报告

*分析日期: 2026-04-13*
*实验目录: `~/research/scion-experiments/sprint-f3/`*
*代码版本: v0.2-dev @ dbc9997（含 Sprint I stagnation 修复）*

---

## 一、实验总览

| | F1 Opus | F2 Opus | F3 Sonnet |
|---|---|---|---|
| 总时长 | 266.5 min | 271.0 min | 411.4 min |
| 轮次利用率 | **100/100** ✅ | **99/100** ✅ | **99/100** ✅ |
| Champion 版本 | v3 | **v4** | v3 |
| 晋升次数 | 2 | **3** | 2 |
| Screening events | 100 | 99 | 99 |

**Sprint I 核心验证**：三组全部跑满，无提前终止。Sprint F2 中 F2 在 24 轮终止的问题彻底消失。

---

## 二、Champion 演化路径

### F1 Opus

| 版本 | 算子 | R | Stage | wr | frozen md | 核心思想 |
|------|------|---|-------|----|-----------|---------|
| v2 | subcategory_consolidate | R3 | frozen | 1.00 | **7,200,000** | 按品类合并车辆，升级车型 |
| v3 | drain_vehicle | R61 | frozen | 1.00 | 4,350 | 同品类内订单重打包，清空最小车辆 |

**v2 subcategory_consolidate**（R1 首轮 wr=1.00，直接晋升）：
> "挑选品类分裂最严重的 vehicle_subcategory，收集所有含该品类订单的车辆，将所有订单装入尽可能少的车辆（升级 T10→HQ40），移除空车辆。"

完美分拆 R1 首轮命中，说明这是"显而易见的第一步"——品类合并是最直接的 split 减少手段。

**v3 drain_vehicle**（R4-R57 搜索 54 轮才找到）：
> "识别同品类下多辆部分填充的车辆，用最大化填充的方式将订单重打包到 N-1 辆车中，清空第 N 辆车（消除其固定成本）。"

关键突破：**从 split 目标切换到 cost 目标**。不改变 splits（品类已高度集中），而是消除多余的空置车辆。frozen md 仅 4,350 但 wr=1.00，说明这是一个低强度但稳定的改进方向。

### F2 Opus

| 版本 | 算子 | R | Stage | wr | frozen md | 核心思想 |
|------|------|---|-------|----|-----------|---------|
| v2 | consolidate_subcategory | R5 | frozen | 1.00 | 150,000 | 品类感知合并（修复 v1 副作用） |
| v3 | subcat_focused_rebuild | R12 | frozen | 1.00 | **6,800,000** | 品类感知 destroy-rebuild |
| v4 | eliminate_weak_vehicle | R26 | frozen | 1.00 | 4,750 | 重分配低装载车辆订单，消车 |

**v2 consolidate_subcategory** 的特殊性：LLM 在 R1 就生成了类似 F1 的合并算子，但 R1 失败（wr=0.3）。R2 时 LLM **分析了失败原因**：
> "失败原因：驱逐非目标品类订单时进入新车辆，反而增加了这些品类的 splits。修复：驱逐逻辑须品类感知，优先将驱逐订单放入已含该品类的车辆。"

这是一个关键学习：R1→R2 的错误分析→修复链，frozen md 仅 150K（v2 较弱）但逻辑正确。

**v3 subcat_focused_rebuild**（R7-R12，跨两次 screening）：
第一次 screening wr=0.60，validation **失败**（wr=0.50），LLM 重新生成，第二次 screening wr=1.00，validation 1.00，frozen 1.00，md=6.8M。
> "SubcategoryAwareDestroyRebuild：锁定分裂品类，收集其所有车辆，销毁后用品类优先贪心重建：先打包目标品类到最少车辆，再把余下订单就近塞入现有车辆。"

这与 F1 v2 的 consolidate 是相似思路但执行更彻底（destroy-rebuild vs 渐进合并），frozen md 6.8M 说明改进空间巨大。

**v4 eliminate_weak_vehicle**（R20-R26，cost 阶段）：
散光算子 scatter_light_vehicle（wr=0.89）先通过 screening，但 validation 扩展后未达阈值（wr=0.60）。随后 eliminate_weak_vehicle：
> "识别低装载率(<50%)的车辆，把其所有订单重分配到已含同品类订单的其他车辆（保持 splits 不变），消除该车辆降低成本。"

frozen md=4,750，极小改进。但晋升后 champion 同时优化了 splits（v3 已接近最优）和 cost（v4 消除了最好消除的低效车辆）。此后再无提升空间。

### F3 Sonnet

| 版本 | 算子 | R | Stage | wr | frozen md | 核心思想 |
|------|------|---|-------|----|-----------|---------|
| v2 | subcategory_consolidate | R8 | frozen | 1.00 | 725,000 | 两辆同品类车合并 |
| v3 | subcategory_chain_consolidate | R20 | frozen | 1.00 | **2,750,000** | 三车旋转重分配 |

**v2 路径有趣**：Sonnet 第一个算子（subcategory_consolidate_merge, R1-R7）经历了 expand_screening，最终 wr=0.67 通过 screening，validation 1.00，但 **frozen 失败**（wr=0.50）。Sonnet 随即转换到稍简单的 subcategory_consolidate，一次通过 frozen（md=725K）。这说明 Sonnet 的首轮算子更复杂但鲁棒性差，frozen holdout 把它过滤掉了。

**v3 subcategory_chain_consolidate**（R11-R20）：Sonnet 发明了更复杂的"三车旋转"：
> "当品类 S 横跨车辆 A、B，但 A+B 容量超过单车上限时，引入第三辆车 C（同品类有空余），先从 A 移一些订单到 C 腾出空间，再把 B 的所有订单合并到 A，消除 B。"

这是比 F1/F2 的两车合并更具创意的方案，frozen md=2.75M。F3 v3 的 hypothesis 质量明显更有结构感——Sonnet 在链式推理上更强。

---

## 三、搜索阶段 Win Rate 分布分析

| 阶段 | F1 Opus | F2 Opus | F3 Sonnet |
|------|---------|---------|-----------|
| 前 v2（品类合并发现期） | n=1, avg=1.00 | n=3, avg=0.50 | n=4, avg=0.58 |
| v2→v3 搜索期 | n=55, wr<0.3: **74%**, avg=0.17 | n=3, avg=0.53 | n=9, wr<0.3: 22%, avg=0.39 |
| v3→v4 搜索期（F2） | — | n=10, wr<0.3: 80%, avg=0.31 | — |
| 最终 champion 后 | n=39, wr<0.3: **97%**, avg=0.09 | n=74, wr<0.3: **100%**, avg=0.01 | n=80, wr<0.3: 82%, avg=0.16 |

**核心规律**：champion 越强，后续候选 wr 分布越低。

- F1 v2 frozen md=7.2M（极强），导致 post-v2 74% wr<0.3，搜索极难
- F2 v4 是 cost-phase 算子（md=4.75K），看似弱，但对 benchmark 而言已无改进空间，post-v4 100% wr=0.00
- F3 v3 frozen md=2.75M（中等），post-v3 82% wr<0.3，搜索难但仍有 18% 的 wr≥0.3 信号

---

## 四、失败方向深度分析

### 4.1 F1 的"subcategory_swap 陷阱"（R62-R100）

v3 晋升后，LLM 连续 39 轮生成几乎相同的 `subcategory_swap` 算子，全部 wr=0.00-0.20：

**R62-R100 hypothesis 分析**：
```
R62: "找两辆各含分裂品类订单的车，做多订单双向交换..."（wr=0.20）
R63: "找两辆含不同品类订单的车，整体交换品类组..."（wr=0.10）
R64: "找 V1 V2 均含品类 S，V1 还含其他品类，把 V1 的品类 S 移到 V2..."（wr=0.00）
...（36 轮同类变体）
R86: "SubcategorySwap：找品类 X 分裂的两辆车做订单交换..."（wr=0.30，触发 continue_explore）
R87-R100: 继续同类变体，全部 wr≤0.20
```

**失败原因**：subcategory_swap 的核心思路是"在两辆车之间交换品类订单以提高纯度"。但在 drain_vehicle 已经实现了高效的车内订单重打包后，剩余分裂要么是：(1) 单辆车内部可以自解决的（drain 已处理），(2) 需要多辆车大范围重组的（swap 两两交换不够）。LLM 无法诊断出"这个方向已死"的根本原因，持续生成细微变体。

**Sprint I 的 soft_stagnation 为何未触发**：soft_stagnation_limit=15，但 R86 的 wr=0.30（continue_explore）在第 25 轮时重置了 soft_abandon_streak。每隔 ~20 轮就会有一次 wr=0.30 的事件，将 streak 清零，使得 15 的阈值永远无法命中。这是 I3 设计的盲点：streak 被边界值（wr 恰好 0.30）的偶发事件打断。

### 4.2 F2 的 "champion 过饱和" 现象（R27-R99，73 轮全 wr=0.00）

eliminate_weak_vehicle（v4，md=4,750）晋升后，所有后续候选 wr=0.00，连续 73 轮无一突破。

**原因**：v4 是在 splits 已接近最优的基础上消除了一个低装载车辆。benchmark 的 cost 改进空间极为有限——消完这辆"最容易消的车"后，剩余车辆装载率已经很高，无法再合并或消除。LLM 在 post-v4 生成的全是：
```
"找两辆品类相同的车做 swap"（wr=0.00）
"找低装载车把订单分散到其他车"（wr=0.00）
"跨品类重分配..."（wr=0.00）
```

这是**局部最优陷阱的经典形态**：champion 看似弱（md=4,750），实则已在 benchmark 上达到了组合优化的局部最优，四面都是山坡下降（wr=0.00 意味着任何扰动都变差）。

### 4.3 F3 的搜索多样性（post-v3 的 18% continue_explore 信号）

F3 post-v3 有 80 轮，其中 14 次（18%）出现 wr=0.30-0.50 的 continue_explore 事件，这些操作涉及：
- subcategory_absorb_via_offload：部分迁移+供体重分配（wr=0.50）
- subcategory_order_reassign：订单级重分配（wr=0.50）
- subcategory_eject_and_consolidate（wr=0.30）
- subcategory_partial_fill（wr=0.30）

Sonnet 产生了更多**边界区域**的算子（wr=0.30-0.50），说明 v3 后的 champion 强度中等，仍有改进空间，但 Sonnet 无法突破 screening 阈值（≥0.667）。这些算子的概念是正确的（offload、partial fill 都是实际可行的优化手段），但实现质量不足以通过严格的多实例验证。

**Sonnet vs Opus 实现质量**：Sonnet 的 hypothesis 逻辑更结构化，但代码实现往往更脆弱（边界条件处理不足），导致在 expand_screening 或 validation 阶段失败。Opus 的实现更健壮，但容易陷入同质化的 hypothesis loop。

---

## 五、三组实验的跨实验比较

### 5.1 算子设计轨迹收敛性

三组实验均独立发现了几乎相同的第一步：
- F1: subcategory_consolidate（两车合并升级）
- F2: consolidate_subcategory（品类感知合并，修复副作用版本）
- F3: subcategory_consolidate（两车合并）+ subcategory_consolidate_merge（先失败）

**结论**：对于当前 benchmark，"品类合并"是 LLM 的必然第一发现，且已被充分探索。这是一个**搜索空间缩窄**的信号——benchmark 可能需要增加更多 large/xlarge 实例来增加难度。

### 5.2 第二次晋升的分叉

| | F1 | F2 | F3 |
|---|---|---|---|
| v3 | drain_vehicle（cost，R61） | subcat_focused_rebuild（split，R12） | chain_consolidate（split，R20） |
| 发现耗时 | 58 轮 | 7 轮 | 12 轮 |
| 路径 | 完全不同方向 | 相同方向的增强版 | 相同方向的创新变体 |

F1 花了 58 轮才找到 v3，因为 v2 极强（md=7.2M），所有 split-reduction 方向都已被 v2 耗尽，最终从 cost 方向突围。

F2 仅 7 轮找到 v3，因为 v2 较弱（md=150K），split-reduction 空间大，v3（md=6.8M）轻松通过。

F3 12 轮找到 v3，因为 v2 中等（md=725K），三车旋转是对两车合并的自然创新升级。

### 5.3 "第三次晋升"的障碍

F2 找到了 v4（cost phase，eliminate_weak_vehicle），F1 和 F3 未能。

分析 F2 为何能找到 v4：
1. v3 后，LLM 快速意识到 split 空间已饱和（v3 md=6.8M，基本清空分裂）
2. LLM 明确将目标切换到 cost：scatter_light_vehicle（先试，validation 未过），eliminate_weak_vehicle（成功）
3. 核心 hypothesis："当 splits 已达局部最优，唯一改进是减少车辆数量/成本"

F1 和 F3 未能做到这个目标切换，因为 F1 v2 极强（split 空间更难被 LLM 判断为"已饱和"），LLM 持续尝试 split 方向。F3 v3 之后也是类似情况。

**根本原因**：LLM 的目标感知依赖 ContextManager 提供的信息。当前 context 中没有明确的"当前 champion 的 split 值已接近 benchmark 最优"信号，LLM 无法自适应切换搜索方向。

---

## 六、Sprint I 修复效果评估

| 指标 | Sprint F2（修复前） | Sprint F3（修复后） |
|------|-------------------|-------------------|
| F2 轮次利用率 | 30%（24/80） | **99%（99/100）** |
| stagnation 触发 | 是（T4 bug） | 否 |
| hard-stagnation escape 触发 | N/A | 未触发（未累积到 10 次） |
| soft-stagnation 触发（15次阈值） | N/A | F1: 接近但未触发；F2/F3: 未触发 |

**I1（T4 不计入 hard stagnation）**：直接有效，三组都没有提前终止。

**I3（soft_stagnation → locus 多样化）**：未充分触发。F1 的 subcategory_swap 陷阱中，wr=0.30 的偶发事件（约每 20 轮一次）始终在 streak 达到 15 前将其重置。这是 I3 的残留盲点。

**结论**：Sprint I 解决了硬性 bug（提前终止），但对"方向饱和后的有效多样化"问题仍有改进空间。

---

## 七、关键发现与 v0.3 建议

### 7.1 "目标饱和感知"缺失（最重要）

三组实验都存在：LLM 持续搜索已饱和的目标方向（split-reduction），无法感知"该切换到 cost 方向"。

**建议**：ContextManager 注入 champion 性能分位信息：
```
当前 champion 统计（vs benchmark）：
  split 改善幅度: 与初始相比 -82%（接近饱和）
  cost 改善幅度: 与初始相比 -12%（仍有空间）
  建议：探索 cost-reduction 方向
```

### 7.2 Hypothesis Loop 检测（I3 增强）

当前 soft_stagnation_limit=15 被偶发的 wr=0.30 重置。需要额外检测：
- 过去 N 轮的 hypothesis 文本语义相似度 > 阈值 → 强制切换方向
- 或：不仅检测 wr<0.3 的连续 abandon，还检测"同类 hypothesis family 的连续失败"

### 7.3 Champion 强度自适应 screening

F2 v4 晋升后（小 md），后续全是 wr=0.00。建议：
- 当晋升 md < MIN_PRACTICAL_DELTA 时（如 md=4,750），标记为"degenerate promotion"
- 后续搜索自动注入"champion 已高度优化，探索方向须更激进"的上下文

### 7.4 Sonnet 适合长程探索，Opus 适合快速晋升

- **Opus**：首轮 wr 更高（F1 R1 直接 1.00），晋升效率高，但容易陷入同质 hypothesis loop
- **Sonnet**：首轮需要 expand_screening，但 hypothesis 语义更多元（chain、partial fill、offload 等），适合 100r+ 的长程搜索

**建议**：混合策略——Opus 做前 20 轮（快速建立高质量 champion），Sonnet 接力后 80 轮（多元探索）。

---

## 八、下一步

1. **增强 ContextManager**：注入 champion 性能饱和度信号（split/cost 分位信息）→ Sprint J P0
2. **Hypothesis Family 语义分类**：检测连续同类 hypothesis，主动触发方向切换 → Sprint J P1  
3. **LLMClient OpenAI 支持**：GLM-5 / Minimax M2.7 / Qwen3.5 接入 → Sprint J P2
4. **Degenerate promotion 标记**：小 md 晋升后特殊处理 → Sprint J P2
5. **更大 benchmark 实例**：当前 v3 实例偏小，品类合并被第一轮就解决，建议补充 xxlarge 实例增加难度
