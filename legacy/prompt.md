
## 背景上下文

### 项目发起人

BigBOSS — Operations Research & Optimization Algorithm Engineer，终端设备行业头部公司。核心领域：组合优化、LLM 训练管道、Agent 框架工程。已有两个 autoresearch 方式优化算法的工作实践经验（人工充当控制流 + agent 执行）。

### 设计演进路径

1. **Karpathy autoresearch 原始概念**：单线爬山，点估计 keep/discard
2. **BigBOSS + Cris 完整方法论**：分支控制器（explore→validate→promoted/abandoned）+ 统计晋升门槛（win_rate ≥ 2/3 + median_delta, N≥6）+ 搜索空间三分（Structural/Parametric/Policy）
3. **GPT-5.4 & GPT-5.4-Pro 工程架构评审**：Verification Pipeline + 灰度发布 + 生产监控
4. **v1 蓝图**：将方法论落地为 agent 框架
5. **GPT-5.4 审核 v1，指出 6 个关键遗漏**：实验协议层、执行沙箱、Artifact Lineage、Failure Taxonomy、调度策略形式化、终止条件
6. **v2 蓝图（本文档）**：整合 GPT-5.4 审核意见，补齐 6 个组件，升级三层控制模型

### 关键设计决策

- 从 CC（Claude Code）和 MiroFlow 学设计决策，不抄结构
- 约束越强框架越简单——OR autoresearch 的约束极强，不需要通用 agent 框架的复杂度
- LLM 产出是"提案"不是"决策"，必须经过确定性约束层才能进入决策层
- Agent + 参数搜索两层嵌套是差异化点（v0.2，FunSearch/EoH 把参数也交给 LLM）

---

## v2 蓝图正文

### 0. 定位

以 autoresearch 方法论为内核的专用 agent 框架，面向组合优化算法自动设计。

- 接受已定义好的组合优化问题（baseline + benchmark + 评价标准）
- 按科学方法论自主执行算法探索与优化
- 通过统计验证输出可靠的、优于 baseline 的新算法

**不是通用 agent 框架。** 不是 LangChain/MiroFlow 的竞品。

---

### 1. 核心原则

1. **方法论是内核，agent 是执行器** — 框架价值在搜索治理方法论
2. **确定性逻辑用代码，创造性推理用 LLM** — 分支控制器/统计门槛/验证管线全确定性
3. **三层控制模型** — LLM Creative → Contract 约束 → Decision 决策
4. **人在回路但不在循环里** — 人定义问题+审核结果，agent 独立执行探索循环

---

### 2. 三层控制模型（v2 核心升级）

v1 只定义了"LLM 的 4 个介入点"，v2 升级为三层约束模型：

```

Layer A: LLM Creative Layer
├── hypothesis proposal     → 必须经过 schema 验证
├── code patch proposal     → 必须经过 contract 检查
├── failure analysis        → 必须经过 allowed\_fields 过滤
└── branch direction        → 必须经过 novelty 检查
│
▼
Layer B: Contract Layer（确定性约束）
├── JSON schema validation
├── file whitelist enforcement
├── AST / interface compliance
├── patch size limit（max 200 行）
├── forbidden-file check（benchmark harness 不可改）
└── analysis field filter（只允许写 suspected\_failure\_mode 等字段）
│
▼
Layer C: Decision Layer（确定性决策）
├── branch state transitions
├── scheduling
├── promotion / abandonment
├── termination
└── artifact persistence

```

边界原则：**LLM 产出的是"提案"，不是"决策"**。提案必须通过 Contract 才能进入 Decision。

---

### 3. 架构总览

```

Problem Spec（人类定义）
problem.yaml + baseline code + benchmark instances + program.md
│
▼
OR-AutoResearch Agent Core
│
├── Control Flow（主循环）
│     while should\_continue():
│       branch = scheduler.select()
│       context = context\_manager.build(branch)
│       if EXPLORE: hypothesis→\[Contract]→code→\[Contract]→verify
│       if VALIDATE: frozen code, fresh cases only
│       label = experiment\_protocol.evaluate()
│       branch\_controller.decide(label)
│       lineage.record()
│
├── Branch Controller（确定性状态机）
│     explore → validate → promoted/abandoned
│     max 3 活跃分支，每分支 max 3 commits
│     从 champion 分叉，promote 时 squash + 清理 stale
│
├── Experiment Protocol（实验协议层）【v2 新增】
│     配对评估（同 case 同 seed）
│     随机采样排除已用 case（防过拟合）
│     回归检测（candidate 不能在历史 case 上显著退化）
│
├── Promotion Gate（确定性）
│     win\_rate ≥ 2/3 + median\_delta ≥ 阈值，N ≥ 6，含 retry
│
├── Contract Layer（确定性约束）【v2 新增】
│     schema + AST + file whitelist + patch size
│
├── Runtime Isolation（执行隔离）【v2 新增】
│     per-branch workspace，champion 快照不可变
│     依赖锁定，超时控制，cleanup
│
├── Context Manager（分层窗口）
│     问题定义 + champion + 近5轮详细 + 早期摘要
│     结构化 HypothesisRecord（替代自然语言日志）【v2 升级】
│
├── Scheduler（显式优先级）【v2 升级】
│     validate debt first → explore by signal → create new
│
├── Failure Taxonomy（失败分类）【v2 新增】
│     可修复（语法/接口/合约） → 反馈 LLM 重试
│     不可修复（超时/OOM/不可行） → 丢弃本次
│     基础设施故障 → 不惩罚分支
│
├── Artifact & Lineage（血缘追踪）【v2 新增】
│     每次实验：hypothesis\_id → code\_hash → protocol\_version
│                → raw\_metrics → decision\_trace
│
└── Termination（多重终止）【v2 新增】
硬预算 + 停滞检测 + 无活跃分支

````

---

### 4. 关键模块设计

#### 4.1 Experiment Protocol

```python
class ExperimentProtocol:
    def sample_cases(self, instance_pool, exclude_used=None):
        # 随机采样排除已用 case（防过拟合）
        available = [i for i in instance_pool if i not in (exclude_used or set())]
        return random.sample(available, min(self.n_cases, len(available)))

    def run_paired_evaluation(self, candidate_code, champion_code, case_set):
        # 配对评估：同 case 同 seed
        for case in case_set:
            for seed in self.seeds:
                cand_score = benchmark_run(candidate_code, case, seed)
                champ_score = benchmark_run(champion_code, case, seed)
                results.append(PairedResult(...))
        return PairedEvaluation(results)
````

#### 4.2 Contract Layer

```python
class ContractLayer:
    def validate_code_patch(self, original_code, new_code):
        checks = [
            self._check_file_whitelist(new_code),
            self._check_patch_size(diff_lines, max=200),
            self._check_interface_compliance(new_code),   # AST 检查
            self._check_frozen_files_untouched(new_code), # benchmark harness 不可改
            self._check_syntax(new_code),
        ]
        return ContractResult(checks)

    def validate_analysis_proposal(self, analysis):
        # 防止 LLM 结果分析间接控制决策
        allowed_fields = ["suspected_failure_mode", "improvement_axes",
                         "confidence", "evidence_summary"]
        return self._check_schema_strict(analysis, allowed_fields)
```

#### 4.3 结构化 HypothesisRecord

```python
@dataclass
class HypothesisRecord:
    hypothesis_id: str
    hypothesis_text: str
    change_locus: str       # "destroy operator", "acceptance criterion"
    expected_effect: str
    observed_effect: str
    failure_mode: str       # "partial_improvement", "regression", "no_effect"
    confidence: float
    blacklist_scope: str    # "local" or "global"
```

#### 4.4 Failure Taxonomy

