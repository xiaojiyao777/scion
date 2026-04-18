# Sprint J 设计规划

*日期: 2026-04-13*
*依据: scion-architecture-v3 + GPT-5.4-Pro 审核意见 + CC 源码设计参考 v2 + Sprint F2/F3 实验分析*

---

## 一、背景与动机

### 1.1 Sprint F3 暴露的核心问题

Sprint F3（100r × 3 组，Sprint I 修复后）全部跑满轮次，但揭示了框架在**搜索质量**上的两个根本缺陷：

**缺陷 A：Branch 间知识断层**
- F1 R62-R100：LLM 连续 39 轮生成 `subcategory_swap` 同族变体，全部 wr=0.00-0.20
- 根因：每个新 branch 的 `branch_steps=[]`，families/strategy_guidance 均为空；blacklist 从未被填充；LLM 对全局搜索历史完全失忆

**缺陷 B：目标饱和盲区**
- 三组实验的 split-reduction 在前 3 次晋升后基本饱和，但 LLM 继续在该方向搜索 70-97 轮
- F2 偶然发现 cost 方向（eliminate_weak_vehicle），F1/F3 完全没有切换
- 根因：ContextManager 没有注入"当前 champion 在各目标维度上的改善饱和度"信号

### 1.2 积累的 v0.3 Backlog

以下问题已在设计文档中明确列为 v0.3 必做，未被 Sprint G/H/I 覆盖：

| 来源 | 问题 |
|------|------|
| GPT-5.4-Pro 审核 P0 | strategy_guidance/exploration_coverage/branch_code/champion_baselines 已实现但未注入 prompt（plumbing 断裂） |
| 08-known-issues | Weight Opt 同步阻塞（每次 promote 阻塞 10-40 分钟） |
| sprint-g-summary v0.3 | HypothesisFamily 语义分类（跨 branch 同族检测） |
| sprint-g-summary v0.3 | Weight Opt 结果反馈给 LLM |
| sprint-g-summary v0.3 | ChampionStore 持久化 |
| CC 设计参考 v2 P01 | cross-branch failure sharing（同族算子在不同分支踩同一坑） |
| CC 设计参考 v2 §2.2 | SM Compact（Session Memory 零 LLM 调用压缩）→ Scion 的结构化搜索历史压缩 |

### 1.3 Sprint J 目标

> 把 Scion 从"能跑满轮次但搜索方向固化"升级为"有全局搜索记忆、能感知目标饱和、能自适应切换方向"的框架。

优先级排序（P0 = Sprint J 必做）：
- **J1（P0）**：Campaign Search Memory — 跨 branch 搜索记忆压缩注入
- **J2（P0）**：Objective Saturation Signal — champion 各维度改善饱和度注入
- **J3（P0）**：Prompt Plumbing Fixes — 已实现的 context 字段真正接通 LLM
- **J4（P1）**：Async Weight Optimization + STALE 机制
- **J5（P1）**：HypothesisFamily Semantic Classifier — LLM 辅助分类器（独立调用）
- **J6（P2）**：Weight Opt 结果反馈给 LLM + ChampionStore 持久化

---

## 二、J1：Campaign Search Memory（P0）

### 2.1 问题陈述

当前 `build_hypothesis_context()` 中：
```python
branch_steps = [s for s in step_history if s.branch_id == branch.branch_id]
families = _extract_families_from_steps(branch_steps)   # 新 branch → []
strategy_guidance = _build_strategy_guidance(families)  # 空 → ""
blacklist = hyp_store.get_by_status("blacklisted")      # 从未被填充 → []
```

新 branch 完全不知道其他 branch 发生了什么。

### 2.2 设计方案

**新增 `CampaignSearchMemory` 类**（`scion/proposal/search_memory.py`）：

