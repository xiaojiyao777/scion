# Scion Framework — Architecture v3

*Date: 2026-04-02*
*Authors: BigBOSS + Cris*
*Status: Foundational Architecture — 基石设计文档*
*Lineage: v2 Blueprint → GPT-5.4-Pro Review → v2.1 Blueprint → Architecture Discussion*

---

## 0. 文档定位

本文档是 Scion 框架的**基石架构设计**。

- 不是某个版本的实现方案（v0.1 MVP 从本文档派生）
- 不是论文（但论文友好）
- 是**所有后续版本共同遵循的设计基座**

核心目标一句话：

> **面向组合优化算法的自动研究框架——让"提假设 → 改算子 → 验证 → 统计判断 → 晋升/淘汰"的过程可信、可控、可追溯。**

---

## 1. 设计原则

### 1.1 方法论是内核，agent 是执行器

框架的价值不在"用了几个 LLM"，在于：
- 分支治理
- 决策边界
- 协议可信性
- 实验可追溯

### 1.2 确定性逻辑用代码，创造性推理用 LLM

| 确定性系统负责 | LLM 负责 |
|---|---|
| Contract 检查 | 提出假设 |
| Verification 验证 | 生成代码补丁 |
| 实验协议执行 | 解释失败原因（仅存档） |
| 调度与决策 | |
| 晋升 / 淘汰 | |
| Artifact 持久化 | |

### 1.3 LLM 只能提案，不能决策

- LLM 输出全部视为 **tainted 数据**
- 必须经过 Contract → Verification → Protocol → Safe Feature Extractor 才能形成 DecisionFeatures
- Decision Layer **只允许读取 DecisionFeatures**，不读任何 LLM 自由文本

### 1.4 先把边界做硬，再考虑搜索做大

优先保证实验可信与边界明确，然后再增加搜索深度/空间/参数层。

### 1.5 人在回路但不在循环里

- 人定义问题 + 审核 oracle + 审核最终结果
- Agent 独立执行探索循环
- 人不参与每轮迭代决策

---

## 2. 目标问题域

### 2.1 Scope

面向**组合优化算法的自动改进**，特别是：
- 基于邻域搜索（VNS/ALNS 等）的求解器
- 模块化算子架构（算子可独立定义、注册、概率选择）
- 含 Solution Pool 的搜索框架

### 2.2 典型问题结构（以仓配协同为参考）

```
仓配协同优化
├── 输入：订单集合 + 车辆资源（多车型）+ 仓库约束
├── 决策：订单 → 车辆分配
├── Solution：{车辆 → [订单列表]} + 约束状态
│
├── 算子层（模块化，操作 Solution）
│   ├── 订单级：增加、移除、交换、批量移动...
│   ├── 车辆级：新增、减少、换车型...
│   └── 概率选择：累积数组，动态自适应权重
│
├── Solution Pool
│   └── 每次迭代：遍历 pool → 每个解选一个算子 → 执行 → 更新
│   └── 最终取 pool 中最优解作为评价结果
│
└── 多目标（字典序）
    └── 业务聚合约束 > 成本 > 运行时间/效率
```

### 2.3 不做

- ❌ 通用 agent 框架
- ❌ 非组合优化问题
- ❌ 没有 baseline solver 的从零设计
- ❌ 自动定义问题

---

## 3. 系统总体架构

```
Problem Spec
(problem.yaml + baseline solver + tests + benchmark instances + split_manifest)
    │
    ▼
Campaign Controller
    │
    ├── Branch Controller（状态机）
    ├── Scheduler（词典序硬优先级）
    ├── Context Manager（暴露控制）
    └── Lineage Registry（append-only）
    │
    ▼
Proposal Engine（两轮：Hypothesis → Code）
    │
    ▼
Contract Gate（结构/边界约束）
    │
    ▼
Workspace Materializer + Runtime Isolation
    │
    ▼
Verification Gate（语义正确性）
    │
    ▼
Experiment Protocol
    ├── Canary Regression Check
    ├── Screening
    ├── Validation
    └── Frozen Holdout
    │
    ▼
Safe Feature Extractor（Decision Input Guard）
    │
    ▼
Decision Engine（确定性）
    ├── keep exploring
    ├── queue validate
    ├── expand sample
    ├── promote
    └── abandon
```

