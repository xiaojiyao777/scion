# Scion v0.4 direct-v3 Onboarding

*Last updated: 2026-09-20*

本文是维护者进入当前 Scion 的稳定源码导览，不是当前状态或历史实验汇总。
v0.4 的目标是让同一套 problem-neutral 精简 V3 runtime 接入不同问题包，为 agent
提供能够持续深入的完整算法源码空间，同时保留必要的安全、科学与证据边界。

## 先读什么

从仓库根 [`AGENTS.md`](../../AGENTS.md) 进入后，按下面顺序建立当前事实：

1. 本文：稳定心智模型、不可变边界和源码入口。
2. [`current-state.md`](status/current-state.md)：可替换的当前工作树、验证和实验快照。
3. [`scion/TASK.md`](../TASK.md)：当前目标、已接受实现与下一条可证伪研究阶梯。
4. [`READING_PROFILES.md`](READING_PROFILES.md)：只选择当前任务所需的一组附加材料。

只有修改 Scion core 或控制边界时，才继续完整阅读
[`scion-architecture-v3.md`](../design/scion-architecture-v3.md)，再读
[`scion-architecture-v3-v0.4-direct-runtime-addendum.md`](../design/scion-architecture-v3-v0.4-direct-runtime-addendum.md)。
V3 是唯一架构权威；addendum 只收窄当前实现。

准备或分析实验时，再读：

- [`operations/README.md`](operations/README.md)：当前操作文档入口；
- [`experiment-runbook.zh.md`](operations/experiment-runbook.zh.md)：direct-v3 准备、启动、低频监控与验收；
- [`postrun-analysis-handoff.md`](operations/postrun-analysis-handoff.md)：运行后逐层还原证据的方法。

历史 experiment、planning、review 和 archive 文档只能解释历史产物，不能覆盖上述当前来源或当前源码。

## 一句话模型

Scion 让模型提出算法假设和代码，但不让模型决定这些改动是否安全、是否有效、是否晋升。当前正式路径是：

```text
完整且安全的问题/源码上下文
  -> 可选的有限 Hypothesis 研究动作，或 direct one-shot
  -> 每个 attempt 最多导出一个 tainted H
  -> Hypothesis Contract
  -> 仅在 H 批准后，可选的有限 Code 研究动作，或 direct one-shot
  -> 每个 attempt 最多导出一个 tainted C
  -> Patch Contract
  -> isolated staging Workspace
  -> Verification
  -> Protocol
  -> Safe Features
  -> deterministic Decision
  -> Evidence + Lineage
```

Creative session 的每个 deliberate provider turn 都计入共享资源上限，但它们
是同一 attempt 内的研究动作，不是 provider retry。H 可先查看完整 source/history
索引并有界读取代码、依赖、调用方、显式 public development tests 与普通历史；C
可有界 read/search/revise/test/finalize。session 只能导出一个 H/C；一旦 finalize、
abstain、abandon、reject 或丢失 provider terminal response，就不能修补、重放、
恢复或重新生成该 H/C。

bounded Creative session 尚未导出 H/C 时，invalid draft/action 可以收到枚举反馈并
作新的 deliberate revision；这不是修补已经导出的 proposal。Code session 中通过
development checks 的最新 draft 调用 `ready` 后立即导出该 patch，不再要求另一次
provider confirmation 或 closure；若 turn 用尽时已有通过检查的冻结 draft，才使用一次
`finalize_patch`/`abandon` 终局选择。direct one-shot response 或 bounded session 在
没有有效导出的情况下关闭时，该 tainted attempt 记为 `RESEARCH_REJECTED`，不计
formal round；scheduler 随后进入 fresh H。Contract 或 Verification 的
`RESEARCH_REJECTED` 遵循相同规则。

默认 H/C transcript 总字符数不设上限，但每个 deliberate provider turn、read、
search、public-test 和 output 仍精确计数；显式 operator-selected limit 只是资源边界，
不是研究质量策略。一个已经 dispatch 的 session 耗尽本地 turn/result/transcript
上限时只拒绝当前 attempt 并继续调度；若完整初始上下文本身在第一次 dispatch 前就
无法满足显式 H limit，则保持 `RESOURCE_EXHAUSTED`，不能靠截断或摘要偷偷开始。

