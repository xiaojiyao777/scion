# Scion v0.2 — Task Manifest

*Date: 2026-04-09*
*Parent: scion-v0.2-design.md*
*Branch: v0.2-dev*

---

## 依赖图

```
Phase 1 — Foundation
  T01 ──→ T02 ──→ (validation campaign)
  T03 ──┐
  T04 ──┤──→ (validation campaign)
  T05 ──┘
  T06 ────→ (validation campaign)

Phase 2 — Search Efficiency
  T07 ──→ T08 ──→ (validation campaign)
  T09 ──┐
  T10 ──┤──→ (validation campaign)
  T11 ──┘

Phase 3 — Parameter Layer
  T12 ──→ T13 ──→ T14 ──→ T15 ──→ T16 ──→ T18
                                    T17 ──→ T18
```

Phase 1 和 Phase 2 可并行开发，但 Phase 1 的 validation campaign 必须先跑。
Phase 3 可在 Phase 1 完成后启动（不硬依赖 Phase 2）。

---

## Phase 1 — Foundation & Instrumentation

### T01: Runner Deterministic Environment

**优先级**: P0 — 所有后续 campaign 的前置条件

**修改文件**:
- `scion/scion/runtime/subprocess_runner.py`

**具体改动**:
```python
# _build_clean_env() 中新增
_ENV_PASSTHROUGH = {"PATH", "PYTHONPATH"}
_ENV_FIXED = {"PYTHONHASHSEED": "0"}

def _build_clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in _ENV_PASSTHROUGH}
    env.update(_ENV_FIXED)
    return env
```

**测试**:
- 单元测试：验证 `_build_clean_env()` 输出包含 `PYTHONHASHSEED=0`
- 集成测试：构造一个使用 `set` 遍历的 mock operator，跑两次 V5，确认 pass
- 回归测试：现有 test suite 全 pass

**验收**: V5 检查在固定环境下行为一致

---

### T02: V5 Diagnostics Enhancement

**优先级**: P0

**修改文件**:
- `scion/scion/verification/state_leak.py`
- `scion/scion/core/models.py`（CheckResult 可能需要扩展 detail 结构）

**具体改动**:

1. `check_state_leak()` 保存两次 run 的完整 output JSON 到 metrics_dir:
   ```python
   # 保存到 {metrics_dir}/v5_run1_{uuid}.json 和 v5_run2_{uuid}.json
   ```

2. 失败时 detail 包含结构化信息:
   ```python
   detail = json.dumps({
       "run1_objective": obj1,
       "run2_objective": obj2,
       "diff_keys": [k for k in obj1 if obj1[k] != obj2.get(k)],
       "run1_ref": run1_path,
       "run2_ref": run2_path,
   })
   ```

3. 新增辅助函数保存候选代码 snapshot:
   ```python
   def _archive_candidate_code(workspace: str, archive_dir: str, tag: str) -> str:
       """Copy operator files to archive. Returns archive path."""
   ```

**测试**:
- 构造 mock operator 触发 V5 failure，验证 detail JSON 结构正确
- 验证归档路径存在且包含算子代码

**验收**: V5 failure detail 从一行字变成结构化 JSON + 归档引用

---

### T03: Campaign Summary Schema Upgrade

**优先级**: P1

**修改文件**:
- `scion/scion/core/campaign.py`（summary 生成逻辑）
- 或新建 `scion/scion/core/report.py`

**具体改动**:

campaign_summary 的每个 step 增加:
```python
{
    "round": 4,
    # ... existing fields ...
    "protocol_result": {
        "stage": "screening",
        "win_rate": 0.95,
        "median_delta": 750000.0,
        "gate_outcome": "pass",
        "case_feedback_summary": [
            {"case_id": "scr_m01", "dominant_result": "win", "decisive": "business_aggregation"},
            # ...
        ]
    },
    "code_content": "class SubcatMergeSafe(Operator):\n    ...",
    # 或
    "code_archive_ref": "archive/round_04_subcat_merge_safe.py",
    "verification_detail": null,  # 或 V5 的结构化 JSON
    "cache_stats": {"total": 2, "cache_read": 1, "cache_create": 1}
}
```

**测试**:
- Mock campaign 跑 3 轮，验证 summary JSON 包含所有新字段
- 验证 code_content 或 archive_ref 非空

**验收**: 单一 JSON 文件可还原 campaign 全貌，无需查 SQLite

---

### T04: Candidate Code Archiving for Failed Runs

**优先级**: P1

**修改文件**:
- `scion/scion/core/campaign.py`（`_run_explore_step` 中 verification failure 路径）
- `scion/scion/runtime/workspace.py`（新增 `archive_operator_files` 方法）

**具体改动**:

