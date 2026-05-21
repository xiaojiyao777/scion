# v3 Boundary 与 Generic Core 审核

审计重点：core / adapter / runtime / evidence / mechanism novelty 的职责边界；Scion core 是否保持问题无关；CVRP/ALNS/VNS/route/fleet/total_distance 等问题域内容是否仍进入 generic core。

## 总体判断

`problem_spec`、provider resolution、active solver facts、runtime telemetry surface declaration 的主线已经向 v3 收敛。`scion/problems/cvrp/adapter.py` 明确暴露 `mechanism_novelty_provider`、`contract_check_provider`、`solver_design_prompt_provider`、`active_solver_design_provider`、`solver_design_smoke_provider`，generic proposal/runtime 通过 provider key 获取问题域能力。

主要剩余问题不是 adapter 缺失，而是 generic 包内仍有历史 CVRP artifact 与 legacy fallback。尤其 `scion/scion/evidence` 作为 v3 evidence 组件，仍直接定义和导出 CVRP final-quality 结构，这是当前最清晰的边界偏离。

## 发现 B-01

Severity：P1

模块：evidence / problem boundary

证据：

- `scion/scion/evidence/__init__.py:3`
- `scion/scion/evidence/final_quality.py:63`
- `scion/scion/evidence/final_quality.py:120`
- `scion/scion/evidence/final_quality.py:223`
- `scion/scion/evidence/final_quality.py:260`
- `scion/scion/evidence/cvrp_final_evaluation.py`
- `scion/scion/evidence/cvrp_baseline_import.py`
- `scion/scion/evidence/cvrp_case_manifest.py`

问题：

generic evidence 包直接导出 `CvrpFinalEvaluationService`、`CvrpBaselineImporter`、`CvrpCaseManifestBuilder` 等 CVRP 类型；`final_quality.py` 中还定义 `_CVRP_CASE_FIELDS`、`bks_routes`、`route_gap`、`baseline_routes`、`candidate_routes`、`benchmark_feasible` 等字段。v3 蓝图要求 Scion core/evidence 保存 typed artifacts 与 lineage，但研究对象语义只能通过 adapter/problem provider 暴露。当前结构会让 evidence 层成为 CVRP schema 的事实拥有者，未来接入第二个问题域时必须改 generic evidence。

风险：

- generic evidence 的 CSV/quality schema 变成 CVRP schema，破坏 core problem-agnostic 约束。
- final-quality artifact 的字段选择由 generic 包决定，而不是由 problem surface/provider 声明。
- boundary sentinel 目前未覆盖 `scion/scion/evidence`，该类泄漏不会被自动发现。

建议修复：

将 CVRP final evaluation、baseline import、case manifest 迁移到 `scion/scion/problems/cvrp/evidence/` 或等价 problem-owned package。generic `evidence` 只保留通用 artifact writer、lineage hooks、typed extension slot。`QualityCaseRecord` 应拆为 generic fields + problem extension payload，extension schema 由 problem provider/surface 声明。`evidence/__init__.py` 不再导出 CVRP 类型。

## 发现 B-02

Severity：P1

模块：contract / problem boundary

证据：

- `scion/scion/contract/gate.py:59`
- `scion/scion/contract/gate.py:814`
- `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py`

问题：

`contract/gate.py` 仍保留 `_LEGACY_PROBLEM_SCALE_NAMES`，包含 `routes`、`customers`、`vehicles` 等问题域名称；`_is_solver_design_patch_path` 仍硬编码 `policies/baseline_algorithm.py`、`policies/solver_algorithm.py`、`policies/baseline_modules/*.py` 等 CVRP 时代路径。虽然测试中有 allowlist 标记这些是 legacy debt，但 v3 的 contract 应只校验 generic patch contract、surface-declared paths 和 provider-owned constraints。

风险：

- 新问题域若不使用 CVRP 风格目录，会被 generic contract 的历史路径假设影响。
- `route/customer/vehicle` 类词汇虽然被 allowlist，但仍在 generic contract 中保留语义。
- allowlist 容易让历史债长期固化，削弱 boundary sentinel 的约束力。

建议修复：

把 legacy path/scale fallback 移到显式 legacy compatibility module，并由配置或 problem surface 开关启用。active v3 path check 应只读取 problem surface 的 allowed integration roots / owned paths。boundary sentinel 应将 allowlist 缩小为短期 TODO，并要求每个 allowlist 项有 owner 和移除条件。

## 发现 B-03

Severity：P2

模块：verification / core model compatibility

证据：

- `scion/scion/verification/state_mutation.py:1`
- `scion/scion/verification/state_mutation.py:90`
- `scion/scion/verification/state_mutation.py:166`
- `scion/scion/core/models.py:440`

问题：

`state_mutation.py` 的 legacy fallback 仍以 `assignment`、`vehicles`、`order_ids`、empty vehicles 等字段判断 state consistency；`core/models.py` 的 `SolverOutput` 仍保留 `vehicles`、`assignment`、`objective`、`feasible`、`runtime`。adapter-backed 路径已经能 fail closed 并走 adapter provider，这是正确方向，但 fallback 和 model 字段仍把车辆/订单语义留在 generic verification/core model。

风险：

- fallback 被误用时，generic verification 会重新变成 CVRP-style verifier。
- `SolverOutput` 名义上是 generic core model，但字段仍面向 routing assignment。

建议修复：

将 legacy `SolverOutput` 和 fallback verifier 标记为 compatibility-only，并从 active v3 path 中移除。新的 verification input 应是 problem-owned typed observation 或 provider-produced normalized evidence。保留旧字段时，应放入 `legacy_*` 命名空间并禁止新 surface 默认使用。

## 发现 B-04

Severity：P2

模块：boundary sentinel / tests

证据：

- `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py`

问题：

boundary sentinel 覆盖 `core`、`proposal`、`contract`、`runtime`、`protocol`、`verification` 等目录，但没有覆盖 `scion/scion/evidence`。本轮最明确的 CVRP 泄漏恰好位于 evidence 包，说明 sentinel 的扫描边界与 v3 组件边界不一致。

风险：

- evidence、lineage、problem provider glue 中的问题域词汇可以绕过 boundary test。
- allowlist 与扫描范围不完整会让“core problem-agnostic”变成局部约束。

建议修复：

将 `evidence`、必要的 `lineage` generic 子包纳入 sentinel；把 problem-owned directories 明确排除。对现有 evidence CVRP 文件先以 P1 迁移任务处理，不建议简单扩大 allowlist。

## 正向对齐点

- `scion/scion/problem/providers.py` 提供 provider resolution helper，generic 层不需要直接 import CVRP provider。
- `scion/scion/proposal/context_manager/manager.py:493` 会从 context/provider 中解析 solver design prompt provider，并写入 context。
- `scion/scion/runtime/surface_telemetry.py` 通过 surface declarations 识别 runtime fields 与 roles，避免 generic runtime 硬编码 `solver_algorithm_*`。
- `scion/scion/problems/cvrp/problem-v1.yaml:141` 将 CVRP telemetry 字段、roles、mechanism activation/effect templates 放在 problem surface 中，符合 v3 adapter-owned telemetry 方向。

