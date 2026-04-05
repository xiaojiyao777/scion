# Scion Framework — v0.1 MVP Design

*Date: 2026-04-02*
*Parent: scion-architecture-v3.md*
*Status: Design — Ready for Review*

---

## 0. v0.1 目标

用一个真实问题（仓配协同 VNS 算子优化）跑通框架骨架，证明：

1. 双硬闸门（Contract + Verification）能拦截越界和语义错误
2. 三级实验协议能区分真改进和噪声
3. 分支治理能支持深度迭代探索
4. 全链路实验可追溯
5. Decision Layer 与 LLM 输出完全隔离

**不是目标**：论文级 ablation、参数层搜索、多问题泛化、生产部署。

---

## 1. 目录结构

```
scion/
├── core/
│   ├── campaign.py              # Campaign Controller 主入口
│   ├── branch.py                # Branch Controller 状态机
│   ├── scheduler.py             # 词典序调度器
│   ├── decision.py              # Decision Engine
│   ├── features.py              # DecisionFeatures + Safe Feature Extractor
│   └── termination.py           # 终止条件
│
├── proposal/
│   ├── engine.py                # 两轮 Proposal Engine
│   ├── hypothesis.py            # HypothesisProposal 数据结构
│   ├── patch.py                 # PatchProposal 数据结构
│   ├── llm_client.py            # LLM API 调用封装
│   ├── prompts/
│   │   ├── hypothesis.jinja2    # Round 1 prompt 模板
│   │   └── code.jinja2          # Round 2 prompt 模板
│   └── schemas.py               # JSON schema 定义
│
├── contract/
│   ├── gate.py                  # Contract Gate 主入口
│   ├── schema_check.py          # JSON schema 校验
│   ├── file_policy.py           # 文件白名单 / 黑名单
│   ├── ast_check.py             # AST 接口签名检查
│   └── import_policy.py         # import 白名单 + 敏感 API 扫描
│
├── verification/
│   ├── gate.py                  # Verification Gate 主入口
│   ├── syntax.py                # import / syntax 检查
│   ├── interface.py             # 接口合规
│   ├── tests.py                 # unit test / regression test runner
│   ├── feasibility.py           # feasibility oracle 调用
│   ├── objective.py             # objective recomputation
│   ├── state_leak.py            # double-run compare
│   └── perf_guard.py            # wall-clock guard
│
├── protocol/
│   ├── experiment.py            # Experiment Protocol 主入口
│   ├── split_manager.py         # SplitManager
│   ├── seed_ledger.py           # SeedLedger
│   ├── evaluation.py            # 配对评估（A/B）
│   ├── gates.py                 # Screening / Validation / Frozen Gate
│   ├── canary.py                # Canary Regression Check
│   ├── stats.py                 # bootstrap CI / win_rate / median_delta
│   └── exposure.py              # 暴露控制策略
│
├── runtime/
│   ├── workspace.py             # 分支 workspace 管理 + Materializer
│   ├── runner.py                # Runner Protocol
│   ├── subprocess_runner.py     # LocalSubprocessRunner
│   ├── pool_manager.py          # 算子池管理（注册/注销/权重）
│   └── champion.py              # ChampionState 管理
│
├── lineage/
│   ├── registry.py              # SQLite append-only 事件存储
│   ├── models.py                # ExperimentEvent / HypothesisRecord
│   └── query.py                 # 查询接口（by branch / hypothesis / failure）
│
├── memory/
│   ├── context_manager.py       # 上下文构建 + 暴露控制
│   ├── hypothesis_store.py      # 假设存储 + 结构化摘要
│   └── blacklist.py             # scope_tags + evidence_count + expiry
│
├── failure/
│   ├── taxonomy.py              # 四层 Failure 分类
│   └── router.py                # 失败路由（retry / discard / record）
│
├── config/
│   ├── problem.py               # problem.yaml 加载 + 校验
│   ├── protocol_config.py       # protocol.yaml 加载
│   └── split_manifest.py        # split_manifest.yaml 加载
│
├── cli/
│   └── main.py                  # CLI 入口
│
└── problems/                    # 问题实例（不进框架包）
    └── warehouse_delivery/
        ├── problem.yaml
        ├── protocol.yaml
        ├── split_manifest.yaml
        ├── seed_ledger.yaml
        ├── baseline/
        │   ├── solver.py
        │   └── operators/
        │       ├── registry.yaml
        │       ├── destroy/
        │       └── repair/
        ├── verification/
        │   ├── check_feasibility.py   # Oracle（人审核冻结）
        │   └── recompute_objective.py # Oracle（人审核冻结）
        ├── tests/
        │   ├── test_operator_interface.py
        │   ├── test_solution_integrity.py
        │   └── regression/
        └── cases/
            ├── screening/
            ├── validation/
            ├── frozen/
            └── canary/
```

