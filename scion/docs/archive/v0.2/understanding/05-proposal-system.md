# 05 — 两轮 Proposal 系统 + Context Manager + Memory

## 为什么要两轮

直接让 LLM 生成代码，容易产生"随便试试"的代码——没有明确的改进方向，只是在解空间里乱走。

两轮设计强迫 LLM **先想清楚，再动手**：

```
Round 1: 提出可检验的假设（自然语言）
Round 2: 基于假设写具体代码
```

---

## Round 1：Hypothesis Generation

**输入上下文（Context Manager 控制暴露）：**

| 信息 | 是否提供 | 原因 |
|------|---------|------|
| Problem spec 摘要 | ✅ | 让 LLM 了解问题结构 |
| Champion 算子代码 | ✅ | 知道现有基线 |
| 本分支历史结果（结构化） | ✅ | 避免重复失败方向 |
| 已失败 hypothesis 列表 | ✅ | 防止重复提案 |
| 兄弟分支状态（简要） | ✅ | 避免重复探索方向 |
| HypothesisFamily 预警 | ✅ | 同族 3+ 次失败时提示换方向 |
| SearchMemory（跨分支去重）| ✅ | Sprint J1 新增，Jaccard 相似度过滤历史方向 |
| Saturation Signal | ✅ | Sprint J2 新增，splits 饱和时提示转向 cost 优化 |
| exploration_coverage | ✅ | Sprint J3 新增，全局已探索 (locus, action) 组合状态 |
| Currently Occupied 活跃假设 | ✅ | Sprint K4 新增，已在进行中的方向清单 |
| Validation/frozen 细节 | ❌ | 防止信息泄漏 |

**输出（结构化 JSON）：**
```python
HypothesisProposal:
  hypothesis_text: str      # 自然语言描述
  change_locus: str         # 枚举：order_level / vehicle_level
  action: str               # "modify" | "create_new" | "remove"
  target_file: Optional[str]
  predicted_direction: str  # "improve" | "tradeoff" | "exploratory"
  target_weakness: str      # 针对 champion 的哪个弱点
  expected_effect: str
  suggested_weight: Optional[float]
```

→ Contract Gate：schema 校验 + change_locus 合法性 + novelty check

---

## Sprint J1：SearchMemory 跨分支去重（v0.2 Sprint J1 新增）

HypothesisFamily 仅在单分支内防止重复方向，无法阻止不同分支独立探索语义相同的假设。

Sprint J1 引入 `SearchMemory`：跨所有分支共享的已探索方向记录，使用 Jaccard 相似度计算新提案与历史提案的文本距离。

```python
SearchMemory:
  # 跨分支全局共享
  past_hypotheses: List[str]   # 所有 ABANDONED / PROMOTED 假设文本

  def is_too_similar(new_hypothesis: str, threshold=0.6) -> bool:
      # Jaccard 相似度：词集合交集 / 并集
      # 相似度 > threshold → 触发 novelty warning 注入 Round 1
```

SearchMemory 不阻止提案，而是在 Round 1 上下文里注入"已探索方向"提示，引导 LLM 主动差异化。不持久化（session 结束后清空），v0.3 family_id 持久化是后续工作。

---

## Sprint J2：Saturation Signal（v0.2 Sprint J2 新增）

`ChampionSaturationAnalyzer` 检测当前 champion 在各目标维度的饱和程度，注入 Round 1 作为方向信号。

```python
ChampionSaturationAnalyzer:
  def analyze(champion, frozen_instances) -> SaturationReport:
    at_absolute_minimum: bool   # splits 是否已降至理论最小值
    splits_headroom: float      # 还能减多少 splits（0=饱和）
    cost_headroom: float        # cost 改善空间估计
```

当 `at_absolute_minimum=True` 时，Round 1 注入：
```
"splits 已在当前实例集的理论最小值，继续追求 splits 减少的方向可能无效，
 建议转向 cost 优化或多目标权衡方向。"
```

Sprint L2 MANDATORY CONSTRAINT 与此联动（见下）。

---

## Sprint J3：exploration_coverage 全局化（v0.2 Sprint J3 新增）

之前 exploration_coverage（已探索的 change_locus × action 组合）只在单分支内统计。Sprint J3 将其全局化，所有分支的探索记录汇总后注入 Round 1。

```python
# Round 1 上下文注入示例
exploration_coverage:
  modify × order_level:    12次（高度探索）
  modify × vehicle_level:  8次（中度探索）
  create_new × order_level: 3次（低度探索，值得尝试）
  remove × *:              0次（未探索）
```

LLM 看到全局覆盖图，主动往低覆盖方向提案，提升全局搜索多样性。

---

## Sprint K4："Currently Occupied" 活跃假设（v0.2 Sprint K4 新增）

除了历史记录外，Round 1 上下文现在包含当前**正在进行中**的活跃假设清单：

```
## Currently Occupied（正在进行的方向）
- Branch-03: "利用 subcategory 信息重排订单装载顺序" [VALIDATING]
- Branch-05: "引入成本感知的车辆拆分策略" [EXPLORE]
```

防止新分支提出与正在进行中的分支语义相同的假设，减少并行探索的重复浪费。

---

## Sprint L2：MANDATORY CONSTRAINT（v0.2 Sprint L2 新增）

当 splits 达到绝对最小值（`ChampionSaturationAnalyzer.at_absolute_minimum=True`）时，Protocol 在 frozen 阶段注入强制约束：

```
## MANDATORY CONSTRAINT
当前 splits 已达绝对最小值。候选方案必须满足：
  splits_count <= champion_splits_count  （不能让 splits 变多）
不满足此约束的候选方案直接判负，不论 cost 改善多少。
```