Provider SDK retry 始终为零。显式 ResourceEnvelope 可以让同一个冻结请求对 typed
timeout、transport、provider 或 rate-limit failure 做有限次 charged/traced
redispatch；耗尽后只产生一次 attempt-local operational `RESEARCH_REJECTED`，不进入
后续算法历史。local proxy 的精确 synthetic 401 sentinel 归为 temporary provider
unavailability；真实或非精确 auth、balance、显式全局 provider-call cap、没有 provider
terminal response、无效 local context、missing typed outcome 和 interruption 仍是
terminal/hold 类结果。每次物理 dispatch 最多写一个 best-effort terminal trace；
trace 不是 receipt 或 call identity，写失败不能改变有效 provider 结果。

## 不可变边界

### 模型只拥有创造性提案

- 模型输出始终是 tainted input。
- H 描述研究假设、改动位置和预期因果机制；C 必须绑定已经批准的 H。
- 模型不能写入 Protocol 结果、DecisionFeatures、分支状态、调度状态或 promotion 状态。
- prompt 中的说明不能替代 Contract、Verification 或 Protocol 的确定性证据。

### 上下文必须完整、安全且值一致

- `ProblemRuntime` 构建一份经过验证的 ordinary corpus；每个 deliberate provider
  turn 只形成一个不可变 provider-visible projection，不给 corpus 或 projection
  附加 identity/authority 语义。
- direct H 获得完整安全上下文；启用 bounded research 时，H 先获得完整普通 source/history 索引，并按需有界读取 target、依赖、调用方、显式 public tests 与历史正文，不做 recent-N/top-k。
- C 获得一个批准的 H 和普通的完整 path/content source mapping；每个可见文件只有规范路径与完整内容，多文件算法改动不是例外路径。
- validation/frozen 原始记录、Decision 输入和其他禁止暴露的事实不得进入 proposal context。
- bounded Creative path 有显式 provider-turn/read/search/public-test/output 计数；
  transcript 默认不设总字符上限，operator 仍可显式声明资源边界。所有限制都不能
  选择研究方向，也不做 top-N、静默截断、compact-to-fit 或摘要替代。
- provider 必需的 transport ceiling 与 solver/subprocess 的科学 time limit 必须显式记录；它们不是 Scion 的语义研究预算或隐藏终止策略。

### Branch 是完整算法对象的持续研究空间

- 每个 live branch 的 `current` 是一棵普通、完整、可执行的源码树，不是 patch
  identity 或 manifest；正常连续研究直接使用这棵完整 tree。
- Contract 与 Verification 通过且 screening 完成后，`CONTINUE_EXPLORE`（包括科学
  screening fail）保留该 candidate 为 branch 的 verified provisional head。下一次 H
  看到完整安全证据，下一次 C 从该完整源码树继续修改。
- Contract/Verification 失败的代码不能进入 executable head；此时回到最后一棵 clean
  branch source，从未产生 verified head 的 branch 才回到 champion。
- expansion、validation 与 frozen 复用同一个 exact candidate，不重新生成、拼接或
  重放 patch。provisional head 不能绕过 held-out 或 promotion。
- live campaign 可以长时间沿 branch head 继续研究；terminal/interrupted campaign
  不恢复半截 mutable state。champion 变化后的 stale reconcile 在完整 branch tree
  的隔离副本上重新 Verification/screening，不重放 patch 或合并 champion 改动。
  CLI `--source-tree` 可显式选择完整目录作为 fresh campaign baseline，并独立复制为
  只读 snapshot；可选 `--research-history` 仍只供 H 使用，不恢复旧状态。

### Gate 只保护自己的边界

| 边界组件 | 只负责什么 | 不负责什么 |
|---|---|---|
| Contract | schema、editable/frozen path、action、import/API/interface、patch graph、C 与批准 H 的绑定 | 评价想法是否新颖、偏好某种算法机制、用 telemetry 文本给研究风格打分 |
| Verification | syntax、接口执行、state isolation、feasibility、objective recomputation、nondeterminism、crash、timeout、invalid solver output | 用比较性能提前替代 Protocol，因诊断 telemetry 不完整而要求模型重写 |
| Protocol | screening/validation/frozen 隔离、seed/split、成对比较、统计与 typed scientific verdict | 请求另一轮 H/C，修改候选代码或把自由文本交给 Decision |
| Decision | 把可信 Protocol verdict 与 hard-safety facts 确定性映射为 branch action | 重算统计阈值、解释模型 reasoning、按机制偏好改判 |
| Scheduler | runnable state、priority/FIFO、active slots 与显式 execution hold | 判断科学真伪、用历史建议替代 Decision、引导模型复刻某个 successor |

