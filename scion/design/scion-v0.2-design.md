# Scion Framework — v0.2 Design Document

*Date: 2026-04-08*
*Parent: scion-architecture-v3.md §19/§20*
*Branch: v0.2-dev*
*Status: Design — Draft (v2, 基于完整 v0.1 回顾)*

---

## 0. 设计方法论

本文档基于对 v0.1 全部产出的系统性回顾：

| 文档 | 核心发现 |
|---|---|
| `campaign_summary.json` + `analysis_data.json` | 15 轮 campaign，6/10 假设死于 V5_state_leak，1 promoted |
| `v0.1-completion-report.md` | 五大目标均达成，但 frozen holdout 统计力弱、hypothesis 同质化 |
| `operator-quality-analysis.md` | 属性名 bug（已修）、hypothesis 重复、缺创新方向、缺结构性理解 |
| `prompt-improvement-plan.md` | 8 项改进，P0/P1 已落地，P2 未做 |
| `v0.1-tuning-report.md` | 调优后从 0→5 次连续 Promote |
| `v0.1.1-changelog.md` | ContextManager 重写、StepRecord、registry 自动更新、状态机修复 |
| `cc-prompt-engineering-analysis.md` | CC 源码对 Scion 的 14 项建议，大部分已落地 |
| `metrics-guide.md` | wr + md 指标体系完整 |
| 源码审计 | V5 检查 + Runner 的 PYTHONHASHSEED 协议缺陷 |

---

## 1. v0.1 遗留问题清单（按根因分类）

### 1.1 框架 Bug

#### BUG-1: V5_state_leak 的 PYTHONHASHSEED 问题

**现象**: 6/10 假设被 V5_state_leak 拦截（60% 失败率）

**根因分析**:
- `subprocess_runner.py` 的环境变量白名单只有 `{"PATH", "PYTHONPATH"}`
- `PYTHONHASHSEED` 未传递 → 每个 subprocess 获得随机 hash seed
- V5 跑两次 subprocess，两次 hash seed 不同
- 算子中任何经过 `set` 的中间数据结构（如 `for sc in set(...)` 构建 dict）会因 set 遍历顺序不同 → dict 插入顺序不同 → `rng.choice(list(d.keys()))` 选到不同目标 → objective 不同
- **这不是 LLM 生成的代码有 bug**——是 Runner 和 V5 之间的环境一致性协议缺失
- Champion 算子碰巧没用 set 遍历，所以不受影响
- LLM 生成的 subcategory consolidation 算子天然需要"按 subcategory 分组"，这个操作模式必然经过 set

**修复方案**:
- Runner 的 `_build_clean_env()` 中设置 `PYTHONHASHSEED=固定值`（如 "0"）
- 这样所有 subprocess 共享相同的 hash seed，set 遍历顺序一致
- V5 检查仍然保留——捕获真正的 state leak（如修改了 input solution）
- **一行修复，预期消除 ~80% 的 V5 失败**

**影响评估**:
- 如果 6 个 V5 失败中有 4-5 个是 PYTHONHASHSEED 导致的，实际的"有效假设率"从 40% 提升到 ~70-80%
- Campaign 效率翻倍——同样 15 轮能尝试更多有效假设

#### BUG-2: campaign_summary 不存 protocol_result 和 code_content

**现象**: `campaign_summary.json` 存了 hypothesis text 和 patch code_size，但没存 protocol_result（wr/md/stage）和 code_content

**影响**:
- 无法事后分析"哪些算子在哪些 case 上赢/输"（除非查 SQLite）
- 无法分析失败算子的代码模式——被 V5 拦截的代码永久丢失
- 论文实验数据不完整

**修复方案**:
- `campaign_summary.json` 增加 `protocol_result` 字段（stage/wr/md/gate_outcome/case_feedback）
- 增加 `code_content` 字段（或引用归档路径）
- V5 失败的算子代码也需要归档（当前 workspace 被清理）

### 1.2 实验设计缺陷

#### EXP-1: Frozen holdout 统计力弱

**现象**: frozen split 只有 4 个 instance，SubcatMergeSafe 在 frozen 上 wr=1.00（12/12 pairs）

**问题**: 碾压级改进（splits 减少 50-58 个）当然全赢。但如果差异更微妙（wr=0.7），4 instance × 3 seeds = 12 pairs 的统计功效不足以区分真改进和噪声。

