# Scion 阶段评审与 v0.5 研究机制提案

初稿：2026-11-14；主线确认、里程碑采纳与阶段收官：2026-11-15。
本次审计所依据的实现：`c82b77ef`，`v0.4-dev`。
定位：阶段分析、已接受的研究主线与阶段收官规则，以及早期机制提案。
它不是已接受的新架构，也不授权实验。
唯一架构权威仍是 [V3](../../../design/scion-architecture-v3.md)；
当前实现解释仍是 [direct-runtime addendum](../../../design/scion-architecture-v3-v0.4-direct-runtime-addendum.md)。

**当前应改变的重点是研究工作单元：让 agent 能持续调查一个算法问题，
主动取得区分竞争解释的证据，再提交 H/C，而不只是不断完成下一份补丁的评价。**
v0.4 已建立值得保留的执行、隔离和科学裁决骨架；CVRP 的独立保留收益仍未得到确认。
现有证据足以支持转向研究机制设计，但不足以证明某个新机制必然带来算法改进。

11 月 15 日用户明确认可主线：**让 agent 围绕一个持续的算法问题，自主观察、
实验、修正解释，再提交正式 H/C。** 随后明确认可下文阶段标准，要求收官 v0.4、
保留 CVRP 未完成科学目标并开展 v0.5 详细设计。**v0.4 机制阶段已收官，原科学成功
验收部分达成。** 具体机制由新的 [v0.5 设计与验收](../../../design/v0.5/README.md)
继续细化；该详细草案尚不是实现或实验授权。本报告第 5–7 节保留分析来源，
后续具体接口和对照方案以新设计草案为准。
11 月 14 日完成的文档、源码和既有结果核验，以及本次收官记录，都没有修改运行代码、
算法、科学输入或原始产物，也没有运行 provider、solver 或重新开启 terminal campaign。

## 1. R26 提供了什么新事实

[R26 终态审计](../../experiments/v0.4/v04-cvrp-r26-scope-and-net-benefit-autonomous-postrun-20261114.md)
确认：北京时间 2026-10-29 14:30:25 完成，12/12 screening stages，
9 个实际评价候选，324 条有效配对记录，648 次有效 solver side；
162/600 次 provider 调用全部成功。一次 C abandonment 后调度了 fresh H。
没有 validation、frozen 或 promotion，champion v1 未改变。
12 个 stage 的 case-median aggregate effect 均为 0。

这个结果不能再简单解释为“agent 不会写真实路径测试”。R26 A1 已断言真实 solve
中非空的 cache publication 和 reuse；最终 A4 在 80-customer synthetic real solve
中观察实际内核完成改进、后续真实工作与最终收益保留。研究测试能力确实在进步。
该见证证明经过新评估路径的 two-opt 改进能够保留，未证明它比继承实现增加净收益。
这些有限实例上的正确证据，仍没有转化为正式问题分布上的稳定净优势。

近期三轮使用同一完整 R22 C3 作为本地 comparator，研究能力与最终效果需要分开看：

|运行|完成评价 stages|实际候选|有效配对行|Provider calls|科学结论|
|---|---:|---:|---:|---:|---|
|[R24](../../experiments/v0.4/v04-cvrp-r24-stable-advantage-autonomous-postrun-20261026.md)|12|6|384|86|A2 expanded +12.75 [0,83.25]，validation +40 [-35.25,606.25]，未晋升|
|[R25](../../experiments/v0.4/v04-cvrp-r25-counterfactual-evidence-autonomous-postrun-20261028.md)|12|10|296|137|全部 stage 中位效果 0，未进入 held-out|
|R26|12|9|324|162|全部 stage 中位效果 0，三个初筛信号扩大后均未通过|

这些是工作量和各轮结果的并列陈述，不能合成一个效果估计。
expanded stages 重跑 initial cells，普通自主路径采用 champion-first；
同 case/seed 的 timed comparator 也可能改变结果。固定 seed 不等于固定搜索轨迹。
已知 screening cases 继续属于自适应开发数据，换 seed 不会使它们重新成为未见问题。

