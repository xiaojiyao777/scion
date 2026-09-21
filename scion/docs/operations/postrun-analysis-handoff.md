# Scion direct-V3 运行后分析交接

*最后更新：2026-09-05*

本文说明如何对已结束的 Warehouse 或 CVRP 运行做轻量、只读分析，从正常研究循环留下
的证据分别判断框架是否按 V3 边界正确执行，以及 agent 是否完成有质量、可归因的算法
研究。进程正常退出、生成代码或某一步通过，都不能单独证明研究有效。

新会话先读 [`../../../AGENTS.md`](../../../AGENTS.md) 及其指向的当前交接。本文只定义
运行后分析方法，不定义当前项目状态、修改/提交权限或后续实验授权。

## 1. 唯一架构 authority

唯一架构 authority 是 `scion/design/scion-architecture-v3.md`。

分析只使用 V3 定义的职责与信息流：LLM 提出 H/C，Contract 检查结构边界，
Verification 检查候选仍在正确求解问题，Protocol 产生比较证据，Safe Feature
Extractor 把允许的数值和枚举交给 Decision。LLM 自由文本不能进入 Decision。

分析文档、状态文档和运行说明可以帮助定位事实，但不能改写上述边界，也不能替代
原始运行证据。

## 2. 范围与只读约束

交给分析者 direct runtime 的 `CAMPAIGN_DIR`（campaign directory 本身就是证据根）、
运行时源码位置/revision、问题与模型、阶段配置、case/seed roster、solver time limit，
以及预先要回答的研究问题。provider-free fixed funnel 则交付它自己的 fresh output
root；不要为两者虚构共同的 `RUN_ROOT/campaign/` 包装层。

源码位置和 Git revision 只是帮助定位当时运行的普通事实，不签发、登记或授权一个
算法对象。不要为分析补建 source hash、identity、lease、receipt、manifest closure
或 Trust 链。

分析者只读现有产物，不修改 campaign 状态，不启动或恢复 invocation，不调用外部模型，
不补跑候选。缺失证据必须如实收窄结论，不能用新的框架产物填补。

当前 direct runtime 不写 `artifacts/formal_candidates/` recorder。分析不得把该目录或
formal candidate index 当作前提，也不得为了分析而恢复它。

## 3. 普通运行证据

按需读取以下既有证据，不要求额外生成交接包。direct runtime 路径都相对于
`$CAMPAIGN_DIR`：

- `status.json` 与 `campaign_summary.json` 中的终态、step、Contract、Verification、
  Protocol、Decision 和 ordinary artifact refs；
- `research_history.jsonl` 与其他已有 JSON/JSONL events；
- `llm_traces/` 中 H/C 调用的上下文、响应和终态；
- `candidate_workspaces/` 中实际送入 Verification/Protocol 的完整 candidate 源码，
  `workspaces/` 中的完整 branch 源码，以及 `champions/` 的完整 champion snapshot；
- `metrics/` 中 Protocol 产生的原始 case/seed/pair 记录；
- Protocol 聚合、Safe Features 与已记录的 Decision。

优先使用 JSON、JSONL、raw metrics 与普通源码树，沿其中的 ordinary refs 定位。
不要直接打开 live/original `scion.db`：普通 SQLite 客户端可能创建 WAL/SHM/journal
sidecar 或干扰仍在运行的现场。只有上述证据确实缺失关键事实时，才在进程停止后使用
单独的只读数据库快照作为次级定位手段，且不得把查询产物写回 campaign。

路径和字段可能随问题 adapter 不同；不要要求每种运行都有同名可选文件。结论引用最短
且足够的证据位置，例如 JSON/JSONL event、branch、trace、workspace 文件或 raw metric
文件。

## 4. 分析顺序

### 4.1 先界定运行与污染

先确认所读 campaign 属于目标 runtime，并记录启动、终止和完成状态。区分：

- 正常完成；
- provider、进程、磁盘、时间预算或数据等 infra failure；
- 与正式 solver 同时争用 CPU、内存或 I/O 的 operator contamination；
- 候选代码自身的 crash、timeout 或不可行结果。

存在污染时仍可分析 H/C 研究行为和发现候选，但必须把性能结论降为探索性。严格晋升
结论只能来自预先声明且未受污染的 Protocol 运行。只有启动前证据时，不评价算法质量。

### 4.2 审核 H 的 source grounding

从 proposal/experiment events 和对应终态 H trace 检查 agent 实际看到的问题说明、源码
与前序事实；H 是否指向真实文件、符号和执行路径；机制是否具体、可证伪并说明预期
影响；以及 H 是否混淆算法、infra 与框架问题。

H 的质量是研究问题，不是 Decision 输入。上下文不足应记录为 context composition 问题，
不能事后把一个合理 H 判成结构违规。

### 4.3 审核 C 的实现 fidelity

从获批 H、终态 C trace 和可用源码检查 C 是否实现所称机制、修改是否进入 solver 的
实际执行路径、多文件依赖与状态更新是否完整，以及是否只是脚手架、注释、重排或部分
实现。

