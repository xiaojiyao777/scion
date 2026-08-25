from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
)

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
    PARKED_LINEAGE = "parked_lineage"
    STALE = "stale"
    STALE_WEIGHT_UPDATE = "stale_weight_update"  # J4: re-screen needed after weight opt
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
class PatchFileChange:
    file_path: str
    action: Literal["modify", "create", "delete"]
    code_content: str
    test_hint: Optional[str] = None


@dataclass
class PatchProposal:
    file_path: str
    action: Literal["modify", "create", "delete"]
    code_content: str
    test_hint: Optional[str] = None
    additional_changes: Tuple[PatchFileChange, ...] = ()

    def iter_file_changes(self) -> Tuple[PatchFileChange, ...]:
        return patch_file_changes(self)


def patch_file_changes(patch: PatchProposal) -> Tuple[PatchFileChange, ...]:
    """Return primary plus additional file changes for a patch proposal."""
    changes = [
        PatchFileChange(
            file_path=patch.file_path,
            action=patch.action,
            code_content=patch.code_content,
            test_hint=patch.test_hint,
        )
    ]
    for change in patch.additional_changes or ():
        if isinstance(change, PatchFileChange):
            changes.append(change)
        elif isinstance(change, dict):
            changes.append(PatchFileChange(**change))
        else:
            changes.append(
                PatchFileChange(
                    file_path=getattr(change, "file_path"),
                    action=getattr(change, "action"),
                    code_content=getattr(change, "code_content"),
                    test_hint=getattr(change, "test_hint", None),
                )
            )
    return tuple(changes)


# --- Results & Stats ---

@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    severity: Literal["light", "heavy"]
    detail: str
    elapsed_ms: int
    metadata: Dict[str, Any] = field(default_factory=dict)

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
    details: Dict[str, Any] = field(default_factory=dict)
    failure_category: str = ""
    reason_codes: Tuple[str, ...] = ()
    candidate_attributable_infeasible_pairs: Optional[int] = None

@dataclass(frozen=True)
class MetricEvalStats:
    metric_name: str
    median_delta: float
    ci_low: float
    ci_high: float
    n_cases: int


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
    # The selected statistical metric is the problem-owned measurement effect
    # metric. All objective rows remain available in metric_stats for analysis.
    statistical_status: Optional[Literal["positive", "negative", "uncertain", "tie"]] = None
    statistical_metric: Optional[str] = None
    metric_stats: Tuple[MetricEvalStats, ...] = ()
    protected_objective_regressions: Tuple[str, ...] = ()
    runtime_ratio_median: Optional[float] = None
    runtime_delta_median_ms: Optional[float] = None
    runtime_regression_rate: Optional[float] = None
    runtime_pairs: int = 0
    total_pairs: int = 0
    attempted_pairs: int = 0
    valid_pairs: int = 0
    failed_pairs: int = 0
    candidate_failed_pairs: int = 0
    champion_failed_pairs: int = 0
    # Pair-local attribution prevents a dual-side execution incident from
    # being flattened into a candidate-only hard failure.  Shared failures
    # have equivalent evidence on both sides; bilateral failures have
    # distinct evidence on both sides.
    shared_failed_pairs: int = 0
    bilateral_failed_pairs: int = 0
    pair_wins: int = 0
    pair_losses: int = 0
    pair_ties: int = 0
    runtime_evidence_status: Literal[
        "sufficient",
        "insufficient",
    ] = "sufficient"

@dataclass(frozen=True)
class ProtocolResult:
    stage: ExperimentStage
    stats: EvalStats
    gate_outcome: Literal["pass", "fail", "unclear", "expand", "continue"]
    reason_codes: Tuple[str, ...]
    exposed_summary: str  # Filtered summary for LLM context
    raw_metrics_ref: str  # Internal path to full JSON metrics; public payloads redact it.
    objective_semantics: str = "unknown"
    case_ids: Tuple[str, ...] = ()
    seed_set: Tuple[int, ...] = ()
    # Case-level feedback (screening only; empty for validation/frozen)
    pair_feedback: Tuple["PairwiseCaseFeedback", ...] = ()
    case_feedback: Tuple["CaseAggregateFeedback", ...] = ()
    pattern_summary: Optional["ScreeningPatternSummary"] = None
    selected_surface: Optional[str] = None
    candidate_surface_runtime_summary: Dict[str, Any] = field(default_factory=dict)
    candidate_phase_telemetry_summary: Dict[str, Any] = field(default_factory=dict)
    candidate_runtime_failure_categories: Dict[str, int] = field(default_factory=dict)
    candidate_first_runtime_failure: Optional[Dict[str, Any]] = None
    candidate_operator_attempts: int = 0
    candidate_operator_accepted: int = 0
    candidate_operator_errors: int = 0
    candidate_operator_invalid_outputs: int = 0
    candidate_policy_errors: int = 0
    candidate_construction_errors: int = 0
    candidate_portfolio_errors: int = 0
    candidate_runtime_stop_reasons: Dict[str, int] = field(default_factory=dict)
    runtime_confidence: str = "high"
    runtime_model: Optional[Literal["comparative", "budget_exhausting"]] = None
    opportunity_status: str = "unknown"
    opportunity_diagnostics: Tuple[str, ...] = ()
    mechanism_evidence: Dict[str, Any] = field(default_factory=dict)
    # Appended to preserve the historical positional constructor prefix.
    case_aggregation_method: str = "seed_vote_majority"
    case_effect_metric: str = ""
    case_equivalence_band: float = 0.0
    candidate_attributable_infeasible_pairs: Optional[int] = None