R24–R26 没有耗尽全局调用上限，不支持把停滞归因于账户或全局额度。
这也不证明局部 H/C turn、probe 时间或工具表达能力足够。
R26 有一次局部 C session abandonment，必须和 campaign 正常完成同时保留。

## 2. v0.4 已经建立的能力

当前 Scion 不是纯 one-shot，也不是只能改固定算子或调几个参数。
CVRP 的 `solver_design` 已暴露普通完整算法对象，允许修改主算法和多个模块。
live branch 保存 verified provisional source head，科学 screening fail 后可继续深入；
Contract/Verification 失败才不能进入 executable head。历史记录和源码可被 H 检索，
C 可读源码、修订 draft 和运行公开开发检查。

当前主路径是：

```text
完整安全源码与历史 → H 调查 → 一个 H → Hypothesis Contract
→ C 调查与实现 → 一个 C → Patch Contract → 隔离源码树
→ Verification → Protocol → Safe Features → deterministic Decision
→ 精确候选复用、分支持续研究或晋升
```

这条路径的重要成果包括：

- **可信执行与裁决。** 模型可以提出算法，但不能写入正式结果或决定晋升。
  正确性、可行性、objective recomputation 与比较性能分别由相应边界处理。
- **完整算法持续演化。** 不再依赖单个 patch 身份或每轮回到 champion；
  多文件改动和 verified source continuation 已经存在。
- **真实算法研究。** R24–R26 包含精确 DP、搜索证书、solve-local cache、
  多路重插入和增量计算等实质实现，不能一概称作无意义微调。
- **跨问题与科学负结果。** Warehouse 已有接受的 retained improvement；
  CVRP R3i 有 development promotion，后续独立比较没有确认其 B0 优势。
  拒绝不稳定收益正是科学边界的价值。

因此，下一版不应重复以“开放更多算法文件”“允许多轮对话”作为主要交付，
也不应通过减弱 gate 来制造成功。需要提升的是已有空间内的研究能力。

## 3. 目前哪些工作仍由 Scion 外部研究者完成

最近的循环大致是：Scion 提案并跑完整比较；外部审计再指出 observer 改变 function
identity、reference scope 不一致、断言为空、own gain 不等于 comparative gain 等问题；
开发者补 optional examples 与 research question；下一 campaign 再尝试。
每次修复都有价值，但整体上，研究方法的纠错和下一项判别实验仍部分由外部人或 agent 代做。

[V3 §1.5](../../../design/scion-architecture-v3.md) 的目标是“人在回路但不在循环里”。
现在外部参与不限于定义问题、审查 oracle 和审阅最终结果，还在连续设计研究方法。
真正的框架进展，应逐步把这些能力交给 Scion 的研究 agent。

应明确区分两种判断：

- **研究判断：** 哪个解释更可能、应看什么数据、下一个实验能排除什么、是否修正假设。
  这些是 agent 应拥有的创造性工作，仍可能出错。
- **系统裁决：** 哪份候选合规、是否可行、是否正式通过、是否晋升。
  这些继续由 Contract、Verification、Protocol 与 Decision 决定。

不让 LLM 决定晋升，并不意味着它只能写补丁而不能选择如何调查问题。

## 4. 源码支持的结构性缺口

### 4.1 H 在形成假设前不能获取新运行证据

[H session](../../../scion/proposal/hypothesis_research_session.py)
提供 source/history read/search 与 H finalize/abstain 等动作，没有测量执行入口。
它能认真阅读已有证据，却不能先测 baseline 的实际成本分布、小实例参考结果、
路径是否完成或某个失败条件，再决定应该提出什么 H。

这不是“模型肯定缺乏诊断能力”的证明；它是框架没有直接提供这种能力的事实。
因而当前实验无法区分“模型不能调查”和“接口不允许它充分调查”。

### 4.2 C 的实验接口以检查为中心，缺少开放观察