### 3.1 组件职责边界表

| 组件 | 解决什么问题 | 不解决什么问题 |
|---|---|---|
| Contract Gate | patch 越界、文件污染、接口不合规、结构风险 | 语义正确性 |
| Verification Gate | 候选是否仍在解同一个问题、是否破坏约束/目标/状态 | 泛化能力、统计显著性 |
| Experiment Protocol | 候选是否可靠优于 champion | 生产业务收益 |
| Runtime Isolation | 运行污染、import/cache/state 泄漏 | 完整恶意代码安全防护 |
| Scheduler | 算力预算与分支治理 | 科学真理判断 |
| Lineage Registry | 可审计、可回放、可追溯 | 自动生成结论 |
| Proposal Engine | 创造性提案与代码生成 | 决策与资源分配 |
| Context Manager | 构造受暴露控制的 LLM 上下文 | 决策信息过滤（由 Safe Feature Extractor 负责） |

---

## 4. 控制模型：三层控制 + 双硬闸门 + 决策输入白名单

### 4.1 控制流分层

```
Layer A: Creative Layer（LLM，tainted）
  输出：HypothesisProposal / PatchProposal / FailureAnalysis
  特性：全部 tainted，不得直接驱动调度与晋升
    │
    ▼
Gate 1: Contract Gate（结构边界）
  检查：schema / 文件白名单 / patch 约束 / AST 接口 / import 白名单
    │
    ▼
Gate 2: Verification Gate（语义正确性）
  检查：syntax / interface / unit tests / feasibility / objective / state leak / wall-clock
    │
    ▼
Layer B: Decision Layer（确定性）
  只读：DecisionFeatures（数值 + 枚举，无自由文本）
```

### 4.2 Decision Input Guard

Decision Layer 的输入必须先经过 Safe Feature Extractor 转换为 DecisionFeatures。

```python
@dataclass(frozen=True)
class DecisionFeatures:
    branch_id: str
    stage: Literal["screening", "validation", "frozen"]
    contract_passed: bool
    verification_passed: bool
    canary_passed: bool

    n_cases: int
    win_rate: Optional[float]
    median_delta: Optional[float]
    ci_low: Optional[float]
    ci_high: Optional[float]

    stale: bool
    recent_retry_count: int
    recent_failure_codes: Tuple[str, ...]
    budget_remaining_ratio: float
```

**关键约束：没有任何自由文本字段。**

### 4.3 数据权限矩阵

| 数据类型 | LLM 可写 | Contract 可改写 | Verification 可写 | Protocol 可写 | Decision 可读 |
|---|:---:|:---:|:---:|:---:|:---:|
| hypothesis_text | ✅ | 仅校验 | ❌ | ❌ | ❌ |
| patch / code | ✅ | ✅ | ❌ | ❌ | ❌ |
| improvement_axes（枚举） | ✅ | ✅ | ❌ | ❌ | 可选 |
| confidence（LLM 自报） | ✅ | 可存档 | ❌ | ❌ | ❌ |
| evidence_summary | ✅ | 可过滤 | ❌ | ❌ | ❌ |
| touched_files / symbols | ✅ | ✅ | ✅ | ❌ | ✅ |
| verification_result | ❌ | ❌ | ✅ | ❌ | ✅ |
| per-case raw metrics | ❌ | ❌ | ❌ | ✅ | ❌ |
| aggregate stats | ❌ | ❌ | ❌ | ✅ | ✅ |
| pass/fail label | ❌ | ❌ | ❌ | ✅ | ✅ |

---

## 5. 两轮 Proposal 流程

### 5.1 Round 1: Hypothesis Generation