---

## 2. 数据模型

### 2.1 problem.yaml Schema

```yaml
meta:
  problem_id: str                     # 唯一标识
  description: str                    # 问题描述

objective:
  # 字典序多目标
  levels:
    - name: "business_aggregation"    # 业务聚合约束满足度
      direction: "maximize"
      tie_tolerance: 0.01             # 差异在此范围内视为 tie，比下一级
    - name: "total_cost"
      direction: "minimize"
      tie_tolerance: 0.005
    - name: "efficiency"
      direction: "minimize"
      tie_tolerance: 0.01
  # 用于 practical significance 的主要竞争目标
  primary_metric: "total_cost"
  practical_delta_screen: 0.002
  practical_delta_validate: 0.003

solver:
  entry: str                          # solver 入口脚本
  run_command: str                    # 调用命令模板
  # 模板变量: {instance}, {seed}, {time_limit}, {operator_registry}
  output_format: "json"               # json | csv | stdout_parse
  output_fields:
    objectives: dict                  # {level_name: value}
    feasible: bool
    solution_file: str                # 用于 verification
    pool_best_index: int              # pool 中最优解索引
  time_limit_sec: int
  pool_size: int                      # solution pool 大小

operator_pool:
  interface:
    signature: "execute(solution: Solution, rng: Random) -> Solution"
    base_class: str                   # 可选
    registration_file: str            # 框架自动管理
  categories:                         # 算子分类（仅标注用，不影响接口）
    - "order_level"                   # 订单级
    - "vehicle_level"                 # 车辆级
  initial_operators:
    - name: str
      file: str
      category: str
      weight: float
  injection_policy:
    initial_weight: "uniform"         # 新算子加入后均匀重分配
  # 动态自适应权重更新机制: 冻结不动（v0.1）
  adaptive_weights_frozen: true

search_space:
  editable:
    - "operators/destroy/*.py"        # glob patterns
  frozen:
    - "solver/**"
    - "benchmark/**"
    - "verification/**"
  interface_signature_frozen: true
  import_whitelist:
    - "numpy"
    - "random"
    - "math"
    - "collections"
    - "itertools"
    - "typing"
    - "copy"

verification:
  unit_tests: list[str]              # 测试文件路径
  regression_suite: str              # 目录路径
  feasibility_oracle:
    script: str
    reference_cases: list             # {case, known_feasible, known_infeasible}
  objective_recompute:
    script: str
    tolerance: float
  state_leak:
    method: "double_run_compare"
  wall_clock:
    max_ratio: float                  # candidate 不超过 champion 的 N 倍
```

### 2.2 protocol.yaml Schema

```yaml
version: str

screening:
  n_cases_modify: 6                   # modify/remove 操作
  n_cases_create: 10                  # create_new 操作
  n_seeds: 2
  expose: "full"
  expand_to_modify: 10
  expand_to_create: 16

validation:
  n_cases: 12
  n_seeds: 3
  expose: "aggregate_only"
  expand_to: 20

frozen:
  n_cases: 12
  n_seeds: 3
  expose: "pass_fail_aggregate"
  max_uses_per_campaign: 3

canary:
  cases: list[str]
  seeds: list[int]

retry:
  infra_max: 2
  llm_fix_max: 2

gates:
  screening:
    win_rate_min: 0.667
    median_delta_min: "practical_delta_screen"  # 引用 problem.yaml
  validation:
    win_rate_min: 0.667
    median_delta_min: "practical_delta_validate"
    bootstrap_ci_low_min: 0.0
    bootstrap_n: 10000
  frozen:
    bootstrap_ci_low_min: 0.0
    canary_required: true
```

