# Scion v0.4 direct-v3 Onboarding

*Last updated: 2026-08-08*

本文是维护者进入当前 Scion 的源码导览，不是历史实验汇总。v0.4 的目标是让同一套精简 V3 runtime 在 warehouse 与 CVRP 上都能进行有效算法研究，同时保留确定性的安全、科学与证据边界。

## 先读什么

不要从旧报告、旧实验记录或工程地图开始。按下面顺序建立当前事实：

1. [`scion/TASK.md`](../TASK.md)：当前任务、已接受实现、阻塞点与下一步。
2. [`current-state.md`](status/current-state.md)：当前工作树、验证状态与运行环境。
3. [`scion-architecture-v3.md`](../design/scion-architecture-v3.md)：组件所有权与信任边界的基石设计。
4. [`scion-architecture-v3-v0.4-direct-runtime-addendum.md`](../design/scion-architecture-v3-v0.4-direct-runtime-addendum.md)：当 V3 的早期运行示例与 v0.4 冲突时，以此收窄运行语义。

准备或分析实验时，再读：

- [`operations/README.md`](operations/README.md)：当前操作文档入口；
- [`experiment-runbook.zh.md`](operations/experiment-runbook.zh.md)：direct-v3 准备、启动、低频监控与验收；
- [`postrun-analysis-handoff.md`](operations/postrun-analysis-handoff.md)：运行后逐层还原证据的方法。

历史 experiment、planning、review 和 archive 文档只能解释历史产物，不能覆盖上述当前来源或当前源码。

## 一句话模型

Scion 让模型提出算法假设和代码，但不让模型决定这些改动是否安全、是否有效、是否晋升。当前正式路径是：

```text
完整且安全的问题/源码上下文
  -> 最多一次 Hypothesis provider call
  -> Hypothesis Contract
  -> 仅在 H 批准后，最多一次 Code provider call
  -> Patch Contract
  -> isolated staging Workspace
  -> Verification
  -> Protocol
  -> Safe Features
  -> deterministic Decision
  -> Evidence + Lineage
```

H 或 C 的结构化响应无效、provider/infra 失败，或其他 `NOT_EVALUATED` 结果时，当前 campaign invocation 停止。已记录的 Contract 或 Verification `RESEARCH_REJECTED` 则结束该 H/C，不作同一 H/C 的自动重放或修补，不计 formal round；scheduler 随后从 exact clean base 进入新的 H。每个新 provider call 都是独立的 `proposal_call.v1` typed event。

## 不可变边界

### 模型只拥有创造性提案

- 模型输出始终是 tainted input。
- H 描述研究假设、改动位置和预期因果机制；C 必须绑定已经批准的 H。
- 模型不能写入 Protocol 结果、DecisionFeatures、分支状态、调度状态或 promotion 状态。
- prompt 中的说明不能替代 Contract、Verification 或 Protocol 的确定性证据。

### 上下文必须完整、安全且有来源

- `ProblemRuntime` 构建 H/C 输入；`ProposalContextSnapshot` 是 provider 调用前的不可变上下文所有者。
- H 获得当前问题事实、允许修改的研究对象、当前安全源码事实，以及每个可见 screening attempt 的一条 canonical record。
- C 获得一个批准的 H 和完整 `SourceLedger`。ledger 对每个可见文件保留路径与完整内容；多文件算法改动不是例外路径。
- validation/frozen 原始记录、Decision 输入和其他禁止暴露的事实不得进入 proposal context。
- production proposal path 不设置 Scion semantic token/item/file/tool/session budget，不做 top-N、截断、compact-to-fit、遗漏标记或摘要替代。
- provider 必需的 transport ceiling 与 solver/subprocess 的科学 time limit 必须显式记录；它们不是 Scion 的语义研究预算或隐藏终止策略。

### Gate 只保护自己的边界

