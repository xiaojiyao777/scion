# Scion Framework — v0.2 Parameter Layer Search Design

*Date: 2026-04-08*
*Parent: scion-architecture-v3.md §19/§20*
*Branch: v0.2-dev*
*Status: Design — Draft*

---

## 0. v0.2 目标

在 v0.1 结构级搜索（算子 create/modify/remove）基础上，增加**参数层搜索**。

蓝图原文（architecture-v3 §19）：
> v0.2 参数层：外层 LLM 探索结构 + 内层贝叶斯优化参数（算子权重等）。两层嵌套搜索是核心差异化点。

蓝图原文（architecture-v3 §20）：
> Agent + 参数搜索两层嵌套——外层 LLM 探索算子结构，内层贝叶斯优化参数。这在 v0.1 不实现，但架构预留。

### 为什么参数层是核心差异化

| 框架 | 搜索空间 | 参数优化 |
|---|---|---|
| FunSearch | 函数级代码生成 | ❌ |
| EoH | 启发式代码生成 | ❌ |
| ReEvo | 算子代码进化 | ❌ |
| AILS-AHD | 启发式结构设计 | ❌（人工调参） |
| **Scion v0.1** | **算子代码变更** | **❌（权重冻结）** |
| **Scion v0.2** | **算子代码变更 + 参数搜索** | **✅ 框架内自动化** |

所有已知同类工作都只做结构级变更。参数层是空白位。

### 不是目标

- ❌ 多问题泛化（v0.3+）
- ❌ 框架架构重构（v0.1 已验证，不需要动）
- ❌ LLM 接口层重做（v0.1 调优已完成 CC 报告 P0/P1）
- ❌ 论文级 ablation（v0.2 提供实验能力，ablation 在论文准备阶段做）

---

## 1. v0.1 现状与参数层的切入点

### 1.1 v0.1 中被冻结的参数

v0.1 design 中明确冻结的参数（architecture-v3 §6.2, §22-22）：

```yaml
# problem.yaml 中的冻结项
operator_pool:
  adaptive_weights_frozen: true     # 动态自适应权重更新机制冻结
  injection_policy:
    initial_weight: "uniform"       # 新算子一律均匀分配

# 当前 surrogate solver 中的硬编码参数
vns:
  pool_size: 40                     # solution pool 大小
  max_iterations: 200               # VNS 最大迭代
  stagnation_limit: 30              # 连续无改进终止
  # 算子权重：registry.yaml 中的静态值
```

### 1.2 参数搜索有哪些维度

按影响力和可搜索性排序：

| 参数 | 当前值 | 类型 | 影响级别 | 搜索方式 |
|---|---|---|---|---|
| **算子权重分配** | 均匀 | 连续向量 | 🔴 高 | 贝叶斯/进化 |
| **pool_size** | 40 | 整数 | 🟡 中 | 网格 |
| **max_iterations** | 200 | 整数 | 🟡 中 | 网格 |
| **stagnation_limit** | 30 | 整数 | 🟢 低 | 网格 |
| **acceptance 策略参数** | N/A | 连续 | 🟡 中 | 取决于 acceptance 机制 |

**核心参数**：算子权重分配。这是 v0.2 的主战场。

原因：
1. VNS solver 每次迭代随机选一个算子（按权重），权重直接决定搜索方向的分配
2. v0.1 冻结为均匀权重，意味着好算子和差算子获得相同的调用频率
3. 这是最容易出 ROI 的参数——不改代码，只调权重，就可能显著提升
4. 与 v0.1 的结构搜索正交且互补

### 1.3 两层嵌套的交互模式

```
外层（结构搜索，v0.1 已有）
  └── LLM 提出算子变更 → Contract → Verification → Screening → ...
       └── 当算子变更被 Promote 后，触发内层搜索

内层（参数搜索，v0.2 新增）
  └── 对 promoted 后的新算子池，搜索最优权重分配
       └── 权重优化结果更新 champion 的 registry.yaml
```

**关键设计决策：内层搜索何时触发？**