**输入上下文：**
| 信息 | 是否提供 |
|---|---|
| problem spec 摘要 | ✅ |
| champion 算子代码 | ✅ |
| 当前分支最新代码（如不同于 champion） | ✅ |
| 本分支历史结果（结构化摘要） | ✅ |
| 已失败 hypothesis 列表 | ✅ |
| 兄弟分支状态（简要） | ✅ |
| validation/frozen 细节 | ❌ |

**输出（structured JSON）：**
```python
@dataclass
class HypothesisProposal:
    hypothesis_text: str           # 自然语言描述
    change_locus: str              # 枚举：算子类型/层级
    action: str                    # "modify" | "create_new" | "remove"
    target_file: Optional[str]     # modify/remove 时指定
    predicted_direction: str       # "improve" | "tradeoff" | "exploratory"
    target_weakness: str           # 针对 champion 的哪个弱点
    expected_effect: str           # 预期效果
    suggested_weight: Optional[float]  # 新算子建议初始权重（仅 create_new）
```

→ Contract Gate: schema 校验 + change_locus 合法性 + novelty check

### 5.2 Round 2: Code Generation

**输入上下文：**
| 信息 | 是否提供 |
|---|---|
| problem spec 摘要 | ✅ |
| approved hypothesis | ✅ |
| champion 算子代码 | ✅ |
| 当前 target 文件内容 | ✅ |
| operator interface spec | ✅ |
| 本分支历史结果 | ❌ |
| 已失败 hypothesis | ❌ |
| 兄弟分支 | ❌ |

**输出（structured JSON）：**
```python
@dataclass
class PatchProposal:
    file_path: str
    action: str                    # "modify" | "create" | "delete"
    code_content: str              # 完整文件内容（框架自行做 diff）
    test_hint: Optional[str]       # tainted，仅存档，不进决策
```

→ Contract Gate: 文件白名单 + AST/接口 + import 检查
→ Materialize → Verification Gate → Protocol → Decision

---

## 6. 算子池管理

### 6.1 算子接口

所有算子共享统一接口，操作 Solution 对象：

```python
# 接口签名冻结，LLM 只能改实现
class Operator:
    def execute(self, solution: Solution, rng: Random) -> Solution
```

算子分类（由 problem spec 定义）：
- 订单级算子：增加、移除、交换、批量移动等
- 车辆级算子：新增、减少、换车型等

### 6.2 候选池管理

- **新增算子**：LLM 提供代码 + 建议权重 → 框架自动注册进池
- **修改算子**：LLM 提供新实现 → 框架替换
- **删除算子**：LLM 提议 → 框架从池中移除，概率重新归一化
- 动态自适应权重更新机制本身**冻结不动**（v0.1）

### 6.3 Champion 定义

Champion 是**池级别**，不是算子级别：

```python
@dataclass
class ChampionState:
    version: int
    operator_pool: dict[str, OperatorConfig]  # name → {file, weight, ...}
    solver_config: SolverConfig               # 冻结
    code_snapshot_hash: str
    promotion_experiment_id: str
```

Promote 一个算子变更 = promote 一个新的池配置。

### 6.4 评估方式：A/B

```
Champion Solver:  pool = {现有算子集}
Candidate Solver: pool = {现有算子集 ± 变更}
```

两者跑相同 case、相同 seed，取 pool 最优解作为单次结果，配对比较。

---

## 7. 多目标处理

### 7.1 字典序评估

目标优先级（由 problem spec 定义）：

```
Level 1: 业务聚合约束满足度（硬约束 / 软约束满足数）
Level 2: 成本
Level 3: 运行时间 / 算法效率
```

比较规则：
1. 先比 Level 1，严格更好则胜出
2. Level 1 相当（差异在容忍度内）则比 Level 2
3. 以此类推

### 7.2 对 Promotion Gate 的影响

字典序自然产出一个二元比较结果（win/loss/tie），可直接对接现有 paired evaluation 体系。

每个 `(case, seed)` 的比较结果：
```
candidate vs champion → win | loss | tie
```