```python
class FailureType(Enum):
    # 可修复 → 反馈 LLM 重试（最多 N 次）
    SYNTAX_ERROR = "syntax_error"
    INTERFACE_VIOLATION = "interface_violation"
    CONTRACT_VIOLATION = "contract_violation"

    # 不可修复 → 丢弃本次，不消耗分支预算
    RUNTIME_TIMEOUT = "runtime_timeout"
    RUNTIME_OOM = "runtime_oom"
    FEASIBILITY_VIOLATION = "feasibility_violation"

    # 基础设施 → 暂停重试，不惩罚分支
    BENCHMARK_INFRA_FAILURE = "benchmark_infra_failure"
    LLM_API_FAILURE = "llm_api_failure"

    # 结构性 → 记录到失败假设
    PERFORMANCE_REGRESSION = "performance_regression"
    HYPOTHESIS_INEFFECTIVE = "hypothesis_ineffective"
```

#### 4.5 Promotion Gate（复用 autoresearch framework 原始实现）

```python
def promotion_gate(experiment_scores, champion_scores, min_practical_delta):
    deltas = [e - c for e, c in zip(experiment_scores, champion_scores)]
    N = len(deltas)
    wins = sum(1 for d in deltas if d > 0)
    win_rate = wins / N
    median_delta = sorted(deltas)[N // 2] if N % 2 == 1 else \
        (sorted(deltas)[N//2 - 1] + sorted(deltas)[N//2]) / 2.0

    if N < 6: return "unclear", win_rate, median_delta
    if win_rate >= 2/3 and median_delta >= min_practical_delta:
        return "confidently_better", win_rate, median_delta
    if win_rate <= 0.5 or median_delta <= 0:
        return "not_better", win_rate, median_delta
    return "unclear", win_rate, median_delta
```

---

### 5. v0.1 Scope（收紧后）

**做**（12 项核心交付物）：

1. 单问题、单机、单进程
2. 单目标优化（higher/lower is better 可配）
3. 固定 benchmark schema（problem.yaml 定义，不做通用 DSL）
4. 受限 patch 空间（文件白名单 + patch size limit）
5. 2-stage evaluation（explore eval + frozen validate）
6. 确定性 branch controller + promotion gate
7. Experiment Protocol（seed 策略 + 配对评估 + 回归检测）
8. Contract Layer（schema + file whitelist + AST check）
9. Runtime Isolation（目录隔离，不用 Docker）
10. Artifact Lineage（结构化实验记录，可审计）
11. Failure Taxonomy（分类处理）
12. 结构化假设记忆

**不做**：

- ❌ 跨问题通用 DSL
- ❌ 自适应 gate
- ❌ 问题定义辅助（v0.3）
- ❌ 多 agent 编排 / MCP
- ❌ Web UI
- ❌ Parametric tuning（v0.2）
- ❌ 灰度发布

---

### 6. 实现计划（4 周）

| 周  | 核心任务                                                                                                                     |
| -- | ------------------------------------------------------------------------------------------------------------------------ |
| W1 | 基础设施：promotion\_gate, experiment\_protocol, branch\_controller, failure\_taxonomy, runtime\_isolation, artifact\_lineage |
| W2 | 三层控制+核心循环：contract\_layer, context\_manager, loop.py, LLM client, prompt 模板                                              |
| W3 | 工具层+Benchmark：code\_verify（多层管线）, benchmark\_run, 准备 VRP destroy operator 验证问题                                           |
| W4 | 端到端验证：≥10 轮实验，验收标准全检查                                                                                                    |

**验收标准**：

1. agent 自主执行探索循环
2. 三层控制有效（Contract 能拦截越界代码）
3. 实验可审计（lineage 全链路可追溯）
4. 失败分类正确路由
5. mock LLM 后确定性部分独立运转

---

### 7. 差异化定位

> **FunSearch/EoH 优化的是"候选程序生成与筛选"；**
> **本框架优化的是"研究过程本身的结构化治理"。**

**5 个结构性差异点**：

| # | 差异点  | FunSearch/EoH/ReEvo | 本框架                                        |
| - | ---- | ------------------- | ------------------------------------------ |
| 1 | 假设对象 | 隐式（代码即假设）           | 显式 HypothesisRecord，可审计可复用                 |
| 2 | 分支治理 | 无（单线或种群）            | explore→validate→promote 状态机               |
| 3 | 验证分离 | 无（评估即验证）            | frozen code + fresh cases 二阶段              |
| 4 | 统计门槛 | 点估计选择               | win\_rate + median\_delta + retry protocol |
| 5 | 失败记忆 | 无或弱                 | 结构化 taxonomy + blacklist                   |

vs Karpathy autoresearch：

> 从"单线程代码代理"提升为"实验分支治理系统"。

vs ReEvo：

> ReEvo 管的是"候选体如何演化"；本框架管的是"研究假设如何被提出、验证、晋升、淘汰"。

---

### 8. 长期路线图

```
v0.1  内核验证 ← 当前
      单问题 → 自主探索 → 统计验证 → 新算法

v0.2  Parametric Tuning 集成
      外层 LLM 探索结构 + 内层贝叶斯优化参数（核心差异化）

v0.3  问题定义辅助
      交互式引导用户定义 problem.yaml

v1.0  初始框架自动设计
      基于问题定义推荐/生成 baseline 求解框架

v1.x  工程集成
      Verification Pipeline + 灰度发布 + 生产监控
```

---

## GPT-5.4 审核意见摘要（已整合进 v2）

以下是 GPT-5.4 对 v1 的审核结论，已整合进 v2：

**6 个关键遗漏（均已补）**：

1. 实验协议层 → Experiment Protocol
2. 执行沙箱/Runtime Isolation → Runtime Isolation
3. Artifact/Lineage 追踪 → Artifact & Lineage
4. Failure Taxonomy → Failure Taxonomy
5. 调度策略形式化 → Scheduler 显式优先级
6. 终止条件 → 多重终止条件

**LLM 边界问题（已升级）**：

- v1：只说 4 个介入点 → v2：三层控制模型，LLM analysis 输出受 schema 约束
- v1：代码生成无 patch 约束 → v2：Contract Layer + 文件白名单 + patch size limit

**v0.1 Scope 建议（已收紧）**：

- 不承诺"广义组合优化即插即用"
- 限定：单目标、单机单进程、固定 benchmark schema、受限 patch 空间

**Top-3 风险（仍需关注）**：

1. 评估噪声导致错误晋升/淘汰（已部分缓解：配对评估+retry）
2. LLM 改动越界污染系统信号（已部分缓解：Contract Layer）
3. 记忆退化为日志堆积（已部分缓解：HypothesisRecord）

# 以下是原autoresearch的框架讨论总结：

# 文档一：工程应用架构

# LLM-Assisted Solver Engineering：工程应用架构设计

*v1.0 — 2026-03-30 | 面向生产环境的 LLM 辅助算法持续改进系统*

---

## 0. 设计哲学

> **目标不是"全自主的 AI 科学家"，而是"让 OR 工程师 10x 更快地改进 solver"。**

核心原则：

- **人是决策者，LLM 是加速器**：LLM 帮你生成候选、跑实验、整理历史，决策权在你手上
- **安全第一**：生产 solver 的 bug 代价远超学术 benchmark 上的性能损失
- **真实数据驱动**：用生产订单数据验证，不用学术 instance
- **简单可靠优于花哨复杂**：一条自动化流水线，不是 5 个 agent 对话

---

## 1. 与学术框架（v2）的关系

本文档建立在 Multi-Agent Autoresearch v2 的基础上，但做了根本性调整：

| 维度           | 学术框架 (v2)                      | 工程架构 (本文档)                   |
| ------------ | ------------------------------ | ---------------------------- |
| 目标           | 证明改善统计显著                       | 让 solver 在生产中跑得更好            |
| 人的角色         | 旁观者（系统全自主）                     | 决策者（LLM 辅助）                  |
| Agent 架构     | 5 个 agent 分层协作                 | 1 个 LLM + 自动化工具链             |
| 验证方式         | 三级 instance 集 + Promotion Gate | Verification Pipeline + 灰度上线 |
| Ground truth | 学术 benchmark                   | 每天的真实订单                      |
| 时间尺度         | 一次性研究 campaign                 | 持续迭代，永不停止                    |

**从 v2 保留的核心资产：**

1. Verification Gate（加重，适配生产要求）
2. 实验历史记录（简化，面向工程实用）
3. 搜索空间三分（Structural + Parametric + Policy）
4. 半结构化通信协议（简化为工程模板）