diagnostic telemetry 可以帮助人分析运行，但不能越权成为另一套研究 gate。问题特有的 objective、feasibility、solver、surface 与 telemetry 含义属于 problem package；generic core 不得内嵌 warehouse 或 CVRP 算法知识。

只有 complete paired observations 可以把 problem-owned mechanism-family
association 暴露给后续 H。它只是非因果 proposal context，不是 exact activation、
host mechanism selection、Protocol gate、Safe Feature 或 Decision input。

### 证据和晋升必须可追溯

- tainted H/C、typed outcome、Contract、Verification、Protocol 与 Decision
  通过普通研究记录串起来；每个 deliberate provider turn 的可选 terminal
  trace 仅作诊断，写失败不能丢弃有效 H/C。trace 不构成 call identity、receipt
  或另一份事实账本。
- lineage 是 append-only 事实；summary、analysis brief 和 inventory 是索引或投影，不是新的事实来源。
- promotion 必须拥有完整的 declared screening、validation、frozen Protocol evidence；普通 candidate cleanup 或可选报告写入只能记录诊断，不能改写已经完成的科学 Decision。
- direct response/session closed without valid export 是 proposal-phase
  `RESEARCH_REJECTED`；open-session invalid action 只是枚举反馈。无 provider 终态、
  `not_evaluated`、`blocked_infra`、`resource_exhausted`、`interrupted` 与
  `evaluated` 仍是不同结果，不能为了报表整洁而合并。

## 按执行顺序阅读源码

下面的顺序比按目录通读更容易看清真实职责。`CampaignManager` 是组合 facade，不要只读它就推断整个 runtime。

### 1. Campaign loop 与一次 branch step

先读：

- `scion/scion/core/campaign.py`：对外 facade 和 runtime 组合入口；
- `scion/scion/core/campaign_composition.py`：各边界组件的实际装配；
- `scion/scion/core/campaign_loop.py`：以 typed formal evaluated rounds 为目标的外层循环；
- `scion/scion/core/branch_step_runner.py`：scheduler action 到 explore/eval/reconcile 的分派；
- `scion/scion/core/explore_step/pipeline.py`：H、H Contract、C、Patch Contract、Workspace、Verification 与 evaluation 的主路径；
- `scion/scion/core/evaluation_orchestrator.py`、`evaluation_pipeline.py`：候选进入 Protocol 与结果回传的边界；
- `scion/scion/core/decision_finalizer.py`：Decision 后的状态与证据收口。

阅读时逐个追踪 `ExecutionOutcome` 和 `StepResult`。direct proposal/session closed
without valid export、started-session local limit、transient-provider exhaustion、
Contract 或 Verification `RESEARCH_REJECTED` 不计 formal round，且 scheduler-forward
到 fresh H；open-session invalid action 不产生另一个 attempt。auth、balance、global
cap、pre-dispatch context/resource、missing terminal/local typed outcome 与 interruption
仍停止或 hold 当前 outer-loop invocation。不要从 `--rounds` 猜测 provider 调用次数。

### 2. Proposal 与 Context

继续读：

- `scion/scion/core/problem_runtime.py`：问题层如何提供 H/C 上下文；
- `scion/scion/core/proposal_pipeline/facade.py`：direct H/C 调用的 host 边界；
- `scion/scion/proposal/hypothesis_research_session.py`、`code_research_session.py`：可选有限 Creative research actions 与单一 H/C 导出；
- `scion/scion/proposal/context_snapshot.py`：安全字段、不可变 context value 与 provider-visible projection；
- `scion/scion/proposal/context_manager/manager.py`：context 组合；
- `scion/scion/proposal/context_manager/code_context.py`：普通 editable path/content source context 的构建与验证；
- `scion/scion/proposal/engine/`：H/C prompt、provider call 与结构化解析；
- `scion/scion/proposal/schemas/`：H 与 typed multi-file patch schema；
- `scion/scion/proposal/llm/`：transport、timeout、错误分类与 SDK policy。

检查某次失败时，先确认完整 source/history index、按需读取的 ordinary context、
是否已经发生 provider dispatch、可用 trace 与 typed outcome。open session 的
invalid action 只返回枚举反馈；successful `ready` 直接导出；session closed without
valid export、started-session local-limit 或 transient-provider exhaustion 是
scheduler-forward proposal `RESEARCH_REJECTED`。其他 terminal/hold lane 仍保持其
原始 typed category。不要仅凭日志里的自然语言归因。

