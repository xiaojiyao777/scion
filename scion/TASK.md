# Sprint N1 — Objective / Benchmark Layer (W15 迁移 + W1 + W4)

*Branch: `v0.3-dev`*  
*Scope: W15 warehouse 真迁移, W1 scoring decouple, W4 MILP integration*  
*前置: Sprint N0 完成*

---

## 0. 开发约束

- **新建** `scion/scion/problem/` 模块（contracts, spec, objectives, loader）
- **新建** `scion/problems/toy_tsp/` MWE
- **新建** `scion/scion/tests/test_problem_adapter.py`
- **不动** `core/campaign.py`（N0 不改 core 调用方式，N1 再切）
- **不动** `protocol/evaluation.py`（现有 lexicographic_compare 保留）
- **不动** `problems/warehouse_delivery/`（N1 再做 adapter 封装）
- 所有现有 tests 必须继续 pass
- 使用 `/home/clawd/miniconda3/envs/claw/bin/python -m pytest`

---

## 1. T1 — ProblemAdapter Protocol + 数据类型

### 新建 `scion/scion/problem/contracts.py`

核心类型：
- `CheckReport(frozen dataclass)`: passed: bool, reasons: tuple[str, ...]
- `LowerBoundEstimate(frozen dataclass)`: metric_name, value, kind ("hard"|"instance"|"heuristic"), note
- `SolverArtifact(frozen dataclass)`: raw_output, objective, feasible, normalized_solution
- `ProblemAdapter(Protocol, runtime_checkable)`: 9 个方法

ProblemAdapter 方法清单：
1. `render_problem_summary() -> str`
2. `render_operator_interface() -> str`
3. `load_instance(instance_path: str) -> Any`
4. `deserialize_solver_output(raw_output, instance) -> SolverArtifact`
5. `check_solution_consistency(artifact, instance) -> CheckReport`
6. `check_feasibility(artifact, instance) -> CheckReport`
7. `recompute_objective(artifact, instance) -> Mapping[str, int|float]`
8. `estimate_lower_bound(metric_name, instance_paths) -> LowerBoundEstimate | None`
9. `compare_objectives(candidate, champion) -> ObjectiveComparison`

接口参考：`reviews/v0.3-design-detail-plan.md` §3.4

### 验收
- [x] import 成功
- [x] `isinstance(adapter, ProblemAdapter)` 可用

---

## 2. T2 — ProblemSpecV1 Strict Schema

### 新建 `scion/scion/problem/spec.py`

- Pydantic BaseModel with `model_config = ConfigDict(extra="forbid")`
- 辅助 spec：ObjectiveMetricSpec, OperatorInterfaceSpec, OperatorCategorySpec, LLMHintsSpec, FamilyTaxonomySpec, ProblemAdapterRef
- ProblemSpecV1 字段：id, display_name, root_dir, description, search_space, solver, parameter_search, operator_interface, objectives, llm_hints, family_taxonomy, adapter
- `@model_validator`: objectives 唯一性, priority 连续性, adapter import_path 前缀校验

接口参考：`reviews/v0.3-design-detail-plan.md` §3.3

### 验收
- [x] 合法 YAML 加载成功
- [x] 非法字段被拒绝（extra="forbid"）
- [x] priority 不连续时报错

---

## 3. T3 — Generic Objective Comparator

### 新建 `scion/scion/problem/objectives.py`

- `MetricComparison(frozen)`: name, candidate_value, champion_value, signed_delta, relation, decisive
- `ObjectiveComparison(frozen)`: outcome ("win"|"loss"|"tie"), decisive_metric, scalar_delta, metrics
- `compare_lexicographic(metric_specs, candidate, champion) -> ObjectiveComparison`

### 验收
- [x] win/loss/tie 各种组合覆盖
- [x] 与现有 `protocol/evaluation.py` 的 `lexicographic_compare` 行为一致（property-based 对比）

---

## 4. T4 — Adapter Loader

### 新建 `scion/scion/problem/loader.py`

- `load_problem_adapter(spec: ProblemSpecV1) -> ProblemAdapter`
- 路径校验：pinned to `scion.problems.*`
- 动态 import (`importlib.import_module` + `getattr`)
- Protocol isinstance 检查
- `ProblemAdapterLoadError(RuntimeError)` 异常

### 验收
- [x] 能加载 toy_tsp adapter
- [x] 路径不合法（不以 `scion.problems.` 开头）时抛 ProblemAdapterLoadError
- [x] 加载的类不满足 Protocol 时抛错

---

## 5. T5 — toy_tsp MWE

### 新建 `scion/problems/toy_tsp/`

```
problems/toy_tsp/
├── __init__.py
├── adapter.py          # ToyTspAdapter(ProblemAdapter)
├── models.py           # TspInstance, TspSolution
├── oracle.py           # tour 有效性 + 距离计算
├── solver.py           # nearest-neighbor + 2-opt
├── operators/
│   ├── __init__.py
│   └── two_opt.py      # 2-opt 算子
├── data/
│   ├── tsp_10.json     # 10 点实例
│   └── tsp_20.json     # 20 点实例
├── problem.yaml        # ProblemSpecV1 格式
└── tests/
    └── test_tsp.py     # 基本冒烟
```

要求：
- ToyTspAdapter 实现 ProblemAdapter 的全部 9 个方法
- 极简实现，不追求质量
- `estimate_lower_bound` 可返回 None（或用简单的 MST lower bound）

### 验收
- [x] `load_problem_adapter` 可加载
- [x] 所有 Protocol 方法可调用且返回正确类型
- [x] solver 能在 toy instance 上跑出合法 tour

---

## 6. T6 — problem 模块入口 + 测试

### 新建 `scion/scion/problem/__init__.py`

导出公共 API：
- ProblemAdapter, ProblemSpecV1, ProblemAdapterRef
- ObjectiveMetricSpec, ObjectiveComparison, MetricComparison
- CheckReport, LowerBoundEstimate, SolverArtifact
- load_problem_adapter, compare_lexicographic

### 新建 `scion/scion/tests/test_problem_adapter.py`

测试清单：
1. ProblemSpecV1 schema 验证（合法 / extra field / priority 不连续 / adapter 路径非法）
2. adapter loader（正常加载 / 路径非法 / Protocol 不满足）
3. generic comparator 单元测试（win / loss / tie / multi-metric / tie-tolerance）
4. toy_tsp adapter 集成测试（load_instance + deserialize + check_feasibility + recompute_objective + compare）

### 验收
- [x] `pytest scion/scion/tests/test_problem_adapter.py` 全绿
- [x] `pytest` 全量不回退

---

## 7. 任务依赖

```
T1 (contracts) ──→ T2 (spec) ──→ T4 (loader)
       │                              │
       └──→ T3 (objectives) ──→ T5 (toy_tsp) ──→ T6 (entry + tests)
```

T1 和 T3 可并行。T2 依赖 T1（spec 引用 Protocol 类型）。T4 依赖 T2。T5 依赖 T1+T3+T4。T6 最后做。

---

## 8. N0 完成标志

- [ ] `scion/scion/problem/` 模块存在且可 import
- [ ] `scion/problems/toy_tsp/` MWE 通过 adapter 全部方法
- [ ] 所有现有 warehouse 测试不回退
- [ ] `pytest` 全绿
- [ ] 本文档 checklist 全部打勾