[C session](../../../scion/proposal/code_research_session.py) 的 `test_patch` 要求先有 draft。
[probe runner](../../../scion/verification/development_probe.py) 丢弃 pytest stdout/stderr
和 assertion explanation，只返回有限类别与 probe line。
最终投影主要是 outcome、checks、counts 和枚举诊断，不能一般性返回测量表、
时间曲线、搜索轨迹或实际 expected/observed 值。

于是，“我想知道某个量是多少”容易被改写成“我先猜它是什么，再写断言”。
对声明性 correctness test 这是有用接口，对开放式研究却不充分。
小型 probe 当前硬上限为 10 秒，正式 solver limits 可达 60–240 秒；
缺少 agent 可自主选择的中间测量层。单纯延长所有 tests 不能解决输出与目的混淆。

[development execution](../../../scion/verification/development.py) 将 pytest exit 1
统一为 failed，不能判断是实现错误、错误 expected，还是一个收益假说被否定。
当前 C 会保留该 session 中 failed falsifier 的 exact executable value 拒绝状态。
这保护了已提交反例不能被弱化测试抹去，但也说明一般探索不适合全塞入 falsifier。
这是设计风险；不能据此断言所有负结果都由这个规则造成。

### 4.3 源码持续存在，研究材料的持续性弱得多

[research history](../../../scion/core/research_history.py) 保存 H、basis、patch、outcome、
Protocol 和 Decision；C 的工具结果主要存在本次 session 和诊断 trace。
下一 attempt 缺少同等方便的普通工作材料：实验脚本、观察值、被推翻的解释、
已知适用范围、尚未回答的问题。trace 可供外部审计，不等于 agent 能直接复用的研究工作台。

H→C 当前也有有意的信息收缩：C 获得批准 H、源码和接口，不直接获得完整 H 调查过程或历史。
因此应研究如何交接 H 自选且公开安全的观察与实验计划，不能悄悄把全部历史塞入 C。

所有允许向该阶段暴露的完整原始证据必须继续可访问；新笔记只能是 tainted 解释和索引，
不能替代、删除或裁定原记录，private 证据继续隔离。
“不能静默压缩证据”不应被解释为“只能无限追加同一份长问题说明”。

R26 trace 的 provider-reported input tokens 累计为 21,474,977，H 每轮中位数 196,667；
这是重复请求的 usage，不是独立 tokenizer 或账单审计，不能单凭它归因算法失败。
首 H 的 research state 约 826,553 字符，其中 history_index 为 817,300 字符，
并非只有轻量记录目录；精确计数方法和 trace 见 R26 审计。
[corpus builder](../../../scion/proposal/hypothesis_research_corpus.py) 已将正文历史改成索引，
但索引又全文复制 H text、target_weakness、expected_effect 和 outcome facts；每轮 H
重新发送完整索引，展开后的 record 还含这些正文。因此没有显式 read 旧记录不代表没有看到旧知识。
下一版可评估完整有序轻量目录、按需完整正文与普通可逆 factoring，保留全语料搜索，
不删除旧记录、不用 top-k、不以模型摘要替代原文。这应是明确的可见性设计变更。

### 4.4 正式 funnel 回答完整候选比较，不自动回答增量因果问题

R25/R26 每个 cumulative head 对固定 R22 C3 比较，不是对自己的上一 head。
因此正式收益混合了继承改动、新改动及其相互作用，不能直接归因给最近一项机制。
真实小实例收益、helper 少调用、更多 ALNS iterations，也都不能单独推出最终 timed quality 优势。

研究需要区分候选与 parent、候选与初始 baseline、机制开/关、相同 eligible frontier、
相同输入下成本变化等问题。正式 held-out funnel 不应承担所有探索职责。
公开开发实验可以服务诊断；正式 Protocol 继续服务独立科学裁决。

普通路径的执行顺序与 wall-clock 噪声也是待研究变量。不能说已经解释了所有信号，
也不能在噪声/功效尚不明确时只靠追加 seeds。新测量设计需事先声明，历史 Decisions 保持不变。