@dataclass(frozen=True)
class PairwiseCaseFeedback:
    """Single instance × seed A/B comparison result."""
    case_id: str
    seed: int
    comparison: Literal["win", "loss", "tie"]
    delta: float  # scalar delta, positive = candidate better
    objective_comparison: Any = None  # ObjectiveComparison from problem/objectives.py
    case_features: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CaseAggregateFeedback:
    """Formal case direction plus descriptive seed-pattern evidence."""
    case_id: str
    n_pairs: int
    wins: int
    losses: int
    ties: int
    win_rate: float
    dominant_result: Literal["win", "loss", "tie", "mixed"]
    # Declared effect metric for paired aggregation, or the legacy pair-vote metric.
    decisive_metric: str = "tie"
    median_deltas: Dict[str, float] = field(default_factory=dict)
    # Descriptive seed agreement only; it never enters the formal case direction.
    seed_consistency: float = 0.0
    seed_pattern: Literal["uniform", "heterogeneous"] = "uniform"
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

DecisionRuntimeEvidenceConfidence = Literal[
    "high",
    "sufficient",
    "low",
    "low_sample_diagnostic",
    "missing",
]
DecisionRuntimeEvidenceStatus = Literal[
    "sufficient",
    "insufficient",
]


@dataclass(frozen=True)
class DecisionFeatures:
    hypothesis_action: Literal["modify", "create_new", "remove"]
    stage: Literal["screening", "validation", "frozen"]
    # None means the gate was not run for this invocation (for example a
    # validation/frozen Protocol call over an already accepted source).
    contract_passed: Optional[bool]
    verification_passed: Optional[bool]
    canary_passed: bool
    n_cases: int
    win_rate: Optional[float]
    median_delta: Optional[float]
    ci_low: Optional[float]
    ci_high: Optional[float]
    stale: bool
    recent_failure_codes: Tuple[str, ...]
    wins: int = 0
    losses: int = 0
    ties: int = 0
    runtime_guard_passed: Optional[bool] = None
    runtime_guard_ratio: Optional[float] = None
    runtime_guard_timeout: bool = False
    runtime_ratio_median: Optional[float] = None
    runtime_delta_median_ms: Optional[float] = None
    runtime_regression_rate: Optional[float] = None
    runtime_pairs: int = 0
    runtime_evidence_confidence: DecisionRuntimeEvidenceConfidence = "high"
    runtime_evidence_status: DecisionRuntimeEvidenceStatus = "sufficient"
    protocol_gate_outcome: Optional[Literal["pass", "fail", "unclear", "expand", "continue"]] = None
    protocol_reason_codes: Tuple[str, ...] = ()
    total_pairs: int = 0
    attempted_pairs: int = 0
    valid_pairs: int = 0
    failed_pairs: int = 0
    candidate_failed_pairs: int = 0
    champion_failed_pairs: int = 0
    shared_failed_pairs: int = 0
    bilateral_failed_pairs: int = 0
    pair_wins: int = 0
    pair_losses: int = 0
    pair_ties: int = 0
    statistical_status: Optional[Literal["positive", "negative", "uncertain", "tie"]] = None
    statistical_metric: Optional[str] = None
    # Stage-specific counts for preregistered Protocol sample expansion. These
    # are scientific stage facts, not provider-call or campaign budgets.
    screening_expand_count: int = 0
    validation_expand_count: int = 0

@dataclass(frozen=True)
class DecisionOutcome:
    decision: Decision
    reason_codes: Tuple[str, ...]

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
    code_snapshot_path: str
    promoted_at: Optional[str] = None
    weight_revision: int = 0

@dataclass
class Branch:
    branch_id: str
    state: BranchState
    base_champion_id: int
    # Content digest of the accepted read-only branch workspace.
    current_code_hash: Optional[str] = None
    # Current ordinary H value for in-process validation/frozen/stale work.
    hypothesis: Optional[HypothesisProposal] = None
    # Stage-specific counts for preregistered Protocol sample expansion. A new
    # hypothesis resets them; evaluation increments the active stage count.
    screening_expand_count: int = 0
    validation_expand_count: int = 0
    failure_codes: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    direction: Optional[str] = None  # Branch direction: '{change_locus}: {hypothesis_text}'
    weight_revision: int = 0  # weight revision this branch was last evaluated against

# --- Solver Output ---

