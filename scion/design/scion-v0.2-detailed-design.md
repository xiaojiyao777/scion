# Scion v0.2 — Detailed Design

*Date: 2026-04-10*  
*Status: Detailed design supplement*  
*Branch: `v0.2-dev`*  
*Parent docs:* `scion-v0.2-design.md`, `scion-v0.2-task-manifest.md`, `scion-v0.2-refined-delivery-plan.md`

---

## 0. 文档定位

本文档不替代已有 v0.2 设计文档，而是把 v0.2 落地到**可直接开发**的粒度。

重点解决三件事：

1. 基于真实代码状态，锁定哪些能力已经在 v0.1 中存在，避免重复设计
2. 明确 v0.2-MVP 与 v0.2-Full 的边界，先落最关键的闭环
3. 将关键任务落到文件、接口、数据结构、执行顺序、测试标准

---

## 1. 当前代码基线（必须承认的现实）

### 1.1 已经存在，不应重做的能力

v0.1 代码中已经存在：

- `ObjectiveBreakdown`
- `PairwiseCaseFeedback`
- `CaseAggregateFeedback`
- `ScreeningPatternSummary`
- `ProtocolResult.case_feedback / pattern_summary`
- `compare_with_breakdown()`
- screening 阶段的 pair → case → pattern 聚合
- hypothesis prompt 中的 case feedback / pattern summary 渲染
- `WorkspaceMaterializer.archive_workspace()`
- `PoolManager.export_registry()` 与权重归一化

因此：

- **T09/T10 是增强，不是重建**
- **T13 应优先复用 `PoolManager`，不是另起一套 registry writer**

### 1.2 确认缺失的 v0.2 关键能力

当前代码中仍缺失：

- subprocess 环境未固定 `PYTHONHASHSEED`
- V5 诊断过浅（仅一行 diff）
- `campaign_summary.json` 信息不足
- failed candidate 归档缺少稳定引用链
- 假设 family tracking 不存在
- strategy-shift guidance 不存在
- parameter layer 完全不存在
- promote 后自动权重搜索不存在
- `weight_optimizations` lineage 不存在
- CLI 无 `optimize-weights` / `inspect --weights`

---

## 2. v0.2 范围重定义

## 2.1 v0.2-MVP

v0.2 的第一阶段目标不是“把 18 个任务一次做完”，而是先形成**可信闭环**：

```text
更干净的环境
    +
更完整的 artifact
    +
promote 后自动参数搜索
    +
可追溯结果
```

v0.2-MVP 包含：

- T01 Deterministic env
- T02 V5 diagnostics enhancement
- T03 Campaign summary schema upgrade
- T04 Failed-code archiving
- T12 Parameter config + models
- T13 Registry weight IO
- T14 Weight evaluator
- T15a Random/local optimizer
- T16 Promote hook integration
- T17a Weight-optimization lineage
- T18 First end-to-end validation

## 2.2 v0.2-Full

在 MVP 跑通后，再做研究效率提升：

- T05 Frozen expansion
- T06 Observability polish
- T07 Family tracking
- T08 Strategy guidance
- T09 Feedback wording refinement
- T10 Champion baseline hints
- T11 Screening rebalance
- T15b Bayesian optimizer
- T17b CLI/report polish

这个拆法的核心思想是：

> **先把 v0.2 的核心差异化能力做实，再做搜索效率和报告层的增强。**

---

## 3. Workstream A — Foundation 细化设计

### 3.1 T01 — Deterministic Runner Environment

**当前现状**：
`runtime/subprocess_runner.py::_build_clean_env()` 只保留 `PATH`, `PYTHONPATH`。

**设计决策**：
增加固定环境变量：

```python
_ENV_PASSTHROUGH = {"PATH", "PYTHONPATH"}
_ENV_FIXED = {"PYTHONHASHSEED": "0"}


def _build_clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in _ENV_PASSTHROUGH}
    env.update(_ENV_FIXED)
    return env
```

**说明**：

- 不引入更多 passthrough 环境变量
- `PYTHONHASHSEED=0` 是唯一新增的 fixed env
- 该 fix 是“去除环境噪声”，不是放松 V5