**从 v2 丢弃的：**

1. Multi-agent 分层（用工具链替代）
2. Director 全自主因果归因（OR 工程师自己做）
3. Promotion Gate + frozen holdout（灰度上线替代）
4. 双层记忆系统（简化为实验日志）

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                    OR 工程师（你）                            │
│                                                             │
│   • 定义改进方向                                             │
│   • 审核候选方案                                             │
│   • 分析 benchmark 报告                                     │
│   • 决定灰度/上线/回滚                                      │
│                                                             │
└──────────────┬──────────────────────────────┬───────────────┘
               │ 改进指令                      │ 审核决策
               ▼                              │
┌──────────────────────────────┐              │
│    Operator Generator        │              │
│    (LLM + RAG)               │              │
│                              │              │
│  • 理解你的改进方向            │              │
│  • 检索相关代码片段（RAG）     │              │
│  • 生成 3-5 个候选变体         │              │
│  • 附带参数建议和设计说明      │              │
└──────────────┬───────────────┘              │
               │ 候选算子代码                   │
               ▼                              │
┌──────────────────────────────┐              │
│    Verification Pipeline     │              │
│    (无 LLM · 确定性)         │              │
│                              │              │
│  11 项强制检查                │              │
│  不通过 → 反馈 LLM 修复      │              │
│  3 次失败 → 丢弃 + 记录      │              │
└──────────────┬───────────────┘              │
               │ 验证通过的候选                  │
               ▼                              │
┌──────────────────────────────┐              │
│    Parametric Tuning         │              │
│    (无 LLM · 贝叶斯优化)     │              │
│                              │              │
│  对每个通过验证的候选：        │              │
│  • 自动搜索最优参数           │              │
│  • 20-50 次 solver run       │              │
│  • 防止好结构被烂参数冤杀     │              │
└──────────────┬───────────────┘              │
               │ 结构 + 最优参数                │
               ▼                              │
┌──────────────────────────────┐              │
│    Offline Benchmark         │              │
│    (无 LLM · 自动化)         │              │
│                              │              │
│  • 最近 30 天真实订单数据      │              │
│  • 多 seed · Common RN       │              │
│  • vs 当前生产版本            │              │
│  • 自动生成对比报告           │              │
└──────────────┬───────────────┘              │
               │ 对比报告                      │
               ▼                              │
┌──────────────────────────────┐              │
│    Report & Review           │──────────────┘
│                              │  你审核报告、看代码、做决策
│  • per-场景 breakdown        │
│  • per-规模 breakdown        │
│  • wall-clock 对比           │
│  • 异常/退化高亮             │
└──────────────┬───────────────┘
               │ 决定灰度上线
               ▼
┌──────────────────────────────┐
│    灰度发布 & 生产监控        │
│                              │
│  Shadow → 5% → 50% → 100%   │
│  实时监控 + 一键回滚          │
└──────────────────────────────┘
```

---

## 3. 各组件详细设计

### 3.1 Operator Generator（LLM + RAG）

**不需要多 agent。一个强 LLM + 好的 RAG 检索就够了。**

**RAG 代码库构建（一次性工作）**：

将 solver 代码按模块切片，建立向量索引：

```
rag_index/
  ├── data_structures/     # Solution, Route, Node 等定义
  ├── operator_interfaces/ # BaseDestroyOperator, BaseRepairOperator
  ├── existing_operators/  # 现有的 destroy/repair 算子
  ├── constraints/         # 约束检查逻辑
  ├── cost_functions/      # 目标函数计算
  └── config/              # 参数配置
```

**交互模板**：

```
你的输入：
  "当前 RandomDestroy 在地理分布密集的场景下效率低。
   想试试基于客户聚类的 destroy。"

LLM 自动检索：
  • BaseDestroyOperator 接口（从 RAG）
  • RandomDestroy 现有实现（从 RAG）
  • DistanceMatrix 相关方法（从 RAG）
  • Solution 数据结构（从 RAG）

LLM 输出：
  • 3-5 个候选实现（附设计说明）
  • 新增参数列表 + 建议范围
  • 已知风险提示（"注意：聚类数 < 路线数时可能删除不足 k 个节点"）
```

**模型选择**：

- 日常使用：GPT-4 级别（Sonnet/GPT-5.4）足够
- 复杂设计：偶尔上 Opus/GPT-5.4-Pro
- 成本：每次生成 \~$0.5-2，可忽略

### 3.2 Verification Pipeline（核心安全组件）

**这是工程架构中最重要的组件。** 从 v2 继承并加重。

```python
class VerificationPipeline:
    """11 项强制检查，全部通过才能进入 benchmark。"""

    def verify(self, candidate, spec) -> VerificationResult:
        return self.run_checks([
            # ── 基础检查 ──
            self.check_import(),              # 语法正确、能导入
            self.check_interface(),            # 实现了 BaseOperator 接口
            self.check_type_consistency(),     # 输入输出类型匹配

            # ── 正确性检查 ──
            self.check_unit_tests(spec.tests), # spec 附带的单元测试
            self.check_regression_tests(),     # 现有 test suite 全量通过
            self.check_feasibility_oracle(),   # 10 个小 instance，解始终可行
            self.check_objective_recompute(),  # 增量 cost vs 全量重算，误差 < 1e-6

            # ── 性能检查 ──
            self.check_wall_clock(),           # 不超过同类算子 2x
            self.check_memory(),               # 内存不超过 baseline 1.5x

            # ── 工程检查 ──
            self.check_no_state_leak(),        # 连续调用不互相污染
            self.check_thread_safety(),        # 多线程环境下无竞态
        ])
```

**失败处理**：

```
候选 → Verification Pipeline
  │
  ├── 全部通过 → 进入 Parametric Tuning
  │
  ├── 基础/正确性检查失败（可修复）
  │   → 带结构化错误信息返回 LLM
  │   → LLM 修复，最多重试 2 次
  │   → 3 次失败 → 丢弃，记录失败原因
  │
  └── 性能/工程检查失败（结构性问题）
      → 直接丢弃
      → 记录到实验日志
      → 如果连续 3 个候选都这样 → 提醒你 spec 可能有问题
```

### 3.3 Parametric Tuning（无 LLM）

**解决"好结构被烂参数冤杀"问题。** 从 v2 保留。

```python
class ParametricTuner:
    """对每个通过验证的候选算子，搜索最优参数。"""

    def tune(self, operator, param_space, instances, n_trials=30):
        """
        用贝叶斯优化（Optuna/SMAC）搜索参数。

        param_space 示例:
          k: int [3, 50]
          cluster_weight: float [0.0, 1.0]
          tw_slack_factor: float [0.1, 0.9]

        instances: 5-10 个代表性真实订单
        n_trials: 20-50 次 solver run
        """
        study = optuna.create_study(direction="minimize")
        study.optimize(
            lambda trial: self.evaluate(operator, trial, instances),
            n_trials=n_trials
        )
        return study.best_params, study.best_value
```

**时间成本**：

- 每个候选 30 次 run × 5 分钟/run = 2.5 小时
- 3 个候选并行 = 2.5 小时总计（如果有 3 台机器）
- 可以晚上跑，早上看结果

### 3.4 Offline Benchmark（自动化对比）

**核心差异：用真实数据，不用学术 instance。**

```yaml
benchmark_config:
  # 数据源
  instances:
    source: "production_orders_last_30_days"
    sample_strategy: "stratified"  # 按场景类型分层抽样
    categories:
      dense_urban: 10 instances
      sparse_rural: 5 instances
      mixed: 5 instances
      large_scale_500plus: 5 instances
      tight_time_window: 5 instances
    total: 30 instances

  # 实验设置
  seeds: [42, 137, 256, 314, 628]  # 5 seeds
  runtime_budget: 300  # seconds per run
  baseline: "current_production_version"
  common_random_numbers: true

  # 报告内容
  report:
    aggregate: [mean_gap, median_gap, win_rate, paired_t_test_p_value]
    per_category: [mean_gap, win_rate]
    performance: [mean_wall_clock, max_wall_clock, memory_peak]
    anomalies: [feasibility_violations, timeout_count, crash_count]
    highlight_threshold:
      improvement: 0.5%   # 高亮显著改善
      regression: -0.3%   # 高亮退化