**修复方案**:
- Frozen holdout 扩容到 8-12 个 instance
- 需要新的 large/xlarge instance，保证与 screening/validation 不重叠
- 更新 `split_manifest.yaml`

#### EXP-2: Screening 与 frozen 的难度梯度

**现象**: Branch 4（ExtractMinoritySubcat）screening wr=0.70 → validation wr=0.44

**分析**: screening 用 small/medium instance，validation/frozen 用 large/xlarge。算子在小规模上"碰巧"表现好，大规模上暴露真实水平。这说明三级协议在正确工作——但也说明 screening 的信号可以更强。

**改进方向**:
- screening 中混入至少 2 个 large instance，提前暴露规模依赖性
- 或者提高 screening 门槛（当前 wr ≥ 0.60，可提到 0.65）

### 1.3 LLM 搜索效率

#### SEARCH-1: Hypothesis 同质化

**现象**: 10 个假设全是 `create_new vehicle_level`，其中 7/10 是"subcategory consolidation"的变体

**根因**: 
- Prompt 引导 LLM 正确识别了 splits 是首要目标 → 所有假设都瞄准 splits
- 但 LLM 不知道除了 consolidation 还有什么别的方式降 splits
- Blacklist 机制存在但 LLM 在语义上绕过——换个名字重复同一策略
- 从未尝试 `order_level` 类别或 `modify`/`remove` 动作

**改进方向**（prompt 层）:
- 连续 N 次同类型失败后，主动引导切换 action 或 change_locus
- 在 hypothesis context 中展示 operator-quality-analysis 报告中的 6 个未探索方向
- Blacklist 机制增强：不只比 target_file 和 action，做语义相似度检测

#### SEARCH-2: 生成代码不够 defensive on determinism

**现象**: 即使 prompt 禁止了 `list(set(...))`，LLM 仍通过间接路径引入非确定性

**分析**: 这在 BUG-1 修复后可能大幅缓解。但仍值得加强 prompt 中的确定性约束描述，覆盖更隐蔽的 pattern：
- `for x in set(...)` → dict 构建顺序非确定
- `collections.Counter` 的 `.keys()` 遍历顺序（Counter 继承 dict，但从 set-like 操作构建）
- `{k: v for k, v in ...}` 如果源是 set

### 1.4 可观测性

#### OBS-1: 上下文增长管理

**现象**: 当前 8 轮窗口够用，100+ 轮需要裁剪策略
**优先级**: P2（v0.2 的 campaign 预计 20-30 轮，8 轮窗口仍够用）

#### OBS-2: Cache hit 率无监控

**现象**: LLMClient 有 cache_stats 但未暴露到 campaign report
**优先级**: P2

---

## 2. v0.2 工作分解

基于上述分析，v0.2 分为三个部分：

### Part A: 基础修复（前置条件，1-2 天）

| ID | 内容 | 优先级 | 预期效果 |
|---|---|---|---|
| A1 | Runner PYTHONHASHSEED 固定 | P0 | V5 误报率从 60% 降到 <15% |
| A2 | campaign_summary 增加 protocol_result + code_content 归档 | P1 | 实验数据完整可追溯 |
| A3 | V5 失败时保存候选代码到 archive | P1 | 事后分析失败模式 |
| A4 | Frozen holdout 扩容到 8+ instance | P1 | 统计功效提升 |

### Part B: 搜索效率提升（与 Part C 并行，2-3 天）

| ID | 内容 | 优先级 | 预期效果 |
|---|---|---|---|
| B1 | Hypothesis 多样性引导（连续失败后切换策略提示） | P1 | 减少同质化 |
| B2 | Prompt 确定性约束增强（覆盖间接 set→dict 污染） | P1 | V5 真阳性 fix 率提升 |
| B3 | Prompt P2 级改进落地（反馈清晰度、champion 基线值） | P2 | LLM 学习效率 |
| B4 | Screening 混入 large instance | P2 | 提前暴露规模依赖 |

### Part C: 参数层搜索（核心新功能，3-5 天）

即蓝图 §19/§20 的本体。详见 §3。

### 执行顺序

```
A1 → A2/A3/A4（可并行）→ 跑一轮 campaign 验证基线
  │
  ├─→ B1/B2（可并行）
  │
  └─→ C: 参数层搜索设计 + 实现
         C1 → C2 → C3 → C4 → C5（见 §3.4）
```