| Owner | 只负责什么 | 不负责什么 |
|---|---|---|
| Contract | schema、editable/frozen path、action、import/API/interface、patch graph、C 与批准 H 的绑定 | 评价想法是否新颖、偏好某种算法机制、用 telemetry 文本给研究风格打分 |
| Verification | syntax、接口执行、state isolation、feasibility、objective recomputation、nondeterminism、crash、timeout、invalid solver output | 用比较性能提前替代 Protocol，因诊断 telemetry 不完整而要求模型重写 |
| Protocol | screening/validation/frozen 隔离、seed/split、成对比较、统计与 typed scientific verdict | 请求另一轮 H/C，修改候选代码或把自由文本交给 Decision |
| Decision | 把可信 Protocol verdict 与 hard-safety facts 确定性映射为 branch action | 重算统计阈值、解释模型 reasoning、按机制偏好改判 |
| Scheduler | runnable state、priority/FIFO、active slots 与显式 execution hold | 判断科学真伪、用历史建议替代 Decision、引导模型复刻某个 successor |

diagnostic telemetry 可以帮助人分析运行，但不能越权成为另一套研究 gate。问题特有的 objective、feasibility、solver、surface 与 telemetry 含义属于 problem package；generic core 不得内嵌 warehouse 或 CVRP 算法知识。

### 证据和晋升必须可追溯

- provider call 的最小 append-only event、可用 trace、typed outcome、Contract、Verification、Protocol 与 Decision 必须能通过普通引用串起来；它们不构成 context identity 或 receipt 闭包。
- lineage 是 append-only 事实；summary、analysis brief 和 inventory 是索引或投影，不是新的事实来源。
- promotion 必须拥有完整 formal evidence；普通 candidate cleanup 只能记录诊断，不能改写已经完成的科学 Decision。
- `invalid_response`、`research_rejected`、`blocked_infra`、`interrupted` 与 `evaluated` 是不同结果，不能为了报表整洁而合并。

## 按执行顺序阅读源码

下面的顺序比按目录通读更容易看清真实所有权。`CampaignManager` 是组合 facade，不要只读它就推断整个 runtime。

### 1. Campaign loop 与一次 branch step

先读：

- `scion/scion/core/campaign.py`：对外 facade 和 runtime 组合入口；
- `scion/scion/core/campaign_composition.py`：各 owner 的实际装配；
- `scion/scion/core/campaign_loop.py`：以 typed formal evaluated rounds 为目标的外层循环；
- `scion/scion/core/branch_step_runner.py`：scheduler action 到 explore/eval/reconcile 的分派；
- `scion/scion/core/explore_step/pipeline.py`：H、H Contract、C、Patch Contract、Workspace、Verification 与 evaluation 的主路径；
- `scion/scion/core/evaluation_orchestrator.py`、`evaluation_pipeline.py`：候选进入 Protocol 与结果回传的边界；
- `scion/scion/core/decision_finalizer.py`：Decision 后的状态与证据收口。

阅读时逐个追踪 `ExecutionOutcome` 和 `StepResult`。已记录的 `RESEARCH_REJECTED` 不计 formal round，且 scheduler-forward 到新的 H；其他非 `EVALUATED` 结果停止当前 outer-loop invocation。不要从 `--rounds` 猜测 provider 调用次数。

### 2. Proposal 与 Context

继续读：

- `scion/scion/core/problem_runtime.py`：问题层如何提供 H/C 上下文；
- `scion/scion/core/proposal_pipeline/facade.py`：direct H/C 调用的 host 边界；
- `scion/core/proposal_pipeline/call_journal.py`：`proposal_call.v1` 的最小 append-only H/C call event、可用 trace 与 typed outcome；
- `scion/scion/proposal/context_snapshot.py`、`context_owner_maps.py`：安全字段、不可变 snapshot 与 provider-visible projection；
- `scion/scion/proposal/context_manager/manager.py`：context 组合；
- `scion/scion/proposal/context_manager/code_context.py`：`proposal-source-ledger.v2` 的构建与验证；
- `scion/scion/proposal/engine/`：H/C prompt、provider call 与结构化解析；
- `scion/scion/proposal/schemas/`：H 与 typed multi-file patch schema；
- `scion/scion/proposal/llm/`：transport、timeout、错误分类与 SDK policy。