**测试**：

1. `_build_clean_env()` 单元测试
2. mock operator 使用 `set` 派生迭代顺序，验证固定 seed 后行为一致
3. 现有 runner tests 全 pass

---

### 3.2 T02 — V5 Diagnostics Enhancement

**当前现状**：
`verification/state_leak.py` 只返回：

```text
non-deterministic output: run1={...} run2={...}
```

这不足以支持：

- 快速判断是环境问题还是候选逻辑问题
- 回放失败案例
- 后续让 LLM/人诊断具体差异

**最小设计目标**：

#### 输出物
对一次 V5 failure，至少产生：

1. `run1_ref`：第一次完整输出 JSON 路径
2. `run2_ref`：第二次完整输出 JSON 路径
3. `diff_keys`：发生差异的 objective keys
4. `candidate_archive_ref`：候选 operators 快照路径
5. `classification`：`ENV_NONDETERMINISM | CANDIDATE_NONDETERMINISM | UNKNOWN_NONDETERMINISM`

#### detail 结构
建议 detail 保持 JSON string，兼容现有 `CheckResult.detail: str`

```python
{
  "classification": "CANDIDATE_NONDETERMINISM",
  "run1_objective": {...},
  "run2_objective": {...},
  "diff_keys": ["subcategory_splits", "total_cost"],
  "run1_ref": ".../v5_run1_xxx.json",
  "run2_ref": ".../v5_run2_xxx.json",
  "candidate_archive_ref": ".../archive/branch_xxx"
}
```

#### 分类规则（v0.2 够用版）

- 如果 `PYTHONHASHSEED` 未固定，不做分类，直接 `UNKNOWN_NONDETERMINISM`
- 如果已固定且两次 objective 不同，默认 `CANDIDATE_NONDETERMINISM`
- 只有在 runner/IO 层自身异常时才落 `ENV_NONDETERMINISM`

也就是说，v0.2 不追求完美归因，只追求：

> **结构化 + 可回放 + 粗分类可解释**

**文件改动建议**：

- `verification/state_leak.py`
- `runtime/workspace.py`（如需增加 archive helper）

---

### 3.3 T03 + T04 — Artifact Track

这两个任务必须视为一条线。

#### 当前问题

`campaign_summary.json` 当前只适合粗读，不适合研究复盘。缺：

- protocol_result 详情
- case feedback 摘要
- verification detail
- stable code archive ref

#### 设计原则

- summary 存**引用**，不存大块源码
- 代码快照由 archive 目录保存
- summary 成为“单文件索引入口”

#### 新增字段（每个 step）

```python
{
  "round": 4,
  "branch_id": "...",
  "decision": "queue_validate",
  "contract_passed": true,
  "verification_passed": true,
  "failure_stage": null,
  "failure_detail": null,
  "hypothesis": {...},
  "patch": {...},
  "protocol_result": {
    "stage": "screening",
    "win_rate": 0.95,
    "median_delta": 750000.0,
    "ci_low": 500000.0,
    "ci_high": 900000.0,
    "gate_outcome": "pass",
    "reason_codes": ["SCREEN_PASS"]
  },
  "case_feedback_summary": [
    {
      "case_id": "large_2",
      "dominant_result": "win",
      "decisive": "business_aggregation"
    }
  ],
  "verification_detail": null,
  "code_archive_ref": "archive/round_04_branch_xxx/",
  "cache_stats": {"total": 2, "cache_read": 1, "cache_create": 1}
}
```

#### 归档策略

- verification heavy failure 前：归档 candidate operators
- abandon 前：已有 `archive_workspace()`，保留并补稳定引用
- promote 后：champion snapshot 本身就是长期 artifact，不重复 archive

**文件改动建议**：

- `core/campaign.py`
- `runtime/workspace.py`

---

## 4. Workstream C — Parameter Layer 细化设计

这是 v0.2 的主线。

---

### 4.1 总体原则

parameter layer 必须满足四个约束：

1. **不改变结构搜索协议**
2. **不绕过 champion 生命周期**
3. **评估语义与现有 lexicographic 规则一致**
4. **搜索过程不污染 champion snapshot**

因此参数搜索流程应为：

