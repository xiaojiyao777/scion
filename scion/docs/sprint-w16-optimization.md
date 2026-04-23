# Scion v0.3 — W16 分析与优化总结

**日期**：2026-04-23  
**分支**：v0.3-dev  
**状态**：优化完成，验证实验运行中

---

## 一、W16 实验回顾

### 1.1 实验配置

| 项目 | 值 |
|------|-----|
| 模型 | claude-sonnet-4-6, gpt-5.4-mini |
| 数据集 | synthetic, production |
| Seeds | 11, 29, 47 |
| 总 campaigns | 12（2×2×3）|
| 最大轮次 | 100 |
| SPLITS_WEIGHT | 1000 |

### 1.2 核心结果

| 指标 | Sonnet synthetic | Sonnet production | GPT synthetic | GPT production |
|------|-----------------|-------------------|--------------|----------------|
| 平均 promotions | 2.3 | 1.0 | 1.7 | 0.3 |
| V5 失败率 | 0% | 0% | ~17% | ~23% |
| 有效轮次占比 | ~100% | ~100% | ~83% | ~75% |
| 早停触发 | 否 | 否 | 否 | 否 |

### 1.3 MILP Gap（v1 → final champion → MILP）

按实例规模，Sonnet/synthetic/s29（最佳 campaign）：

| 规模 | #实例 | v1→final 改进 | final vs MILP | Scion 填补率 |
|------|-------|--------------|---------------|-------------|
| Medium (54-66) | 6 | +3.0 splits | +2.0 (MILP更优) | 60% |
| Large (108-293) | 11 | +26.5 splits | -24.1 (Champion更优) | >100% |
| XLarge (349-408) | 2 | +99.5 splits | -100.5 (Champion更优) | >100% |

Medium 以下 MILP exact 有效；Large 以上 Champion 全面超越 MILP，根因是 MILP 模型无法表达 evolved operator 的车辆重构策略。

---

## 二、W16 发现的问题清单

### 系统级问题

| # | 问题 | 影响 |
|---|------|------|
| P1 | 早停完全未触发，50-90% 轮次空转 | 运算浪费 |
| P2 | W15 ProblemAdapter 未完成，9+ 处 warehouse 硬编码 | 框架无法复用 |
| P3 | abs_min_constraint 在 production 上误触发 | 搜索方向误导 |
| P4 | FIX_TOOL 描述过时（仍写 V5_state_mutation） | 修复指引无效 |
| P5 | 状态机转换表不完整（NEW 状态无转换） | 潜在竞态 |
| P6 | V5 heavy 无修复机会（GPT 119 次失败全部丢弃） | 有效轮次损失 |
| P7 | cross-branch 失败历史不共享 | 重复犯错 |
| P9 | Production campaign 轮次利用率极低 | 1 promote 后耗尽 |

### 设计层面发现

1. **上下文层把评估层的权重关系翻译成了硬约束**：评估层的 `delta = splits_diff × SPLITS_WEIGHT + cost_diff` 允许 trade-off，但 LLM 上下文写的是 "splits >> cost ALWAYS"（严格字典序）。
2. **倾向 vs 约束**：字典序多目标的正确表述是"不恶化高优先级的前提下优化当前目标"——这是倾向，不是严格限制。
3. **多目标兼容单目标**：Scion 作为多目标框架，天然兼容加权单目标（一个目标 = 多目标的退化形式）。
4. **评估层和上下文层应分离**：delta+win_rate 是评估机制，LLM guidance 是独立关注点。

---

## 三、优化实施（Phase 1-5 + ObjectiveBreakdown Sprint）

### Phase 1：快速修复（P4 + P5）

| 改动 | 文件 |
|------|------|
| FIX_TOOL 描述更新：V5_state_mutation → V5_solution_consistency | `schemas.py`, `context_manager.py` |
| NEW 状态添加到转换表 | `branch.py` |

### Phase 2：上下文层改造（P3 + 倾向性描述）