在 verification failure 退出前，把 candidate workspace 的 operators/ 归档:
```python
if not vresult.passed:
    archive_path = self._materializer.archive_operator_files(
        workspace, bid, self._round_num
    )
    # archive_path 写入 step record / summary
```

归档目录: `{campaign_dir}/archives/round_{N}_{branch_short}/`

**测试**:
- 构造 V5 failure，验证归档目录存在且包含 .py 文件
- 验证归档路径出现在 campaign summary

**验收**: 所有被拦截的候选代码可事后查看

---

### T05: Frozen Holdout Expansion

**优先级**: P1

**修改文件**:
- `surrogate/data/generate_v3.py`（或新建 generate_v4.py）
- `scion/problems/warehouse_delivery/split_manifest.yaml`
- `scion/problems/warehouse_delivery/seed_ledger.yaml`

**具体改动**:
- 新增 4-8 个 frozen instances（large + xlarge 混合）
- 确保与 screening/validation cases 不重叠
- 每个 instance 通过区分度验证（≥2/3 seeds distinct）
- 更新 split_manifest 和 seed_ledger

**测试**:
- 区分度验证脚本
- `scion init` + `scion run` 能加载新 manifest

**验收**: Frozen holdout ≥ 8 instances，规模跨度覆盖 medium → xlarge

---

### T06: Observability Fields in Report

**优先级**: P2

**修改文件**:
- `scion/scion/core/campaign.py`（`get_state` / report 输出）
- `scion/scion/cli/main.py`（`scion report` 子命令）

**具体改动**:

Report 增加:
```python
{
    "cache_hit_rate": 0.85,
    "verification_breakdown": {
        "V1_syntax": {"total": 10, "passed": 10},
        "V5_state_leak": {"total": 10, "passed": 6, "failed": 4},
        # ...
    },
    "action_coverage": {"create_new": 8, "modify": 1, "remove": 1},
    "locus_coverage": {"vehicle_level": 7, "order_level": 3},
}
```

**测试**:
- Mock campaign 后 `scion report` 输出包含新字段

**验收**: 一眼能看出 campaign 的效率指标

---

## Phase 2 — Outer-loop Search Efficiency

### T07: Hypothesis Family Tracking

**优先级**: P1

**新增文件**:
- `scion/scion/memory/family_tracker.py`

**修改文件**:
- `scion/scion/core/models.py`（新增 HypothesisFamily dataclass）
- `scion/scion/core/campaign.py`（hypothesis 生成后 assign family）
- `scion/scion/lineage/registry.py`（新增 hypothesis_families 表）

**具体改动**:

```python
@dataclass
class HypothesisFamily:
    family_id: str
    mechanism_label: str          # rule-based: 从 hypothesis_text 提取关键词
    action_pattern: str           # create_new / modify / remove
    locus_pattern: str            # vehicle_level / order_level
    member_count: int
    success_count: int
    failure_count: int
```

Family assignment 用 rule-based heuristic:
```python
def assign_family(hypothesis: HypothesisProposal, existing: list[HypothesisFamily]) -> str:
    """基于 action + locus + keyword 匹配 assign family。"""
    keywords = _extract_mechanism_keywords(hypothesis.hypothesis_text)
    # 匹配已有 family 或创建新 family
```

**测试**:
- 用 v0.1 的 10 个 hypothesis 文本验证：至少 7 个被归入同一 family
- 新 mechanism 自动创建新 family

**验收**: Campaign report 可展示 family 分布

---

### T08: Strategy-shift Guidance

**优先级**: P1

**修改文件**:
- `scion/scion/proposal/context_manager.py`（`_build_experiment_history` 或新 helper）

**具体改动**:

在 hypothesis context 的 user prompt 中注入 guidance block:

```python
def _build_strategy_guidance(
    step_history: list[StepRecord],
    family_tracker: FamilyTracker,
    branch_id: str,
) -> str:
    """连续 N 次同 family 失败 → 切换建议；locus 覆盖不均 → 引导探索。"""
    guidance_lines = []

    # 1. 连续同 family 失败
    recent_families = [...]
    if len(set(recent_families[-3:])) == 1:
        guidance_lines.append(
            f"⚠️ The last 3 hypotheses all targeted '{recent_families[-1]}' and failed. "
            f"Try a fundamentally different mechanism."
        )

    # 2. Action 单一性
    action_counts = Counter(s.hypothesis.action for s in step_history)
    if action_counts.get("modify", 0) == 0 and len(step_history) >= 3:
        guidance_lines.append(
            "💡 You haven't tried 'modify' yet. Consider improving an existing operator "
            "rather than creating a new one."
        )

    # 3. Locus 覆盖
    locus_counts = Counter(s.hypothesis.change_locus for s in step_history)
    if locus_counts.get("order_level", 0) == 0 and len(step_history) >= 5:
        guidance_lines.append(
            "💡 All hypotheses so far target vehicle_level. Try order_level operators."
        )

    return "\n".join(guidance_lines) if guidance_lines else ""
```

