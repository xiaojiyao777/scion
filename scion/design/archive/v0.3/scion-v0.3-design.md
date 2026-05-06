# Scion v0.3 设计文档（Finalization Framework）

*Date: 2026-04-19*  
*Author: BigBOSS + Cris*  
*Status: Final-level framework draft, ready for final wording pass*  
*Lineage: `scion-architecture-v3.md` + `scion-v0.3-draft.md` + `reviews/v0.3-design-review-report.md` + `reviews/v0.3-design-detail-plan.md`*

---

## 0. 文档定位

本文档不是 v0.3 Draft v2 的简单修订版，而是 **Scion v0.3 的 final 级别定稿框架**。

它的职责有三层：

1. **锁定 v0.3 的最终定位、边界、工作项和 Sprint 结构**
2. **把 review report 与 detail plan 收敛为一份可实施的权威主文档**
3. **为后续 task spec / CC 开发 / validation preregistration 提供单一上位依据**

### 0.1 文档权威性

从本文件开始：

- 若与 `scion-v0.3-draft.md` 冲突，**以本文为准**
- 若本文未展开某个实现细节，优先参考：
  - `reviews/v0.3-design-detail-plan.md`
  - `reviews/v0.3-design-review-report.md`
- `reviews/v0.3-design-review-request.md` 仅保留为审核输入归档，不再作为 v0.3 定稿依据

### 0.2 这次定稿真正完成的事

v0.3 不是“把 v0.2 backlog 补完”，而是完成下面三个升级：

- 从 **可跑** 升级到 **边界更稳、机制更清楚、证据更诚实**
- 从 **warehouse_delivery 特定实现** 升级到 **有问题适配边界的研究框架**
- 从“做了很多机制”升级到“**机制、实验、表述三者对齐**”

---

## 1. v0.3 最终定位

### 1.1 最终 release 定位

> **工程固化 + full-system validation + 技术债清理 + 问题适配边界建立 + 搜索机制系统化**

相比 Draft v2，这里有两个关键收口：

1. **“问题定义解耦”明确收口为 ProblemAdapter 边界**，不再停留在 YAML 去术语化
2. **“搜索研究体系化”拆成两层**：
   - W16: full-system validation
   - W17: lightweight mechanism study

这样做的目的，是让 v0.3 的研究表述与实验能力真实对齐。

### 1.2 v0.3 的五个最终目标

| 目标 | 最终含义 |
|---|---|
| 工程固化 | 把 v0.2 已设计但未接稳的核心机制接通，并收口成可维护实现 |
| Full-system validation | 用一组可复现实验矩阵验证完整 Scion 系统，而不是零散 showcase |
| 技术债清理 | 清掉会干扰 v0.3 稳定性和可读性的高价值技术债 |
| 问题适配边界建立 | 让 Scion core 不再直接依赖 warehouse_delivery 的语义、字段名、输出 shape |
| 搜索机制系统化 | 让 weight opt / plateau / classifier / memory 成为受控机制，而不是补丁堆叠 |

### 1.3 v0.3 不做什么

- ❌ Shadow deployment / 生产接入
- ❌ 结构级搜索（改 solver 主体架构）
- ❌ 多问题族的大规模研究验证
- ❌ 论文级完整 ablation matrix
- ❌ 为了“更通用”而重写 operator registry / pool 架构
- ❌ 把 Scion 过早抽象成“任意组合优化框架”

---

## 2. v3 基石架构中不可动摇的约束

v0.3 所有修改都必须服从 v3 蓝图，以下内容不讨论、不重开。

### 2.1 控制边界

- **Creative Layer = tainted**
- **Decision Layer = deterministic**
- LLM 只能提案，不能直接决策
- Contract Gate 与 Verification Gate 的职责边界保持不变

### 2.2 Decision Input Guard

Decision Layer 只允许读取：

- 数值
- 有闭集定义的枚举
- protocol / verification 产生的确定性聚合特征

Decision Layer 不允许直接读取：

- hypothesis_text
- classifier 原始文本输出
- search memory 自由文本总结
- research journal 自由文本总结
- weight-opt textual feedback

### 2.3 协议与晋升语义

- 三层 split 保持：screening / validation / frozen holdout
- champion 仍是 **池级别**，不是算子级别
- A/B 评估保持 champion solver vs candidate solver 语义
- 多目标 protocol 比较仍以 **字典序** 为主

