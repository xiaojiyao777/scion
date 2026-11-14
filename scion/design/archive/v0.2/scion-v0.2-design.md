# Scion Framework — v0.2 Design Document

*Date: 2026-04-08*  
*Parent*: `design/scion-architecture-v3.md` §19/§20  
*Branch*: `v0.2-dev`  
*Status*: Design — Reviewed Draft

---

## 0. 文档定位

本文档不是“想到什么做什么”的 todo list，而是基于 **v0.1 全量产出回顾 + 源码审计 + 实验记录复盘** 得出的 v0.2 正式设计文档。

设计输入包括：

- `design/scion-architecture-v3.md`
- `design/scion-engineering-arch-v1.md`
- `docs/v0.1-completion-report.md`
- `docs/v0.1-tuning-report.md`
- `docs/v0.1.1-changelog.md`
- `docs/operator-quality-analysis.md`
- `docs/prompt-improvement-plan.md`
- `docs/cc-prompt-engineering-analysis.md`
- `docs/reference/metrics-guide.md`
- `docs/campaign_summary.json`
- `~/.openclaw/workspace/scion-v01-analysis/analysis_data.json`
- 现有 `scion/` 源码实现

**核心结论先写在前面**：

> v0.2 不应该是“框架大改版”，而应该是：
> **先修掉 v0.1 暴露出的基础缺陷与观测缺口，再把蓝图里真正属于 v0.2 的参数层搜索落地。**

因此，v0.2 的主体由三部分组成：

1. **Part A — Foundation Fixes**：修正 v0.1 暴露出的确定性/可观测性/统计力问题
2. **Part B — Search Efficiency Upgrades**：提升外层结构搜索的有效探索率
3. **Part C — Parameter Layer Search**：实现蓝图定义的“外层结构 + 内层参数”两层嵌套搜索

---

## 1. v0.1 复盘：已经证明了什么

### 1.1 v0.1 已经成功证明的部分

根据 `docs/v0.1-completion-report.md`，v0.1 的 5 个核心目标全部达成：

1. **双硬闸门可工作**：Contract + Verification 能拦截越界和语义错误
2. **三级实验协议可工作**：Screening → Validation → Frozen 能区分真改进和噪声
3. **分支治理可工作**：分支内迭代 + 状态机 + stale/reconcile 语义成立
4. **全链路可追溯**：SQLite lineage 已可查
5. **Decision Layer 与 LLM 输出隔离**：DecisionFeatures 无自由文本，边界成立

### 1.2 v0.1 的最好结果说明了什么

`analysis_data.json` 显示：

- 4 个分支
- 1 个 promoted branch
- 10 个假设中 4 个通过 verification，6 个失败于 `V5_state_leak`
- Promoted 分支 `SubcatMergeSafe`：
  - Screening: `wr=0.95`, `md=750000`
  - Validation: `wr=1.00`, `md=2200000`
  - Frozen: `wr=1.00`, `md=5150000`

这说明：

- Scion 已经能够发现 **真实、稳定、可晋升** 的结构性改进
- 三级协议没有把一个弱 improvement 错晋升上去
- 在大/超大实例上，结构性改进会被放大，不是“碰巧赢”

### 1.3 v0.1 的主要不足不是“框架不行”，而是“效率还不够高”

v0.1 的主问题不是方向错了，而是：

- 外层搜索有效假设率不够高
- 一些 failure 其实是**环境/诊断问题**，不是算法问题
- 实验记录还不够完整，限制了事后分析与论文化
- 蓝图里定义的参数层搜索尚未落地

所以 v0.2 的工作不是推翻 v0.1，而是：

> **把 v0.1 从“能跑通、能发现改进”推进到“能高效探索、能系统比较、能承载论文实验”。**

---

## 2. v0.1 复盘：真正暴露出来的问题

### 2.1 问题一：`V5_state_leak` 失败率过高，但根因不全在 LLM

#### 现象

从 `campaign_summary.json` 与 `analysis_data.json` 可见：

- 10 个 hypothesis 中有 6 个死于 `V5_state_leak`
- 占全部 hypothesis 的 60%
- 严重拖慢外层搜索效率

#### 审计结论

V5 的定义是：

> 同一个 case、同一个 seed，candidate 连跑两次，objective 必须一致。

这本身是合理的。但源码审计发现：

