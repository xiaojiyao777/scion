# Sprint C — Parameter Search Close Loop

*Branch: `v0.2-dev`*
*Scope: T15a + T16 + T17a*
*Goal: 把 optimizer、promote hook、lineage 串起来，形成 promote → optimize → persist 闭环*
*前置: Sprint B 已完成（parameter config + models + registry IO + evaluator）*

---

## 0. 开发约束

- **新建 `scion/scion/parameter/optimizer.py`**
- **修改 `scion/scion/core/campaign.py`**（仅 `__init__` 和 `_on_promote`）
- **修改 `scion/scion/lineage/registry.py`**（新增 weight_optimizations 表）
- **不要碰 `proposal/`、`verification/`、`contract/`、`memory/` 目录**
- **不要修改主循环 `run()` 或 `_run_explore_step()`**
- **所有现有 tests 必须继续 pass**
- **每个 task 先写测试，再写实现**

---

## 1. T15a — Random + Local Perturbation Optimizer

### 新建 `parameter/optimizer.py`

```python
"""Weight optimizer: random initialization + local perturbation."""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from scion.core.models import WeightOptimizationResult
from scion.parameter.search_space import ParameterSearchSpace


class RandomLocalWeightOptimizer:
    """Bayesian-free optimizer: random init + local perturbation around best.
    
    Search in log-space for natural positivity constraint.
    """
    
    def __init__(
        self,
        search_space: ParameterSearchSpace,
        evaluator_fn: Callable[[Dict[str, float]], float],
        seed: int = 0,
    ) -> None:
        self._space = search_space
        self._eval_fn = evaluator_fn  # weights -> median_delta
        self._rng = random.Random(seed)
        
    def optimize(self) -> WeightOptimizationResult:
        """Run optimization. Returns result with best weights found."""
        t0 = time.time()
        names = list(self._space.operator_names)
        lo, hi = math.log(self._space.weight_bounds[0]), math.log(self._space.weight_bounds[1])
        
        observations: List[Tuple[Dict[str, float], float]] = []
        
        # Phase 1: evaluate baseline (current weights via eval_fn with no change)
        # The caller should have set up the evaluator to compare against baseline
        
        # Phase 2: random initialization
        for _ in range(self._space.n_initial_random):
            w = self._random_weights(names, lo, hi)
            score = self._eval_fn(w)
            observations.append((w, score))
        
        # Find best so far
        best_w, best_score = max(observations, key=lambda x: x[1])
        
        # Phase 3: local perturbation around best
        for i in range(self._space.n_iterations):
            sigma = 0.3 * (1.0 - i / max(self._space.n_iterations, 1))  # decay
            w = self._perturb(best_w, names, lo, hi, sigma)
            score = self._eval_fn(w)
            observations.append((w, score))
            if score > best_score:
                best_w, best_score = w, score
        
        elapsed = time.time() - t0
        
        # Baseline score is first observation (or 0 if no observations)
        baseline_score = observations[0][1] if observations else 0.0
        baseline_weights = observations[0][0] if observations else {}
        
        return WeightOptimizationResult(
            baseline_weights=baseline_weights,
            best_weights=best_w,
            baseline_score=baseline_score,
            best_score=best_score,
            improved=best_score > baseline_score,
            n_evaluations=len(observations),
            elapsed_seconds=round(elapsed, 1),
            observations_ref="",  # caller fills this if saving to disk
        )
    
    def _random_weights(self, names: List[str], lo: float, hi: float) -> Dict[str, float]:
        return {n: math.exp(self._rng.uniform(lo, hi)) for n in names}
    
    def _perturb(
        self, base: Dict[str, float], names: List[str],
        lo: float, hi: float, sigma: float,
    ) -> Dict[str, float]:
        result = {}
        for n in names:
            log_w = math.log(base[n]) + self._rng.gauss(0, sigma)
            log_w = max(lo, min(hi, log_w))  # clamp
            result[n] = math.exp(log_w)
        return result
```