### 4.5 外层完成单位与研究问题完成单位不同

[campaign loop](../../../scion/core/campaign_loop.py) 以 requested evaluated stages 为结束条件。
12 stages 可以全部有效完成，但同一个研究问题仍没有被解释。
这不是 loop 的 correctness bug，而是当前运行单位的选择。

全局 cap 剩余、candidate 数量、通过多少 tests，均不等于研究效率。
研究效率应看减少了什么不确定性、避免了什么重复错误，以及这些认识是否能支持更好的完整算法。
不能再用“跑完另一轮”替代这三个问题。

## 5. 建议的 v0.5 核心机制

**把持续的算法研究问题作为 Creative Layer 的工作单元，把 H/C 保留为不可变的正式提交边界。**
先做小而完整的一条链，不建立大型多 agent 平台，不增加研究风格评分系统。

```text
当前完整源码 + 公开问题数据 + 普通研究材料
    ↓
研究 agent：提出竞争解释 → 选择公开实验 → 观察 → 修正认识
    ├─ 负结果、零结果、不确定结果 → 留存并继续调查
    └─ 形成一个 H → H Contract
          ↓
       C 在批准 H 内实现、观察和测试 → 一个 C
          ↓
       原有 Patch Contract → Verification → Protocol → Decision
          ↓
       允许暴露的结果与 verified source → 后续 fresh attempt
```

### 第一项能力：公开开发观察

增加与 `test_patch` 分离的 observation 动作。H 可以针对未修改的当前源码调查，
C 可以针对当前未导出 draft 做测量。agent 提交实验脚本与公开输入，host 检查权限、
资源和数据边界；执行复用 development safety preflight、editable/frozen、import/API
与接口/隔离所需约束。host 不选择算法或判定想法好坏，未导出草稿也不能无条件执行。

problem package 提供可公开执行的输入/生成器、求解入口、objective/feasibility
参考能力；generic core 负责隔离执行与普通结果传递，不理解 route、capacity 或 operator 含义。
工具应返回实际执行状态、数值/表格/有限文本和结果位置，使 agent 能看到数据而非只看到 pass/fail。
完整公开输出可存普通文件、按需读取，不能静默以摘要替代。

资源上限必须显式计数；sandbox 只挂载公开源码、公开开发数据与 scratch，
不挂载 held-out、控制状态或 credentials。输出可能被 tainted 脚本伪造，
只能供研究，不能进入正式 Decision。可行性和 objective 正确性由原 Verification 与
problem checks 保障，正式比较结论由 Protocol 给出。

**该能力不能清除已 failed 的 exact-patch falsifier 状态。**
不允许把既有反例事后改称 observation 来获得 ready；当前规则继续生效。
新能力让未知量可以一开始就作为测量问题，而不必先伪装成正确性断言。

### 第二项能力：普通研究材料的跨 attempt 延续

保存 agent 自写的问题、竞争解释、脚本、公开输入、实际结果引用、结论适用范围和待办调查。
这些都只是普通文件，保留原记录，不引入 claim identity、登记、签名、receipt 或新状态权威。
agent 可以检索和修订自己的认识；host 不要求必须引用几条历史、提供正收益 witness，
也不以笔记完整性决定候选资格。

一次提交的 H/C 仍不可修补或重导出。若 C 发现需要改变 H 的研究方向，结束该 attempt，
后续 fresh H 可读取已完成的安全研究材料。这是研究内容延续，不是 terminal session resume。
H→C 的安全研究交接要显式定义；第一版不开放任意完整历史，更不开放 private 结果。

### 第三项能力：围绕解释而非固定测试模板选择实验

可用实验包括 baseline profiling、独立小实例参考、公开实例族、matched parent comparison、
机制消融、scope/cutoff 对照、质量—计算量或质量—时间曲线。
这些是 agent 可以选择的工具用途，不是每次必须全部完成的流程。