```python
@dataclass
class FamilyEntry:
    label: str                    # 机制标签（_extract_mechanism_label 产出）
    locus: str
    action: str
    total_attempts: int
    best_wr: float
    consecutive_fails: int        # 当前连续失败次数
    is_exhausted: bool            # total_attempts >= 5 AND best_wr < 0.35
    last_failure_reason: str      # 最近失败的关键 pattern（从 pattern_summary 提取）
    champion_version_at_discovery: int

@dataclass
class CampaignSearchMemory:
    champion_evolution: List[str]   # ["v1→v2 subcategory_consolidate (R3, md=7.2M): 品类合并"]
    exhausted_families: List[FamilyEntry]   # AVOID 列表
    promising_families: List[FamilyEntry]   # wr=0.3-0.6 但未晋升
    coverage_gaps: Dict[str, int]           # locus/action → attempt_count
    # 注意：不设固定 token_budget，由调用方（ContextManager）测量后传入

    def update(self, step: StepRecord) -> None:
        """每轮结束后增量更新，O(1)"""
    
    def render(self, available_tokens: Optional[int] = None) -> str:
        """
        available_tokens=None → 全量输出（不裁剪）
        available_tokens=N   → 在 N tokens 内按优先级分级裁剪

        裁剪优先级（高→低，越高越不能丢）：
          L0: champion 演化 + AVOID 列表标签（最小可用信息）
          L1: AVOID 条目的 last_failure_reason
          L2: promising 方向
          L3: coverage_gaps 详细统计

        token 估算用字符/4（保守，不调用 API）。
        """
    
    def estimate_tokens(self, level: Literal["full", "compact", "minimal"]) -> int:
        """估算各压缩级别的 token 数，供 ContextManager 决策用"""
```

**渲染格式**（无固定预算，由 ContextManager 根据实际 context 剩余空间决定传入多少）：

```
## Campaign Search Memory

### Champion 演化
v1 → v2 subcategory_consolidate (R3, frozen md=7.2M): 品类合并升级车型
v2 → v3 drain_vehicle (R61, frozen md=4K): 同品类内清空最小车

### 已耗尽方向（AVOID — 全局失败 ≥5 次，best_wr < 0.35）
subcategory_swap [39次, best_wr=0.30]: champion splits 已饱和，swap 无法减少
purify_vehicle   [12次, best_wr=0.30]: 驱逐少数品类无效
evacuate_minority [ 8次, best_wr=0.30]: 同上

### 有信号方向（值得参考，但实现不足）
drain_vehicle 方向: [已晋升]
subcat_rebalance [wr=0.40, R20]: 方向正确，实现可更强

### 搜索覆盖缺口（OPPORTUNITY）
vehicle_level/create_new: 75次 ← 过度探索
order_level/create_new:    3次 ← 严重不足
vehicle_level/modify:      5次 ← 不足
vehicle_level/remove:      0次 ← 从未尝试
```

**淘汰规则**（budget 溢出时）：
1. 永不淘汰：champion_evolution，coverage_gaps
2. 先淘汰：promising_families 中 wr < 0.25 的
3. 再淘汰：exhausted_families 中 attempts < 3 的（变成"早期失败"降级存储）

**"已耗尽"判定**：同一 family（跨所有 branch）累计 ≥ 5 次 fail，且 best_wr < 0.35。

### 2.3 ContextManager 负责测量与调度

**核心原则**：Search Memory 自己不知道也不应该知道 context window 总量——它只负责按调用方传入的可用空间做分级渲染。测量和调度是 ContextManager 的职责。

```python
# context_manager.py 中，build_hypothesis_context() 调用 render() 前：
def _compute_search_memory_budget(self, other_blocks: List[str]) -> Optional[int]:
    """
    测量其他所有 blocks 已占用的 token 数，
    返回 Search Memory 可用的剩余预算（None = 不限）。
    
    token 估算：字符数 / 4（保守系数），避免调用 API 计数。
    CONTEXT_WINDOW_LIMIT 和 SAFETY_MARGIN 从 config 读取，
    不同模型（Opus 1M / Sonnet 1M）context window 均为 1,000,000 tokens，
    safety_margin 建议 50K（留给输出 + 工具结果），实际可用约 950K。
    在 1M 窗口下，Search Memory 几乎不会被压缩，available_tokens=None（全量）是常态。
    分级裁剪逻辑作为保险机制保留，应对未来更小 context 模型。
    """
    used = sum(len(b) // 4 for b in other_blocks)
    remaining = self._config.context_window_limit - used - self._config.safety_margin
    return max(0, remaining) if remaining < self._config.context_window_limit * 0.8 else None
    # 若剩余 > 80% → 不限制（全量输出），只在接近上限时才收紧
```