检查某次失败时，先确认完整 source/context、`proposal_call.v1` event、可用 trace 与 typed outcome，再判断是 response invalid、infra failure 还是后续 gate 拒绝。不要仅凭日志里的自然语言归因。

### 3. Contract -> Verification -> Protocol -> Decision

按 owner 边界读：

- `scion/scion/contract/gate.py` 以及同目录的 `hypothesis_checks.py`、`patch_paths.py`、`patch_graph.py`、`surface_interface.py`；
- `scion/scion/verification/gate.py` 以及同目录的 syntax、interface、state、feasibility、objective、nondeterminism 与 candidate canary checks；
- `scion/scion/protocol/evaluation.py`、`gates.py`、`stats.py`；
- `scion/scion/core/features.py`、`decision.py`、`decision_coordinator.py`、`decision_finalizer.py`。

审核 gate 时问三个问题：输入是否来自它有权信任的 owner；拒绝是否只基于它拥有的规则；结果是否越过 typed boundary 去改变别层的判断。

### 4. Evidence 与 Lineage

接着读：

- `scion/scion/core/evidence_recording/`：durable event、accounting、summary 和 artifact refs；
- `scion/scion/core/formal_candidate_artifacts.py`：formal candidate 与 source/context 身份；
- `scion/scion/core/proposal_trajectory_artifacts.py`、`proposal_trajectory_attempts.py`：direct attempt 轨迹；
- `scion/scion/lineage/registry.py`、`branch_store.py`、`champion_store.py`；
- `scion/scion/core/public_refs.py`、`promotion_service.py`、`promotion_lifecycle.py`。

报告字段与 durable event 不一致时，以 durable event、formal candidate、Protocol raw metrics 和 lineage refs 为依据，并把投影漂移本身记为框架缺陷。

### 5. Generic/problem 边界

再读：

- `scion/scion/problem/contracts.py`、`providers.py`、`loader.py`、`bridge.py`；
- `scion/scion/config/problem.py`、`protocol_config.py`、`split_manifest.py`、`seed_ledger.py`；
- `scion/scion/core/problem_runtime.py` 和 `research_surface_index.py`。

generic 层可以声明接口、传递 typed facts、执行通用安全/科学流程，但不得推断 route、capacity、warehouse assignment、某种 local search 或某个历史 successor 的算法语义。新问题应通过 problem-owned spec、adapter、provider 和 checks 接入，而不是在 core 中增加问题名分支。

### 6. Warehouse

warehouse 是 assignment/bin-packing 型 surrogate，不是 routing 问题。阅读：

- `scion/problems/warehouse_delivery/problem.yaml` 与 `problem-v1.yaml`：问题身份、research surfaces、editable/frozen 边界；
- `scion/problems/warehouse_delivery/protocol_prod.yaml`、`split_manifest_prod.yaml`、`seed_ledger.yaml`：正式科学协议；
- `surrogate/solver.py`、`vns.py`、`models.py`、`oracle.py`：实际 solver 与权威检查；
- `surrogate/operators/`：当前可研究的算法对象。

不要把 CVRP 的 route、distance、2-opt 或 capacity-route 假设带入 warehouse gate 或 prompt。

### 7. CVRP

CVRP 的主要研究对象是完整 solver design。阅读：

- `scion/scion/problems/cvrp/problem.yaml`、`problem-v1.yaml`：问题和 surface 声明；
- `scion/scion/problems/cvrp/adapter.py`、`solver.py`、`solution_checks.py`：解析、执行、可行性与 objective 权威；
- `scion/scion/problems/cvrp/solver_design_provider.py` 与 `solver_design/`：problem-owned 源码/能力事实；
- `scion/scion/problems/cvrp/policies/baseline_algorithm.py` 与 `policies/baseline_modules/`：当前可研究算法；
- `scion/scion/problems/cvrp/contract_checks/`：CVRP 专属静态边界；
- `scion/scion/problems/cvrp/formal/protocol.yaml`、`formal/split_manifest.yaml`、`formal/seed_ledger.yaml`：当前 formal CLI 直跑的科学协议输入。

