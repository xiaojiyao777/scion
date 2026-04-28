# Scion 实验流程速查手册

*Date: 2026-04-26*
*面向：需要理解 Scion 实验输出的读者*

---

## 1. Campaign 基本概念

**Campaign** 是一次完整的自动化搜索实验。它包含多个 **Round**（轮次），每轮尝试一个新的算子改进。

**Champion** 是当前最优的 solver 配置（算子池 + 权重）。所有新算子都与 champion 做 A/B 对比。

**Branch** 是一个探索方向。一个分支内可以迭代多个假设。分支被 abandon 后会创建新分支。

---

## 2. 每轮（Round）做什么

```
Round N:
  1. LLM 生成假设（Round 1 of Proposal）
  2. LLM 生成代码（Round 2 of Proposal）
  3. Contract Gate：结构检查（文件白名单、AST、import）
  4. Verification Gate：语义检查（V1-V9，含确定性检测）
  5. 实验评估：Screening → Validation → Frozen Holdout
  6. Decision Engine：基于统计结果决定 promote / abandon / 继续
```

注意"Round 1/Round 2 of Proposal"和"Campaign Round N"是不同的概念：
- **Proposal 的两轮**：先生成假设（what to change），再生成代码（how to change）
- **Campaign 的轮次**：每轮跑完整个上述流程

---

## 3. 谁控制什么

| 谁决定 | 决策内容 |
|---|---|
| **框架（确定性代码）** | 创建/销毁分支、分支状态转换、选哪个分支执行、是否 promote/abandon、实验协议执行、调度优先级 |
| **LLM（创造性提案）** | 在给定分支上提出什么假设、生成什么代码 |

LLM 不参与分支管理、实验调度、晋升/淘汰决策。它只看到 ContextManager 构造的上下文，提出一个提案。框架负责其余一切。

这是 Scion 的核心设计原则：**确定性逻辑用代码，创造性推理用 LLM。**

---

## 4. 三级实验协议

每个通过 Verification 的算子，需要经过三级 A/B 评估才能晋升：

| 阶段 | 目的 | 实例规模 | 通过条件 | 失败后果 |
|---|---|---|---|---|
| **Screening** | 快速粗筛 | 小+中（m01-m06, l01-l04） | wr ≥ 2/3, md > 0 | 继续迭代或 abandon |
| **Validation** | 正式验证 | 大+超大（l01-l04, x01-x02） | wr ≥ 2/3, CI > 0 | abandon |
| **Frozen Holdout** | 最终确认 | 超大+巨大（x01-x02, xx01-xx02） | CI > 0, canary pass | promote 或 reject |

每个阶段使用不同的 benchmark 实例和 seed 集合，防止信息泄漏。

---

## 5. 什么是"一对"实验

一对（pair）是一次 A/B 对比：

```
输入：一个 instance（如 fro_x01.json，含 400 个订单）+ 一个 seed（如 256）

  Champion solver（当前最优配置）
    → 跑 200 轮 VNS 迭代
    → 得到 objective A: splits=164, cost=477300

  Candidate solver（champion + 新算子）
    → 跑 200 轮 VNS 迭代（同 seed，确保可比）
    → 得到 objective B: splits=125, cost=441700

比较（字典序）：
  splits: 125 < 164 → candidate 胜
  结果：win, delta = (164-125) × 100000 = 3,900,000
```

**耗时**取决于实例规模：
- 小实例（54 订单）：每对 ~3 秒
- 中实例（100 订单）：每对 ~5 秒
- 大实例（400 订单）：每对 ~30 秒
- 巨大实例（675 订单）：每对 ~60 秒

---

## 6. 关键统计指标

| 指标 | 含义 | 晋升门槛 |
|---|---|---|
| **wr (win_rate)** | candidate 胜出的比例（跨所有 case×seed 对） | ≥ 2/3 |
| **md (median_delta)** | delta 的中位数，衡量改进幅度 | > 0 |
| **CI (bootstrap CI low)** | 95% 置信区间下界 | > 0 |

delta 的计算：`splits_weight × Δsplits + Δcost`，其中 `splits_weight = 100,000`。
这意味着减少 1 个 split 等价于节省 100,000 的成本。

---

## 7. Weight Optimization

Promotion 后可以执行算子权重优化。当前 v0.3 支持两种模式：

| 模式 | 适用场景 | 语义 |
|---|---|
| `sync` | 当前 2-core 服务器、正式 v0.3 实验 | promote 后阻塞直到 weight optimization 完成并落表，再继续下一轮结构搜索 |
| `async` | 核心数充足的机器 | promote 后后台优化权重，主搜索继续推进 |

正式 v0.3 validation 使用：

```bash
--weight-opt-execution sync
```

`status.json` 中的 `weight_optimization.runs[]` 会记录：

- `mode`
- `phase`
- `n_cases`
- `n_seeds`
- `n_operators`
- `total_evaluations`
- `completed_evaluations`
- `estimated_solver_runs`
- `improved`
- `elapsed_minutes`

SQLite 检查：

```bash
sqlite3 <campaign>/scion.db \
  'select champion_version,n_evaluations,baseline_score,best_score,improved from weight_optimizations;'
```

## 8. 决策结果

| 决策 | 含义 |
|---|---|
| **expand_screening** | screening 结果不明确（wr 接近阈值），扩大样本量重新评估 |
| **queue_validate** | screening 通过，进入 validation 阶段 |
| **queue_frozen** | validation 通过，进入 frozen holdout 最终确认 |
| **promote** | frozen 通过，新算子晋升为 champion |
| **abandon** | 任一阶段失败，放弃当前假设 |

---

## 9. 日志阅读指南

典型日志条目：

```
# LLM 生成假设
Branch xxx R1 hypothesis: locus=vehicle_level action=create_new target=operators/xxx.py

# Verification 失败
Branch xxx: verification failed (heavy): V8_nondeterminism

# 实验对结果
Pair instance_v3_scr_m01.json seed=42: cmp=win delta=700000.0 decisive=business_aggregation
  cand(splits=5 cost=39300) champ(splits=12 cost=42800)

# 阶段决策
Branch xxx: features wr=1.0 md=900000.0 stage=screening → decision=queue_validate

# 晋升
Promoted branch xxx to champion v2

# 同步权重优化
Champion v2: running weight optimization synchronously
Synchronous weight opt complete for champion v2 (49.9 min) — no improvement
```

## 10. 当前正式实验

v0.3 formal validation：

```text
~/research/scion-experiments/v03-final-sync-12campaign-20260426/
```

队列日志：

```text
~/research/scion-experiments/v03-final-sync-12campaign-20260426/formal_queue.runner.log
```

健康检查：

```bash
pgrep -af 'v03-final-sync-12campaign-20260426|run_validation_campaign.py'
tail -n 40 ~/research/scion-experiments/v03-final-sync-12campaign-20260426/formal_queue.runner.log
```

---

*本文档不包含架构设计细节。详见 `design/scion-architecture-v3.md`。*