**关键决策**: A1（PYTHONHASHSEED）必须最先做，因为它直接影响后续所有 campaign 的实验效率。在 60% 误报率下跑 campaign 是浪费。

---

## 3. 参数层搜索设计

### 3.1 定位

在 v0.1 结构级搜索（算子 create/modify/remove）基础上，增加**参数层搜索**。

蓝图原文（architecture-v3 §19）：
> v0.2 参数层：外层 LLM 探索结构 + 内层贝叶斯优化参数（算子权重等）。两层嵌套搜索是核心差异化点。

### 3.2 差异化分析

| 框架 | 搜索空间 | 参数优化 |
|---|---|---|
| FunSearch | 函数级代码生成 | ❌ |
| EoH | 启发式代码生成 | ❌ |
| ReEvo | 算子代码进化 | ❌ |
| AILS-AHD | 启发式结构设计 | ❌（人工调参） |
| **Scion v0.1** | **算子代码变更** | **❌（权重冻结）** |
| **Scion v0.2** | **算子代码变更 + 参数搜索** | **✅ 框架内自动化** |

### 3.3 搜索空间

v0.1 冻结的参数：

```yaml
operator_pool:
  adaptive_weights_frozen: true     # 动态自适应权重更新机制冻结
  injection_policy:
    initial_weight: "uniform"       # 新算子一律均匀分配
```

v0.2 的参数搜索目标：

| 参数 | 当前值 | 类型 | 影响级别 | 搜索方式 |
|---|---|---|---|---|
| **算子权重分配** | 均匀 | 连续向量 | 🔴 高 | 贝叶斯优化 |
| pool_size | 40 | 整数 | 🟡 中 | v0.2 不搜索 |
| max_iterations | 200 | 整数 | 🟡 中 | v0.2 不搜索 |

**v0.2 只搜索算子权重。** 原因：
1. 权重直接决定搜索方向分配，ROI 最高
2. 与 v0.1 结构搜索正交且互补
3. 不改 solver 代码，风险低
4. 算子池 6-10 个 → 6-10 维连续优化，贝叶斯可处理

### 3.4 两层嵌套的交互

```
外层（结构搜索，v0.1 已有）
  └── LLM 提出算子变更 → Contract → Verification → Screening → Promote
       └── Promote 触发内层搜索

内层（参数搜索，v0.2 新增）
  └── 对 promoted 后的新算子池，搜索最优权重分配
       └── 最优权重写入 champion 的 registry.yaml
```

**触发时机：每次 Promote 后。** 与分支治理语义一致——Promote 意味着池结构变化，权重应重新优化。

### 3.5 内层搜索：贝叶斯优化

#### 为什么贝叶斯优化

- 评估一次需要跑 solver（6 cases × 3 seeds × ~10s = ~3 min）→ sample-efficient 很重要
- 6-10 维连续空间 → GP surrogate 合适
- 不用 LLM：连续参数调优是贝叶斯优化的主场，不需要领域推理

#### 搜索配置

```python
@dataclass(frozen=True)
class ParameterSearchSpace:
    operator_names: Tuple[str, ...]          # 参与搜索的算子名
    weight_bounds: Tuple[float, float]       # 每个算子权重上下界，默认 (0.05, 5.0)
    n_initial_random: int = 8                # 随机初始采样
    n_iterations: int = 20                   # 贝叶斯优化迭代
    n_eval_seeds: int = 3                    # 每组权重的评估 seed 数
    eval_cases: Tuple[str, ...] = ()         # 评估用 case（从 screening split 取）
```

#### 评估函数

```python
def evaluate_weights(weight_vector, champion_workspace, cases, seeds, runner) -> float:
    """写入 registry.yaml → 跑 solver → 收集 objectives → 聚合为标量。
    
    标量化：score = -splits * 100_000 - total_cost
    与 compute_delta 的 SPLITS_WEIGHT 保持一致。
    返回所有 (case, seed) 的 median score。
    """
```

#### 搜索空间处理

- 在 log-space 搜索（weight = exp(x)），保证 weight > 0 且等比例变化
- 不约束权重归一化（solver 内部归一化）

### 3.6 权重优化不走 Branch/Protocol

权重变更不涉及代码 → Contract/Verification 无意义。
权重变更可逆、风险低 → 不需要三级协议。