```

**自动生成的报告示例**：

```
================================================================
Benchmark Report: ClusterBoundaryDestroy v3
Date: 2026-04-01
Baseline: production-v2.4.1
================================================================

AGGREGATE (30 instances × 5 seeds = 150 runs)
  Mean gap vs baseline:   -1.2% (改善)
  Median gap vs baseline: -0.9% (改善)
  Win rate:               21/30 instances (70%)
  Paired t-test:          p = 0.003 (显著)
  Wall-clock:             +8% slower (287s vs 265s)

PER-CATEGORY BREAKDOWN
  dense_urban (10):    Δ = -2.1%, win = 9/10  ✅ 显著改善
  sparse_rural (5):    Δ = +0.3%, win = 1/5   ⚠️ 轻微退化
  mixed (5):           Δ = -0.8%, win = 3/5   → 中性
  large_scale (5):     Δ = -1.5%, win = 4/5   ✅ 改善
  tight_tw (5):        Δ = -0.6%, win = 4/5   ✅ 改善

ANOMALIES
  Feasibility violations: 0
  Timeouts: 0
  Crashes: 0

RECOMMENDATION
  改善显著但 wall-clock +8%，sparse_rural 轻微退化。
  建议：只在非 sparse 场景启用，或进一步优化复杂度。
================================================================
```

### 3.5 灰度发布 & 生产监控

**生产数据是最好的 holdout。**

```
灰度阶段设计：

Stage 0: Shadow Mode（1 周）
  ├── 新算子和旧算子同时跑
  ├── 只用旧算子的结果
  ├── 记录新算子的结果用于对比
  └── 验证：无 crash、无 feasibility violation、wall-clock 可接受

Stage 1: 5% 灰度（3 天）
  ├── 5% 真实流量用新算子
  ├── 实时监控 KPI
  └── 任何异常 → 一键回滚

Stage 2: 50% 灰度（3 天）
  ├── A/B 对比有统计意义
  └── 确认无长尾问题

Stage 3: 全量上线
  └── 持续监控 1 周后标记为 stable
```

**监控指标**：

```yaml
production_metrics:
  quality:
    - total_cost_vs_baseline
    - route_count_vs_baseline
    - average_utilization

  safety:
    - feasibility_violation_rate     # 必须为 0
    - time_window_violation_rate     # 必须 < 0.1%
    - capacity_violation_rate        # 必须为 0

  performance:
    - solve_time_p50
    - solve_time_p99
    - memory_peak

  business:
    - on_time_delivery_rate
    - customer_complaint_rate        # 滞后指标，1 周后看

  rollback_trigger:
    - feasibility_violation_rate > 0          → 立即回滚
    - solve_time_p99 > 2x baseline            → 立即回滚
    - total_cost > baseline + 2%              → 人工评估
    - any_crash                               → 立即回滚
```

### 3.6 实验日志（工程版）

**不需要 v2 的双层记忆。一个结构化日志就够。**

核心目的：避免重复劳动 + 新人快速了解历史。

```yaml
# ~/solver/experiment_log/2026-04-01-cluster-destroy.yaml

experiment:
  date: "2026-04-01"
  engineer: "BigBOSS"
  objective: "改善密集场景的 destroy 效率"

  hypothesis: "基于客户聚类边界的 destroy 在密集场景优于 random destroy"

  candidates_generated: 5
  candidates_passed_verification: 3
  candidates_after_tuning: 2

  best_candidate:
    name: "ClusterBoundaryDestroy_v3"
    code_path: "operators/cluster_boundary_destroy_v3.py"
    key_params: { k: 12, cluster_weight: 0.7, min_cluster_size: 3 }
    design_insight: "按 DBSCAN 聚类，优先删除聚类边界节点"

  benchmark_result:
    overall_gap: "-1.2%"
    win_rate: "21/30"
    wall_clock_change: "+8%"
    best_category: "dense_urban: -2.1%"
    worst_category: "sparse_rural: +0.3%"

  decision: "conditional_deploy"
  deploy_scope: "非 sparse 场景"
  deploy_date: "2026-04-03"

  production_result:  # 灰度后填写
    shadow_result: "无异常，gap 与 offline 一致"
    gray_5pct_result: "成本 -1.0%，无 violation"
    gray_50pct_result: "成本 -1.1%，稳定"
    full_deploy_date: "2026-04-12"
    stable_after_1week: true

  lessons_learned:
    - "聚类在稀疏场景不稳定，需要 fallback 到 random destroy"
    - "wall-clock +8% 可接受，因为总体成本改善更大"
    - "DBSCAN 的 eps 参数对结果影响大，后续可以做自适应"

  related_experiments:
    - "2026-03-20-random-walk-destroy.yaml"  # 之前尝试过的
```

---

## 4. 搜索空间三分（从 v2 保留简化）

### 4.1 三类改进类型

```
Type 1: Structural（代码逻辑）
  工具：LLM 生成 → Verification → Benchmark
  频率：每月 1-2 次大改
  示例：新的 destroy 算子

Type 2: Parametric（参数调优）
  工具：贝叶斯优化，不需要 LLM
  频率：每次新算子上线后 + 每季度复查
  示例：k 值、权重、阈值

Type 3: Policy（选择策略）
  工具：LLM 辅助设计 + 规则引擎实现
  频率：按需
  示例：什么场景用什么算子
```

### 4.2 Policy 设计（解决 conditional deploy 问题）

当一个算子在某些场景好、某些场景差时，不是"不上线"，而是"条件上线"：

```python
class OperatorSelector:
    """根据 instance 特征选择算子。"""

    def select_destroy(self, instance: Instance) -> DestroyOperator:
        density = instance.compute_density()

        if density > self.dense_threshold:
            return ClusterBoundaryDestroy(k=12, cluster_weight=0.7)
        else:
            return RandomDestroy(k=15)
```

Policy 本身也走 Verification + Benchmark + 灰度流程。

---

## 5. 一次完整的改进周期

```
Week 1, Day 1 (Monday):
  你："destroy 算子在密集场景效率低，试试聚类方法"
  │
  ▼
  LLM 生成 5 个候选 → Verification Pipeline → 3 个通过
  │
  ▼
  晚上启动 Parametric Tuning（3 个候选 × 30 runs）

Week 1, Day 2 (Tuesday):
  早上看 tuning 结果 → top-2 候选（带最优参数）
  │
  ▼
  启动 Offline Benchmark（2 个候选 × 30 instances × 5 seeds）

Week 1, Day 3 (Wednesday):
  早上看 benchmark 报告
  │
  ├── 候选 A：dense -2.1%, sparse +0.3%, wall-clock +8%
  └── 候选 B：dense -1.5%, sparse -0.1%, wall-clock +2%
  │
  你的决策：
  "候选 B 更稳，虽然 dense 改善小一点但 sparse 不退化。
   先上 B，后续再看能不能把 A 的聚类逻辑和 B 结合。"
  │
  ▼
  启动 Shadow Mode

Week 2, Day 1-3:
  Shadow 无异常 → 启动 5% 灰度

Week 2, Day 4-7:
  5% 灰度 → 成本 -0.8%, 无 violation → 启动 50%

Week 3:
  50% 灰度 → 稳定 → 全量上线
  │
  ▼
  填写实验日志 → done
```

**总周期：2-3 周（从 idea 到全量上线）。**
传统纯人工：可能 1-2 个月。加速 3-5x。

---

## 6. 前置工程要求

在这套系统能跑之前，solver 本身需要满足一些前置条件：

### 6.1 算子接口标准化（最重要）

```python
class BaseDestroyOperator(ABC):
    """所有 destroy 算子必须实现此接口。"""

    @abstractmethod
    def execute(self, solution: Solution, k: int,
                params: DestroyParams) -> DestroyResult:
        """
        Args:
            solution: 当前解（不可直接修改，需要 copy）
            k: 删除节点数
            params: 算子特定参数

        Returns:
            DestroyResult:
                removed_nodes: List[Node]
                partial_solution: Solution（删除后的解）
                metadata: dict（可选，用于 repair 参考）
        """
        pass

    def get_param_space(self) -> dict:
        """返回参数搜索空间，用于 parametric tuning。"""
        return {}
