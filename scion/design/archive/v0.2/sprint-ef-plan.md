# Sprint E & F 重构方案（正式版）

*Date: 2026-04-11*
*输入: v0.2-development-plan §6 + cc-design-reference-v2 §9 + uuid-fix-validation-report*
*Status: 待 BigBOSS 审核*

---

## 0. 重构背景

原 Sprint E 是"Search-efficiency polish"（9 个 task），定位为 MVP 后的打磨。但经过：

1. **uuid 根因发现 + postmortem**：暴露了框架诊断链、ContractGate、实验后分析的系统性缺陷
2. **CC 源码深度分析**：16 份报告 + 综合对照，识别出 5 个 P0 + 16 个 P1 改进点
3. **验证实验**：确认 uuid 修复有效（V8 归零），但同时暴露了 hypothesis 同质化（4/4 subcategory 相关）、weight opt 权限 bug、cache hit rate 低等问题

Sprint E 的范围需要从"打磨"扩展为"修核心链路 + 提搜索效率 + 补工程健壮性"。Sprint F 作为端到端验证，需要 Sprint E 的产出作为前置。

---

## 1. Sprint E — 重构后的完整方案

### 1.1 Sprint E 目标（一句话）

> **修掉阻塞实验质量的核心链路问题，提升搜索多样性，让 Sprint F 的对照实验能产出可信结论。**

### 1.2 分阶段执行

#### E1: 阻塞项修复（必须先做）
*预计 1-2 天*

| Task | 内容 | 来源 | 为什么 P0 |
|---|---|---|---|
| **T-fix-weightopt** | 修复 weight optimization permission bug（champion snapshot 只读权限） | 验证实验发现 | Sprint F 的 F2/F3 实验直接依赖参数搜索正常工作 |
| **T21** | ContractGate AST 非 rng 随机源扫描 | CC ref P0-5, postmortem #001 | 从源头拦截 uuid 类问题，防止 Sprint E 后续实验出现新的非确定性 bug |

E1 DoD：weight opt 在测试中正常运行 + ContractGate 能拦截 `uuid.uuid4()` 调用

#### E2: 搜索多样性（核心价值）
*预计 2-3 天*

| Task | 内容 | 来源 | 依赖 |
|---|---|---|---|
| **T07** | HypothesisFamily tracking（机制标签 + 证据计数） | 原 Sprint E + CC ref P0-3 | 无 |
| **T08** | Strategy-shift guidance（连续失败族 → 强制换方向 + 探索覆盖度注入） | 原 Sprint E + CC ref P0-3 | T07 |
| **T26** | 记忆分类学 + 正向记录（记住"什么有效"，防过度保守） | CC ref P1-11/12 | T07 |

E2 DoD：在一次短 campaign（5 轮）中，action/locus 覆盖度 ≥ 2 种

#### E3: 实验基础设施
*预计 1-2 天*

| Task | 内容 | 来源 | 依赖 |
|---|---|---|---|
| **T05** | Frozen holdout 扩充（更多 case、更大规模跨度） | 原 Sprint E | 无 |
| **T11** | Screening set 重平衡（混入 large case） | 原 Sprint E | 无 |
| **T06** | Observability polish（cache hit rate、failure breakdown、family coverage 纳入 report） | 原 Sprint E + CC ref P1-7 | 无 |
| **T09** | Richer case feedback rendering（decisive objective 可读化） | 原 Sprint E | 无 |
| **T10** | Champion baseline hints（告诉 LLM 某 case 上 splits 已经是 0） | 原 Sprint E | 无 |

E3 DoD：新 split_manifest 和 seed_ledger 更新，report 中可见 family 覆盖度

#### E4: 错误链路改进
*预计 1-2 天*

| Task | 内容 | 来源 | 依赖 |
|---|---|---|---|
| **T19** | ProposalEngine 前置校验层（Pydantic validateInput，格式错误不进执行路径） | CC ref P0-1 | 无 |
| **T20** | 降级恢复（Hypothesis 成功但 Code 失败时返回 hypothesis-only） | CC ref P0-4 | 无 |
| **T25** | StagnationDetector（oscillation/plateau/collapse 检测） | CC ref P1-4 | 无 |

E4 DoD：Proposal 格式错误不再触发 LLM 重试 + 停滞检测能在测试中正确触发

#### E5: 分析工具（Sprint F 前置）
*预计 1 天*

| Task | 内容 | 来源 | 依赖 |
|---|---|---|---|
| **T24** | `scion postmortem` CLI（失败模式自动抽样 + 代码级根因模板） | CC ref P1-10, postmortem #001 教训 1 | T06 的 artifact 完整性 |

E5 DoD：对验证实验的 campaign_summary.json 运行 `scion postmortem`，输出可读报告