聚合为 per-case 结果（跨 seed 取多数），再进入 win_rate / median_delta 计算。

对于字典序中**最主要的竞争目标**（通常是成本），计算 delta 用于 practical significance 判断。

---

## 8. 实验协议层

### 8.1 协议目标

同时解决 4 件事：
1. 噪声控制
2. 信息泄漏控制
3. 重复试探导致的错误晋升
4. 回归与安全退化检测

### 8.2 统计单位

主统计单位为 **case**。每个 case 跨 seed 聚合为 case-level delta。

### 8.3 三层 Split

| 层级 | 用途 | 可重复使用 | 暴露级别 | 默认 N_cases |
|---|---|---|---|---|
| Screening | 快速粗筛 | 是 | 完整细节 | 6（modify/remove）/ 10（create_new） |
| Validation | 正式验证 | 分支级一次性 | 仅 aggregate | 12 |
| Frozen Holdout | 最终确认 | campaign 级限量 | 仅 pass/fail + aggregate | 12~20 |

### 8.4 暴露控制

| 信息类型 | Screening | Validation | Frozen |
|---|---|---|---|
| per-case 原始结果 | 可见（LLM/人类） | 不可见 | 永不暴露 |
| subgroup breakdown | 可见 | 不可见 | 永不暴露 |
| aggregate（win_rate / delta / CI） | 可见 | 可见 | 仅 aggregate |
| pass/fail | 可见 | 可见 | 可见 |
| 结果回喂后续搜索 | 是 | 有限（aggregate） | 默认否 |

### 8.5 SplitManager + SeedLedger

固定版本化的实验集和种子管理。

```yaml
# split_manifest.yaml
version: "split-v1"
screening:
  cases: [...]
validation:
  cases: [...]
frozen:
  cases: [...]

# seed_ledger.yaml
version: "seed-v1"
screening: [11, 29]
validation: [11, 29, 47]
frozen: [11, 29, 47]
```

### 8.6 Promotion Gate（分阶段）

#### Screening Gate（粗筛）
- `win_rate >= 2/3`
- `median_delta >= δ_screen`
- 结果：pass / unclear / fail
- **明确定位：screening gate，不是 promotion 依据**

#### Validation Gate（正式验证）
- `win_rate >= 2/3`
- `median_delta >= δ_validate`
- `bootstrap_ci_low >= 0`
- 结果：pass_to_frozen / expand_sample / fail

#### Frozen Gate（最终确认）
- `bootstrap_ci_low >= 0`
- `canary_passed == True`
- 无 critical verification/runtime failure
- 结果：confirmed / rejected

### 8.7 Retry 规则

#### 允许：Infra Retry
- benchmark 基础设施故障、LLM API 故障、机器故障
- 同 case 同 seed，最多 2 次

#### 允许：Statistical Expand（不是 retry）
- 结果 unclear 时按预注册规则扩大样本
- screening: 6/10 → expand to 10/16
- validation: 12 → 20
- 不能无限刷到过阈值

#### 不允许
- 换 seed/case 重跑
- 反复刷到过门槛

### 8.8 Canary Regression Check

- 固定小型 canary set
- 只做 veto，不做改善证据
- Veto 规则：feasibility violation > 0 / objective mismatch / timeout 超阈值 / 明显负退化

---

## 9. Contract Gate

### 9.1 检查范围

1. JSON schema 严格校验
2. touched files 在白名单
3. forbidden files 未修改
4. AST / 接口签名检查
5. import 白名单
6. 禁止 shell / subprocess / socket 等敏感调用
7. analysis 字段白名单
8. change_locus 必须可枚举

### 9.2 Contract 与 Verification 的边界

| 维度 | Contract | Verification |
|---|:---:|:---:|
| 文件白名单 | ✅ | ❌ |
| AST / 接口签名 | ✅ | 可复检 |
| import / forbidden API | ✅ | 可选 |
| 单元测试 | ❌ | ✅ |
| feasibility | ❌ | ✅ |
| objective recomputation | ❌ | ✅ |
| state leak | ❌ | ✅ |
| wall-clock / memory | ❌ | ✅ |

