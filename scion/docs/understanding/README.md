# Understanding Scion — 系统性理解指南

*整理自 2026-04-12 深度讨论，面向任何想理解 Scion 框架的读者。*

---

## 文档目录

| 文件 | 内容 |
|------|------|
| [01-what-is-scion.md](01-what-is-scion.md) | Scion 是什么、解决什么问题、名字含义 |
| [02-three-layer-isolation.md](02-three-layer-isolation.md) | 三层隔离：Contract Gate / Verification Gate / Decision Input Guard |
| [03-experiment-protocol.md](03-experiment-protocol.md) | 三级实验协议：Screening / Validation / Frozen Holdout |
| [04-branch-design.md](04-branch-design.md) | 分支设计：状态机 / workspace / Stale reconcile |
| [05-proposal-system.md](05-proposal-system.md) | 两轮 Proposal：Hypothesis → Code |
| [06-champion-pool.md](06-champion-pool.md) | Champion Pool / 权重优化 / A/B 评估 |
| [07-philosophical-position.md](07-philosophical-position.md) | Scion 的认识论定位：精确算法 vs 启发式 vs LLM 语义推理 |
| [08-known-issues-roadmap.md](08-known-issues-roadmap.md) | 当前已知问题 / v0.3 路线图 |
| [09-failure-router.md](09-failure-router.md) | Failure Router：四层分类 / 路由动作 / 设计缺口 |
| [10-lineage-registry.md](10-lineage-registry.md) | Lineage Registry：持久化审计层 / 双重角色 / 事后分析 |

## 快速入口

**第一次了解 Scion** → 从 [01](01-what-is-scion.md) 开始顺序读

**理解实验设计** → 重点看 [02](02-three-layer-isolation.md) + [03](03-experiment-protocol.md)

**理解搜索机制** → 重点看 [04](04-branch-design.md) + [05](05-proposal-system.md)

**思考框架价值** → 直接看 [07](07-philosophical-position.md)