### 2.3 split_manifest.yaml

```yaml
version: str
screening:
  cases: list[str]                    # case 文件路径
validation:
  cases: list[str]
frozen:
  cases: list[str]
canary:
  cases: list[str]
# 四个集合必须互不相交
```

### 2.4 seed_ledger.yaml

```yaml
version: str
screening: list[int]
validation: list[int]
frozen: list[int]
canary: list[int]
```

---

## 3. 核心数据结构

### 3.1 Proposal 相关

```python
@dataclass
class HypothesisProposal:
    hypothesis_text: str
    change_locus: str              # 枚举，由 problem spec 定义
    action: Literal["modify", "create_new", "remove"]
    target_file: Optional[str]     # modify/remove
    predicted_direction: Literal["improve", "tradeoff", "exploratory"]
    target_weakness: str
    expected_effect: str
    suggested_weight: Optional[float]  # 仅 create_new

@dataclass
class PatchProposal:
    file_path: str
    action: Literal["modify", "create", "delete"]
    code_content: str              # 完整文件内容
    test_hint: Optional[str]       # tainted，仅存档
```

### 3.2 Branch 相关

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

@dataclass
class Branch:
    branch_id: str
    state: BranchState
    base_champion_id: str
    base_champion_hash: str
    created_at: str

    hypotheses: list[str]          # hypothesis_id 列表
    current_code_hash: Optional[str]
    last_clean_code_hash: Optional[str]  # 最后通过 verification 的版本

    screening_result: Optional[str]
    validation_result: Optional[str]
    frozen_result: Optional[str]

    retry_count: int
    failure_codes: list[str]
```

### 3.3 Champion 相关

```python
@dataclass
class ChampionState:
    version: int
    operator_pool: dict[str, OperatorConfig]
    solver_config_hash: str
    code_snapshot_path: str
    code_snapshot_hash: str
    promotion_experiment_id: Optional[str]
    promoted_at: Optional[str]
```

### 3.4 Decision 相关

```python
@dataclass(frozen=True)
class DecisionFeatures:
    branch_id: str
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
    recent_failure_codes: tuple[str, ...]
    budget_remaining_ratio: float

class Decision(Enum):
    CONTINUE_EXPLORE = "continue_explore"
    EXPAND_SCREENING = "expand_screening"
    QUEUE_VALIDATE = "queue_validate"
    EXPAND_VALIDATION = "expand_validation"
    QUEUE_FROZEN = "queue_frozen"
    PROMOTE = "promote"
    ABANDON = "abandon"
```

### 3.5 Lineage 相关

```python
@dataclass
class ExperimentEvent:
    event_id: str                  # UUID
    campaign_id: str
    branch_id: str
    hypothesis_id: str
    timestamp: str                 # ISO 8601

    # Code
    code_hash: str
    patch_action: str              # modify / create / delete

    # Gates
    contract_result: str           # passed / failed:reason
    verification_result: str       # passed / failed:check_name
    canary_result: Optional[str]

    # Protocol
    protocol_version: str
    split_version: str
    seed_version: str
    stage: str
    case_ids: list[str]
    seed_set: list[int]
    raw_metrics_ref: str           # 指向 JSON 文件

    # Decision
    decision_features_json: str    # 序列化的 DecisionFeatures
    decision: str
    decision_reason: str

    # LLM
    llm_model: str
    hypothesis_prompt_hash: str
    code_prompt_hash: str
    tokens_used: int

    # Env
    problem_spec_hash: str
```

### 3.6 Failure 相关

```python
class FailureCategory(Enum):
    PROPOSAL_CONTRACT = "proposal_contract"
    VERIFICATION_LIGHT = "verification_light"
    VERIFICATION_HEAVY = "verification_heavy"
    INFRA = "infra"
    EVALUATION = "evaluation"

@dataclass
class FailureEvent:
    category: FailureCategory
    detail: str                    # 具体错误信息
    retryable: bool
    consumes_budget: bool
    writes_hypothesis_memory: bool