把 C 分为 faithful、partial 或 scaffolding-only，并给出源码依据。该判断解释研究行为，
不替代 Contract、Verification 或 Protocol。

### 4.4 Contract 与 Verification

Contract 只回答结构边界是否满足，例如可编辑 surface、patch action、接口与 import。
不要把算法风格、机制偏好、预期收益或诊断丰富度追加成新的硬条件。

Verification 只回答候选是否仍在解同一个问题：语法与接口、feasibility、objective
一致性、状态泄漏、确定性、crash 和 timeout。失败必须归因到 candidate、framework、
problem/data 或 infra；不完整诊断本身不应覆盖正确的 solver 结果。

### 4.5 候选完整源码与归因

算法对象首先是一棵完整、可运行的普通源码树，不是一条 patch/hash/receipt 链。把
Protocol 指标归因到某个候选至少需要：

1. ordinary branch/experiment event 指向实际评估的 branch/candidate；
2. 对应 stage 使用的完整 workspace 或 champion snapshot 仍可只读取得；
3. Contract、Verification、Protocol 的普通引用与这棵源码树相符；
4. 若进一步声称某个 H/C 机制导致结果，对应终态 C trace 或普通 diff 足以说明该
   机制确实进入执行路径。

完整 stage source 存在时，不要求从起始基线重复重放整条 accepted-patch chain，也不
为它补建 identity、digest closure 或来源证明。完整 source 缺失时，可以在临时只读
副本中把 ordinary patch sequence 作为兼容性定位手段；若仍不能确定实际受测源码，标为
`UNIDENTIFIABLE`，只报告可直接观察的 H/C、Verification 和未归因 Protocol 事实。
不得写回 campaign，也不得为分析新增长期 recorder 或自证账本。

### 4.6 Protocol、Safe Features 与 Decision

对每个可分析阶段读取 raw metrics，并核对最小科学事实：

- case、seed、candidate/champion 两侧是否都实际完成；
- feasibility、absolute objective、elapsed time 和 bounded failure；
- AB/BA 执行顺序、solver limit 与样本扩展是否符合预先设计；
- win/loss/tie、effect estimate 与不确定性是否能由 raw pairs 解释。

每个阶段先写清 estimand：比较谁、在哪个 case/seed population、以什么指标和统计量。
screening、validation、frozen/heldout 若使用不同 population，各自只支持自己的声明；
不能把跨阶段、不同样本的效果拼成连续提升轨迹。

Safe Features 只能来自 Contract、Verification 与 Protocol 的 typed 事实。分析检查记录的
Decision 是否只消费这些输入，以及相同输入是否确定地产生已记录 action。

运行后分析永不重判 Decision：不根据 hindsight 改写 action，不从 provider prose 生成
新 action，也不把分析者自己的阈值冒充原 Decision。发现输入、实现或边界错误时，报告
framework defect；原 Decision 仍作为历史事实保留。

### 4.7 回到算法研究

在源码可重建且 Protocol 证据适用时，说明 agent 选择了什么算法机制、为什么与当前
solver 有关、实现 fidelity 与行为变化如何；综合 feasibility、objective、质量、
runtime 和失败分布，判断证据支持可复现收益、有信息量的无收益还是仅候选发现，并将
结论限制在实际覆盖的 Warehouse 或 CVRP population。

不得用 gate 数量、调用成功率或 patch 数量代替算法研究质量。

## 5. 两个独立 verdict

### Framework correctness

判断 H/C 信息流、Contract、Verification、Protocol、Safe Features 与 Decision 是否各守
V3 职责，ordinary events 和原始指标是否足以支持已记录事实，并单列 infra/contamination。

### Research effectiveness

判断 H 是否有源码根据、C 是否忠实进入 solver 路径、实验 estimand 是否明确、指标是否
支持限定范围内的算法结论。源码不可重建或样本不支持时，写 `UNIDENTIFIABLE`，不要把
它误写成算法无效。

允许的组合包括“框架正确、研究无效”“框架错误、研究效果不可识别”以及“两者均通过”。
框架失败不能自动证明算法失败，算法无收益也不能自动证明框架失败。

## 6. 交付模板

```markdown
# <run> Read-only Analysis

## Scope
- Runtime / problem / model:
- Stage estimands and claim boundaries:
- Infra or contamination:

## Framework correctness
- H/C flow and context:
- Contract / Verification:
- Protocol / Safe Features / recorded Decision:
- Verdict:

## Research effectiveness
- H source grounding:
- C implementation fidelity:
- Candidate source: FULL_SOURCE_IDENTIFIED | PATCH_FALLBACK_IDENTIFIED | UNIDENTIFIABLE
- Raw quality / feasibility / runtime evidence:
- Verdict and claim boundary:

## Evidence-backed next action
- Preserve:
- Repair or simplify:
- Next clean experiment, if needed:
```

若结论改变项目状态，按 `AGENTS.md` 声明的当前交接文档职责更新
`scion/TASK.md` 与 `scion/docs/status/current-state.md`。
推测、缺失证据和未来实验必须与已观察事实明确分开。