- `subprocess_runner.py` 只透传 `PATH` 和 `PYTHONPATH`
- 没有固定 `PYTHONHASHSEED`
- Python 3.12 的 **dict 有序**，但 **set/hash 仍受 hash seed 影响**
- 如果候选算子使用 `set` 构建中间索引，再由此影响 dict 的插入顺序，就可能出现跨 subprocess 的行为差异

这意味着：

- 一部分 `V5_state_leak` 是**真实的非确定性 bug**
- 另一部分是 **Runner 环境未固定导致的误放大**

#### 设计结论

v0.2 必须同时做两件事：

1. **修环境**：让 subprocess 的 hash seed 固定，消除环境侧的伪非确定性
2. **增强诊断**：不要只报 `run1 != run2`，要能帮助定位到底是哪一段逻辑引入了分歧

> 不能只做环境修复，否则会掩盖真实 deterministic bug；
> 也不能只做诊断，否则继续在脏环境里浪费大量实验预算。

---

### 2.2 问题二：Hypothesis 同质化严重

#### 现象

从 `campaign_summary.json` 与 `operator-quality-analysis.md`：

- 10/10 hypothesis 都是 `create_new`
- 10/10 hypothesis 都是 `vehicle_level`
- 其中 7/10 本质都是同一个机制：**subcategory consolidation / purification** 的变体

#### 含义

这说明：

- 框架已经把 LLM 正确引导到了“splits 是首要目标”这件事上
- 但 LLM 没有在 **change_locus / action / mechanism family** 上形成足够多样性
- 现有 blacklist 更像“文本去重”，不是“机制去重”

#### 设计结论

v0.2 不能只依靠 blacklist，而需要：

1. **机制层级的失败归纳**：记录“这是一类 subcategory consolidation operator”，而不是只记录文件名/标题
2. **策略切换提示**：连续 N 次同族机制失败后，主动引导：
   - 从 `create_new` 切到 `modify`
   - 从 `vehicle_level` 切到 `order_level`
   - 从“直接 consolidation”切到“rebuild / destroy / chain-move / swap”
3. **探索配额意识**：Context 中显式告诉 LLM 当前 campaign 在不同 action/locus 上的覆盖情况

---

### 2.3 问题三：实验记录不够完整，影响复盘和论文化

#### 现象

当前 `campaign_summary.json`：

- 有 hypothesis 文本
- 有 patch 文件路径和 code size
- 但**没有完整 protocol_result**
- 也**没有 code_content** 或可靠归档引用

这导致：

- 事后无法从单一 summary 还原每轮 screening/validation/frozen 细节
- 无法直接统计某类假设在哪些 case 上表现好/差
- 被 verification 拒绝的代码细节容易丢失

#### 设计结论

v0.2 必须把“实验 summary”升级为真正的研究 artifact：

- 保存 `protocol_result`（至少 stage / wr / md / gate / case feedback 摘要）
- 保存候选代码内容或稳定的归档路径
- 对 verification failure 保留 failure detail + code snapshot

---

### 2.4 问题四：Frozen holdout 统计力仍偏弱

#### 现象

`v0.1-completion-report.md` 已明确指出：

- 当前 frozen holdout 仍偏小
- 对于像 `SubcatMergeSafe` 这种碾压级 improvement 没问题
- 但如果是中等强度 improvement，统计功效不一定够

#### 设计结论

v0.2 需要：

- 扩充 frozen set 的 case 数量与规模跨度
- 保证 frozen 的结构异质性
- 让 frozen 更像“真正的 final exam”，而不是“额外一次 validation”

---

### 2.5 问题五：Prompt 层已经大幅改进，但还缺最后一层“研究友好型提示”

通过对 `cc-prompt-engineering-analysis.md`、`prompt-improvement-plan.md` 和当前源码比对，可以确认：

- CC 报告中的 P0/P1 大部分已经落地
- 当前系统 prompt / tool description / problem summary / interface spec 已明显优于 v0.1 初期

所以 v0.2 **不需要再搞一次“大规模 prompt 重写”**。

但仍有几个 P2 级的、对研究效率有价值的增强：

- 更清晰地解释 `case_feedback` 中的 decisive objective 与 delta 含义
- 在 hypothesis context 中加入 champion case baseline（告诉 LLM 某 case 上 splits 已经是 0，就别再瞄准 splits）
- 增加对探索覆盖度的结构化提示

---

## 3. v0.2 总体目标

### 3.1 一句话目标

> **让 Scion 从“能发现改进的研究执行框架”升级为“能高效、可诊断、可比较地执行结构搜索 + 参数搜索的研究平台”。**

