# 📋 内容审核报告

- **审核时间**: 2026-04-01 17:16:48
- **审核模型**: gpt-5.4-pro
- **推理深度**: high
- **内容来源**: prompt.md
- **内容长度**: 53265 字符
- **审核耗时**: 747.5 秒

---

## 📝 审核意见

# OR-AutoResearch Agent Framework v0.1 Blueprint v2 深度审核意见

> 以下审核**以 v0.1 蓝图正文为主**，并结合你后附的两份上下文文档（工程应用架构 / Multi-Agent Autoresearch v2）一起看。  
> 先给一句总判断：

## 总体结论

**v2 相比 v1 是一次“实质升级”，不是表面修补。**  
它已经从“一个 agent loop 的想法”进化成了“一个有治理意识的实验系统蓝图”。

但我更准确的判断是：

> **v2 把 v1 的 6 个缺口基本都“显式补上了组件”，但还没有全部“补成可发表、可复现、可抗质疑的协议闭环”。**

换句话说：

- **骨架补齐了**：有了协议、合同层、隔离、血缘、失败分类、终止条件
- **但还没完全长出“研究可信性”的硬器官**：尤其是  
  1) **语义级 Verification Gate**  
  2) **反泄漏的三级实验协议 / 暴露控制**  
  3) **LLM 隐蔽决策路径封堵**

如果要给一个简短定位：

> **v2 已经是一个高质量原型蓝图；但还不是一个论文级“可信自动研究协议”。**

---

## 一、快速评分总览

| 维度 | 评分 | 审核结论 |
|---|---:|---|
| 架构完整性 | **7/10** | 6 个缺口都被补到了，但多数仍停留在“模块存在”而非“协议闭环” |
| 三层控制模型 | **6/10** | 比 v1 明显更硬，但仍存在若干隐蔽决策路径 |
| 实验协议层 | **5/10** | 有统计意识，但还不足以支撑“研究结论可信” |
| 可行性（4 周） | **MVP 6/10 / 完整版 3.5/10** | 做出受限原型现实；做出“完整可信版”不现实 |
| 差异化 | **6.5/10** | 方向是对的，但当前贡献更偏“治理工程”而非已被证明的学术新意 |
| 学术价值 | **5.5/10** | 有潜力，但离顶会/顶刊还差严格实验设计、ablation 和跨任务验证 |

---

# 二、v2 是否真正解决了 v1 的问题？

这是本次审核的核心。我先直接回答：

## 结论：**“部分解决，且解决程度不均衡”**

v2 对 v1 的 6 个关键遗漏，**不是没补**，而是**补得有深有浅**。

## 2.1 六个缺口逐项审核

| v1 缺口 | v2 的补法 | 我的判断 | 主要剩余问题 |
|---|---|---|---|
| 实验协议层 | `Experiment Protocol` | **部分解决** | 只有配对评估/seed/回归检测雏形，缺**split 管理、暴露策略、顺序检验、功效分析、多重比较控制** |
| 执行沙箱 / Runtime Isolation | `per-branch workspace + champion immutable + timeout + cleanup` | **部分解决** | 这更像“工作目录隔离”，还不是严格 sandbox；缺**只读挂载、子进程隔离、无网络、资源上限、import/cache 污染防护** |
| Artifact / Lineage | `hypothesis_id → code_hash → protocol_version → raw_metrics → decision_trace` | **大体解决，但不完整** | 还缺**append-only / hash-chain、不变更保证、prompt/model version、retrieval context hash、依赖和硬件信息** |
| Failure Taxonomy | Enum 分类 + 路由策略 | **部分解决** | 分类维度混杂：把**执行错误、基础设施故障、实验结果标签**放在一个 taxonomy 里，后续会难维护 |
| Scheduler 形式化 | `validate debt first → explore by signal → create new` | **部分解决** | 这是策略口号，不是形式化调度；缺**优先级函数、饥饿避免、budget 分配、stale branch 处理** |
| 终止条件 | `硬预算 + 停滞检测 + 无活跃分支` | **部分解决** | “停滞”定义不清；缺**统计上定义的停滞、holdout 使用上限、不同失败类型是否计入停滞** |

---

## 2.2 比 6 个已知缺口更关键的“仍未补齐项”

这是我认为最重要的一点：  
**v2 补齐了 v1 被指出的 6 个缺口，但仍缺了几个对“可信研究”同样关键的一等组件。**

### 仍缺失/弱化的关键组件

#### 1）**Verification Gate 仍未在蓝图正文中成为一等公民**
你在上下文文档里其实已经有更强版本了：  
- unit tests  
- feasibility oracle  
- objective recomputation  
- no state leak  
- wall-clock / memory guard  

但在本蓝图 v2 正文里，**Contract Layer 被写得很强，Verification 却被弱化成了 `verify` 一步和 W3 的 `code_verify`**。

这是个关键问题，因为：

- **Contract 解决的是“越不越界”**
- **Verification 解决的是“是不是还在解同一个问题、有没有偷偷改 objective / 约束 / 状态语义”**

这两者不是一回事。  
**目前 v2 更像“语法/接口/边界约束很强”，但“语义正确性校验仍不够一等化”。**

---

#### 2）**缺少“实验集 / seed / 暴露控制”的正式管理器**
蓝图里写了：
- same case same seed
- fresh cases only
- exclude_used 防过拟合

这些都对，但还不够。

你真正需要的是一个明确的：

- `SplitManager`
- `SeedLedger`
- `ExposurePolicy`

否则 reviewer 会质疑：

