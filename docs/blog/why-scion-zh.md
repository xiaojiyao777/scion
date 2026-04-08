# 为什么做 Scion：重新思考 LLM 如何改进优化算法

*2026 年 4 月 · Xiao Jiyao*

---

所有人都在讨论 LLM 写代码。但如果让它**设计更好的算法**呢？

这是 Scion 背后的问题 —— 一个用 LLM 推理能力自动改进组合优化启发式算子的框架。这篇文章解释动机、Scion 和现有方法的本质区别，以及 v0.1 实验中我们学到的东西。

## 现有方法的根本问题

过去两年，LLM + 优化算法方向涌现了大量工作。Google 的 FunSearch、Evolution of Heuristics (EoH)、ReEvo、AILS-AHD —— 都共享一个类似的范式：

1. 给 LLM 一个已有的启发式算法
2. 让它变异或重写
3. 在 benchmark 上评估
4. 选最好的，重复

本质上是**进化搜索，LLM 充当变异算子**。效果不错 —— FunSearch 在 cap set 问题上找到了新构造，EoH 发现了有竞争力的装箱启发式。但有一个根本性局限：

**LLM 被当作随机代码生成器，而不是推理主体。**

它没有记忆：不记得之前尝试过什么。它不形成假设：不推理*为什么*某个改动可能有效。它不从失败中学习：每一代本质上是独立的。LLM 最强大的推理能力，在这个范式下被浪费了。

还有一个更实际的问题：**没有人认真讨论安全性**。当 LLM 生成的代码运行在处理真实物流、制造、排程的求解器中，一个隐蔽的 bug 可以在无人注意的情况下腐蚀解的质量 —— 状态篡改、约束违反、目标函数的微妙变化。程序不会崩溃，只是悄悄给出错误答案。

## Scion 的路线

Scion 走了一条不同的路。三个核心思想：

### 1. 假设驱动的搜索

不是"这是代码，改好一点"，Scion 要求 LLM 先阐述一个**假设** —— 结构化地说明*要改什么*以及*为什么期望改善*：

```
Round 1（假设）：
"当前 merge_vehicles 算子只考虑相邻路线的合并。
如果按主导子品类匹配来合并车辆，应该能更有效地减少 splits，
因为……"

Round 2（代码）：
[基于上述假设的实现]
```

两轮 Proposal 迫使 LLM 先推理再编码。更重要的是，当假设失败时，框架会反馈*失败了什么*和*为什么* —— 使 LLM 能跨轮次迭代理解。

### 2. 三层治理架构

Scion 将 LLM 的输出**默认视为不可信的（tainted）**。所有产出必须通过多层关卡才能影响算法池：

```
Creative Layer（LLM）      → 产出代码（tainted）
    ↓
Contract Gate（静态）       → 语法、接口、禁用 import 等（C1-C10）
    ↓
Verification Gate（动态）   → state leak 检测、约束保持验证
    ↓
Experiment Protocol         → Screening → Validation → Frozen Holdout
    ↓
Decision Layer（Oracle）    → 仅接收数值特征，不接收 LLM 文本
```

**Decision Input Guard** 尤其关键：决策层只接收数值化的 DecisionFeatures（胜率、中位差、评估次数），从不接收 LLM 的自由文本。这在架构层面防止了 LLM "用语言说服系统"做出晋升决策。

### 3. 统计严谨性 > 适应度分数

大多数 LLM + 进化方法用单一适应度分数决定存活。Scion 用三级实验协议，灵感来自临床试验：

| 阶段 | 目的 | 数据 |
|------|------|------|
| Screening | 小规模实例快速过滤 | 20 对 |
| Validation | 中等规模确认 | 18 对 |
| Frozen Holdout | 从未见过的大规模实例终检 | 12 对 |

每个阶段要求达到统计门槛（胜率 ≥ 2/3 + 中位差 ≥ 最小实际显著性）。Frozen Holdout 的实例在前两个阶段中**完全不可见**，直接解决了单适应度方法的过拟合隐患。

## v0.1 实验：我们学到了什么

目标问题是真实的仓配协同 VNS（Variable Neighborhood Search）+ 子品类齐套优化。22 个 benchmark 实例，54-675 个订单，15 轮 LLM 交互。

### LLM 的学习曲线

最有趣的发现不是最终结果 —— 而是看 LLM 如何学习：

- **Round 1-3**：LLM 连续三次生成了修改输入解状态的代码（VNS 算子的常见 bug）。全部被 Verification Gate 拦截。
- **Round 4**：LLM 的假设中明确写道：*"the KEY difference from the 3 failed attempts: deep_copy() immediately, build ALL new data structures from scratch."* 通过验证。
- **Round 4 的算子（SubcatMergeSafe）** 在 Screening 胜率 95%，Validation 100%，**Frozen Holdout 100%** —— 在大规模实例上减少 50-58 个子品类拆分。

这在无记忆的进化框架中不可能发生。LLM 在失败中积累了理解并加以应用。

### Gate 漏斗效应

10 个生成的算子中：
- 6 个（60%）被 Verification Gate 拦截（state leak）
- 3 个通过验证但未达统计显著性
- **仅 1 个**通过全部三级验证，晋升为 Champion

10% 的存活率说明两件事：LLM 富有创造力但不可靠（60% 有 bug），统计关卡不可或缺（还有 3 个看起来不错但不显著）。两个发现都验证了多层架构的必要性。

### 坦诚的局限

- 只在一个问题领域验证过 —— 泛化性未证明
- 只有 1 次成功晋升 —— 样本量小
- 没有和 FunSearch/EoH 做横向对比（v0.2 计划）
- 60% 的 V5_state_leak 失败率说明 prompt 工程还有改进空间
- 缺少跨 Campaign 记忆 —— 每次运行从零开始

## 致谢

Scion 的灵感来源于 Andrej Karpathy 的 [autoresearch](https://github.com/karpathy/autoresearch) 愿景 —— LLM 可以在人类定义好的沙盒内自主进行研究。Scion 将这个理念带入组合优化领域，并加入了形式化治理来保障生产安全性。

## 接下来

Scion v0.1 证明了**假设驱动搜索 + 治理架构**这条路是可行的。路线图：

- **v0.2**：增强 Verification Gate（深度语义检查）、参数层搜索
- **v0.3**：RAG 记忆模块，实现跨 Campaign 知识沉淀
- **v1.0**：多问题泛化、与现有方法的正式对比、论文

## 为什么现在就开源？

因为这个领域在快速发展，而**没有人在认真做治理问题**。论文不断展示"LLM 找到了更好的启发式！"，却没有回答"怎么确保它不破坏系统？"或者"怎么防止在 benchmark 上过拟合？"

Scion 对这些问题给出了明确的立场。代码是真实的（9,272 行、239 个测试、完整的 Campaign 流水线）。如果你在做 LLM 驱动的算法设计，并且关心可靠性，欢迎交流。

**仓库**：[github.com/xiaojiyao777/scion](https://github.com/xiaojiyao777/scion)

---

*Scion 是一个探索 LLM 驱动算法改进 + 形式化治理的研究项目。欢迎贡献、批评和合作。*
