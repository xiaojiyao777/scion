# Scion Framework — Engineering Architecture v1

*Date: 2026-04-05*
*Parent: scion-architecture-v3.md, scion-v0.1-design.md*
*Status: Engineering Design — Ready for Implementation*

---

## 1. 系统概览

### 1.1 Scion 与 Surrogate Solver 的关系

```
┌─────────────────────────────────────────────────┐
│                   Scion Framework                │
│  (控制层：搜索、治理、验证、决策)                    │
│                                                   │
│  ┌───────┐  ┌──────────┐  ┌───────────┐          │
│  │Creative│→│ Contract  │→│Verification│→ ...     │
│  │ Layer  │  │   Gate    │  │   Gate     │          │
│  └───────┘  └──────────┘  └───────────┘          │
│        ↕                        ↕                  │
│  ┌─────────────────────────────────────┐          │
│  │         Solver Runner               │          │
│  │  (调用 surrogate solver 子进程)       │          │
│  └─────────────────────────────────────┘          │
└─────────────────────┬───────────────────────────┘
                      │ subprocess
                      ▼
┌─────────────────────────────────────────────────┐
│              Surrogate Solver                    │
│  (被优化对象：VNS + Solution Pool + Operators)    │
│                                                   │
│  solver.py → greedy_init → vns(operators) → result│
│                                                   │
│  operators/                                       │
│  ├── swap_orders.py     (Scion 可修改/新增/删除)   │
│  ├── move_order.py                                │
│  ├── destroy_rebuild.py                           │
│  ├── merge_vehicles.py                            │
│  ├── change_vehicle_type.py                       │
│  └── split_vehicle.py                             │
│                                                   │
│  oracle.py  (冻结：feasibility + objective)        │
│  models.py  (冻结：数据模型)                        │
│  vns.py     (冻结：VNS 引擎)                       │
│  pool.py    (冻结：Solution Pool)                  │
└─────────────────────────────────────────────────┘
```

**关键关系**：
- Scion 是**控制层**，surrogate solver 是**被优化对象**
- Scion 通过修改 `operators/` 目录下的文件来改变 solver 行为
- Scion 通过子进程调用 `solver.py`，收集 JSON 输出
- `oracle.py`、`models.py`、`vns.py`、`pool.py`、`config.py` 均为**冻结文件**，Scion 不可修改

### 1.2 端到端数据流

```
Campaign Init
    │
    ▼
┌─ Scheduler 选择分支 ─────────────────────────────────────────────────┐
│                                                                       │
│  ① Branch Controller 确定代码基线                                      │
│       ↓                                                               │
│  ② Context Manager 构建上下文                                          │
│       ↓                                                               │
│  ③ Creative Layer: Round 1 → HypothesisProposal                      │
│       ↓                                                               │
│  ④ Contract Gate: validate_hypothesis                                 │
│       ↓ (passed)                                                      │
│  ⑤ Creative Layer: Round 2 → PatchProposal                           │
│       ↓                                                               │
│  ⑥ Contract Gate: validate_patch                                      │
│       ↓ (passed)                                                      │
│  ⑦ Workspace Materializer: 写入候选 workspace                         │
│       ↓                                                               │
│  ⑧ Verification Gate: syntax → interface → unit test → regression     │
│       → feasibility → objective recompute → state leak → wall-clock   │
│       ↓ (passed)                                                      │
│  ⑨ Canary Regression Check                                           │
│       ↓ (passed)                                                      │
│  ⑩ Experiment Protocol: Screening / Validation / Frozen               │
│       ↓                                                               │
│  ⑪ Safe Feature Extractor → DecisionFeatures                          │
│       ↓                                                               │
│  ⑫ Decision Engine → Promote / Iterate / Abandon                     │
│       ↓                                                               │
│  ⑬ Branch Controller: apply state transition                          │
│       ↓                                                               │
│  ⑭ Lineage Registry: record full event                                │
│                                                                       │
└── 回到 Scheduler ────────────────────────────────────────────────────┘
```

### 1.3 核心状态机

#### Branch 生命周期

```
                    NEW
                     │ create
                     ▼
                  EXPLORE ◄──────────────────────┐
                  │  │  │                         │
     screen_pass  │  │  │ screen_fail/unclear    │ iterate
                  │  │  └────────────────────────┘
                  │  │
                  │  └──► EXPLORE_EXPAND ──expand_done──► (重入 EXPLORE 判定)
                  ▼
            READY_VALIDATE
                  │ schedule
                  ▼
              VALIDATING
              │   │   │
  validate_pass│  │   │validate_fail
              │   │   └──► ABANDONED
              │   └──► VALIDATING_EXPAND ──expand_done──► (重入 VALIDATING 判定)
              ▼
           READY_FROZEN
              │ schedule
              ▼
          FROZEN_TESTING
           │         │
  frozen_pass│        │frozen_fail
           ▼         └──► ABANDONED
        PROMOTED

任意活跃状态 ──champion_changed──► STALE
任意活跃状态 ──budget_exhausted──► ABANDONED
任意活跃状态 ──infra_incident────► BLOCKED_INFRA
```

#### Experiment 生命周期

```
CREATED → RUNNING → COMPLETED
                  → FAILED_INFRA (可 infra retry)
                  → FAILED_VERIFICATION (不可 retry)
```

---

## 2. 模块划分

### 2.1 Campaign Manager

**对应 v3 架构**：Campaign Controller (§3, §18 主循环)

**职责边界**：
- ✅ 初始化 campaign（加载 problem spec、protocol config、split manifest）
- ✅ 驱动主循环：Scheduler → Branch → Proposal → Gate → Protocol → Decision
- ✅ 管理 campaign 级状态（champion、frozen 使用计数、全局预算）
- ✅ 终止条件判断
- ❌ 不直接执行任何检查/评估（委托给子模块）
- ❌ 不与 LLM 直接交互

**公开接口**：

```python
class CampaignManager:
    def __init__(self, problem_spec: ProblemSpec, protocol_config: ProtocolConfig,
                 split_manifest: SplitManifest, seed_ledger: SeedLedger) -> None: ...

    def run(self, max_rounds: Optional[int] = None) -> CampaignReport:
        """执行主循环直到终止条件满足或达到 max_rounds。"""
        ...

    def run_one_step(self) -> StepResult:
        """执行主循环的一步（用于调试和 mock 测试）。"""
        ...

    def get_state(self) -> CampaignState:
        """返回当前 campaign 状态快照（只读）。"""
        ...

    def should_continue(self) -> bool:
        """终止条件判断。"""
        ...
```

**依赖**：Branch Controller, Scheduler, Creative Layer, Contract Gate, Verification Gate, Experiment Protocol, Decision Engine, Safe Feature Extractor, Lineage Registry, Context Manager, Failure Router

### 2.2 Branch Controller

**对应 v3 架构**：Branch Controller 状态机 (§11)

**职责边界**：
- ✅ 创建新分支（基于当前 champion）
- ✅ 管理分支状态机转换
- ✅ 确定分支内代码基线（champion / last_clean / current）
- ✅ 标记所有活跃分支为 STALE（champion 变更时）
- ✅ 执行 stale reconcile（重新应用 patch → Contract → Verification → re-Screening）
- ❌ 不执行实际的验证/评估（委托）
- ❌ 不直接与 LLM 交互

**公开接口**：

```python
class BranchController:
    def create_branch(self, champion: ChampionState) -> Branch:
        """创建新分支，基于当前 champion。"""
        ...

    def apply_decision(self, branch_id: str, decision: Decision) -> None:
        """根据决策执行状态转换。"""
        ...

    def mark_all_stale(self, new_champion_id: int) -> list[str]:
        """Champion 更新时标记所有活跃分支为 STALE，返回受影响的 branch_id 列表。"""
        ...

    def get_code_base(self, branch_id: str) -> CodeBase:
        """获取分支当前应使用的代码基线。"""
        ...

    def record_verification_result(self, branch_id: str, passed: bool,
                                     code_hash: str) -> None:
        """记录 verification 结果，更新 last_clean_code_hash。"""
        ...

    def next_stage(self, branch_id: str) -> ExperimentStage:
        """根据分支当前状态确定下一个实验阶段。"""
        ...

    def get_active_branches(self) -> list[Branch]:
        """返回所有活跃分支。"""
        ...

    def get_branch(self, branch_id: str) -> Branch:
        """获取指定分支的完整状态。"""
        ...
```

**依赖**：Storage（持久化分支状态）

### 2.3 Creative Layer

**对应 v3 架构**：Proposal Engine (§5), Context Manager (§15)

**职责边界**：
- ✅ Round 1: 生成 HypothesisProposal（结构化 JSON）
- ✅ Round 2: 生成 PatchProposal（完整文件代码）
- ✅ Fix: Verification 轻度失败后的修复尝试
- ✅ 管理 prompt 模板渲染
- ✅ LLM API 调用封装（超时、重试、格式校验）
- ❌ 不做任何决策
- ❌ 不访问 validation/frozen 数据
- ❌ 不直接调用 Contract/Verification Gate

**公开接口**：