- “fresh cases only” 是**每分支 fresh**，还是**全局 fresh**？
- seed 是不是可以“挑 seed”？
- validation 看过 aggregate 以后是否还在继续搜索？如果是，那它就不是 frozen holdout 了

---

#### 3）**缺少“Decision Input Guard / 信息流白名单”**
三层控制是对的，但你还没有把它写成“严格的数据读写权限矩阵”。

现在最大的隐患是：

> 虽然你口头上说 “LLM 只提案不决策”，但如果 Decision/Scheduler 能读取 LLM 的文本字段，它就仍然在**间接决策**。

这个问题我在后面会展开。

---

## 2.3 核心判断

### v2 是否真正解决了 v1 的问题？
**回答：解决了 60%~70%，但还没有达到“可证明地解决”。**

更准确地说：

- **v1 的问题在 v2 已经被“识别并结构化承认”**
- **但只有一部分被“协议化落地”**
- **最大短板不再是模块数量，而是协议形式化程度**

---

# 三、逐维度深度审核

---

## 1. 架构完整性：v2 补了 6 个组件，是否真正补齐了 v1 的问题？还有关键遗漏吗？

## 1.1 优点

### （1）总体结构已经明显成型
v2 的强项不是 agent 数量，而是**实验治理骨架**已经比较完整：

- `Control Flow`
- `Branch Controller`
- `Experiment Protocol`
- `Contract Layer`
- `Runtime Isolation`
- `Context Manager`
- `Scheduler`
- `Failure Taxonomy`
- `Artifact & Lineage`
- `Termination`

这比很多“自动科研”方案要严肃得多，也比 Karpathy 式 keep/discard loop 明显成熟。

---

### （2）Scope 收紧是非常正确的
这一点值得肯定。  
你把 v0.1 明确收紧为：

- 单问题
- 单机
- 单进程
- 单目标
- 固定 benchmark schema
- 受限 patch 空间

这会大幅减少“设计上很美、实现上爆炸”的风险。  
**这是 v2 比很多空泛 agent 项目更可信的地方。**

---

### （3）Branch Controller 的存在是实打实的进步
`explore → validate → promoted/abandoned`  
再加上：

- max 3 活跃分支
- 每分支 max 3 commits
- 从 champion 分叉

这些规则虽然朴素，但已经开始把搜索从“单线爬山”变成了“有限分支治理”。

---

## 1.2 关键不足

### （1）**Verification Gate 没有被真正抬到一等架构层**
这是我认为当前架构里最大的缺口之一。

#### 现在的问题
蓝图里 `Contract Layer` 很突出，但 `verify` 只在流程中一笔带过。  
而从你的上下文文档看，真正保证可信性的其实是：

- feasibility oracle
- objective recomputation
- regression tests
- state leak check
- complexity guard

#### 为什么这是硬缺口
因为如果没有 semantic verification，LLM 完全可能在白名单文件里做出：

- 放松约束
- 改变目标函数增量计算
- 引入状态污染
- 偷偷改变 benchmark interaction

这些行为**不一定违反 Contract**，但会污染实验信号。

#### 建议
把 `Verification Gate` 独立成顶层组件，位置在：

```text
Proposal -> Contract -> Build Candidate -> Verification Gate -> Experiment Protocol
```

并明确区分：

- **Contract**：边界与结构
- **Verification**：语义正确性与安全性
- **Protocol**：统计可信性

这三层缺一不可。

---

### （2）**Experiment Protocol 还不是“协议”，更像“统计意识 + 几个规则”**
现在的设计只有：

- 配对评估
- seed
- exclude_used
- regression detection

这还不足以应对 adaptive search 下的统计污染。

#### 缺的核心点
- 固定且版本化的 `screen / dev / frozen` split
- 信息暴露矩阵（谁能看哪些结果）
- frozen set 使用次数上限
- 多分支多轮搜索下的多重比较问题
- optional stopping / repeated peeking 的控制
- 功效分析或最小样本量规则
- 实例分层抽样而不是纯随机抽样

---

### （3）**Scheduler 还没有真正形式化**
`validate debt first → explore by signal → create new`  
这个方向没问题，但它还不够“可实现、可复盘、可写论文”。

#### 还需要明确的东西
- “signal” 到底是什么？
- signal 是否只来自数值结果，还是也读取 LLM 的 `confidence / improvement_axes`？
- 如何防止 starvation？
- champion 更新后，老分支是否 stale？是否要 rebase / revalidate？
- 如果某分支多次 infra failure，调度如何处理？

---

### （4）**缺少 parent champion / stale branch 的正式语义**
当前只说“从 champion 分叉，promote 时 squash + 清理 stale”，但没有正式规则。

这会引发一个实际问题：

- 分支 A 是从 champion_0 分出的
- 分支 B 先晋升成了 champion_1
- 这时分支 A 的结果要和谁比？
  - champion_0？
  - champion_1？
  - 还是必须重跑？

如果这里不写清楚，后面实验结论会混乱。

#### 建议
在 lineage 中加入：
- `parent_champion_id`
- `branch_base_hash`
- `stale_status`
- `revalidation_required`

---

### （5）**Runtime Isolation 目前更像“目录隔离”，不是严格执行隔离**
你写的是：

- per-branch workspace
- champion snapshot immutable
- 依赖锁定
- timeout
- cleanup
- 不用 Docker

对于 v0.1 工程原型，这个选择我能理解；  
但要把它称为“执行隔离”，**目前力度偏弱**。