### 关键设计

- **Log-space 搜索**：权重天然为正
- **Sigma 衰减**：`0.3 * (1 - i/N)`，越到后面扰动越小
- **Deterministic seed**：`random.Random(seed)` 可复现
- **evaluator_fn**：由调用方绑定具体的 evaluate_weights，optimizer 只关心 `weights → score`

### 测试（加到 `tests/test_parameter.py`）

1. `test_optimizer_improves_on_convex_mock` — mock evaluator 为凸函数（如 `-sum((w-1)^2)`），验证 best_score > baseline_score
2. `test_optimizer_is_seed_deterministic` — 相同 seed 跑两次，结果完全一致
3. `test_optimizer_returns_correct_structure` — 验证返回 WeightOptimizationResult 所有字段非 None
4. `test_optimizer_respects_weight_bounds` — 所有输出权重在 [0.05, 5.0] 范围内
5. `test_optimizer_n_evaluations` — 验证 `n_evaluations == n_initial_random + n_iterations`

### 验收

- Mock evaluator 下能找到更优权重
- 行为确定性可复现

---

## 2. T16 — Campaign Promote Hook Integration

### 修改 `core/campaign.py`

#### 2.1 `__init__` 新增参数

```python
def __init__(
    self,
    ...
    *,
    ...
    weight_optimizer_factory: Optional[Callable] = None,
    # factory: (champion_snapshot_path, problem_spec) -> WeightOptimizationResult or None
):
```

或者更简单：传入 `problem_spec.parameter_search` 配置，在 `_on_promote` 内部构造 optimizer。

**推荐方案**：不新增 `__init__` 参数，直接在 `_on_promote` 中读 `self._spec.parameter_search`。这样不需要修改所有 CampaignManager 的调用方。

#### 2.2 修改 `_on_promote`

在当前 `_on_promote` 的末尾（`self._champion = new_champion` 之前），插入权重优化逻辑：

```python
def _on_promote(self, branch: Branch) -> None:
    """Update champion and mark all other active branches stale."""
    bid = branch.branch_id
    ws = self._branch_workspaces.get(bid)
    if ws is None:
        logger.warning("Branch %s promoted but no workspace found", bid)
        return

    new_version = self._champion.version + 1
    
    # Create champion snapshot (existing code)
    try:
        snapshot_path = self._materializer.create_champion_snapshot(...)
    except Exception as exc:
        ...

    # --- v0.2: Weight optimization ---
    param_cfg = self._spec.parameter_search
    if param_cfg.enabled and self._experiment_protocol is not None:
        try:
            opt_result = self._run_weight_optimization(snapshot_path, new_version)
            if opt_result and opt_result.improved:
                from scion.runtime.pool_manager import update_weights
                registry_path = os.path.join(snapshot_path, "registry.yaml")
                update_weights(registry_path, opt_result.best_weights)
                logger.info(
                    "Champion v%d: weights optimized (score %.1f → %.1f)",
                    new_version, opt_result.baseline_score, opt_result.best_score,
                )
            # Record in lineage
            if opt_result:
                self._registry.record_weight_optimization(
                    campaign_id=self._campaign_id,
                    champion_version=new_version,
                    result=opt_result,
                )
        except Exception as exc:
            logger.error("Weight optimization failed for champion v%d: %s", new_version, exc)

    # Rebuild operator_pool from final registry.yaml (critical fix from review-notes)
    from scion.runtime.pool_manager import read_registry
    try:
        final_pool = read_registry(os.path.join(snapshot_path, "registry.yaml"))
    except Exception:
        final_pool = self._champion.operator_pool  # fallback
    
    code_hash = self._materializer.compute_code_hash(ws)
    new_champion = ChampionState(
        version=new_version,
        operator_pool=final_pool,  # <-- 从 registry 重建，不用旧的
        solver_config_hash=self._champion.solver_config_hash,
        code_snapshot_path=snapshot_path,
        code_snapshot_hash=code_hash,
        promoted_at=datetime.now().isoformat(),
    )
    self._champion = new_champion
    stale_ids = self._branch_ctrl.mark_all_stale(new_version)
    ...
```