**`CampaignManager.__init__`**：
```python
self._search_memory = CampaignSearchMemory()
```

**`CampaignManager.run_one_step()`** 末尾：
```python
self._search_memory.update(step_record)
```

**`_on_promote()`** 中：
```python
self._search_memory.record_champion_promotion(branch, champion_version, frozen_md)
```

**`ContextManager.build_hypothesis_context()`**：
```python
def build_hypothesis_context(
    self,
    ...
    search_memory: Optional[CampaignSearchMemory] = None,
    ...
) -> Dict[str, Any]:
    ...
    search_memory_block = search_memory.render() if search_memory else ""
    return {
        ...
        "search_memory": search_memory_block,
        ...
    }
```

**Prompt 注入**（`_split_hypothesis_context()` 中 system blocks 部分，在 champion code 之前）：
```
## Global Search Memory
{search_memory_block}
```

### 2.4 与现有 blacklist 机制的关系

废弃当前 `hyp_store.get_by_status("blacklisted")` 的 blacklist 展示（因为 blacklisted 状态从未被写入）。由 Search Memory 的 AVOID 列表替代，信息更丰富（包含失败次数、best_wr、失败原因）。

### 2.5 测试要求

- `test_search_memory_update_on_abandon`：abandon 后 family.total_attempts+1，consecutive_fails+1
- `test_search_memory_reset_on_promote`：promote 后，相关 family 的 consecutive_fails=0（新 champion 下重新计）
- `test_exhausted_detection`：≥5 次 fail 且 best_wr<0.35 → is_exhausted=True
- `test_render_within_budget`：render() 输出 token 数 ≤ budget（用字符/4 估算）
- `test_render_eviction`：超出 budget 时低优先级条目被淘汰
- `test_coverage_gaps_computed`：vehicle_level/create_new=75 次时，rendered 中显示"过度探索"

---

## 三、J2：Objective Saturation Signal（P0）

### 3.1 问题陈述

F1/F3 在 split-reduction 基本饱和后继续搜索 70-97 轮无效。LLM 没有感知到"主要目标已接近最优，应切换到次要目标"。

F2 偶然发现了 cost 方向，是因为 LLM 在 v3 晋升后的某轮 hypothesis 中显式推断了"splits 已在局部最优，唯一改进是 cost"——这是 LLM 自己推断的，不是框架提示的，因此不可靠。

### 3.2 设计方案

**新增 `ChampionSaturationAnalyzer`**（`scion/proposal/saturation.py`）：

```python
@dataclass
class SaturationSignal:
    objective: str           # "business_aggregation" | "cost" | "efficiency"
    improvement_ratio: float # (initial - current) / initial，正值=改善
    saturation_level: str    # "low"(<30%) | "medium"(30-70%) | "high"(>70%)
    opportunity_hint: str    # 改善空间文字描述

class ChampionSaturationAnalyzer:
    """
    分析 champion 在各目标维度上的改善饱和度。
    
    计算方式：
    - 基线：v1 champion 在 benchmark 上的均值（campaign 启动时一次性计算）
    - 当前：最近一次 frozen holdout 实验的 champion 表现
    - 改善比 = (baseline - current) / baseline （splits 越小越好）
    """
    
    def analyze(
        self,
        step_history: List[StepRecord],
        benchmark_baseline: Dict[str, float],  # v1 champion 的均值指标
    ) -> List[SaturationSignal]:
```

**`CampaignManager`** 启动时计算 v1 benchmark 基线（对 screening cases 跑一次 v1 solver，记录均值 splits 和 cost）。

**注入格式**（在 Search Memory block 之后，固定 ~200 tokens）：

```
## Champion 当前状态与改善空间

目标饱和度（vs baseline v1 champion）：
  subcategory_splits: 改善 82%（high saturation）→ 接近局部最优
  total_cost:         改善 12%（low saturation）← 仍有较大空间
  
搜索建议：splits 改善空间已高度饱和，建议探索 cost-reduction 方向。
  当前 champion 典型分布：m 实例 ~{N} splits，cost ~{C}
```

### 3.3 接入点

`CampaignManager.__init__`：
```python
self._baseline_metrics = self._compute_baseline_metrics()   # v1 champion 跑 benchmark
self._saturation_analyzer = ChampionSaturationAnalyzer(self._baseline_metrics)
```