| 改动 | 文件 |
|------|------|
| `abs_min_constraint` → `_build_objective_guidance()`（倾向性语言） | `context_manager.py` |
| `ChampionSaturationAnalyzer` 新增 `lower_bounds` 参数 | `saturation.py` |
| `render_saturation_signals` 移除 MANDATORY CONSTRAINT | `saturation.py` |
| Locus 集合从 `spec.operator_categories` 读取 | `context_manager.py` |
| 移除 split 质量阈值硬编码 | `context_manager.py` |
| `CampaignManager` 新增 `objective_lower_bounds` 参数 | `campaign.py` |

### Phase 3：早停重设计（P1 + P9）

新增三条规则替代原有两条：

| 规则 | 触发条件 | 解决问题 |
|------|---------|---------|
| `all_bounded` | 所有目标达到已知下界 | 数学确定性停止 |
| `budget_efficiency` | idle ratio > 60% | 空转检测（P9） |
| `diminishing_returns` | 连续 15 轮无 promote + plateau 信号 | 收益递减检测 |

新增 `_rounds_since_last_promote` 计数器，promote 时重置。

### Phase 4：V5 修复机会 + 失败历史共享（P6 + P7）

| 改动 | 文件 |
|------|------|
| V5 统一改为 light severity（所有失败都可 fix retry） | `state_mutation.py` |
| `FamilyEntry` 新增 `recent_failure_details` 字段 | `search_memory.py` |
| AVOID 渲染包含最近失败详情 | `search_memory.py` |

### Phase 5：ProblemAdapter 完整迁移（P2）

| 改动 | 文件 |
|------|------|
| `WarehouseDeliveryAdapter.render_problem_summary()` 填充完整 warehouse 描述 | `adapter.py` |
| `WarehouseDeliveryAdapter.render_operator_interface()` 填充完整数据结构+约束 | `adapter.py` |
| `ContextManager` 接收 adapter，优先委托 adapter 渲染 | `context_manager.py` |
| `_build_problem_summary` / `_build_operator_interface_spec` 旧 body 精简为 fallback | `context_manager.py` |
| Locus 多样化泛化（不再硬编码 vehicle_level ↔ order_level） | `campaign.py` |
| `_extract_mechanism_label` 支持 taxonomy 参数 | `context_manager.py`, `search_memory.py`, `stagnation.py` |
| `StagnationDetector` 支持 taxonomy | `stagnation.py` |

### ObjectiveBreakdown 泛化 Sprint

| 改动 | 文件 |
|------|------|
| `PairwiseCaseFeedback.objective_breakdown` → `objective_comparison: ObjectiveComparison` | `models.py` |
| `CaseAggregateFeedback` 泛化：`decisive_metric` + `median_deltas: Dict` | `models.py` |
| 删除 `_objective_comparison_to_breakdown` shim | `experiment.py` |
| `_aggregate_case_feedback` 从 `ObjectiveComparison.metrics` 读取 | `experiment.py` |
| `_build_pattern_summary` 使用 `decisive_metric` | `experiment.py` |
| `extract_champion/candidate_metrics` 从 `oc.metrics` 迭代 | `saturation.py` |
| `_render_case_feedback` / `_select_cases_for_prompt` 使用 `median_deltas` | `context_manager.py` |
| Champion baselines 从 `MetricComparison` 构建 | `context_manager.py` |

---

## 四、当前 Scion 状态

### 4.1 代码质量

- **973 tests pass**，0 new failures（4 pre-existing failures 与本次改动无关）
- 净减少 ~200 行 warehouse 硬编码
- `ObjectiveBreakdown` 标记为 DEPRECATED，不再有新代码构造

### 4.2 框架泛化程度

