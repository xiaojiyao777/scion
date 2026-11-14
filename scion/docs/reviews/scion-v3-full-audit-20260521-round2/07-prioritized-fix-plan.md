# Prioritized Fix Plan

本计划面向主会话分发给开发子agent。按 P0 -> P1 -> P2 排序。每个任务要求只改相关模块，保持 v3 deterministic decision 不读取 free text，不把 CVRP 语义移入 generic core。

## P0

本轮未发现 P0。无需分发紧急 stop-the-line 修复。

建议主会话在进入 P1 前确认两点：

- 当前基线包含 `e1df1f6`，formal telemetry failure summary count 修复已在工作区。
- 当前基线包含 `e04b1de`，CVRP cluster removal novelty false-positive 已有 exact span / allowed variant 保护。

## P1-A：迁移 generic evidence 中的 CVRP 内容

对应发现：B-01、T-02

目标模块：

- `scion/scion/evidence/*`
- `scion/scion/problems/cvrp/*`
- evidence / final-quality 相关 tests

任务：

1. 将 `cvrp_final_evaluation.py`、`cvrp_baseline_import.py`、`cvrp_case_manifest.py` 迁移到 `scion/scion/problems/cvrp/evidence/`。
2. 将 `QualityCaseRecord` 拆成 generic common fields + problem extension payload。
3. 让 CVRP extension schema 由 CVRP problem provider 或 surface declaration 暴露。
4. 收窄 `scion/scion/evidence/__init__.py`，不再导出 CVRP 类型。
5. 更新 imports 和 tests，确保 generic evidence 不再包含 route/BKS/CVRP 字段。

验收标准：

- boundary sentinel 覆盖 `scion/scion/evidence` 后不需要为 CVRP final-quality 新增 allowlist。
- generic evidence 不出现 `cvrp`、`route_gap`、`bks_routes`、`baseline_routes`、`candidate_routes` 等问题域字段。

## P1-B：细化 telemetry decision reason taxonomy

对应发现：T-01、A-02、C-03

目标模块：

- `scion/scion/core/decision.py`
- `scion/scion/core/telemetry_validation.py`
- `scion/scion/core/evidence_recorder.py`
- `scion/scion/lineage/registry.py`
- proposal feedback consumers

任务：

1. 保留 telemetry guard failure 的 deterministic veto，但新增 typed subreason payload。
2. payload 至少包含 stage、category、mechanism id、surface field id、runtime role、missing/invalid fields、repairable flag、declaration source digest。
3. 在 decision artifact 中保留 auxiliary protocol reason，例如 runtime regression、candidate failure、negative median delta，不改变最终 veto。
4. summary/status/lineage 同时展示 top-level reason 与 typed telemetry details。
5. proposal feedback 直接消费 typed details，避免只看到 `SCREENING_TELEMETRY_FAILED`。

验收标准：

- formal telemetry failed count 仍与 `e1df1f6` 行为一致。
- 不向 decision engine 引入 free text。
- activation missing、undeclared field、outcome/protected role misuse 能在 summary 中区分。

## P1-C：修正 negative median delta screening pass 语义

对应发现：L-01

目标模块：

- `scion/scion/core/decision.py`
- protocol decision tests
- campaign summary reason mapping

任务：

1. 修改 `win_rate` 达标但 `median_delta < 0` 的 screening path，不默认 `QUEUE_VALIDATION`。
2. 默认决策建议为 `CONTINUE_EXPLORE` 或 `EXPAND_SCREENING`，reason 使用 non-pass 语义。
3. 如果确有问题域需要允许该路径，必须通过 protocol config / problem declaration 显式启用，并在 reason 中体现 rationale。
4. 更新 tests，覆盖 high-win negative-effect、high-win positive-effect、low-win positive-effect 三类场景。

验收标准：

- v3 screening gate 中“胜率和效果同时达标”的默认语义成立。
- `SCREENING_PASS_NEGATIVE_DELTA` 不再作为默认 validation 入场理由。

## P1-D：拆分核心大文件，先机械拆分后行为修复

对应发现：M-01、M-02

目标模块：

- `scion/scion/core/evidence_recorder.py`
- `scion/scion/core/explore_step_pipeline.py`
- `scion/scion/proposal/llm_client.py`

任务：

1. `evidence_recorder.py` 拆为 status writer、summary builder、protocol progress recorder、telemetry summary、artifact refs。
2. `explore_step_pipeline.py` 拆为 proposal step、pre-protocol gates、protocol execution、decision finalization glue。
3. `llm_client.py` 拆为 provider transport、structured parser、schema repair/retry policy、error taxonomy。
4. 第一阶段尽量机械移动，保持 public API 和行为不变。
5. 第二阶段再承接 P1-B/P1-C 的行为变化。

