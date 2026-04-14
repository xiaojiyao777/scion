# Scion v0.2 — Development Plan

*Date: 2026-04-10*  
*Status: Execution plan*  
*Branch: `v0.2-dev`*  
*Companion docs:* `scion-v0.2-detailed-design.md`, `scion-v0.2-refined-delivery-plan.md`

---

## 0. 目标

本开发文档回答三个问题：

1. **先做什么，后做什么**
2. **每一段做到什么程度算完成**
3. **如何用最短路径拿到第一个可信的 v0.2 结果**

本文档默认：

- 不回写旧 v0.2 文档
- 直接在新文档体系下推进开发
- 优先完成 v0.2-MVP，再补 v0.2-Full

---

## 1. 总体策略

### 1.1 总路线

```text
Sprint A: Foundation cleanup
Sprint B: Parameter plumbing
Sprint C: Parameter search close loop
Sprint D: First v0.2 experiment proof
Sprint E: Search-efficiency polish
```

### 1.2 为什么这样排

因为 v0.2 的核心价值不是：

- 多一份更漂亮的 report
- 多几个 prompt guidance
- 多一个 family tracker

而是：

> **promote 后能自动做参数搜索，并且结果可追溯、可比较。**

所以开发顺序必须围绕这个闭环。

---

## 2. Sprint A — Foundation cleanup

## 2.1 目标

把 v0.1 的环境噪声和 artifact 缺口补齐，为后续参数层提供可信基座。

## 2.2 任务范围

- T01 deterministic env
- T02 V5 diagnostics enhancement
- T03 campaign summary schema upgrade
- T04 failed-code archiving

## 2.3 修改文件

### 必改
- `scion/scion/runtime/subprocess_runner.py`
- `scion/scion/verification/state_leak.py`
- `scion/scion/core/campaign.py`
- `scion/scion/runtime/workspace.py`

### 可能补测试
- `scion/scion/tests/test_runner.py`
- `scion/scion/tests/test_verification.py`
- `scion/scion/tests/test_campaign.py`
- `scion/scion/tests/test_workspace.py`

## 2.4 具体交付物

### A1. Runner env fix

完成标准：
- `_build_clean_env()` 包含 `PYTHONHASHSEED=0`
- 测试断言通过

### A2. V5 enhanced diagnostics

完成标准：
- 失败时落盘 run1 / run2 JSON
- 返回 structured detail
- 归档 candidate operator files

### A3. Summary schema upgrade

完成标准：
- `campaign_summary.json` 每个 step 可见：
  - protocol aggregate
  - case feedback 摘要
  - verification detail
  - code archive ref

### A4. Failed-code archiving

完成标准：
- verification heavy failure 不会在 cleanup 后丢失代码
- summary 中可以通过 `code_archive_ref` 定位

## 2.5 Sprint A 验收

跑一个短 campaign（例如 5~8 轮）后：

- 能看到新 summary 字段
- V5 失败可定位到具体 archive 和 output JSON
- rerun 后真实 V5 failure pattern 更清楚

---

## 3. Sprint B — Parameter plumbing

## 3.1 目标

把参数层需要的配置、权重 IO、评估器接通。

## 3.2 任务范围

- T12 parameter config + models
- T13 registry weight IO
- T14 evaluator

## 3.3 修改文件

### 必改
- `scion/scion/config/problem.py`
- `scion/scion/core/models.py`
- `scion/scion/runtime/pool_manager.py`
- `scion/scion/parameter/__init__.py`
- `scion/scion/parameter/search_space.py`
- `scion/scion/parameter/evaluator.py`

### 测试
- `scion/scion/tests/test_config.py`
- `scion/scion/tests/test_pool_manager.py`
- `scion/scion/tests/test_protocol.py`（如复用 delta 逻辑）
- 新增：`scion/scion/tests/test_parameter.py`

## 3.4 具体交付物

### B1. ParameterSearchConfig

完成标准：
- `ProblemSpec.from_yaml()` 能加载 `parameter_search`
- 默认值稳定可测
- `eval_cases=[]` 语义明确为 screening fallback

### B2. Registry weight IO

完成标准：
- 能从 `registry.yaml` 读取权重
- 能安全更新所有 operator 权重
- 不破坏其他字段