---

## 10. Verification Gate

### 10.1 定位

位于 Contract 之后、Protocol 之前。解决"候选是否仍在解同一个问题"。

### 10.2 检查清单

| # | 检查项 | 优先级 |
|---|---|---|
| 1 | import / syntax | P0 |
| 2 | interface compliance | P0 |
| 3 | unit tests | P0 |
| 4 | regression tests | P0 |
| 5 | feasibility oracle | P0 |
| 6 | objective recomputation | P0 |
| 7 | no state leak（double-run compare） | P0 |
| 8 | wall-clock guard | P0 |
| 9 | memory guard | P1 |
| 10 | RNG interface compliance | P1 |

### 10.3 Oracle 来源

- **人写 spec**（自然语言 + reference cases）
- **Agent（Opus）写 oracle 代码**
- **人审核 + 跑 reference cases 验证**
- **冻结为 frozen files，不可被搜索过程修改**

Oracle 是信任锚点，不能自举。

### 10.4 失败路由

| 失败类型 | 允许 LLM 修复重试 | 消耗分支预算 |
|---|:---:|:---:|
| Syntax / import | ✅ | 否 |
| Interface violation | ✅ | 否 |
| Unit test failure | ✅（限次） | 否 |
| Feasibility violation | ❌ | 是 |
| Objective mismatch | ❌ | 是 |
| State leak | ❌ | 是 |
| Wall-clock excessive | 视情况 | 是 |

---

## 11. 分支治理

### 11.1 分支语义

**1 branch = 1 方向，可迭代演化 hypothesis。**

分支内做深度探索，分支间做广度探索。分支多样性不做强制约束，由 LLM 自然发散。

```
Branch A: 方向 "改善 shaw removal"
  H1: 改距离度量 → screening fail
  H2: 改选择策略 → screening pass → validate
  H3: ...
```

### 11.2 分支内代码基线规则

```
上一个 hypothesis 的结果是：
  - verification 通过 + screening fail  → 基于当前代码继续迭代
  - verification 未通过               → 回退到分支内最后一个 clean 版本
  - 从未通过 verification              → 回退到 champion
```

### 11.3 分支状态机

```
NEW
  ↓
EXPLORE
  ├── screen_pass      → READY_VALIDATE
  ├── screen_unclear   → EXPLORE_EXPAND
  └── screen_fail      → (继续迭代 hypothesis 或 ABANDONED)

READY_VALIDATE
  ↓
VALIDATING
  ├── validate_pass    → READY_FROZEN
  ├── validate_expand  → VALIDATING_EXPAND
  └── validate_fail    → ABANDONED

READY_FROZEN
  ↓
FROZEN_TESTING
  ├── frozen_pass      → PROMOTED
  └── frozen_fail      → ABANDONED

任意状态
  ├── champion_changed → STALE
  ├── infra_incident   → BLOCKED_INFRA
  └── budget_exhausted → ABANDONED
```

### 11.4 Stale Branch 语义

每个分支记录 `base_champion_id` 和 `base_solver_hash`。

当 champion 变化时：
1. 所有活跃分支标记为 STALE
2. Stale 分支执行 reconcile：重新应用 patch → Contract → Verification → re-Screening
3. 仍有正信号则恢复到 READY_VALIDATE，否则 ABANDONED

### 11.5 预算规则

- `max_active_branches = 3`（可配）
- 分支内 hypothesis 数量不设硬限（budget 自然约束）
- LLM fix retry per candidate: 2
- screening expand: 1 次
- validation expand: 1 次
- frozen uses per campaign: 3

---

## 12. Scheduler

### 12.1 词典序硬优先级（MVP）

```
Priority 1: READY_FROZEN（等待最终确认）
Priority 2: READY_VALIDATE（等待正式验证）
Priority 3: STALE（待 reconcile）
Priority 4: EXPLORE 中已有正信号的分支
Priority 5: 创建新分支
```