### 3.2 v0.2 三大目标

#### Goal A — 修正 v0.1 中影响研究效率与结论可信度的基础缺陷

重点解决：

- deterministic environment
- richer V5 diagnostics
- campaign artifact completeness
- stronger frozen holdout

#### Goal B — 提升外层结构搜索的有效探索率

重点解决：

- mechanism homogeneity
- action/locus coverage不足
- experiment feedback不够面向“研究决策”

#### Goal C — 落地参数层搜索

这是蓝图 `architecture-v3 §19/§20` 中 v0.2 的真正本体：

- 外层：LLM 搜结构
- 内层：算法搜参数

---

## 4. v0.2 不做什么

为了防止 scope 膨胀，明确列出不做的事：

- ❌ 不做框架大重构（v0.1 架构已验证正确）
- ❌ 不做多问题泛化（放到 v0.3）
- ❌ 不做 solver framework 本体搜索（放到 v1.0）
- ❌ 不做“所有参数都搜”——v0.2 只聚焦 **operator weights**
- ❌ 不把 PoolManager 深度集成当作主线目标（可顺手整理，但不是 v0.2 成败关键）

---

## 5. v0.2 设计原则

### 5.1 先修“研究基础设施”，再扩大搜索空间

v0.2 的第一优先级不是上新 feature，而是修掉会扭曲实验结论或浪费大算力预算的问题。

### 5.2 区分“真实失败”和“环境/协议失败”

v0.1 一个很重要的教训是：

> 如果基础运行环境不稳定，Verification Failure 的统计就会混入环境噪声。

v0.2 必须把这两类 failure 分开。

### 5.3 不把 prompt 当万能药

Prompt 对 v0.1 的提升已经很大，但 v0.2 的主战场不是再堆 prompt，而是：

- better diagnostics
- better experiment design
- better search decomposition

### 5.4 参数搜索要与结构搜索解耦，但保持因果顺序

结构变了，参数空间也变；因此：

- 参数搜索必须依附在 champion pool 上
- 不能把结构搜索和参数搜索混在一个分支协议里
- 但也不能完全脱离 champion 生命周期

---

## 6. v0.2 结构：三条工作流

# 靠三个并行工作流组成 v0.2

---

### Workstream A — Foundation & Instrumentation

这是 v0.2 的前置基础，不解决就会拖累后面所有工作。

#### A1. Deterministic Runner Environment

**目标**：修正 subprocess 运行环境的不一致性。

**改动**：

- `runtime/subprocess_runner.py`
  - 在 clean env 中固定 `PYTHONHASHSEED`
  - 保持其余环境继续最小白名单

**注意**：

- 这是为了解决环境侧伪随机，不是为了掩盖真实 bug
- `V5_state_leak` 检查保留，不删除

#### A2. V5 诊断升级

当前 V5 失败 detail 只有：

- run1 objective
- run2 objective

这对 LLM 或人都不够。

**v0.2 增强**：

1. 保存两次 run 的完整 output JSON
2. 保存候选算子的 code snapshot
3. 如果可能，增加轻量 trace：
   - 本轮选中的 operator
   - 关键中间 decision（后续可选）
4. 把 V5 failure 分成：
   - `ENV_NONDETERMINISM`（环境不一致导致）
   - `CANDIDATE_NONDETERMINISM`（候选逻辑真的不确定）
   - `UNKNOWN_NONDETERMINISM`

> v0.2 至少做到分类 + 归档；精细 trace 可以 P1。

#### A3. Campaign Artifact Completeness

`campaign_summary.json` 扩展：

- `protocol_result`
- `case_feedback` 摘要
- `code_archive_ref`
- `verification_detail`
- `cache_stats`

这样 future analysis 不必重新爬 SQLite 或 log。

#### A4. Frozen Holdout Expansion

- 增加 frozen cases 数量
- 增加 large/xlarge 异质性
- 更新 split manifest 与 seed ledger

#### A5. Long-run observability

- 把 cache hit rate、verification failure breakdown、action/locus coverage 纳入 report

---

### Workstream B — Outer-loop Search Efficiency

这个工作流不改变三层控制架构，而是提升 **外层结构搜索** 的有效探索率。

#### B1. Hypothesis Family Tracking

现有 blacklist 基于 record，不足以防止“语义改写的重复机制”。

新增机制：

