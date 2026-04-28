# 为什么做 Scion：从 LLM 写代码到 OR Autoresearch

*2026 年 4 月 · Xiao Jiyao*

---

所有人都在讨论 LLM 写代码。但 Scion 真正关心的问题是：

> 如果让 LLM 在人类定义好的组合优化算法沙盒里，持续提出假设、修改启发式算子、运行实验、保留有效改进，它能不能成为一个可信的算法研究助手？

Scion 的灵感来自 Andrej Karpathy 的 `autoresearch`：人写好研究程序和实验边界，agent 在边界内不断尝试、评估、保留或丢弃。Scion 把这个想法带到 OR 里的组合优化启发式改进，并额外加入了治理、统计验证和 lineage。

## 为什么不是普通的 LLM + 进化搜索

FunSearch、EoH、ReEvo 等方法证明了 LLM 可以生成有价值的算法片段。但很多方法把 LLM 当成 mutation operator：

1. 给一个已有程序；
2. 让 LLM 变异；
3. 跑 benchmark；
4. 选高分个体；
5. 重复。

这个范式有效，但它弱化了 LLM 最有价值的能力：推理、解释、从失败中形成假设。

Scion 选择另一条路线：**让 LLM 先提出可审计假设，再写代码**。每个候选改动都必须回答：

- 它想修复 champion 的什么弱点？
- 它改变哪个 operator family？
- 它预计改善哪个 objective？
- 它为什么不应该破坏可行性？

代码只是第二步。真正进入系统的是一条完整的“假设 -> 实现 -> 验证 -> 证据 -> 晋升/淘汰”链路。

## 核心架构

Scion 把 LLM 输出默认视为 tainted data。它不能直接决定 promotion，也不能用自然语言说服系统。

```text
Creative Layer (LLM)
  -> Hypothesis
  -> Code
  -> Contract Gate
  -> Verification Gate
  -> Screening
  -> Validation
  -> Frozen Holdout
  -> Decision Layer
  -> Champion / Abandon
```

关键约束：

- **Decision Input Guard**：决策层只读数值特征和闭集枚举，不读 LLM 自由文本。
- **Contract Gate**：限制文件、import、接口和明显复杂度风险。
- **Verification Gate**：检查可行性、objective、一致性、状态污染、非确定性和性能风险。
- **三级实验协议**：Screening 快速过滤，Validation 确认，Frozen Holdout 做未见实例终检。
- **Lineage**：hypothesis、patch、metrics、promotion、weight revision 都可追踪。

这个架构的目标不是“让 LLM 更自由”，而是先把边界做硬，再让它在边界内搜索。

## v0.3 做到了什么

v0.3 是 Scion 的第一个真正框架化里程碑。

它把研究对象从框架里拆出来：

```text
surrogate/      = 仓配协同 VNS 研究对象
scion/scion/    = 自动改进框架
```

并完成了：

- ProblemAdapter 边界；
- adapter-driven objective policy；
- synthetic / production protocol 分离；
- sync weight optimization；
- 完整 metrics lineage 和 LLM traces；
- production incomplete-evidence / timeout 修复；
- `status.json`、`campaign_summary.json`、SQLite DB 等可审计 artifact。

最终 evidence 见：

- `scion/docs/evidence-manifest.md`
- `scion/docs/v0.3-final-visual-report.md`
- `scion/docs/v0.3-production-timeout-fix-analysis.md`

核心结果：

```text
formal 12-campaign validation: 12/12 completed
synthetic: 6/6 campaigns promoted, 10 total structural promotions
production rerun after evidence/runtime fixes:
  Sonnet: 3/3 promotions
  GPT-mini: 0/3 promotions
```

最强 synthetic champion：

```text
campaign = sonnet-4-6_synthetic_seed29
final champion = v5_r0
vs v1 baseline on 47 comparable cases:
  better = 45
  equal  = 2
  worse  = 0
  median Δf1 = -17
```

production 修复后，Sonnet 产生了 3 个完整证据的 cost-improving promotion；GPT-mini 仍然 0/3，主要失败在代码可靠性和 solution consistency。

## 这些结果说明什么

v0.3 能证明：

- LLM 驱动的假设搜索可以在受控 synthetic frozen protocol 下持续改进启发式算子；
- 强模型可以在 production-style warehouse instances 上产生完整证据的 cost 改进；
- Scion 的完整闭环已经跑通：hypothesis -> code -> verification -> protocol -> promote -> weight opt -> lineage；
- governance 是必要的，不是装饰。没有 evidence completeness 和 runtime guard，production 结论会被慢算子和跳过失败 pair 污染。

v0.3 不能证明：

- Scion 已经是通用 OR autoresearch framework；
- production 成功能跨所有模型稳定复现；
- 当前 champion 接近最优；
- LLM “真正理解”了问题，而不是在统计协议下持续做对；
- Scion 能直接打败专门的 SOTA OR solver。

这些边界很重要。Scion 的目标不是提前宣称成功，而是把每一步 claim 都绑到可审计证据上。

## v0.4 为什么转向 CVRP

早期路线考虑用 FCMCNF + Benders 作为第二问题。它仍然有价值，尤其适合验证 lower bound、optimum gap 和 decomposition-aware adapter。

但 v0.4 会优先接 **CVRP**。

原因很直接：

- CVRP 是最标准的组合优化问题之一；
- benchmark 和经典方法成熟；
- 它是真正的 routing 问题，而当前 warehouse 是 assignment/bin-packing 问题；
- 它能测试 route sequence、distance objective、capacity feasibility 和 route-local operators；
- 它天然会暴露 runtime complexity 问题，正好对应 v0.4 的 performance-aware hardening。

换句话说，CVRP 是更好的下一步泛化测试：

```text
warehouse delivery: orders -> vehicles
CVRP: customers -> ordered routes
```

如果 Scion 能在一个强 CVRP baseline 上跑通同样的假设、验证、晋升和 runtime-aware protocol，它才真正开始接近 OR autoresearch framework。

## 接下来

v0.4 的目标：

- performance-aware promotion；
- complete-evidence gate；
- CVRP ProblemAdapter；
- CVRP baseline evidence manifest；
- final quality/runtime harness；
- warehouse + CVRP 统一报告口径。

v1.0 的目标：

- warehouse + CVRP 双问题证据固化；
- 机制消融；
- 更强的 campaign 运维；
- 文档和接口稳定化。

Scion 现在还不是“通用 OR 自动研究框架”。更准确地说，它已经是一个在 warehouse delivery 上验证过的、可审计的 agentic algorithm optimization framework，并正在用 CVRP 迈向多问题泛化。

这正是项目当前最有价值的位置。
