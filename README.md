# Scion — LLM 驱动的组合优化算法自动改进框架

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: v0.3](https://img.shields.io/badge/version-v0.3-blue.svg)](#)

**Scion**（嫁接/分支）是一个研究项目，探索如何利用 LLM 的推理能力自动改进组合优化算法中的启发式算子。与传统的 LLM+进化算法方法不同，Scion 将 LLM 视为**推理主体**（而非随机变异算子），通过假设驱动的搜索、三级统计验证、契约式治理和参数层优化，在保证安全性的前提下实现算子自动发现与权重优化。

## 项目结构

```
.
├── scion/               # Scion Framework — 核心自动改进框架
├── surrogate/           # Surrogate Solver — 仓配协同 VNS 求解器
├── docs/blog/           # 博客文章与致谢
└── reviews/             # 架构审核报告
```

---

## v0.3 最终结果

v0.3 的目标是把 Scion 从仓配 VNS 原型推进到可审计、可扩展的工程化框架：研究对象保留在 `surrogate/`，框架能力沉淀在 `scion/scion/`，并支持 adapter-driven objective policy、production/synthetic protocol 分离、同步权重优化、完整 lineage 和实验证据。

最终验证：

```text
formal 12-campaign validation: 12/12 completed
synthetic: 6/6 campaigns promoted, 10 total structural promotions
production rerun after timeout/evidence fixes:
  Sonnet: 3/3 promotions
  GPT-mini: 0/3 promotions
```

最强一次优化来自 `sonnet-4-6_synthetic_seed29`：

```text
final champion = v5_r0
promotions = 4
best champion vs v1 baseline:
  better = 45 / 47 cases
  equal  = 2 / 47 cases
  worse  = 0 / 47 cases
  median Δf1 = -17
```

![Best Synthetic Champion Quality](scion/docs/figures/v0.3-final/04_best_synthetic_quality.png)

完整报告：

- [`scion/docs/v0.3-final-visual-report.md`](scion/docs/v0.3-final-visual-report.md)
- [`scion/docs/v0.3-final-12campaign-analysis.md`](scion/docs/v0.3-final-12campaign-analysis.md)
- [`scion/docs/v0.3-production-timeout-fix-analysis.md`](scion/docs/v0.3-production-timeout-fix-analysis.md)

v0.3 的工程结论：Scion 已经具备完整的 agentic algorithm optimization 闭环；synthetic 优化能力强，production 在强模型 Sonnet 下能得到完整证据的 cost 改进。v0.4 将继续补强 performance-aware optimization。

---

## 📐 设计理念

### 核心问题

> 如何让 LLM 在人类定义好的"算法沙盒"内，自主且可信地改进组合优化算法？

### 三个关键洞察

1. **LLM 是推理主体，不是变异算子**：FunSearch/EoH 等方法将 LLM 当作进化算法中的变异算子（无记忆、随机变异）。Scion 让 LLM 提出**有理由的假设**，基于历史失败学习，在搜索空间中做**有方向的探索**。

2. **治理先于搜索**：LLM 输出不可信（幻觉、state leak、越界）。先把安全边界做硬（Contract Gate + Verification Gate + Decision Input Guard），再放开搜索空间。

3. **两层嵌套搜索**（v0.2）：外层 LLM 搜索算子结构（发现新算子），内层算法搜索参数（优化算子权重配比）。结构决定"有什么工具"，参数决定"怎么用这些工具"。

### 认识论定位

#### 三种“理解问题”的方式

| 方式 | 理解来源 | 优势 | 代价 |
|------|----------|------|------|
| 精确算法 | 数学结构 | 最优性有数学保证 | NP-hard 问题在实际规模下通常不可解 |
| 传统启发式 | 人类直觉 | 计算可行，大规模上能找到好解 | 质量上限受工程师经验约束，改进依赖人工 |
| Scion / LLM 驱动 | 语义推理 | 能把 problem spec、业务语义、搜索动态联合起来形成可检验假设 | 没有最优性证明，只能给出统计证据 |

Scion 不是精确算法与启发式之间的折中，而是接受“复杂组合优化必须依赖启发式”这个现实之后，继续追问：

> **既然必须使用启发式，怎样才能系统化、持续地把启发式做得更好？**

它工作的不是传统的**解空间（solution space）**，而是更高一层的**算子设计空间（operator design space）**：

```text
解空间（Solution Space）
  ← 精确算法 vs 启发式算法的主战场

算子设计空间（Operator Design Space）
  ← Scion 工作的地方
```

这个视角下，Scion 与精确算法存在一个有趣的平行结构：

- **精确算法**：在指数级解空间里，用 bound + 剪枝做智能枚举
- **Scion**：在开放的算子设计空间里，用 LLM 推理 + 统计验证做智能枚举

两者都面对组合爆炸，都需要“方向感”避免盲目搜索。区别只是，前者搜索解，后者搜索算法结构。

### 为什么两轮 Proposal 很重要

Scion 的 Round 1 不是让 LLM 直接吐代码，而是先要求它把“理解”显式化成**可审计、可反驳的假设**；Round 2 才把假设落实为实现。随后再通过 Frozen Holdout 检验：

> 如果这个理解是真的，它应该能在从未见过的数据上继续成立。

因此 Scion 建立的不是一个“自动写算子”的流水线，而是一个 **LLM 推理 → 假设显式化 → 实证验证 → 保留/淘汰** 的知识生产回路。

### 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Campaign Manager                         │
│  (Branch lifecycle, round scheduling, budget control)       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Creative Layer    Contract Gate    Verification Gate       │
│  (LLM, tainted) ──> (C1-C10,     ──> (V3-V8,         ──>  │
│                      static)          dynamic)              │
│                                                             │
│  Experiment Protocol (Screening → Validation → Frozen)      │
│  Decision Layer (Oracle, numerical features only)           │
│  Weight Optimization (on promote, 25 evals)    ← v0.2 新增  │
├─────────────────────────────────────────────────────────────┤
│  Lineage (SQLite) │ Runtime (subprocess) │ Config (Pydantic)│
└─────────────────────────────────────────────────────────────┘
```

**设计原则**：

- **三层控制**：Creative（LLM, tainted）→ Gate Layer（静态+动态校验）→ Decision Layer（纯数值 Oracle）
- **Decision Input Guard**：决策层仅接收 `DecisionFeatures`（数值+枚举），彻底隔离 LLM 文本干扰
- **两轮 Proposal**：Round 1 Hypothesis（假设推理）→ Round 2 Code（代码生成）
- **三级实验协议**：Screening → Validation → Frozen Holdout，Bootstrap CI 控制过拟合
- **字典序多目标**：业务聚合（subcategory splits）> 物流成本 > 求解效率

> 📖 详细架构：[`scion/design/scion-architecture-v3.md`](scion/design/scion-architecture-v3.md)（基石设计，22 条关键决策）

---

## 🚚 目标问题：仓配协同 VNS

`surrogate/` 是 Scion 的目标问题实现：仓配协同场景下的 VNS + Solution Pool 求解器。

**问题**：给定一批订单（含子品类属性），分配到不同车型的车辆，最小化子品类拆分（同子品类订单尽量同车）并优化物流成本。

**求解器**：9 个基础算子（订单级 + 车辆级），统一接口 `execute(solution, rng) → Solution`，这是 Scion 能自动发现新算子的基础。

**Benchmark**：48 个实例（22→990 orders），覆盖合成数据 + 真实生产数据统计特征。

---

## ⚙️ Scion Framework

`scion/` 是核心框架实现，包含 campaign lifecycle、protocol gates、objective policy、lineage、runtime isolation、LLM context 和 parameter search。

| 模块 | 职责 |
|------|------|
| `core/` | Campaign 主循环、Branch 状态机、Decision Engine、Scheduler、Termination |
| `config/` | ProblemSpec、ProtocolConfig、SplitManifest、SeedLedger（Pydantic v2） |
| `contract/` | ContractGate — C1-C10 静态检查（语法、接口、import 白名单、novelty） |
| `verification/` | VerificationGate — V3-V8 动态校验（feasibility、objective、state mutation、nondeterminism） |
| `protocol/` | ExperimentProtocol — 三级实验、Case-level 统计、Bootstrap CI |
| `proposal/` | LLMClient、CreativeLayer、ContextManager、SearchMemory、SaturationSignal |
| `parameter/` | WeightOptimizer、Evaluator — 算子权重优化（v0.2 新增） |
| `runtime/` | SubprocessRunner（隔离执行）、WorkspaceMaterializer、PoolManager |
| `failure/` | FailureRouter — 四层故障分类 + escalation + infra 检测 |
| `lineage/` | SQLite Registry、BranchStore、ChampionStore、HypothesisStore |
| `cli/` | Typer CLI（init / run / inspect / report） |

> 📖 当前文档索引：[`scion/docs/README.md`](scion/docs/README.md)

---

## 与相关工作的对比

| 特征 | FunSearch / EoH / ReEvo | Scion |
|------|------------------------|-------|
| LLM 角色 | 变异算子（无记忆） | 推理主体（有记忆，假设驱动） |
| 搜索策略 | 随机变异 + 适应度选择 | 假设推理 + 统计检验 |
| 安全控制 | 无/弱 | Contract Gate + Verification Gate |
| 评估方式 | 单轮 fitness | 三级实验协议 + Bootstrap CI |
| 决策机制 | LLM 参与选择 | 纯数值 Oracle（Decision Input Guard） |
| 参数优化 | 无 | Weight Optimization（两层嵌套搜索） |

### 第三种范式

| 维度 | 精确算法 | 传统启发式 | Scion / LLM 驱动 |
|------|---------|------------|------------------|
| 理解来源 | 数学结构 | 人类直觉 | 语义推理 |
| 保证类型 | 最优性证明 | 无保证 | 统计显著性 |
| 知识形式 | 公式 | 编码直觉 | 可审计假设 |
| 可进化性 | 固定 | 靠人工迭代 | 自动持续进化 |
| 对偶 gap | 可计算 | 未知 | 未知 |

### 局限性

Scion 在 v0.3 能证明的是：**在受控 synthetic frozen-gate 验证中，LLM 驱动框架可以持续产出可泛化的算法改进；在 production 数据上，强模型可以在完整证据 gate 下取得 cost 改进。**

但它不能证明：

1. 改进一定能无缝泛化到线上生产环境，生产落地仍需要 shadow deployment / 灰度验证。
2. production 成功可以跨所有模型稳定复现；GPT-mini 的结果说明模型能力和代码可靠性仍是边界。
3. LLM “真的理解了问题”，统计证据只能说明它持续做对了，不能区分“真懂”与“碰对”。
4. 当前 champion 就是最优算子设计，开放设计空间没有穷尽证明。
5. Scion 已经泛化到第二个问题类别；这是 v1.0 的核心验证目标。

统计证据已经是这类系统里最强的可操作保证，但它不是数学证明。

---

## 🚀 快速开始

```bash
# 安装
git clone https://github.com/xiaojiyao777/scion.git
cd scion/scion && pip install -e .

# 运行测试
python -m pytest scion/scion/tests/test_protocol.py scion/scion/tests/test_contract.py -q

# 运行 Campaign
export SCION_API_KEY="your-api-key"
export SCION_MODEL="claude-opus-4-6"
cd scion
python run_validation_campaign.py --model claude-sonnet-4-6 --variant synthetic --seed 11 --max-rounds 30
```

## 开发路线

- [x] **v0.1** — MVP：核心循环、Contract Gate、三级实验协议、SQLite Lineage ✅
- [x] **v0.1.1** — 调优：ContextManager 重写、prompt caching、subprocess 修复 ✅
- [x] **v0.2** — 参数层搜索、FailureRouter 升级、Pro 审查整改、生产数据支持 ✅
- [x] **v0.3** — 框架工程化、adapter/objective 泛化、production protocol、sync weight opt、完整证据 gate ✅
- [ ] **v0.4** — Performance-aware optimization：runtime/complexity 作为公共优化维度
- [ ] **v1.0** — 多问题泛化、第二问题对象、结构级搜索

## 致谢

Scion 的灵感来源于 Andrej Karpathy 的 [autoresearch](https://github.com/karpathy/autoresearch) 愿景——LLM 可以在人类定义好的沙盒内自主进行研究。Scion 将这个理念带入组合优化领域，并加入了形式化治理（三层控制 + 三级实验协议 + Decision Input Guard）来保障研究的可信性与可追溯性。

## Blog

- [Why Scion: Rethinking How LLMs Improve Optimization Algorithms](docs/blog/why-scion-en.md) (English)
- [为什么做 Scion：重新思考 LLM 如何改进优化算法](docs/blog/why-scion-zh.md)（中文）

## License

MIT

---

*Built with precision — Scion Framework v0.3*
