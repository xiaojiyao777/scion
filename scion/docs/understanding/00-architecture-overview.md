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

---

## Scion 的边界

### 定位：组合优化领域的算法自动改进框架

OR（运筹学）的范围很广——随机规划、排队论、网络流、线性规划都属于 OR。Scion 的初始定位在**组合优化**这个子领域，原因：

1. **问题结构明确**：决策变量离散，目标函数和约束可以精确定义，适合用 oracle 做形式化验证
2. **启发式算法是主导范式**：NP-hard 问题在实际规模下无法用精确算法，VNS/ALNS/SA/GA 等邻域搜索是业界标配——这正是 Scion 改进的对象
3. **改进可量化**：solution quality 有明确指标（splits、cost、time），统计比较有意义
4. **实际价值直接**：BigBOSS 在工作中直接使用和验证，VRP 变种是生产中的真实问题

**Scion 不直接针对**：
- 连续优化（已有成熟梯度方法）
- 线性规划（精确算法已经很好）
- 随机规划 / 模拟优化（目标函数评估更复杂，验证机制需要重新设计）

---

### Scion 是什么

- **组合优化算法的自动改进框架**
- **方法论**：LLM 语义推理 + 统计实验验证，假设驱动，可追溯
- **实验基础设施**：严格控制有效性（三层隔离 + 三级验证 + frozen holdout）
- **知识生产回路**：LLM 理解 → 可检验假设 → 实证验证 → 晋升进 champion

### Scion 不是什么

- **不是精确算法**：无最优性保证，只有统计显著性
- **不是数据生成工具**：benchmark 实例需人工设计或从生产提取
- **不是部署系统**：promote 的算子是候选，需生产 A/B 才能上线
- **不是通用 agent 框架**：专为算法改进场景设计

### 人在回路的边界

```
人负责：问题定义 / oracle 设计 / 审核最终结果 / 生产部署决策
Scion负责：探索循环 / 实验执行 / 统计判断 / lineage 记录
```

人不参与每轮迭代，但人的判断是系统信任锚点——oracle 是人写的规范，不是 Scion 自生成的。

### 版本边界

```
v0.x：VNS 算子接口固定，在算子设计空间内搜索（当前）
v1.x：扩展搜索空间（VNS 结构层、weight 更新机制）
v2.x：支持更广的组合优化范式（调度、装箱、分配等）
v3.x：算法无关化，支持神经 CO / RL policy 改进
```