### 2.4 v0.3 新增的 tainted metadata 约束

下列数据默认只允许给 LLM 或报表读，不允许直接进 Decision / Termination：

- `family_id`
- `family_source`
- `taxonomy_version`
- `search_memory_summary`
- `research_log`
- `weight_opt_summary`
- `optimum_gap`

如果未来要进入 deterministic control，必须先经过：

1. closed-set taxonomy
2. source / version 可追溯
3. 明确的 deterministic mapping

**v0.3 不做这一步。**

---

## 3. v0.3 最终工作项总表

### 3.1 工作项总览

为保持 lineage 连续性，保留原编号，但对部分 work item 做重定义或更名。

| # | 代号 | 最终定义 | Priority | Sprint |
|---|---|---|---|---|
| **W15** | **PROBLEM-ADAPTER** | 建立 ProblemAdapter 边界 + strict ProblemSpec + `toy_tsp` MWE | **P0** | **N0/N1** |
| W1 | SCORING-DECOUPLE | protocol scoring 与 weight-opt scoring 分离，加入 low-signal probe / auto-skip | P0 | N1 |
| W4 | MILP-INTEGRATION | 将 MILP 作为 report-only exact/bound anchor 接入 campaign/reporting | P0 | N1 |
| W2 | ASYNC-WEIGHT-OPT | immutable snapshot + version/revision + stage-aware stale | P0 | N2 |
| W3 | EARLY-STOP | plateau calibration + hard/soft saturation + override | P0 | N2 |
| W6 | FAMILY-PERSIST | hypotheses 落库 family_id/family_source/taxonomy_version | P0 | O0 |
| W7 | CLASSIFIER-WIRE | classifier 正式接电，taxonomy 闭环 + cache + fallback provenance | P0 | O1 |
| **W5** | **MEMORY-VIEWS-FROM-LINEAGE** | persist facts, rebuild views，不新增 mutable SearchMemory store | P1 | O1 |
| W8 | FAILURE-SUMMARY-V2 | failure facts 进 lineage，由 lineage 派生 failure summary / context | P1 | O1 |
| W9 | CAMPAIGN-JOURNAL | richer journal / champion evolution / cross-branch history for LLM context | P1 | P |
| W10 | WEIGHT-OPT-FEEDBACK | 将 coarse-grained parameter signal 注入 Round 1 prompt | P1 | P |
| W11 | SOLUTION-CONSISTENCY-DIAGNOSIS | 先把 V5 正名，再做 ENV/CANDIDATE/UNKNOWN 三分类 | P2 | P |
| W12 | CANARY-UPGRADE | canary set 版本化 + 自动积累只影响下一 campaign | P2 | P |
| W13 | TOKEN-USAGE-PERSIST | token usage / request kind / cache usage 持久化 | P2 | Q0 |
| W14 | TECH-DEBT-CLEANUP | 高价值 tech debt 清理与命名统一 | P2/P3 | Q0 |
| **W16** | **VALIDATION-MATRIX** | 18-campaign full-system validation matrix | **P0** | **Q1** |
| **W17** | **MECHANISM-STUDY** | lightweight mechanism study，承接 structure/parameter/early-stop/classifier 问题 | **P1** | **Q1** |

### 3.2 最关键的三处重定义

#### W15
从“problem.yaml 驱动去术语化”升级为：

> **ProblemAdapter 边界 + strict ProblemSpec + MWE 验证**

#### W2
从“把 async weight opt 接通”升级为：

> **结构版本 / 权重修订号 / 不可变 snapshot / stage-aware stale 的并发语义设计**

#### W16
从“18 campaigns 回答所有 RQ”升级为：

> **full-system validation；机制性问题由 W17 补充承接**

---

## 4. 问题适配边界：W15 的最终定义

W15 是 v0.3 最重要的地基工作。其目标不是“让 Scion 看起来 generic”，而是：

> **把 warehouse_delivery 的特有知识，从 core 中受控拔出，并收口到明确的 adapter boundary。**

### 4.1 最终原则

#### 原则 A：静态配置放 YAML，动态行为放 adapter

适合放 `problem.yaml`：

- problem id / display name
- objectives 列表及优先级
- operator categories
- llm hints
- family taxonomy
- search space / solver / parameter search config

适合放 `adapter.py`：

- solver output 反序列化
- feasibility 检查
- objective recomputation
- solution consistency 检查
- stronger lower-bound estimation
- richer problem summary / interface rendering

