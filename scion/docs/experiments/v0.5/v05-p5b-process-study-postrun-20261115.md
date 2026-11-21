# P5b 固定矩阵：过程证据与结果

*2026-11-15 · 八个固定槽位已处置；单评审完成，独立第二评审待补；本批未满足 E2*

**执行完成不等于能力验收通过。** 七项完成预定 formal 目标，warehouse-02 因调用
上限未完成；全部失败和无收益结果保留。298 次 provider 调用均成功、attempt 0，
没有重试、追加槽位或预算转移。11 个正式阶段产生 214 行有效 pair，无求解失败；
这些行包含扩样重叠，不能视作 214 个独立样本。八项 champion 均保持 v1。
最后终态为 06:08:04 UTC。**observe 为 0，跨 attempt/导入材料的实际读取为 0**；
因此没有满足本阶段要求的 O/M 见证，不能因正式流水线完成而勾选 E2。

本批按[启动前冻结记录](v05-p5b-process-study-preregistration-20261115.md)执行。
原始根为 `/home/clawd/research/scion-experiments/v05-p5b-process-study-20261115`；
`run-plan.json`、源码/输入副本和失败 trace 不随结果改写。运行期间没有修改框架、
提示词、算法、题目或预算，没有人工向研究 agent 提供解释、代码或下一步建议。

## 证据入口与报告口径

- `runs/<run_id>/status.json`、`campaign_summary.json`：原始终态与全部 attempt。
- `runs/<run_id>/llm_traces/`：实际 provider 请求、响应、工具反馈和 usage。
- `runs/<run_id>/public_research/`：公开材料、资源快照及完整 continuity。
- `runs/<run_id>/metrics/`：正式配对、时间策略、门槛与失败；不是公开材料入口。
- `review/inventory.json`：只读收集所得索引；不能代替原始证据。
- `review/assessment.json`：离线五维评审；独立第二评审尚未完成。

`observe` 的 subject/analysis 执行与原有 C `test_patch` 分开统计。源码阅读、
微型样本手算和测试通过各自有价值，但不能冒充新的自主观察闭环。
同 session 读取自己笔记、读取本次初始源码投影不算跨 attempt 复用。
正式筛选建议 expand/validate 不等于实际完成该阶段，更不等于 retained improvement。

成本按实际可知范围报告。原始 trace 的 normalized usage 不保证 provider 披露了
所有可选细项；未披露不能当零。最后 session 的研究资源快照可能不含 Decision 后
材料保留工作。metrics 的两侧 elapsed 合计不含 canary、Verification 或宿主开销；
不能将它冒称全部 formal wall。未记录的独立时长保留 null 和原因。
`storage_bytes` 是最终 campaign 普通文件总字节，包含 trace 和源码副本，不是公开材料
预算计数。`review/initial-execution-source-audit.json` 按启动前文件清单比较实际 v1
执行树，六个诊断分别 103/406 文件均相同。运行后冻结目录新增的是 Python/pytest
缓存；原文件只读不等于整个目录禁止创建缓存，不能宣称本批用了不可变文件系统。
实际正式数据路径以 metrics 的 `case_path_resolution` 为准：CVRP 来自冻结数据根，
Warehouse 优先解析各执行 workspace 的 data 副本。离线审计逐项比较后者与
`inputs/warehouse/formal-data` 的对应字节，而不是假定设置环境变量就改变了解析优先级。

## 已核对的过程发现

六个诊断槽位全部处置。
warehouse-02 在 48 次调用后 resource stop，没有正式候选/评估，两个 attempt 中
一个 H 局部轮次拒绝、一个 C 资源中止。该项是 incomplete，不能当作算法负收益。

|诊断|调用|正式有效 pair / 失败|screening 中位差 / CI|终态去向|
|---|---:|---:|---|---|
|cvrp-01|20|20 / 0|0 / [0,4]|expand_screening；按一轮目标停止|
|warehouse-01|39|12 / 0|750 / [-4150,3300]|queue_validate；按一轮目标停止|
|cvrp-02|36|20 / 0|0 / [0,4]|expand_screening；按一轮目标停止|
|warehouse-02|48|未执行|无分数|PROVIDER_CALL_CAP_EXHAUSTED；不完整|
|cvrp-03|24|20 / 0|0 / [0,2]|expand_screening；按一轮目标停止|
|warehouse-03|37|12 / 0|275 / [-1875,3825]|expand_screening；按一轮目标停止|