方案分析：

| 方案 | 触发时机 | 优点 | 缺点 |
|---|---|---|---|
| A：每次 Promote 后 | 算子池变更时 | 自然、及时 | 增加 Promote 路径延迟 |
| B：独立 campaign phase | 结构搜索结束后 | 不影响结构搜索流程 | 权重过时问题 |
| C：Screening 阶段并行 | 每个 candidate 自带权重优化 | 最精细 | 复杂度爆炸 |

**推荐方案 A**：每次 Promote 后触发内层搜索。原因：
- 与分支治理语义一致——Promote 意味着池结构变化，权重应重新优化
- 实现简单——在 `_on_promote()` 后插入 weight optimization phase
- 不需要重新设计主循环

---

## 2. 参数搜索的设计

### 2.1 搜索空间定义

```python
@dataclass(frozen=True)
class ParameterSearchSpace:
    """Defines the parameter search space for weight optimization."""

    operator_names: Tuple[str, ...]          # 参与权重搜索的算子名称
    weight_bounds: Tuple[float, float]       # 每个算子权重的上下界，默认 (0.05, 5.0)
    constraint: Literal["none", "simplex"]   # "simplex" = 权重归一化为概率
    fixed_params: Dict[str, Any]             # 固定不搜索的参数（pool_size 等）

    # 搜索超参数
    n_initial_random: int = 8                # 随机初始采样点数
    n_iterations: int = 20                   # 贝叶斯优化迭代数
    n_eval_seeds: int = 3                    # 每组权重的评估 seed 数
    eval_cases: Tuple[str, ...] = ()         # 评估用 case 集（从 screening split 取）
```

### 2.2 评估函数

权重搜索的评估函数：**在固定算子池上，用不同权重跑 solver，取字典序 objective 的聚合 delta。**

```python
def evaluate_weights(
    weight_vector: Dict[str, float],
    champion_workspace: str,
    cases: List[str],
    seeds: List[int],
    runner: Runner,
    time_limit: int,
) -> float:
    """评估一组权重配置的质量。

    写入 registry.yaml → 跑 solver → 收集 objectives → 聚合。
    返回值：越大越好的标量分数。
    """
    # 1. 写入 weight_vector 到 workspace 的 registry.yaml
    # 2. 对每个 (case, seed) 跑 solver
    # 3. 字典序多目标转标量：
    #    score = -subcategory_splits * 100_000 - total_cost
    # 4. 返回所有 (case, seed) 的 median score
```

标量化策略：

- 不改变字典序语义——splits 有绝对优先级
- `SPLITS_WEIGHT = 100_000` 与 `evaluation.py` 的 `compute_delta` 保持一致
- 用 median（不是 mean）抵抗离群值

### 2.3 搜索策略

#### 2.3.1 MVP：贝叶斯优化（Gaussian Process）

使用 `scipy.optimize.minimize` + 高斯过程代理模型。不引入外部库依赖。

```python
class WeightOptimizer:
    """Bayesian optimization for operator weight tuning.

    MVP uses scipy's minimize with a Gaussian Process surrogate.
    Constraint: weights must be positive (log-space search).
    """

    def __init__(
        self,
        search_space: ParameterSearchSpace,
        runner: Runner,
        champion_workspace: str,
    ) -> None:
        self._space = search_space
        self._runner = runner
        self._workspace = champion_workspace
        self._observations: List[Tuple[Dict[str, float], float]] = []

    def optimize(self) -> WeightOptimizationResult:
        """Run the full optimization loop.

        1. Random initialization (n_initial_random points)
        2. Bayesian optimization (n_iterations points)
        3. Return best observed weights
        """
        ...
```

#### 2.3.2 为什么不用 LLM 搜索参数

参数搜索是**连续优化问题**。LLM 的优势在离散的、需要领域知识的结构设计。连续参数调优用贝叶斯优化（或进化策略）比 LLM 更 sample-efficient。

蓝图已经明确了这一点（§20）：
> 外层 LLM 探索结构 + 内层贝叶斯优化参数

