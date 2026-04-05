# OR-AutoResearch Agent Framework — GPT-5.4-Pro 审核包

*用途：将本文档完整内容提交给 GPT-5.4-Pro 进行深度审核*
*Date: 2026-04-02*

---

## 审核任务

你是 GPT-5.4-Pro，担任架构审核角色。请对以下 OR-AutoResearch Agent Framework v0.1 Blueprint v2 进行深度审核。

请从以下维度逐一审核：

1. **架构完整性**：v2 补了 6 个组件，是否真正补齐了 v1 的问题？还有关键遗漏吗？
2. **三层控制模型**：Creative→Contract→Decision 的边界是否足够硬？LLM 是否仍有隐蔽决策路径？
3. **实验协议层**：seed 策略/配对评估/回归检测的设计是否合理？能否保证研究结论可信？
4. **可行性**：4 周实现 v2 完整 scope 是否现实？哪些模块难度仍被低估？
5. **差异化**：5 个结构性差异点是否足够强？能否撑住论文级 contribution？
6. **Top-3 仍存在的风险**：v2 引入了哪些新问题？
7. **学术价值**：发顶会/顶刊论文还缺什么？ablation 设计、实验要求？

重点关注：**v2 是否真正解决了 v1 的问题**、**是否引入新问题**、**最需要改进的 top-3**。

---

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
  ├── failure analysis        → 必须经过 allowed_fields 过滤
  └── branch direction        → 必须经过 novelty 检查
          │
          ▼
Layer B: Contract Layer（确定性约束）
  ├── JSON schema validation
  ├── file whitelist enforcement
  ├── AST / interface compliance
  ├── patch size limit（max 200 行）
  ├── forbidden-file check（benchmark harness 不可改）
  └── analysis field filter（只允许写 suspected_failure_mode 等字段）
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
  │     while should_continue():
  │       branch = scheduler.select()
  │       context = context_manager.build(branch)
  │       if EXPLORE: hypothesis→[Contract]→code→[Contract]→verify
  │       if VALIDATE: frozen code, fresh cases only
  │       label = experiment_protocol.evaluate()
  │       branch_controller.decide(label)
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
  │     win_rate ≥ 2/3 + median_delta ≥ 阈值，N ≥ 6，含 retry
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
  │     每次实验：hypothesis_id → code_hash → protocol_version
  │                → raw_metrics → decision_trace
  │
  └── Termination（多重终止）【v2 新增】
        硬预算 + 停滞检测 + 无活跃分支
```

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
```

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

| 周 | 核心任务 |
|---|---------|
| W1 | 基础设施：promotion_gate, experiment_protocol, branch_controller, failure_taxonomy, runtime_isolation, artifact_lineage |
| W2 | 三层控制+核心循环：contract_layer, context_manager, loop.py, LLM client, prompt 模板 |
| W3 | 工具层+Benchmark：code_verify（多层管线）, benchmark_run, 准备 VRP destroy operator 验证问题 |
| W4 | 端到端验证：≥10 轮实验，验收标准全检查 |

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

| # | 差异点 | FunSearch/EoH/ReEvo | 本框架 |
|---|--------|-------------------|--------|
| 1 | 假设对象 | 隐式（代码即假设） | 显式 HypothesisRecord，可审计可复用 |
| 2 | 分支治理 | 无（单线或种群） | explore→validate→promote 状态机 |
| 3 | 验证分离 | 无（评估即验证） | frozen code + fresh cases 二阶段 |
| 4 | 统计门槛 | 点估计选择 | win_rate + median_delta + retry protocol |
| 5 | 失败记忆 | 无或弱 | 结构化 taxonomy + blacklist |

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