@dataclass(frozen=True)
class SolverOutput:
    """Parsed JSON output from a solver run."""
    objective: Dict[str, Any]
    feasible: bool
    runtime: Dict[str, Any] = field(default_factory=dict)
    solution_payload: Dict[str, Any] = field(default_factory=dict)

    def to_raw_mapping(self) -> Dict[str, Any]:
        """Reconstruct the complete solver mapping with stable key ownership."""
        raw: Dict[str, Any] = {
            "objective": dict(self.objective),
            "feasible": bool(self.feasible),
            "runtime": dict(self.runtime),
        }
        for key in sorted(self.solution_payload):
            if key not in raw:
                raw[key] = self.solution_payload[key]
        return raw

# --- Infrastructure ---

@dataclass(frozen=True)
class RunResult:
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: int
    output: Optional[SolverOutput] = None
    error_category: Optional[Literal["timeout", "oom", "crash"]] = None

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
    """Record of one completed proposal or evaluation attempt.

    Stored in CampaignManager._step_history and passed to ContextManager
    so the LLM receives a rich history of prior attempts on each branch.

    failure_stage values:
        'proposal_hypothesis' — no hypothesis was produced
        'hypothesis_contract' — hypothesis failed ContractGate
        'code_generation'     — LLM failed to produce a patch
        'patch_contract'      — patch failed ContractGate
        'workspace'           — workspace setup / apply_patch failed
        'verification'        — VerificationGate failed (light or heavy)
        'evaluation'          — Protocol/evaluation failed before DecisionEngine
        'screening'           — experiment returned a non-promote result
        None                  — no failure (reached _apply_decision_and_finalize)

    decision: None means the step did not reach the Decision Engine (early failure).
              Only set to a real Decision value when the Decision Engine actually ran.
    decision_reason_codes: formal Decision outcome reason codes.
    candidate_parent_scope: host-owned source fact captured before applying the
                            current patch; None preserves conservative legacy output.
    """
    round_num: int
    branch_id: str
    hypothesis: HypothesisProposal | None
    patch: Optional[PatchProposal]
    contract_passed: Optional[bool]
    verification_passed: Optional[bool]
    protocol_result: Optional[ProtocolResult]
    decision: Optional[Decision]
    failure_stage: Optional[str]
    failure_detail: Optional[str]
    decision_reason_codes: Optional[Tuple[str, ...]] = None
    decision_engine_reason_codes: Tuple[str, ...] = ()
    diagnostic_reason_codes: Tuple[str, ...] = ()
    bypass_reason_codes: Tuple[str, ...] = ()
    contract_diagnostics: Tuple[Dict[str, Any], ...] = ()
    canary_result: Optional[CanaryResult] = None
    candidate_parent_scope: Optional[
        Literal["declared_champion", "retained_branch_head"]
    ] = None
    execution_outcome: ExecutionOutcomeRecord | None = None

    def __post_init__(self) -> None:
        record = self.execution_outcome
        if record is not None and not isinstance(record, ExecutionOutcomeRecord):
            raise TypeError("execution_outcome must be an ExecutionOutcomeRecord")
        if self.hypothesis is None:
            if record is None:
                raise ValueError(
                    "a hypothesis-free step requires an execution outcome"
                )
            if record.outcome is ExecutionOutcome.EVALUATED:
                raise ValueError(
                    "a hypothesis-free step cannot be evaluated"
                )
            if self.failure_stage != "proposal_hypothesis":
                raise ValueError(
                    "a hypothesis-free step must fail at proposal_hypothesis"
                )
            if self.patch is not None:
                raise ValueError("a hypothesis-free step cannot carry a patch")
            if self.contract_passed is not None:
                raise ValueError(
                    "a hypothesis-free step cannot carry a Contract result"
                )
            if self.verification_passed is not None:
                raise ValueError(
                    "a hypothesis-free step cannot carry a verification result"
                )
            if self.protocol_result is not None or self.decision is not None:
                raise ValueError(
                    "a hypothesis-free step cannot carry Protocol or Decision data"
                )
            if self.canary_result is not None:
                raise ValueError(
                    "a hypothesis-free step cannot carry a canary result"
                )
            if self.candidate_parent_scope is not None:
                raise ValueError(
                    "a hypothesis-free step cannot carry candidate parent scope"
                )
            if (
                self.decision_reason_codes is not None
                or self.decision_engine_reason_codes
                or self.diagnostic_reason_codes
                or self.bypass_reason_codes
                or self.contract_diagnostics
            ):
                raise ValueError(
                    "a hypothesis-free step cannot carry decision or "
                    "Contract diagnostics"
                )
            if self.failure_detail != record.reason_code:
                raise ValueError(
                    "a hypothesis-free step failure detail must be its reason code"
                )
            if record.detail:
                raise ValueError(
                    "a hypothesis-free step execution detail must be redacted"
                )
            if record.provenance != {"stage": "proposal_hypothesis"}:
                raise ValueError(
                    "a hypothesis-free step provenance must contain only its stage"
                )
        if record is not None and record.outcome is not ExecutionOutcome.EVALUATED:
            if self.decision is not None:
                raise ValueError(
                    "non-evaluated execution outcome cannot carry a Decision"
                )
            if self.protocol_result is not None:
                raise ValueError(
                    "non-evaluated execution outcome cannot carry a ProtocolResult"
                )