parent/消融对照必须使用实际保存的完整普通源码副本。当前旧 head 会被清理，
因此按研究需要保留 parent 是后续设计依赖，不是现有能力保证；不得从历史 patch
重建 executable candidate，也不由 host 自动合并 sibling 算法。

例如，对于“缓存释放成本后能增加有效搜索”的假说，agent 应能自行区分：
真实重复查询是否存在、缓存是否等价、总调用成本是否下降、节省的工作是否用于有效搜索、
最终比较优势是否出现。若其中一条不成立，它可以修正或放弃解释；
框架不强迫它为每个步骤补一个能通过的断言。

公开研究可以产生有信息量的负结果；正式 solver-improvement 目标仍必须由独立收益证据完成。

## 6. 哪些边界保留，哪些实现选择值得改变

|项目|下一阶段立场|
|---|---|
|Problem-neutral core、problem-owned 算法与语义|保留|
|Tainted H/C、Contract、Verification、Protocol、held-out、deterministic Decision|保留|
|每 attempt 一个导出 H，批准后一个与其绑定的 C|最小方案保留|
|完整 verified branch tree、精确 held-out candidate reuse|保留|
|Failed falsifier exact-value 规则|保留；新观察不得绕过|
|H 只读、C 只能通过 test_patch 执行研究|作为 v0.5 能力边界扩展来设计|
|C 只能看到批准 H 而无法接收安全调查材料|设计明确的最小交接，不直接全量放开|
|12 formal stages 与局部 turns 作为实际研究节奏|作为实验设计变量评估，不宣称资源剩余就一定充分|
|依赖每轮外部审计更新长问题说明和 optional examples|停止作为默认进展路径，检验 agent 自主调查能否承担|
|Host novelty、机制推荐排名、研究质量 gate|不增加|

新动作超出现有 addendum 对有限 Creative actions 的描述。
在实现前需要更新相应架构解释与信息流定义，不能伪装成兼容性修复。
旧 APS 文档中的 compaction/resume、host priority、identity 等已废弃机制不随之恢复。
本报告没有修改 V3/addendum，也没有将提案写成已接受实现。

## 7. 如何检验新机制，而非继续盲目试下一份算法

先预注册框架假说，再安排实验。至少分三个层次：

|层次|要证伪的判断|可信的评价方式|
|---|---|---|
|边界和能力|新增工具可安全提供研究观察，负结果能被保留|公开/私有隔离、来源与资源计数、反例不得被洗白、研究输出不进入 Decision 的针对性测试；共享边界变更后做跨问题控制|
|研究过程|agent 能更准确诊断、更新解释并复用已有调查|对同一公开源码任务，以固定模型和资源，比较现有 v0.4 与新增能力；独立核验诊断事实、错误归因、重复调查、外部干预|
|算法效果|研究过程改善提高独立完整 solver 优势|多个独立 campaigns，预先固定 baseline/分布/预算/成功标准，使用未暴露的确认数据，报告全部结果与不确定性|

评价单位不能只是一条漂亮 trace 或一个最好的 candidate。
正式 campaign 是研究策略的重复单位；算法测量仍按 problem Protocol 的 case/seed 单位处理。
每个 campaign 的最终提交/确认规则与确认集使用次数应事先固定；不能根据确认结果
重新选候选、补采，或决定只报告某个 campaign。
比较两种框架时，需要同时记录 provider 输入/输出、wall time、公开研究 solver 资源和正式 solver 资源。
相同 call cap 不代表相同 token 或计算成本，额外公开实验也不能成为不计费的优势。

第一轮机制对照宜只增加 observation，保持模型、起始源码、公开材料和正式 gates 可比；
后续再检验研究材料延续的增益。若一次加入工具、笔记、多 agent、更强模型和更大预算，
即使变好也无法知道是哪一项有效。

研究诊断的盲审与反例任务是框架研发评测，不进入生产候选的 Contract 或 promotion gate。
若诊断变好而算法收益仍无改善，应保留该结果，转查问题分布、基线强度、可研究空间与模型能力；
不能追加示例后把同一机制重跑到成功。