#### 2.3.3 搜索空间处理

算子权重是正实数（solver 内部归一化为概率）。搜索在 log-space 进行：

```python
# 搜索空间：log(weight)
# 映射：weight = exp(log_weight)
# 好处：
#   1. 自然保证 weight > 0
#   2. 等比例变化（0.1→0.2 和 1.0→2.0 等价）
#   3. GP 在 log-space 更平滑
```

### 2.4 与主循环的集成

#### 2.4.1 在 Promote 后触发

```python
# campaign.py: _on_promote() 扩展

def _on_promote(self, branch: Branch) -> None:
    """Update champion and optionally optimize weights."""
    # ... existing promotion logic ...

    # --- v0.2: Weight optimization after promotion ---
    if self._weight_optimizer is not None:
        logger.info("Champion v%d promoted. Starting weight optimization...", new_version)
        opt_result = self._weight_optimizer.optimize()
        if opt_result.improved:
            # Update champion's registry.yaml with optimized weights
            self._apply_optimized_weights(opt_result.best_weights)
            logger.info(
                "Weight optimization: score improved %.4f → %.4f",
                opt_result.baseline_score, opt_result.best_score,
            )
        # Record in lineage
        self._record_weight_optimization(opt_result)
```

#### 2.4.2 Weight optimization 不走 Branch/Protocol

权重优化是 champion 级别的"精装修"，不走分支治理流程。原因：

- 不涉及代码变更 → Contract Gate 无意义
- 不涉及新算子 → Verification Gate 无意义
- 权重变更可逆、风险低 → 不需要三级协议

但需要**独立的评估**来确认权重优化确实有效：

```python
@dataclass(frozen=True)
class WeightOptimizationResult:
    baseline_weights: Dict[str, float]       # 优化前权重（均匀）
    best_weights: Dict[str, float]           # 最优权重
    baseline_score: float                    # 均匀权重的 median score
    best_score: float                        # 最优权重的 median score
    improved: bool                           # best_score > baseline_score
    n_evaluations: int                       # 总评估次数
    elapsed_seconds: float
    all_observations: List[Tuple[Dict[str, float], float]]  # 完整搜索历史
```

#### 2.4.3 评估 case 来源

权重优化使用 **screening cases**（不碰 validation/frozen）。原因：
- screening cases 已经对 LLM 暴露（暴露控制允许）
- 权重优化不涉及信息泄漏风险（不是 LLM 在读结果）
- 数量足够（6-10 个 case × 2-3 seeds = 12-30 次 solver 调用 / 权重配置）

### 2.5 数据模型扩展

```python
# core/models.py 新增

@dataclass(frozen=True)
class WeightConfig:
    """A specific operator weight configuration."""
    weights: Dict[str, float]           # operator_name → weight
    source: Literal["uniform", "optimized", "manual"]
    optimization_id: Optional[str] = None


@dataclass
class ChampionState:
    # ... existing fields ...
    weight_config: Optional[WeightConfig] = None  # v0.2: optimized weights
```

### 2.6 Lineage 扩展

权重优化事件记录到 SQLite：

```sql
CREATE TABLE IF NOT EXISTS weight_optimizations (
    optimization_id        TEXT PRIMARY KEY,
    campaign_id            TEXT,
    champion_version       INTEGER NOT NULL,
    n_operators            INTEGER NOT NULL,
    n_evaluations          INTEGER NOT NULL,
    baseline_score         REAL,
    best_score             REAL,
    improved               INTEGER,  -- boolean
    baseline_weights_json  TEXT,
    best_weights_json      TEXT,
    elapsed_seconds        REAL,
    timestamp              TEXT NOT NULL
);
```

---

## 3. 实现计划

### 3.1 新增文件

```
scion/scion/
├── parameter/                      # 新模块
│   ├── __init__.py
│   ├── search_space.py             # ParameterSearchSpace 定义
│   ├── evaluator.py                # evaluate_weights() 函数
│   ├── optimizer.py                # WeightOptimizer (贝叶斯优化)
│   └── registry_writer.py          # 将权重写入 registry.yaml
```