```python
class CreativeLayer:
    def __init__(self, llm_client: LLMClient, prompt_templates: PromptTemplates,
                 schemas: ResponseSchemas) -> None: ...

    def generate_hypothesis(self, context: HypothesisContext) -> HypothesisProposal:
        """Round 1: 基于上下文生成结构化假设。
        Raises: LLMTimeoutError, LLMFormatError, LLMRetryExhaustedError
        """
        ...

    def generate_code(self, context: CodeContext) -> PatchProposal:
        """Round 2: 基于假设生成完整文件代码。
        Raises: LLMTimeoutError, LLMFormatError, LLMRetryExhaustedError
        """
        ...

    def fix_code(self, context: FixContext) -> PatchProposal:
        """修复 verification 轻度失败。
        Raises: LLMTimeoutError, LLMFormatError, LLMRetryExhaustedError
        """
        ...


class ContextManager:
    def build_hypothesis_context(self, branch: Branch, champion: ChampionState,
                                  problem_spec: ProblemSpec,
                                  hypothesis_store: HypothesisStore,
                                  sibling_branches: list[Branch]) -> HypothesisContext:
        """构建 Round 1 的 LLM 输入上下文。
        暴露：problem spec、champion 代码、分支历史、失败假设、兄弟分支摘要。
        不暴露：validation/frozen 数据。
        """
        ...

    def build_code_context(self, branch: Branch, hypothesis: HypothesisProposal,
                            champion: ChampionState,
                            problem_spec: ProblemSpec) -> CodeContext:
        """构建 Round 2 的 LLM 输入上下文。
        暴露：problem spec、假设、champion 代码、target 文件、接口规范。
        不暴露：历史结果、兄弟分支。
        """
        ...

    def build_fix_context(self, branch: Branch, patch: PatchProposal,
                           verification_result: VerificationResult,
                           problem_spec: ProblemSpec) -> FixContext:
        """构建修复上下文（轻度 verification 失败后）。"""
        ...
```

**依赖**：LLM Client, Prompt Templates, Hypothesis Store

### 2.4 Contract Gate

**对应 v3 架构**：Contract Gate (§9), Gate 1

**职责边界**：
- ✅ HypothesisProposal 的结构校验：JSON schema、change_locus 合法性、action-target 一致性
- ✅ PatchProposal 的边界检查：文件白名单、frozen files 保护、AST 接口签名、import 白名单、敏感 API 拦截
- ✅ 新颖性检查（与活跃分支 + blacklist 比较）
- ❌ 不做语义正确性检查（Verification 的职责）
- ❌ 不执行代码

**公开接口**：

```python
class ContractGate:
    def __init__(self, problem_spec: ProblemSpec) -> None: ...

    def validate_hypothesis(self, hypothesis: HypothesisProposal,
                             active_hypotheses: list[HypothesisRecord],
                             blacklist: list[HypothesisRecord]) -> ContractResult:
        """校验假设提案的结构合规性。"""
        ...

    def validate_patch(self, patch: PatchProposal) -> ContractResult:
        """校验代码补丁的边界合规性。"""
        ...


@dataclass(frozen=True)
class ContractResult:
    passed: bool
    checks: tuple[CheckResult, ...]   # 每项检查的结果
    failure_reason: Optional[str]      # 首个失败原因（若有）

    @staticmethod
    def from_checks(checks: list[CheckResult]) -> ContractResult: ...
```

**依赖**：ProblemSpec（文件白名单、import 白名单、接口签名定义）

### 2.5 Verification Gate

**对应 v3 架构**：Verification Gate (§10), Gate 2

**职责边界**：
- ✅ 8 项 P0 动态检查（fail-fast 顺序）：
  1. syntax/import 检查
  2. interface compliance（运行时确认 Operator 子类签名）
  3. unit tests
  4. regression tests
  5. feasibility oracle（在 canary case 上调用 `oracle.check_feasibility`）
  6. objective recompute（`oracle.recompute_objective` vs solver 报告值）
  7. state leak（同输入双跑比较）
  8. wall-clock guard（不超过 champion 的 N 倍）
- ❌ 不做统计显著性评估（Protocol 的职责）
- ❌ 不做决策

**公开接口**：

```python
class VerificationGate:
    def __init__(self, problem_spec: ProblemSpec, runner: Runner) -> None: ...

    def run(self, candidate_workspace: str, champion_workspace: str) -> VerificationResult:
        """按 fail-fast 顺序执行所有 P0 检查。"""
        ...

    def check_syntax(self, workspace: str) -> CheckResult: ...
    def check_interface(self, workspace: str) -> CheckResult: ...
    def check_unit_tests(self, workspace: str) -> CheckResult: ...
    def check_regression_tests(self, workspace: str) -> CheckResult: ...
    def check_feasibility(self, workspace: str) -> CheckResult: ...
    def check_objective_recompute(self, workspace: str) -> CheckResult: ...
    def check_state_leak(self, workspace: str) -> CheckResult: ...
    def check_wall_clock(self, workspace: str, champion_time_ms: float) -> CheckResult: ...


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    checks: tuple[CheckResult, ...]
    failure_severity: Optional[Literal["light", "heavy"]]  # light=可 LLM fix, heavy=不可
    first_failure: Optional[str]

    @staticmethod
    def from_checks(checks: list[CheckResult]) -> VerificationResult: ...


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    severity: Literal["light", "heavy"]
    detail: str
    elapsed_ms: int
```

**依赖**：Runner（子进程执行）, ProblemSpec（oracle 脚本路径、测试路径）

### 2.6 Experiment Protocol

**对应 v3 架构**：Experiment Protocol (§8)

**职责边界**：
- ✅ Canary Regression Check（安全 veto）
- ✅ 三级实验执行：Screening → Validation → Frozen Holdout
- ✅ 配对评估（A/B：candidate solver vs champion solver）
- ✅ 字典序多目标比较
- ✅ 统计计算（win_rate、median_delta、bootstrap CI）
- ✅ 暴露控制（不同阶段返回不同详细度的结果）
- ✅ Split 管理和 Seed 管理
- ❌ 不做决策（只产出统计结果）
- ❌ 不修改分支状态

**公开接口**：

```python
class ExperimentProtocol:
    def __init__(self, protocol_config: ProtocolConfig,
                 split_manager: SplitManager, seed_ledger: SeedLedger,
                 runner: Runner) -> None: ...

    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        """运行 canary regression check。Veto-only，不做改善证据。"""
        ...

    def run_experiment(self, stage: ExperimentStage, candidate_ws: str,
                       champion_ws: str, hypothesis_action: str,
                       expand: bool = False) -> ProtocolResult:
        """执行指定阶段的配对评估实验。"""
        ...


class SplitManager:
    def __init__(self, manifest: SplitManifest) -> None: ...
    def get_cases(self, stage: ExperimentStage) -> list[str]: ...
    def validate_disjoint(self) -> bool: ...

class SeedLedger:
    def __init__(self, ledger: SeedLedgerConfig) -> None: ...
    def get_seeds(self, stage: ExperimentStage) -> list[int]: ...


@dataclass(frozen=True)
class ProtocolResult:
    stage: ExperimentStage
    stats: EvalStats                  # 聚合统计
    gate_result: GateResult           # 门控判定
    exposed: ExposedResult            # 按暴露控制过滤后的结果（可回喂 LLM）
    raw_metrics_ref: str              # 指向完整原始数据的路径（存入 lineage）

@dataclass(frozen=True)
class EvalStats:
    n_cases: int
    wins: int
    losses: int
    ties: int
    win_rate: float
    median_delta: float
    ci_low: float
    ci_high: float

@dataclass(frozen=True)
class GateResult:
    outcome: Literal["pass", "fail", "unclear", "expand"]
    reason_codes: tuple[str, ...]

@dataclass(frozen=True)
class CanaryResult:
    passed: bool
    reason: Optional[str]
```

**依赖**：Runner（子进程执行 solver）, SplitManager, SeedLedger

### 2.7 Decision Engine

**对应 v3 架构**：Decision Engine (§4, Layer B)

**职责边界**：
- ✅ 基于 DecisionFeatures（纯数值/枚举）做确定性决策
- ✅ 按阶段应用不同门控阈值
- ✅ 输出 Decision 枚举值 + 原因码
- ❌ **绝对不读取任何 LLM 自由文本**
- ❌ 不读取 per-case 原始数据
- ❌ 不执行任何 LLM 调用

**公开接口**：

```python
class DecisionEngine:
    def __init__(self, gate_thresholds: GateThresholds) -> None: ...

    def decide(self, features: DecisionFeatures) -> DecisionOutcome:
        """纯确定性决策。输入必须是 DecisionFeatures（无自由文本）。"""
        ...


@dataclass(frozen=True)
class DecisionOutcome:
    decision: Decision
    reason_codes: tuple[str, ...]
    features_snapshot: DecisionFeatures  # 决策时的输入快照（审计用）
```

**依赖**：无（纯函数，只依赖 GateThresholds 配置）

### 2.8 Safe Feature Extractor (Decision Input Guard)

**对应 v3 架构**：Safe Feature Extractor (§4.2)

**职责边界**：
- ✅ 从 ContractResult、VerificationResult、CanaryResult、ProtocolResult 中提取纯数值/枚举特征
- ✅ 构造 DecisionFeatures（frozen dataclass）
- ✅ **严格校验：输出不含任何自由文本字段**
- ❌ 不做决策
- ❌ 不访问 LLM 输出

**公开接口**：

```python
class SafeFeatureExtractor:
    def extract(self, branch: Branch, contract: ContractResult,
                verification: VerificationResult, canary: CanaryResult,
                protocol: ProtocolResult,
                budget: BudgetState) -> DecisionFeatures:
        """
        从各阶段结果中提取 DecisionFeatures。
        返回值为 frozen dataclass，所有字段均为数值或枚举。

        Invariant: 返回类型经过编译时 + 运行时双重校验，
                   不含 str 类型字段（branch_id 和 stage 除外，
                   且 stage 为 Literal 枚举）。
        """
        ...


@dataclass(frozen=True)
class DecisionFeatures:
    branch_id: str                                           # 标识用，不参与决策逻辑
    hypothesis_action: Literal["modify", "create_new", "remove"]
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
    recent_failure_codes: tuple[str, ...]                    # 枚举值元组
    budget_remaining_ratio: float
```

