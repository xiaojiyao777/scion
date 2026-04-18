# 06 — Champion Pool、Weight Optimization 与 Bayesian Optimization

## Champion 的定义

**Champion 是池级别，不是算子级别。**

Champion 是整个算子集合（pool）的一个配置赢了，而不是某个算子单独赢了。

```python
ChampionState:
  version: int
  operator_pool: dict[str, OperatorConfig]  # 算子名 → {file, weight}
  code_snapshot_path: str
  code_snapshot_hash: str                    # 含 registry.yaml，weight 变化会改变 hash
  promoted_at: str
```

---

## A/B 评估结构

每次实验是：

```
Champion Solver:   pool = {现有算子集合，权重 w1...wN}
Candidate Solver:  pool = {现有算子集合 ± 变更，权重同}

相同实例 × 相同 seed → 配对比较（win / loss / tie）
```

**字典序比较规则：**
```
Level 1: 业务聚合约束（splits 数）← 最高优先级
Level 2: 成本（cost）
Level 3: 运行效率
```

---

## Promote 的语义

Promote = 把"新的 pool 配置"提升为 champion。

原 pool = {A, B, C}，候选是"新增算子 D" → Promote 后 champion = {A, B, C, D}。
下一次实验的 champion baseline 是 {A, B, C, D}，不是原来的 {A, B, C}。

---

## Weight Optimization：参数层优化

### 两层优化的分工

```
算法层（LLM 驱动）
  → 找更好的算子：有哪些算子？每个做什么？
  → 离散、开放的搜索空间

参数层（BayesianWeightOpt）
  → 给定算子集合，各自概率分配多少最优？
  → 连续、有界的搜索空间 [0.05, 5.0]
```

每次 promote 成功后，参数层接着跑：在新算子组合上找最优权重。

### 为什么需要 Bayesian Optimization

目标函数 f(w) = "权重向量 w 下 solver 的表现"：
- **不可微**：VNS 输出不是解析函数，没有梯度
- **评估代价高**：每次 f(w) = N 个 instance × M 个 seed 的 solver，数十秒

这两个特点决定要用**无梯度、样本高效**的优化方法——Bayesian Optimization。

### Bayesian Optimization 原理

**核心假设**：相近的 w，得分也相近。

```
已观测 n 个点：(w₁,f₁), ..., (wₙ,fₙ)

对未观测的 w*：
  μ(w*) = 加权平均（越近的观测点权重越大）
  σ(w*) = 加权方差（附近观测稀疏 → 不确定性大）

权重计算：exp(-distance(w*, wᵢ)² / h²)

UCB(w*) = μ(w*) + κ × σ(w*)
  → 选"均值高"（exploitation）和"不确定性高"（exploration）之间的平衡点
```

每轮选 UCB 最高的 w 评估，更新代理模型，再选下一个。

**比随机采样好在哪**：不往已知不好的区域浪费，往"可能好但还没探索"的地方钻。

### 实现层次

```
BayesianWeightOptimizer.optimize(current_weights)
  ↓
try:
  → skopt.gp_minimize（GP + acquisition function）
  → scipy.optimize.minimize L-BFGS-B（多次随机重启）← claw 环境有，F2/F3 走这条
  → Pure Python UCB fallback（自实现）← 无依赖时的兜底，F1 走的是这条
```

### 当前配置（Sprint M T5 后）

```
n_initial_random = 8   # 随机探索次数（Sprint M T5 从 4 → 8）
n_iterations     = 16  # UCB 引导次数（Sprint M T5 从 4 → 16）
n_eval_seeds     = 2   # 每个 case 跑 2 个 seed

总评估次数 = 8+16+1(baseline) = 25 次
每次评估 = ~8 个 instance × 2 seed = 16 次 solver 调用
总时间 ≈ 40-50 分钟（claw 环境 + scipy）
```

**为什么从 n=9 升级到 n=25**：F5 实验发现 n=9 时 weight opt 全部失败（0/4 improved），增加采样次数是提升优化器信号质量的直接手段。F6 实验验证：n=25 时合成数据 3/3 improved=1。