### B3. Weight evaluator

完成标准：
- 在一个独立 workspace 上写 weights
- 跑 `(case, seed)` pairs
- 返回 `median_delta`
- evaluator 不直接修改 champion snapshot

## 3.5 Sprint B 验收

- 通过单元测试证明 evaluator 对 mock runner 可用
- 在真实 workspace 上能手工调用 evaluator 得到 baseline score

---

## 4. Sprint C — Parameter search close loop

## 4.1 目标

把 optimizer、promote hook、lineage 串起来，形成第一次 v0.2 主闭环。

## 4.2 任务范围

- T15a random/local optimizer
- T16 campaign promote hook
- T17a weight optimization lineage

## 4.3 修改文件

### 必改
- `scion/scion/parameter/optimizer.py`
- `scion/scion/core/campaign.py`
- `scion/scion/lineage/registry.py`

### 可能补 helper
- `scion/scion/runtime/pool_manager.py`
- `scion/scion/parameter/search_space.py`

### 测试
- `scion/scion/tests/test_campaign.py`
- `scion/scion/tests/test_lineage.py`
- `scion/scion/tests/test_lineage_sprint3.py`
- `scion/scion/tests/test_parameter.py`

## 4.4 具体交付物

### C1. RandomLocalWeightOptimizer

完成标准：
- baseline + random init + local perturbation
- deterministic optimizer seed
- 输出 `WeightOptimizationResult`

### C2. Promote hook integration

完成标准：
- `_on_promote()` 内自动触发 optimizer
- 优化只在 optimization workspace 中进行
- improved 后才写回 champion snapshot 的 `registry.yaml`
- 最终 `ChampionState.operator_pool` 从最终 registry 重建

### C3. Weight optimization lineage

完成标准：
- 新表 `weight_optimizations`
- 可记录 baseline/best weights 与 score
- 可按 champion_version 查询

## 4.5 Sprint C 验收

通过一个 mock promote 场景证明：

```text
promote -> optimize -> persist -> rebuild champion metadata
```

整个链路在单测/集成测中跑通。

---

## 5. Sprint D — First v0.2 experiment proof

## 5.1 目标

完成第一次真正的 v0.2-MVP 实验闭环。

## 5.2 任务范围

- T18 end-to-end validation
- 必要时补 T17b 的最低可用 CLI

## 5.3 执行步骤

1. 在 `v0.2-dev` 跑完整 campaign
2. 等待首次 promote
3. 自动触发权重优化
4. 比较：
   - promoted structure + baseline weights
   - promoted structure + optimized weights
5. 产出实验 note

## 5.4 产出物

至少包含：

- 优化前后 weights 对比表
- baseline / optimized median_delta
- frozen holdout A/B 表
- 一段简短解释：收益来自结构还是配权

## 5.5 Sprint D 验收

如果满足以下条件，就算 v0.2-MVP 成功：

1. promote 自动触发 weight search
2. 优化结果可持久化查询
3. frozen 上能做 baseline vs optimized 对比
4. 整个 campaign 无崩溃

---

## 6. Sprint E — Search-efficiency polish

这部分放在 MVP 后。

## 6.1 任务范围

- T05 frozen expansion
- T06 observability
- T07 family tracking
- T08 strategy guidance
- T09 richer wording
- T10 baseline hints
- T11 screening rebalance
- T15b Bayesian optimizer
- T17b CLI/report polish

## 6.2 建议顺序

```text
E1: T05 + T11
E2: T07 + T08
E3: T09 + T10 + T06
E4: T15b + T17b
```

原因：

- 先修 benchmark 结构
- 再修 outer-loop proposal quality
- 最后再上更贵的 optimizer

---

## 7. 每个 Sprint 的 Definition of Done

## Sprint A DoD

- 代码合并
- 测试通过
- 短 campaign 复跑
- summary / archive 实际可读

## Sprint B DoD

- config / model / evaluator 全通过测试
- 真 workspace 上可计算 baseline score

## Sprint C DoD

- promote hook 在测试中真正调用 optimizer
- weight_optimizations 表可查询

## Sprint D DoD

- 真实 campaign 产出第一份 v0.2 comparison artifact

