# Sprint F 设计 — v0.2 端到端完整验证分析

*Date: 2026-04-11*
*Parent: cc-design-reference-v2.md §9, v0.2-development-plan.md*
*Status: Draft — 待 Sprint E 完成后启动*

---

## 1. 定位

Sprint F 不是"再跑一次 campaign 看看能不能 promote"。它是 v0.2 作为**研究平台**的完整验证：

> **跑完 → 分析为什么 → 回答研究问题 → 产出可论文化的 experiment note**

Sprint D 证明了"能跑通"，Sprint E 提升了搜索效率和工程健壮性，Sprint F 要证明的是**结论可信、可追溯、可复现**。

---

## 2. 验收标准（Sprint F 成功的定义）

### 2.1 必须达成

1. **完整 campaign 闭环**：结构搜索 → promote → 参数搜索 → 对比（weight optimization 正常工作）
2. **零 V8_nondeterminism 失败**（uuid 修复回归验证）
3. **每类失败/成功都有代码级根因分析**（用 T24 的 postmortem 流程）
4. **回答 v0.2 设计文档 §8.4 的四个研究型问题**（见 §4）

### 2.2 期望达成

5. 假设多样性：至少覆盖 2 种 action（create_new + modify/remove）
6. 假设多样性：至少覆盖 2 种 locus（vehicle_level + order_level）
7. HypothesisFamily tracking 产出可用的探索覆盖度报告
8. StagnationDetector 至少触发一次有意义的信号

### 2.3 产出物

- `scion/docs/v02-sprint-f-experiment-report.md` — 完整实验报告
- `scion/docs/v02-sprint-f-research-note.md` — 论文级 experiment note
- `scion/postmortem/002-sprint-f-*.md` — 每类异常的 postmortem（如有）
- campaign_summary.json + SQLite lineage — 原始数据归档

---

## 3. 实验设计

### 3.1 对照实验矩阵

| 实验 | 配置 | 目的 |
|---|---|---|
| **F1: Structure-only** | 结构搜索 + 均匀权重（不做参数优化） | 基线：结构搜索 alone 的收益 |
| **F2: Structure + Parameter** | 结构搜索 + promote 后自动参数优化 | 完整 v0.2 流程 |
| **F3: Parameter-only** | 固定基线算子池 + 只做参数优化 | 隔离参数搜索的独立收益 |

### 3.2 每个实验的 campaign 配置

```yaml
max_rounds: 15          # 比验证实验多，给足探索空间
solver_timeout: 300s
screening_n: 20
validation_n: 18
frozen_n: 12
model: claude-opus-4-6
```

### 3.3 分析要求（每个实验结束后必做）

1. **Aggregate 统计**：总轮数、V-check 通过率、promote 次数、总耗时、LLM 调用/cost
2. **每轮根因追溯**：
   - 成功的：为什么成功？是框架引导还是偶然？代码质量如何？
   - 失败的：失败在哪一步？根因是什么？是可避免的吗？
3. **HypothesisFamily 覆盖度报告**：action/locus/mechanism 分布
4. **对比分析**：F1 vs F2 vs F3 的 objective 改善幅度

---

## 4. 四个研究型问题（v0.2 设计文档 §8.4）

Sprint F 必须能回答：

### Q1: 结构搜索 alone 的收益是多少？
- 数据来源：F1 实验
- 度量：champion v1 vs final champion 的 objective delta（across frozen holdout）
- 分解：哪些算子贡献了多少 splits 减少

### Q2: 参数搜索 alone 的收益是多少？
- 数据来源：F3 实验
- 度量：均匀权重 vs 优化权重的 objective delta
- 分解：哪些算子的权重变化最大，变化方向是否符合直觉

### Q3: 结构 + 参数叠加后收益是多少？
- 数据来源：F2 实验
- 度量：baseline vs final (structure + optimized weights)
- 分析：是否超线性（1+1>2）？如果是，为什么？

### Q4: 某类算子的收益主要来自"存在"还是"被高频调用"？
- 数据来源：F2 实验 + F3 实验对比
- 度量：在均匀权重下的 win_rate vs 在优化权重下的 win_rate
- 如果优化权重显著提高某算子的权重且 win_rate 跟着涨 → "高频调用"贡献大
- 如果均匀权重下 win_rate 就很高 → "存在"本身就够了

---

## 5. 前置条件

Sprint F 启动前必须确认：

- [ ] Sprint E 全部 DoD 通过
- [ ] Weight optimization permission bug 已修复（当前阻塞 F2/F3）
- [ ] T24 postmortem CLI 可用
- [ ] T25 StagnationDetector 可用
- [ ] T07/T08 HypothesisFamily tracking 可用
- [ ] 新的 split_manifest 和 seed_ledger 已更新（如 T05 扩展了 frozen set）

---

## 6. 执行计划

```
Day 1: F1 实验（Structure-only）
  → 跑 campaign（~1h）
  → 根因分析（~1h）
  → 初步报告

Day 2: F3 实验（Parameter-only）
  → 跑 weight optimization（~30min）
  → 对比分析
  → 更新报告

Day 3: F2 实验（Structure + Parameter）
  → 跑完整 campaign + auto weight opt（~1.5h）
  → 根因分析（~1h）

Day 4: 综合分析 + 写报告
  → 回答四个研究问题
  → 写 experiment note（论文级）
  → 更新 MEMORY.md / wiki
```

---

## 7. 与论文化的衔接

Sprint F 的 experiment note 应能直接作为论文 §4 Experiments 的素材：

- **实验设置**：三组对照实验，配置参数，benchmark 实例规模
- **主要结果**：四个研究问题的回答，含数值证据
- **消融分析**：结构 vs 参数的独立/叠加贡献
- **Case Study**：一个成功的 promote 全程追溯（hypothesis → code → verification → protocol → promote）
- **失败分析**：一个有代表性的失败 case 的根因追溯
- **框架有效性证据**：V-check 拦截统计、三级协议的 false positive/negative 率

---

*Sprint F 是 v0.2 的最终验证。通过后 Scion 从"能跑"升级为"能产出可信的研究结论"。*
