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