## Sprint E DoD

- family diversity 和报告能力有可见改善
- 若上 BO，必须证明优于 random/local 或至少更 sample-efficient

---

## 8. 测试计划

### 8.1 单元测试

#### T01
- `test_runner_build_clean_env_contains_pythonhashseed`

#### T02
- `test_state_leak_writes_run_refs_and_diff_keys`
- `test_state_leak_archives_candidate_code`

#### T12
- `test_problem_spec_parameter_search_defaults`
- `test_problem_spec_parameter_search_yaml_load`

#### T13
- `test_pool_manager_read_weights`
- `test_pool_manager_update_weights_preserves_other_fields`

#### T14
- `test_evaluator_returns_median_delta`
- `test_evaluator_uses_temp_workspace`

#### T15a
- `test_random_local_optimizer_improves_convex_mock`
- `test_random_local_optimizer_is_seed_deterministic`

#### T16
- `test_campaign_on_promote_runs_weight_optimization`
- `test_campaign_rebuilds_operator_pool_from_registry`

#### T17a
- `test_registry_records_weight_optimization`
- `test_registry_queries_weight_optimization_by_version`

### 8.2 集成测试

- `test_promote_then_optimize_then_persist`
- `test_cli_optimize_weights_minimal`
- `test_campaign_summary_contains_archive_refs`

### 8.3 真实实验验证

- 短 campaign（Sprint A 后）
- 中等 campaign（Sprint D）
- full campaign（Sprint E 或之后）

---

## 9. 风险与应对

### 风险 1：T02 做太重，拖慢整个节奏

**应对**：
先做结构化输出 + archive，不做深 trace。

### 风险 2：T15 BO 依赖卡住

**应对**：
MVP 明确只要求 random/local。

### 风险 3：promote hook 直接改 champion snapshot 造成污染

**应对**：
始终在 optimization workspace 搜索，只在最终 improved 后写回。

### 风险 4：`ChampionState.operator_pool` 与 registry 不一致

**应对**：
在 T16 里把“从 registry 重建 operator_pool”作为强制步骤。

### 风险 5：evaluator 太慢

**应对**：
降低默认：
- `n_iterations=8`
- `n_eval_seeds=2`
- `eval_cases=screening`

---

## 10. 推荐命令与工作节奏

### 10.1 开发顺序

```text
A. 先写测试骨架
B. 再实现核心逻辑
C. 每个 Sprint 结束跑 targeted tests
D. 每个大里程碑结束跑一次真实 campaign
```

### 10.2 推荐测试节奏

```bash
pytest scion/scion/tests/test_runner.py -q
pytest scion/scion/tests/test_verification.py -q
pytest scion/scion/tests/test_pool_manager.py -q
pytest scion/scion/tests/test_campaign.py -q
pytest scion/scion/tests/test_lineage.py -q
pytest scion/scion/tests/test_e2e.py -q
```

### 10.3 真实验证节奏

- Sprint A 后：5~8 rounds
- Sprint D 后：完整 first proof run
- Sprint E 后：正式对比 run

---

## 11. 文档产出要求

每个 Sprint 结束后，至少追加一份简短记录：

- 做了什么
- 哪些测试新增/修复
- 当前 blockers
- 是否需要调整 task manifest

建议文件：

```text
scion/design/
  scion-v0.2-sprint-a-note.md
  scion-v0.2-sprint-b-note.md
  ...
```

这样后面写实验报告和论文附录会轻松很多。

---

## 12. 最终建议

如果明天开始正式开发，我建议按下面的最短路径推进：

```text
Day 1-2: Sprint A
Day 3-4: Sprint B
Day 5-6: Sprint C
Day 7:   Sprint D first proof
```

也就是说：

> **一周内拿到 v0.2-MVP 的第一份可信结果**

之后再进入 Sprint E，把研究效率和 optimizer sophistication 往上推。

---

## 13. Bottom line

v0.2 的开发策略不应该是“平均推进 18 个任务”，而应该是：

1. 先清环境和 artifact
2. 再打通参数层 plumbing
3. 再闭 promote-after-optimize 主链路
4. 最后补搜索效率和 BO

这条路线最稳，也最快见真结果。