#### 原则 B：genericize comparison layer，不打散整个 objective type

v0.3 要 genericize 的是：

- objective comparator
- metric comparison / feedback schema
- case aggregate breakdown

**不建议**把整个 objective 体系粗暴改成裸 `dict[str, float]` 到处流动。

#### 原则 C：adapter 只允许 problem-root 内受控导入

不允许提供任意 `importlib.import_module("foo")` 能力。  
adapter import path 必须受限于：

```text
scion.problems.<problem_id>.*
```

### 4.2 推荐结构

```text
scion/
  scion/
    problem/
      contracts.py
      loader.py
      objectives.py
  problems/
    warehouse_delivery/
      problem.yaml
      adapter.py
      solver.py
      oracle.py
      operators/
        ...
    toy_tsp/
      problem.yaml
      adapter.py
      solver.py
      oracle.py
      operators/
        ...
```

### 4.3 strict ProblemSpec

v0.3 中 `ProblemSpec` 必须具备：

- `extra="forbid"`
- objective 名称唯一
- priority 连续且唯一
- adapter import_path 受限
- taxonomy 闭集可验证

### 4.4 generic objective comparison

`protocol/evaluation.py` 不再硬编码 warehouse 的 `(subcategory_splits, total_cost, runtime)`。

最终要求：

- 字典序比较由 `ObjectiveMetricSpec` 驱动
- `tolerance_abs` / `tolerance_rel` 明确化
- feedback / report 使用 generic metric breakdown
- protocol 的 win/loss/tie 口径不因 W15 变松

### 4.5 `toy_tsp` Minimal Working Example

`toy_tsp` 不是 README 占位，而是 **W15 的硬验收工具**。

最小要求：

- `problem.yaml`
- `adapter.py`
- `solver.py`
- `oracle.py`
- `operators/base.py`
- 至少 2 个 operator
- 1 个 screening case
- 1 个 canary case
- 一次短 campaign smoke
- 一组最小 tests

### 4.6 W15 验收标准

#### 一级验收（必须）

1. `warehouse_delivery` 已迁到 adapter boundary
2. `toy_tsp` MWE 跑通短 campaign
3. generic comparator tests 通过
4. ProblemSpec strict mode 生效
5. core runtime path 不再直接 import warehouse-specific runtime logic

#### 二级验收（辅助）

- `grep` 不再命中 warehouse 术语，只作为辅助手段，不作为核心验收

---

## 5. 目标比较与 weight-opt：W1 的最终定义

W1 的核心不是“让生产数据也出现 improved=True”，而是：

> **把 protocol 的判决口径，与 parameter layer 的优化信号彻底分离。**

### 5.1 必须保持不变的东西

- protocol 仍然使用 **strict lexicographic compare**
- promotion / abandon 决策口径不因 W1 改变
- Scion 的“主目标不能退化”原则不能被 scoring trick 洗掉

### 5.2 parameter layer 新增的能力

parameter layer 可引入：

- primary regression penalty
- secondary-focused normalized scoring
- low-signal probe
- auto-skip when low-signal

### 5.3 推荐最小策略

- 先做 quick probe（例如 6 eval）
- 若 score variance 过低，则标记 `low_signal_skip`
- 若主目标退化，则给极大惩罚
- 只有在主目标不退化时，次目标信号才进入优化

### 5.4 W1 验收标准

- synthetic 下旧行为不回退
- prod-like 数据下：
  - 要么稳定非负 gain
  - 要么被正确识别为 `low_signal_skip`
- protocol 判决与 v0.2 口径保持一致

---

## 6. Async weight opt 并发语义：W2 的最终定义

W2 是 v0.3 第二个最容易返工的点。它的核心不是“补 STALE_WEIGHT_UPDATE”，而是：

> **让 weight-only update 成为可审计、可取消、不会污染 live champion 的并发机制。**

### 6.1 版本语义

建议将 champion 的版本语义拆为：

- `version`: 结构版本（structural promote）
- `revision`: 权重修订号（weight-only update）

例：

```text
champion_v3_r0/
champion_v3_r1/
champion_v3_r2/
```

### 6.2 不可变 snapshot

v0.3 不允许：

- 原地 chmod 已冻结 snapshot
- 原地改写 live champion 目录
- 后台线程直接操作当前 champion 的活动目录

必须采用：

