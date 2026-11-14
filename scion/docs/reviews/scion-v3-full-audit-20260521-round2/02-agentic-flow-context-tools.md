# Agentic Flow、Context 与 Tools 审核

审计重点：两阶段 hypothesis/code；工具调用；上下文构造；agent 是否能充分研究问题对象，同时 gate 不比 agent 看得更多；agent-quality block 是否保留 branch-local 信息。

## 总体判断

当前 agentic flow 已明显按 v3 收敛：hypothesis 与 code phase 分离，planner/tool-selection 上下文注入 `active_algorithm_facts_anchor`，prompt 渲染 active facts 在 raw tool observations 之前，repair flow 也携带同源 facts。与上一轮相比，主要 P0/P1 问题已修复或降级为可测试性债务。

仍需关注的是：这些约束主要由若干上下文构造函数约定维持，还缺一个跨所有 LLM tool-selection call 的硬性 invariant 测试；proposal-quality / telemetry feedback 虽然更丰富，但在复杂 CVRP novelty 与 telemetry activation 失败场景中，agent 仍可能收到过于粗粒度的 top-level block reason。

## 发现 A-01

Severity：P2

模块：proposal / tool-selection context

证据：

- `scion/scion/proposal/agentic_session_planner_loop.py:95`
- `scion/scion/proposal/agentic_session_planner_loop.py:601`
- `scion/scion/proposal/agentic_session_code_tools.py:148`
- `scion/scion/proposal/agentic_session_hypothesis.py:306`
- `scion/scion/proposal/agentic_session_patch_flow.py:129`
- `scion/scion/proposal/agentic_session_repair.py:42`
- `scion/scion/proposal/engine/prompt_common.py:75`

问题：

active facts anchor 已在主要 hypothesis/code/repair/planner 路径中注入，且 prompt 会渲染 `## Active Algorithm Facts`。但 v3 onboarding 明确要求 active-facts anchor 适用于每一次 LLM tool-selection call，包括 code-phase targeted reads、diagnosis、repair follow-up。目前约束分散在多个 context builder 中，缺少一个统一 contract test 来枚举所有 LLM tool-selection entrypoint 并断言 anchor、digest、fact ids、provenance 均存在。

风险：

- 后续新增 tool-selection 路径时，容易忘记携带 active facts，导致 agent 与 semantic gate 不同源。
- 如果某个诊断/repair follow-up path 漏掉 anchor，gate 可能引用 agent 未见过的 fact packet。

建议修复：

增加 agentic context invariant 测试或 shared builder：所有 LLM tool-selection payload 必须通过同一个 active facts anchor helper。测试应覆盖 hypothesis planner、code targeted read、code diagnosis、repair follow-up，并断言 `source_digest`、`fact_packet_digest`、`snapshot_digest`、`fact_ids`、`provenance` 非空或显式 unavailable reason。

## 发现 A-02

Severity：P2

模块：proposal feedback / agent quality loop

证据：

- `scion/scion/proposal/context/feedback.py:188`
- `scion/scion/proposal/mechanism_novelty.py:20`
- `scion/scion/problems/cvrp/mechanism_novelty/provider.py:560`
- `scion/scion/core/decision.py:68`

问题：

agent quality feedback 已保存 `fact_packet_digest`、provenance、contradicted span、matched span、allowed variant guidance，这是 v3 要求的正向改进。但 formal telemetry failure 在 decision 层仍会压成 `SCREENING_TELEMETRY_FAILED` / `VALIDATION_TELEMETRY_FAILED` 等粗 reason；proposal feedback 与 branch-local quality memory 中能看到细节，但主 decision artifact 的顶层语义不足，agent 后续很难区分“activation missing 可修复”“protected outcome misuse”“runtime emitted undeclared field”“代码未触发 mechanism”等不同失败。

风险：

- agent 可能反复修同一类 telemetry/novelty问题，但顶层历史摘要无法清晰指导下一轮。
- 主会话审计时需要跨多个 artifact 才能还原失败类型，不符合 v3 可追溯审计的低摩擦要求。

建议修复：

在不把 free text 暴露给 deterministic decision 的前提下，扩展 typed decision reason taxonomy 或 auxiliary reason payload：保留 `*_TELEMETRY_FAILED` 作为 veto 类别，同时附带 `category`、`mechanism_id`、`missing_activation_fields`、`undeclared_fields`、`agent_repairable`、`quality_aux_reason` 等 typed 字段。proposal feedback 可直接消费这些 typed fields。

## 发现 A-03

Severity：P2

模块：solver-design prompt provider / context ownership

证据：

- `scion/scion/proposal/context_manager/manager.py:493`
- `scion/scion/proposal/engine/solver_design_prompts.py:217`
- `scion/scion/problems/cvrp/solver_design_provider.py`

问题：

solver-design prompt provider 已从 adapter 暴露并由 generic context manager 解析，这是正确方向。但 CVRP provider 文件本身已达 872 行，承担 API manifest、integration path、prompt fragment、active design context 等多种职责。虽然这不是 generic core 泄漏，但会让 problem-owned prompt/context 继续膨胀，后续变更容易影响 agent 能看到的对象知识。

风险：

- CVRP problem provider 的职责边界变模糊，难以审计哪些内容是 prompt、哪些是 tool manifest、哪些是 smoke/contract。
- 其他问题域复用模式时可能复制一个大型 provider，而不是形成清晰 provider interface。

建议修复：

将 CVRP solver-design provider 拆成 prompt fragments、tool/API manifest、integration path policy、active design context 四个小模块，通过 adapter 暴露同一 provider facade。generic proposal 不需要变化。

## 正向对齐点

- `scion/scion/proposal/engine/prompt_common.py:75` 明确将 active facts 放在 raw observations 前，并声明 semantic gates 共享同一 fact packet。
- `scion/scion/proposal/active_solver_snapshot.py` 生成 `provenance`、`source_digest`、`snapshot_digest`、`fact_packet_digest` 和 `active_algorithm_facts`，为同源审计提供基础。
- `scion/scion/proposal/context/feedback.py` 会过滤 validation/frozen 细节，只保留 screening 与 safe pre-protocol failure，符合 v3 exposure boundary。
- `query_holdout_summary` 与 `query_runtime` 不暴露 raw metrics file refs，且 runtime feedback 只来自 screening-derived 数据。