**依赖**：无（纯转换函数）

### 2.9 Operator Registry & Pool Manager

**对应 v3 架构**：算子池管理 (§6)

**职责边界**：
- ✅ 管理算子池配置：add / remove / modify
- ✅ 构建 candidate pool（champion pool ± 变更）
- ✅ 导出 registry（供 solver 启动时读取）
- ✅ 权重归一化
- ❌ 不执行算子代码
- ❌ 不做动态自适应权重更新（v0.1 冻结）

**公开接口**：

```python
class PoolManager:
    def __init__(self, initial_pool: dict[str, OperatorConfig]) -> None: ...

    def build_candidate_pool(self, champion_pool: dict[str, OperatorConfig],
                              hypothesis: HypothesisProposal,
                              patch: PatchProposal) -> dict[str, OperatorConfig]:
        """根据 hypothesis action 构造 candidate pool。"""
        ...

    def export_registry(self, pool: dict[str, OperatorConfig],
                         target_dir: str) -> str:
        """导出为 registry.yaml 到指定目录，返回文件路径。"""
        ...


@dataclass
class OperatorConfig:
    name: str
    file_path: str                # 相对于 operators/ 的路径
    category: str                 # order_level | vehicle_level
    weight: float
    class_name: str               # Python 类名
```

**依赖**：无

### 2.10 Solver Runner

**对应 v3 架构**：Runtime Isolation (§16), Runner 抽象

**职责边界**：
- ✅ 在独立子进程中执行 solver
- ✅ 资源限制（timeout、memory）
- ✅ 环境变量净化
- ✅ 收集 JSON 输出、解析为 SolverResult
- ✅ 捕获 infra 故障（subprocess timeout、OOM、crash）
- ❌ 不做结果判断（由 Verification/Protocol 负责）

**公开接口**：

```python
class Runner(Protocol):
    def run_solver(self, workdir: str, instance_path: str, seed: int,
                   time_limit_sec: int, registry_path: str) -> RunResult:
        """在隔离环境中运行 solver，返回执行结果。"""
        ...


class LocalSubprocessRunner:
    """MVP 实现：本地子进程 + resource 限制。"""

    def __init__(self, limits: ResourceLimits) -> None: ...

    def run_solver(self, workdir: str, instance_path: str, seed: int,
                   time_limit_sec: int, registry_path: str) -> RunResult:
        ...


@dataclass(frozen=True)
class RunResult:
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: int
    output: Optional[SolverOutput]     # 解析后的 JSON 输出（success=True 时有效）
    error_category: Optional[str]      # "timeout" | "oom" | "crash" | None

@dataclass(frozen=True)
class SolverOutput:
    vehicles: dict                     # 原始 JSON
    assignment: dict
    objective: dict
    feasible: bool

@dataclass
class ResourceLimits:
    timeout_sec: int = 300
    memory_mb: int = 4096
    max_file_descriptors: int = 256
```

**依赖**：无外部模块依赖（使用标准库 subprocess + resource）

### 2.11 Workspace Materializer

**对应 v3 架构**：Workspace Materializer + Runtime Isolation (§16)

**职责边界**：
- ✅ 为每个分支创建独立 workspace（文件系统目录）
- ✅ 将 PatchProposal 物化为实际文件
- ✅ Champion snapshot 只读保护
- ✅ 清理 workspace（实验结束后）
- ❌ 不执行代码

**公开接口**：

```python
class WorkspaceMaterializer:
    def __init__(self, campaign_dir: str) -> None: ...

    def create_branch_workspace(self, branch_id: str,
                                 code_base: CodeBase) -> str:
        """创建分支 workspace，从 code_base 复制文件，返回 workspace 路径。"""
        ...

    def apply_patch(self, workspace: str, patch: PatchProposal) -> str:
        """将 patch 写入 workspace，返回新的 code hash。"""
        ...

    def create_champion_snapshot(self, champion: ChampionState,
                                  target_dir: str) -> str:
        """创建 champion 的只读快照，返回路径。"""
        ...

    def cleanup(self, workspace: str) -> None:
        """清理 workspace 临时文件。"""
        ...
```

**依赖**：无

### 2.12 Storage & Lineage

**对应 v3 架构**：Lineage Registry (§14)

**职责边界**：
- ✅ SQLite append-only 事件存储
- ✅ 记录完整的 ExperimentEvent
- ✅ 查询接口（by branch、hypothesis、failure 类型等）
- ✅ Champion 状态持久化
- ✅ Branch 状态持久化
- ✅ Campaign 状态持久化
- ✅ 代码快照持久化（JSON + 文件副本）
- ❌ 不做数据分析（由 CLI 查询后展示）

**公开接口**：

```python
class LineageRegistry:
    def __init__(self, db_path: str) -> None: ...

    def record_event(self, event: ExperimentEvent) -> str:
        """记录一条实验事件，返回 event_id。"""
        ...

    def record_decision(self, branch_id: str, features: DecisionFeatures,
                         decision: DecisionOutcome) -> None:
        """记录决策（与 event 关联）。"""
        ...

    def query_by_branch(self, branch_id: str) -> list[ExperimentEvent]: ...
    def query_by_hypothesis(self, hypothesis_id: str) -> list[ExperimentEvent]: ...
    def query_failures(self, category: Optional[str] = None) -> list[ExperimentEvent]: ...
    def get_campaign_summary(self) -> CampaignSummary: ...


class ChampionStore:
    def __init__(self, db_path: str, snapshot_dir: str) -> None: ...

    def get_current(self) -> ChampionState: ...
    def promote(self, new_champion: ChampionState) -> None:
        """保存新 champion，创建代码快照。"""
        ...
    def get_history(self) -> list[ChampionState]: ...


class BranchStore:
    def __init__(self, db_path: str) -> None: ...

    def save(self, branch: Branch) -> None: ...
    def load(self, branch_id: str) -> Branch: ...
    def load_all_active(self) -> list[Branch]: ...


class HypothesisStore:
    def __init__(self, db_path: str) -> None: ...

    def save(self, record: HypothesisRecord) -> None: ...
    def get_structural_summary(self, branch_id: Optional[str] = None,
                                include_global_blacklist: bool = False) -> list[HypothesisRecord]: ...
    def mark_status(self, hypothesis_id: str, status: str) -> None: ...
```

**依赖**：无外部模块依赖（使用标准库 sqlite3）

### 2.13 Failure Router

**对应 v3 架构**：Failure Model (§13)

**职责边界**：
- ✅ 对失败事件分类（四层：Proposal/Contract、Verification-Light、Verification-Heavy、Infra、Evaluation）
- ✅ 路由：决定是 retry、discard、还是 record
- ✅ 管理 retry 计数
- ❌ 不执行实际的重试操作（返回路由指令，由 Campaign Manager 执行）

**公开接口**：

```python
class FailureRouter:
    def __init__(self, retry_config: RetryConfig) -> None: ...

    def route(self, failure: FailureEvent, branch: Branch) -> FailureAction:
        """根据失败类型和分支状态确定处理方式。"""
        ...


@dataclass(frozen=True)
class FailureAction:
    action: Literal["retry_llm", "retry_infra", "discard", "abandon"]
    consumes_budget: bool
    writes_hypothesis_memory: bool
    max_retries_remaining: int
```

**依赖**：无

---

## 3. 接口契约

### 3.1 Creative Layer → Contract Gate: Proposal 结构

```python
@dataclass
class HypothesisProposal:
    """LLM Round 1 输出 — 全部 tainted。"""
    hypothesis_text: str                                    # 自然语言描述（tainted）
    change_locus: str                                       # 必须属于 ProblemSpec.operator_categories
    action: Literal["modify", "create_new", "remove"]
    target_file: Optional[str]                              # modify/remove 必填，create_new 为 None
    predicted_direction: Literal["improve", "tradeoff", "exploratory"]
    target_weakness: str                                    # tainted，仅存档
    expected_effect: str                                    # tainted，仅存档
    suggested_weight: Optional[float]                       # 仅 create_new，范围 (0, 1]

    # --- Contract Gate 校验规则 ---
    # 1. change_locus ∈ ProblemSpec.operator_pool.categories
    # 2. action=="modify"|"remove" → target_file != None
    # 3. action=="create_new" → target_file == None, suggested_weight != None
    # 4. suggested_weight ∈ (0, 1] if not None
```

```python
@dataclass
class PatchProposal:
    """LLM Round 2 输出 — 全部 tainted。"""
    file_path: str                                          # 相对路径
    action: Literal["modify", "create", "delete"]
    code_content: str                                       # 完整文件内容（modify/create）
    test_hint: Optional[str]                                # tainted，仅存档

    # --- Contract Gate 校验规则 ---
    # 1. file_path 匹配 ProblemSpec.search_space.editable glob
    # 2. file_path 不匹配 ProblemSpec.search_space.frozen glob
    # 3. code_content 通过 AST 解析无 SyntaxError
    # 4. 若 action=="modify": 文件中包含 Operator 子类，签名为 execute(self, solution, rng)
    # 5. 若 action=="create": 同上 + 类名不与现有算子冲突
    # 6. import 仅限 ProblemSpec.search_space.import_whitelist
    # 7. 无 subprocess/socket/os.system/eval/exec 等敏感调用
```