```

**没有标准化接口，LLM 生成的代码就没法 plug in。** 这是必须先做的一次性工程投入。

### 6.2 Benchmark Harness

```python
class BenchmarkHarness:
    """自动化 benchmark 运行框架。"""

    def run(self, operator, instances, seeds, budget):
        """
        运行 benchmark 并生成结构化结果。
        支持 common random numbers。
        """
        results = []
        for instance in instances:
            for seed in seeds:
                result = self.solver.solve(
                    instance, operator=operator,
                    seed=seed, time_limit=budget
                )
                results.append(result)
        return BenchmarkResult(results)

    def compare(self, result_new, result_baseline):
        """生成对比报告。"""
        return ComparisonReport(result_new, result_baseline)
```

### 6.3 回归测试集

现有 solver 的测试用例，覆盖：

- 空路线、单客户、超大订单
- 时间窗紧/松
- 容量紧/松
- 各种边界条件

**每个候选算子必须通过全部回归测试。**

---

## 7. 与学术框架 (v2) 的桥梁

如果未来要发论文，可以在工程架构上叠加学术层：

```
工程架构（日常使用）
  │
  │ 叠加学术层（发论文时启用）
  │
  ├── 用学术 benchmark instance（CVRPLib 等）替代生产数据
  ├── 三级验证集替代灰度上线
  ├── Promotion Gate 替代人工审核
  ├── 全自主 Director 替代 OR 工程师
  └── 完整 Experiment Registry 替代简化实验日志
```

两套架构共享：

- Verification Pipeline（完全一样）
- Parametric Tuning（完全一样）
- 算子接口设计（完全一样）
- 搜索空间三分（完全一样）

---

## 8. 总结

| 组件                    | 工程价值  | 实现难度 | 优先级         |
| --------------------- | ----- | ---- | ----------- |
| 算子接口标准化               | ★★★★★ | 中    | P0（前置条件）    |
| Verification Pipeline | ★★★★★ | 中高   | P0（安全基石）    |
| Benchmark Harness     | ★★★★  | 中    | P1          |
| LLM + RAG 生成器         | ★★★★  | 低    | P1          |
| Parametric Tuning     | ★★★   | 低    | P2          |
| 灰度发布机制                | ★★★★  | 中    | P2（取决于部署环境） |
| 实验日志                  | ★★★   | 低    | P2          |
| Policy 选择器            | ★★    | 低    | P3          |

**一句话**：先标准化算子接口 + 建 Verification Pipeline，然后接 LLM 生成 + Benchmark 自动化。灰度机制根据你的部署环境决定。

---

*文档位置：\~/research/or-llm-survey/architecture/engineering-architecture-v1.md*
*关联文档：*

- - multi-agent-autoresearch-v2.md（学术框架）\*
- - gpt-pro-review-v1.md（GPT-5.4-Pro 审核）\*

\========================================================================
文档二：学术实验治理框架 (Multi-Agent Autoresearch v2)
==========================================

# Multi-Agent Autoresearch v2：LLM 驱动的自适应算法设计实验系统

*v2.0 — 2026-03-30 | 基于 GPT-5.4-Pro 审核意见修订*

---

## 0. 设计哲学

> **核心命题不是"多个 agent 协作"，而是"把 heuristic 自动设计变成可审计、可验证、可追溯的实验科学"。**

Multi-agent 是承载方式，不是目的。真正的价值来自四个支柱：

1. **角色解耦**：把"提假设"和"写代码"拆开，让对的模型做对的事
2. **实验治理**：每次实验可复现、可追溯、可审计
3. **统计闸门**：不靠 fitness 排名拍脑袋，用严格检验做决策
4. **结构化记忆**：事实和假设分离，防止自我强化叙事

---

## 1. 系统总览

```
┌─────────────────────────────────────────────────────────────────┐
│                     Research Director                            │
│                (强LLM · 低频 · 战略决策)                         │
│                                                                 │
│  输入：Statistical Report + Fact Memory + Hypothesis Memory      │
│  输出：Research Directive（假设 + 预期 + 允许范围 + 验证要求）    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Architecture Analyst                           │
│              (中等LLM · 中频 · 技术翻译)                         │
│                                                                 │
│  输入：Research Directive + Module Interface Doc                  │
│  输出：Operator Spec（半结构化）                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Operator Designer(s)                           │
│            (弱/中LLM · 高频 · 可并行)                            │
│                                                                 │
│  输入：Operator Spec + 局部代码片段                               │
│  输出：candidate_operator.py × 3-5 变体                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
│              ★ Verification Gate [v2 新增]                       │
│                   (无LLM · 确定性检查)                           │
│                                                                 │
│  静态检查 → 接口兼容 → 单元测试 → feasibility oracle →           │
│  objective recomputation → complexity guard → timeout/mem cap    │
│                                                                 │
│  不通过 → 带错误类型反馈给 Designer 重试（最多 2 次）             │
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┬ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘
                           │ 只有通过的候选进入实验
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Test Executor                                │
│                  (无LLM · 纯计算)                                │
│                                                                 │
│  三级 Instance 集 + 多 seed + Common Random Numbers              │
│  输出：experiment_results.json                                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Statistical Auditor                            │
│               (无LLM · 确定性统计)                               │
│                                                                 │
│  Promotion Gate + 过拟合检测 + 条件分析                           │
│  输出：statistical_report.md → Director                          │
│        (Screening/Dev 结果公开; Frozen 结果仅报 pass/fail)       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              ★ Experiment Registry [v2 新增]                     │
│                (无LLM · 持久化存储)                               │
│                                                                 │
│  每次实验的完整 provenance，不可篡改                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 优先项 A：Verification Gate

### 2.1 定位

放在 Designer 和 Executor 之间的**硬闸门**。任何候选算子必须通过全部检查才能进入 benchmark。否则 Auditor 看到的"改善"可能是约束被偷偷放松或 objective 算错的假象。

### 2.2 检查清单（按顺序执行，fail-fast）

```python
class VerificationGate:
    """所有检查均为确定性，不需要 LLM。"""

    def check_all(self, candidate_operator, spec) -> VerificationResult:
        checks = [
            self.check_import(),           # 能否正常导入，无语法错误
            self.check_interface(),         # 是否实现了 spec 要求的接口
            self.check_type_hints(),        # 输入输出类型与基类一致
            self.check_unit_tests(),        # 通过 spec 附带的单元测试
            self.check_feasibility(),       # 在 3 个小 instance 上跑，解始终可行
            self.check_objective_recomp(),  # 增量 cost 与全量重算一致（误差 < 1e-6）
            self.check_no_state_leak(),     # 连续调用两次，结果不互相污染
            self.check_complexity(),        # wall-clock 不超过同类算子 2x
            self.check_memory(),            # 内存不超过 baseline 1.5x
        ]
        return VerificationResult(checks)
```

### 2.3 失败处理

```
候选算子 → Verification Gate
  │
  ├── 全部通过 → 进入 Test Executor
  │
  ├── 失败（可修复类，如接口不匹配/单元测试未通过）
  │     → 带结构化错误信息返回 Designer
  │     → Designer 修复（最多重试 2 次）
  │     → 3 次均失败 → 丢弃，记录 failure_mode 到 Registry
  │
  └── 失败（不可修复类，如 feasibility 破坏/objective 不一致）
        → 直接丢弃
        → 记录到 Registry，标记 "critical_failure"
        → 如果同一 spec 连续 3 个候选都 critical_failure
          → 反馈给 Architect 重新审视 spec
```

### 2.4 Spec 必须附带验证资源

Architect 输出的 operator\_spec.md 必须包含：