## 8. v0.4 里程碑与进入 v0.5 的条件

### 8.1 先保留原来的成功定义

`c82b77ef` 中的 TASK 明确要求 Warehouse 与 CVRP 都取得 retained improvement，
才算 v0.4 完整完成。这比更早的
[v0.4 design](../../../design/v0.4/v0.4-design.md) 中侧重 adapter、证据完整性、
运行约束和组件拆分的 exit criteria 更强。较早设计属于历史，不能用来覆盖后来的承诺；
其已废弃的静态 gate 等实现也不能恢复。

按原完整成功验收，当前答案是 **v0.4 尚不能宣布成功完成**：Warehouse 已接受，
CVRP 有真实算法工作和 development promotion，却没有所要求的独立保留收益。
负结果、测试进步、更多调用或新的版本号都不能代替这项证据。

下面是用户于 11 月 15 日明确采纳的**有未完成科学目标的阶段收官规则**。
这是显式的项目阶段调整，不是对原成功标准的追溯改写。按此规则记录阶段 closed；
不能把原科学验收改成全部 complete。

### 8.2 已采纳的 v0.4 阶段里程碑

**交付一个跨问题、能够承载真实算法改动和持续分支研究、并诚实裁决科学结果的研究基座；
用实际证据明确它的收益、局限与下一阶段需要检验的机制。**

这比“流程能跑通”更强，但不声称已经普遍具备自主研究能力。
五项条件必须一起成立；下表是项目阶段判断，不添加任何运行时 candidate gate。

|条件|可检查的完成标准|当前判断与证据|
|---|---|---|
|M1 通用且可信的研究基座|Warehouse/CVRP 都经问题自有语义接入同一主链；正确性、科学比较、晋升职责独立；没有已知会推翻本次关键结论的未处置边界错误|已在现有测试和实际运行范围内得到支持。见 onboarding、P16 共享回归、跨问题控制与 R24–R26 审计；不等于证明所有代码无缺陷|
|M2 真实算法研究和连续性|agent 实际完成有机制含义的算法修改，能从 verified 完整源码继续下一 attempt；不能只以合法 JSON、一次 smoke 或宿主手写改进作证|已有证据。R24–R26 的算法、source continuation 与真实 probe；constructor 工程修复继续单独标注，不算 Scion 自主发现|
|M3 科学结果已得到明确判定|至少已有一类问题的独立正面成效，同时第二类问题经历完整、有效的检验；正面、负面、不确定、未完成和基础设施失败分别归类，不要求都变成正结果|Warehouse retained 已接受；CVRP 的 R3i→R4 和后续固定/自主比较已能区分晋升与独立收益，R26 有效完成。CVRP 原科学成功目标仍未满足|
|M4 可用的比较基线和证据交接|当前 runtime、完整起始算法、科学输入和资源可定位，结论能追到实际记录；无法复原的历史内容和测量限制明确列出|`c82b77ef` 加文档改动可定位；完整 C3、R26 inputs/status/metrics/trace 与审计已链接。部分 superseded full trees 缺失，不能宣称逐候选完全复现；足以保留明确的后续对照起点|
|M5 下一阶段有不同且可证伪的框架问题|列明本版限制、继续保留的边界、跨版本未完成科学任务，以及一个能区别新旧机制的评价方向|本报告已给出：检验公开开发观察是否改善诊断与解释修正；原 CVRP 目标继续由 TASK 跟踪。主线已接受；v0.5 接口与验收初稿已形成，具体契约待评审，资源和采样参数须在启动前冻结|

据现有证据，五项条件已有足够材料支持**阶段收官**，用户已明确认可这一判断；
不需要为了制造一个正结果而再跑 R27。
这不是证明现有机制已到性能上限，也不是证明下一版一定更好；它足以说明继续同一种
support-patch 循环不应是唯一默认工作。