**调用协议**：同步调用。Contract Gate 不执行任何代码，仅做静态分析。

**不变量**：
- Contract Gate 是**纯检查**，不修改 Proposal 内容
- 所有 tainted 字段原样保存到 HypothesisRecord，但不进入 Decision

### 3.2 Contract Gate → Verification Gate: VerifiedProposal 结构

Contract Gate 通过后，Campaign Manager 负责将 PatchProposal 物化到 workspace，然后传给 Verification Gate：

```python
@dataclass(frozen=True)
class MaterializedCandidate:
    """经过 Contract Gate 且已物化到 workspace 的候选。"""
    branch_id: str
    hypothesis_id: str
    workspace_path: str                 # 物化后的 workspace 绝对路径
    champion_workspace_path: str        # champion 快照路径
    code_hash: str                      # workspace 内算子目录的 hash
    patch_action: str                   # modify / create / delete
    touched_files: list[str]            # 被修改的文件路径列表
```

**调用协议**：同步，fail-fast。Verification Gate 按顺序执行检查，第一个 heavy failure 立即返回。

**不变量**：
- candidate workspace 和 champion workspace 在 Verification 期间均不可被外部修改
- Verification Gate 只读访问 workspace，通过 Runner 在子进程中执行

### 3.3 Verification Gate → Decision Layer: DecisionFeatures

```python
@dataclass(frozen=True)
class DecisionFeatures:
    """Decision Engine 的唯一输入 — 无自由文本。

    Invariants:
    - 所有字段均为 bool / int / float / Optional[float] / str(Literal) / tuple[str(Literal)]
    - branch_id 仅用于标识，不参与决策逻辑
    - recent_failure_codes 元素均为预定义枚举值
    """
    branch_id: str
    hypothesis_action: Literal["modify", "create_new", "remove"]
    stage: Literal["screening", "validation", "frozen"]

    contract_passed: bool
    verification_passed: bool
    canary_passed: bool

    n_cases: int
    win_rate: Optional[float]           # None if pre-protocol
    median_delta: Optional[float]       # 主要竞争目标的 median delta
    ci_low: Optional[float]             # bootstrap CI lower bound
    ci_high: Optional[float]            # bootstrap CI upper bound

    stale: bool
    recent_retry_count: int
    recent_failure_codes: tuple[str, ...]  # 枚举：SYNTAX, INTERFACE, UNIT_TEST, FEASIBILITY, ...
    budget_remaining_ratio: float          # [0.0, 1.0]
```

**调用协议**：同步。Safe Feature Extractor → DecisionFeatures → Decision Engine → DecisionOutcome。纯函数链，无副作用。

**关键不变量**：
1. DecisionFeatures 是 `frozen=True` dataclass，创建后不可变
2. **没有任何 str 字段承载自由文本**（branch_id 是 UUID，stage/hypothesis_action/recent_failure_codes 均为枚举）
3. Safe Feature Extractor 在运行时验证此不变量

### 3.4 Decision Engine 输出

```python
class Decision(Enum):
    CONTINUE_EXPLORE = "continue_explore"       # 分支内继续迭代
    EXPAND_SCREENING = "expand_screening"       # 扩大 screening 样本
    QUEUE_VALIDATE = "queue_validate"           # 进入 validation
    EXPAND_VALIDATION = "expand_validation"     # 扩大 validation 样本
    QUEUE_FROZEN = "queue_frozen"               # 进入 frozen holdout
    PROMOTE = "promote"                         # 晋升为新 champion
    ABANDON = "abandon"                         # 放弃分支


@dataclass(frozen=True)
class DecisionOutcome:
    decision: Decision
    reason_codes: tuple[str, ...]               # 可审计的原因码
    features_snapshot: DecisionFeatures          # 决策时的完整输入（审计用）
```

**状态转换映射**：
| Decision | Branch State Transition |
|---|---|
| CONTINUE_EXPLORE | 保持 EXPLORE |
| EXPAND_SCREENING | EXPLORE → EXPLORE_EXPAND |
| QUEUE_VALIDATE | EXPLORE → READY_VALIDATE |
| EXPAND_VALIDATION | VALIDATING → VALIDATING_EXPAND |
| QUEUE_FROZEN | VALIDATING → READY_FROZEN |
| PROMOTE | FROZEN_TESTING → PROMOTED |
| ABANDON | → ABANDONED |

---

## 4. 状态管理

### 4.1 Branch 状态机

完整状态定义：

```python
class BranchState(Enum):
    NEW = "new"
    EXPLORE = "explore"
    EXPLORE_EXPAND = "explore_expand"
    READY_VALIDATE = "ready_validate"
    VALIDATING = "validating"
    VALIDATING_EXPAND = "validating_expand"
    READY_FROZEN = "ready_frozen"
    FROZEN_TESTING = "frozen_testing"
    PROMOTED = "promoted"
    ABANDONED = "abandoned"
    STALE = "stale"
    BLOCKED_INFRA = "blocked_infra"
```

**合法状态转换表**：

| From | To | Trigger |
|---|---|---|
| NEW | EXPLORE | branch created, first hypothesis generated |
| EXPLORE | EXPLORE | screening_fail or screening_unclear → continue iterate |
| EXPLORE | EXPLORE_EXPAND | screening_unclear + win_rate >= 0.5 |
| EXPLORE_EXPAND | EXPLORE | expand completed → re-evaluate |
| EXPLORE | READY_VALIDATE | screening_pass |
| READY_VALIDATE | VALIDATING | scheduler selects for validation |
| VALIDATING | READY_FROZEN | validation_pass |
| VALIDATING | VALIDATING_EXPAND | validation_unclear |
| VALIDATING_EXPAND | VALIDATING | expand completed → re-evaluate |
| VALIDATING | ABANDONED | validation_fail |
| READY_FROZEN | FROZEN_TESTING | scheduler selects for frozen |
| FROZEN_TESTING | PROMOTED | frozen_pass |
| FROZEN_TESTING | ABANDONED | frozen_fail |
| any active | STALE | champion_changed |
| any active | ABANDONED | budget_exhausted |
| any active | BLOCKED_INFRA | infra_incident |
| STALE | EXPLORE / ABANDONED | reconcile result |
| BLOCKED_INFRA | previous state | infra recovered |

### 4.2 Experiment 状态机

```python
class ExperimentState(Enum):
    CREATED = "created"           # 实验记录已创建
    RUNNING = "running"           # solver 正在执行
    COMPLETED = "completed"       # 正常完成（不论 pass/fail）
    FAILED_INFRA = "failed_infra" # 基础设施故障（可 retry）
```

### 4.3 Champion 状态

```python
@dataclass
class ChampionState:
    version: int                          # 单调递增
    operator_pool: dict[str, OperatorConfig]  # name → config
    solver_config_hash: str               # solver 配置 hash（冻结，应不变）
    code_snapshot_path: str               # 快照目录绝对路径
    code_snapshot_hash: str               # 快照内容 hash
    promotion_experiment_id: Optional[str]  # None for initial champion
    promoted_at: Optional[str]            # ISO 8601 timestamp
```

Champion 变更触发：
1. 所有活跃分支标记 STALE
2. 新 champion 快照持久化
3. Lineage 记录 promotion event

### 4.4 持久化策略

```
campaign_dir/
├── scion.db                            # SQLite 主数据库
│   ├── experiment_events               # append-only 事件表
│   ├── branches                        # 分支状态表
│   ├── hypotheses                      # 假设记录表
│   ├── champions                       # champion 历史表
│   └── decisions                       # 决策记录表
│
├── champion_snapshots/
│   ├── v0/                             # 初始 champion
│   │   ├── operators/
│   │   └── registry.yaml
│   ├── v1/
│   └── ...
│
├── branch_workspaces/
│   ├── {branch_id}/
│   │   ├── operators/                  # 当前代码
│   │   └── registry.yaml
│   └── ...
│
├── raw_metrics/
│   ├── {experiment_event_id}.json      # 每次实验的原始结果
│   └── ...
│
├── problem/                            # 问题定义（只读）
│   ├── problem.yaml
│   ├── protocol.yaml
│   ├── split_manifest.yaml
│   ├── seed_ledger.yaml
│   └── ...
│
└── logs/
    └── campaign.log
```

**SQLite Schema（核心表）**：

```sql
CREATE TABLE experiment_events (
    event_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    hypothesis_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    patch_action TEXT NOT NULL,
    contract_result TEXT NOT NULL,
    verification_result TEXT NOT NULL,
    canary_result TEXT,
    stage TEXT,
    case_ids TEXT,                -- JSON array
    seed_set TEXT,                -- JSON array
    raw_metrics_ref TEXT,
    decision_features_json TEXT,
    decision TEXT,
    decision_reason TEXT,
    llm_model TEXT,
    hypothesis_prompt_hash TEXT,
    code_prompt_hash TEXT,
    tokens_used INTEGER,
    problem_spec_hash TEXT NOT NULL,
    protocol_version TEXT NOT NULL,
    split_version TEXT NOT NULL,
    seed_version TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE branches (
    branch_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    base_champion_id INTEGER NOT NULL,
    base_champion_hash TEXT NOT NULL,
    current_code_hash TEXT,
    last_clean_code_hash TEXT,
    retry_count INTEGER DEFAULT 0,
    failure_codes TEXT,           -- JSON array
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    parent_hypothesis_id TEXT,
    change_locus TEXT NOT NULL,
    action TEXT NOT NULL,
    target_file TEXT,
    touched_symbols TEXT,         -- JSON array
    predicted_direction TEXT,
    target_weakness TEXT,
    rationale_text TEXT,          -- tainted
    status TEXT NOT NULL,
    suggested_weight REAL,
    blacklist_scope_tags TEXT,    -- JSON array
    blacklist_evidence_count INTEGER,
    blacklist_expiry_round INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE champions (
    version INTEGER PRIMARY KEY,
    operator_pool_json TEXT NOT NULL,
    solver_config_hash TEXT NOT NULL,
    code_snapshot_path TEXT NOT NULL,
    code_snapshot_hash TEXT NOT NULL,
    promotion_experiment_id TEXT,
    promoted_at TEXT
);
```