`build_hypothesis_context()` 新增参数：
```python
saturation_signals: Optional[List[SaturationSignal]] = None
```

### 3.4 实现约束

- baseline 计算只在 campaign 启动时跑一次（使用 screening 实例子集，不超过 5 个 medium 实例）
- 不引入 LLM 调用，纯数值计算
- saturation_level 的阈值：高饱和 > 70%（即已改善超过 baseline 的 70%）

### 3.5 测试要求

- `test_baseline_computed_once`：`_compute_baseline_metrics` 只在 init 时调用一次
- `test_saturation_level_high`：splits 改善 82% → level="high"
- `test_saturation_level_low`：cost 改善 12% → level="low"
- `test_saturation_render`：render 后包含"建议探索 cost-reduction"

---

## 四、J3：Prompt Plumbing Fixes（P0）

### 4.1 问题陈述

GPT-5.4-Pro 审核（3.2 节）发现：`build_hypothesis_context()` 已构建了多个字段，但 `_split_hypothesis_context()`（CreativeLayer 的 prompt 组装函数）完全没有使用它们：

| 字段 | 已实现 | 已注入 prompt |
|------|--------|---------------|
| `exploration_coverage` | ✅ | ❌ |
| `strategy_guidance` | ✅ | ❌ |
| `branch_code` | ✅ | ❌ |
| `champion_baselines` | ✅ | ❌ |
| `prior_failure` in code context | ✅ | ❌ |

这意味着 Sprint E 的大量 prompt engineering 工作是"写了但没生效的"。

### 4.2 修复内容

**文件**：`scion/proposal/engine.py`（`CreativeLayer._split_hypothesis_context()`）

**修复**：将以下字段显式注入 system blocks：

```python
# Round 1: hypothesis context
system_blocks = [
    # Block 1 (cacheable): Problem spec + operator interface
    {"type": "text", "text": problem_summary + operator_interface, "cache_control": {"type": "ephemeral"}},
    
    # Block 2 (cacheable): Champion code（更新频率低）
    {"type": "text", "text": f"## Champion Code\n{champion_code}", "cache_control": {"type": "ephemeral"}},
    
    # Block 3 (non-cache): 动态内容 - 每轮变化
    {"type": "text", "text": "\n".join(filter(None, [
        search_memory_block,          # J1 新增
        saturation_signal_block,      # J2 新增
        exploration_coverage,         # ← 修复：之前未注入
        strategy_guidance,            # ← 修复：之前未注入
        champion_baselines,           # ← 修复：之前未注入
        experiment_history,           # 已有，保持
        branch_code_diff,             # ← 修复：之前未注入（分支代码 vs champion 的 diff）
        forced_locus_constraint,      # Sprint I 已有
        failure_pattern_warning,      # Sprint H2 已有
    ]))}
]
```

**Round 2 code context**：
```python
# 修复：prior_failure 未被注入
if prior_failure:
    user_message = f"## Previous Code Generation Failed\n{prior_failure}\n\n{user_message}"
```

### 4.3 branch_code_diff 实现

当 `branch_workspace != champion.code_snapshot_path` 时，展示差异（只展示变化的算子文件，不展示未变化的）：

```python
def _build_branch_code_diff(branch_workspace: str, champion: ChampionState) -> str:
    """对比 branch workspace 与 champion snapshot，只返回变化的算子文件内容。"""
    # 用 filecmp + readlines 做简单 diff
    # 只展示 operators/ 目录下的差异文件
    # 格式：## Branch Code Changes\n--- champion/{file}\n+++ branch/{file}\n...
```

### 4.4 测试要求

- `test_exploration_coverage_in_prompt`：mock context，验证 exploration_coverage 字符串出现在 system blocks
- `test_strategy_guidance_in_prompt`：同上
- `test_prior_failure_in_code_prompt`：code context with prior_failure → 出现在 user message
- `test_branch_code_diff_shows_changes`：branch 有修改算子时，diff 出现在 prompt
- `test_no_diff_when_same_as_champion`：branch 未改代码时，diff block 为空

---

## 五、J4：Async Weight Optimization + STALE 机制（P1）

### 5.1 问题陈述