诊断共 204 次调用；五个候选通过 Contract/Verification/canary 并进入 screening，
没有 validation、frozen 或 promotion。六项均无 `observe`，公开 subject/analysis/checker
计数均为 0；legacy `test_patch` 分别为 1/2/2/0/1/1 次。两项 03 未读取导入材料，
本次输入和自己新写笔记的读取不能替代跨 campaign 读取。

03 导入材料中的源码仅供研究阅读，不替换其默认执行起点；实际 argv/导入条目数见
`review/cvrp-03-launch.json` 与 `review/warehouse-03-launch.json`。
cvrp-01 的 40 个条目含 39 份源码投影及一个公开输入，无笔记或 observation；
warehouse-01 的 51 条包含两条 C 笔记；没有人为补写材料。

1. CVRP 第一题提出 SWAP*，第二题提出精确 2-opt delta/prefix 评估。两者都有
   源码依据、可证伪预测和自写测试，但都没有 pre-H `observe`。两题一轮 screening
   的中位差都是 0，CI [0,4]、20 个有效 pair、无失败；Decision 为 expand_screening，
   按本题一轮上限结束，没有实际扩样。
2. Warehouse 第一题提出带车辆重选型的有界 beam repacking。12 个有效 pair、
   无失败，screening 中位差 750、CI [-4150,3300]，进入 queue_validate 后按一轮
   上限结束。该 screening 规则不要求 CI 下界为正，不能把 pass 写成确证收益。
3. Warehouse 第一题自写测试曾失败。`045318428537` trace 的 line 93 期待总成本
   2000，但测试同时要求不改动的 Z 车辆使用 HQ40，其自身成本已是 3300。
   后续笔记承认草稿被拒绝，再修改算法和测试；没有明确解释此参考值错误。
   因此失败→修改→通过不能单独支持 explanation revision。
4. CVRP 第二题 `050239952159` trace 的失败 line 177 要求零收益整路线反转必须
   调用完整重算；候选允许安全排除不改善动作，给定规模下零差值远离 -EPS 阈值。
   后续版本有实际代码变动，第二测试通过，但笔记没有明确诊断原断言问题。
   原失败和新测试分别保留，不能说原数值反例已经被解决。
5. CVRP 第二题在失败后搜索研究材料中的 `def test`、`177`。旧 `test_patch` 的
   脚本及结果存在原始 trace，但不会自动成为新研究材料条目；目前仅 agent 自写
   笔记进入该 corpus。这是后续需要审视的材料连续性接口问题，尚非因果结论。
6. open-cvrp 首次 C 的 `053402571554` 原始 note 明确说 probe line 137 的诊断不能
   确定原因，原 probe source 不在可见研究索引。它另提出 prefix cancellation 和
   EPS 附近保守重算的源码风险，未冒称已经解释原失败。原 line 137 将完整 solver
   的 `_route_distance` 调用数与局部 2-opt delta 调用数比较，缺少同范围计数；
   这不能直接定位 2-opt 计算错误。完整程序实验的归因和实验材料延续必须一起审视。
   对应代码是 [C session](../../../scion/proposal/code_research_session.py) 的
   `_provider_context` 与 `_run_test_patch`：下一轮带回 latest draft 和 bounded results，
   没有前次 falsifier source；[公开材料 session](../../../scion/observation/session.py)
   的材料动作也没有自动接收这个旧测试入口的脚本。原始 trace 对 operator 可见，
   不能据此认定研究 agent 在下一轮也能读取。

## 开放 CVRP（已终态）

62 次 provider 调用，两个 H/C 候选，三个正式 screening 阶段，champion v1 不变；
没有 validation、frozen 或 promotion。expanded screening 复用已验证候选，不重复
Contract/Verification；原 summary 的 screened 计数为阶段数，不能冒称三个新候选。