---

## 5. LLM 调用编排

### 5.1 模型分工

| 角色 | 模型 | 用途 | 调用时机 |
|---|---|---|---|
| 研究员/架构师 | Opus | 分析 problem spec、诊断连续失败、生成 oracle 代码 | Campaign 初始化（v0.2+）、深度诊断（v0.2+） |
| 代码主力 | Sonnet / GPT-5.4 | Hypothesis 生成、Code 生成、Fix 生成 | 每轮 proposal |

**v0.1 范围**：仅使用 Sonnet/GPT-5.4 作为代码主力。Opus 角色在 v0.2+ 激活。

### 5.2 Prompt 模板结构

#### Round 1: hypothesis.jinja2

```
输入槽位：
├── {{ problem_summary }}          # ProblemSpec 的结构化摘要
├── {{ champion_operators }}       # 当前 champion 所有算子的代码
├── {{ champion_stats }}           # champion 的聚合性能指标
├── {{ branch_code }}              # 当前分支的算子代码（如不同于 champion）
├── {{ branch_history }}           # 最近 5 轮的结构化实验摘要
├── {{ failed_hypotheses }}        # 已失败/已拒绝的假设列表（结构化）
├── {{ sibling_summary }}          # 兄弟分支的简要状态
├── {{ operator_categories }}      # 允许的 change_locus 枚举
└── {{ output_schema }}            # 要求的 JSON 输出 schema

不包含：
├── ✗ validation/frozen 原始数据
├── ✗ per-case 详细结果
└── ✗ 其他分支的代码/假设详情
```

#### Round 2: code.jinja2

```
输入槽位：
├── {{ problem_summary }}          # ProblemSpec 摘要
├── {{ hypothesis }}               # 已通过 Contract 的 HypothesisProposal
├── {{ champion_operators }}       # champion 算子代码
├── {{ target_file_content }}      # modify/remove 时的当前文件内容
├── {{ operator_interface_spec }}  # 接口签名要求
├── {{ import_whitelist }}         # 允许的 import 列表
└── {{ output_schema }}            # 要求的 JSON 输出 schema

不包含：
├── ✗ 历史实验结果
├── ✗ 失败假设列表
├── ✗ 兄弟分支信息
└── ✗ 任何统计数据
```

#### Fix: fix.jinja2

```
输入槽位：
├── {{ problem_summary }}          # ProblemSpec 摘要
├── {{ original_code }}            # 产生失败的代码
├── {{ failure_detail }}           # 轻度失败的具体错误信息
├── {{ operator_interface_spec }}  # 接口签名要求
├── {{ import_whitelist }}         # 允许的 import
└── {{ output_schema }}            # 要求的 JSON 输出 schema
```

### 5.3 Context 管理：暴露控制

| 信息类别 | Round 1 (Hypothesis) | Round 2 (Code) | Fix |
|---|:---:|:---:|:---:|
| problem spec 摘要 | ✅ | ✅ | ✅ |
| champion 算子代码 | ✅ | ✅ | ❌ |
| 当前分支代码 | ✅ | ❌（target_file 内容） | ✅ (original code) |
| 分支历史结果 | ✅ (结构化摘要) | ❌ | ❌ |
| 失败假设列表 | ✅ | ❌ | ❌ |
| 兄弟分支摘要 | ✅ (简要) | ❌ | ❌ |
| 接口规范 | ❌ | ✅ | ✅ |
| import 白名单 | ❌ | ✅ | ✅ |
| screening per-case 数据 | ✅ (仅 aggregate) | ❌ | ❌ |
| validation 数据 | ❌ | ❌ | ❌ |
| frozen 数据 | ❌ | ❌ | ❌ |
| 失败详情 | ❌ | ❌ | ✅ |

### 5.4 错误处理

```python
class LLMClient:
    """LLM API 调用封装。"""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def call(self, prompt: str, response_schema: dict,
             model: str = "sonnet") -> dict:
        """
        调用 LLM API，返回解析后的 JSON。

        错误处理策略：
        1. API 超时 → 最多重试 2 次（指数退避 5s, 15s）
        2. 格式不合规（JSON 解析失败 / schema 不匹配）→ 重新调用，
           prompt 附加上次的错误信息，最多重试 2 次
        3. API 限流（429）→ 遵守 Retry-After header
        4. 连续 3 次失败 → raise LLMRetryExhaustedError

        Raises:
            LLMTimeoutError: API 超时，重试耗尽
            LLMFormatError: 格式不合规，重试耗尽
            LLMRetryExhaustedError: 任何原因导致的重试耗尽
        """
        ...
```

**LLM 失败的路由**：
- LLM 超时/限流 → FailureCategory.INFRA → infra retry（不消耗预算）
- LLM 格式不合规且重试耗尽 → FailureCategory.PROPOSAL_CONTRACT → 丢弃，继续下一轮

---

## 6. 安全边界

### 6.1 Contract Gate 检查项与实现

| # | 检查项 | 实现方式 | 适用目标 |
|---|---|---|---|
| C1 | JSON Schema 校验 | pydantic v2 model_validate | HypothesisProposal, PatchProposal |
| C2 | change_locus 合法性 | `∈ ProblemSpec.operator_pool.categories` | HypothesisProposal |
| C3 | action-target 一致性 | modify/remove 需 target_file, create_new 不需要 | HypothesisProposal |
| C4 | 文件白名单 | `fnmatch(file_path, editable_patterns)` | PatchProposal |
| C5 | Frozen files 保护 | `not fnmatch(file_path, frozen_patterns)` | PatchProposal |
| C6 | AST 语法检查 | `ast.parse(code_content)` | PatchProposal |
| C7 | 接口签名检查 | AST 遍历找 class 定义，验证 execute(self, solution, rng) | PatchProposal |
| C8 | Import 白名单 | AST 遍历所有 Import/ImportFrom 节点 | PatchProposal |
| C9 | 敏感 API 拦截 | AST 遍历 Call 节点，检查 subprocess/socket/os.system/eval/exec/open(非读) | PatchProposal |
| C10 | 新颖性检查 | hypothesis 与活跃分支 + blacklist 的 change_locus+action+target 比较 | HypothesisProposal |

**实现依赖**：标准库 `ast` 模块，pydantic v2

### 6.2 Decision Input Guard

Safe Feature Extractor 的运行时校验：

```python
def _validate_no_free_text(features: DecisionFeatures) -> None:
    """运行时校验：确保 DecisionFeatures 不含自由文本。

    允许的 str 字段：
    - branch_id: UUID 格式（正则校验）
    - hypothesis_action: Literal 枚举
    - stage: Literal 枚举
    - recent_failure_codes: 每个元素必须 ∈ KNOWN_FAILURE_CODES

    违反则 raise DecisionInputGuardError（框架级 bug，不应出现）。
    """
    import re
    UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

    assert UUID_PATTERN.match(features.branch_id), f"branch_id is not UUID: {features.branch_id}"
    assert features.hypothesis_action in ("modify", "create_new", "remove")
    assert features.stage in ("screening", "validation", "frozen")
    for code in features.recent_failure_codes:
        assert code in KNOWN_FAILURE_CODES, f"Unknown failure code: {code}"


KNOWN_FAILURE_CODES = frozenset({
    "SYNTAX", "INTERFACE", "UNIT_TEST", "REGRESSION",
    "FEASIBILITY", "OBJECTIVE", "STATE_LEAK", "WALL_CLOCK",
    "CANARY_FAIL", "SCREENING_FAIL", "VALIDATION_FAIL", "FROZEN_FAIL",
})
```

### 6.3 Frozen Files 保护

**三层保护机制**：

1. **Contract Gate 静态检查**（§6.1 C5）：PatchProposal.file_path 不匹配 frozen patterns
2. **Workspace Materializer 拒绝写入**：apply_patch 时二次校验文件路径
3. **文件系统只读标记**：champion snapshot 目录和 problem/ 目录设为只读权限

**Frozen 文件范围**（由 ProblemSpec 定义）：
- `solver.py` — VNS 主循环
- `vns.py` — VNS 引擎
- `pool.py` — Solution Pool
- `models.py` — 数据模型
- `config.py` — 超参数配置
- `oracle.py` — feasibility + objective oracle
- `greedy_init.py` — 初始解生成
- `operators/base.py` — 算子基类
- `operators/__init__.py` — 算子注册
- 所有 benchmark 实例（`data/`）
- 所有 verification 脚本（`tests/`）
- `split_manifest.yaml`, `seed_ledger.yaml`

### 6.4 LLM 输出沙箱化

1. **LLM 输出 → JSON 解析 → Pydantic 校验**：在 Creative Layer 内完成，不合规立即拒绝
2. **代码物化 → 独立 workspace**：PatchProposal.code_content 写入分支 workspace 的 `operators/` 目录
3. **代码执行 → Runner 子进程**：
   - 独立 subprocess（`subprocess.Popen`）
   - `resource.setrlimit` 限制 CPU / memory / file descriptors
   - `env` 净化（仅保留 PATH、PYTHONPATH）
   - `timeout` 硬限制
   - 无网络访问（v0.1 不强制隔离网络，但 import 白名单禁止 socket）