当前 `_on_promote()` 同步运行 weight optimization，每次 promote 阻塞 campaign 10-40 分钟（08-known-issues P1）。这导致：
- F1 在 R7 promote 后阻塞，然后才开始搜索 v3 算子（浪费实际时钟时间）
- 并行实验（F1/F2/F3）互不影响，但单个实验内部搜索效率受损

### 5.2 设计方案（来自 08-known-issues v0.3 路线图）

```python
def _on_promote(self, branch: Branch) -> None:
    # Step 1: 立即用旧权重创建新 champion（返回，不阻塞）
    new_champion = self._create_champion_snapshot(branch)
    self._champion = new_champion
    self._mark_all_stale()  # 标记现有活跃 branch 为 STALE
    
    # Step 2: 后台异步跑 weight optimization
    thread = threading.Thread(
        target=self._run_weight_opt_async,
        args=(new_champion,),
        daemon=True,
    )
    thread.start()
    self._pending_weight_opt = thread

def _run_weight_opt_async(self, champion: ChampionState) -> None:
    # 后台线程：跑 weight optimization，完成后写回 registry.yaml
    result = self._weight_optimizer.optimize(...)
    if result.improved:
        self._apply_weight_opt_result(result)
        self._mark_all_stale(reason="weight_update")  # 再次标记，用新权重重做
    self._weight_opt_event.set()
```

**STALE 机制**：
- promote 时，所有活跃 branch 标记为 STALE（等待 reconcile 到新 champion）
- weight opt 完成后，再次标记 STALE（需要用新权重重做 screening）
- Reconcile 流程：weight_update_stale → re-screening（仅 screening，不需要完整 validate/frozen）

**超时处理**：weight opt 超时（>15min）→ 跳过权重更新，保持当前权重，清除 pending 标记。

### 5.3 新增状态

`BranchState` 新增：`STALE_WEIGHT_UPDATE`（区别于 promote 引起的 STALE）

### 5.4 约束

- Double-promote：第二次 promote 时，取消第一个 weight opt thread（通过 cancel event）
- weight opt 用 eval_ws（独立副本），不直接修改 champion snapshot

---

## 六、J5：HypothesisFamily Semantic Classifier（P1）

### 6.1 问题陈述

当前 `_extract_mechanism_label()` 是纯规则关键词匹配，无法识别：
- modify + vehicle_level + "让同品类订单聚合" ≡ create_new + order_level + "subcategory 合并" 的语义等价性
- 同一方向的不同描述词（evacuate / evict / purify / drain 都是"清空低效车辆"族）

导致 Search Memory 的 family 分类粒度过粗，AVOID 列表无法有效覆盖语义近邻方向。

### 6.2 设计方案（来自 sprint-g-summary v0.3 backlog）

**Classifier LLM 调用**（独立于主循环，不影响决策边界）：

```python
class HypothesisFamilyClassifier:
    """
    独立的语义分类器（Sonnet/Flash 级别，不需要 Opus）。
    与主 proposal LLM 完全隔离：不注入"哪些族已失败"信息，只做纯分类。
    """
    
    TAXONOMY = [
        "subcategory_merge_consolidate",   # 品类合并/整合（两车→一车）
        "subcategory_chain_rotation",      # 三车链式旋转
        "intra_subcat_repack",             # 同品类内订单重打包（drain 类）
        "cross_subcat_displacement",       # 跨品类订单驱逐/重分配
        "vehicle_elimination_cost",        # 消车降成本（cost-focused）
        "subcat_rebuild_destroy",          # 品类感知 destroy-rebuild
        "order_level_reassign",            # 订单级重分配
        "generic_merge",                   # 通用合并（无品类感知）
        "NEW_FAMILY",                      # 以上都不符合时
    ]
    
    def classify(self, hypothesis_text: str) -> str:
        """返回 taxonomy 中的标签名"""
```

**集成方式**：
- 在 `CampaignManager.run_one_step()` 中，Round 1 生成 hypothesis 后，异步调用 Classifier（不阻塞主循环）
- 分类结果写入 `HypothesisRecord.family_id`（现有字段，原本用规则方法填写）
- `CampaignSearchMemory` 使用 Classifier 的结果而非 `_extract_mechanism_label()`