但需要独立评估确认有效：

```python
@dataclass(frozen=True)
class WeightOptimizationResult:
    baseline_weights: Dict[str, float]
    best_weights: Dict[str, float]
    baseline_score: float
    best_score: float
    improved: bool
    n_evaluations: int
    elapsed_seconds: float
    all_observations: List[Tuple[Dict[str, float], float]]
```

### 3.7 评估 case 来源

使用 **screening cases**。原因：
- 暴露控制允许（screening 层级完整暴露）
- 不碰 validation/frozen
- 数量足够

### 3.8 Lineage 扩展

```sql
CREATE TABLE IF NOT EXISTS weight_optimizations (
    optimization_id        TEXT PRIMARY KEY,
    campaign_id            TEXT,
    champion_version       INTEGER NOT NULL,
    n_operators            INTEGER NOT NULL,
    n_evaluations          INTEGER NOT NULL,
    baseline_score         REAL,
    best_score             REAL,
    improved               INTEGER,
    baseline_weights_json  TEXT,
    best_weights_json      TEXT,
    elapsed_seconds        REAL,
    timestamp              TEXT NOT NULL
);
```

### 3.9 Task 分解

```
C1: 数据模型（ParameterSearchSpace, WeightConfig, WeightOptimizationResult）
C2: 评估函数（evaluate_weights + registry_writer）
C3: 贝叶斯优化器（WeightOptimizer，依赖 scipy）
C4: Campaign 集成（_on_promote 扩展 + lineage）
C5: CLI（scion optimize-weights）+ 配置扩展
C6: 端到端验证
```

依赖：C1 → C2 → C3 → C4 → C6。C5 可并行。

### 3.10 性能预估

- (8 + 20) 配置 × 6 cases × 3 seeds × ~10s/run ≈ **84 分钟**
- Promote 后阻塞主循环（v0.2 简单模式，v0.3 可异步）

---

## 4. 配置扩展

```yaml
# problem.yaml 新增段
parameter_search:
  enabled: true
  trigger: "on_promote"              # on_promote | manual | never
  target: "operator_weights"
  strategy: "bayesian"               # bayesian | grid | random
  n_initial_random: 8
  n_iterations: 20
  n_eval_seeds: 3
  weight_bounds: [0.05, 5.0]
```

---

## 5. 风险

| 风险 | 缓解 |
|---|---|
| 贝叶斯优化维度灾难（>10 算子） | v0.1 池 6 个算子，6 维可接受；>10 时降维或切换 random search |
| 权重过拟合 screening cases | Promote 仍需过 frozen holdout |
| Promote 延迟 ~84 分钟 | 可配置 `trigger: manual`，或 v0.3 异步化 |
| scipy 新依赖 | 标准库，surrogate 已有相关依赖 |

---

## 6. 验收标准

### 功能验收
1. ✅ `PYTHONHASHSEED` 固定后，V5 误报率 < 15%
2. ✅ 完整 campaign：结构搜索 → Promote → 自动权重优化 → 写入 champion
3. ✅ 权重优化后 solver 在 frozen holdout 上表现 ≥ 均匀权重
4. ✅ campaign_summary 含完整 protocol_result + code archive
5. ✅ 所有现有 tests pass

### 实验对比
| 配置 | 对比 |
|---|---|
| v0.1 champion（均匀权重） | baseline |
| v0.2 champion（结构搜索 + 权重优化） | target |

---

## 7. 不做的事情

| 不做 | 原因 |
|---|---|
| PoolManager 接入 campaign | 代码洁癖，零功能影响 |
| 框架架构重构 | v0.1 已验证正确 |
| Context 压缩 / Autocompact | v0.3+（当前 8 轮窗口够用） |
| 多问题泛化 | v0.3+ |
| 搜索 pool_size / max_iterations | v0.2 只搜索权重，验证参数层可行性 |

---

## 8. 演进方向（v0.3+）

1. 搜索更多参数（pool_size, stagnation_limit, acceptance 参数）
2. 条件参数搜索（根据 instance 特征自适应权重）
3. 结构+参数联合搜索（Screening 阶段就带权重优化）
4. 多问题泛化
5. 论文级 ablation 实验
6. 上下文增长管理（100+ 轮 campaign）

---

*本文档基于 v0.1 全部产出的系统性回顾 + scion-architecture-v3.md §19/§20。*