4. **双跑验证**（state leak check）：同输入同 seed 跑两次，结果必须一致

---

## 7. 开发任务清单

```yaml
# TASKS.yaml — Scion v0.1 开发任务清单
# 按依赖关系排序，先骨架 → 管道 → LLM

# ═══════════════════════════════════════════════════
# Phase 1: 数据模型 + 配置加载 + 存储
# ═══════════════════════════════════════════════════

- task_id: T01
  name: "Core Data Models"
  description: |
    定义所有核心数据结构（Pydantic v2 models）：
    HypothesisProposal, PatchProposal, Branch, BranchState, ChampionState,
    DecisionFeatures, Decision, DecisionOutcome, ExperimentEvent,
    HypothesisRecord, FailureEvent, OperatorConfig, EvalStats, GateResult,
    ContractResult, VerificationResult, CheckResult, CanaryResult, ProtocolResult
  depends_on: []
  input: "scion-architecture-v3.md §3-14, scion-v0.1-design.md §3"
  output: "scion/core/models.py — 所有 dataclass 定义 + 类型注解"
  acceptance:
    - "所有 dataclass 可实例化，frozen 类型不可变"
    - "DecisionFeatures 无自由文本字段（单元测试覆盖）"
    - "BranchState 枚举完整覆盖状态机所有状态"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T02
  name: "Config Loaders"
  description: |
    实现 problem.yaml, protocol.yaml, split_manifest.yaml, seed_ledger.yaml 的
    加载与校验。使用 Pydantic v2 做 schema 校验。
    验证 split 集合互不相交。
  depends_on: [T01]
  input: "scion-v0.1-design.md §2 schema 定义"
  output: |
    scion/config/problem.py — ProblemSpec 加载
    scion/config/protocol_config.py — ProtocolConfig 加载
    scion/config/split_manifest.py — SplitManifest + 交叉校验
    scion/config/seed_ledger.py — SeedLedger 加载
  acceptance:
    - "合法 YAML 加载成功，字段类型正确"
    - "非法 YAML 抛出明确的 ValidationError"
    - "split 集合交叉时拒绝加载"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T03
  name: "SQLite Lineage Registry"
  description: |
    实现 append-only 事件存储：
    - ExperimentEvent 写入
    - Branch / Hypothesis / Champion 状态表
    - 基础查询接口（by branch, by hypothesis, failures）
    DDL 见工程架构 §4.4。
  depends_on: [T01]
  input: "scion-engineering-arch-v1.md §4.4 SQLite Schema"
  output: |
    scion/lineage/registry.py — LineageRegistry
    scion/lineage/models.py — DB-specific models
    scion/lineage/query.py — 查询接口
  acceptance:
    - "写入后可查询，数据一致"
    - "append-only：无 UPDATE/DELETE 语句"
    - "并发安全（WAL 模式）"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T04
  name: "Champion Store + Branch Store + Hypothesis Store"
  description: |
    持久化层：
    - ChampionStore: 保存/加载/历史查询
    - BranchStore: 保存/加载/列出活跃分支
    - HypothesisStore: 保存/查询/标记状态/blacklist
  depends_on: [T01, T03]
  input: "scion-engineering-arch-v1.md §2.12, §4.4"
  output: |
    scion/runtime/champion.py — ChampionStore
    scion/lineage/branch_store.py — BranchStore
    scion/memory/hypothesis_store.py — HypothesisStore
  acceptance:
    - "CRUD 操作正确"
    - "blacklist 过期机制生效"
    - "pytest 通过"
  suggested_model: "Sonnet"

# ═══════════════════════════════════════════════════
# Phase 2: 双硬闸门 + Runner
# ═══════════════════════════════════════════════════

- task_id: T05
  name: "Contract Gate"
  description: |
    实现 10 项检查（C1-C10）：
    - HypothesisProposal: schema, change_locus, action-target, novelty
    - PatchProposal: file whitelist, frozen files, AST syntax, interface,
      import whitelist, forbidden APIs
    使用标准库 ast 模块做静态分析。
  depends_on: [T01, T02]
  input: "scion-engineering-arch-v1.md §6.1, scion-architecture-v3.md §9"
  output: |
    scion/contract/gate.py — ContractGate 主入口
    scion/contract/schema_check.py — C1
    scion/contract/file_policy.py — C4, C5
    scion/contract/ast_check.py — C6, C7, C9
    scion/contract/import_policy.py — C8
  acceptance:
    - "forbidden file 修改 → 100% 拦截"
    - "import 黑名单 → 100% 拦截"
    - "subprocess/eval/exec 调用 → 100% 拦截"
    - "合法 patch → 通过"
    - "接口签名不符 → 拦截"
    - "pytest 通过，覆盖 10 项检查的正反用例"
  suggested_model: "Sonnet"

- task_id: T06
  name: "Runner (LocalSubprocessRunner)"
  description: |
    实现隔离子进程执行器：
    - subprocess.Popen + resource limits
    - timeout、memory guard
    - 环境变量净化
    - JSON 输出解析
    - 异常捕获（timeout → RunResult.error_category="timeout"）
  depends_on: [T01]
  input: "scion-architecture-v3.md §16, scion-engineering-arch-v1.md §2.10"
  output: |
    scion/runtime/runner.py — Runner Protocol
    scion/runtime/subprocess_runner.py — LocalSubprocessRunner
  acceptance:
    - "正常 solver 执行返回正确 SolverOutput"
    - "超时场景正确杀进程并返回 error_category='timeout'"
    - "OOM 场景正确捕获"
    - "环境变量已净化（无 HOME 泄漏）"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T07
  name: "Workspace Materializer"
  description: |
    分支 workspace 管理：
    - 从 code_base 复制创建 workspace
    - apply_patch 写入文件 + frozen file 二次校验
    - champion snapshot 只读权限
    - 清理
  depends_on: [T01]
  input: "scion-engineering-arch-v1.md §2.11"
  output: "scion/runtime/workspace.py — WorkspaceMaterializer"
  acceptance:
    - "workspace 正确创建，文件完整"
    - "apply_patch 拒绝写入 frozen files"
    - "champion snapshot 不可写"
    - "cleanup 后目录已删"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T08
  name: "Verification Gate"
  description: |
    实现 8 项 P0 检查（fail-fast）：
    1. syntax/import — subprocess 执行 `python -c "import {module}"`
    2. interface compliance — 动态导入检查类定义
    3. unit tests — pytest 子进程
    4. regression tests — pytest 子进程
    5. feasibility oracle — 调用 oracle.check_feasibility
    6. objective recompute — oracle.recompute_objective vs solver output
    7. state leak — 同输入双跑
    8. wall-clock guard — 计时对比
  depends_on: [T01, T02, T06, T07]
  input: "scion-architecture-v3.md §10, scion-engineering-arch-v1.md §2.5"
  output: |
    scion/verification/gate.py — VerificationGate 主入口
    scion/verification/syntax.py
    scion/verification/interface.py
    scion/verification/tests.py
    scion/verification/feasibility.py
    scion/verification/objective.py
    scion/verification/state_leak.py
    scion/verification/perf_guard.py
  acceptance:
    - "objective mismatch → 100% 拦截（heavy）"
    - "state leak（加全局变量的 patch）→ 100% 拦截（heavy）"
    - "syntax error → 拦截为 light failure"
    - "合法 patch → 全部通过"
    - "pytest 通过"
  suggested_model: "Sonnet"

# ═══════════════════════════════════════════════════
# Phase 3: Protocol + Pool Manager
# ═══════════════════════════════════════════════════

- task_id: T09
  name: "Experiment Protocol + Statistics"
  description: |
    实现三级实验执行：
    - SplitManager: case 集合管理
    - SeedLedger: seed 管理
    - 配对评估：A/B，字典序多目标比较
    - 统计：win_rate, median_delta, bootstrap_ci
    - 门控：Screening Gate, Validation Gate, Frozen Gate
    - Canary Regression Check
    - 暴露控制：不同阶段返回不同详细度
  depends_on: [T01, T02, T06]
  input: "scion-architecture-v3.md §8, scion-v0.1-design.md §4.4"
  output: |
    scion/protocol/experiment.py — ExperimentProtocol
    scion/protocol/split_manager.py
    scion/protocol/seed_ledger.py
    scion/protocol/evaluation.py — 配对评估 + 字典序比较
    scion/protocol/gates.py — 三级门控
    scion/protocol/canary.py
    scion/protocol/stats.py — bootstrap CI
    scion/protocol/exposure.py — 暴露控制
  acceptance:
    - "固定 case/seed → screening 结果确定性可复现"
    - "bootstrap CI 置信区间合理（已知 positive → ci_low > 0）"
    - "不同 stage 暴露级别正确（validation 无 per-case 数据）"
    - "canary 中 feasibility violation → veto"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T10
  name: "Pool Manager"
  description: |
    算子池管理：
    - add_operator: 新增 + 均匀重分配权重
    - remove_operator: 删除 + 归一化
    - modify_operator: 替换实现
    - build_candidate_pool: champion pool ± 变更
    - export_registry: 导出 registry.yaml
  depends_on: [T01]
  input: "scion-architecture-v3.md §6, scion-v0.1-design.md §4.8"
  output: "scion/runtime/pool_manager.py — PoolManager"
  acceptance:
    - "add 后权重之和 == 1.0"
    - "remove 后权重归一化正确"
    - "build_candidate_pool 正确应用 create_new/modify/remove"
    - "export_registry 输出合法 YAML"
    - "pytest 通过"
  suggested_model: "Sonnet"

# ═══════════════════════════════════════════════════
# Phase 4: Branch + Scheduler + Decision + Failure
# ═══════════════════════════════════════════════════

- task_id: T11
  name: "Branch Controller"
  description: |
    分支状态机：
    - 创建分支
    - 状态转换（apply_decision）
    - 代码基线选择（get_code_base）
    - STALE 标记与 reconcile
    - verification 结果记录 → last_clean_code_hash 更新
  depends_on: [T01, T04]
  input: "scion-architecture-v3.md §11, scion-engineering-arch-v1.md §4.1"
  output: "scion/core/branch.py — BranchController"
  acceptance:
    - "状态机：explore → validate → frozen → promote 完整路径"
    - "stale → reconcile → re-explore 路径"
    - "非法状态转换抛 StateTransitionError"
    - "代码基线规则正确（champion / last_clean / current）"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T12
  name: "Scheduler"
  description: |
    词典序硬优先级调度：
    P1: READY_FROZEN → P2: READY_VALIDATE → P3: STALE →
    P4: EXPLORE 系列 → P5: 创建新分支
    同级 FIFO。
  depends_on: [T01, T11]
  input: "scion-architecture-v3.md §12"
  output: "scion/core/scheduler.py — Scheduler"
  acceptance:
    - "P1 优先于 P2，P2 优先于 P3，以此类推"
    - "同级内按创建时间排序"
    - "无活跃分支时返回 create_new 信号"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T13
  name: "Decision Engine + Safe Feature Extractor"
  description: |
    确定性决策：
    - Safe Feature Extractor: 从各阶段结果提取 DecisionFeatures
    - Decision Input Guard: 运行时校验无自由文本
    - Decision Engine: 基于阈值做 screening/validation/frozen 决策
  depends_on: [T01, T02]
  input: "scion-architecture-v3.md §4, scion-v0.1-design.md §4.7"
  output: |
    scion/core/features.py — SafeFeatureExtractor + DecisionFeatures
    scion/core/decision.py — DecisionEngine
  acceptance:
    - "screening: win_rate >= 2/3 + median_delta → QUEUE_VALIDATE"
    - "validation: win_rate + ci_low → QUEUE_FROZEN 或 EXPAND 或 ABANDON"
    - "frozen: ci_low >= 0 + canary → PROMOTE 或 ABANDON"
    - "DecisionFeatures 含自由文本 → raise DecisionInputGuardError"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T14
  name: "Failure Router"
  description: |
    四层失败分类 + 路由：
    - Proposal/Contract: retry LLM（不消耗预算）
    - Verification-Light: retry LLM fix（不消耗预算）
    - Verification-Heavy: discard（消耗预算，写 hypothesis memory）
    - Infra: infra retry（不消耗预算）
    - Evaluation: 走协议（消耗预算，写 hypothesis memory）
  depends_on: [T01]
  input: "scion-architecture-v3.md §13"
  output: |
    scion/failure/taxonomy.py — FailureCategory
    scion/failure/router.py — FailureRouter
  acceptance:
    - "syntax error → retry_llm, consumes_budget=False"
    - "feasibility violation → discard, consumes_budget=True"
    - "API timeout → retry_infra, consumes_budget=False"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T15
  name: "Termination Conditions"
  description: |
    Campaign 终止条件：
    - max_experiments 达到
    - max_wall_clock_hours 达到
    - 连续 N 个分支完全 abandoned（stagnation）
    - 无活跃分支 + 不可创建新分支
  depends_on: [T01]
  input: "scion-architecture-v3.md §12.2"
  output: "scion/core/termination.py — TerminationChecker"
  acceptance:
    - "各终止条件独立可测"
    - "pytest 通过"
  suggested_model: "Sonnet"

# ═══════════════════════════════════════════════════
# Phase 5: Creative Layer + Context + 主循环
# ═══════════════════════════════════════════════════

- task_id: T16
  name: "LLM Client"
  description: |
    LLM API 调用封装：
    - 支持 Anthropic (Sonnet) + OpenAI (GPT-5.4) 切换
    - 超时重试（指数退避）
    - 格式不合规重试（附加错误信息）
    - 限流处理（429 + Retry-After）
    - Mock 模式（返回预定义 JSON，用于骨架测试）
  depends_on: [T01]
  input: "scion-engineering-arch-v1.md §5.4"
  output: |
    scion/proposal/llm_client.py — LLMClient
    scion/proposal/mock_client.py — MockLLMClient
  acceptance:
    - "正常调用返回解析后的 JSON"
    - "超时自动重试"
    - "Mock 模式返回可通过 Contract Gate 的 proposal"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T17
  name: "Prompt Templates + Schemas"
  description: |
    Jinja2 模板 + JSON Schema：
    - hypothesis.jinja2: Round 1 模板（§5.2 输入槽位）
    - code.jinja2: Round 2 模板
    - fix.jinja2: 修复模板
    - hypothesis_schema.json: HypothesisProposal 的 JSON Schema
    - patch_schema.json: PatchProposal 的 JSON Schema
  depends_on: [T01]
  input: "scion-engineering-arch-v1.md §5.2"
  output: |
    scion/proposal/prompts/hypothesis.jinja2
    scion/proposal/prompts/code.jinja2
    scion/proposal/prompts/fix.jinja2
    scion/proposal/schemas.py — JSON Schema 定义
  acceptance:
    - "模板渲染无语法错误"
    - "schema 校验正确拦截非法 JSON"
    - "所有输入槽位均已定义"
  suggested_model: "Sonnet"

- task_id: T18
  name: "Creative Layer (Proposal Engine)"
  description: |
    两轮 Proposal Engine：
    - generate_hypothesis: 调用 LLM → 解析 → HypothesisProposal
    - generate_code: 调用 LLM → 解析 → PatchProposal
    - fix_code: 调用 LLM → 解析 → PatchProposal
  depends_on: [T01, T16, T17]
  input: "scion-architecture-v3.md §5, scion-v0.1-design.md §4.1"
  output: "scion/proposal/engine.py — CreativeLayer (ProposalEngine)"
  acceptance:
    - "Mock LLM → 产出合法 HypothesisProposal"
    - "Mock LLM → 产出合法 PatchProposal"
    - "LLM 格式错误 → 自动重试 → 最终 raise"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T19
  name: "Context Manager"
  description: |
    LLM 上下文构建 + 暴露控制：
    - build_hypothesis_context: 含 champion 代码、分支历史、失败假设、兄弟摘要
    - build_code_context: 含 problem spec、hypothesis、target file、接口规范
    - build_fix_context: 含原代码、失败详情
    暴露控制：严格按 §5.3 矩阵过滤。
  depends_on: [T01, T04]
  input: "scion-architecture-v3.md §15, scion-engineering-arch-v1.md §5.3"
  output: "scion/memory/context_manager.py — ContextManager"
  acceptance:
    - "hypothesis context 不含 validation/frozen 数据"
    - "code context 不含历史结果"
    - "pytest 通过"
  suggested_model: "Sonnet"

- task_id: T20
  name: "Campaign Manager (Main Loop)"
  description: |
    主循环编排：
    - Scheduler → Branch → Proposal → Contract → Materialize →
      Verification → Canary → Protocol → Features → Decision → State Transition
    - 每步调用对应模块，处理失败路由
    - Mock LLM 模式支持
    - 单步执行支持（run_one_step）
  depends_on: [T11, T12, T13, T14, T15, T18, T19, T05, T08, T09, T10, T07, T03]
  input: "scion-architecture-v3.md §18, scion-v0.1-design.md §4"
  output: "scion/core/campaign.py — CampaignManager"
  acceptance:
    - "Mock LLM → 完整循环跑通（explore → screening → validation → frozen → promote）"
    - "Mock LLM → 失败路由跑通（contract fail → retry → discard）"
    - "Mock LLM → stale 路径跑通"
    - "每步都有 lineage 记录"
    - "pytest 通过"
  suggested_model: "Sonnet"

# ═══════════════════════════════════════════════════
# Phase 6: CLI + 端到端
# ═══════════════════════════════════════════════════

- task_id: T21
  name: "CLI"
  description: |
    命令行接口（typer）：
    - scion init: 初始化 campaign
    - scion run: 运行主循环
    - scion inspect: 查询 branch / hypothesis / experiment
    - scion report: summary / failures / branches
  depends_on: [T20]
  input: "scion-v0.1-design.md §5"
  output: "scion/cli/main.py — CLI 入口"
  acceptance:
    - "scion init 成功创建 campaign 目录"
    - "scion run --mock-llm --rounds 5 跑通"
    - "scion inspect 输出可读"
    - "scion report 输出摘要"
  suggested_model: "Sonnet"

- task_id: T22
  name: "Surrogate Integration + Problem Config"
  description: |
    将 surrogate solver 集成为 Scion 的第一个问题实例：
    - 编写 problem.yaml（指向 surrogate 目录）
    - 编写 protocol.yaml
    - 划分 split_manifest.yaml（从 9 个实例中分配）
    - 编写 seed_ledger.yaml
    - 确保 solver.py CLI 接口与 Runner 对接
  depends_on: [T02, T06]
  input: "surrogate 代码, surrogate-problem-spec-v1.md"
  output: |
    problems/warehouse_delivery/problem.yaml
    problems/warehouse_delivery/protocol.yaml
    problems/warehouse_delivery/split_manifest.yaml
    problems/warehouse_delivery/seed_ledger.yaml
  acceptance:
    - "scion init --problem problems/warehouse_delivery/problem.yaml 成功"
    - "Runner 能调用 solver.py 并解析输出"
    - "split 集合互不相交"
  suggested_model: "Sonnet"

- task_id: T23
  name: "End-to-End Validation"
  description: |
    端到端验证：
    1. Mock LLM 模式完整 campaign（≥10 轮）
    2. 真实 LLM 模式至少 5 轮
    3. 验证：Contract 拦截、Verification 拦截、Screening pass/fail、
       Lineage 可查、暴露控制正确
  depends_on: [T20, T21, T22]
  input: "所有模块"
  output: |
    tests/e2e/test_mock_campaign.py
    tests/e2e/test_real_campaign.py
    docs/e2e_report.md
  acceptance:
    - "Mock LLM: ≥10 轮无 crash"
    - "≥1 个 Contract 拦截"
    - "≥1 个 Verification 拦截"
    - "≥1 个 screening pass"
    - "全链路 lineage 可 scion inspect 查看"
    - "真实 LLM: ≥5 轮无 crash"
  suggested_model: "Sonnet"
```

