# Scion 术语表 — 名词与语义对照

*为了让架构文档更易读，本文将 Scion 中的专业术语用一句话解释清楚。*

---

## 顶层概念

| 术语 | 一句话含义 |
|------|-----------|
| **Scion** | 整个框架的名字。取自园艺"嫁接枝"，意思是在已有求解器上嫁接新能力 |
| **Surrogate Solver** | 被优化的对象——你的仓配协同 VNS 求解器。Scion 不跑它的逻辑，只修改它的算子文件 |
| **Campaign** | 一次完整的自动优化运行。类似"一轮实验"，从初始化到终止条件触发 |
| **Champion** | 当前最优的算子组合（"擂主"）。所有新候选都要跟它比 |

## 分支与探索

| 术语 | 一句话含义 |
|------|-----------|
| **Branch** | 一条探索路线。每个分支代表一个"试试这个改法"的假设链 |
| **EXPLORE** | 分支正在做 Screening 阶段的尝试（初筛） |
| **EXPLORE_EXPAND** | Screening 结果模糊（不够好也不够差），需要多跑几个 case 再看 |
| **STALE** | Champion 更新后，这个分支的基线已经过时了，需要 reconcile |
| **Reconcile** | 把 STALE 分支的改动重新应用到新 Champion 上，看是否还能跑通 |

## 提案与生成

| 术语 | 一句话含义 |
|------|-----------|
| **Round 1 (Hypothesis)** | LLM 先生成"我打算改什么、为什么"的结构化假设 |
| **Round 2 (Code)** | LLM 根据假设生成具体的代码补丁 |
| **Creative Layer** | 负责调用 LLM 生成假设和代码的模块。"Creative"是因为它是唯一允许自由发挥的层 |
| **Tainted** | LLM 的输出被标记为"不可信的"（tainted），必须经过 Gate 校验后才能用 |
| **Proposal** | LLM 的提案（假设或代码），统称 |

## 双闸门（安全屏障）

| 术语 | 一句话含义 |
|------|-----------|
| **Contract Gate** | 第一道关卡——纯静态检查（不执行代码）。检查文件白名单、接口签名、import 限制等 |
| **C1-C10** | Contract Gate 的 10 项检查项编号（C1=Schema, C4=文件白名单, C9=敏感API拦截 等） |
| **Verification Gate** | 第二道关卡——动态检查（实际跑代码）。包括单元测试、可行性验证、状态泄漏检测等 |
| **Light failure** | 轻度失败（语法错误等），可以让 LLM 尝试修复 |
| **Heavy failure** | 重度失败（可行性被破坏等），直接丢弃，不给修复机会 |

## 实验协议

| 术语 | 一句话含义 |
|------|-----------|
| **Canary** | 金丝雀测试——在正式实验前，用最少的 case 快速检测候选是否会崩溃或产出不可行解。只有否决权 |
| **Screening** | 初筛——用少量 case 快速判断候选是否有提升潜力 |
| **Validation** | 验证——用更多 case + 统计检验确认 Screening 的结论是否可靠 |
| **Frozen Holdout** | 最终考试——用从未见过的保留集做最终判定，防止过拟合 |
| **A/B 评估** | 候选 vs Champion 的配对比较。同 instance、同 seed，只换算子池 |
| **Split Manifest** | 把测试实例分成三组（screening / validation / frozen），互不相交 |
| **Seed Ledger** | 每个阶段使用的固定随机种子列表，保证可复现 |

## 统计与决策

| 术语 | 一句话含义 |
|------|-----------|
| **Win Rate (wr)** | 候选赢 Champion 的比例（赢 = 字典序更优）。详见 [`metrics-guide.md`](metrics-guide.md) |
| **Median Delta (md)** | 候选相对 Champion 的中位改善量。详见 [`metrics-guide.md`](metrics-guide.md) |
| **Bootstrap CI** | 用 bootstrap 方法计算的置信区间，判断改善是否统计显著 |
| **Lexicographic Compare** | 字典序比较——先比第一目标（业务聚合），相同再比第二目标（成本） |
| **DecisionFeatures** | 送给决策引擎的"成绩单"——只含数字和枚举，**绝对不含**自由文本 |
| **Decision Input Guard** | 运行时校验 DecisionFeatures 是否真的没有自由文本混入（框架安全红线） |
| **Decision Engine** | 纯确定性决策器——输入 DecisionFeatures，输出 promote / abandon / continue 等 |

## 决策枚举

| Decision | 含义 |
|----------|------|
| **CONTINUE_EXPLORE** | 初筛没过，丢弃当前代码，重新从 Round 1 开始提案 |
| **EXPAND_SCREENING** | 初筛结果模糊，多跑几个 case 再判断 |
| **QUEUE_VALIDATE** | 初筛通过，排队进入 Validation |
| **EXPAND_VALIDATION** | Validation 结果模糊，扩大样本 |
| **QUEUE_FROZEN** | Validation 通过，排队进入 Frozen Holdout |
| **PROMOTE** | 全部通过，升级为新 Champion |
| **ABANDON** | 放弃这条分支 |

## 调度与终止

| 术语 | 一句话含义 |
|------|-----------|
| **Scheduler** | 每一步选哪个分支来处理。优先级：Frozen > Validate > Stale > Explore > 创建新分支 |
| **Termination** | Campaign 停止条件：实验次数达上限 / 时间耗尽 / 连续 N 个分支全失败 / 无分支可跑 |
| **Stagnation** | 连续多个分支被 ABANDON（"停滞"），说明当前搜索方向可能枯竭 |

## 失败处理

| 术语 | 一句话含义 |
|------|-----------|
| **Failure Router** | 失败分类器——根据失败类型决定是重试、丢弃还是放弃 |
| **retry_llm** | 让 LLM 重新生成（不消耗预算） |
| **retry_infra** | 基础设施故障（超时、内存溢出），重试不消耗预算 |
| **discard** | 丢弃当前提案（可能消耗预算），记入 blacklist |

## 基础设施

| 术语 | 一句话含义 |
|------|-----------|
| **Runner** | 在隔离子进程中执行 solver 的组件。净化环境变量，限制 CPU/内存 |
| **Workspace Materializer** | 管理分支的文件系统目录——复制代码、应用补丁、创建快照、清理 |
| **Pool Manager** | 管理算子池——添加/删除/修改算子，归一化权重，导出 registry.yaml |
| **Lineage Registry** | 血缘追踪——用 SQLite 记录每一步的实验事件，供审计和回溯 |

## 暴露控制（信息隔离）

| 术语 | 一句话含义 |
|------|-----------|
| **Exposure Control** | LLM 不应该看到所有信息。Round 1 能看 champion 代码和历史，Round 2 只能看假设和接口规范 |
| **Context Manager** | 按暴露矩阵构建 LLM 输入上下文的模块。validation/frozen 数据**永远不**暴露给 LLM |
| **Hypothesis Memory/Log View** | Creative Layer 的 proposal memory 和 research log 默认只渲染 screening-derived summary；promotion path/count/champion evolution/promoted hypothesis text 以及 validation/frozen aggregate、gate outcome、case feedback、pair feedback 只保留在 evidence/lineage/audit，不进入 hypothesis prompt |

---

*本文档不替代架构文档，只帮助快速建立术语直觉。详细设计请看 `../../design/scion-architecture-v3.md` 和 `../../design/archive/v0.1/scion-engineering-arch-v1.md`。*