| 模块 | 泛化状态 |
|------|---------|
| 上下文层（LLM prompt） | ✅ adapter 驱动，倾向性描述 |
| 评估层（delta + win_rate） | ✅ ObjectiveComparison 泛化 |
| 早停 | ✅ 三条通用规则，无 warehouse 依赖 |
| 验证层（V5） | ✅ 统一 light，fix retry |
| 搜索记忆 | ✅ taxonomy-aware 机制标签 |
| 饱和分析 | ✅ lower_bounds 参数驱动 |
| Locus 多样化 | ✅ 从 spec.operator_categories 读取 |
| `_build_problem_summary` | ✅ adapter 优先，fallback 精简 |
| `_build_operator_interface_spec` | ✅ adapter 优先，fallback 精简 |
| `ObjectiveBreakdown` | ✅ DEPRECATED，替换为 ObjectiveComparison |
| `CaseAggregateFeedback` | ✅ generic `decisive_metric` + `median_deltas` |
| `_MECHANISM_KEYWORDS` | ⚠️ 硬编码 fallback 保留（taxonomy 优先路径已加） |
| `extract_champion/candidate_metrics` case_features 路径 | ⚠️ 仍引用 "champion_splits"/"champion_cost"（legacy fallback） |

### 4.3 遗留项

1. **`ObjectiveBreakdown` 类定义**：保留为 DEPRECATED，待所有下游消费者确认无引用后删除。
2. **`CaseAggregateFeedback` deprecated aliases**：`dominant_decisive_objective`、`median_delta_total_cost`、`median_delta_subcategory_splits` 保留为向后兼容字段。
3. **`evaluation.py` legacy 路径**：`compare_with_breakdown()` 等函数仍在，作为无 `metric_specs` 时的 fallback。待确认所有实验配置都传入 `metric_specs` 后可删除。
4. **`_MECHANISM_KEYWORDS` 硬编码关键词**：taxonomy 优先路径已加，但 `context_manager.py` 内部调用未传 taxonomy（无 spec 上下文）。

### 4.4 Git 历史

```
bcc6a21 fix: set log level to INFO, silence DEBUG noise
2646d02 fix(v5): make all V5 failures light severity
203ca29 feat(experiment): post-optimization validation campaign runner
e070f61 data(milp): Sprint F4 MILP bounds (78 instances)
8b56b04 docs(w16): experiment infrastructure + campaign log + pre-registration
1cea806 chore: W16 prep
57dabb0 feat(generic): genericize ObjectiveBreakdown → ObjectiveComparison
2d382e3 refactor(adapter): Phase 5 cleanup — strip warehouse prose
4b78226 feat(adapter): Phase 5 — wire ProblemAdapter into ContextManager
8496705 feat(w16): Phase 1-4 optimization
```

### 4.5 验证实验

**状态**：运行中（tmux session `val-exp`）

| Campaign | 配置 |
|----------|------|
| sonnet-4-6_synthetic_seed11 | 100 rounds, SPLITS_WEIGHT=1000, adapter + lower_bounds + metric_specs |
| gpt-54-mini_synthetic_seed11 | 同上 |

输出目录：`~/research/scion-experiments/v03-post-opt/`

**验证目标**：
1. 早停 `budget_efficiency` 是否在空转 60% 后触发
2. V5 light severity 下 GPT 的修复成功率
3. 倾向性上下文是否改变 LLM 搜索行为
4. adapter 驱动的 problem summary 是否正常工作
5. ObjectiveComparison 管线是否全链路正确

---

## 五、设计原则（本次确认）

1. **多目标框架兼容单目标**：Scion 是多目标组合优化 agent 框架。多目标天然包含单目标和加权目标作为特例。框架不区分 lexicographic/weighted 模式。

2. **倾向而非约束**：字典序的正确表述是"不恶化高优先级目标的前提下优化当前目标"——这是倾向，不是严格限制。LLM 上下文用软偏好语言，不用硬约束。

3. **评估层与上下文层分离**：`delta = Σ(weight_i × diff_i)` + `win_rate` 是评估机制，与 LLM 搜索引导是独立关注点。两者兼容单目标场景。

4. **ProblemAdapter 是边界**：所有 problem-specific 内容（目标描述、数据结构、约束列表、可行性检查）通过 adapter 注入。Scion core 不直接引用 warehouse 概念。