```

### 3.7 HypothesisRecord

```python
@dataclass
class HypothesisRecord:
    hypothesis_id: str
    branch_id: str
    parent_hypothesis_id: Optional[str]

    change_locus: str
    action: Literal["modify", "create_new", "remove"]
    target_file: Optional[str]
    touched_symbols: list[str]
    predicted_direction: str
    target_weakness: str

    rationale_text: str            # tainted
    evidence_refs: list[str]       # experiment_event ids
    status: Literal["active", "weakened", "rejected", "promoted"]

    suggested_weight: Optional[float]

    # Blacklist 信息（如果 rejected）
    blacklist_scope_tags: Optional[list[str]]
    blacklist_evidence_count: Optional[int]
    blacklist_expiry_round: Optional[int]
```

---

## 4. 组件设计

### 4.1 Proposal Engine

```python
class ProposalEngine:
    def __init__(self, llm_client, prompt_templates, schemas):
        self.llm = llm_client
        self.templates = prompt_templates
        self.schemas = schemas

    def generate_hypothesis(self, context: HypothesisContext) -> HypothesisProposal:
        """Round 1: 生成结构化假设"""
        prompt = self.templates.render_hypothesis(context)
        raw = self.llm.call(
            prompt=prompt,
            response_schema=self.schemas.hypothesis,
            model="sonnet"  # 或 gpt-5.4，可配
        )
        return HypothesisProposal.from_json(raw)

    def generate_code(self, context: CodeContext) -> PatchProposal:
        """Round 2: 生成完整文件代码"""
        prompt = self.templates.render_code(context)
        raw = self.llm.call(
            prompt=prompt,
            response_schema=self.schemas.patch,
            model="sonnet"
        )
        return PatchProposal.from_json(raw)

    def fix_code(self, context: FixContext) -> PatchProposal:
        """Verification 轻度失败后的修复"""
        prompt = self.templates.render_fix(context)
        raw = self.llm.call(
            prompt=prompt,
            response_schema=self.schemas.patch,
            model="sonnet"
        )
        return PatchProposal.from_json(raw)
```

### 4.2 Contract Gate

```python
class ContractGate:
    def __init__(self, problem_spec):
        self.spec = problem_spec

    def validate_hypothesis(self, h: HypothesisProposal) -> ContractResult:
        checks = [
            self._check_schema(h),
            self._check_change_locus(h),
            self._check_action_target_consistency(h),
            self._check_novelty(h),  # 与活跃分支 + blacklist 比较
        ]
        return ContractResult.from_checks(checks)

    def validate_patch(self, p: PatchProposal) -> ContractResult:
        checks = [
            self._check_file_whitelist(p),
            self._check_frozen_files(p),
            self._check_syntax(p),
            self._check_interface_compliance(p),  # AST 检查
            self._check_imports(p),
            self._check_forbidden_apis(p),         # subprocess/socket/os.system 等
        ]
        return ContractResult.from_checks(checks)
```

### 4.3 Verification Gate

```python
class VerificationGate:
    def __init__(self, problem_spec, runner):
        self.spec = problem_spec
        self.runner = runner

    def run(self, candidate_workspace: str) -> VerificationResult:
        """fail-fast: 按顺序检查，第一个 P0 重度失败立即返回"""
        checks = []

        # 轻度（可修复）
        checks.append(self.check_syntax(candidate_workspace))
        checks.append(self.check_interface(candidate_workspace))
        checks.append(self.check_unit_tests(candidate_workspace))
        checks.append(self.check_regression_tests(candidate_workspace))

        # 重度（不可修复）
        checks.append(self.check_feasibility(candidate_workspace))
        checks.append(self.check_objective_recompute(candidate_workspace))
        checks.append(self.check_state_leak(candidate_workspace))
        checks.append(self.check_wall_clock(candidate_workspace))

        return VerificationResult.from_checks(checks)

    def check_state_leak(self, workspace):
        """同输入跑两次，结果必须一致"""
        r1 = self.runner.run(workspace, self._canary_command(seed=42))
        r2 = self.runner.run(workspace, self._canary_command(seed=42))
        return Check("state_leak", passed=(r1.output == r2.output))

    def check_objective_recompute(self, workspace):
        """独立全量重算 vs solver 报告值"""
        solver_result = self.runner.run(workspace, self._solver_command())
        recomputed = self.runner.run(workspace, self._recompute_command(solver_result.solution_file))
        delta = abs(solver_result.objective - recomputed.objective)
        return Check("objective_recompute",
                     passed=(delta <= self.spec.verification.objective_recompute.tolerance))