#### 主要风险
- Python import cache 污染
- 环境变量泄漏
- 子进程/网络访问
- 对父目录的写入
- 临时文件 / cache 的跨 run 污染

#### 建议最低配
即使不用 Docker，也建议至少做到：

- **subprocess-per-run**
- `resource.setrlimit` 的 CPU / memory / file descriptor 限制
- 只读 benchmark / champion snapshot
- 临时目录 chroot-like 约束（至少路径级隔离）
- 禁网
- 禁止非白名单 import / subprocess / shell 调用

---

## 1.3 架构完整性结论

### 结论一句话
**v2 把 v1 从“缺骨头”推进到了“有骨架”，但还没到“协议闭环、论文级可信”的程度。**

### 最关键的仍缺项
1. **Verification Gate 一等化**
2. **实验集/seed/暴露管理正式化**
3. **Decision Input Guard（LLM 文本字段不能进入决策层）**

---

## 2. 三层控制模型：Creative → Contract → Decision 的边界是否足够硬？LLM 是否仍有隐蔽决策路径？

## 2.1 这是 v2 最正确的升级方向之一

我先明确说：  
**“LLM 产出是提案，不是决策”** 这一原则是对的，而且是整份文档里最有价值的理念之一。

相比 v1 的“只列 4 个介入点”，v2 把控制关系抽象成：

- Layer A：Creative
- Layer B：Contract
- Layer C：Decision

这个抽象是显著更强的。

---

## 2.2 但边界还不够“硬”

### 关键问题：**你目前的 Contract 更像“格式过滤器”，还不是“决策隔离器”**

以下几条是我认为仍然存在的隐蔽决策路径：

---

### 隐蔽路径 1：`analysis` 字段本身就是 covert channel
你现在允许的 analysis fields 是：

- `suspected_failure_mode`
- `improvement_axes`
- `confidence`
- `evidence_summary`

#### 问题在哪里？
这些字段虽然“被白名单了”，但它们依然是**高自由度文本/半结构化信息**。  
如果后续 Scheduler / Branch Controller / 人类 reviewer 会看这些字段，它们就仍然可能成为隐蔽决策通道。

尤其危险的是：

- `confidence`：**不应该由 LLM 提供给决策层**
- `evidence_summary`：可能携带大量未受控偏置
- `improvement_axes`：实质上可能在影响下一步搜索方向

#### 建议
- `confidence` 改为 **Auditor/Protocol 计算出的数值**
- `suspected_failure_mode` 必须是**枚举**而不是自由文本
- `improvement_axes` 必须从**预注册的 change_locus taxonomy** 中选择
- `evidence_summary` 仅供人类阅读，**不得被调度器读取**

---

### 隐蔽路径 2：`branch direction` 本身就接近“战略决策”
你把 `branch direction` 放在 Creative Layer，然后用 novelty 检查约束。

但问题是：

> “往哪个方向分支”本身，已经非常接近决策了。

如果 LLM 可以持续建议：

- 改 destroy 不改 repair
- 聚焦 dense 不管 sparse
- 重试某一方向而不是放弃

那它就在实质上影响资源分配。

#### 建议
更硬的做法是：

- LLM 只能提出若干**候选 hypothesis proposal**
- **是否开新分支、先 validate 还是先 explore、是否 abandon**，必须只由 Decision Layer 基于数值证据决定
- `branch direction` 不应该是 LLM 的最终动作，而应该是 LLM 的**候选建议**

---

### 隐蔽路径 3：Context Manager 本身可能放大叙事偏差
你已经从自然语言日志升级为 `HypothesisRecord`，这是对的。  
但它目前仍有相当多自由文本字段：

- `hypothesis_text`
- `expected_effect`
- `observed_effect`

这些一旦进入 LLM 上下文，仍可能形成“自我强化叙事”。

#### 建议
将 `HypothesisRecord` 进一步结构化：
- `change_locus`: enum
- `predicted_direction`: improve / neutral / tradeoff
- `target_subgroup`: enum
- `evidence_refs`: experiment_id list
- `status`: active / weakened / rejected / promoted
- `blacklist_scope`: 不要只 local/global，改为条件化 scope

---

### 隐蔽路径 4：`novelty check` 本身也可能不确定
如果 novelty check 只是：
- 文本相似度
- LLM 判断“是不是新”

那它又把 LLM 带回决策回路了。

#### 建议
novelty 至少先做 deterministic 版本：
- touched files
- touched symbols
- AST diff signature
- change_locus taxonomy signature
- parameter vector signature

---

### 隐蔽路径 5：小 patch 不代表小风险
`patch size limit = 200 lines` 很有工程价值，但不能当成真正边界。

因为：
- 1 行 `import hacked_helper` 的风险可能大于 200 行普通逻辑
- 一个小 patch 可以改变 RNG、目标函数、约束调用路径

所以 patch size 只能是**辅助约束**，不能是核心安全依据。

---

## 2.3 这套三层模型怎样才算“边界足够硬”？

我建议你在 v2.1 里加一个概念：

## **Decision Input Guard / Taint Rule**

### 原则
Decision Layer 只能读取：
- 枚举标签
- 数值指标
- contract pass/fail
- verification pass/fail
- protocol statistics
- branch metadata

**Decision Layer 不得读取任何 LLM 自由文本。**

---

### 建议的权限矩阵