**任务依赖关系图**：

```
T01 ─────────────────────────────────────────────────────────
 │                                                           │
 ├── T02 ──┬── T05 ──────────┐                              │
 │         │                  │                              │
 │         ├── T09 ──────────┤                              │
 │         │                  │                              │
 │         └── T13 ──────────┤                              │
 │                            │                              │
 ├── T03 ── T04 ─── T11 ─── T12 ──┐                        │
 │                                  │                        │
 ├── T06 ──────────── T08 ─────────┤                        │
 │                                  │                        │
 ├── T07 ─────────────────────────┤                         │
 │                                  │                        │
 ├── T10 ─────────────────────────┤                         │
 │                                  │                        │
 ├── T14 ─────────────────────────┤                         │
 │                                  │                        │
 ├── T15 ─────────────────────────┤                         │
 │                                  │                        │
 ├── T16 ── T18 ──────────────────┤                         │
 │                                  │                        │
 └── T17 ──────────────────────────┤                        │
                                    │                        │
                                    ├── T19 ── T20 ── T21   │
                                    │                  │     │
                                    └── T22 ────────── T23   │
```

---

## 8. 与 Surrogate Solver 的集成点

### 8.1 注入新算子

**步骤**：

1. **写入文件**：`WorkspaceMaterializer.apply_patch` 将 `PatchProposal.code_content` 写入分支 workspace 的 `operators/{new_name}.py`
2. **更新 registry**：`PoolManager.build_candidate_pool` 根据 hypothesis action 构造新 pool → `PoolManager.export_registry` 导出 `registry.yaml` 到 workspace
3. **修改 `__init__.py`**：对于 create_new 操作，自动在 `operators/__init__.py` 中添加 import 和 `__all__` 条目