同级内按创建时间排序（FIFO），不做加权打分。

### 12.2 终止条件

```python
def should_continue():
    if total_experiments >= budget.max_experiments: return False
    if wall_clock_hours >= budget.max_wall_clock_hours: return False
    if consecutive_fully_abandoned_branches >= budget.stagnation_threshold: return False
    if active_branches == 0 and not can_create_new(): return False
    return True
```

---

## 13. Failure Model

### 13.1 四层分类

#### A. Proposal / Contract Failure
- schema invalid / forbidden file touched / import blacklist violation
- **路由**：反馈 LLM 重试，不计入分支预算，不写 hypothesis memory

#### B. Verification Failure
- 轻度（syntax, interface, unit test）→ 反馈 LLM 重试，不计入分支预算
- 重度（feasibility, objective, state leak）→ 不重试，计入预算，写入 hypothesis memory

#### C. Runtime / Infra Incident
- subprocess timeout, OOM, harness crash, LLM API failure
- **路由**：infra retry，不计入分支预算

#### D. Evaluation Outcome
- screening_fail / validation_fail / frozen_fail / unclear / regression
- **路由**：走协议规则，计入预算，写入 hypothesis memory

---

## 14. Artifact & Lineage

### 14.1 存储方式

- MVP: SQLite + append-only 事件表
- 概念保留 hash-chain，MVP 不强制实现（P1）

### 14.2 最低记录字段

每次实验必须记录：
- campaign_id, branch_id, hypothesis_id, parent_hypothesis_id
- base_champion_id
- code_hash, patch_hash
- prompt_hash, model_version
- problem_spec_hash, split_version, seed_version, protocol_version
- verification_result
- raw_metrics_ref（指向具体数据）
- decision_features
- decision_reason_codes

### 14.3 结构化 HypothesisRecord

```python
@dataclass
class HypothesisRecord:
    hypothesis_id: str
    branch_id: str
    parent_hypothesis_id: Optional[str]

    change_locus: str              # 枚举
    action: str                    # modify / create_new / remove
    touched_symbols: list[str]
    predicted_direction: str       # improve / tradeoff / exploratory
    target_subgroup: Optional[str]

    rationale_text: str            # tainted，仅供人/LLM 读
    evidence_refs: list[str]       # experiment ids
    status: str                    # active / weakened / rejected / promoted
```

注意：`rationale_text` 不进入 Decision，`change_locus` 必须枚举。

---

## 15. Context Manager

### 15.1 上下文分层

给 LLM 的上下文遵循暴露控制：
1. 问题定义摘要
2. 当前 champion 算子代码 + 简述
3. 当前分支最新代码（如不同于 champion）
4. 当前分支最近 N 轮结果（结构化）
5. 已验证失败的结构化假设摘要
6. 兄弟分支简要状态

**不暴露**：validation/frozen 细节。

### 15.2 记忆压缩

- 保留完整：active hypotheses、promoted hypotheses、最近 3 轮 experiment summaries
- 压缩：长期 rejected hypotheses、重复失败模式

### 15.3 Blacklist 机制

不用 local/global 二值，使用：
- `scope_tags`
- `evidence_count`
- `expiry_round`（可过期，防止错误固化）

---

## 16. Runtime Isolation

### 16.1 最低标准

1. **每次 run 在独立 subprocess 中执行**（解决 Python 污染）
2. 每个分支独立 workspace
3. Champion snapshot 只读
4. Benchmark / protocol 文件只读
5. 资源限制（timeout, memory, file descriptor）
6. 环境变量净化
7. 临时目录隔离
8. Run 后清理 workspace cache

### 16.2 Runner 抽象

```python
class Runner(Protocol):
    def run(self, workdir: str, cmd: list[str], limits: ResourceLimits) -> RunResult: ...
```

MVP: `LocalSubprocessRunner`，后续可扩展 Docker/Remote。