| 数据类型 | LLM 可写 | Contract 可改写 | Decision 可读 |
|---|---:|---:|---:|
| hypothesis_text | ✅ | 仅存档 | ❌ |
| improvement_axes(enum) | ✅ | 校验 | 可选，建议有限读取 |
| confidence（LLM 版本） | ✅ | 可存档 | ❌ |
| protocol_confidence / CI | ❌ | ❌ | ✅ |
| evidence_summary | ✅ | 仅过滤 | ❌ |
| touched_files / touched_symbols | ✅ | 校验生成 | ✅ |
| win_rate / median_delta / CI | ❌ | ❌ | ✅ |
| failure_type(enum) | 部分 | 归一化 | ✅ |

---

## 2.4 三层控制模型结论

### 结论一句话
**v2 的三层控制模型比 v1 进步很大，但还没有做到“LLM 无法间接操控调度和晋升”。**

### 最需要补的硬化动作
1. **Decision Layer 只读数值和枚举，不读自由文本**
2. **LLM 的 confidence 一律不进入决策**
3. **branch direction 从“LLM动作”降级为“LLM候选建议”**
4. **novelty check 做 deterministic signature，不依赖语义主观判断**

---

## 3. 实验协议层：seed 策略 / 配对评估 / 回归检测是否合理？能否保证研究结论可信？

这是我认为目前 **最大的不够硬之处**。

## 3.1 先说优点

### （1）你已经抓住了几个正确方向
- **配对评估**：对 stochastic solver 非常关键
- **同 case 同 seed**：是 Common Random Numbers 的近似做法
- **fresh cases**：比在同一批 case 上反复调 prompt 强
- **回归检测**：有安全意识

这说明你已经超出“跑一堆 benchmark 取最好”的水平了。

---

## 3.2 但当前协议还不足以支撑“可信研究结论”

### 核心问题 1：`N >= 6` + `win_rate >= 2/3` 作为 promotion 依据太弱
这是最需要明确指出的一点。

如果把每个配对结果压缩成 win/loss，  
那么在零假设下，`N=6` 时：

- `4/6` 胜出的单侧精确符号检验 p 值约为 **0.344**
- `5/6` 胜出 p 值也还有 **0.109**
- 只有 `6/6` 才接近 **0.016**

也就是说：

> **`win_rate >= 2/3, N >= 6` 更像 screening 阈值，不像 confirmatory promotion 阈值。**

`median_delta >= min_practical_delta` 能过滤一部分无意义改善，但它不是显著性控制，也不能解决 repeated search 下的多重比较问题。

---

### 核心问题 2：same seed 不等于真正的 CRN
你写的“同 case 同 seed”是对的，但要小心一个常见误区：

> **相同 seed 不一定带来可比的随机流。**

如果 candidate 改变了：
- RNG 调用顺序
- 调用次数
- 提前停止逻辑

那它和 champion 虽然 seed 相同，实际并不共享相同随机轨迹。

#### 建议
如果真想更接近 CRN，最好做：
- 外部注入 RNG stream
- destroy / repair / acceptance 分流的随机源
- 或至少在论文里诚实表述：这是 `same-seed paired evaluation`，不是严格 CRN

---

### 核心问题 3：`exclude_used` 还不够，必须有固定 split 与暴露策略
当前 `sample_cases(exclude_used)` 有两个问题：

#### 问题 A：分布漂移
随机排除已用 case 会导致不同分支看到的 case 分布可能不同，后续比较不稳定。

#### 问题 B：信息泄漏仍然存在
即使单个分支不重复 case，**系统层面**仍可能通过多轮 adaptive search 间接“看遍整个 benchmark pool”。

#### 建议
升级为正式三层实验集：

1. **Screening set**  
   - 可反复用  
   - 可看细节  
   - 用于 explore

2. **Dev validation set**  
   - 分支级 one-shot  
   - 只暴露 aggregate  
   - 用于 validate

3. **Frozen holdout set**  
   - 全 campaign 限量使用  
   - 只给 pass/fail + aggregate  
   - 用于最终 paper claim

> 你后附的 Multi-Agent v2 其实已经有这个设计了。  
> **很遗憾的是，当前蓝图正文把这部分简化弱化了。**

这是一个明显的“可信性回退”。

---

### 核心问题 4：回归检测的定义不够清晰，容易变成“伪安全阈”
你写的是：

> candidate 不能在历史 case 上显著退化

这个思路没错，但现在定义不够清楚：

- 历史 case 是什么集合？
- 是过去 explore 用过的 case，还是一个固定 canary set？
- “显著退化”怎么判？
- 如果历史 case 越积越多，会不会让 veto 越来越严，最后什么都过不了？

#### 建议
把回归检测重命名并正式化为：

## **Canary Regression Check**
- 使用固定小型 canary set
- 只做安全 veto，不作为改善证据
- 阈值可设为：
  - feasibility violation = 0
  - timeout rate 不上升
  - paired lower CI 不低于 -δ_regress

---

### 核心问题 5：缺少 optional stopping / retry 的规则
你写了“含 retry”，这个地方非常敏感。

如果 retry 的含义不清楚，就容易被 reviewer 质疑为：
- rerun 直到过门槛
- seed shopping
- case shopping

#### 建议强制区分两种 retry：
1. **Infra retry**：允许  
   - API failure
   - benchmark infra failure
   - 机器故障

2. **Stat retry**：不能随意重试  
   如果结果 `unclear`，只能按照**预注册规则扩大样本量**
   - 例如从 N=6 扩到 N=12，再到 N=20
   - 不能无限 rerun 到过阈值

---

## 3.3 如果目标是“研究结论可信”，最低需要补哪些协议？

我建议至少做成如下层级：