**注意**：surrogate solver 当前使用硬编码的算子列表（`solver.py` 中 `operator_classes = [...]`）。Scion 集成需要改造 solver 以从 `registry.yaml` 动态加载算子。这是 **T22** 的一部分。

**改造方案**（对 surrogate solver 的最小侵入修改）：

```python
# solver.py 中增加动态加载逻辑
def load_operators_from_registry(instance, phase, registry_path=None):
    """从 registry.yaml 动态加载算子。"""
    if registry_path is None:
        # fallback: 使用硬编码默认算子
        return default_operators(instance, phase), default_weights()

    with open(registry_path) as f:
        registry = yaml.safe_load(f)

    operators = []
    weights = []
    for entry in registry["operators"]:
        module = importlib.import_module(f"operators.{entry['module']}")
        cls = getattr(module, entry["class_name"])
        operators.append(cls(instance, phase))
        weights.append(entry["weight"])
    return operators, weights
```

### 8.2 调用 solver.py 并收集结果

**Runner 调用命令**：

```bash
python solver.py <instance.json> \
    --phase {phase} \
    --seed {seed} \
    --max-iter {max_iter} \
    --output {output.json} \
    --registry {registry.yaml}  # 新增参数
```

**结果收集**：

```python
# Runner 解析 output.json
{
    "vehicles": { "V_xxx": { "vehicle_id": "...", "vehicle_type": "HQ40", ... } },
    "assignment": { "order_001": "V_xxx", ... },
    "objective": {
        "subcategory_splits": 5,
        "total_cost": 42000,
        "solve_time_ms": 1234
    }
}
```

Runner 将其解析为 `SolverOutput`，传给 Verification Gate 和 Experiment Protocol。

### 8.3 A/B 对比

```
Champion Solver:
  workspace = champion_snapshots/v{N}/
  registry = champion registry.yaml (原始算子池)
  ↓ run solver.py --registry champion_registry.yaml

Candidate Solver:
  workspace = branch_workspaces/{branch_id}/
  registry = candidate registry.yaml (champion pool ± 变更)
  ↓ run solver.py --registry candidate_registry.yaml
```

**关键约束**：
- **同 instance、同 seed**：确保可比性
- **独立子进程**：避免状态污染
- **取 pool 最优解**：solver 输出的 `objective` 即为 pool 最优解的目标值
- **字典序比较**：由 `ExperimentProtocol._lexicographic_compare` 执行

**执行流程**：

```python
for case in selected_cases:
    for seed in seeds:
        # Champion run
        champ_result = runner.run_solver(
            workdir=champion_workspace,
            instance_path=case,
            seed=seed,
            time_limit_sec=problem_spec.solver.time_limit_sec,
            registry_path=champion_registry,
        )
        # Candidate run
        cand_result = runner.run_solver(
            workdir=candidate_workspace,
            instance_path=case,
            seed=seed,
            time_limit_sec=problem_spec.solver.time_limit_sec,
            registry_path=candidate_registry,
        )
        # Compare
        comparison = lexicographic_compare(cand_result.output, champ_result.output)
```

### 8.4 回退机制

当 verification 未通过或 screening/validation 失败时：

1. **分支级回退**：
   - verification 未通过 → 分支代码回退到 `last_clean_code_hash`（若有）或 champion
   - 具体由 `BranchController.get_code_base` 实现（§2.2 中的代码基线规则）

2. **Champion 不变**：
   - 只有通过 Frozen Holdout 才能变更 champion
   - 任何失败都不影响 champion 状态

3. **算子池回退**：
   - candidate pool 是临时构造，不持久化
   - 失败后该 pool 直接丢弃
   - Champion pool 保持不变

4. **Stale 后的 reconcile**：
   - Champion 变更后，活跃分支标记 STALE
   - Reconcile: 基于新 champion 重新应用 patch → Contract → Verification
   - 通过 → 基于新 champion 重新 screening
   - 不通过 → ABANDONED

```python
def reconcile_stale_branch(self, branch: Branch, new_champion: ChampionState) -> Branch:
    """Stale 分支 reconcile 流程。"""
    # 1. 尝试在新 champion 基础上重新应用当前 patch
    new_workspace = workspace.create_branch_workspace(branch.branch_id, new_champion)
    current_patch = self._extract_patch(branch)  # 从分支 workspace 提取 diff

    # 2. 重新走 Contract → Verification
    contract = contract_gate.validate_patch(current_patch)
    if not contract.passed:
        branch.state = BranchState.ABANDONED
        return branch

    workspace.apply_patch(new_workspace, current_patch)
    verification = verification_gate.run(new_workspace, champion_workspace)
    if not verification.passed:
        branch.state = BranchState.ABANDONED
        return branch

    # 3. 更新分支基线
    branch.base_champion_id = new_champion.version
    branch.base_champion_hash = new_champion.code_snapshot_hash
    branch.state = BranchState.EXPLORE  # 重新进入探索（需重新 screening）
    return branch
```

---

## 设计决策总结

**最重要的 3 个设计决策**：

1. **DecisionFeatures 作为硬隔离边界，所有字段经过运行时校验**。这不仅是 v3 架构的要求，更是工程实现的关键点——在 Safe Feature Extractor 中加入 `_validate_no_free_text` 运行时断言，确保即使未来代码修改引入了新字段，也不会有自由文本泄漏到 Decision Engine。选择运行时 + 编译时双重校验（frozen dataclass + assert），而非仅靠类型注解，因为 Python 类型系统无法阻止 `str` 字段被赋予任意值。

2. **Workspace Materializer 与 Runner 分离，Solver Runner 统一子进程接口**。将"准备代码"和"执行代码"解耦为两个独立模块，使得 Verification Gate（8 项检查）和 Experiment Protocol（A/B 评估）都通过同一个 Runner Protocol 调用 solver，保证隔离一致性。这也为 v0.2+ 切换 Docker/Remote runner 提供了扩展点，不需要修改上层逻辑。同时，对 surrogate solver 的改造被限定为最小侵入——仅增加 `--registry` 参数和动态加载逻辑。

3. **存储层采用 SQLite 单文件 + 文件系统快照的混合策略**。结构化元数据（events、branches、hypotheses、champions）存 SQLite（便于查询和事务），代码快照和原始 metrics 存文件系统（避免 SQLite 存大 blob）。`raw_metrics_ref` 字段作为桥接，指向 JSON 文件路径。这样 lineage 查询是 O(1) 的（SQLite index），而代码回溯是 O(1) 的（目录直读），且整个 campaign 可以用 `tar` 一次性打包归档。

---

*本文档基于 scion-architecture-v3.md 和 scion-v0.1-design.md，面向工程实现。所有设计决策忠实于 v3 架构锁定的决策。*