```yaml
verification:
  unit_tests:
    - test_empty_solution_returns_empty
    - test_single_route_basic
    - test_respects_capacity_constraint
  feasibility_instances:
    - small_10nodes.json
    - small_20nodes_tight_tw.json
    - small_15nodes_heterogeneous.json
  complexity_baseline:
    reference_operator: RandomDestroy
    max_ratio: 2.0
  forbidden_side_effects:
    - "不得修改 solution.global_penalty_state"
    - "不得调用 route.recalculate_all()（性能禁区）"
```

---

## 3. 优先项 B：Experiment Registry

### 3.1 定位

系统的"实验账本"。每次实验的完整 provenance，不可篡改。没有 Registry，所有"归因""日志""失败教训"都是不可复现的叙事。

### 3.2 数据模型

```yaml
experiment:
  id: "exp-2026-0330-001"
  timestamp: "2026-03-30T21:00:00+08:00"

  # 溯源
  hypothesis_id: "hyp-cluster-boundary-v3"
  branch_id: "branch-dense-destroy"
  parent_champion_id: "champ-20260329-baseline"
  directive_hash: "sha256:abc123..."

  # 代码
  operator_patch:
    file: "cluster_boundary_destroy_v3.py"
    code_hash: "sha256:def456..."
    diff_from_parent: "..."
  solver_hash: "sha256:ghi789..."   # solver 代码的 git commit
  config_hash: "sha256:jkl012..."   # solver 配置参数

  # 实验设置
  instance_split:
    version: "split-v2"
    screening: ["inst_01", "inst_02", ..., "inst_06"]
    dev_validation: ["inst_07", "inst_08", ..., "inst_12"]
    frozen_holdout: ["inst_13", "inst_14", ..., "inst_22"]
  seeds: [42, 137, 256]
  runtime_budget_per_run: 300  # seconds
  hardware: "AMD EPYC 7763 + 64GB"

  # 验证
  verification_result:
    passed: true
    checks: { import: pass, interface: pass, feasibility: pass, ... }

  # 结果
  results:
    screening:
      per_instance: { "inst_01": { "seed_42": 1523.4, ... }, ... }
      aggregate: { mean_gap: 0.012, median_gap: 0.009 }
    dev_validation: null  # 只在 validate 阶段填充
    frozen_holdout: null   # 只在 promotion 时填充

  # 元信息
  failure_mode: null       # 或 "crash" / "infeasible" / "timeout" / "objective_mismatch"
  designer_model: "gemini-flash"
  designer_retries: 1
  wall_clock_total: 2847   # seconds
```

### 3.3 不可篡改性

- 结果一旦写入不可修改（append-only log）
- 每条记录有前一条的 hash chain（轻量级，不需要区块链）
- Director 只能读 Registry，不能写（写入由 Executor/Auditor 完成）

### 3.4 查询接口

```python
registry.query(
    branch="branch-dense-destroy",
    status="completed",
    metric="screening.aggregate.median_gap",
    order="asc",
    limit=10
)

registry.compare(
    exp_a="exp-2026-0330-001",
    exp_b="exp-2026-0330-005",
    instances="screening",
    paired=True  # common random numbers
)

registry.failure_analysis(
    branch="branch-dense-destroy",
    failure_types=["critical_failure", "verification_failed"]
)
```

---

## 4. 优先项 C：Validation 防泄漏（三级实验集）

### 4.1 问题

如果 Director 反复看 validation 的细粒度 breakdown（dense/sparse 分组）并据此调整策略，validation 就变成了隐性 training，promotion gate 的统计意义失效。

### 4.2 三级实验集设计

```
┌──────────────────────────────────────────────────────────┐
│  Level 1: Screening Set (6-10 instances)                  │
│                                                          │
│  用途：explore 阶段快速淘汰                                │
│  暴露级别：Director 可看完整结果 + 分组 breakdown           │
│  统计要求：无严格要求，仅做粗筛                             │
│  可重复使用：是                                            │
│  备注：承认这是"开发集"，Director 的策略调整基于此集        │
└──────────────────────────────────────────────────────────┘
                           │
                           │ Director 判断"有潜力"，进入 validate
                           ▼
┌──────────────────────────────────────────────────────────┐
│  Level 2: Dev Validation Set (6-10 instances)             │
│                                                          │
│  用途：validate 阶段的统计检验                             │
│  暴露级别：Director 只看 aggregate 指标                    │
│            (win_rate, median_delta, CI)                   │
│            ★ 不暴露 per-instance breakdown                │
│            ★ 不暴露 分组分析结果                            │
│  统计要求：Promotion Gate 的主要判据                        │
│  可重复使用：同一分支内可用 1 次；跨分支可复用              │
│  备注：Auditor 内部做分组分析，但只在 frozen 阶段           │
│        或 abandon 后才向 Director 披露细节                  │
└──────────────────────────────────────────────────────────┘
                           │
                           │ Dev Validation 通过 Promotion Gate
                           ▼
┌──────────────────────────────────────────────────────────┐
│  Level 3: Frozen Holdout Set (10+ instances)              │
│                                                          │
│  用途：最终确认，防止 screening + dev 上的过拟合            │
│  暴露级别：Director 只看 pass/fail + aggregate gap         │
│            ★ 永不暴露 per-instance 或分组信息              │
│  统计要求：win_rate ≥ 2/3, median_delta ≥ min_practical   │
│  使用次数：整个研究过程中最多使用 3-5 次                    │
│  备注：每次使用都记录在 Registry 中                         │
└──────────────────────────────────────────────────────────┘
```

### 4.3 信息流控制矩阵

| 信息类型                             | Screening   | Dev Validation | Frozen Holdout    |
| -------------------------------- | ----------- | -------------- | ----------------- |
| Per-instance 结果                  | Director 可见 | Auditor 内部     | 永不暴露              |
| 分组 breakdown                     | Director 可见 | Auditor 内部     | 永不暴露              |
| Aggregate (win\_rate, median\_Δ) | Director 可见 | Director 可见    | Director 可见       |
| CI / bootstrap interval          | 可选          | Director 可见    | Director 可见       |
| Pass/Fail 判定                     | 无门槛         | Promotion Gate | Confirmation Gate |

### 4.4 Subgroup 分析预注册

为防止事后切片找故事（p-hacking），所有分组维度必须在研究启动时预注册：

```yaml
preregistered_subgroups:
  - dimension: "distribution_density"
    categories: ["dense", "sparse", "mixed"]
    definition: "avg_nearest_neighbor_distance < median → dense"

  - dimension: "instance_scale"
    categories: ["small(<100)", "medium(100-500)", "large(>500)"]

  - dimension: "constraint_tightness"
    categories: ["tight(capacity_util>0.9)", "moderate", "loose"]

# 研究过程中新增分组维度需要：
#   1. Director 提出理由
#   2. 记录在 Registry 中
#   3. 该维度的分析结果降权处理（exploratory, not confirmatory）
```

---

## 5. 优先项 D：搜索空间扩展（算子 + 参数 + 策略联合搜索）

### 5.1 问题

只优化 operator 代码，忽略参数调优和选择策略，会导致：

- 结构上好的算子因默认参数不佳被冤杀
- "conditional promote" 无法落地（缺 gating policy）
- 不同分支的局部改进无法组合

### 5.2 三类搜索对象

```
┌─────────────────────────────────────────────────────────┐
│ Type 1: Structural Change（代码逻辑）                    │
│                                                         │
│ 由 Designer 生成，经 Verification Gate 验证              │
│ 示例：新的 destroy 算子代码                               │
│ 搜索代价：高（需要 LLM + 验证 + benchmark）              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Type 2: Parametric Change（参数/阈值/权重）              │
│                                                         │
│ 不需要 LLM，用贝叶斯优化/网格搜索                        │
│ 示例：destroy 的 k 值、相关性阈值、温度参数               │
│ 搜索代价：低（只需要 benchmark runs）                     │
│                                                         │
│ ★ 每个新 structural change 必须附带参数调优阶段           │
│   防止"好结构+烂参数"被冤杀                              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Type 3: Policy Change（选择/调度策略）                    │
│                                                         │
│ 由 Director 提出，Architect 翻译                         │
│ 示例："dense instance 用 ClusterDestroy，                │
│       sparse instance 用 RandomWalkDestroy"              │
│                                                         │
│ ★ "Conditional promote" 必须显式定义 gating policy       │
│   gating policy 本身也是搜索对象                         │
│   gating policy 也要过 Promotion Gate                    │
└─────────────────────────────────────────────────────────┘
```