### Screening（探索阶段）
- N=6 可接受
- paired
- stratified sample
- 允许看 breakdown
- 只用于“是否继续探索”

### Validation（开发验证）
- N>=12 或 20
- 预注册 seed bank
- 只暴露 aggregate
- 使用：
  - paired sign test / Wilcoxon / bootstrap CI
  - practical effect threshold

### Frozen Holdout（最终确认）
- disjoint case set
- 使用次数全局上限
- 只给 pass/fail + aggregate
- 不允许基于结果继续改模型后再重测同一 holdout

---

## 3.4 实验协议层结论

### 结论一句话
**当前 v2 的实验协议设计“方向正确但证据强度不足”，还不能单凭它保证研究结论可信。**

### 最关键建议
1. **把两阶段升级回三阶段（screen/dev/frozen）**
2. **把 `N>=6 + 2/3` 明确降级为 screening gate，而不是最终 promotion 依据**
3. **引入 seed ledger、暴露矩阵、optional stopping 规则**
4. **用 paired bootstrap CI / sign test / Wilcoxon 补强统计证据**

---

## 4. 可行性：4 周实现 v2 完整 scope 是否现实？哪些模块难度仍被低估？

## 4.1 我的判断：**做出“可演示原型”现实；做出“完整可信 v2”不现实**

结合你的背景：

- 你是 OR & 优化算法工程师
- 已有 2 次 autoresearch 实战
- 应该已有 benchmark/harness 基础

所以我不会简单说“不现实”。  
但必须分清两个目标：

### 目标 A：**4 周做出受限 MVP**
这个是**有机会的**。

### 目标 B：**4 周做出完整 v2 scope、达到研究可信与论文级复现**
这个我判断是**明显偏乐观**。

---

## 4.2 哪些模块难度被低估了？

### 难度 Top 1：**Verification / Benchmark 语义正确性**
这通常不是“写几个 check”就完了，而是要回答：

- feasibility oracle 从哪里来？
- objective recomputation 如何可靠实现？
- no state leak 怎么测？
- wall-clock 基线怎么公平定义？
- benchmark harness 是否足够确定性？

这部分往往是整个系统最耗时间的。

---

### 难度 Top 2：**实验协议 + 统计细节**
看起来只是：
- 配对评估
- seed
- gate

但真正实现时会碰到很多坑：

- seed bank 版本化
- case split 固定与暴露控制
- unclear 时扩样规则
- infra failure 重试与统计 failure 的边界
- 历史 case / canary case / validate case 的关系

这部分如果不提前形式化，后期很容易返工。

---

### 难度 Top 3：**Runtime Isolation**
“目录隔离，不用 Docker”听上去省事，但实际容易踩坑：

- import 污染
- Python module 缓存
- 相对路径穿透
- cache 和临时文件残留
- 同进程状态污染

如果你想让 benchmark 结果真正可信，至少要做到**子进程级隔离**。  
这部分实际工程成本并不低。

---

### 难度 Top 4：**Context Manager + 结构化记忆**
这块在文档里看起来轻，但实际很容易退化成：
- 结构体很多
- 真正有用的信息提炼很少
- 记忆逻辑影响 prompt 稳定性

尤其 `HypothesisRecord` 如果字段不够强类型，很快会再次变成“半结构化日志堆”。

---

## 4.3 4 周计划逐周审核

| 周次 | 计划 | 审核意见 |
|---|---|---|
| W1 | promotion_gate, experiment_protocol, branch_controller, failure_taxonomy, runtime_isolation, artifact_lineage | **任务堆得过满**。这些模块里至少 3 个需要联调和测试，不太像一周稳定收尾 |
| W2 | contract_layer, context_manager, loop.py, LLM client, prompt 模板 | 合理，但前提是 W1 已稳定，否则这里会被上游拖慢 |
| W3 | code_verify, benchmark_run, VRP destroy operator 验证问题 | **高风险周**。Verification + Benchmark 往往才是最难的 |
| W4 | ≥10 轮实验，验收 | **只够 smoke test，不够验证“系统可信”** |

---

## 4.4 更现实的排期建议

### 如果坚持 4 周
建议把目标改成 **v2-lite**：

#### P0 必做
- Branch FSM
- Contract Layer
- Basic Verification（至少 import/interface/unit test/feasibility）
- Paired Evaluation
- Artifact Lineage
- subprocess 级 runtime isolation

#### P1 延后
- 复杂 failure taxonomy
- 结构化 blacklist_scope
- scheduler sophistication
- 回归检测显著性版本
- 真正 paper-grade holdout protocol

---

### 我更建议的现实版本
- **4 周：做 v2-lite 原型**
- **6~8 周：做可信版 v2**
- **8~12 周：做论文版实验和 ablation**

---

## 4.5 可行性结论

### 结论一句话
**4 周做“能跑的 v2 核心原型”现实；做“完整可信的 v2 full scope”明显偏乐观。**

---

## 5. 差异化：5 个结构性差异点是否足够强？能否撑住论文级 contribution？

## 5.1 你现在的差异化方向是对的

我认可你的核心定位：

> 不是优化单个候选程序生成，而是优化**研究过程本身的治理结构**。

这比很多“多几个 agent 对话”的说法要扎实得多。

---

## 5.2 5 个差异点里，强弱不均

### 最强的 3 个差异点
#### （1）显式分支治理（explore → validate → promote）
这是很强的结构差异。

#### （2）验证分离（frozen code + fresh cases）
这个方向对“防 adaptive overfitting”很重要。

