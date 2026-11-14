# Scion v0.3 名词对照表（Reading Aid）

*Date: 2026-04-19*  
*Purpose: 帮助阅读 `scion-v0.3-design.md`、review report、detail plan 时快速对照缩写与术语。*  
*Style: 不追求严格规范定义，优先追求“看文档时一眼能懂”。*

---

## 0. 怎么用这份文档

如果你在主文档里看到：

- `W2 / W15 / W16` 这种编号，去看 **第 1 节**
- `Sprint N0 / O1 / Q1`，去看 **第 2 节**
- `ProblemAdapter / stale / revision / family_id`，去看 **第 3-6 节**
- `screening / validation / frozen`，去看 **第 7 节**
- `full-system validation / mechanism study`，去看 **第 8 节**

---

## 1. Work Item 对照表（W1 / W2 / W15 这些到底是什么）

这些 `Wxx` 就是 **v0.3 的工作项编号**。可以把它理解成“一个个独立专题”。

| 编号 | 简称 | 一句话意思 |
|---|---|---|
| **W15** | PROBLEM-ADAPTER | 把 Scion core 和 `warehouse_delivery` 问题实现解耦，建立统一问题适配边界 |
| **W1** | SCORING-DECOUPLE | 把 protocol 的胜负判定，和 weight-opt 的优化打分拆开 |
| **W4** | MILP-INTEGRATION | 把 MILP 精确解 / bound 接进报告体系，作为 gap 基准 |
| **W2** | ASYNC-WEIGHT-OPT | 让后台权重优化变成安全、可追踪、不会污染 champion 的机制 |
| **W3** | EARLY-STOP | 平台期检测与自动早停 |
| **W6** | FAMILY-PERSIST | 把 hypothesis 的 family 信息正式落库 |
| **W7** | CLASSIFIER-WIRE | 把 hypothesis 分类器真正接进主流程 |
| **W5** | MEMORY-VIEWS-FROM-LINEAGE | 不单独存 SearchMemory，而是从 lineage 事实重建各种 memory 视图 |
| **W8** | FAILURE-SUMMARY-V2 | 失败模式聚合与上下文注入 |
| **W9** | CAMPAIGN-JOURNAL | 给 LLM 更丰富的跨轮/跨分支历史上下文 |
| **W10** | WEIGHT-OPT-FEEDBACK | 把权重优化得到的粗粒度信号反馈给 Round 1 |
| **W11** | SOLUTION-CONSISTENCY-DIAGNOSIS | 把原先的 V5 问题重构为更清晰的 solution consistency 诊断 |
| **W12** | CANARY-UPGRADE | 强化 canary 集合，让危险回归更早暴露 |
| **W13** | TOKEN-USAGE-PERSIST | token 使用量持久化 |
| **W14** | TECH-DEBT-CLEANUP | 技术债清理 |
| **W16** | VALIDATION-MATRIX | 18 个 campaign 的 full-system validation 实验矩阵 |
| **W17** | MECHANISM-STUDY | 小规模机制研究，用来回答 W16 回答不了的问题 |

### 1.1 最常出现的几个 W 项，重点理解版

#### W15 = 问题适配边界
不是“改几个名字”，而是：

> 以后 Scion core 不应该知道 warehouse 特有字段名、目标名、oracle 细节。  
> 这些东西应该通过 `ProblemAdapter` 统一接入。

#### W2 = 后台权重优化并发语义
不是“开个线程跑 weight opt”这么简单，而是：

> champion 在主流程里继续进化时，后台权重优化不能把它写坏。  
> 所以需要 version / revision / immutable snapshot / stale 恢复语义。

#### W16 = 完整系统验证
意思是：

> 用一组固定矩阵，验证“完整 Scion 系统”在不同模型、不同问题 variant 下的表现。

#### W17 = 机制补充研究
意思是：

> 如果你想问“结构搜索单独有多大作用”“参数搜索单独有多大作用”，W16 不够，要另外做小规模补实验。

---

## 2. Sprint 对照表

`sprint` 可以理解为“开发阶段”。