验收标准：

- 三个生产文件均降至 800 行以下，且职责边界能用模块名解释。
- 原测试套件通过后，再继续 telemetry/screening 行为修改。

## P2-A：清理 legacy problem-domain fallback

对应发现：B-02、B-03

目标模块：

- `scion/scion/contract/gate.py`
- `scion/scion/verification/state_mutation.py`
- `scion/scion/core/models.py`

任务：

1. 将 `_LEGACY_PROBLEM_SCALE_NAMES`、CVRP-style patch path fallback 移到 legacy compatibility module。
2. active v3 contract 只读取 problem surface/provider 声明的 path 和 constraints。
3. 将 `SolverOutput` 中 routing-style fields 标记为 legacy，禁止新 v3 problem surface 默认依赖。
4. 对 legacy path 增加明确配置开关和 deprecation test。

验收标准：

- generic contract/verification active path 不再出现 route/customer/vehicle/order 语义。
- legacy compatibility 仍能服务旧测试或旧 artifact，但必须显式启用。

## P2-B：改进 branch lifecycle 与 scheduler capacity

对应发现：L-02、L-03、L-04

目标模块：

- `scion/scion/core/branch_lifecycle_policy.py`
- `scion/scion/core/scheduler.py`
- `scion/scion/core/campaign_loop.py`
- status summary

任务：

1. 为 low-signal continue 添加 pair-level soft-risk signal，不直接 hard abandon。
2. 将 `BLOCKED_INFRA` 从 active scientific branch capacity 中拆出，或增加单独 infra retry lane。
3. proposal-quality budget summary 拆成 total、per-branch、per-category。
4. status 中展示 soft risk、blocked infra retry 状态和 quality budget 消耗来源。

验收标准：

- branch 不因弱信号过早抛弃，但明显退化方向会被 deprioritize。
- infra-blocked branch 不会长期占用 active exploration capacity。

## P2-C：拆分 CVRP novelty 与 solver-design provider

对应发现：C-01、C-02、M-03

目标模块：

- `scion/scion/problems/cvrp/mechanism_novelty/*`
- `scion/scion/problems/cvrp/solver_design_provider.py`
- CVRP novelty tests

任务：

1. 按 mechanism family 拆分 novelty matcher。
2. 建立 table-driven novelty regression corpus，覆盖 duplicate、contradiction、allowed variant、negated premise、insufficient evidence。
3. 拆分 solver-design provider 内部 prompt fragments、API manifest、integration policy、active design context。
4. adapter facade 保持兼容。

验收标准：

- `destroy_repair.py` 和 `solver_design_provider.py` 均降至 800 行以下。
- cluster removal / Or-opt / noise / negated premise 等 case 有独立 regression fixtures。

## P2-D：扩展 v3 boundary sentinel

对应发现：B-04、M-05

目标模块：

- `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py`
- generic evidence / lineage packages

任务：

1. 将 generic `evidence` 和必要的 generic `lineage` 子包纳入扫描。
2. 明确排除 `scion/scion/problems/*` problem-owned package。
3. 缩小 allowlist，并为每个 allowlist 项添加 owner、移除条件和目标阶段。
4. 新增断言：generic runtime/protocol/evidence 不能出现 `solver_algorithm_total_distance`、`fleet_violation`、`route_gap`、`bks_routes` 等 CVRP surface field。

验收标准：

- 当前 B-01 迁移完成后，boundary sentinel 扩展不需要新增 CVRP evidence allowlist。
- 新增 generic CVRP 泄漏会被单独 test 捕获。

## P2-E：持久化 protocol progress 审计事件

对应发现：T-03

目标模块：

- `scion/scion/protocol/experiment/stages.py`
- `scion/scion/core/evidence_recorder.py`
- `scion/scion/core/campaign.py`
- lineage event schema

任务：

1. 将 in-flight protocol progress 写入 append-only internal lineage event。
2. public status 只保留 redacted aggregate，不展示 validation/frozen 的 case/seed 级细节。
3. raw metrics ref 保持 internal-only，并在 status 中只展示 digest/ref scope。
4. 添加 tests 覆盖 normal completion、external stop、validation/frozen interruption 三类路径。

验收标准：

- 正常完成后仍能审计中途 progress heartbeat。
- validation/frozen raw detail 不会通过 public status 泄露给 agent-facing context。