### 5.3 搜索流程整合

```
一个完整的分支迭代:

1. Director: "尝试 cluster boundary destroy"
              (Structural hypothesis)

2. Architect → Designer → Verification Gate
   → 生成 3-5 个 structural 变体

3. Executor: 在 screening set 上快速评估
   → 选出 top-2 结构（不是 top-1，防止 winner's curse）

4. ★ Parametric tuning [v2 新增]
   → 对 top-2 结构，用贝叶斯优化搜索参数
   → 每个结构 20-50 次 solver run（不需要 LLM）
   → 选出最优参数配置

5. Director 判断是否进入 validate
   → 如果是：在 dev validation 上检验（带最优参数）
   → Promotion Gate

6. 如果 conditional promote:
   → ★ Policy search [v2 新增]
   → Director 提出 gating policy 假设
   → Architect 翻译为 instance classifier
   → 在 screening set 上验证 policy 效果
   → Policy 也要过 Promotion Gate
```

### 5.4 分支组合机制 \[v2 新增]

解决"A 分支的 destroy + B 分支的 repair 可能协同更好"的问题：

```
分支管理扩展:

1. 保留 Elite Archive（不只是单一 champion）
   archive = [champion, promoted_1, promoted_2, ...]

2. 允许"组合试验"
   Director 可以提出：
   "尝试将 Branch A 的 ClusterDestroy 与
    Branch B 的 GreedyRepair 组合"
   
   组合试验走标准 verify → screen → validate 流程

3. 新分支不仅可以从 champion 分叉，也可以从 archive 中任一 elite 分叉
   → 降低路径依赖
   → 增加搜索多样性

4. Branch Budget Manager（bandit 思想）
   → 根据各分支的 screening 表现动态分配算力
   → 高不确定性 + 高潜力的分支优先
   → 连续 2 轮 screening 无改善的分支降低优先级
```

---

## 6. 结构化记忆系统 \[v2 升级]

### 6.1 双层记忆

```
┌─────────────────────────────────────────────────────────┐
│  Fact Memory（事实层 · 不可改写）                         │
│                                                         │
│  内容：                                                  │
│  - 所有实验结果（来自 Registry）                          │
│  - 所有 patch / code diff                                │
│  - 所有验证结果（pass/fail + 错误类型）                   │
│  - 所有分支的生命周期事件                                 │
│                                                         │
│  写入权限：仅 Executor / Auditor / Verification Gate     │
│  读取权限：所有 Agent                                    │
│  修改权限：无（append-only）                              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Hypothesis Memory（假设层 · 可更新）                     │
│                                                         │
│  每条记录格式：                                          │
│  {                                                      │
│    "id": "hyp-003",                                     │
│    "statement": "聚类边界 destroy 在紧凑分布上优于随机",  │
│    "confidence": "medium",                              │
│    "supporting_evidence": ["exp-001", "exp-005"],       │
│    "contradicting_evidence": ["exp-008"],               │
│    "applicable_conditions": "density > threshold",      │
│    "status": "active",                                  │
│    "created_round": 3,                                  │
│    "last_updated_round": 7                              │
│  }                                                      │
│                                                         │
│  写入权限：仅 Director                                   │
│  约束：每次更新必须引用 Fact Memory 中的实验 ID           │
│  约束：confidence 只能基于 Auditor 的统计结论调整         │
│        不能仅基于 Director 的"直觉"                      │
└─────────────────────────────────────────────────────────┘
```

### 6.2 记忆压缩策略

Director 的 context 有限，不能无限追加日志。压缩规则：

```
每 5 轮执行一次记忆压缩：

1. Fact Memory：保持完整（在 Registry 中，不进 Director context）
   Director 只看 Auditor 生成的 aggregate summary

2. Hypothesis Memory：
   - status=abandoned 且 last_updated > 10 轮前 → 压缩为一行摘要
   - status=promoted → 保留完整
   - status=active → 保留完整

3. Director context 预算分配：
   - 当前活跃分支状态：~500 tokens
   - 最近 3 轮 statistical report：~1500 tokens
   - 活跃假设列表：~500 tokens
   - 关键失败教训（最近 5 条）：~500 tokens
   ────────────────────────
   总计：~3000 tokens（可控）
```

---

## 7. Agent 间通信协议 \[v2 半结构化]

### 7.1 Research Directive（Director → Architect）

```yaml
directive:
  id: "dir-007"
  round: 7
  branch: "branch-dense-destroy"
  action: "iterate"  # iterate | validate | new_branch | abandon | combine

  hypothesis:
    statement: "在聚类边界删除的基础上，增加时间窗松弛度加权，
                可以在紧凑分布上进一步改善 0.5%+"
    expected_improvement:
      target_instances: "dense distribution"
      expected_delta: ">= 0.5%"
    failure_alternatives:
      - "时间窗松弛度与距离的相关性可能抵消加权效果"
      - "加权计算可能引入不可接受的时间开销"

  scope:
    allowed_modules: ["destroy_operators"]
    forbidden_changes: ["repair_operators", "acceptance_criterion"]

  validation_requirement:
    min_screening_improvement: 0.3%
    proceed_to_validate_if: "screening win_rate >= 4/6"
```

### 7.2 Operator Spec（Architect → Designer）

```yaml
spec:
  id: "spec-007-a"
  directive_ref: "dir-007"
  branch: "branch-dense-destroy"

  task: "在 ClusterBoundaryDestroy v3 基础上，增加时间窗松弛度加权"

  interface:
    base_class: "BaseDestroyOperator"
    input: "Solution, int k, DestroyParams"
    output: "PartialSolution (removed_nodes: List[Node])"
    must_call_after: "solution.mark_modified()"

  context_code:
    - file: "operators/cluster_boundary_destroy_v3.py"  # 当前版本
    - file: "core/distance_matrix.py"  # 行 45-80，get_cluster_distances
    - file: "core/time_window.py"  # 行 12-30，get_tw_slack

  constraints:
    touched_interfaces: ["DestroyOperator.execute()"]
    required_invariants:
      - "所有返回的 removed_nodes 必须在 solution 中存在"
      - "不能删除 depot 节点"
    forbidden_side_effects:
      - "不得修改 solution.global_penalty_state"
    complexity_budget: "O(k * n) where n = total nodes"

  new_hyperparameters:
    - name: "tw_slack_weight"
      type: float
      range: [0.0, 1.0]
      default: 0.5
      description: "时间窗松弛度在选择权重中的占比"

  verification:
    unit_tests:
      - "test_removes_exactly_k_nodes"
      - "test_no_depot_removal"
      - "test_feasibility_preserved"
    feasibility_instances: ["small_10.json", "small_20_tight.json"]
    complexity_baseline:
      reference: "ClusterBoundaryDestroy_v3"
      max_ratio: 1.5
```

---

## 8. 完整搜索流程 \[v2]

