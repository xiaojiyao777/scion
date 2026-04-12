# 09 — Failure Router

## 定位

Campaign 主循环里会遇到各种失败——代码语法错、API 超时、feasibility 违反、screening 不过……每种失败该怎么处理完全不同。FailureRouter 把失败统一分类，然后派发到正确的处理路径。

**实现状态**：Sprint G2-patch 落地，当前可正常工作。

---

## 四层分类

```
Layer A: Proposal / Contract Failure
  ← schema 格式错 / 文件白名单违规 / import 黑名单
  → RETRY_LLM，不消耗分支预算，不写 hypothesis memory

Layer B: Verification Failure（轻 / 重）
  轻度（light）: syntax / interface / unit test
  → RETRY_LLM（最多 N 次），不消耗预算
  重度（heavy）: feasibility violation / state mutation / nondeterminism
  → DISCARD，消耗分支预算，写入 hypothesis memory

Layer C: Runtime / Infra Incident
  ← subprocess timeout / OOM / LLM API failure
  → RETRY_INFRA，不消耗预算，不改变分支状态

Layer D: Evaluation Outcome
  ← screening_fail / validation_fail / frozen_fail / unclear
  → 走协议规则，消耗预算，写入 hypothesis memory
```

---

## 四种路由动作

| 动作 | 含义 | 触发场景 |
|------|------|---------|
| RETRY_LLM | 把错误反馈给 LLM，重新生成 | 轻度 verification 失败、schema 错 |
| RETRY_INFRA | 等待后重试同一实验 | API timeout、OOM |
| DISCARD | 丢弃 hypothesis，分支继续 | 重度 verification 失败 |
| ABANDON | 整个分支放弃 | 预算耗尽、严重失败 |

---

## 为什么区分轻 / 重 Verification

**轻度**（V1/V2/V3）：LLM 写了语法错或接口不符的代码，"写错了"，给它看错误信息可以改。

**重度**（V5/V8）：feasibility violation 或 nondeterminism 说明算子核心设计有问题，再 retry 只是浪费调用。直接丢弃并计入预算。

---

## 预算影响

```
轻度失败 retry    → 不消耗 branch budget
重度失败 discard  → 消耗 budget
Infra retry       → 不消耗
Screening fail    → 消耗（实验跑了，有结论）
```

---

## Sprint G2-patch 做了什么

G2-patch 之前：FailureRouter 的分类逻辑存在，但路由决策只写进 Lineage 日志，主循环里没有实际调用对应处理函数。

G2-patch 之后：`retry_llm / retry_infra / discard / abandon` 在主循环里真正被执行，不再只是写日志。Lineage 同步增加 `event_kind` 区分和 audit columns（model_id / protocol_version / tokens）。

---

## 已知设计缺口（v0.3 待改进）

### 缺口一：无时间记忆

FailureRouter 每次失败独立决策，不看历史模式。

```
Round 1-30: V3_unit_tests → RETRY_LLM（每次相同决定）
```

F3 实验中，pytest 环境问题导致 30 轮全部失败，FailureRouter 从未升级为 INFRA_SUSPECTED，30 轮全部浪费。

**修复**：同类 light failure 连续 3 次 → 升级为 INFRA_SUSPECTED → 触发 circuit breaker。

### 缺口二：与 StagnationDetector 断联

FailureRouter 观察到的失败模式不流入 StagnationDetector。当前四种 stagnation 模式（collapse/oscillation/plateau/timeout_cascade）不覆盖"infra_loop"场景。

**修复**：增加第五种 stagnation 模式：
```
infra_loop: 同种 light failure 连续 5+ 次 → should_stop
```

### 缺口三：评估结果路由粒度太粗

wr=0.15 和 wr=0.55 都走 `continue_explore`，信息完全不同：
- wr=0.15：碾压级失败，方向大概率死了
- wr=0.55：刚差一点，值得深挖

**修复**：
```
wr < 0.3    → ABANDON_FAST（快速放弃）
wr 0.3-threshold → CONTINUE_EXPLORE
wr 接近 threshold → CONTINUE_EXPLORE + 提升 expand 优先级
```

### 缺口四：无跨分支失败共享

Branch A 和 Branch B 独立踩同一类算子的同一个坑，重复浪费预算和 API。

**修复**：全局 failure registry，新分支创建时注入"已知危险失败模式"。

### 缺口五：LLM 看到点状错误，看不到失败模式

轻度失败 retry 时，LLM 只看到本次错误信息，看不到"这种错误在这个分支出现了 N 次"的模式信息。

**修复**：ContextManager 在 retry 上下文里注入失败模式摘要，而不只是单次错误。

---

## v0.3 设计目标

把 FailureRouter 从**无状态点处理器**升级为**有记忆、有联动的失败智能系统**：

| 维度 | 当前 | v0.3 目标 |
|------|------|----------|
| 时间 | 每次独立 | 连续失败自动升级 |
| 空间 | 单分支 | 跨分支失败共享 |
| 联动 | 孤立 | ↔ StagnationDetector 双向数据流 |
| 评估 | 两档 | 多档精细路由 |
