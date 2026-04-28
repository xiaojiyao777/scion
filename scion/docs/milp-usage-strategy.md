# MILP 在 Scion 中的使用策略

*归档日期：2026-04-19*
*状态：设计参考，待 v0.3+ 集成实现*

---

## 背景

Scion 通过 LLM 驱动的 operator search 优化 surrogate solver 上的 champion 算法。
然而，只看"champion vs baseline"的相对改进，**无法回答"离真实最优还差多远"**。

MILP exact solver (`surrogate/milp_solver.py`) 给出问题的**数学下界**，可以量化
每个 champion 的**最优性上界保证（optimality gap）**。

本文档记录：何时接 MILP、下界有多可信、大规模怎么办、怎么集成进 Sprint 流程。

---

## 核心定位：MILP 是 benchmark provider，不是 Scion 主 evaluator

MILP 在 Scion v0.3+ 中的职责应明确为：**外部 benchmark provider / optimality calibration layer**。
它回答的是：
- 当前 champion 在小规模上是否已达到 exact optimum
- 当前 champion 在中规模上距离已知 lower bound 还有多远
- 不同 champion 版本的 gap 是否在收敛

它**不**负责：
- 替代 Scion 主循环里的 surrogate evaluator
- 参与每轮 screening / validation / frozen 的常规打分
- 作为日常搜索内环的一部分频繁调用

原因：
- surrogate evaluator 解决的是**高频、低成本、可扩展**的搜索反馈
- MILP provider 解决的是**低频、高价值、带最优性解释**的外部校准
- 两者服务的决策层不同，不能混用

**结论**：Scion 主协议保持不变，MILP 以旁路 benchmark provider 的形式挂到 champion 晋升 / sprint 总结等关键节点。

---

## 核心洞察：什么是"下界"

### 两种下界，两种可信度

#### A. LP 下界（HiGHS B&B 维护）

- **永远是数学上严格有效的下界** —— 定理保证
- 即便 timeout，HiGHS 返回的 `lower_bound` 也是 **valid lower bound**
- `gap = (incumbent - LB) / LB` 是**严格的 optimality gap**
- **LB 不会因 timeout 变得"不可信"**，只是可能偏松（真实 LB 更大）

#### B. Optimal（精确最优）

- 只有 HiGHS 显式返回 `status=Optimal` 且 `gap=0` 才是
- timeout 不会返回 Optimal
- 实验中大部分情况只能拿到 B，拿不到 A + gap=0

### gap 的正确解读

```
LB ≤ 真实最优 ≤ champion_f1
gap = (champion_f1 - LB) / LB
```

- `gap=5%` → champion **最多**比真实最优差 5%（可能更好）
- `gap=30%` → champion 最多差 30%，但也**可能只差 3%**——是 LB 太松，**不是** champion 差
- **gap 是"champion 质量的上界保证"，不是"champion 的绝对质量"**

---

## 使用时机

### 推荐顺序（价值/成本）

| 时机 | 价值 | 成本 | 推荐 |
|---|---|---|---|
| **Frozen testing 后**（champion 晋升新版本）| ⭐⭐⭐⭐⭐ | 中 | ✅ 主要触发点 |
| **Campaign 结束**（sprint 终局版）| ⭐⭐⭐⭐ | 低 | ✅ 写进报告 |
| **Weight opt 后** | ⭐⭐ | 高 | ❌ 算子结构未变，LB 不变 |
| **每轮实验** | ⭐ | 极高 | ❌ 浪费 |

### 为什么 weight opt 不用跑 MILP

- Weight opt 只改算子选择概率，**champion 算子代码没变**
- MILP 下界由**问题实例**决定（instance 决定 LB），和 surrogate 算子无关
- MILP 上界由**champion solution** 决定，但 weight opt 产生的 solution 在同一批算子内搜索
  不会显著超越 operator 能达到的 Pareto 前沿
- 每次 weight opt 跑 MILP 是重复劳动