这防止了在 splits 饱和后，LLM 提出"牺牲少量 splits 换 cost 改善"的方案被错误促进。

---

## Round 2：Code Generation

**输入上下文（比 Round 1 更窄，专注实现）：**

| 信息 | 是否提供 |
|------|---------|
| Approved hypothesis | ✅ |
| Champion 算子代码 | ✅ |
| Target 文件当前内容 | ✅ |
| Operator interface spec | ✅ |
| 本分支历史结果 | ❌ |
| 兄弟分支信息 | ❌ |

→ Contract Gate → WorkspaceMaterializer → Verification Gate → Protocol

---

## Context Manager：暴露控制

ContextManager 的核心职责是**精确控制 LLM 能看到什么**。

**暴露分级：**

| 信息类型 | Round 1 | Round 2 | LLM 永远看不到 |
|---------|---------|---------|--------------|
| Screening per-case 结果 | ✅ 完整 | ❌ | |
| Validation aggregate | ✅ 摘要 | ❌ | |
| Frozen 结果 | ❌ | ❌ | ✅ 永不暴露 |
| 兄弟分支状态 | ✅ 简要 | ❌ | |
| 历史失败假设 | ✅ | ❌ | |

**Prompt Caching：** System prompt ~5800 tokens，TTL 1h，cache hit 率 ~80%，显著降低 API 成本。

---

## Memory 结构：StepRecord

每轮实验结束，写入一条 StepRecord：

```python
StepRecord:
  round_num: int
  branch_id: str
  hypothesis_text: str        # tainted，仅供参考
  action: str                 # modify / create_new / remove
  change_locus: str
  decision: Decision          # CONTINUE_EXPLORE / QUEUE_VALIDATE / PROMOTE...
  screening_win_rate: float
  screening_median_delta: float
  failure_stage: Optional[str]
  failure_detail: Optional[str]
```

ContextManager 在 Round 1 时从历史 StepRecord 中选择性提取，不是全量注入。

**历史管理**：最近 N 轮完整记录 + 所有失败假设摘要 + 所有成功假设摘要，避免 token 随轮数线性增长。

---

## HypothesisFamily：结构化记忆

对历史假设做语义分类，识别同族（相似方向）的假设群。

### 当前实现（规则分类）

```python
family_key = (
    hypothesis.change_locus,    # 枚举
    hypothesis.action,          # 枚举
    hypothesis.target_weakness, # 关键词归一化
)

# 同族连续失败计数
if family_failure_streak[family_key] >= 3:
    → ContextManager 在 Round 1 注入预警
```

**优点**：确定性、零额外 API 调用、无法被 LLM 操纵。

**局限**：字段不同但语义相近的假设无法归族：
```
modify + vehicle_level + "改善 subcategory 合并"     ← 规则认为不同族
create_new + order_level + "让同品类订单聚合"         ← 实际是同方向
```

### v0.3 改进：双路语义分类

引入独立的 Classifier LLM（小模型，如 Sonnet）做语义分族：

```
Hypothesis 生成（proposing LLM，tainted）
    ↓
[Classifier LLM] — 独立调用，上下文完全不同
  输入：hypothesis_text + 当前 family 列表 + problem spec
  输出：family_label（预定义 taxonomy）
  ← 不感知"哪些族已失败"，只做纯分类
    ↓
FamilyTracker.update(family_label, outcome)
```

**为什么不会被操纵**：两次 LLM 调用完全独立（stateless），proposing LLM 不知道 classifier 的提示词，无法预测分类标准，"自我作弊"是伪命题。

**Classifier 隔离原则**：classifier 不注入"已失败方向"信息，防止 proposing LLM 通过多轮观察推断分类规则，进而调整措辞规避预警（跨轮次措辞漂移风险）。

---

## StagnationDetector：Campaign 级记忆

StagnationDetector 分析最近 5 步 StepRecord，检测四种僵局模式：

| 模式 | 触发条件 | 处理 |
|------|---------|------|
| collapse | 连续多次 contract/verification 失败 | → should_stop() |
| oscillation | 反复在两个决策间跳跃 | → 记录，继续 |
| plateau | 连续多次 continue_explore 无改善 | → 记录，继续 |
| timeout_cascade | 连续多次 wall-clock 超时 | → should_stop() |

StagnationDetector 是**观察者，不是决策者**——输出 StagnationSignal 和 CampaignDiagnosis，由确定性的 should_stop() 做最终判断。

---

## 核心设计原则总结

```
LLM 每次调用是无状态的（stateless）
  → 历史记忆完全由 ContextManager 主动注入
  → 历史偏差可控：喂什么才知道什么

分支隔离
  → Branch A 的失败历史不全局广播
  → 方向失败只影响该分支的后续假设

HypothesisFamily 防失败方向的过度坚持
  → 不防成功方向的过度集中（exploitation 偏差）
  → v0.3 用 Classifier LLM + 未探索方向提示来补这个盲点
```

---

## 已知局限：exploitation 偏差

HypothesisFamily 只防"失败方向死磕"，不防"成功方向垄断"。

SubcategoryAwareMoveOrder promote 后，所有分支的历史记录里都有这个成功案例。LLM 会倾向于继续提 subcategory-aware 系列假设，忽略完全不同的方向（如时间窗口优化、装载效率改进）。

**当前缓解**：多分支并行提供有限 exploration 保障，但没有显式的多样性强制机制。

**v0.3 候选**：
- 显式追踪已探索的 (change_locus, action) 组合，在 Round 1 注入"未探索方向"提示
- Tabula Rasa 分支：偶尔创建历史最小化的分支，强制从零出发探索
- 成功记录权重衰减：promoted 算子随时间降低上下文权重