generic Contract 可以调用 CVRP-owned checks，但不得复制其中的 solver 结构或算法偏好。prompt 应开放研究对象，不得注入 successor 排名、denylist、target-file hint 或指定机制配方。

## 测试通过证明什么

测试分三层理解：

1. 单元/集成测试证明 owner、schema、failure lane 和模块组合符合预期。
2. direct warehouse/CVRP outer smoke 证明控制流能够穿过 Contract -> Verification -> Protocol -> Decision。
3. 从 exact clean commit 运行的正式 warehouse 与 open CVRP control，才可能证明模型做出了有效研究。

框架测试、HTTP 200、非空 completion、生成 patch、进程正常退出或 report 状态都不能单独证明算法研究有效。研究验收必须阅读实际 H、批准绑定、完整 patch、solver 行为变化、Protocol 结果与 full-solver outcome。

## 修改纪律

- 优先删除重复 owner 和兼容层，不为单次实验失败叠加 helper、特殊 gate 或 prompt steering。
- 一个事实只保留一个权威 owner；summary 与 report 只能引用或投影它。
- 保持 problem semantics 在 problem package，保持 generic core 问题无关。
- 修改热路径前先定位对应 Contract/Verification/Protocol/Decision 边界和 durable evidence；同步更新针对该边界的测试。
- 不恢复自动 provider retry、响应修补、partial resume、上下文压缩、语义预算、novelty/material-difference gate 或 telemetry-quality gate。
- 不用 forced surface/action/target 的诊断运行充当正式研究证据。
- 不用历史 campaign 的成功命名、自然语言总结或 successor 关系替代当前源码和当前运行证据。

## 正式运行纪律

正式实验使用当前 CLI 直跑：在仓库根目录设置 `PYTHONPATH=.` 后，通过
`python -m scion.cli.main run` 传入问题、protocol、split、seeds 与独立的
`--campaign-dir`。已删除的 direct launcher、prepared/readiness 与 postrun
工具不是当前入口。

共同边界：

- exact clean commit 和 clean worktree；
- 由当前真实 CLI 解析并记录问题、protocol、split 与 seeds；
- 不使用 forced surface/action/target；
- 不从旧 campaign resume；
- warehouse control 先行，通过逐层证据审核后再运行 clean/open CVRP；
- 按 [`experiment-runbook.zh.md`](operations/experiment-runbook.zh.md) 低频监控，不用高频轮询干扰长实验分析。

当前 worktree 是否获准 stage、commit、prepare 或 launch，只以 `TASK.md` 和 `current-state.md` 为准；不要从本文推断授权。

## 运行环境

Server `claw`：

- repo：`/home/clawd/research/or-autoresearch-agent`；
- Python：`/home/clawd/miniconda3/envs/claw/bin/python`；
- 用于聚焦测试和一次正式运行。

WSL `scion`：

- repo：`/home/xjy-ubuntu/research/or-autoresearch-agent`；
- runner copy：`/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629`；
- Python：`/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`；
- 仅在重新确认连接、代码同步和当前 CLI 配置后用于大型或并发验证。

两边必须从相同 clean commit 分别创建并运行独立 campaign。不要跨机器复用
campaign state 或运行产物，也不要假设 shell 环境变量会跨命令持久存在。

## 开始工作前的检查

- 我是否先读了 `TASK.md` 和 `current-state.md`？
- 我的判断是否服从 V3 与 v0.4 addendum 的 owner 边界？
- 我是否沿真实控制流定位了问题，而不是只看 facade 或 summary？
- 我是否保持完整安全上下文和 `SourceLedger`，没有引入内容丢失？
- 我新增或修改的 gate 是否只保护它有权拥有的边界？
- 我是否区分框架正确、运行有效和算法研究有效？
- 若涉及正式实验，我是否确认 clean commit、当前 CLI 配置、无 forced binding、无 resume 和当前明确授权？

如果其中任何一项答案不明确，先补证据，不要通过新增控制机制来掩盖不确定性。