```

### 4.4 Experiment Protocol

```python
class ExperimentProtocol:
    def __init__(self, protocol_config, split_manager, seed_ledger, runner):
        self.config = protocol_config
        self.splits = split_manager
        self.seeds = seed_ledger
        self.runner = runner

    def run_canary(self, candidate_ws, champion_ws) -> CanaryResult:
        """安全 veto，不做改善证据"""
        cases = self.splits.canary_cases()
        seeds = self.seeds.canary_seeds()
        for case in cases:
            for seed in seeds:
                result = self._run_single(candidate_ws, case, seed)
                if not result.feasible:
                    return CanaryResult(passed=False, reason="feasibility_violation")
                if result.timeout:
                    return CanaryResult(passed=False, reason="timeout")
        return CanaryResult(passed=True)

    def run(self, stage, candidate_ws, champion_ws, hypothesis_action) -> ProtocolResult:
        """执行指定阶段的配对评估"""
        cases = self.splits.get_cases(stage)
        seeds = self.seeds.get_seeds(stage)
        n_cases = self._get_n_cases(stage, hypothesis_action)

        selected_cases = cases[:n_cases]  # 固定顺序，不随机
        paired_results = []

        for case in selected_cases:
            case_deltas = []
            for seed in seeds:
                cand = self._run_single(candidate_ws, case, seed)
                champ = self._run_single(champion_ws, case, seed)
                comparison = self._lexicographic_compare(cand, champ)
                case_deltas.append(comparison)
            # per-case 聚合（跨 seed 取多数）
            paired_results.append(self._aggregate_seeds(case_deltas))

        # 统计计算
        stats = self._compute_stats(paired_results)

        # Gate 判定
        gate_result = self._apply_gate(stage, stats)

        # 暴露控制
        exposed = self._apply_exposure(stage, paired_results, stats)

        return ProtocolResult(
            stage=stage,
            raw_results=paired_results,   # 存入 lineage
            stats=stats,
            gate_result=gate_result,
            exposed=exposed               # 只有这部分可能回喂 LLM
        )

    def _get_n_cases(self, stage, action):
        if stage == "screening":
            if action == "create_new":
                return self.config.screening.n_cases_create
            else:
                return self.config.screening.n_cases_modify
        elif stage == "validation":
            return self.config.validation.n_cases
        else:
            return self.config.frozen.n_cases

    def _lexicographic_compare(self, cand_result, champ_result):
        """字典序多目标比较，返回 win/loss/tie + primary_delta"""
        for level in self.objective_levels:
            c_val = cand_result.objectives[level.name]
            h_val = champ_result.objectives[level.name]
            delta = self._directed_delta(c_val, h_val, level.direction)
            if abs(delta) > level.tie_tolerance:
                return PairedComparison(
                    result="win" if delta > 0 else "loss",
                    deciding_level=level.name,
                    primary_delta=self._primary_delta(cand_result, champ_result)
                )
        return PairedComparison(result="tie", deciding_level=None,
                               primary_delta=self._primary_delta(cand_result, champ_result))

    def _compute_stats(self, paired_results):
        wins = sum(1 for r in paired_results if r.result == "win")
        losses = sum(1 for r in paired_results if r.result == "loss")
        n = len(paired_results)
        win_rate = wins / n if n > 0 else 0
        deltas = [r.primary_delta for r in paired_results]
        median_delta = np.median(deltas)
        ci_low, ci_high = bootstrap_ci(deltas, n_bootstrap=10000)
        return EvalStats(
            n_cases=n, wins=wins, losses=losses,
            win_rate=win_rate, median_delta=median_delta,
            ci_low=ci_low, ci_high=ci_high
        )