#### （3）统计门槛不是点估计
这也是正确的方向，至少比 keep/revert 靠感觉强很多。

---

### 相对弱一些的 2 个差异点
#### （4）显式 HypothesisRecord
这个更像**提高可审计性和可复盘性**，是有价值的，但单独拿出来不一定构成论文级 novelty。

#### （5）Failure Taxonomy + blacklist
这是好的工程治理，但 reviewer 很可能会问：
- 它是否真正提高了最终质量？
- 还是只是日志更整齐？

如果没有 ablation，容易被当成“合理工程实践”，而非 scientific contribution。

---

## 5.3 当前差异化最大的隐患：**你最强的那个点还不在 v0.1**
你前面自己说了：

> **Agent + 参数搜索两层嵌套是差异化点（v0.2）**

问题就在这里：

- 这确实是一个很强的结构差异点
- 但它**不在当前 v0.1 scope 里**

这会导致一个论文层面的尴尬：

> 你口头上的“最强 differentiator”，在本版系统里其实还没实现。

所以如果现在就写论文，最好不要把“结构 + 参数双层搜索”当作 v0.1 的核心贡献去讲；不然 reviewer 会抓这一点。

---

## 5.4 论文级 contribution 是否足够？

### 我的判断
**现在足够撑一个“方法论/系统型 workshop 或偏 systems 的论文故事”，但还不够稳地撑住顶会/顶刊主贡献。**

原因不是你方向不行，而是：

- 当前差异点多数还是“设计型主张”
- 还缺“这些机制在固定预算下确实降低错误晋升、提高可复现性、提高搜到改进的概率”的硬证据

---

## 5.5 差异化要怎么强化成论文贡献？

你需要把“结构差异”改写成“可验证 claim”。

例如：

### Claim 1
与单强 LLM + keep/discard 相比，  
**本框架在相同计算预算下能显著降低 false promotion rate**

### Claim 2
与无 contract / 无 verification 的代理相比，  
**本框架能显著降低 infeasible / invalid candidate 比例**

### Claim 3
与无 validation split 的方案相比，  
**本框架能在重复 campaign 中给出更稳定、可复现的 improvement**

### Claim 4
HypothesisRecord / Failure Taxonomy  
**不是为了好看，而是能提高 search efficiency / 降低重复试错率**

只有这样，5 个差异点才能从“设计理念”变成“论文贡献”。

---

## 5.6 差异化结论

### 结论一句话
**5 个结构性差异点方向是对的，但当前还不足以“自动撑住论文级 contribution”；需要更强的实证证明，且最强差异点（参数层）尚未进入 v0.1。**

---

## 6. Top-3 仍存在的风险：v2 引入了哪些新问题？

这里我给两个版本：

- **版本 A：总体 Top-3 风险**
- **版本 B：v2 新引入 / 放大的问题**

---

## 6.1 总体 Top-3 风险（含未完全解决 + 新引入）

### 风险 1：**自适应搜索下的统计偏差，仍可能导致错误晋升**
**性质：v1 遗留，v2 只部分缓解**

#### 为什么仍严重
- `N>=6 + 2/3` 证据太弱
- 多分支、多轮尝试会放大偶然优胜
- 如果 validate 结果会影响后续搜索，它就不是纯 holdout

#### 直接后果
- 错把噪声当 improvement
- 论文结果重复不出来
- champion 演化被 lucky run 带偏

---

### 风险 2：**Contract 很强，但 Verification 和 Sandbox 还不够，仍可能出现语义绕过**
**性质：v1 遗留，v2 仍未彻底解决**

#### 为什么危险
- 小 patch 也能做大破坏
- 文件白名单不能防止共享 utility 被语义污染
- benchmark harness 不可改，不等于 objective / data loader / RNG 没被间接影响

#### 直接后果
- 实验信号被污染
- improvement 是“改题”不是“改算法”

---

### 风险 3：**治理机制本身开始“过强”，可能把搜索压成局部爬山**
**性质：v2 新引入/放大的问题**

#### 具体表现
- patch size limit
- max 3 commits
- max 3 active branches
- whitelist
- blacklist_scope

这些限制能提升安全，但也可能产生新问题：

- 有价值但较大的结构性改动被过早挡掉
- 系统越来越偏向安全的小修小补
- 最终你得到的是“高质量 ablation 工厂”，而不是“真正有新意的搜索系统”

这也是你后附“同行批评”里最容易被人抓住的一点。

---

## 6.2 v2 新引入 / 放大的 3 个问题

### 新问题 A：**合同层与 blacklist 可能引入错误先验固化**
一旦早期错误地把某个 change_locus 标成无效，后续可能被 blacklist 压制，导致：

- 错误经验沉淀
- 局部最优锁死
- 多样性下降

#### 建议
blacklist 不要硬编码成 local/global 二值，改成：
- `scope_conditions`
- `evidence_count`
- `expiry / reevaluation trigger`

---

### 新问题 B：**系统复杂度上升，吞吐量和可调试性下降**
v2 加入更多治理层之后，实际可能出现：

- 每轮通过率下降
- 每轮调试时间变长
- 出问题时很难定位是在 prompt、contract、verify、protocol 还是 scheduler

#### 建议
从一开始就做：
- replay mode
- decision trace viewer
- per-stage failure counters
- golden path 测试

---

### 新问题 C：**Failure Taxonomy 混合不同维度，后续会造成决策混乱**
当前 taxonomy 把这些混在一起了：

- 合约/接口错误
- 运行时错误
- 基础设施错误
- 实验表现差
- 假设无效