---

## 17. 模型分工

### 17.1 角色定义

| 角色 | 模型 | 职责 | 触发时机 |
|---|---|---|---|
| 架构师 / 研究员 | Opus | 分析 problem spec、诊断连续失败、生成 oracle 代码 | Campaign 初始化、深度诊断 |
| 代码主力 | Sonnet / GPT-5.4 | 根据 hypothesis 生成 code patch、修复 verification failure | 每轮 proposal |

### 17.2 调用方式

**方案 A：直接 API 调用，不嵌 CC。**

框架运行时的 proposal engine 是直接 API 调用，LLM 只是"函数"：输入 context，输出 structured JSON。

CC 的价值在框架开发阶段——用 CC 帮写框架本身的代码。

---

## 18. 主循环伪代码

```python
while termination.not_reached(campaign_state):
    branch = scheduler.select(campaign_state)

    # 1) Stale 分支 reconcile
    if branch.state == "STALE":
        branch = stale_handler.reconcile(branch, current_champion)
        if branch.state == "ABANDONED":
            continue

    # 2) Round 1: Hypothesis
    hypothesis_context = context_manager.build_hypothesis_context(branch)
    hypothesis = proposal_engine.generate_hypothesis(hypothesis_context)

    contract_h = contract_gate.validate_hypothesis(hypothesis)
    lineage.record(contract_h)
    if not contract_h.passed:
        failure_router.handle(branch, contract_h)
        continue

    # 3) Round 2: Code
    code_context = context_manager.build_code_context(branch, hypothesis)
    patch = proposal_engine.generate_code(code_context)

    contract_c = contract_gate.validate_patch(patch)
    lineage.record(contract_c)
    if not contract_c.passed:
        failure_router.handle(branch, contract_c)
        continue

    # 4) Materialize + Verification
    candidate = workspace.materialize(branch, patch)
    verify = verification_gate.run(candidate)
    lineage.record(verify)
    if not verify.passed:
        failure_router.handle(branch, verify)
        # 轻度失败可能 retry（回到 Round 2）
        continue

    # 5) Canary
    canary = protocol.run_canary(candidate, champion)
    lineage.record(canary)
    if not canary.passed:
        branch_controller.reject(branch, "CANARY_FAIL")
        continue

    # 6) Screening / Validation / Frozen
    stage = branch_controller.next_stage(branch)
    proto_result = protocol.run(stage, candidate, champion)
    lineage.record(proto_result)

    # 7) Extract safe features
    features = safe_feature_extractor.extract(
        branch, contract_c, verify, canary, proto_result
    )

    # 8) Decision
    decision = decision_engine.decide(features)
    lineage.record(decision)

    # 9) State transition
    branch_controller.apply(branch, decision)
```

---

## 19. 演进路线

```
v0.1  MVP — 内核验证
      单问题 · 函数/文件级搜索 · 三级协议 · 双硬闸门
      目标：证明框架骨架能跑通、实验可审计

v0.2  参数层
      外层 LLM 探索结构 + 内层贝叶斯优化参数（算子权重等）
      两层嵌套搜索是核心差异化点

v0.3  问题定义辅助
      交互式引导用户定义 problem spec
      Oracle 半自动生成

v1.0  结构级搜索
      允许修改求解器框架本身（接受准则、搜索策略等）
      更强的 Verification Gate

v1.x  工程集成
      Verification Pipeline（灰度发布 + 生产监控）
      多问题族验证
      论文级 ablation + campaign 重复实验
```

---

## 20. 差异化定位

> **FunSearch/EoH 优化"候选程序生成与筛选"；**
> **Scion 优化"研究过程本身的结构化治理"。**

### 核心差异点

