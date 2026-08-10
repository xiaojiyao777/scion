# Scion direct-V3 运行后分析交接

*最后更新：2026-08-10*

本文说明如何对已结束的 Warehouse 或 CVRP 运行做轻量、只读分析，从正常研究循环留下
的证据分别判断框架是否按 V3 边界正确执行，以及 agent 是否完成有质量、可归因的算法
研究。进程正常退出、生成代码或某一步通过，都不能单独证明研究有效。

## 1. 唯一架构 authority

唯一架构 authority 是 `scion/design/scion-architecture-v3.md`。

分析只使用 V3 定义的职责与信息流：LLM 提出 H/C，Contract 检查结构边界，
Verification 检查候选仍在正确求解问题，Protocol 产生比较证据，Safe Feature
Extractor 把允许的数值和枚举交给 Decision。LLM 自由文本不能进入 Decision。

分析文档、状态文档和运行说明可以帮助定位事实，但不能改写上述边界，也不能替代
原始运行证据。

## 2. 范围与只读约束

交给分析者 `RUN_ROOT` 与其中的 `campaign/`、exact runtime commit、问题与模型、阶段
配置、case/seed roster、solver time limit，以及预先要回答的研究问题。

分析者只读现有产物，不修改 campaign 状态，不启动或恢复 invocation，不调用外部模型，
不补跑候选。缺失证据必须如实收窄结论，不能用新的框架产物填补。

当前 direct runtime 不写 `artifacts/formal_candidates/` recorder。分析不得把该目录或
formal candidate index 当作前提，也不得为了分析而恢复它。

## 3. 普通运行证据

按需读取以下既有证据，不要求额外生成交接包：

- `campaign/scion.db` 中的 proposal、branch 和 experiment events；
- `campaign/llm_traces/` 中 H/C 调用的上下文、响应和终态；
- `campaign/workspaces/` 的分支源码与 `campaign/champions/` 的 champion snapshot；
- summary 或 events 中的 Contract 与 Verification 结果；
- `campaign/metrics/` 中 Protocol 产生的原始 case/seed/pair 记录；
- Protocol 聚合、Safe Features 与已记录的 Decision。

路径和字段可能随问题 adapter 不同。沿数据库事件中的普通引用定位即可；不要要求每种
运行都有同名汇总文件。结论引用最短且足够的证据位置，例如 event id、branch、trace、
workspace 文件或 raw metric 文件。

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

### 4.5 候选源码可重建性

只有同时满足以下条件，才可把指标归因到某个具体 C：

1. ordinary branch/experiment lineage 给出明确的基线与步骤顺序；
2. 对应终态 C trace 保留 exact patch 或完整的文件修改；
3. 这些修改能够按顺序 exact compose 到该基线；
4. 可用 workspace 或 champion snapshot 与重建结果相符。

若任一条件不能由现有证据证明，将该候选标为 `UNIDENTIFIABLE`。此时仍可报告 H/C
行为、Verification 事实和未归因的 Protocol 观测，但不得声称某个代码机制导致了结果。

分析可以在临时只读副本中做确定性的文本组合；不得写回 campaign，也不得新增长期
recorder。若少于研究设计所需的可重建候选数，直接报告 attribution unidentifiable，
而不是扩大声明。

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
- Candidate reconstruction: RECONSTRUCTED | UNIDENTIFIABLE
- Raw quality / feasibility / runtime evidence:
- Verdict and claim boundary:

## Evidence-backed next action
- Preserve:
- Repair or simplify:
- Next clean experiment, if needed:
```

若结论改变项目状态，再更新 `scion/TASK.md` 与 `scion/docs/status/current-state.md`。
推测、缺失证据和未来实验必须与已观察事实明确分开。