### 3. Contract -> Verification -> Protocol -> Decision

按职责边界读：

- `scion/scion/contract/gate.py` 以及同目录的 `hypothesis_checks.py`、`patch_paths.py`、`patch_graph.py`、`surface_interface.py`；
- `scion/scion/verification/gate.py` 以及同目录的 syntax、interface、state、feasibility、objective、nondeterminism 与 candidate canary checks；
- `scion/scion/protocol/evaluation.py`、`gates.py`、`stats.py`；
- `scion/scion/core/features.py`、`decision.py`、`decision_coordinator.py`、`decision_finalizer.py`。

审核 gate 时问三个问题：输入是否来自前一条明确的数据流；拒绝是否只基于本层规则；结果是否越过 typed boundary 去改变别层的判断。

### 4. Evidence 与 Lineage

接着读：

- `scion/scion/core/evidence_recording/`：durable event、accounting、summary 和 artifact refs；
- `scion/scion/core/research_history.py`：显式、H-only 的普通跨 campaign 研究历史；
- `scion/scion/lineage/registry.py`：当前最小 append-only lineage；
- `scion/scion/core/branch.py`、`workspace_service.py`、`promotion_service.py` 与当前 branch/promotion 路径。

当前 campaign 不生成 formal-candidate identity/hash 闭包。报告字段与 durable event
不一致时，以 step history、branch workspace、champion snapshot、Protocol raw metrics
和 lineage refs 为依据，并把投影漂移本身记为框架缺陷。

### 5. Generic/problem 边界

再读：

- `scion/scion/problem/contracts.py`、`providers.py`、`loader.py`、`bridge.py`；
- `scion/scion/config/problem.py`、`protocol_config.py`、`split_manifest.py`、`seed_ledger.py`；
- `scion/scion/core/problem_runtime.py` 和 `research_surface_index.py`。

generic 层可以声明接口、传递 typed facts、执行通用安全/科学流程，但不得推断 route、capacity、warehouse assignment、某种 local search 或某个历史 successor 的算法语义。新问题应通过 problem-owned spec、adapter、provider 和 checks 接入，而不是在 core 中增加问题名分支。

当前 generic core 没有直接按 Warehouse/CVRP 分支，但仍残留
`operator_pool`、`operator`、`policy`、`construction`、`portfolio` 等算法形状词汇。
这是已知 problem-neutrality 债务，不是可继续扩展的模板。后续应把含义移到
problem-owned declaration 或 opaque observation，并保持它们不进入新的
Protocol/Decision gate；不要为修它引入 registry、identity 或 telemetry 自证层。

### 6. Warehouse

warehouse 是 assignment/bin-packing 型 surrogate，不是 routing 问题。阅读：

- `scion/problems/warehouse_delivery/problem.yaml` 与 `problem-v1.yaml`：问题定义、research surfaces、editable/frozen 边界；
- `scion/problems/warehouse_delivery/protocol_prod.yaml`、`split_manifest_prod.yaml`、`seed_ledger.yaml`：正式科学协议；
- `surrogate/solver.py`、`vns.py`、`models.py`、`oracle.py`：实际 solver 与确定性语义检查；
- `surrogate/operators/`：当前可研究的算法对象。

不要把 CVRP 的 route、distance、2-opt 或 capacity-route 假设带入 warehouse gate 或 prompt。

### 7. CVRP

CVRP 的主要研究对象是完整 solver design。阅读：

- `scion/scion/problems/cvrp/problem.yaml`、`problem-v1.yaml`：问题和 surface 声明；
- `scion/scion/problems/cvrp/adapter.py`、`solver.py`、`solution_checks.py`：解析、执行、可行性与 objective 检查；
- `scion/scion/problems/cvrp/solver_design_provider.py` 与 `solver_design/`：problem-owned 源码/能力事实；
- `scion/scion/problems/cvrp/policies/baseline_algorithm.py` 与 `policies/baseline_modules/`：当前可研究算法；
- `scion/scion/problems/cvrp/contract_checks/`：CVRP 专属静态边界；
- `scion/scion/problems/cvrp/formal/protocol.yaml`、`formal/split_manifest.yaml`、`formal/seed_ledger.yaml`：当前 formal CLI 直跑的科学协议输入。