```

### 4.5 Branch Controller

```python
class BranchController:
    def __init__(self, config):
        self.max_active = config.branch.max_active
        self.branches: dict[str, Branch] = {}

    def create_branch(self, champion: ChampionState) -> Branch:
        branch = Branch(
            branch_id=uuid4(),
            state=BranchState.NEW,
            base_champion_id=champion.version,
            base_champion_hash=champion.code_snapshot_hash,
            ...
        )
        self.branches[branch.branch_id] = branch
        return branch

    def apply(self, branch: Branch, decision: Decision):
        transitions = {
            Decision.CONTINUE_EXPLORE: self._continue_explore,
            Decision.EXPAND_SCREENING: self._expand_screening,
            Decision.QUEUE_VALIDATE: self._queue_validate,
            Decision.EXPAND_VALIDATION: self._expand_validation,
            Decision.QUEUE_FROZEN: self._queue_frozen,
            Decision.PROMOTE: self._promote,
            Decision.ABANDON: self._abandon,
        }
        transitions[decision](branch)

    def mark_all_stale(self, new_champion_id: str):
        """Champion 更新时标记所有活跃分支为 STALE"""
        for b in self.branches.values():
            if b.state not in (BranchState.PROMOTED, BranchState.ABANDONED):
                b.state = BranchState.STALE
                b.stale_since_champion = new_champion_id

    def next_stage(self, branch: Branch) -> str:
        stage_map = {
            BranchState.EXPLORE: "screening",
            BranchState.EXPLORE_EXPAND: "screening",
            BranchState.READY_VALIDATE: "validation",
            BranchState.VALIDATING: "validation",
            BranchState.VALIDATING_EXPAND: "validation",
            BranchState.READY_FROZEN: "frozen",
            BranchState.FROZEN_TESTING: "frozen",
        }
        return stage_map[branch.state]

    def get_code_base(self, branch: Branch, champion: ChampionState) -> str:
        """分支内代码基线规则"""
        if branch.current_code_hash is None:
            return champion.code_snapshot_path
        if branch.last_clean_code_hash is None:
            # 从未通过 verification
            return champion.code_snapshot_path
        # verification 通过过，基于当前代码继续
        return branch.current_workspace_path
```

### 4.6 Scheduler

```python
class Scheduler:
    def select(self, branches: dict[str, Branch], budget) -> Optional[Branch]:
        """词典序硬优先级"""
        # P1: READY_FROZEN
        candidates = [b for b in branches.values() if b.state == BranchState.READY_FROZEN]
        if candidates:
            return min(candidates, key=lambda b: b.created_at)

        # P2: READY_VALIDATE
        candidates = [b for b in branches.values() if b.state == BranchState.READY_VALIDATE]
        if candidates:
            return min(candidates, key=lambda b: b.created_at)

        # P3: STALE
        candidates = [b for b in branches.values() if b.state == BranchState.STALE]
        if candidates:
            return min(candidates, key=lambda b: b.created_at)

        # P4: EXPLORE with positive signal
        explore = [b for b in branches.values()
                   if b.state in (BranchState.EXPLORE, BranchState.EXPLORE_EXPAND)]
        if explore:
            return min(explore, key=lambda b: b.created_at)

        # P5: Create new branch
        active = [b for b in branches.values()
                  if b.state not in (BranchState.PROMOTED, BranchState.ABANDONED)]
        if len(active) < self.max_active and budget.can_create_new():
            return None  # 信号：需要创建新分支

        return None  # 终止信号
```

### 4.7 Decision Engine

```python
class DecisionEngine:
    def decide(self, features: DecisionFeatures) -> Decision:
        """纯确定性决策，只基于 DecisionFeatures"""

        if not features.contract_passed:
            return Decision.ABANDON  # 不应该到这里，前置拦截

        if not features.verification_passed:
            return Decision.ABANDON  # 不应该到这里

        if not features.canary_passed:
            return Decision.ABANDON

        if features.stage == "screening":
            return self._decide_screening(features)
        elif features.stage == "validation":
            return self._decide_validation(features)
        elif features.stage == "frozen":
            return self._decide_frozen(features)

    def _decide_screening(self, f: DecisionFeatures) -> Decision:
        if f.win_rate >= self.gates.screening.win_rate_min \
           and f.median_delta >= self.gates.screening.median_delta_min:
            return Decision.QUEUE_VALIDATE
        elif f.win_rate >= 0.5:  # 有点信号但不够
            return Decision.CONTINUE_EXPLORE  # 分支内继续迭代
        else:
            return Decision.CONTINUE_EXPLORE  # 也允许继续尝试，budget 自然约束

    def _decide_validation(self, f: DecisionFeatures) -> Decision:
        if f.win_rate >= self.gates.validation.win_rate_min \
           and f.median_delta >= self.gates.validation.median_delta_min \
           and f.ci_low >= self.gates.validation.ci_low_min:
            return Decision.QUEUE_FROZEN
        elif f.win_rate >= 0.5 and f.ci_low < 0:
            return Decision.EXPAND_VALIDATION
        else:
            return Decision.ABANDON

    def _decide_frozen(self, f: DecisionFeatures) -> Decision:
        if f.ci_low >= self.gates.frozen.ci_low_min and f.canary_passed:
            return Decision.PROMOTE
        else:
            return Decision.ABANDON
