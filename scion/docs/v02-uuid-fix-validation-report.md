# UUID 修复验证实验 — 完整分析报告

*Date: 2026-04-11*
*Experiment: v02-uuid-fix-validation*
*Duration: 58.9 min, 4 rounds, 7 LLM calls (Claude Opus 4-6)*

---

## 1. 实验目的

验证 uuid.uuid4() → generate_vehicle_id(rng) 修复后：
1. V8_nondeterminism（原 V5_state_leak）失败率是否归零
2. 框架整体搜索效率是否提升
3. 是否有新暴露的问题

## 2. 对照数据

| 指标 | Sprint D (修复前) | 本次 (修复后) | 变化 |
|---|---|---|---|
| V8_nondeterminism 失败 | 6/8 (75%) | **0/4 (0%)** | -75pp ✅ |
| Verification 总通过率 | 2/8 (25%) | **3/4 (75%)** | +50pp ✅ |
| 首次 promote 轮数 | Round 7 | **Round 3** | -4 轮 ✅ |
| LLM 调用次数 | 16 | **7** | -56% ✅ |
| 实验预算利用率 | 2/8 有效实验 | **3/4 有效实验** | 25%→75% ✅ |
| Weight optimization | Permission denied | Permission denied | 未修复 ⚠️ |

## 3. 每轮详细分析

### Round 1: SubcategoryConsolidate — 验证通过，validation abandon

- **Hypothesis**: 按子类别合并车辆，13,956 字节代码（较大）
- **Verification**: 全部通过（V5_state_mutation ✅, V8_nondeterminism ✅）
- **Screening**: 初轮 wr=0.50 → expand → 扩展后 wr=0.65, md=100K → queue_validate
- **Validation**: wr=0.50, md=50K → **abandon (VALIDATION_FAIL_WIN_RATE)**

**根因分析**：算子在 medium 实例上表现不稳定（m02/m05/m06 有多次 loss），可能是逻辑过于复杂（13K 代码）导致在小实例上引入额外 cost 而 splits 改善不显著。在 large 实例上表现明显更好（l01-l04 多数 win）。这是**真实的算法性能问题**，不是框架 bug。

**对比 Sprint D**：同样的 hypothesis 方向，Sprint D 会在 verification 阶段就失败（V5_state_leak），根本走不到 screening。现在能走完整条链路，暴露的是算法层面的不足。

### Round 2: Contract 拦截重复假设

- **Hypothesis**: 与 Round 1 几乎相同的 SubcategoryConsolidate
- **Result**: C10_novelty 检查拦截 → abandon

**分析**：LLM 在第一个假设 abandon 后尝试重新提出类似假设，ContractGate 正确拦截。这验证了 novelty check 的有效性。但也暴露了 v0.2 设计中提到的 **hypothesis 同质化问题**——LLM 倾向于在同一方向上反复尝试。

### Round 3: SubcategoryMerge — 三级全通，promote ✅

- **Hypothesis**: 更简洁的子类别合并，5,306 字节代码（Round 1 的 38%）
- **Verification**: 全部通过
- **Screening**: wr=0.90, md=700K → queue_validate
- **Validation**: wr=1.00, md=2.3M → queue_frozen（18/18 全胜）
- **Frozen**: wr=1.00, md=4.55M → **promote to champion v2**（12/12 全胜）

**为什么 Round 3 成功而 Round 1 失败**：

1. **代码简洁性**：5.3K vs 13.9K。Round 3 的 SubcategoryMerge 逻辑更直接——找两辆同子类别车，合并成一辆。Round 1 的 SubcategoryConsolidate 试图同时做合并+重新分配+换车型，复杂度带来了不稳定性。
2. **深拷贝时机**：Round 3 在找到可行合并后才做 deep_copy，Round 1 在函数开头就 deep_copy 然后做大量操作。
3. **迭代策略**：Round 3 遍历所有 pair 找第一个可行解就返回；Round 1 试图做全局最优合并。

**这个成功是框架设计引导的还是偶然的？**
- **框架引导的**：C10 novelty check 拦截了 Round 2 的重复假设，迫使 LLM 在 Round 3 换了实现策略
- **框架引导的**：Round 1 的 validation abandon 把"在 medium 实例上不稳定"的信号正确反馈了
- **偶然的**：LLM 选择"更简洁"的实现是自然涌现，不是框架指导的。如果 LLM 在 Round 3 又写了一个复杂版本，可能也会在 validation 失败

### Round 4: SubcategoryRedistribute — screening 进行中

- **Hypothesis**: order_level 的重新分配（第一次出现非 vehicle_level 的 locus！）
- **Verification**: 全部通过
- **Screening**: wr=0.50, md=-700 → expand_screening（实验结束时仍在 expand）

**分析**：这是本次实验中唯一一个 order_level 假设。表现一般，但值得注意的是 LLM 终于开始探索不同的 locus 了——可能是因为 vehicle_level 方向已经有了 promoted champion，上下文中的成功案例引导它尝试新方向。

## 4. 已知 Bug

### Weight Optimization Permission Denied

champion snapshot 被复制为只读（0444），weight optimizer 无法写入 registry.yaml。

**根因**：WorkspaceMaterializer 复制 champion 时保留了 frozen file 的只读权限，weight_opt workspace 继承了这些权限。

**修复建议**：weight_opt workspace 创建时对 registry.yaml 做 chmod u+w。

**影响**：v0.2 的参数搜索功能（Workstream C）无法正常工作。Sprint E 必须修。

## 5. 结论

### uuid 修复效果确认

V8 失败率从 75% → 0%，验证预算利用率从 25% → 75%。修复完全有效，根因诊断正确。

### 框架验证链路正常

- Contract Gate 正确拦截重复假设（Round 2）
- Verification Gate 通过了 3 个合法算子，0 个误杀
- 三级协议正确区分了"中等改进"（Round 1, validation fail）和"强改进"（Round 3, promote）
- Decision Engine 的纯数值决策逻辑工作正常

### 仍然存在的问题

1. **Hypothesis 同质化**：4/4 个假设都是 subcategory 相关，3/4 是 vehicle_level
2. **Weight optimization 权限 bug**：promote 后的参数搜索无法运行
3. **无实验后分析步骤**：campaign 结束后没有自动的根因追溯
4. **Cache hit rate 低**：10.5%（因为 champion 变了，cache 失效）

---

*本报告遵循 postmortem #001 的教训：对每类成功和失败都追溯根因，不只看 aggregate metrics。*