**F6 实验证据（v0.2 Sprint F6 新增）**：

| Champion | n_evals | improved | Best Score | 关键权重变化 |
|---|---|---|---|---|
| v2 | 25 | ✅ | 100,000 | swap_orders 0.2→2.91, split_vehicle 0.15→2.88 |
| v3 | 25 | ✅ | 3,300 | swap_orders 0.11→2.93, consolidate_subcat 0.05→1.61 |
| v4 | 25 | ✅ | 3,300 | consolidate_subcat 最高(2.05), chain_consolidate 最低(0.07) |

**v4 最终权重排序（算子贡献度排名）**：

```
consolidate_subcategory  2.0461  ★ 核心算子
change_vehicle_type      0.8422
move_order               0.5538
merge_vehicles           0.5020
swap_orders              0.3458
destroy_rebuild          0.2337
split_vehicle            0.1357
chain_consolidate        0.0686  ← v3 晋升算子，被 v4 取代后贡献度最低
```

关键发现：consolidate_subcategory 权重是 chain_consolidate 的 **30 倍**——即使两者都曾被 promote 过。Solver 应把绝大部分迭代预算分配给 consolidate_subcategory。

---

## Oracle：评估的信任锚点

Oracle 是验证算子输出"业务正确性"的代码，用于 Verification Gate 的 feasibility check 和 objective recomputation。

**Oracle 的特殊性：**
- 由人写 spec + Opus 写实现 + 人审核
- 冻结为 frozen files，搜索过程不可修改
- 这是整个系统的信任锚点——oracle 有 bug，所有实验结论不可信

---

## 已知局限

**Weight opt 只改"怎么用现有算子"，不改"用什么算子"。**

如果某算子设计本身不适合当前 pool 组合（如两个功能重叠），weight opt 无法发现，更不会删除其中一个。改变算子组合结构仍依赖 LLM 的 remove action。

**同步阻塞（v0.3 待修复）：**
weight opt 在 `_on_promote()` 内同步运行，每次 promote 阻塞 campaign 40-50 分钟（n=25 配置下）。
v0.3 方案：async + STALE 机制（详见 08-known-issues-roadmap.md）。

**SPLITS_WEIGHT 信号淹没问题（v0.2 Sprint F6 新增发现）：**

`compute_delta()` 被实验协议和 weight optimization 共用，在生产数据场景（splits≈0）下产生信号淹没：

- 实验协议需要 `SPLITS_WEIGHT=100K`（splits 绝对优先于 cost），用于 win/loss 判定——这是正确的
- Weight optimizer 用同一函数评分时，随机 split 波动（0↔1）= ±100K，淹没 cost 信号 O(1K-10K)，优化器无法找到有意义的权重

F6 实验证据：Group A（splits=23.8，cost 信号 O(100K)）→ 3/3 improved；Group B（splits≈0，SPLITS_WEIGHT=100K）→ 0/1 improved，完全失灵。

**v0.3 规划**：weight optimization 使用独立的 scoring function，不复用 `compute_delta()`，支持 per-problem-spec 配置（详见 08-known-issues-roadmap.md — Weight Opt Scoring Function 独立化）。

---

## v0.3 改进：Weight Opt 结果反馈给 LLM

**当前**：weight opt 结果（各算子优化权重）不进入 LLM 上下文，信息断层。

**价值**：weight opt 量化了每个算子的实际贡献——
- 低权重算子（0.05）= 设计薄弱或与 pool 不互补 → 改进机会
- 高权重算子（4.97）= 承担过多搜索压力 → 深挖或建立互补算子

**注入方式**（弱信号，非指令）：
```
"当前算子贡献估计（weight opt 结果）：
  - destroy_rebuild: 高贡献（4.97）
  - subcat_move: 中等（1.12）
  - move_order: 低贡献（0.05）—— 可能是改进机会"
```

**风险**：加剧 exploitation 偏差（高权重方向被 LLM 过度聚焦）。
**缓解**：与 HypothesisFamily 语义分类配合，形成"弱方向改进"+"未探索方向"双向信号。