```text
branch promoted
    ↓
create champion snapshot
    ↓
clone optimization workspace from champion snapshot
    ↓
run weight search in optimization workspace
    ↓
if improved: write best weights back to champion snapshot registry.yaml
    ↓
record lineage
    ↓
reload champion operator metadata from registry
```

---

### 4.2 T12 — Parameter Config + Models

#### 新增配置模型
建议在 `config/problem.py` 中新增：

```python
class ParameterSearchConfig(BaseModel):
    enabled: bool = True
    trigger: Literal["on_promote"] = "on_promote"
    target: Literal["operator_weights"] = "operator_weights"
    strategy: Literal["random_local", "bayesian"] = "random_local"
    n_initial_random: int = 8
    n_iterations: int = 8
    n_eval_seeds: int = 2
    weight_bounds: tuple[float, float] = (0.05, 5.0)
    eval_cases: List[str] = Field(default_factory=list)
```

然后挂到 `ProblemSpec`：

```python
parameter_search: ParameterSearchConfig = Field(default_factory=ParameterSearchConfig)
```

#### 为什么默认不用 bayesian

因为 v0.2 第一阶段先要求 plumbing 正确：

- 能读 registry
- 能写 registry
- 能跑 evaluator
- 能在 promote 后自动搜索
- 能存 lineage

这些比 BO 本身更关键。

#### 新增模型
在 `core/models.py` 中新增：

```python
@dataclass(frozen=True)
class WeightConfig:
    weights: Dict[str, float]
    source: Literal["uniform", "optimized", "manual"]
    optimization_id: Optional[str] = None


@dataclass(frozen=True)
class WeightOptimizationResult:
    baseline_weights: Dict[str, float]
    best_weights: Dict[str, float]
    baseline_score: float
    best_score: float
    improved: bool
    n_evaluations: int
    elapsed_seconds: float
    observations_ref: str
```

---

### 4.3 T13 — Registry Weight IO（基于 PoolManager）

#### 设计决策
不建议单独新建 `registry_writer.py` 作为主实现。

更合理的是：

- 在 `runtime/pool_manager.py` 上新增 read/update helper
- parameter layer 直接调用这些 helper

#### 建议新增接口

```python
def read_registry(registry_path: str) -> Dict[str, OperatorConfig]:
    ...


def read_weights(registry_path: str) -> Dict[str, float]:
    ...


def update_weights(registry_path: str, weights: Dict[str, float]) -> None:
    ...
```

#### 行为要求

- 只改 `weight`
- 保持 `name/file_path/category/class_name` 不变
- 若存在 registry 中没有的 weight key：报错
- 若 registry 中存在但 weight map 缺失：报错

也就是说：

> **参数搜索不允许偷偷改 pool 结构，只能改权重。**

---

### 4.4 T14 — Weight Evaluator

#### 评估语义
不要引入第二套 scoring 规则。

当前系统已经有：

- `compare_with_breakdown()`
- `compute_delta()`
- screening / validation 的 practical-significance 逻辑

因此 evaluator 应直接复用 `compute_delta()` 语义。

#### 建议签名

```python
def evaluate_weights(
    weights: Dict[str, float],
    workspace: str,
    cases: List[str],
    seeds: List[int],
    runner: Runner,
    time_limit_sec: int,
) -> float:
    """Return median_delta under the current lexicographic scoring rule."""
```

#### 核心流程

```text
write weights -> run solver on all (case, seed) pairs -> compute delta per pair -> median
```

#### eval_cases 默认规则

如果 `parameter_search.eval_cases == []`：

- 默认使用 screening split

如果用户显式配置：

- 使用配置值

该 fallback 逻辑只实现一次，放在 parameter search 初始化阶段。

#### workspace 规则

- evaluator 只在 optimization workspace 中运行
- 不允许直接修改 champion snapshot
- 每次评估都写同一个 optimization workspace 的 registry.yaml

---

### 4.5 T15 — Optimizer 分两层

## T15a — Random + Local Perturbation（MVP）

这是 v0.2 第一阶段推荐实现。

#### 搜索空间

- log-space
- bounds = `(0.05, 5.0)`
- 最终由 solver/registry 使用原值