|阶段|候选|有效 pair / 失败|中位差 / CI|Decision|
|---|---|---:|---|---|
|1|2-opt edge delta|20 / 0|0 / [0,213]|expand_screening|
|2|同一候选扩样|48 / 0|0 / [0,106.5]|continue_explore，case-quality fail|
|3|route-distinct regret|20 / 0|0 / [-10,0]|continue_explore，screening fail|

初筛与扩样有重叠，88 行是执行工作量，不是 88 个独立观察。第二个 H 实际读取
history-0002，指出扩样六个 case 中五个全种子持平、一个全种子获胜，证据不足以
支持广泛收益或精确机制归因，随后改为研究 regret 的路线选择。这支持既有正式
反馈路径中的范围修正和下一步研究，不应抹去这项正面能力。

第二次 H 是另一条 fresh branch，初始源为默认冠军；第一 branch 的 verified head
仍保留。agent 核对当前源码，明确发现旧 edge-delta 修改不在当前树中，拒绝只凭
历史 patch_present 假定存在。后续 C 与测试绑定的是当前树。

但全程 `observe=0`。两次 read_research 仅为当前公开输入和当前 C 自写笔记；
第二 H 能看见前一 attempt 的 note 索引却没有读取。因此正式 history 与源码的
正确使用不是新增公开材料 M 的实际复用见证。

## 开放 Warehouse（已终态）

32 次调用，一个 H/C 候选，依次完成 screening、validation、frozen。候选替换
DestroyRebuild 的重装逻辑为有界 beam search，包含车辆重选型、约束检查和完整
字典序改进检查；自写测试通过。不能因为它与其他槽位提出相近思路，就把不同源码
实现合并成一次独立重复。

|阶段|有效 pair / 失败|Protocol 中位差 / CI|Decision|
|---|---:|---|---|
|screening|12 / 0|3525 / [-5075,9400]|queue_validate|
|validation|18 / 0|5250 / [950,10200]|queue_frozen|
|frozen|12 / 0|1050 / [-12200,9700]|abandon，FROZEN_FAIL_UNCLEAR|

canary 通过，frozen 的不确定性未通过原门槛；没有 promotion 或独立 retained 收益。
后两个正式阶段不再开启 H/C，不把宿主 Decision 当作 agent 的解释。该运行没有
`observe`，写过一条实现计划 note，但没有后续 H，未形成跨 attempt 复用机会。

abandon 后候选 workspace 已清理，完整 accepted head 和 previous head 仍分别保留
在 `public_research/retained_sources/retained-000002/tree` 与 `retained-000003/tree`。
两棵各有 406 个原始普通文件（缓存另计）；previous head 与默认树一致，accepted
head 与之仅有 `operators/destroy_rebuild.py`、`registry.yaml` 两个声明变更。
这是实际触发的源码保留/清理证据，**不是 agent 实际复用材料的证据**。
详见 `review/abandoned-head-retention-audit.json`；完整 private tree 没有作为公开材料导入。

## 成本与离线核验

|槽位|physical calls|input tokens|output tokens|
|---|---:|---:|---:|
|cvrp-01|20|459416|6923|
|warehouse-01|39|856691|16231|
|cvrp-02|36|1191892|17350|
|warehouse-02|48|701391|3730|
|cvrp-03|24|693701|6948|
|warehouse-03|37|946172|7950|
|open-cvrp|62|2184313|22598|
|open-warehouse|32|551091|9654|
|合计|298 / 672 上限|7584667|91384|

输入已包含 cache-read tokens，output 的 reasoning 细项不能另加成额外输出。
normalized reasoning/cache-read 合计分别 23956/87808，但旧 transport 将缺失的
可选细项也置零，不能确认逐次完整披露，严格评审表保留 null+原因。价格、后端模型
快照及精确货币成本仍未知。214 pair 两侧已记录 elapsed 合计 1377.353 秒，只是
正式成本的部分范围；完整 test/formal/invocation wall 未记录，不能以 trace 窗口代替。
最终 campaign 普通文件合计 261038725 bytes；这不等于公开材料预算用量。