**测试**:
- 构造 3 轮 same-family-failure 的 step_history，验证 guidance 出现
- 构造 5 轮 all-create_new 的 history，验证 modify 建议出现

**验收**: Hypothesis prompt 中出现动态 guidance

---

### T09: Richer Case Feedback Rendering

**优先级**: P2

**修改文件**:
- `scion/scion/proposal/context_manager.py`（`_render_case_feedback`）

**具体改动**:

改善渲染清晰度:
```python
# Before:
#   decisive=business_aggregation  deltas: splits=+1.0, cost=-200.0

# After:
#   decisive: subcategory_splits increased (+1) — strictly worse regardless of cost
#   deltas: splits=+1 (BAD), cost=-200 (good but overridden by splits)
```

**测试**: 渲染函数单元测试

---

### T10: Champion Baseline Hints

**优先级**: P2

**修改文件**:
- `scion/scion/proposal/context_manager.py`
- `scion/scion/protocol/experiment.py`（收集 champion baseline objectives）

**具体改动**:

在 screening 执行时，额外收集 champion 的绝对 objective per case:
```python
champion_baselines = {}
for case in cases:
    for seed in seeds[:1]:  # 只需一个 seed 取 baseline
        champ_r = self.runner.run_solver(champion_ws, case, seed, ...)
        if champ_r.output:
            champion_baselines[case] = champ_r.output.objective
```

渲染到 experiment_history:
```
case scr_m01: champion baseline — splits=0, cost=5100
  → splits already optimal. Only cost improvements can win.
```

**测试**: Mock runner 测试 baseline 收集和渲染

---

### T11: Screening Set Rebalance

**优先级**: P2

**修改文件**:
- `scion/problems/warehouse_delivery/split_manifest.yaml`

**具体改动**:
- 将 screening 从纯 small/medium 改为 small + medium + 2 large
- 保持 validation 和 frozen 不变
- 更新 seed_ledger 如需要

**测试**: `scion init` 加载新 manifest 成功

---

## Phase 3 — Parameter Layer Search

### T12: Parameter Data Models + Config

**优先级**: P0（Phase 3 入口）

**新增文件**:
- `scion/scion/parameter/__init__.py`
- `scion/scion/parameter/search_space.py`

**修改文件**:
- `scion/scion/core/models.py`（WeightConfig, WeightOptimizationResult）
- `scion/scion/config/problem.py`（parameter_search 配置段）

**具体改动**:

models.py:
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

search_space.py:
```python
@dataclass(frozen=True)
class ParameterSearchSpace:
    operator_names: Tuple[str, ...]
    weight_bounds: Tuple[float, float] = (0.05, 5.0)
    n_initial_random: int = 8
    n_iterations: int = 20
    n_eval_seeds: int = 3
    eval_cases: Tuple[str, ...] = ()
```

problem.yaml 新增段:
```yaml
parameter_search:
  enabled: true
  trigger: "on_promote"
  target: "operator_weights"
  strategy: "bayesian"
  n_initial_random: 8
  n_iterations: 20
  n_eval_seeds: 3
  weight_bounds: [0.05, 5.0]
```

**测试**: Pydantic/dataclass 校验 + config 加载测试

---

### T13: Registry Writer

**优先级**: P1

**新增文件**:
- `scion/scion/parameter/registry_writer.py`

**具体改动**:
```python
def write_weights(registry_path: str, weights: Dict[str, float]) -> None:
    """读 registry.yaml → 更新 weight 字段 → 写回。保持其余字段不变。"""
```

```python
def read_weights(registry_path: str) -> Dict[str, float]:
    """从 registry.yaml 读取当前权重。"""
```

**测试**:
- 写入后读回验证一致
- 不破坏 registry 其余字段（class_name, file_path 等）

---

### T14: Weight Evaluation Function

**优先级**: P1

**新增文件**:
- `scion/scion/parameter/evaluator.py`

**具体改动**:
```python
def evaluate_weights(
    weight_vector: Dict[str, float],
    champion_workspace: str,
    cases: List[str],
    seeds: List[int],
    runner: Runner,
    time_limit: int,
) -> float:
    """
    1. 写入 weight_vector 到 workspace 的 registry.yaml
    2. 对每个 (case, seed) 跑 solver
    3. 标量化: score = -(splits * 100_000 + total_cost)
    4. 返回 median score
    """
```

**测试**:
- Mock runner 验证标量化逻辑
- 验证 registry 写入 → solver 调用 → 结果收集的完整链路

---

### T15: Bayesian Optimizer