若发现使关键结论失效的 source/held-out/feasibility/Protocol 问题，必须先处理该具体问题；
不能把它包装成一般遗留债务。反之，operator-shaped schema、全部历史源码补存、
完整噪声校准或消除所有重复上下文，不应变成没有尽头的 v0.4 关闭前清单。
这些限制各自约束相关声明，后续工作按新研究需要处理。

### 8.3 已记录的阶段状态

依据用户最新授权，当前明确记录为：

> v0.4 机制阶段收官，原科学成功验收部分达成。
> Warehouse 独立保留收益已接受；CVRP 独立保留收益未确认，继续跨版本跟踪。
> 已接受持续算法问题驱动的研究主线；v0.5 进入机制设计。

这里关闭的是本阶段的默认研发范围，不能写成“双问题 retained 已完成”或“自主研究能力已证明”。
原 CVRP 未完成项继续保留 objective、对照基线、成功标准和证据链接；
不能通过将原始 B0 改名为本地 C3/B0-fixed 来消除差额。

也不要求先实现 v0.5 才能关闭 v0.4。进入设计、具备可执行实现、完成机制对照、
取得独立算法收益，是不同状态。当前为阶段已关闭、主线已接受、v0.5 详细设计初稿已形成；
不声称新能力已实现或有效。
Git 提交或 tag 可以定位版本，但不是科学成功证据。阶段评审之后，用户已明确要求
提交、创建 `v0.4` tag、合入主分支并 push，正式进入 v0.5；其发布状态由
[current-state](../../status/current-state.md) 记录，不改变本报告的科学判断。

### 8.4 v0.5 应如何承接

下一阶段的实质里程碑应是：**agent 在一个持续问题上自主取得观察，发现反例，修正解释，
跨 attempt 复用实际研究材料，并据此产出通过原有边界评价的候选。**
它的机制效果还须在可比资源下与现有 v0.4 对照，不能只验收“新增了两个工具”。

新 [机制设计](../../../design/v0.5/v0.5-continuous-algorithm-research-design.md) 与
[验收设计](../../../design/v0.5/v0.5-research-mechanism-acceptance.md) 已展开以下顺序：

1. 明确公开观察的输入、输出、隔离、资源、H/C 交接和失败语义，评审架构差异。
2. 实现最小 observation 能力，保持现有安全/科学边界；另行加入普通研究材料延续。
3. 对照检验诊断、解释修正、重复错误和外部干预是否改善；这类评价不成为候选 gate。
4. 再用重复完整 campaigns 和事先固定的独立确认检验算法收益；CVRP 未完成目标不消失。

不以多 agent 数量、补丁大小、新颖程度或工具调用量作为版本目标。
研究效率改善与独立 solver 收益仍分别报告，避免把 v0.4 的“必须等到正结果”
换成 v0.5 的“做完工具就宣布有效”。

## 9. 本次核验与交接

主 profile：Design Discussion。完整阅读入口四文档、V3 与 addendum，
读取相关算法空间/APS 历史设计时只作背景，不恢复其旧机制。
额外读取 runbook、R24/R25 postrun、R26 preregistration 和对应当前源码。
独立 R26 审计限定在 current-state 明确链接的根及其精确引用产物，范围见该报告。

11 月 14 日 live Git 检查：入口 clean `c82b77ef`，与本地 `origin/v0.4-dev` 一致；
所有列出的 experiment panes 已 dead，R26 科学终态由 JSON/metrics 确认。
本次文档更新不更改 launch provenance，不复写历史证据。
验证仅包括只读证据/源码核对、文档链接与 diff 检查；没有新的运行测试或科学效果声明。
TASK 保留当前工作顺序，本报告仅作为该任务的分析依据，不构成第二个 work queue。

11 月 15 日复核：HEAD 仍为 `c82b77ef`，工作树有前述八份文档改动，全部保留；
所有列出的 experiment panes 仍 dead。补读历史 v0.4 design 以核对里程碑来源，
根据随后用户的明确认可记录阶段收官，并补充 v0.5 机制与验收初稿；
不重跑算法/测试、不改运行边界，不把阶段关闭写成全部科学目标成功。