- copy-on-write / temp snapshot
- 原子指针切换
- 旧 snapshot 保持只读可追溯

### 6.3 stale 建模

不建议继续把 `STALE_WEIGHT_UPDATE` 作为核心状态扩张。

更稳的做法：

- 保持 `state=STALE`
- 新增 stale metadata：
  - `stale_reason`
  - `stale_from_stage`
  - `stale_from_version`
  - `stale_from_revision`

### 6.4 stage-aware 恢复语义

| stale 前阶段 | 最低重做阶段 |
|---|---|
| EXPLORE / EXPLORE_EXPAND | screening |
| READY_VALIDATE / VALIDATING / VALIDATING_EXPAND | validation |
| READY_FROZEN | validation |
| FROZEN_TESTING | 默认不打断，当前 frozen 完成后再 stale |

### 6.5 W2 验收标准

1. weight update 产生新 snapshot 目录，不改旧目录
2. double-promote 不会污染当前 champion
3. stale 恢复遵循 `stale_from_stage`
4. lineage 可追出 `(version, revision)` 链路
5. wall-clock 节省只作为附加指标，不作为主验收

---

## 7. 平台期与终止：W3 的最终定义

W3 的目标不是“更早停”，而是：

> **让 plateau 成为可校准、可覆写、不会误杀有效探索的终止机制。**

### 7.1 必须区分两类信号

- **hard saturation**：有可信下界支撑
- **empirical plateau**：经验上长期无正信号

这两类信号不能混在一个 `at_absolute_minimum=True` 语义里。

### 7.2 family_exhausted 的定位

`family_exhausted` 在 v0.3 只作为：

- soft guidance
- diversify 提示
- replay 诊断维度

**不作为 hard stop 依据。**

### 7.3 stop 策略

推荐两阶段机制：

1. plateau 首次命中 → 强制 diversify
2. diversify 后仍长期无正信号 → 才允许 stop

### 7.4 必要保护

- `force_continue=True`
- CLI `--disable-early-stop`
- `min_rounds_after_promote` 保护边界
- replay calibration on F1–F6

### 7.5 W3 验收标准

不再使用“F4-A 在某轮数区间停住”作为唯一主验收。  
必须增加：

- false-stop replay count
- missed-promotion cases
- saved rounds distribution

---

## 8. MILP integration：W4 的最终定义

MILP 在 v0.3 中的定位是：

> **exact / bound anchor，而不是主搜索决策器。**

### 8.1 保持 report-only 角色

MILP 不进入：

- promotion gate
- branch scheduling
- hard termination

MILP 进入：

- report
- optimum gap 分析
- benchmark calibration
- impossible claim sanity check

### 8.2 实例范围

- `s01/s02/s03`：必须求 exact optimum
- `ml01-ml04`：能跑就跑，超时记 bound-only
- 大实例：不做 exact 尝试

### 8.3 必加 sanity check

若某实例已知 exact optimum，而 candidate 报告出现：

- objective 优于 exact optimum
- 或 negative gap 超出 epsilon

这不是“候选太强”，而应触发：

- objective recomputation bug 排查
- oracle bug 排查
- MILP mapping bug 排查
- solver output bug 排查

### 8.4 W4 产物

- exact optimum cache
- bound-only metadata
- certified optimum / timeout-bound 区分
- gap 曲线和 summary 对齐

---

## 9. 语义分类与 memory：W5/W6/W7/W8 的最终定义

这条线的总原则是：

> **persist facts, not views**

### 9.1 W6 前移，先于 W7

先完成：

- `family_id`
- `family_source`
- `taxonomy_version`
- 可选 `classifier_model`

落库，再做 classifier 接电。

### 9.2 W7 classifier 的最终形态

v0.3 推荐保守实现：

- hypothesis Contract 通过后
- **同步**调用 classifier
- timeout 3s
- 失败即 fallback
- 记录 provenance
- 命中 cache 时直接复用

不建议再起新 async thread，以免再引入一套并发复杂度。

### 9.3 taxonomy 来源

family taxonomy 最终应从 problem spec 读取，而不是散落在 code 常量里。

### 9.4 W5 更名与收口

W5 更名为：

> **MEMORY-VIEWS-FROM-LINEAGE**

事实层持久化：

- hypotheses
- family metadata
- promotions
- failures
- weight optimizations
- token usage

视图层按需重建：

- SearchMemory
- CampaignJournal
- FailureSummary
- Report tables