```

### 4.8 Pool Manager

```python
class PoolManager:
    def __init__(self, initial_pool: dict[str, OperatorConfig]):
        self.pool = dict(initial_pool)

    def add_operator(self, name: str, file: str, category: str,
                     suggested_weight: Optional[float] = None):
        """新增算子，均匀重分配权重"""
        n = len(self.pool) + 1
        new_weight = 1.0 / n
        # 均匀重分配
        for op in self.pool.values():
            op.weight = (1.0 - new_weight) * op.weight / sum(o.weight for o in self.pool.values())
        self.pool[name] = OperatorConfig(file=file, category=category, weight=new_weight)

    def remove_operator(self, name: str):
        """删除算子，剩余概率归一化"""
        del self.pool[name]
        total = sum(op.weight for op in self.pool.values())
        for op in self.pool.values():
            op.weight /= total

    def modify_operator(self, name: str, new_file: str):
        """修改算子实现，权重不变"""
        self.pool[name].file = new_file

    def build_candidate_pool(self, champion_pool, patch: PatchProposal,
                             hypothesis: HypothesisProposal) -> dict:
        """根据 hypothesis action 构造 candidate pool"""
        candidate = dict(champion_pool)
        if hypothesis.action == "create_new":
            self.add_operator(...)
        elif hypothesis.action == "modify":
            self.modify_operator(...)
        elif hypothesis.action == "remove":
            self.remove_operator(...)
        return candidate

    def export_registry(self, pool, path):
        """导出为 registry.yaml，solver 启动时读取"""
        ...
```

### 4.9 Context Manager

```python
class ContextManager:
    def build_hypothesis_context(self, branch, champion, problem_spec,
                                  hypothesis_store, sibling_branches) -> HypothesisContext:
        return HypothesisContext(
            problem_summary=self._summarize_problem(problem_spec),
            champion_code=self._read_champion_operators(champion),
            champion_stats=self._summarize_champion_stats(champion),
            branch_code=self._read_branch_code(branch) if branch.current_code_hash else None,
            branch_history=self._format_branch_history(branch, max_rounds=5),
            failed_hypotheses=hypothesis_store.get_structural_summary(
                branch_id=branch.branch_id,
                include_global_blacklist=True
            ),
            sibling_summary=self._summarize_siblings(sibling_branches),
            # 不包含 validation/frozen 细节
        )

    def build_code_context(self, branch, hypothesis, champion, problem_spec) -> CodeContext:
        return CodeContext(
            problem_summary=self._summarize_problem(problem_spec),
            hypothesis=hypothesis,
            champion_code=self._read_champion_operators(champion),
            target_file_content=self._read_target(branch, hypothesis),
            interface_spec=problem_spec.operator_pool.interface,
            # 不包含历史结果、失败假设、兄弟分支
        )
```

---

## 5. CLI 接口

```bash
# 初始化 campaign
scion init --problem problems/warehouse_delivery/problem.yaml

# 运行（可指定轮数或持续运行）
scion run --rounds 10
scion run --until-stagnation

# Mock LLM 模式（确定性骨架独立验证）
scion run --mock-llm --rounds 5

# 查询
scion inspect campaign              # campaign 概览
scion inspect branch <branch_id>    # 分支详情
scion inspect hypothesis <hyp_id>   # 假设详情
scion inspect experiment <event_id> # 实验详情

# 回放
scion replay <event_id>             # 重放单次实验

