from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Literal, Union, Any, Dict, List, Tuple
import uuid

# --- Branch & Campaign Enums ---

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

class ExperimentState(Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED_INFRA = "failed_infra"
    FAILED_VERIFICATION = "failed_verification"

class ExperimentStage(Enum):
    SCREENING = "screening"
    VALIDATION = "validation"
    FROZEN = "frozen"

class Decision(Enum):
    CONTINUE_EXPLORE = "continue_explore"
    EXPAND_SCREENING = "expand_screening"
    QUEUE_VALIDATE = "queue_validate"
    EXPAND_VALIDATION = "expand_validation"
    QUEUE_FROZEN = "queue_frozen"
    PROMOTE = "promote"
    ABANDON = "abandon"

# --- Proposals (Tainted from LLM) ---

@dataclass
class HypothesisProposal:
    hypothesis_text: str
    change_locus: str
    action: Literal["modify", "create_new", "remove"]
    target_file: Optional[str] = None
    predicted_direction: Literal["improve", "tradeoff", "exploratory"] = "exploratory"
    target_weakness: str = ""
    expected_effect: str = ""
    suggested_weight: Optional[float] = None

@dataclass
class PatchProposal:
    file_path: str
    action: Literal["modify", "create", "delete"]
    code_content: str
    test_hint: Optional[str] = None

# --- Results & Stats ---

@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    severity: Literal["light", "heavy"]
    detail: str
    elapsed_ms: int

@dataclass(frozen=True)
class ContractResult:
    passed: bool
    checks: Tuple[CheckResult, ...]
    failure_reason: Optional[str] = None

@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    checks: Tuple[CheckResult, ...]
    failure_severity: Optional[Literal["light", "heavy"]] = None
    first_failure: Optional[str] = None

@dataclass(frozen=True)
class CanaryResult:
    passed: bool
    reason: Optional[str] = None

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
class ProtocolResult:
    stage: ExperimentStage
    stats: EvalStats
    gate_outcome: Literal["pass", "fail", "unclear", "expand"]
    reason_codes: Tuple[str, ...]
    exposed_summary: str  # Filtered summary for LLM context
    raw_metrics_ref: str  # Path to full JSON metrics
    # Case-level feedback (screening only; empty for validation/frozen)
    pair_feedback: Tuple["PairwiseCaseFeedback", ...] = ()
    case_feedback: Tuple["CaseAggregateFeedback", ...] = ()
    pattern_summary: Optional["ScreeningPatternSummary"] = None


# --- Case-level Feedback (for screening) ---

@dataclass(frozen=True)
class ObjectiveBreakdown:
    """Per-pair breakdown of objectives with 'positive = candidate better' convention."""
    candidate_subcategory_splits: Optional[float] = None
    champion_subcategory_splits: Optional[float] = None
    candidate_total_cost: Optional[float] = None
    champion_total_cost: Optional[float] = None
    # Deltas: positive = candidate is better
    delta_subcategory_splits: Optional[float] = None  # champ - cand
    delta_total_cost: Optional[float] = None           # champ - cand
    # Which objective level decided win/loss
    decisive_objective: Literal[
        "business_aggregation", "cost", "efficiency", "tie"
    ] = "tie"


@dataclass(frozen=True)
class PairwiseCaseFeedback:
    """Single instance × seed A/B comparison result."""
    case_id: str
    seed: int
    comparison: Literal["win", "loss", "tie"]
    delta: float  # cost delta, positive = candidate better
    objective_breakdown: ObjectiveBreakdown
    case_features: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CaseAggregateFeedback:
    """Aggregated feedback for one instance across all seeds."""
    case_id: str
    n_pairs: int
    wins: int
    losses: int
    ties: int
    win_rate: float
    dominant_result: Literal["win", "loss", "tie", "mixed"]
    dominant_decisive_objective: Literal[
        "business_aggregation", "cost", "efficiency", "mixed", "tie"
    ]
    median_delta_total_cost: Optional[float] = None
    median_delta_subcategory_splits: Optional[float] = None
    seed_consistency: float = 0.0  # max(win,loss,tie) / n_pairs
    case_features: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScreeningPatternSummary:
    """Code-generated pattern summary across all cases in a screening round."""
    total_cases: int
    winning_cases: int
    losing_cases: int
    mixed_cases: int
    wins_by_decisive_objective: Dict[str, int] = field(default_factory=dict)
    losses_by_decisive_objective: Dict[str, int] = field(default_factory=dict)
    wins_by_size_bucket: Dict[str, int] = field(default_factory=dict)
    losses_by_size_bucket: Dict[str, int] = field(default_factory=dict)
    consistent_win_cases: Tuple[str, ...] = ()
    consistent_loss_cases: Tuple[str, ...] = ()
    key_observations: Tuple[str, ...] = ()

# --- Decision Features (The "Safe" Boundary) ---

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
    recent_failure_codes: Tuple[str, ...]
    budget_remaining_ratio: float
    expand_count: int = 0  # Number of screening expands on this branch

@dataclass(frozen=True)
class DecisionOutcome:
    decision: Decision
    reason_codes: Tuple[str, ...]
    features_snapshot: DecisionFeatures

# --- Campaign & Branch State ---

@dataclass
class OperatorConfig:
    name: str
    file_path: str
    category: str
    weight: float
    class_name: str

@dataclass
class ChampionState:
    version: int
    operator_pool: Dict[str, OperatorConfig]
    solver_config_hash: str
    code_snapshot_path: str
    code_snapshot_hash: str
    promotion_experiment_id: Optional[str] = None
    promoted_at: Optional[str] = None

@dataclass
class Branch:
    branch_id: str
    state: BranchState
    base_champion_id: int
    base_champion_hash: str
    current_code_hash: Optional[str] = None
    last_clean_code_hash: Optional[str] = None
    retry_count: int = 0
    expand_count: int = 0  # Tracks screening expand rounds
    failure_codes: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    direction: Optional[str] = None  # Branch direction: '{change_locus}: {hypothesis_text[:100]}'

@dataclass
class HypothesisRecord:
    hypothesis_id: str
    branch_id: str
    change_locus: str
    action: str
    status: str
    target_file: Optional[str] = None
    parent_hypothesis_id: Optional[str] = None
    suggested_weight: Optional[float] = None
    hypothesis_text: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

# --- Solver Output ---

@dataclass(frozen=True)
class SolverOutput:
    """Parsed JSON output from a solver run."""
    vehicles: Dict[str, Any]
    assignment: Dict[str, str]
    objective: Dict[str, Any]
    feasible: bool

# --- Infrastructure ---

@dataclass(frozen=True)
class RunResult:
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: int
    output: Optional[SolverOutput] = None
    output_path: Optional[str] = None
    error_category: Optional[Literal["timeout", "oom", "crash"]] = None

@dataclass(frozen=True)
class FailureEvent:
    category: Literal["proposal", "contract", "verification_light", "verification_heavy", "infra", "evaluation"]
    detail: str
    timestamp: datetime = field(default_factory=datetime.now)
    retryable: bool = True


@dataclass(frozen=True)
class WeightConfig:
    weights: Dict[str, float]
    source: Literal["uniform", "optimized", "manual"]
    optimization_id: Optional[str] = None


@dataclass(frozen=True)
class WeightOptimizationResult:
    baseline_weights: Dict[str, float]
    best_weights: Dict[str, float]
    baseline_score: float
    best_score: float
    improved: bool
    n_evaluations: int
    elapsed_seconds: float
    observations_ref: str  # path to observations JSON


@dataclass
class StepRecord:
    """Record of one completed proposal+evaluation cycle (explore step).

    Stored in CampaignManager._step_history and passed to ContextManager
    so the LLM receives a rich history of prior attempts on each branch.

    failure_stage values:
        'hypothesis_contract' — hypothesis failed ContractGate
        'code_generation'     — LLM failed to produce a patch
        'patch_contract'      — patch failed ContractGate
        'workspace'           — workspace setup / apply_patch failed
        'verification'        — VerificationGate failed (light or heavy)
        'screening'           — experiment returned a non-promote result
        None                  — no failure (reached _apply_decision_and_finalize)
    """
    round_num: int
    branch_id: str
    hypothesis: HypothesisProposal
    patch: Optional[PatchProposal]
    contract_passed: bool
    verification_passed: bool
    protocol_result: Optional[ProtocolResult]
    decision: Decision
    failure_stage: Optional[str]
    failure_detail: Optional[str]
    verification_detail: Optional[str] = None  # Full verification failure detail for LLM diagnosis
    code_archive_ref: Optional[str] = None  # 归档目录路径
    cache_stats: Optional[Dict[str, int]] = None  # {"total": N, "cache_read": M, "cache_create": K}