```python
@dataclass
class HypothesisFamily:
    family_id: str
    mechanism_label: str          # e.g. subcategory_consolidation
    action_pattern: str           # create_new / modify / remove
    locus_pattern: str            # vehicle_level / order_level
    evidence_count: int
    statuses: list[str]           # rejected / borderline / promoted
    notes: str                    # for human/LLM readable summary
```

用途：

- 让 ContextManager 告诉 LLM：
  - “你已经连续 4 次在这个 family 上失败了”
  - “当前 campaign 还没探索 order_level family”

#### B2. Strategy-shift Guidance

在 hypothesis prompt 中加入结构化 guidance：

- 连续 N 次 `create_new` 失败 → 建议尝试 `modify`
- 某机制 family 连续失败 → 强制引导切换 mechanism family
- 某个 `change_locus` 长期未探索 → 提示去探索

#### B3. Feedback for research, not just for logging

当前 case feedback 已经很不错，但对“下一轮应该怎么变”还不够直接。

v0.2 增强：

- 把 decisive objective 渲染成人可理解的解释
- 告诉 LLM：某些 case 上 champion 的 splits 已经为 0
- 给出跨 round 的 pattern summary：
  - 哪类 case 一直赢
  - 哪类 case 一直输
  - 哪类 case 对某 family 特别敏感

#### B4. Screening set rebalance

- 混入少量 large cases
- 提前暴露“只在小实例上好看”的算子

---

### Workstream C — Parameter Layer Search (v0.2 核心新能力)

这是蓝图里定义的 v0.2 真正主线。

#### C1. 设计定位

> 外层结构搜索决定“有哪些算子”；内层参数搜索决定“这些算子应该如何配权”。

#### C2. 为什么 v0.2 只做 operator weights

v0.1 中被冻结的参数很多，但 v0.2 只选 **operator weights**，原因：

1. 与结构搜索天然耦合
2. 不需要改 solver 结构
3. 风险低，ROI 高
4. 可清晰对比“均匀权重 vs 优化权重”

#### C3. 触发时机

参数搜索在 **每次 Promote 后** 触发：

```text
new champion promoted
    ↓
optimize weights for current pool
    ↓
write optimized registry.yaml
    ↓
record optimization lineage
```

这是最自然的生命周期绑定方式。

#### C4. 为什么不走 Branch / Verification / Protocol

参数优化与结构搜索不同：

- 不改代码
- 不碰文件白名单问题
- 不会引入 interface/feasibility bug

因此：

- 不需要 Contract Gate
- 不需要 Verification Gate
- 不需要作为 branch candidate 跑三级状态机

但仍需要**独立的评估循环**和**独立的 lineage**。

#### C5. 搜索空间

```python
@dataclass(frozen=True)
class ParameterSearchSpace:
    operator_names: tuple[str, ...]
    weight_bounds: tuple[float, float] = (0.05, 5.0)
    search_space: Literal["log"] = "log"
    n_initial_random: int = 8
    n_iterations: int = 20
    n_eval_seeds: int = 3
    eval_cases: tuple[str, ...] = ()
```

说明：

- 在 log-space 搜索，天然保证正值
- solver 内部会归一化，所以不需要 simplex 约束

#### C6. 搜索算法

默认：**Bayesian Optimization**

原因：

- 评估贵（每组权重要跑 solver）
- 维度低到中等（6~10 维）
- 比 random/grid 更 sample-efficient

fallback：

- 若依赖/实现复杂度过高，可先用 `random + local perturbation` 做 MVP
- 但正式设计目标仍是贝叶斯优化

#### C7. 评估函数

输入：

- 当前 champion pool
- 一组候选 weights
- screening cases + 固定 seeds

输出：

- 标量 score

标量化保持与现有 lexicographic delta 一致：

```python
score = -(subcategory_splits * SPLITS_WEIGHT + total_cost)
SPLITS_WEIGHT = 100_000
```

对所有 `(case, seed)` 求 median score。

#### C8. 输出与持久化

```python
@dataclass(frozen=True)
class WeightOptimizationResult:
    baseline_weights: dict[str, float]
    best_weights: dict[str, float]
    baseline_score: float
    best_score: float
    improved: bool
    n_evaluations: int
    elapsed_seconds: float
    observations_ref: str
```

Lineage 需要新增独立表：

- `weight_optimizations`

以及 CLI 能看：

- `scion inspect` / `report` 中展示当前 champion 权重来源与优化历史

---

## 7. v0.2 任务拆解

### Phase 0 — 审计闭环（必须先做）

1. 确认 deterministic env fix 的最小实现
2. 定义 V5 诊断增强输出 schema
3. 设计新的 campaign artifact schema