#### 2.3 新增 `_run_weight_optimization` 方法

```python
def _run_weight_optimization(self, champion_snapshot: str, version: int) -> Optional[WeightOptimizationResult]:
    """Run weight optimization on a copy of the champion snapshot."""
    import shutil
    from scion.parameter.optimizer import RandomLocalWeightOptimizer
    from scion.parameter.evaluator import collect_baseline, evaluate_weights
    from scion.parameter.search_space import ParameterSearchSpace
    from scion.runtime.pool_manager import read_weights
    
    param_cfg = self._spec.parameter_search
    
    # Create evaluation workspace (copy of champion snapshot)
    eval_ws = os.path.join(self._campaign_dir, f"weight_opt_v{version}")
    if os.path.exists(eval_ws):
        shutil.rmtree(eval_ws)
    shutil.copytree(champion_snapshot, eval_ws)
    
    # Determine eval cases (fallback to screening)
    eval_cases = param_cfg.eval_cases
    if not eval_cases:
        eval_cases = list(self._split_manifest.screening)
    # Resolve case paths relative to root_dir
    resolved_cases = []
    for c in eval_cases:
        path = os.path.join(self._spec.root_dir, c) if not os.path.isabs(c) else c
        resolved_cases.append(path)
    
    seeds = list(self._seed_ledger.screening)[:param_cfg.n_eval_seeds]
    
    runner = self._experiment_protocol._runner if self._experiment_protocol else None
    if runner is None:
        logger.warning("No runner available for weight optimization")
        return None
    
    time_limit = self._spec.solver.time_limit_sec if self._spec.solver else 300
    
    # Read current weights
    current_weights = read_weights(os.path.join(eval_ws, "registry.yaml"))
    operator_names = tuple(current_weights.keys())
    
    # Collect baseline
    baseline = collect_baseline(eval_ws, resolved_cases, seeds, runner, time_limit)
    
    # Build search space
    search_space = ParameterSearchSpace(
        operator_names=operator_names,
        weight_bounds=param_cfg.weight_bounds,
        n_initial_random=param_cfg.n_initial_random,
        n_iterations=param_cfg.n_iterations,
        n_eval_seeds=param_cfg.n_eval_seeds,
        eval_cases=tuple(resolved_cases),
    )
    
    # Build evaluator function
    def eval_fn(weights: Dict[str, float]) -> float:
        return evaluate_weights(
            weights=weights,
            workspace=eval_ws,
            cases=resolved_cases,
            seeds=seeds,
            runner=runner,
            time_limit_sec=time_limit,
            baseline_objectives=baseline,
        )
    
    # Run optimizer
    optimizer = RandomLocalWeightOptimizer(search_space, eval_fn, seed=version)
    result = optimizer.optimize()
    
    # Cleanup eval workspace
    try:
        shutil.rmtree(eval_ws)
    except Exception:
        pass
    
    return result
```

### 关键约束

- **优化在 eval workspace 中进行**，不直接改 champion snapshot
- **只有 improved 时才写回** best_weights 到 champion snapshot 的 registry.yaml
- **promote 后从 registry.yaml 重建 operator_pool**（修复 review-notes 中发现的 stale pool 问题）
- **如果没有 experiment_protocol（runner），跳过优化**

### 测试（加到 `tests/test_campaign.py`）

1. `test_on_promote_runs_weight_optimization` — mock CampaignManager + mock runner，验证 promote 后触发 weight optimization
2. `test_on_promote_rebuilds_operator_pool_from_registry` — promote 后 champion.operator_pool 来自 registry.yaml，不是旧的内存副本
3. `test_on_promote_without_parameter_search` — parameter_search.enabled=False 时不触发优化
4. `test_on_promote_without_runner` — experiment_protocol=None 时不触发优化，不崩溃