### 为什么 champion 晋升时值得跑

- 晋升意味着**算子集合变了**（新增 / 修改算子）
- 新 champion 的 f1/f2 真实改进 → 值得问 MILP "现在 gap 多少"
- 如果连续几次晋升后 gap 已经很小（<5%），是 **"可以停止 Sprint"** 的信号

---

## 分规模策略（关键：MILP 大规模跑不动）

MILP 单实例求解时间随规模超线性增长。经验区间：

| 规模 | MILP 1200s 预期 | 策略 |
|---|---|---|
| ≤40 orders | Optimal 或 gap<5% | ✅ MILP warm-start |
| 40-100 orders | gap 10-30% | ✅ MILP warm-start，接 gap |
| 100-500 orders | 1h 不收敛 | ❌ MILP 放弃，用 LP relax |
| >500 orders | LP 也吃力 | 闭式下界 |

### 分层下界方法

#### Layer 1 — MILP with warm start（小中规模首选）

- 用 baseline-v1 champion 作 warm start
- 时间预算：300-1200s
- 收敛则拿精确最优，不收敛则拿 `(incumbent, LB, gap)` 三元组
- **实现**：v0.3 CC 任务进行中（2026-04-19）

#### Layer 2 — LP relaxation（中大规模）

- 只跑 LP 松弛，不跑整数部分
- 几秒到几十秒给下界
- **LP 下界 ≤ MILP 下界 ≤ 真实最优**，给宽松但即时的 LB
- 适用 100-500 规模
- **实现**：待 v0.3+ 排期

#### Layer 3 — 闭式下界（任意规模）

利用问题结构推导：

```python
# f1 下界: 激活的 subcategory 数（每 subcat 至少 1 辆车）
f1_lb = n_active_subcats

# f2 下界: 总 pallet / 最大容量 × 最便宜车型成本
f2_lb = ceil(total_pallets / max_capacity) * cheapest_cost
# 考虑 hazmat 必须用 HQ40_DG:
f2_lb_refined = f2_lb + hazmat_pallets * (hq40_dg_cost - hq40_cost) / hq40_capacity
```

- 瞬时计算（<1ms）
- **通常比 LP relaxation 松**（闭式忽略多维耦合）
- 对 `f1 splits` 特别紧（几乎等于真实最优）
- **实现**：待 v0.3+ 排期（`surrogate/milp_quick_bound.py`）

---

## Sprint 集成架构（推荐）

```
Scion Campaign
├── Sprint 进行中: 不跑 MILP（贵）
├── Champion v2 晋升: MILP 300s @ 小规模 → 记 gap
├── Champion v3 晋升: MILP 300s @ 小+中规模 → 记 gap
├── Champion v4 晋升: ...
├── Campaign 结束:
│   ├── 小规模 (≤40): MILP 1200s → 尽量 Optimal
│   ├── 中规模 (40-100): MILP 1200s → LB + gap
│   └── 大规模 (>100): LP relax + 闭式下界
└── Sprint Report:
    "Champion vN: small_gap=X%, mid_gap≤Y%, large_vs_greedy=+Z%"
```

### 何时可以停 Sprint

- **gap<5% @ 小规模** → champion 已接近最优，继续 LLM 探索收益递减
- **gap>20% @ 小规模** → 还有大空间，继续探索
- **gap 在 5 次晋升内没收窄** → 问题可能已经卡死，换方向或换问题

---

## 数据字段规范（实验记录）

每次跑 MILP benchmark，记录。注意这里记录的是 **benchmark provider 输出**，不是主 evaluator 输出。

### 推荐 canonical schema