这几类东西的“惩罚方式”“是否计入 branch budget”“是否应反馈给 LLM”都不同。

#### 建议
拆成三层 taxonomy：

1. **ExecutionFailure**
2. **InfraIncident**
3. **EvaluationOutcome**

不要混成一个 Enum。

---

## 6.3 风险结论

### 我认为最需要盯住的 Top-3
1. **统计可信性不足**
2. **语义级绕过/验证不足**
3. **过强治理导致搜索收缩和错误固化**

---

## 7. 学术价值：发顶会/顶刊论文还缺什么？ablation 设计、实验要求？

## 7.1 先给判断

### 当前状态
**有论文潜力，但还不够“顶会/顶刊 ready”。**

### 主要原因
你现在更像是在提出一套**很有判断力的系统方法论**，  
但论文要的不只是“设计合理”，还要证明：

1. 这些设计是必要的  
2. 这些设计在固定预算下有效  
3. 这些设计提升的不只是最终分数，还有“研究过程质量”

---

## 7.2 发论文还缺什么？

## （1）缺**正式 problem statement**
你现在有很多设计原则，但还缺一个更数学化 / protocol 化的定义：

- 搜索对象是什么
- 决策单位是什么
- 什么算 promotion
- 哪些变量是 stochastic
- 哪些信息是可见/不可见
- 结论的统计目标是什么（improvement? false discovery control? campaign success probability?）

这在 paper 里很重要。

---

## （2）缺**跨 campaign 重复实验**
这是很多 agent 论文会忽略的一点，但你这个题目里尤其重要。

因为系统的随机性不只有 solver seed，还有：
- LLM sampling
- branch path
- scheduling order
- case sampling

所以不能只重复 solver run，**还要重复完整 research campaign**。

### 建议
每个 benchmark/problem 至少：
- **5~10 个独立 campaign seed**
- 每个 campaign 在同样计算预算下运行
- 汇报：
  - best improvement
  - median improvement
  - success rate
  - time-to-first-valid-improvement
  - false promotion rate

这是 reviewer 会很在意的。

---

## （3）缺**更强的 baseline**
至少需要这些对照：

### 基线 A：Single strong LLM + 同样 verification/protocol
验证收益是不是来自“多层治理”，不是单纯来自更强模型或更多 token。

### 基线 B：去掉 Contract Layer
看越界和污染问题是否显著上升。

### 基线 C：去掉 Verification Gate
看无效 improvement、不可行解、错误 objective 是否显著增加。

### 基线 D：去掉 validation split / frozen holdout
看 false discovery 是否上升。

### 基线 E：Greedy keep/discard hill-climbing
直接对比 Karpathy 风格。

### 基线 F：人类工程师同预算
如果你真想打“科研治理”的牌，这个 baseline 非常有价值。

---

## （4）缺**多任务 / 多问题族验证**
如果只在“VRP destroy operator”一个点上验证，  
论文容易被认为是 case study。

### 更稳的方案
至少覆盖：
- 2~3 类 OR 任务，或
- 同一任务上 2~3 种 solver component（destroy / repair / acceptance）

否则“框架贡献”的外推性不足。

---

## （5）缺**过程指标**
你的贡献不是单纯“最后找到更好的算子”，  
而是“研究过程治理”。

所以论文里必须有过程指标：

- valid candidate rate
- contract failure rate
- verification failure rate
- false promotion rate
- promotion precision
- compute-to-improvement ratio
- auditability / replay success rate
- duplicate hypothesis rate
- branch diversity / collapse rate

没有这些，5 个差异点无法落地成 evidence。

---

## 7.3 建议的 ablation 设计

我建议至少做以下 ablation：

| Ablation | 目的 |
|---|---|
| Full system | 主系统 |
| - Contract Layer | 验证边界约束的必要性 |
| - Verification Gate | 验证语义正确性检查的必要性 |
| - Paired Evaluation | 验证噪声控制贡献 |
| - Validation split / holdout | 验证反过拟合贡献 |
| - HypothesisRecord | 验证结构化记忆是否真正提高效率 |
| - Branch Controller | 验证分支治理是否优于单线爬山 |
| Single strong LLM baseline | 验证收益不是仅来自模型能力 |

---

## 7.4 最建议补的一类实验：**“协议本身”的合成实验**
这是我非常推荐的做法。

### 做法
构造一个**已知真实优劣关系**的 synthetic / semi-synthetic 环境：
- 候选 improvement 的真实效应是已知的
- 加入可控噪声
- 比较不同协议：
  - keep/discard
  - 你的 gate
  - 无 paired
  - 无 holdout

### 作用
这样你可以直接证明：
- false promotion rate
- false rejection rate
- sample efficiency
- stability

这会极大增强论文说服力。

---

## 7.5 学术价值结论

### 结论一句话
**当前 v2 更像“有论文潜力的方法蓝图”，还不是“顶会/顶刊可直接投稿的完整研究系统”。**

### 缺的核心不是“再多几个 agent”
而是：
1. **协议更硬**
2. **验证更语义化**
3. **实验更系统**
4. **campaign 级证据更充分**

---

# 四、最需要改进的 Top-3（优先级最高）

这是我认为你下一版最值得投入的三件事。

## Top-1：把 **Verification Gate** 升成一等组件
### 为什么最重要
因为它决定你优化的是不是**同一个问题**。  
没有 semantic verification，再漂亮的 experiment protocol 都可能建立在脏信号上。

### 最低应包含
- import / syntax
- interface compliance
- unit tests
- feasibility oracle
- objective recomputation
- no state leak
- wall-clock / memory guard