### 验收

- Mock promote → weight optimization 被调用
- Registry.yaml 被更新（如果 improved）
- Lineage 记录被写入
- 无 runner 时 graceful skip

---

## 3. T17a — Weight Optimization Lineage

### 修改 `lineage/registry.py`

#### 3.1 新增表（在 `__init__` 的 CREATE TABLE 块中）

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
)
```

#### 3.2 新增方法

```python
def record_weight_optimization(
    self,
    campaign_id: str,
    champion_version: int,
    result: WeightOptimizationResult,
) -> str:
    """Record a weight optimization result. Returns optimization_id."""
    import json as _json
    opt_id = str(uuid.uuid4())
    row = {
        "optimization_id": opt_id,
        "campaign_id": campaign_id,
        "champion_version": champion_version,
        "n_operators": len(result.best_weights),
        "n_evaluations": result.n_evaluations,
        "baseline_score": result.baseline_score,
        "best_score": result.best_score,
        "improved": 1 if result.improved else 0,
        "baseline_weights_json": _json.dumps(result.baseline_weights),
        "best_weights_json": _json.dumps(result.best_weights),
        "elapsed_seconds": result.elapsed_seconds,
        "observations_ref": result.observations_ref,
        "timestamp": datetime.now().isoformat(),
    }
    cols = ", ".join(row.keys())
    placeholders = ", ".join(["?"] * len(row))
    sql = f"INSERT INTO weight_optimizations ({cols}) VALUES ({placeholders})"
    with sqlite3.connect(self.db_path) as conn:
        conn.execute(sql, list(row.values()))
    return opt_id


def query_weight_optimizations(
    self,
    campaign_id: Optional[str] = None,
    champion_version: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Query weight optimization records."""
    sql = "SELECT * FROM weight_optimizations WHERE 1=1"
    params = []
    if campaign_id:
        sql += " AND campaign_id = ?"
        params.append(campaign_id)
    if champion_version is not None:
        sql += " AND champion_version = ?"
        params.append(champion_version)
    sql += " ORDER BY timestamp"
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
```

### 测试（加到 `tests/test_lineage.py` 或新建 `tests/test_lineage_weight.py`）

1. `test_weight_optimization_table_created` — 新建 LineageRegistry，验证 weight_optimizations 表存在
2. `test_record_weight_optimization` — 写入一条记录，验证返回 optimization_id
3. `test_query_weight_optimizations_by_version` — 写入 2 条不同 version 的记录，按 version 查询正确
4. `test_query_weight_optimizations_empty` — 空表查询返回空列表

### 验收

- 新表 `weight_optimizations` 正确创建
- 可记录 baseline/best weights 与 score
- 可按 campaign_id / champion_version 查询

---

## 4. 完成后验证

Sprint C 全部完成后：

1. `pytest scion/tests/ -q` — 全量测试 pass
2. 验证 `parameter/optimizer.py` 存在且 RandomLocalWeightOptimizer 可 import
3. Mock promote 场景：`promote → optimize → persist → rebuild champion metadata` 链路在测试中跑通
4. SQLite 中 weight_optimizations 表可读写

---

## 5. 文件改动清单

| 文件 | 改动类型 | Task |
|---|---|---|
| `scion/parameter/optimizer.py` | 新建 | T15a |
| `scion/core/campaign.py` | 修改 `_on_promote` + 新增 `_run_weight_optimization` | T16 |
| `scion/lineage/registry.py` | 新增 weight_optimizations 表 + record/query 方法 | T17a |
| `scion/tests/test_parameter.py` | 新增 optimizer 测试 | T15a |
| `scion/tests/test_campaign.py` | 新增 promote hook 测试 | T16 |
| `scion/tests/test_lineage.py` 或 `test_lineage_weight.py` | 新增 lineage 测试 | T17a |