| Sprint | 一句话意思 |
|---|---|
| **N0** | 先打地基，冻结 ProblemAdapter / comparator / strict config |
| **N1** | 接 objective / scoring / MILP 这层 |
| **Mini-Validation A** | 小规模冒烟，确认 N1 没把系统打坏 |
| **N2** | 处理 async weight-opt 和 early-stop |
| **O0** | 先把 family persistence 和 classifier 契约打稳 |
| **O1** | 再接 classifier / failure summary / memory views |
| **Mini-Validation B** | 再做一次 classifier / async / early-stop 的冒烟 |
| **P** | context、feedback、诊断、canary 这一层 |
| **Q0** | token usage 和 tech debt 清理 |
| **Q1** | 最终 validation matrix + mechanism study |

### 2.1 为什么不是直接 N → O → P → Q？

因为原来粒度太粗了。  
拆成 N0/N1/N2、O0/O1 的好处是：

- 能先冻结最危险的边界
- 能中途插 mini-validation
- 出问题时更容易定位是哪个阶段引入的

---

## 3. ProblemAdapter 相关名词

### ProblemAdapter
一句话：

> 问题特有逻辑和 Scion core 之间的“适配层”。

它负责的通常是：

- 读 instance
- 把 solver 输出变成统一格式
- feasibility 检查
- objective 重算
- solution consistency 检查
- 渲染 problem summary 给 LLM

### ProblemSpec
一句话：

> 某个问题的结构化配置说明。

通常在 `problem.yaml` 里，写的是静态信息，比如：

- objective 列表
- operator categories
- llm hints
- family taxonomy
- search space / solver config

### strict ProblemSpec
意思是：

> YAML 里不认识的字段，直接报错，不允许静默忽略。

目的是防止“你以为新字段生效了，其实没用”。

### `toy_tsp` MWE
MWE = Minimal Working Example，最小可工作例子。  
这里的作用不是为了研究 TSP，而是证明：

> Scion 的 generic pipeline 真能接第二个问题，W15 不是假解耦。

---

## 4. Champion / version / revision / stale 是什么

这几个词在 W2 里最容易让人读着头疼，其实可以这么理解。

### champion
一句话：

> 当前系统认可的“最佳池配置”。

注意不是“最佳单个算子”，而是整个 operator pool 的当前版本。

### version
一句话：

> 结构版本号。

当发生“结构性提升”时，比如：

- 新增一个有效算子
- 修改一个算子实现后 promote

这一般会让 champion 的 **version** 增加。

### revision
一句话：

> 同一结构版本下的权重修订号。

当只有权重优化改了，而算子结构没变，就不该升 version，而是升 revision。

例子：

- `v3_r0` = 第 3 个结构版本，初始权重
- `v3_r1` = 结构没变，但做过一次权重更新

### stale
一句话：

> 某个 branch 手里的基线已经过期了，不能再拿它直接和当前 champion 比。

最常见原因：

- champion 已被 promote
- champion 权重已更新

### stage-aware stale
意思是：

> branch 过期之后，不是无脑从头开始，而是根据它当时做到哪一步，决定至少回退到哪一阶段重做。

这就是“按阶段恢复”的意思。

---

## 5. Classifier / family 这条线是什么

### hypothesis
一句话：

> LLM 在 Round 1 提出的“这次想尝试什么改动方向”的结构化提案。

### family_id
一句话：

> 这个 hypothesis 属于哪一类机制家族。

比如都属于“清空低效车辆”“合并同类订单”“repack vehicle”这种方向。

### classifier
一句话：

> 一个专门做 hypothesis 归类的小模型/组件。

它不是主 proposal 模型，而是专门判断：

> 这条 hypothesis 更像哪个 family？

### family_source
一句话：

> 这个 family_id 是怎么来的。

常见值：

- `classifier`：模型分的
- `keyword`：关键词规则分的
- `backfill`：后来补写回去的

### taxonomy_version
一句话：

> 这次分类使用的是哪一版分类体系。

目的：

> 后续 taxonomy 改版时，不至于把旧数据和新数据混在一起。

---

## 6. lineage / facts / views 是什么