```json
{
  "instance": "instance_v4_scr_s03.json",
  "n_orders": 39,
  "champion_version": "v3",
  "provider": "milp",
  "solver": "HiGHS 1.14",
  "warm_start_f1": 13,
  "warm_start_f2": 43200,
  "milp_status": "optimal",
  "milp_exact": true,
  "milp_verified": true,
  "milp_f1": 11,
  "milp_f2": 41300,
  "milp_lb_f1": 11,
  "milp_lb_f2": 41300,
  "gap_f1_pct": 0.0,
  "gap_f2_pct": 0.0,
  "elapsed_s": 1200,
  "champion_vs_milp_delta_f1": 2,
  "champion_vs_milp_delta_f2": 1900,
  "notes": "exact on small instance"
}
```

### 字段语义

- `provider="milp"`：显式声明这是 benchmark provider 结果
- `milp_status`：求解状态（`optimal` / `feasible` / `timeout` / `no_feasible` / `error`）
- `milp_exact`：仅当 exact optimum 被证明时为 `true`
- `milp_verified`：仅当 incumbent 通过 strict extract + oracle verification 时为 `true`
- `milp_f1` / `milp_f2`：**对外统一口径**的 benchmark 值，直接与 champion `(f1, f2)` 比较
- `milp_lb_f1` / `milp_lb_f2`：已证明下界；timeout 时允许只有部分 lower bound
- `champion_vs_milp_delta_*`：champion 相对 benchmark incumbent 的差值，用于 sprint report

### 口径约束

- **只认 `milp_f1` / `milp_f2`，不认 phase-1 内部 raw `sum_alpha`**
- **只把 `milp_verified=true` 的 incumbent 纳入正式 benchmark**
- **timeout case 必须保留 LB / gap 语义，不得伪装成 exact**

### 报告口径

- **严谨**: `"Champion v3 gap ≤ 10% on f1, ≤ 2.7% on f2 (instance s03)"`
- **进度**: 在 `scion/docs/sprint-*.md` 里追踪 `gap over time`
- **警告**: 如果 gap 变大（champion 变差），说明退化需调查

---

## 常见坑

### 1. 把 gap 当 champion 的"真实差距"
`gap=30%` 可能只是 LB 太松，不是 champion 真的差 30%。

**修正**：只在 `gap<10%` 时用"离最优 ≤X%"表述；更大 gap 只说"valid upper bound on gap"。

### 2. 每次 weight opt 都跑 MILP
浪费 —— LB 不变。

**修正**：只在 champion **晋升**（代码变化）时跑。

### 3. 用同一个 instance 反复跑
MILP 单 instance 的 LB **不因多次跑而改善**（除非改了模型）。

**修正**：多 instance 求平均 gap，不是同 instance 跑多次。

### 4. 忽略 warm start 无效场景
如果 champion 不可行（违反 oracle）→ warm start 会被 HiGHS 拒绝 → fallback 到冷启动。

**修正**：`build_warmstart_values` 前先 `oracle.check_feasibility(champion, instance)`。

### 5. Phase 2 warm start 错用
Phase 2 固定 `f1 = f1*`（phase 1 最优），champion 的 f1 > f1* → warm start 在 phase 2 不可行。

**修正**：只在 phase 1 用 warm start；phase 2 留 TODO。

---

## v0.3+ 集成 Roadmap

- [x] MILP exact solver（v0.2 完成）
- [x] HiGHS 切换（Sprint M, 2026-04-18）
- [ ] **MILP warm start from champion**（CC 开发中, 2026-04-19）← 当前
- [ ] Scion 主循环 hook: champion 晋升 → 自动跑 MILP 300s → 写入 research log
- [ ] `surrogate/milp_quick_bound.py` 闭式下界
- [ ] `surrogate/milp_lp_relaxation.py` LP 松弛下界
- [ ] Sprint report 自动化: `gap over time` 图 + champion 质量追踪

---

## 相关文档

- `scion/docs/milp-model.md` — MILP 数学模型
- `scion/docs/metrics-guide.md` — wr/md/gap 指标详解
- `scion/reviews/v0.3-design-review-report.md` — v0.3 评审（含 MILP ground truth 章节）
- `scion/postmortem/` — Sprint M HiGHS 切换纪要