### 3.2 修改文件

| 文件 | 修改内容 |
|---|---|
| `core/models.py` | 新增 WeightConfig, WeightOptimizationResult |
| `core/campaign.py` | `_on_promote()` 扩展，WeightOptimizer 注入 |
| `lineage/registry.py` | weight_optimizations 表 |
| `cli/main.py` | `scion optimize-weights` 子命令（独立调用） |
| `config/problem.py` | ProblemSpec 增加 parameter_search 配置段 |

### 3.3 配置扩展

```yaml
# problem.yaml 新增段
parameter_search:
  enabled: true
  trigger: "on_promote"              # on_promote | manual | never
  target: "operator_weights"         # v0.2 只支持权重
  strategy: "bayesian"               # bayesian | grid | random
  n_initial_random: 8
  n_iterations: 20
  n_eval_seeds: 3
  weight_bounds: [0.05, 5.0]
  constraint: "none"                 # none | simplex
```

### 3.4 Task 分解

```
Task P01: ParameterSearchSpace + WeightConfig 数据模型
  - search_space.py + models.py 扩展
  - 单元测试

Task P02: evaluate_weights() 评估函数
  - evaluator.py
  - 接入 Runner，写 registry.yaml，跑 solver，收集 objective
  - 标量化策略实现
  - 单元测试 + mock runner 集成测试

Task P03: registry_writer — 权重写入 registry.yaml
  - 读取现有 registry → 更新权重 → 写回
  - 保持其他字段不变（operator 文件路径、class_name 等）
  - 单元测试

Task P04: WeightOptimizer — 贝叶斯优化主体
  - 随机初始化 + GP surrogate + acquisition function
  - log-space 搜索
  - 优化循环 + 收敛判断
  - 单元测试（mock evaluator）

Task P05: Campaign 集成 — _on_promote() 扩展
  - WeightOptimizer 注入 CampaignManager
  - Promote 后触发 optimize
  - 结果写入 champion + lineage
  - 集成测试

Task P06: Lineage 扩展
  - weight_optimizations 表
  - record_weight_optimization()
  - scion inspect 输出权重历史

Task P07: ProblemSpec 配置扩展
  - parameter_search 段
  - 配置加载 + 校验
  - CLI: scion optimize-weights 子命令

Task P08: 端到端验证
  - 完整 campaign：结构搜索 → Promote → 权重优化 → 验证权重效果
  - 对比：均匀权重 vs 优化权重在 frozen holdout 上的表现
```

### 3.5 依赖关系

```
P01 ──→ P02 ──→ P04 ──→ P05 ──→ P08
  │       │                ↑
  └──→ P03 ────────────────┘
P06 ─────────────────────→ P05
P07 ─────────────────────→ P05
```

P01/P03/P06/P07 可并行。
P02 依赖 P01。
P04 依赖 P02。
P05 是集成点，依赖 P03/P04/P06/P07。
P08 依赖 P05。

---

## 4. LLM 接口层增量改进

这些不是 v0.2 的核心，但可以顺手做：

### 4.1 Tool Description 补充示例（CC 报告 P2-2）

在 PATCH_TOOL description 末尾添加一个最小示例：

```python
"Example skeleton:\n"
"```python\n"
"class MyOperator(Operator):\n"
"    def execute(self, solution, rng):\n"
"        new_sol = solution.deep_copy()\n"
"        # ... your logic, using sorted() for determinism ...\n"
"        new_sol.remove_empty_vehicles()\n"
"        return new_sol\n"
"```\n"
```

### 4.2 Cache Hit 监控（CC 报告 P2-1）

在 `LLMClient.call_with_tool()` 中追踪 `cache_creation_input_tokens` 和 `cache_read_input_tokens`：

```python
self._cache_stats["total"] += 1
if usage.get("cache_read_input_tokens", 0) > 0:
    self._cache_stats["cache_read"] += 1
