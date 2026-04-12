# 00 — 整体架构概览

*阅读本文前可先看 [01-what-is-scion.md](01-what-is-scion.md) 了解背景。*

---

## 一次完整 Campaign Round 的数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                        Campaign Manager                          │
│                                                                 │
│  Scheduler（词典序优先级）                                        │
│    → 选下一个分支 + 决定操作类型                                   │
│                    │                                            │
│          ┌─────────▼──────────┐                                │
│          │   _run_explore_step │  ← EXPLORE 分支                 │
│          └─────────┬──────────┘                                │
│                    │                                            │
│         ┌──────────▼───────────────────────────┐              │
│         │  Proposal Engine（两轮）               │              │
│         │                                       │              │
│         │  Round 1: Hypothesis（LLM，tainted）   │              │
│         │    Context Manager 构造上下文           │              │
│         │    ← _step_history（内存）             │              │
│         │    ← HypothesisFamily 预警             │              │
│         │    ← 兄弟分支状态                       │              │
│         │    ← Champion 算子代码                 │              │
│         │                                       │              │
│         │  Round 2: Code（LLM，tainted）         │              │
│         │    只给 hypothesis + 接口 spec         │              │
│         └──────────┬────────────────────────────┘              │
│                    │                                            │
│         ┌──────────▼──────────┐                                │
│         │   Contract Gate     │ C1-C10 AST 静态检查              │
│         │   （结构边界）         │ 失败 → RETRY_LLM               │
│         └──────────┬──────────┘                                │
│                    │                                            │
│    WorkspaceMaterializer 复制代码到隔离目录                        │
│                    │                                            │
│         ┌──────────▼──────────┐                                │
│         │  Verification Gate  │ 动态语义验证（subprocess 隔离）    │
│         │  V1~V8 检查清单      │ 轻度失败 → RETRY_LLM             │
│         │                     │ 重度失败 → DISCARD               │
│         └──────────┬──────────┘                                │
│                    │                                            │
│         ┌──────────▼──────────────────────────┐               │
│         │         Experiment Protocol          │               │
│         │                                      │               │
│         │  Canary Check（3 固定实例，veto-only）│               │
│         │         ↓ passed                     │               │
│         │  Screening（17 instances × 2 seeds） │               │
│         │   → A/B: champion vs candidate       │               │
│         │   → 字典序比较：win/loss/tie          │               │
│         │   → 统计：wr, median_delta, CI       │               │
│         │         ↓ pass → READY_VALIDATE      │               │
│         │  Validation（10 instances × 3 seeds）│               │
│         │         ↓ pass → READY_FROZEN        │               │
│         │  Frozen Holdout（18 instances × 3）  │               │
│         │   → 结果永不回流给 LLM               │               │
│         └──────────┬────────────────────────────┘              │
│                    │                                            │
│    Safe Feature Extractor                                       │
│    → DecisionFeatures（纯数值+枚举，无自由文本）                   │
│                    │                                            │
│         ┌──────────▼──────────┐                                │
│         │   Decision Engine   │ 确定性，只读 DecisionFeatures    │
│         │   continue_explore  │                                 │
│         │   queue_validate    │                                 │
│         │   promote ────────►│ _on_promote()                   │
│         │   abandon           │   → 更新 Champion               │
│         └──────────┬──────────┘   → weight optimization        │
│                    │               → mark_all_stale             │
│         写入 SQLite Lineage Registry（append-only）              │
│         写入 _step_history（内存，供下轮 ContextManager 使用）     │
│                    │                                            │
│         FailureRouter（跨层路由）                                 │
│         StagnationDetector（检测僵局模式）                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 组件分工一览

| 组件 | 回答什么问题 | 详细文档 |
|------|------------|---------|
| Scheduler | 下一步推进哪个分支？做什么操作？ | [04](04-branch-design.md) |
| Context Manager | 给 LLM 看什么信息？ | [05](05-proposal-system.md) |
| Lineage / _step_history | LLM 的历史记忆从哪里来？ | [10](10-lineage-registry.md) |
| HypothesisFamily | 是否在同一方向死磕？ | [05](05-proposal-system.md) |
| Contract Gate | 代码结构合规吗？ | [02](02-three-layer-isolation.md) |
| Verification Gate | 代码语义正确吗？ | [02](02-three-layer-isolation.md) |
| Canary | 有没有破坏基本正确性？ | [11](11-canary-regression.md) |
| Experiment Protocol | 算子统计上更好吗？ | [03](03-experiment-protocol.md) |
| Decision Input Guard | 决策有没有被 LLM 文本污染？ | [02](02-three-layer-isolation.md) |
| Decision Engine | 该 promote 还是继续探索？ | [04](04-branch-design.md) |
| Champion Pool | 当前最优算子集合是什么？ | [06](06-champion-pool.md) |
| Weight Optimizer | 当前算子的最优权重分配？ | [06](06-champion-pool.md) |
| Branch 状态机 | 这个探索方向处于哪个阶段？ | [04](04-branch-design.md) |
| FailureRouter | 失败了怎么处理？ | [09](09-failure-router.md) |
| StagnationDetector | Campaign 是否陷入僵局？ | [05](05-proposal-system.md) |
| Lineage Registry | 所有事件如何持久化？ | [10](10-lineage-registry.md) |

---

## 三层控制的核心隔离

```
Creative Layer（LLM，tainted）
  ↓ Contract Gate（结构边界）
  ↓ Verification Gate（语义正确性）
Decision Layer（确定性，只读 DecisionFeatures）
```

LLM 的输出永远是 tainted data。任何影响决策的信息，在进入 Decision Layer 之前都必须经过门控和类型系统的净化。详见 [02](02-three-layer-isolation.md)。

---

## Scion 的认识论定位

不是精确算法（数学保证）与启发式（人类直觉）之间的妥协，而是**算子设计空间上的统计分支定界**——用 LLM 语义推理探索算子设计，用统计显著性替代数学 bound 做剪枝。详见 [07](07-philosophical-position.md)。