### lineage
一句话：

> Scion 的事实账本。记录 hypothesis、promotion、failure、champion 演化这些真实发生过的事。

### facts
一句话：

> 原始事实记录，最接近“发生了什么”。

比如：

- 某 hypothesis 的 family_id
- 某次 failure 的 code
- 某次 promote 的时间和版本
- 某次 weight-opt 的结果

### views
一句话：

> 从 facts 计算出来的“阅读视图”或“总结视图”。

比如：

- SearchMemory
- FailureSummary
- CampaignJournal
- 各种 report table

### persist facts, rebuild views
一句话：

> 只把事实存下来，视图需要时再从事实重建。不要把每个视图也当独立真相去存。

这是为了避免：

- 一套 SQLite 事实
- 一套 SearchMemory
- 一套 ResearchLog
- 一套 FailureRouter summary

最后口径打架。

---

## 7. Screening / Validation / Frozen 是什么

这是 Scion 的三级实验协议。

### screening
一句话：

> 快速粗筛，看 candidate 有没有继续往下验证的资格。

特点：

- 快
- 可以多跑
- 暴露细节更多

### validation
一句话：

> 正式验证，看 candidate 是否真的相对 champion 稳定更好。

特点：

- 更严格
- 分支级别一次性
- 暴露控制更强

### frozen holdout
一句话：

> 最后确认，不让系统反复试探同一批数据。

特点：

- 信息暴露最少
- 用来抑制 overfitting / retry hunting

### canary
一句话：

> 专门用来暴露危险回归或已知脆弱点的小型“警戒实例集合”。

---

## 8. W16 / W17 里那些研究词是什么意思

### full-system validation
一句话：

> 验证完整 Scion 系统跑起来到底怎么样。

这类实验回答的是：

- 完整系统有效吗
- 不同模型下差异大吗
- synthetic 和 prod 的行为差异怎样

### mechanism study
一句话：

> 单独研究某个机制本身有没有作用。

例如：

- 只关 structure search 的贡献
- 只关 weight-opt 的贡献
- 只关 early-stop 开关的影响

### exact gap
一句话：

> 当前 heuristic 解，离 MILP 精确最优解还差多少。

### bound-only
一句话：

> 没求到精确最优，但有一个上界/下界信息，可以给出不完全确定的 gap 参考。

### impossible-better-than-optimum sanity check
一句话：

> 如果 heuristic 声称比 exact optimum 还好，那不是奇迹，而是系统 somewhere 出 bug 了。

---

## 9. 最容易混淆的几组词

### 9.1 Draft / Final / Review Report / Detail Plan

- **Draft**：原始设计草案
- **Review Report**：基于设计 + 代码审核后的问题与建议总结
- **Detail Plan**：把审核结论进一步收敛成更可执行的定稿/落地方案
- **Final design**：最后的主文档，真正指导开发

### 9.2 protocol scoring vs weight-opt scoring

- **protocol scoring**：决定 win/loss/tie，用于是否 promote
- **weight-opt scoring**：给参数优化器一个更细的优化信号

这两个绝对不能混为一谈。

### 9.3 hard saturation vs empirical plateau

- **hard saturation**：有比较可信的下界依据，接近“理论上很难再降”
- **empirical plateau**：只是观察上长期没改善，不代表理论到头了

### 9.4 version vs revision

- **version**：结构变了
- **revision**：结构没变，只是权重等参数变了

---

## 10. 最后给一个超短阅读地图

如果你在主文档里看到：

- **W15** → 想成“问题适配边界”
- **W2** → 想成“后台权重优化的并发安全设计”
- **W16** → 想成“完整系统验证”
- **W17** → 想成“补充机制研究”
- **family_id** → 想成“这条 hypothesis 属于哪类改动方向”
- **lineage** → 想成“事实账本”
- **views** → 想成“从事实账本里算出来的各种视图”
- **screening / validation / frozen** → 想成“粗筛 / 正式验证 / 最终确认”

---

*这份文档是阅读辅助，不是正式设计规范。正式口径仍以 `scion-v0.3-design.md` 为准。*
