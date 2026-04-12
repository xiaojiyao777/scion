# 05 — 两轮 Proposal 系统

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
| Validation/frozen 细节 | ❌ | 防止信息泄漏 |

**输出（结构化 JSON）：**
```python
HypothesisProposal:
  hypothesis_text: str      # 自然语言描述改进逻辑
  change_locus: str         # 枚举：order_level / vehicle_level
  action: str               # "modify" | "create_new" | "remove"
  target_file: Optional[str]
  predicted_direction: str  # "improve" | "tradeoff" | "exploratory"
  target_weakness: str      # 针对 champion 的哪个弱点
  expected_effect: str
  suggested_weight: Optional[float]  # 新算子建议初始权重
```

→ Contract Gate：schema 校验 + change_locus 合法性 + novelty check（防止重复）

---

## Round 2：Code Generation

**输入上下文（比 Round 1 更窄，更聚焦）：**

| 信息 | 是否提供 | 原因 |
|------|---------|------|
| Approved hypothesis | ✅ | 代码要忠实实现这个假设 |
| Champion 算子代码 | ✅ | 参考接口和现有实现 |
| Target 文件当前内容 | ✅ | modify 时需要知道改哪里 |
| Operator interface spec | ✅ | 必须遵守接口契约 |
| 本分支历史结果 | ❌ | Round 2 专注于代码实现，不需要历史 |
| 兄弟分支信息 | ❌ | 同上 |

**输出（结构化 JSON）：**
```python
PatchProposal:
  file_path: str
  action: str           # "modify" | "create" | "delete"
  code_content: str     # 完整文件内容（Scion 自行 diff）
  test_hint: Optional[str]  # tainted，仅存档，不进决策
```

→ Contract Gate → WorkspaceMaterializer → Verification Gate → Protocol

---

## Context Manager：暴露控制

ContextManager 的核心职责是**控制 LLM 能看到什么**，防止信息过度暴露导致：
1. LLM 对 validation/frozen 实例过拟合
2. LLM 看到过多上下文导致 token 浪费和质量下降

**关键暴露原则：**
- Screening 结果：完整 per-case 细节（帮助 LLM 分析哪类实例有效）
- Validation 结果：仅 aggregate（win_rate + delta，不暴露 case 细节）
- Frozen 结果：仅 pass/fail，永不暴露 aggregate

---

## Prompt Caching

LLM 调用使用 Anthropic prompt caching（TTL 1h）：
- System prompt（~5800 tokens）：problem spec + interface spec + operator 代码 → cached
- 历史上下文：每轮新增，不 cached
- 效果：cache hit 率 ~80%，显著降低 API 成本

---

## HypothesisFamily 追踪（Sprint E）

对所有 hypothesis 做语义分类，识别同族（相似方向）的假设。

**用途**：如果同一族连续失败 3 次，StagnationDetector 触发"换方向"警告，提示 LLM 跳出局部搜索陷阱。

---

## Failure 路由

| 失败类型 | LLM 可重试？ | 消耗分支预算？ |
|---------|:---:|:---:|
| Schema/JSON 格式错误 | ✅（轻度） | 否 |
| Contract 违规（import 等）| ✅（轻度） | 否 |
| Unit test 失败 | ✅（限次） | 否 |
| Feasibility violation | ❌（重度） | 是 |
| State mutation/nondeterminism | ❌（重度） | 是 |
| Screening fail | — | 是（但 branch 继续） |
| Validation fail | — | 是，branch ABANDONED |