### 9.5 W8 收口

W8 不再建立新的“failure 事实源”，而是：

- failure facts 进入 lineage
- summary / aggregation 从 lineage 派生
- context 注入使用 derived view，不复制事实

### 9.6 W5/W6/W7/W8 的共同验收要求

- 不新增第二套 mutable truth store
- `family_source` 可区分 classifier / keyword / backfill
- 重复 hypothesis 文本可命中 cache
- failure taxonomy 与 DecisionFeatures 使用口径一致

---

## 10. 上下文、反馈与诊断：W9/W10/W11/W12

### 10.1 W9 Campaign Journal

目标是增强 LLM context，不是把所有历史全量塞进 prompt。  
最终要求：

- champion 演化摘要结构化
- cross-branch history 可控压缩
- 旧 champion 全量代码不默认注入 prompt
- context 仍服从暴露控制

### 10.2 W10 Weight-opt Feedback

只允许注入 **coarse-grained、tentative** 的参数信号，例如：

- 哪些算子在近期 weight-opt 中表现相对稳定
- 哪些算子信号低或不确定

不允许把 weight-opt textual summary 直接送进 Decision。

### 10.3 W11 Solution Consistency Diagnosis

先做语义正名：

- 旧 `V5_state_leak` 命名已不足以表达真实问题
- v0.3 先统一到 `solution_consistency` 语义
- 再做 `ENV / CANDIDATE / UNKNOWN` 三分类

### 10.4 W12 Canary Upgrade

- canary set 必须版本化
- 自动积累只影响下一 campaign，不 retroactively 改当前 campaign 语义
- impossible claim / known failure replay 可进入 canary 候选池

---

## 11. 技术债与数据记录：W13/W14

### 11.1 W13 Token Usage Persist

除了 prompt/completion tokens，建议同时记录：

- request kind
- model id
- cache tokens / cache hit usage（若 provider 可提供）
- retry counts
- timeout / provider incidents

这样 W16/W17 才能做更可信的成本与 drift 分析。

### 11.2 W14 Tech Debt Cleanup

本轮优先清理：

- `verification/state_leak.py` 删除
- V1-V9 命名口径统一
- classifier API mismatch
- debug 前缀与 logger 统一
- ProblemSpec strict mode
- failure code taxonomy 对齐

原则：

- 清理会干扰 v0.3 设计收口的债
- 不做大范围“顺手重构”

---

## 12. Sprint 结构：最终版

原始 `N → O → P → Q` 宏观顺序保留，但粒度细化为以下结构。

### 12.1 Sprint N0 — Foundation Abstraction

- W15 基础边界冻结
- strict ProblemSpec
- adapter loader
- generic objective comparator
- `toy_tsp` MWE 骨架

### 12.2 Sprint N1 — Objective / Benchmark Layer

- W15 warehouse 真迁移
- W1 scoring decouple
- W4 MILP integration

### 12.3 Mini-Validation A

- warehouse synthetic smoke
- warehouse prod smoke
- toy_tsp smoke

目标：证明 ProblemAdapter + scoring + MILP anchor 没把系统打坏。

### 12.4 Sprint N2 — Concurrency & Termination

- W2 async weight-opt redesign
- W3 early-stop redesign

### 12.5 Sprint O0 — Persistence Foundation

- W6 family persistence
- classifier API repair
- taxonomy contract 收口

### 12.6 Sprint O1 — Semantic Memory Wire-up

- W7 classifier wire
- W5 memory views from lineage
- W8 failure summary v2

### 12.7 Mini-Validation B

- classifier on/off smoke
- async weight update stress
- early-stop replay smoke

### 12.8 Sprint P — Context & Diagnosis

- W9 campaign journal
- W10 weight-opt feedback
- W11 solution consistency diagnosis
- W12 canary upgrade

### 12.9 Sprint Q0 — Instrumentation & Cleanup

- W13 token usage persist
- W14 tech debt cleanup

### 12.10 Sprint Q1 — Validation & Mechanism Study

- W16 validation matrix
- W17 mechanism study

---

## 13. W16/W17：实验设计与研究表述的最终对齐

这是 v0.3 定稿最重要的研究表述修正。

### 13.1 W16 的最终角色

W16 只负责：

> **full-system validation**

即回答：

- 在给定 proposal model、problem variant、protocol 下，完整 Scion 系统的表现如何
- 不同 model / variant 下，full-system 行为模式如何变化
- 小实例 exact gap 分布如何

