# Evidence、Lineage 与 Telemetry 审核

审计重点：evidence/lineage 可追溯性；active algorithm facts、telemetry declarations、novelty/validation gates 是否同源；formal telemetry failure 统计；gate 是否不会看得比 agent 多。

## 总体判断

`e1df1f6` 后，formal telemetry failure 的统计路径已基本修复：正式 screening/validation/frozen protocol 的 telemetry guard failure 会进入 evaluation orchestrator、campaign status、evidence summary 与 lineage summary。telemetry surface declaration 也已经问题域化，`solver_algorithm_*` 不再由 generic runtime 硬编码。

剩余主要风险是语义粒度：统计能数到失败，但 top-level decision reason 仍会把不同失败压成粗粒度 telemetry failure。另一个 P1 边界问题是 generic evidence 包内仍直接定义 CVRP final-quality schema。

## 发现 T-01

Severity：P1

模块：decision / telemetry evidence

证据：

- `scion/scion/core/decision.py:41`
- `scion/scion/core/decision.py:68`
- `scion/scion/core/decision.py:75`
- `scion/scion/core/telemetry_validation.py:37`
- `scion/scion/core/telemetry_validation.py:70`
- `scion/scion/core/telemetry_validation.py:130`
- `scion/scion/core/evaluation_orchestrator.py:138`
- `scion/scion/core/campaign.py:287`
- `scion/scion/core/evidence_recorder.py:857`
- `scion/scion/lineage/registry.py`

问题：

formal telemetry failure 已能被统计，但 `DecisionEngine` 在遇到 non-repairable telemetry guard failure 时，会先于 runtime/stage/quality 分支返回 `SCREENING_TELEMETRY_FAILED`、`VALIDATION_TELEMETRY_FAILED` 或 `FROZEN_TELEMETRY_FAILED`。这保证了 telemetry guard 的 veto 权威，但也遮蔽了同一次 experiment 中可能存在的 runtime regression、candidate failures、negative effect、protected outcome misuse 等辅助事实。

风险：

- summary 中能看到 `telemetry_failed_experiments`，但不能直接看到失败是 activation missing、undeclared field、outcome-as-activation、aggregate path 错误还是代码没有触发 mechanism。
- branch lifecycle 与 agent feedback 需要跨 telemetry details、protocol stats、decision reason 多处拼接，削弱 v3 可审计性。
- 最近 `e1df1f6` 解决的是“数不数”的问题，不是“为什么失败”的问题。

建议修复：

保留 telemetry guard 作为 deterministic veto，但在 decision artifact 中增加 typed `telemetry_failure_detail` 和 `auxiliary_protocol_reason`。字段应来自 `TelemetryValidationSignal`、guard categories 和 `DecisionFeatures`，不要引入 free text。summary/status/lineage 应同时展示 top-level veto reason 与 typed subreason。

## 发现 T-02

Severity：P1

模块：evidence / problem boundary

证据：

- `scion/scion/evidence/final_quality.py:63`
- `scion/scion/evidence/final_quality.py:120`
- `scion/scion/evidence/cvrp_final_evaluation.py`
- `scion/scion/evidence/cvrp_baseline_import.py`
- `scion/scion/evidence/cvrp_case_manifest.py`

问题：

generic evidence 包仍包含 CVRP-specific final-quality 字段和服务。v3 中 evidence/lineage 是 deterministic kernel 的一部分，应保存通用 artifact identity、stats、hash、refs、decision features 与 problem extension，而不是直接拥有 CVRP route/BKS/benchmark schema。

风险：

- lineage artifact schema 与 CVRP 绑定，后续第二问题域必须改 generic evidence。
- audit 文档中“generic evidence”与“problem-owned evaluation”无法一眼分清。

建议修复：

同 B-01：把 CVRP final evaluation 迁移到 problem package，generic evidence 只保留 extension-aware writer/reader。lineage summary 记录 extension digest 与 declared schema id，不直接理解 `routes` / `bks_routes` / `route_gap`。

## 发现 T-03

Severity：P2

模块：protocol progress / in-flight lineage

证据：

- `scion/scion/protocol/experiment/stages.py:94`
- `scion/scion/protocol/experiment/stages.py:128`
- `scion/scion/protocol/experiment/stages.py:162`
- `scion/scion/core/evidence_recorder.py:101`
- `scion/scion/core/evidence_recorder.py:521`
- `scion/scion/core/campaign.py:360`
- `scion/scion/core/campaign.py:405`

问题：

in-flight protocol progress 已能在外部 stop 时写入 status，并标记 raw metrics ref 为 internal-only，这是对 v3 可追溯性的改进。但当前主要是 status snapshot，而不是 append-only progress event stream；正常完成后 `_end_status_progress` 会清理 in-flight 状态，后续审计难以证明长实验中间确实有进度上报。snapshot 还可能包含 `last_case_id` / `last_seed`，虽然 raw refs 被标为 internal-only，但 validation/frozen 中断时的 exposure policy 需要更明确。

风险：

- 人工审计能看到最终状态，但不能复盘 progress heartbeat 历史。
- 如果 status artifact 被 agent 或非预期消费者读取，validation/frozen 的 case/seed 级提示可能触碰 v3 holdout exposure boundary。

建议修复：

将 progress snapshot 同步写入 append-only internal lineage event，status 只保留 redacted aggregate。对 validation/frozen 阶段，默认不在 public status 中展示 `last_case_id` / `last_seed`，只展示 completed/total counts 和 internal ref digest。

## 发现 T-04

Severity：P2

模块：runtime telemetry declaration

证据：

- `scion/scion/runtime/surface_telemetry.py:52`
- `scion/scion/runtime/surface_telemetry.py:83`
- `scion/scion/runtime/surface_telemetry.py:163`
- `scion/scion/runtime/telemetry_guard/contract.py:25`
- `scion/scion/runtime/telemetry_guard/contract.py:122`
- `scion/scion/problems/cvrp/problem-v1.yaml:141`

问题：

runtime telemetry guard 已从 problem surface declaration 派生字段和 roles，这是正确的 v3 方向。剩余风险在 contract 的可解释性：当 field role 冲突或 aggregate path 不合法时，guard guidance 与 decision reason 之间的语义链路仍不够直观，容易回到 T-01 的 coarse reason 问题。

风险：

- agent 能收到 guard guidance，但 campaign summary / branch decision 只能看到粗 reason。
- telemetry declaration 与 validation gate 同源，但审计 artifact 没有充分展示“哪个 declaration/role 导致失败”。

建议修复：

在 telemetry guard result 中记录 `surface_field_id`、`role`、`declaration_source_ref`、`mechanism_template_id`，并在 summary/status 中以 typed digest 形式展示。保持 agent prompt 不暴露 validation/frozen raw metrics。

## 正向对齐点

- `scion/scion/core/telemetry_validation.py:37` 只把 completed formal stages 的 guard failure 视为 formal telemetry failure，preview/smoke 不混入统计。
- `scion/scion/core/telemetry_validation.py:70` 把 activation missing 建模为 screening/validation repairable，而 frozen 仍 fail closed，符合 v3 validation gate 边界。
- `scion/scion/core/telemetry_validation.py:121` 将 repairable telemetry validation failure 排除出 effective screened experiment，避免把未激活机制当成有效研究证据。
- `scion/scion/proposal/mechanism_novelty.py` 与 CVRP novelty provider 传递 `snapshot_digest`、`fact_packet_digest`、fact ids 和 provenance，支持 gate/agent 同源审计。