# 报告
scion report summary                # campaign 摘要
scion report failures               # 失败分布
scion report branches               # 分支生存曲线
```

---

## 6. 开发顺序

不设硬周限，按依赖关系排序。每个阶段有明确验收标准。

### Phase 1: 数据模型 + 配置加载 + Lineage

**交付**：
- 所有数据结构定义（§3 全部）
- problem.yaml / protocol.yaml / split_manifest / seed_ledger 加载 + 校验
- SQLite Lineage Registry（append-only write + basic query）

**验收**：
- 能加载合法配置，拒绝非法配置
- 能写入和查询 ExperimentEvent

### Phase 2: Contract Gate + Verification Gate

**交付**：
- Contract Gate 全部检查项
- Verification Gate 8 项 P0 检查
- Runner（LocalSubprocessRunner）

**验收**：
- 构造 forbidden file 修改 → 100% 拦截
- 构造 objective mismatch → 100% 拦截
- 构造 state leak patch → 100% 拦截
- 构造合法 patch → 通过

### Phase 3: Protocol + Pool Manager

**交付**：
- SplitManager + SeedLedger
- 配对评估（A/B 模式 + 字典序比较）
- Screening / Validation / Frozen Gate
- Canary Regression Check
- Bootstrap CI
- Pool Manager（add/remove/modify + registry export）
- Exposure Policy

**验收**：
- 给定固定 case/seed，screening 结果确定性可复现
- 不同 stage 的暴露级别正确
- Pool 操作后 registry 正确

### Phase 4: Branch + Scheduler + Decision + Failure Router

**交付**：
- Branch Controller 状态机
- Scheduler（词典序）
- Decision Engine
- Safe Feature Extractor
- Failure Router（四层分类 + 路由）
- Stale 处理
- 终止条件

**验收**：
- mock 数据驱动状态机走完 explore → validate → frozen → promote 全路径
- mock 数据驱动 stale → reconcile 路径
- Decision 不读取任何自由文本字段

### Phase 5: Proposal Engine + Context Manager + 主循环

**交付**：
- LLM Client（支持 Sonnet / GPT-5.4 切换）
- Prompt 模板（hypothesis + code + fix）
- Context Manager（暴露控制）
- Hypothesis Store + Blacklist
- 主循环（campaign.py）
- Mock LLM 模式

**验收**：
- Mock LLM 下完整循环可跑通
- 真实 LLM 下可产出合法 hypothesis + code

### Phase 6: 端到端验证 + CLI

**前置条件**（由人完成）：
- 仓配协同 baseline solver 可稳定运行
- 算子接口标准化
- Feasibility oracle + objective recompute oracle（Opus 写，人审核）
- unit tests / regression tests
- benchmark 实例 + split 划分

**交付**：
- CLI
- ≥10 轮真实 LLM 实验
- Campaign summary report
- Failure distribution report

**验收**：
- 至少 1 个被 Contract 拦截的越界 patch
- 至少 1 个被 Verification 拦截的语义错误
- 至少 1 个通过 screening 的候选
- 至少 1 个完成 frozen 的候选（promote 或 reject）
- 全链路 lineage 可查
- Mock LLM + 真实 LLM 都能跑

---

## 7. 技术选型

| 依赖 | 用途 |
|---|---|
| Python 3.11+ | 主语言 |
| pydantic v2 | 数据模型 + 配置校验 |
| sqlite3 | Lineage Registry |
| numpy | bootstrap CI / 统计计算 |
| jinja2 | prompt 模板 |
| ast / libcst | 静态检查 |
| difflib | diff 计算 |
| psutil + resource | 资源限制 |
| click / typer | CLI |
| pytest | 框架自身测试 |

不引入：LangChain、MCP、Docker（MVP）、Web 框架。

---

## 8. 前置条件清单

以下由人（BigBOSS）完成，框架开发可并行但 Phase 6 依赖：

- [ ] 仓配协同 solver 入口标准化（接受命令行参数，输出 JSON）
- [ ] 算子接口统一为 `execute(solution, rng) -> Solution`
- [ ] 算子注册机制（registry.yaml）
- [ ] Feasibility oracle spec
- [ ] Objective recompute spec
- [ ] Unit tests（至少覆盖接口合规）
- [ ] Benchmark 实例准备 + split 划分
- [ ] Canary cases 选取

---

*本文档基于 scion-architecture-v3.md，面向 v0.1 MVP 实现。*