---

## Top-2：把实验协议从“二阶段”升级为“三级 split + seed ledger + 暴露控制”
### 为什么重要
这决定你能不能对 reviewer 说：
> “我们不是在 validation 上反复调到过拟合。”

### 最低要补
- screening / dev / frozen 三层
- 每层 seed bank 固定
- validate 只暴露 aggregate
- frozen 使用上限
- unclear 时只允许扩样，不允许自由 retry

---

## Top-3：把三层控制模型从“概念隔离”升级为“输入权限隔离”
### 为什么重要
因为现在 LLM 仍可能通过 `confidence / summary / improvement_axes` 影响调度和决策。

### 最低要补
- Decision Layer 不读 LLM 自由文本
- 所有 decision-relevant 字段必须是枚举或数值
- LLM confidence 只存档，不参与决策
- novelty / failure_mode / change_locus 做强类型化

---

# 五、文档质量、逻辑性、准确性、表达清晰度审核

这一部分从“内容审核专家”的角度给你更偏文档本身的意见。

---

## 5.1 内容质量：**高于平均水平，且明显克制**
这份文档整体质量是高的，尤其体现在：

- 不贩卖“通用 AI 科学家”幻觉
- 明确承认约束
- 明确做/不做边界
- 有版本演化逻辑
- 有比较强的工程可执行意识

这点比很多 agent 方案成熟很多。

---

## 5.2 逻辑性：**主线清楚，但有几处概念层级混杂**

### 优点
- 从 v1 → v2 的修正路径清晰
- “方法论是内核，agent 是执行器”这个定位很稳
- 结构上从原则 → 架构 → 模块 → scope → 计划 → 差异化，层次很顺

### 主要逻辑混杂点
#### （1）Contract vs Verification 没完全拆开
这是最重要的概念混杂。

#### （2）v0.1 / v2 / Multi-Agent v2 / engineering v1 版本命名容易混淆
建议你加一个版本关系表，例如：

| 名称 | 类型 | 当前版本 | 说明 |
|---|---|---|---|
| 方法论 | Methodology | v2 | 实验治理原则 |
| 框架蓝图 | Framework Blueprint | v0.1 / Blueprint v2 | 当前实现蓝图 |
| 工程架构 | Production Architecture | v1.0 | 生产化方案 |

#### （3）“validate”与“frozen”的术语不够统一
你有时在说：
- frozen code
- frozen holdout
- validate fresh cases

但这三者不是同一个“冻结”。

建议明确区分：
- **code frozen**
- **validation split**
- **frozen holdout**

---

## 5.3 准确性：有一些需要补正的点

### （1）Promotion Gate 的代码与“单目标 higher/lower is better 可配”不一致
你 scope 里说支持 higher/lower 可配，  
但 `promotion_gate` 代码默认 `e - c > 0` 才是 win。

#### 建议
加入：
- `direction`
- `epsilon_tie`
- `metric_transform`

---

### （2）伪代码里有一些实现级不严谨
例如：

#### `run_paired_evaluation`
`results.append(...)` 前没有初始化 `results`

#### `validate_code_patch`
`diff_lines` 没有定义来源  
`_check_file_whitelist(new_code)` 也不足以从单个 new_code 判断 touched files

这不算大问题，但如果文档要更“spec 化”，建议让伪代码更严谨。

---

### （3）`same seed = paired` 的表述容易被误读为严格 CRN
这个建议在文档里澄清。

---

## 5.4 表达清晰度：总体好，但建议更“规范化”
建议你在文档中加入几个表：

### 建议新增表 1：组件职责边界表
| 组件 | 解决什么问题 | 不解决什么问题 |
|---|---|---|

### 建议新增表 2：各层可读写权限矩阵
| 字段 | LLM 可写 | Contract 可写 | Verification 可写 | Decision 可读 |
|---|---|---|---|---|

### 建议新增表 3：实验协议暴露矩阵
| 信息 | Screening | Validation | Frozen |
|---|---|---|---|

这样 reviewer 会更容易信服“你不是口头上有边界，而是真的画清了边界”。

---

# 六、最终结论

## 最终判断

### v2 是否真正解决了 v1 的问题？
**答：解决了大半，但还没有“彻底解决”。**  
它已经补上了主要骨架，但还缺几个关键的协议级硬化点。

### v2 是否引入了新问题？
**答：有。**  
主要是：
- 治理机制变强后，搜索空间可能被压窄
- blacklist / taxonomy 可能固化错误先验
- 系统复杂度上升，吞吐量和调试难度增加

### 最需要改进的 top-3
1. **Verification Gate 一等化**
2. **实验协议升级为三级 split + seed ledger + 暴露控制**
3. **Decision 输入白名单化，彻底封堵 LLM 文本影响决策**

---

## 最后一句话总结

> **这是一份质量很高、比绝大多数“自动科研”叙事更严肃的蓝图。**  
> 但它目前更像“可信自动研究系统的正确方向”，还不是“已经足以支撑强研究结论的完整协议”。  
> 如果你下一步把**语义验证、反泄漏协议、决策输入隔离**这三件事补硬，v2 的说服力会明显上一个台阶。

如果你愿意，我下一步可以继续帮你做两件更具体的事之一：

1. **把这份审核意见转成一个“v2.1 修订清单（按优先级和实现成本排序）”**  
2. **直接替你重写一版更论文化的 v2 蓝图结构**（含组件图、权限矩阵、实验协议表、ablation 章节）