**优先级**: P1

**新增文件**:
- `scion/scion/parameter/optimizer.py`

**具体改动**:
```python
class WeightOptimizer:
    """Bayesian optimization for operator weight tuning.

    Uses scipy.optimize.minimize with GP surrogate.
    Search in log-space for natural positivity constraint.
    """

    def __init__(self, search_space, evaluator_fn):
        ...

    def optimize(self) -> WeightOptimizationResult:
        """
        1. Random initialization (n_initial_random)
        2. GP fit + acquisition function (n_iterations)
        3. Return best observed
        """
```

如果 scipy GP 实现复杂度过高，MVP 降级为:
```python
class RandomSearchOptimizer:
    """Random + local perturbation fallback."""
```

接口相同，可替换。

**测试**:
- 用简单凸函数验证 optimizer 能找到最优
- Mock evaluator 验证迭代过程

---

### T16: Campaign Integration — Promote Hook

**优先级**: P0（Phase 3 集成点）

**修改文件**:
- `scion/scion/core/campaign.py`（`_on_promote` 方法）

**具体改动**:
```python
def _on_promote(self, branch: Branch) -> None:
    # ... existing promotion logic ...

    # --- v0.2: Weight optimization ---
    if self._weight_optimizer is not None:
        logger.info("Champion v%d: starting weight optimization...", new_version)
        opt_result = self._weight_optimizer.optimize()
        if opt_result.improved:
            write_weights(
                os.path.join(self._champion.code_snapshot_path, "registry.yaml"),
                opt_result.best_weights,
            )
            logger.info(
                "Weights optimized: score %.1f → %.1f",
                opt_result.baseline_score, opt_result.best_score,
            )
        self._record_weight_optimization(opt_result)
```

CampaignManager.__init__ 新增可选参数:
```python
weight_optimizer: Optional[WeightOptimizer] = None
```

**测试**:
- Mock promote → 验证 weight optimization 被调用
- 验证 registry.yaml 被更新
- 验证 lineage 记录被写入

---

### T17: Lineage + CLI + Reporting

**优先级**: P1

**修改文件**:
- `scion/scion/lineage/registry.py`（新增 weight_optimizations 表）
- `scion/scion/cli/main.py`（`scion optimize-weights` 子命令 + `scion inspect` 扩展）

**具体改动**:

Lineage:
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

CLI:
```bash
scion optimize-weights --problem ./problems/warehouse_delivery
# 独立调用，不依赖 campaign 主循环

scion inspect --weights
# 展示 champion 权重历史
```

**测试**: CLI 集成测试

---

### T18: End-to-End Validation

**优先级**: P0（最终验收）

**无新文件**，是集成验证。

**执行步骤**:
1. 跑完整 campaign（PYTHONHASHSEED 固定 + 新 frozen + family tracking）
2. 等待 Promote
3. 验证 Promote 后自动触发权重优化
4. 对比均匀权重 vs 优化权重在 frozen holdout 上的表现
5. 生成 v0.2 experiment report

**验收**:
- 完整 campaign 无崩溃
- 权重优化结果写入 lineage
- A/B 对比数据可用

---

## 任务总览

| Task | 名称 | 优先级 | 新增/修改文件数 | 依赖 |
|---|---|---|---|---|
| T01 | Deterministic env | P0 | 1 修改 | — |
| T02 | V5 diagnostics | P0 | 2 修改 | T01 |
| T03 | Summary schema | P1 | 1-2 修改 | — |
| T04 | Code archiving | P1 | 2 修改 | — |
| T05 | Frozen expansion | P1 | 3 修改/新增 | — |
| T06 | Observability | P2 | 2 修改 | — |
| T07 | Family tracking | P1 | 3 新增/修改 | — |
| T08 | Strategy guidance | P1 | 1 修改 | T07 |
| T09 | Richer feedback | P2 | 1 修改 | — |
| T10 | Champion baseline | P2 | 2 修改 | — |
| T11 | Screening rebalance | P2 | 1 修改 | — |
| T12 | Param data models | P0 | 3 新增/修改 | — |
| T13 | Registry writer | P1 | 1 新增 | T12 |
| T14 | Weight evaluator | P1 | 1 新增 | T12, T13 |
| T15 | Optimizer | P1 | 1 新增 | T14 |
| T16 | Campaign hook | P0 | 1 修改 | T15 |
| T17 | Lineage + CLI | P1 | 2 修改 | T16 |
| T18 | E2E validation | P0 | — | All |

**P0 (must)**: T01, T02, T12, T16, T18 — 5 个任务
**P1 (should)**: T03, T04, T05, T07, T08, T13, T14, T15, T17 — 9 个任务
**P2 (nice-to-have)**: T06, T09, T10, T11 — 4 个任务