### 1.3 可选（如时间允许）

| Task | 内容 | 优先级 |
|---|---|---|
| T22 | LLM Client 分级重试 | P1 |
| T27 | 主循环 max_tokens 截断恢复 | P1 |
| T29 | 熔断器模式（连续失败保护） | P1 |
| T15b | Bayesian optimizer | P1（依赖 F3 证明 random/local 不够用） |
| T17b | CLI/report polish | P2 |

### 1.4 不做的（明确排除）

- ❌ ProposalEngine 多 content block 序列化重构（P0-1 中的完整方案）— 改动太大，留给 v0.3
- ❌ Campaign 中期停滞诊断（T23）— 需要更多实验数据确认 trigger 条件
- ❌ 工具结果外包到磁盘（T28）— 当前求解器输出不大，不是瓶颈

### 1.5 Sprint E 验收标准

- [ ] Weight optimization 正常工作（promote 后自动触发，能产出 baseline vs optimized 对比）
- [ ] ContractGate 拦截 uuid.uuid4() 等非 rng 随机源
- [ ] HypothesisFamily tracking 正常记录，strategy guidance 能注入上下文
- [ ] Frozen holdout 扩充完成，screening 含 large case
- [ ] 跑一次短 campaign（5 轮）验证以上所有功能联动
- [ ] `scion postmortem` CLI 可用

---

## 2. Sprint F — 端到端完整验证分析

### 2.1 Sprint F 目标

> **通过三组对照实验，回答 v0.2 的四个研究问题，产出可论文化的 experiment note。**

### 2.2 三组对照实验

| 实验 | 配置 | 目的 |
|---|---|---|
| **F1** | 结构搜索 + 均匀权重 | 基线：结构搜索 alone 的收益 |
| **F2** | 结构搜索 + promote 后参数优化 | 完整 v0.2 流程 |
| **F3** | 固定基线算子池 + 只做参数优化 | 隔离参数搜索的收益 |

每个实验：max_rounds=15, claude-opus-4-6

### 2.3 四个研究问题

| # | 问题 | 数据来源 |
|---|---|---|
| Q1 | 结构搜索 alone 的收益？ | F1: champion v1 vs final champion |
| Q2 | 参数搜索 alone 的收益？ | F3: 均匀权重 vs 优化权重 |
| Q3 | 叠加收益是否超线性？ | F2 vs F1 + F3 |
| Q4 | 算子收益来自"存在"还是"高频调用"？ | F2 vs F3 对比 |

### 2.4 分析要求

每个实验结束后用 `scion postmortem` + 人工审核：
- 每类成功/失败追根因
- 区分"框架引导的"vs"偶然的"
- HypothesisFamily 覆盖度报告
- 对比三组实验的 objective 改善幅度

### 2.5 产出物

- 完整实验报告（每轮根因追溯）
- 论文级 experiment note（四个问题的数值回答）
- Postmortem（如有异常）
- 原始数据归档（campaign_summary.json + SQLite）

### 2.6 前置条件

Sprint E 的 DoD 全部通过，特别是：
- Weight optimization 正常工作
- HypothesisFamily tracking 正常工作
- Frozen holdout 已扩充
- `scion postmortem` CLI 可用

### 2.7 预计执行时间

```
Day 1: F1 实验 + 分析（~2h）
Day 2: F3 实验 + 分析（~1h）
Day 3: F2 实验 + 分析（~2.5h）
Day 4: 综合对比 + 写报告 + experiment note
```

---

## 3. 总体路线图

```
当前位置
    │
    ▼
Sprint E（~7-10 天）
  E1: 阻塞项修复（1-2d）     ← weight opt bug + AST 扫描
  E2: 搜索多样性（2-3d）     ← family tracking + guidance + 正向记忆
  E3: 实验基础设施（1-2d）    ← frozen 扩充 + screening 重平衡 + feedback
  E4: 错误链路改进（1-2d）    ← 前置校验 + 降级恢复 + 停滞检测
  E5: 分析工具（1d）         ← postmortem CLI
    │
    ▼
Sprint F（~4 天）
  F1: Structure-only 实验      ← Q1
  F3: Parameter-only 实验      ← Q2
  F2: Structure + Parameter    ← Q3, Q4
  综合分析 + experiment note
    │
    ▼
v0.2 完成 🎉
```

---

*本方案合并了三个输入：原 Sprint E 的 9 个 task（保留全部有价值的）、CC 综合分析的 11 个新 task（筛选后纳入 7 个）、验证实验暴露的 1 个阻塞项。Sprint F 的对照实验设计确保 v0.2 的结论不只是"能跑通"，而是"能回答研究问题"。*