| # | 差异点 | FunSearch/EoH/ReEvo | Scion |
|---|---|---|---|
| 1 | 分支治理 | 无（单线或种群） | explore→validate→promote 状态机，分支内深度迭代 |
| 2 | 验证分离 | 无（评估即验证） | Contract + Verification + Protocol 三关独立 |
| 3 | 信息隔离 | 无 | 三层控制 + Decision Input Guard，LLM 无法间接操控决策 |
| 4 | 统计协议 | 点估计 keep/discard | 三级 split + seed ledger + 暴露控制 + bootstrap CI |
| 5 | 可追溯性 | 弱或无 | 完整 lineage，hypothesis → code → evaluation → decision 全链路 |

### 最强差异化（v0.2）

Agent + 参数搜索两层嵌套——外层 LLM 探索算子结构，内层贝叶斯优化参数。这在 v0.1 不实现，但架构预留。

---

## 21. 已知风险

### 风险 1：治理过强，搜索退化为小修小补
**缓解**：patch/commit 限制已放宽；blacklist 可过期；架构预留 structural branch 模式。

### 风险 2：Verification 成为开发瓶颈
**缓解**：Oracle 由 agent 写、人审核；先做 8 项核心检查；每项独立可测。

### 风险 3：A/B 评估信号弱（新算子被稀释）
**缓解**：create_new 操作 screening N=10；多 seed 降噪；validation 要求 bootstrap CI。

### 风险 4：Context 退化为日志堆
**缓解**：结构化 HypothesisRecord；自由文本不进 Decision；定期记忆压缩。

### 风险 5：多目标字典序可能遮蔽次要目标改进
**缓解**：Lineage 记录所有目标维度的 raw metrics；人类审核时可看全貌。

---

## 22. 决策记录

以下为架构讨论中的全部已锁定决策：

| # | 决策 | 结论 | 日期 |
|---|---|---|---|
| 1 | 主体蓝图 | v2.1 为主，整合为 Architecture v3 | 2026-04-02 |
| 2 | 开发周期 | 放宽，不卡硬限 | 2026-04-02 |
| 3 | Scheduler | MVP 词典序硬优先级 | 2026-04-02 |
| 4 | Lineage | 概念保留 hash-chain，MVP 用 SQLite + append | 2026-04-02 |
| 5 | Patch/Commit 限制 | 放宽，不设硬限 | 2026-04-02 |
| 6 | 算子操作 | 新增 + 删减 + 修改 | 2026-04-02 |
| 7 | Oracle | 人写 spec → agent 写代码 → 人审核 → 冻结 | 2026-04-02 |
| 8 | 搜索粒度 | v0.1 函数级 + 文件级并存 | 2026-04-02 |
| 9 | LLM 调用方式 | 直接 API，不嵌 CC | 2026-04-02 |
| 10 | 模型分工 | Opus 架构师/研究员，Sonnet/GPT-5.4 代码主力 | 2026-04-02 |
| 11 | Proposal 流程 | 两轮：先 hypothesis 再 code | 2026-04-02 |
| 12 | 分支迭代 | 方案 Y，分支内迭代演化 hypothesis | 2026-04-02 |
| 13 | 代码基线 | verification 未过回退干净基线 | 2026-04-02 |
| 14 | 评估方式 | A/B：champion solver vs (champion ± 变更) | 2026-04-02 |
| 15 | Champion 定义 | 池级别 | 2026-04-02 |
| 16 | 分支多样性 | 不强制约束，LLM 自然发散 | 2026-04-02 |
| 17 | 代码输出 | 完整文件（框架自行 diff） | 2026-04-02 |
| 18 | 算子注册 | 框架自动完成 | 2026-04-02 |
| 19 | Screening N | modify/remove: 6, create_new: 10 | 2026-04-02 |
| 20 | 多目标 | 字典序（业务聚合 > 成本 > 效率） | 2026-04-02 |
| 21 | Pool 评估结果 | 取 pool 最优解作为单次实验结果 | 2026-04-02 |
| 22 | 动态权重 | v0.1 冻结自适应机制，允许 agent 建议初始权重 | 2026-04-02 |

---

*本文档为基石架构，后续 v0.1 MVP 方案、v0.2 参数层设计、论文实验方案均从本文档派生。*
