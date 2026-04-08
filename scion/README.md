# Scion: OR × LLM 算法自动改进框架

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 239 passed](https://img.shields.io/badge/tests-239%20passed-brightgreen.svg)](#)

**Scion**（分支/嫁接）是一个面向组合优化问题的 **LLM 驱动算法自动改进框架**。它通过 LLM 的先验知识与推理能力，在人类定义的"算法沙盒"内自主探索、验证并迭代启发式算子。

## 核心理念

与传统的纯进化算法不同，Scion 强调 **"推理驱动"** 而非随机变异：

- **LLM 作为推理主体**：利用 LLM 对业务逻辑的理解，提出改进假设（Hypothesis），而不仅仅是随机修改代码
- **严格的实验协议**：三级过滤机制（Screening → Validation → Frozen Holdout）控制过拟合风险
- **契约式治理**：通过静态 Contract Gate 与动态 Verification Gate 强制约束算法边界，抑制 LLM 幻觉

## v0.1 实验结果

以**仓配协同 VNS**（Vehicle Routing with Subcategory Consolidation）为目标问题，Scion v0.1 完成了完整的闭环实验验证：

### 实验配置

| 项目 | 配置 |
|------|------|
| LLM 模型 | Claude Opus 4 |
| 实例规模 | 54–675 orders（22 个 benchmark 实例） |
| 实验协议 | Screening(20 pairs) → Validation(18) → Frozen(12) |
| 总时间 | 59.4 分钟（15 rounds） |
| LLM API 调用 | 20 次 (10 × R1+R2) |

### 关键结果

> 📊 指标详解：如何理解 Win Rate 和 Median Delta，参见 [`docs/metrics-guide.md`](docs/metrics-guide.md)

🏆 **成功晋升 1 个新算子**（SubcatMergeSafe），通过完整三级验证：

| Stage | Win Rate | Median Δ | Evaluations |
|-------|----------|----------|-------------|
| Screening | **95%** (19W/1L) | 750,000 | 20 pairs |
| Validation | **100%** (18W/0L) | 2,200,000 | 18 pairs |
| Frozen Holdout | **100%** (12W/0L) | **5,150,000** | 12 pairs |

> Frozen Holdout 在 349–675 orders 的超大规模实例上全部 win，splits 减少 50–58 个（~27–32%），
> delta 在 4.5M–6.1M 范围内。实例越大，改善越显著——这是结构性改进的标志。

### Gate 过滤效果

Scion 的多级 Gate 体系有效过滤了 LLM 幻觉：

- 15 rounds 共生成 **10 个算子**
- 其中 **6 个**（60%）被 Verification Gate 拦截（V5_state_leak：代码修改了输入解的状态）
- **3 个**通过验证但在 Screening/Validation 被统计检验拒绝
- 仅 **1 个** 通过全部三级验证并晋升为 Champion

### LLM 学习轨迹

框架展示了 LLM 从失败中学习的能力：

1. **Round 1-3**：LLM 连续 3 次生成的代码都有 state leak 问题
2. **Round 4**：LLM 总结前 3 次失败教训，在 hypothesis 中明确写出 "the KEY difference from the 3 failed attempts: deep_copy() immediately, build ALL new data structures from scratch"，成功通过验证
3. **Round 5-10**：在新 Champion 基础上，LLM 尝试更精细的 order-level 算子（purify vehicle、cross-subcat swap），但改善幅度更小，统计上不够显著 → 正确被 Validation Gate 拒绝

### 可视化

<details>
<summary>📊 展开查看实验图表</summary>

#### Campaign 分支时间线
![Campaign Timeline](docs/figures/fig1_campaign_timeline.png)

#### 各分支累积胜率演化
![Win Rate Progression](docs/figures/fig2_promotion_gate.png)

#### Branch 1 (Promoted) 逐实例表现
![Instance Detail](docs/figures/fig3_split_reduction.png)

#### 从假设到 Champion 的漏斗
![Gate Funnel](docs/figures/fig5_gate_funnel.png)

</details>

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Campaign Manager                         │
│  (Branch lifecycle, round scheduling, budget control)       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐│
│  │ Creative │   │ Contract │   │  Verify  │   │Decision ││
│  │  Layer   │──>│   Gate   │──>│   Gate   │──>│  Layer  ││
│  │  (LLM)   │   │ (Static) │   │(Dynamic) │   │(Oracle) ││
│  └──────────┘   └──────────┘   └──────────┘   └─────────┘│
│       │                                            │       │
│       │         ┌──────────────────┐               │       │
│       └────────>│  Experiment      │<──────────────┘       │
│                 │  Protocol        │                        │
│                 │  (3-stage eval)  │                        │
│                 └──────────────────┘                        │
├─────────────────────────────────────────────────────────────┤
│  Lineage (SQLite) │ Runtime (subprocess) │ Config (Pydantic)│
└─────────────────────────────────────────────────────────────┘
```

### 分层控制

1. **Creative Layer (LLM, Tainted)**：负责 Hypothesis 提出与代码生成
2. **Gate Layer (Static & Dynamic)**：负责语法检查、契约校验（C1-C10）与 state leak 验证
3. **Protocol Layer (Statistical)**：执行三级实验协议，计算统计显著性
4. **Decision Layer (Oracle)**：根据字典序多目标评价体系，决定分支的命运

### 关键设计决策

- **Decision Input Guard**：Decision Layer 仅接收数值化的 DecisionFeatures，屏蔽 LLM 的文本干扰
- **两轮 Proposal**：Round 1 生成 Hypothesis（假设），Round 2 生成 Code（实现）
- **分支内迭代演化**：方案在分支内迭代，不是每次从 champion 重新分叉
- **Champion 是池级别**：不是单个算子，而是整个 operator pool 的快照
- **字典序多目标**：业务聚合（subcategory splits）> 成本（total cost）> 效率（solve time）

## 快速开始

### 安装

```bash
git clone https://github.com/xiaojiyao777/or-autoresearch-agent.git
cd or-autoresearch-agent/scion
pip install -e .
```

### 运行 Campaign

```bash
# Mock campaign (无需 LLM API)
python run_mock_campaign.py 5

# Full campaign with real LLM (需要 aihubmix/Anthropic API key)
export ANTHROPIC_AUTH_TOKEN="your-api-key"
python run_v3_campaign.py 15
```

### 运行测试

```bash
cd scion
python -m pytest scion/tests/ -q
# 239 passed
```

## 项目结构

```
scion/
├── scion/                    # 核心框架
│   ├── core/                 # Campaign, Branch, Decision, Scheduler, Termination
│   ├── config/               # ProblemSpec, ProtocolConfig, SplitManifest (Pydantic v2)
│   ├── contract/             # ContractGate (C1-C10 静态检查)
│   ├── verification/         # VerificationGate (V5 state leak 等动态检查)
│   ├── protocol/             # ExperimentProtocol (三级实验), Evaluation (字典序)
│   ├── proposal/             # LLMClient, CreativeLayer, ContextManager
│   ├── runtime/              # SubprocessRunner, WorkspaceMaterializer, PoolManager
│   ├── failure/              # FailureRouter (四层分类)
│   ├── lineage/              # SQLite Registry, BranchStore, ChampionStore
│   └── tests/                # 239 tests
├── problems/                 # 问题配置 (YAML)
│   └── warehouse_delivery/   # 仓配协同 VNS 配置
├── docs/                     # 实验文档与可视化
│   └── figures/              # 实验结果图表
├── design/                   # 架构设计文档
└── reviews/                  # 审核报告
```

## 目标问题：仓配协同

Scion v0.1 在**仓配协同 VNS + Solution Pool** 场景下完成验证：

- **Surrogate Solver**：针对大规模订单分配与路径规划的启发式算法（VNS + Solution Pool）
- **Operator Pool**：9 个基础算子（订单级：Move/Swap/DestroyRebuild；车辆级：Merge/Split/VehicleType）
- **目标函数**：字典序——优先确保业务齐套率（subcategory splits），其次优化物流总成本
- **Benchmark**：22 个实例（54–675 orders），覆盖 screening/validation/frozen/canary 四个角色

## 开发路线

- [x] **v0.1 MVP**：核心循环、Contract Gate、三级实验协议、SQLite Registry ✅
- [x] **v0.1.1 调优**：ContextManager 重写、prompt caching、subprocess timeout 修复 ✅
- [x] **v0.1 实验验证**：完整 15-round campaign，1 次 Champion 晋升 ✅
- [ ] **v0.2**：增强 Verification Gate（深度业务逻辑校验）、参数层搜索
- [ ] **v0.3**：引入 RAG 记忆模块，实现跨 Campaign 的经验沉淀
- [ ] **v1.0**：多问题泛化、论文实验

## 相关工作

Scion 的核心区别于传统 LLM+进化算法方法（FunSearch, EoH, ReEvo, AILS-AHD）：

| 特征 | LLM+进化算法 | Scion |
|------|-------------|-------|
| LLM 角色 | 变异算子（无记忆） | 推理主体（有记忆） |
| 搜索策略 | 随机变异 + 适应度选择 | 假设驱动 + 统计检验 |
| 安全控制 | 无/弱 | Contract Gate + Verification Gate |
| 评估方式 | 单轮 fitness | 三级实验（screening → validation → frozen） |
| 决策机制 | LLM 参与 | 纯数值 Oracle（隔离 LLM 干扰） |

## 当前状态

**v0.1 MVP + 调优完成** (2026-04-08)

- 59 个 Python 文件，9,272 行代码
- 239/239 tests passed
- 完整 15-round campaign 验证通过
- 1 次 Champion 晋升（SubcatMergeSafe），3 个 branch 被正确拒绝
- Campaign 数据：`docs/campaign_summary.json`、`docs/v3_campaign.log`

### 已知局限（v0.2 待改进）

- Verification Gate 仅检查 V5_state_leak，需增加深度业务逻辑校验
- LLM 生成多样性不足（10 个假设全部是 `create_new`，没有 `modify` 已有算子）
- V5_state_leak 失败率 60%，需在 prompt 中强化 deep copy 要求
- 缺少跨 Campaign 的经验沉淀（RAG 记忆模块）

## 开源协议

基于 MIT License 开源。

---

*Built with ⚙️ precision — Scion Framework v0.1*