**降级**：Classifier 调用失败 → 回退到规则方法（不阻塞）。

### 6.3 约束

- Classifier 调用不进入 Decision Layer，结果只用于 Search Memory 和 strategy_guidance
- 使用独立的 `SCION_CLASSIFIER_MODEL` 环境变量（默认 claude-sonnet-4-6）
- 分类延迟 ≤ 3s（Sonnet Flash 级别调用）

---

## 七、J6：Weight Opt 反馈 + ChampionStore 持久化（P2）

### 7.1 Weight Opt 结果反馈给 LLM

当前 weight opt 结果（各算子权重）不进入 LLM 上下文。这与 Saturation Signal（J2）配合使用效果最好。

注入格式（在 saturation block 之后，~100 tokens）：
```
## 当前算子贡献估计（weight optimization 结果）
  subcategory_consolidate:  高贡献（权重 4.97）
  drain_vehicle:            高贡献（权重 2.31）
  subcat_focused_rebuild:   中等贡献（权重 1.12）→ 可能有改进空间
```

### 7.2 ChampionStore 持久化

在 `_on_promote()` 末尾调用 `ChampionStore.record()`，写入 SQLite `champions` 表（目前该表始终为空）。需实现 `ChampionStore.record()` 方法。

---

## 八、测试总要求

Sprint J 完成后，全量测试必须通过：

```bash
~/miniconda3/envs/claw/bin/python -m pytest scion/tests/ -q --tb=short
```

新增测试文件：
- `scion/tests/unit/test_sprint_j1_search_memory.py`（≥10 cases，J1）
- `scion/tests/unit/test_sprint_j2_saturation.py`（≥6 cases，J2）
- `scion/tests/unit/test_sprint_j3_prompt_plumbing.py`（≥8 cases，J3）
- `scion/tests/unit/test_sprint_j4_async_weight.py`（≥8 cases，J4）
- `scion/tests/unit/test_sprint_j5_classifier.py`（≥6 cases，J5，含 Classifier mock）

**集成测试**（mock campaign）：
- `test_sprint_j_e2e_no_swap_loop`：模拟 39 轮 subcategory_swap 场景，验证 Search Memory 中 AVOID 列表包含该族且被注入 prompt
- `test_sprint_j_e2e_saturation_switch`：模拟 split 改善 80% 后，验证 saturation block 显示"建议探索 cost"

---

## 九、模块修改范围

| 文件 | 改动 | Sprint |
|------|------|--------|
| `scion/proposal/search_memory.py` | **新建** | J1 |
| `scion/proposal/saturation.py` | **新建** | J2 |
| `scion/proposal/classifier.py` | **新建** | J5 |
| `scion/proposal/context_manager.py` | 接收 search_memory/saturation 参数，修复 plumbing | J1/J2/J3 |
| `scion/proposal/engine.py` | `_split_hypothesis_context()` 真正注入所有字段 | J3 |
| `scion/core/campaign.py` | 初始化 SearchMemory/Saturation，接入 Async weight opt | J1/J2/J4 |
| `scion/core/termination.py` | 无修改（Sprint I 已足够） | — |
| `scion/core/models.py` | `BranchState` 新增 `STALE_WEIGHT_UPDATE` | J4 |
| `scion/parameter/optimizer.py` | 支持 cancel signal | J4 |
| `scion/lineage/champion_store.py` | 实现 `record()` 方法 | J6 |

---

## 十、优先级与执行顺序

```
Phase 1（必须完成，直接影响搜索质量）：
  J1（Search Memory） → J2（Saturation Signal） → J3（Prompt Plumbing）
  三者共享 context_manager.py 修改，建议一起实现避免冲突

Phase 2（架构优化，不影响搜索质量但提升效率）：
  J4（Async Weight Opt）

Phase 3（增强，可延后）：
  J5（Family Classifier）→ 依赖 J1 的 Search Memory 基础设施
  J6（Weight feedback + ChampionStore）→ 依赖 J4 完成
```

**估计工作量**：J1+J2+J3 约 600-800 行代码（新建 2 个模块 + 修改 2 个模块），J4 约 200 行，J5+J6 约 300 行。

---

## 十一、完成后

```bash
touch /tmp/sprint-j-done
openclaw system event --text "[Sprint J] 完成" --mode now
```