`review/configuration-audit.json` 核对八项终态、请求模型/attempt、实际调用数与
各 cap、所有 metric/pair 的 1/5 秒策略、原始清单内初始源码。118 个已解析 case-side
数据位置均与冻结正式数据一致；其中 16 个通过清理前保留的完整树核对，不做补丁重建。
源码新增项只有缓存。实际运行没有新的源码/配置修改或科学干预。
`review/capability-exposure-audit.json` 还核对了全部 298 个实际请求上下文：O/M 标志
均为 true（200 H、98 C），没有把误关闭功能造成的零使用误报为自主行为。

`review/assessment.json` 的八行均有一份非盲单评审，60 处原始字节引用通过
`p5_assessment.py review` 校验，结果在 `review/coverage.json`；八行均待独立第二评审。
引用存在并不证明语义正确。本轮未改生产代码，不冒称重跑 P4 全套回归；既有 P5a
74 项工程结果保持原证据范围，本轮新增验证是实际矩阵及离线引用/配置/数据核验。
本轮八份相关 Markdown 的 90 个本地链接及 `git diff --check` 均通过；八个 tmux
pane 均已终止，七项 exit 0、warehouse-02 exit 21，与 JSON 终态一致。

## 阶段判断与下一步机制设计

本批没有证明新增 O/M 的研究闭环。234/298 次调用用于 read/search_source；11 次
legacy test_patch 中保留了 3 次失败，另有 6 次 write_research、10 次 read_research，
后者都是当前输入、当前源码投影或自己本 session 的笔记。三个有实际历史材料可读
机会的槽位（两个 03、open-cvrp 后续 H）均未读其内容；open-warehouse 没有后续 H。
六个诊断对题意的回答也不齐：02 两题正确计算合成模型总成本，cvrp-03 指出容量
限制；部分 01/warehouse-03 没有明确核验题给的数值/失效条件，不能用相关算法测试
替代这份参考答案核验。这是“证据不足”，不是判定模型算错或普遍不会研究。

单评审认为 open-cvrp 有一条通过**既有正式历史**完成调查、范围解释、修正和下一
行动的见证；它没有变成新 O 见证。P4 的实际完整源码保留也有效，但 M 可读能力
没有转化为实际条件化复用。两问题的 Contract/Verification/Protocol/Decision 路径
都实际执行，保留了失败和不确定性；新观察 runner/checker 的真实 provider 使用
没有发生，其工程 smoke 不能在这里升级为 E2。D07 双评审和 D09 实际复用未满足，
D10 两个开放运行已完成，D12 完整矩阵报告给出未满足结论。E3/E4 没有执行。

**核心判断：当前会话的重心仍是生成并验证 H/C；增加可选工具和材料索引，尚不足以
让持续算法问题成为实际研究工作的中心。** 这是一批固定任务中的行为证据，不是
O/M 无效的因果估计，也不意味着靠强制工具调用次数就能解决。下一步先设计清楚：

1. **实验材料必须可继续调查。** 自写测试、输入、预期、结果和对应草稿应能作为
   普通研究材料被本人下一轮核对，并在适当边界内延续。当前“脚本在 operator trace、
   agent 只见失败行号”的断点已被实际触发；不能只加一句提示要求更认真分析。
2. **区分算法反例与错误测试。** 错误的 2000 成本、要求安全可拒绝动作必须重算、
   不同作用域的调用数比较，分别说明参考、断言和归因都可能错。需设计有证据的
   复核/修正路径，不能把改代码后 PASS 自动算作解释修正，也不绕过正式检查。
3. **持续问题需要可用的工作状态和停止语义。** 正式轮数目标驱动下，静态源码
   调查很快转为 H/C；应审视如何允许围绕同一问题累积预测、反例、未决问题和
   有依据的无候选结论，再由 agent 决定是否提交。材料应保留实际 source/input
   条件与缺失项，而非要求 host 选择机制、强制读固定笔记或设置“新颖性”门槛。

先完成独立复核和上述接口/研究会话设计，再另立前瞻验证；不自动加预算重跑本矩阵，
也不直接扩为 P6 大规模效果实验。评分仍只在 operator 侧，未进入 Safe Features、
Contract、Protocol 或 Decision；V3 的问题无关 core、正式数据隔离和确定性科学边界
不变。本轮不增加 V3 权威扩展。v0.4 收官不重开，CVRP 原科学目标继续开放。