### Phase 1 — Foundation & Instrumentation

- T01: Runner deterministic env fix
- T02: V5 diagnostics enhancement
- T03: campaign summary schema upgrade
- T04: candidate code archiving for failed runs
- T05: frozen holdout expansion
- T06: observability fields in report

### Phase 2 — Outer-loop Search Efficiency

- T07: Hypothesis family tracking
- T08: strategy-shift guidance injection
- T09: richer case feedback rendering
- T10: champion baseline hints per case
- T11: screening set rebalance

### Phase 3 — Parameter Layer Search

- T12: parameter data models + config schema
- T13: registry writer for weights
- T14: evaluation function for weight configs
- T15: optimizer implementation
- T16: campaign hook on promote
- T17: lineage + CLI + reporting
- T18: end-to-end experiment

---

## 8. 验收标准

### 8.1 Foundation 成功标准

- `V5_state_leak` failure rate 明显下降，且失败分类更可解释
- 每轮 candidate（包括失败的）都有稳定可追溯 artifact
- frozen holdout 规模与异质性提升

### 8.2 Outer-loop 成功标准

- hypothesis family 多样性提高
- `create_new/modify/remove` 不再极度单一
- `vehicle_level/order_level` 覆盖更平衡
- 同族机制重复率下降

### 8.3 Parameter Layer 成功标准

- 可以在 promote 后自动进行 weight optimization
- 可以明确对比：均匀权重 vs 优化权重
- 至少在一个 promoted champion 上观察到稳定权重收益

### 8.4 研究产出标准

v0.2 完成后，应能支持以下研究型问题：

1. 结构搜索 alone 的收益是多少？
2. 参数搜索 alone 的收益是多少？
3. 结构 + 参数叠加后收益是多少？
4. 某类算子的收益主要来自“存在”还是“被高频调用”？

这四个问题正是论文化的基础。

---

## 9. 风险与对策

### 风险 1：修 deterministic env 后，V5 真实 failure 仍然高

**对策**：
- 这是好事，说明我们把“环境噪声”剥离了
- 进一步依赖 enhanced diagnostics 去找真实代码模式

### 风险 2：Hypothesis family tracking 过于复杂

**对策**：
- v0.2 先做 rule-based / heuristic family labeling
- 不要求一开始就做 embedding clustering

### 风险 3：Bayesian Optimization 实现成本高

**对策**：
- 接口先抽象好
- MVP 可先 random + local search
- 但设计上保留 BO 作为正式目标

### 风险 4：Promote 后的参数优化时间过长

**对策**：
- v0.2 默认串行执行（简单正确）
- 若时间成本不可接受，v0.3 再异步化

---

## 10. 最终判断：什么构成“好的 v0.2”

一个好的 v0.2，不是单纯多了一个 `optimize_weights()` 函数，而应该具备以下属性：

1. **更少被环境问题浪费的实验预算**
2. **更强的 failure diagnosis 能力**
3. **更丰富、更不重复的结构探索**
4. **真正落地的参数层搜索**
5. **能直接支撑论文化分析的 artifact 与报告体系**

如果只做参数层搜索而不修前面的基础问题，v0.2 会变成“新 feature 叠在旧噪声上”；
如果只做基础修复而不落地参数层，v0.2 又失去蓝图定义的核心差异化。

因此，v0.2 的正确形态是：

> **Foundation Fixes + Outer-loop Efficiency + Parameter Layer Search**

缺一不可，但主线仍然是参数层搜索。

---

## 11. 推荐实施顺序（最终版）

```text
Week 1:
  A1 deterministic env
  A2/A3 diagnostics + artifacts
  A4 frozen expansion
  → 跑一轮新 campaign，重新测真实 V5 failure rate

Week 2:
  B1/B2 family tracking + strategy guidance
  B3/B4 richer feedback + screening rebalance
  → 再跑一轮 campaign，看 hypothesis 多样性是否改善

Week 3:
  C1/C2/C3 parameter search core
  C4/C5 campaign hook + lineage + CLI
  → 跑 promote-after-optimize 的完整闭环

Week 4:
  C6 end-to-end evaluation
  baseline vs optimized-weight comparison
  撰写 v0.2 experiment note
```

---

*本设计文档替代此前的“仅参数层版本”草稿。后续若继续细化，可拆为：*

- `scion-v0.2-foundation.md`
- `scion-v0.2-parameter-search.md`
- `scion-v0.2-experiment-plan.md`