#### 迭代策略

1. 评估 baseline
2. 做 `n_initial_random` 个随机样本
3. 选择当前 best
4. 在 best 周围做局部扰动 `n_iterations` 轮
5. 返回 best observed

#### 局部扰动建议

```python
log_w_new = log_w_best + Normal(0, sigma)
```

其中 `sigma` 随轮数衰减。

#### 优点

- 无额外依赖
- 行为稳定，可测试
- 先把 plumbing 跑通

## T15b — Bayesian Optimizer（增强版）

在 T15a 跑通后再做。

可选实现路线：

1. `skopt`
2. `sklearn.gaussian_process` + custom acquisition
3. 保持 random/local，不在 v0.2 强上 BO

当前建议：

> **不要让 BO 依赖成为 v0.2 主线阻塞点。**

---

### 4.6 T16 — Promote Hook Integration

#### 正确挂载点
`core/campaign.py::_on_promote()`

#### 当前问题
当前 `_on_promote()`：

- 创建 champion snapshot
- 用旧 `operator_pool` 构造新 `ChampionState`
- 标记其他分支 stale

问题在于：

- 新 champion 的 registry.yaml 可能已发生结构变化
- 直接复制旧 `operator_pool` 可能失真

#### 新版流程

```python
1. create promoted snapshot
2. if parameter_search.enabled:
       create optimization workspace from promoted snapshot
       run weight optimizer
       if improved:
           update champion snapshot registry.yaml
3. rebuild operator_pool from final registry.yaml
4. construct final ChampionState
5. mark all other branches stale
```

#### 新增成员
在 `CampaignManager.__init__()` 中增加：

```python
weight_optimizer: Optional[WeightOptimizer] = None
```

但更推荐的做法是：

- 传入 `problem_spec.parameter_search`
- Campaign 内部自己构造 optimizer 所需组件

原因是 CLI / campaign / test 都更容易统一。

---

### 4.7 T17 — Lineage + CLI

## T17a — 最小 lineage

`lineage/registry.py` 新增表：

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
    observations_ref       TEXT,
    timestamp              TEXT NOT NULL
);
```

新增 helper：

```python
def record_weight_optimization(...): ...
def query_weight_optimizations(...): ...
```

## T17b — CLI

基于当前 `cli/main.py`，新增：

```bash
scion optimize-weights --campaign-dir ...
scion inspect weights --campaign-dir ...
```

说明：

- 当前 CLI 是 `inspect_app` / `report_app` 两个 sub-app
- `inspect weights` 比 `inspect --weights` 更贴合当前 typer 结构

建议保持现有风格，不要为单一功能破坏命令树。

---

### 4.8 T18 — First End-to-End Validation

第一轮 T18 的验收不要定太高。

#### 最小成功标准

1. campaign 中出现一次 promote
2. promote 后自动触发参数搜索
3. 搜索结果写入 `weight_optimizations`
4. 若 improved，champion snapshot 中 `registry.yaml` 被更新
5. 可通过 CLI 读取优化记录
6. frozen holdout 上能出一份 baseline vs optimized 的对比表

第一轮 T18 **不要求**：

- BO 实现
- family tracking
- screening rebalance
- champion baseline hints

---

## 5. Workstream B — Search Efficiency 细化设计

这部分重要，但不应阻塞 MVP。

---

### 5.1 T07 — Family Tracking

#### 当前缺失
代码中完全不存在 `HypothesisFamily` / `family_tracker`。

#### 建议新增文件

- `memory/family_tracker.py`

#### 建议数据结构

```python
@dataclass
class HypothesisFamily:
    family_id: str
    mechanism_label: str
    action_pattern: str
    locus_pattern: str
    member_count: int
    success_count: int
    failure_count: int