```
Phase 0: 初始化
  ├── 人类提供：solver 代码 + 模块接口文档 + instance 集（三级划分）
  ├── 人类定义：预注册的 subgroup 维度
  ├── 系统生成：baseline champion 的 screening/dev/frozen 性能
  └── Registry 初始化

Phase 1: 研究迭代（重复直到停止条件）

  Round N:
  ┌─────────────────────────────────────────────────┐
  │ 1. Director 读取:                                │
  │    - Round N-1 的 statistical_report             │
  │    - 活跃分支状态                                │
  │    - Hypothesis Memory（活跃假设）               │
  │    - 最近失败教训                                │
  │                                                 │
  │    Director 输出:                                │
  │    - 更新 Hypothesis Memory                      │
  │    - research_directive                          │
  │      (action: iterate/validate/new/abandon/combine)│
  └────────────────────┬────────────────────────────┘
                       ▼
  ┌─────────────────────────────────────────────────┐
  │ 2. Architect 接收 directive                      │
  │    - 耦合分析                                    │
  │    - 输出 operator_spec（含验证资源）             │
  └────────────────────┬────────────────────────────┘
                       ▼
  ┌─────────────────────────────────────────────────┐
  │ 3. Designer(s) 按 spec 生成 3-5 变体             │
  └────────────────────┬────────────────────────────┘
                       ▼
  ┌─────────────────────────────────────────────────┐
  │ 4. ★ Verification Gate                           │
  │    通过 → 继续                                   │
  │    失败 → 反馈 Designer 重试（≤2次）             │
  │    全部失败 → 反馈 Architect 审视 spec           │
  └────────────────────┬────────────────────────────┘
                       ▼
  ┌─────────────────────────────────────────────────┐
  │ 5. Executor: Screening (training set)            │
  │    - 多 seed, Common Random Numbers              │
  │    - 选 top-2 结构（非 top-1）                   │
  └────────────────────┬────────────────────────────┘
                       ▼
  ┌─────────────────────────────────────────────────┐
  │ 6. ★ Parametric Tuning (无 LLM)                  │
  │    - 对 top-2 结构做贝叶斯优化                    │
  │    - 20-50 runs per structure                    │
  │    - 选出各自最优参数                             │
  └────────────────────┬────────────────────────────┘
                       ▼
  ┌─────────────────────────────────────────────────┐
  │ 7. Auditor: Screening Report                     │
  │    - aggregate + breakdown → Director 可见        │
  │    - 记录到 Registry                             │
  └────────────────────┬────────────────────────────┘
                       ▼
              Director 判断是否 validate
                       │
           ┌───────────┴───────────┐
           │ YES                   │ NO → 回到 Round N+1
           ▼                       │
  ┌────────────────────┐           │
  │ 8. Executor:       │           │
  │    Dev Validation   │           │
  │    (多 seed, CRN)  │           │
  └────────┬───────────┘           │
           ▼                       │
  ┌────────────────────┐           │
  │ 9. Auditor:        │           │
  │    Promotion Gate   │           │
  │    win_rate ≥ 2/3  │           │
  │    median_Δ ≥ min  │           │
  │    报告 CI         │           │
  │    ★ 只给 Director │           │
  │      aggregate     │           │
  └────────┬───────────┘           │
           │                       │
     ┌─────┴─────┐                 │
     │ PASS      │ FAIL            │
     ▼           ▼                 │
  ┌──────┐  ┌──────────┐          │
  │Frozen│  │Record    │          │
  │Holdout│ │failure   │──────────┘
  │ test │  │lessons   │
  └──┬───┘  └──────────┘
     │
     │ Frozen: win_rate ≥ 2/3
     │ Director 只看 pass/fail + aggregate
     ▼
  ┌──────────┐
  │ PROMOTE  │ → squash merge to champion / add to elite archive
  └──────────┘

Phase 2: 停止条件（任一触发）
  - 连续 M 轮（建议 M=5）screening 无显著改善
  - Frozen holdout 使用次数达到上限（3-5 次）
  - 算力预算耗尽
  - 新候选通过 Verification Gate 的比例连续 3 轮 < 20%
  - Director 判断搜索空间已充分覆盖（需记录理由）
```

---

## 9. 与现有方法的定位对比 \[v2]

| 维度    | EoH/ReEvo        | AILS-AHD           | **Multi-Agent Autoresearch v2** |
| ----- | ---------------- | ------------------ | ------------------------------- |
| 核心贡献  | LLM 演化 heuristic | LLM 优化 solver 关键组件 | **heuristic 设计作为实验科学**          |
| 搜索对象  | 算子代码             | 算子代码               | 算子 + 参数 + 选择策略                  |
| 正确性保证 | 无                | 无                  | Verification Gate               |
| 实验可追溯 | 无                | 无                  | Experiment Registry             |
| 统计严谨  | fitness 排序       | fitness 排序         | 三级验证 + Promotion Gate + CI      |
| 过拟合防护 | 无                | 无                  | 信息流隔离 + frozen holdout          |
| 记忆    | 无                | 无                  | Fact + Hypothesis 双层记忆          |
| 可扩展性  | 小 solver         | 中等 solver          | 大 solver（上下文隔离）                 |
| 分支管理  | 种群隐式             | 无                  | 显式分支 + elite archive            |

---

## 10. 待验证假设与 Ablation 计划

为证明系统价值不是"复杂度堆叠"，必须做以下对照实验：

| 实验                                                 | 目的                           |
| -------------------------------------------------- | ---------------------------- |
| A1: Single strong LLM + 同样的 Verification + Auditor | 验证：收益来自实验治理还是 multi-agent    |
| A2: Multi-agent 但去掉 Promotion Gate                 | 验证：统计闸门的贡献                   |
| A3: Multi-agent 但去掉 Verification Gate              | 验证：正确性保证的贡献                  |
| A4: Multi-agent 但去掉 Architect 层                    | 验证：架构层的必要性                   |
| A5: 人类手工 spec + Designer LLM coding                | 验证：Director+Architect 的自动化价值 |
| A6: 同算力预算下的人工 baseline                             | 验证：整个系统 vs 人类专家的性价比          |

---

## 11. 开放问题（v2 遗留）

1. **接口文档的半自动化生成**：能否用 LLM 从 solver 代码自动提取接口文档初稿，人类审核确认？
2. **Branch Budget Manager 的具体算法**：UCB1？Thompson Sampling？需要实验确定。
3. **跨 solver 迁移性**：在 solver A 上训练的 Hypothesis Memory 能否迁移到 solver B？
4. **Verification Gate 的测试用例自动生成**：当前依赖 Architect 提供，能否自动化？
5. **多目标场景**：当 objective 是字典序多目标时，Promotion Gate 如何适配？
6. **实时/在线场景**：如果 solver 需要处理动态 instance，实验框架如何适配？

#

## 一些同行的以意见
这里有一部分网上同行的帖子，可以参考：
大多数人去年还是保持着严谨谦卑态度看待agent这一新技术的诞生。但今年二三月份开始，随着OpenClaw等等工具大幅度拉低了agent的使用门槛，fomo情绪疯狂席卷所有人。
	
这其中，以“自动科研”为重灾区，让广大研究生着实受到了严重精神冲击。这篇帖子我会列举目前小红书上的主流自动科研工具，逐一分析，为什么很多帖子都是虚假，夸张，贩卖焦虑之流[生气R]还我们研究生一个清净！
	
1️⃣首先是大名鼎鼎的Andrej Karpathy的AutoResearch，已经有60+k⭐。核心机制其实很简单：
edit code → run experiment → evaluate metric → keep / revert → repeat
本质上是训练工程优化。局部搜索，范围限于代码，不动数据，不改问题定义，需要明确metric。能实现的都是小trick，10年前的AutoML系统几乎已经做到了。
	
2️⃣ AutoResearchClaw。做的是多batch / 多agent，试图通过增强 exploration，跳出单轨搜索，complexity 爆炸，但收益不稳定。本质上是用token和你的GPU来换更大的搜索空间。十倍实验量，性能涨0.03%，还没法写进论文，因为大搜索空间引起混乱，人都难理解[再见R]
	
3️⃣ ARIS (Auto-Research-In-Sleep)。把 autoresearch loop 接到 Claude Code / dev workflow，工程化你的研究，通过debugging/tuning/ranking来做典型 hill-climbing。Ablation工厂罢了，brute-force换性能。
	
4️⃣ ScienceClaw / MedgeClaw / Dr Claw。Skills大集合，把科研能力拆成 API + tool，强依赖 human prompt，做的只是科研流程管理。
	
5️⃣ EvoScientist。真正沾边的一个，尝试真的出idea并解决问题，但evaluation 还是 proxy，根本没有科研里的“定义问题”并评估的能力。
	让人感觉做这些项目的人反而最焦虑，没有真正的科研，全是短期工程




# 以下是最新一轮审核意见：

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