generic Contract 可以调用 CVRP-owned checks，但不得复制其中的 solver 结构或算法偏好。prompt 应开放研究对象，不得注入 successor 排名、denylist、target-file hint 或指定机制配方。

## 测试通过证明什么

测试分三层理解：

1. 单元/集成测试证明组件职责、schema、failure lane 和模块组合符合预期。
2. direct warehouse/CVRP outer smoke 证明控制流能够穿过 Contract -> Verification -> Protocol -> Decision。
3. 从运行期间冻结、如实记录的完整源码状态执行正式 problem control，才可能证明模型做出了有效研究；Git clean/commit 是方便的定位方式，不是算法研究 gate。

框架测试、HTTP 200、非空 completion、生成 patch、进程正常退出或 report 状态都不能单独证明算法研究有效。研究验收必须阅读实际 H、批准绑定、完整 patch、solver 行为变化、Protocol 结果与 full-solver outcome。

## 修改纪律

- 优先删除重复 writer、状态来源和兼容层，不为单次实验失败叠加 helper、特殊 gate 或 prompt steering。
- 一个事实只保留一个普通 writer/source；summary 与 report 只能引用或投影它。
- 保持 problem semantics 在 problem package，保持 generic core 问题无关。
- 修改热路径前先定位对应 Contract/Verification/Protocol/Decision 边界和 durable evidence；同步更新针对该边界的测试。
- 不恢复隐藏 SDK retry、响应修补、partial resume、上下文压缩、语义预算、
  novelty/material-difference gate 或 telemetry-quality gate；只有显式 ResourceEnvelope
  内同一冻结请求的有限 charged/traced transient redispatch 可以存在。
- 不用 forced surface/action/target 的诊断运行充当正式研究证据。
- 不用历史 campaign 的成功命名、自然语言总结或 successor 关系替代当前源码和当前运行证据。
- 当前阶段不投入 distribution、packaging、build、deploy、root/systemd、
  Trust/Hash authority、object identity、lease、signing、registration、receipt 或
  duplicate closure。

## 正式运行纪律

自主 H/C 正式实验使用当前 CLI 直跑：在仓库根目录设置 `PYTHONPATH=scion:.` 后，
通过 `python -m scion.cli.main run` 传入问题、protocol、split、seeds 与独立的
`--campaign-dir`。已冻结 exact candidate 的 provider-free estimand 只使用
`run_fixed_candidate_funnel.py`，导出 H/C 与 provider calls 均为零，同时保留
complete-pair canary -> Protocol -> Safe Features -> Decision。已删除的 direct
launcher、prepared/readiness 与 postrun 工具都不是入口。

共同边界：

- 明确记录并在运行期间冻结的完整源码状态；如有 Git revision 或未提交 diff，
  如实记录即可，不把 clean commit/worktree 变成身份或授权 gate；
- 由当前真实 CLI 或 narrow fixed-funnel driver 解析并记录问题、protocol、split
  与 seeds；
- 不使用 forced surface/action/target；
- 不从旧 campaign resume；显式 H-only ordinary history 不等于 mutable reopen；
- 普通 problem-owned 算法研究只运行本问题声明的 Contract、Verification、canary
  与 Protocol；只有 shared core/adapter boundary 改动或明确的跨问题验收任务，才按
  当前预注册额外运行另一个问题的 control。不要把 Warehouse→CVRP 顺序固化成
  generic Scion gate；
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

两边必须从同一份明确记录且运行期间冻结的完整源码状态分别创建独立 campaign。
不要跨机器复用 campaign state 或运行产物，也不要假设 shell 环境变量会跨命令持久存在。

## 开始工作前的检查

- 我是否按根 `AGENTS.md` 的唯一顺序读完了 onboarding、`current-state.md`、
  `TASK.md` 和所选 reading profile？
- 我的判断是否服从 V3 与 v0.4 addendum 的职责边界？
- 我是否沿真实控制流定位了问题，而不是只看 facade 或 summary？
- 我是否保持完整安全上下文和 ordinary path/content source mapping，没有引入内容丢失或 identity wrapper？
- 我新增或修改的 gate 是否只保护它有权拥有的边界？
- 我是否区分框架正确、运行有效和算法研究有效？
- 若涉及正式实验，我是否确认源码状态已记录并冻结、当前 CLI 配置、无 forced
  binding、无 resume，并且行动没有超出 `TASK.md`/`current-state.md` 记录的用户授权范围？

如果其中任何一项答案不明确，先补证据，不要通过新增控制机制来掩盖不确定性。