```

#### family label 规则
仅做 rule-based，不用 embedding。

建议标签来源：

- action
- change_locus
- hypothesis_text keyword patterns

例如：

- `subcategory`, `merge`, `consolidate`, `purify` → `subcategory_consolidation`
- `swap`, `exchange` → `swap_move`
- `rebuild`, `destroy`, `repair` → `destroy_rebuild`

#### 验收要求
使用 v0.1 的 10 个 hypothesis 文本回测：

- 7 个“subcategory consolidation”变体必须被聚到同一 family 或最多两个相邻 family

---

### 5.2 T08 — Strategy Guidance

#### 注入点
建议新增 `strategy_guidance` block，单独进入 hypothesis context。

不要把它埋在 experiment history 里，否则：

- 不显眼
- 测试困难
- prompt 对比不清楚

#### 建议结构

```text
## Strategy Guidance
- The last 3 hypotheses all targeted family 'subcategory_consolidation' and failed.
- You have not tried action=modify yet.
- You have not explored order_level operators yet.
```

#### 触发条件

1. 最近 3 次同 family failure
2. 最近 3+ 次全是 create_new
3. 最近 5+ 次没有 order_level

---

### 5.3 T09 — Richer Feedback Rendering

现有 `_render_case_feedback()` 已经能工作。

v0.2 只需把：

```text
decisive=business_aggregation deltas: splits=+1.0, cost=-200.0
```

改为更具解释性的文本：

```text
decisive: business_aggregation
candidate increased splits by 1, so this case is strictly worse even though cost improved by 200
```

不改数据结构，不改 protocol。

---

### 5.4 T10 — Champion Baseline Hints

只做最小版本：

- 每个 case 取 champion 一组 baseline objective
- prompt 中提醒：
  - `splits already 0`
  - `only cost can improve`

不做 per-seed baseline 展开。

---

### 5.5 T11 — Screening Set Rebalance

建议：

- screening 中保留 small + medium 主体
- 额外加入 2 个 large
- frozen 保持大规模异质性

目的：

- 提前暴露“小实例好看，大实例失效”的算子

---

## 6. 建议模块布局（v0.2 目标形态）

```text
scion/scion/
├── parameter/
│   ├── __init__.py
│   ├── evaluator.py
│   ├── optimizer.py
│   └── search_space.py
│
├── runtime/
│   └── pool_manager.py         # 扩展 read/update weights
│
├── memory/
│   └── family_tracker.py       # 新增
│
├── lineage/
│   └── registry.py             # 新增 weight_optimizations table
│
├── core/
│   └── campaign.py             # _on_promote hook + richer summary
│
├── verification/
│   └── state_leak.py           # richer V5 diagnostics
│
└── cli/
    └── main.py                 # optimize-weights / inspect weights
```

---

## 7. 接口草图

### 7.1 Pool weight IO

```python
# runtime/pool_manager.py

def read_registry(registry_path: str) -> Dict[str, OperatorConfig]: ...

def read_weights(registry_path: str) -> Dict[str, float]: ...

def update_weights(registry_path: str, weights: Dict[str, float]) -> None: ...
```

### 7.2 Evaluator

```python
# parameter/evaluator.py

def evaluate_weights(
    weights: Dict[str, float],
    workspace: str,
    cases: List[str],
    seeds: List[int],
    runner: Runner,
    time_limit_sec: int,
) -> float: ...
```

### 7.3 Optimizer

```python
# parameter/optimizer.py

class RandomLocalWeightOptimizer:
    def __init__(self, search_space, evaluator_fn, seed: int = 0) -> None: ...
    def optimize(self) -> WeightOptimizationResult: ...
```

### 7.4 Registry

```python
# lineage/registry.py

def record_weight_optimization(...): ...

def query_weight_optimizations(
    campaign_id: Optional[str] = None,
    champion_version: Optional[int] = None,
) -> List[Dict[str, Any]]: ...
```

---

## 8. 非目标

v0.2 不做：

- solver framework 结构搜索
- acceptance criterion / VNS 主循环结构搜索
- 多问题泛化
- embedding-based family clustering
- 异步参数搜索调度
- 分布式 optimizer

---

## 9. 最终判断

一个好的 v0.2 不是“把 task manifest 写完整”，而是让下面这条链条第一次可靠成立：

```text
promote
  -> optimize weights
  -> persist result
  -> inspect later
  -> compare with baseline
```

只要这个闭环成立，Scion 就真正从 v0.1 的“结构搜索框架”进化到了 v0.2 的“结构 + 参数两层搜索框架”。