```

### 4.3 State Leak 专项提示增强

当前已有 "NEVER use `list(set(...))`"，补充更具体的模式：

```
"Determinism traps (WILL cause V5_state_leak rejection):\n"
"- `list(set(...))` → use `sorted(set(...))`\n"
"- `for k in some_dict:` → use `for k in sorted(some_dict):`\n"
"- `dict.values()` iteration → use `sorted(d.items())`\n"
"- Any operation where output order depends on hash randomization\n"
```

---

## 5. 不做的事情（及原因）

| 不做 | 原因 |
|---|---|
| PoolManager 接入 campaign | 代码洁癖，零功能影响 |
| 框架架构重构 | v0.1 已验证正确 |
| Context 压缩 / Autocompact | v0.3+ 长 campaign 才需要 |
| 多问题泛化 | v0.3+ |
| 完整 LLM 接口重做 | v0.1 调优已完成 P0/P1，剩余 P2 顺手做 |
| PoolManager.adjust_weights | 被 parameter/ 模块替代 |

---

## 6. 验收标准

### 6.1 功能验收

1. ✅ 完整 campaign 跑通：结构搜索 → Promote → 自动触发权重优化 → 权重写入 champion
2. ✅ 权重优化后 solver 在 frozen holdout 上的表现 ≥ 均匀权重
3. ✅ Lineage 完整记录权重优化历史
4. ✅ `scion optimize-weights` CLI 可独立调用
5. ✅ 所有现有 tests 继续 pass

### 6.2 性能预期

- 权重优化单次：(8 + 20) 配置 × 6 cases × 3 seeds × ~10s/run ≈ **~84 分钟**
- 可配置 n_iterations 控制时间

### 6.3 实验对比

v0.2 完成后，需要在 frozen holdout 上做 A/B：

| 配置 | 对比 |
|---|---|
| v0.1 champion（均匀权重） | baseline |
| v0.2 champion（结构搜索 + 权重优化） | target |

如果权重优化在 frozen holdout 上 win_rate > 0.6，说明参数层有价值。

---

## 7. 风险

### 7.1 贝叶斯优化维度灾难

算子池 6-10 个算子 → 6-10 维搜索空间。GP 在 >10 维时效率下降。

**缓解**：
- v0.1 池只有 6 个算子，6 维可接受
- 如果池增长到 >10，可以切换到随机搜索 + 重点扫描
- 或者固定表现最差的几个算子权重为最小值，降维

### 7.2 权重优化过拟合 screening cases

**缓解**：
- 权重优化在 screening cases 上做，最终 Promote 仍需过 frozen holdout
- frozen holdout 是独立的、未暴露的 case set
- 如果过拟合，frozen 会拒绝

### 7.3 Promote 路径延迟增加

权重优化约 84 分钟，在 Promote 后阻塞主循环。

**缓解**：
- 可配置 `trigger: manual` 改为手动触发
- 或在 background 跑，主循环继续创建新分支
- v0.2 先做阻塞模式（简单），v0.3 考虑异步

### 7.4 scipy 依赖

贝叶斯优化需要 scipy（GP surrogate）。v0.1 不依赖 scipy。

**缓解**：
- scipy 是标准科学计算库，已在 surrogate solver 的 requirements 中
- 如果严格不想加依赖，可以用纯 random search 作为 fallback
- 或用 `sklearn.gaussian_process`（同样常用库）

---

## 8. 演进方向（v0.3+）

参数层一旦就位，后续可扩展：

1. **搜索更多参数**：pool_size, max_iterations, acceptance 参数
2. **条件参数搜索**：根据 instance 特征自适应权重（不同规模用不同权重）
3. **结构+参数联合搜索**：Screening 阶段就带权重优化（方案 C）
4. **迁移学习**：一个问题上优化好的权重比例模式，迁移到新问题

---

*本文档基于 scion-architecture-v3.md §19/§20 和 v0.1 验证结果。不改框架架构，只新增 parameter 模块。*