### 13.2 W16 实验矩阵

- Proposal model：3
  - `claude-opus-4-6`
  - `claude-sonnet-4-6`
  - `gpt-5.4`
- Problem variant：2
  - `warehouse_synthetic`
  - `warehouse_prod`
- Seed：3
  - `11 / 29 / 47`
- Campaign rounds：100（允许 early stop）

总计：**18 campaigns**

### 13.3 W16 能回答什么，不能回答什么

| 问题 | W16 能否回答 |
|---|---|
| full-system efficacy | ✅ |
| selected proposal models 的系统差异 | ✅ |
| synthetic vs prod 在当前协议下的行为差异 | ✅（带限定） |
| small exact cases 上的 gap 分布 | ✅ |
| structure-only 效果 | ❌ |
| parameter-only 效果 | ❌ |
| structure + parameter synergy | ❌ |
| early-stop causal gain | ❌ |

### 13.4 W17 的必要性

W17 是轻量机制研究层，用最小成本承接 W16 回答不了的问题。

建议最小设计：

#### Layer A: structure / synergy
- full-system vs weight-opt off
- 2 variants × 3 seeds × 1 主模型

#### Layer B: parameter-only
- offline snapshots 做 parameter-only analysis

#### Layer C: early-stop
- replay / paired subset on/off

#### Layer D: classifier utility
- classifier on/off 或 classifier vs keyword replay

### 13.5 最终研究表述

因此 v0.3 最诚实的表述是：

> **v0.3 完成 full-system validation，并用小规模 mechanism study 初步回答部分搜索机制问题。**

而不是：

> “18 campaigns 已经完整回答 structure/parameter/synergy/early-stop 全部问题。”

---

## 14. Review Gate 与验收机制

### 14.1 每个 Sprint 的共同门槛

- pytest 全绿
- 相关 smoke / replay 通过
- 不破坏 v3 基石边界
- 文档 / schema / logging 同步更新

### 14.2 Sprint 级关键 checkpoint

#### Sprint N 结束必须证明
- ProblemAdapter 不是假解耦
- scoring decouple 不破坏 protocol
- MILP anchor 可产出可信 gap / bound
- async / early-stop 设计草案已冻结，未留悬空语义

#### Sprint O 结束必须证明
- family persistence 与 classifier provenance 成立
- memory views 来源统一，不形成多 truth source

#### Sprint P 结束必须证明
- context 丰富化没有把 tainted metadata 偷渡进 Decision

#### Sprint Q 结束必须证明
- validation-prereg 冻结
- W16 / W17 的 claim 与 experiment 对齐

---

## 15. v0.3 最终交付物

### 15.1 代码层

- ProblemAdapter 边界与 strict ProblemSpec
- generic comparator
- immutable weight-update revision path
- calibrated early-stop
- classifier + family persistence + lineage-derived views
- MILP exact/bound integration

### 15.2 文档层

至少应新增或定稿：

- `design/scion-v0.3-design.md`（本文）
- `design/scion-problem-interface-v1.md`
- `design/validation-prereg.md`
- `design/w16-w17-experiment-redesign.md`（可并入 prereg）
- `docs/v0.3-final-state.md`（发版时）

### 15.3 报告层

- `reports/v0.3-validation/`
- `reports/v0.3-validation/SUMMARY.md`
- `reports/v0.3-mechanism-study/`（若做 W17）

---

## 16. 立即下一步

按本文定稿后，建议直接进入以下动作：

1. **冻结本文 wording，完成一次 BigBOSS review**
2. 基于本文拆出 3 份 P0 task spec：
   - W15 ProblemAdapter
   - W2 Async Weight Opt redesign
   - W16/W17 experiment redesign
3. 同步生成：
   - `scion-problem-interface-v1.md`
   - `validation-prereg.md`
4. 切 `v0.3-dev`，按 N0 → N1 → Mini-Validation A 开工

---

## 17. 一句话总结

Scion v0.3 的定稿目标，不是“把 backlog 清干净”，而是：

> **在不破坏 v3 架构基石的前提下，把问题适配边界、搜索机制、验证实验、研究表述一起收口成一套更稳、更诚实、可继续演进到 v1.0 的框架。**

---

*本文为 v0.3 final 级别主文档框架。后续若继续细化实现接口与实验细节，应在不改变本文边界判断的前提下展开。*
