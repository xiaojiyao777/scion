"""Frozen public types and internal facts for M32 postrun scoring."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, NamedTuple, NoReturn

from scion.core.execution_outcome import ExecutionOutcome

HISTORY_REPLAY_BASIS_UNAVAILABLE = "HISTORY_REPLAY_BASIS_UNAVAILABLE"
SCIENTIFIC_DELEGATION_INCOMPLETE = "SCIENTIFIC_DELEGATION_INCOMPLETE"
INITIAL_CELL_DATA_UNAVAILABLE = "INITIAL_CELL_DATA_UNAVAILABLE"
BLOCK_UNSCORABLE = "BLOCK_UNSCORABLE"
CANDIDATE_FEASIBILITY_EVIDENCE_UNAVAILABLE = (
    "CANDIDATE_FEASIBILITY_EVIDENCE_UNAVAILABLE"
)
_REQUEST_KINDS = (
    "hypothesis",
    "hypothesis_research_turn",
    "code",
    "code_research_turn",
    "code_research_finalize",
    "other",
)
_OUTCOMES = tuple(member.value for member in ExecutionOutcome)
_SCIENTIFIC_OUTCOMES = frozenset(
    {ExecutionOutcome.EVALUATED.value, ExecutionOutcome.RESEARCH_REJECTED.value}
)
_INCOMPLETE_REASON_CODES = frozenset(
    {
        "HYPOTHESIS_RESEARCH_TRANSCRIPT_EXHAUSTED",
        "HYPOTHESIS_RESEARCH_TURN_CAP_EXHAUSTED",
        "HYPOTHESIS_RESEARCH_RESULT_CAP_EXHAUSTED",
        "CODE_RESEARCH_TRANSCRIPT_EXHAUSTED",
        "CODE_RESEARCH_TURN_CAP_EXHAUSTED",
        "CODE_RESEARCH_RESULT_CAP_EXHAUSTED",
        "PROVIDER_CALL_CAP_EXHAUSTED",
        "OUTER_HARDWALL_EXCEEDED",
    }
)
_FORBIDDEN_DECISIONS = frozenset({"queue_frozen", "promote", "expand_validation"})
_SCREENING_DECISIONS = frozenset(
    {"continue_explore", "abandon", "expand_screening", "queue_validate"}
)
_SCREENING_GATES = frozenset({"pass", "fail", "unclear", "expand", "continue"})
_FORBIDDEN_STAGES = frozenset({"validation", "frozen", "retained"})
_H_FIELDS = (
    "text",
    "change_locus",
    "action",
    "target_file",
    "predicted_direction",
    "target_weakness",
    "expected_effect",
    "suggested_weight",
)
_ATTEMPT_COUNTERS = (
    "hypothesis_candidates_completed",
    "hypothesis_candidates_selected",
    "hypotheses_exported",
    "patches_completed",
    "code_candidates_ready",
)
_SHARED_TERMINAL_FIELDS = (
    "proposal_runtime",
    "run_result",
    "campaign_mode",
    "proposal_runtime_mode",
    "n_steps",
    "total_rounds",
    "n_experiments",
    "screened_experiments",
)
_INCOMPLETE_STOP_FRAGMENTS = (
    "HARDWALL",
    "INTERRUPT",
    "PROVIDER",
    "SOLVER",
    "TRANSCRIPT_EXHAUSTED",
    "TURN_CAP_EXHAUSTED",
    "RESULT_CAP_EXHAUSTED",
)


class ResearchEffectivenessInputError(ValueError):
    """An ordinary artifact failed one fixed, body-free input check."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class InitialCell(NamedTuple):
    """Identity-free numeric evidence for one physical initial cell."""

    candidate_total_distance: float
    b0_total_distance: float


@dataclass(frozen=True)
class ResearchEffectivenessExpectation:
    """Frozen facts that terminal artifacts are not allowed to self-declare."""

    problem_id: str
    expected_initial_case_count: int
    expected_initial_pair_count: int
    a_cap: int
    p_cap: int
    max_hypothesis_candidates: int

    def __post_init__(self) -> None:
        if not isinstance(self.problem_id, str) or not self.problem_id.strip():
            raise ValueError("INVALID_EXPECTED_PROBLEM_ID")
        for name in (
            "expected_initial_case_count",
            "expected_initial_pair_count",
            "a_cap",
            "p_cap",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError("INVALID_RESEARCH_EFFECTIVENESS_EXPECTATION")
        if type(self.max_hypothesis_candidates) is not int or (
            self.max_hypothesis_candidates not in {1, 2}
        ):
            raise ValueError("INVALID_MAX_HYPOTHESIS_CANDIDATES")

    @property
    def proposal_runtime_mode(self) -> str:
        return (
            "bounded_hypothesis_candidates_v1"
            if self.max_hypothesis_candidates == 2
            else "bounded_research_v1"
        )


@dataclass(frozen=True)
class LoadedHistoryAvailable:
    """A common frozen replay corpus, including a known-empty corpus."""

    records: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        if type(self.records) is not tuple:
            raise ValueError("LOADED_HISTORY_RECORDS_MUST_BE_A_TUPLE")


@dataclass(frozen=True)
class LoadedHistoryUnavailable:
    """An explicit statement that the common replay basis is unavailable."""

    reason: str = HISTORY_REPLAY_BASIS_UNAVAILABLE

    def __post_init__(self) -> None:
        if self.reason != HISTORY_REPLAY_BASIS_UNAVAILABLE:
            raise ValueError("INVALID_LOADED_HISTORY_UNAVAILABLE_REASON")


@dataclass(frozen=True, repr=False)
class ResearchEffectivenessArmArtifacts:
    """One identity-bearing arm input kept outside the public comparison result."""

    status: Mapping[str, Any]
    summary: Mapping[str, Any]
    current_history: tuple[Mapping[str, Any], ...]
    expectation: ResearchEffectivenessExpectation
    initial_cells: tuple[tuple[InitialCell, ...], ...] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, Mapping) or not isinstance(
            self.summary, Mapping
        ):
            raise TypeError("ARM_ARTIFACT_MAPPING_INVALID")
        if type(self.current_history) is not tuple or any(
            not isinstance(record, Mapping) for record in self.current_history
        ):
            raise ValueError("ARM_CURRENT_HISTORY_MUST_BE_A_TUPLE")
        if type(self.expectation) is not ResearchEffectivenessExpectation:
            raise ValueError("ARM_EXPECTATION_INVALID")
        if self.initial_cells is not None and (
            type(self.initial_cells) is not tuple
            or any(type(cells) is not tuple for cells in self.initial_cells)
        ):
            raise ValueError("ARM_INITIAL_CELLS_MUST_BE_TUPLES")

    def __repr__(self) -> str:
        return "ResearchEffectivenessArmArtifacts(<redacted>)"


@dataclass(frozen=True, repr=False)
class MatchedResearchEffectivenessBlock:
    """One K=1/K=2 block sharing exactly one loaded-history basis."""

    k1: ResearchEffectivenessArmArtifacts
    k2: ResearchEffectivenessArmArtifacts
    loaded_history: LoadedHistoryAvailable | LoadedHistoryUnavailable

    def __post_init__(self) -> None:
        if (
            type(self.k1) is not ResearchEffectivenessArmArtifacts
            or type(self.k2) is not ResearchEffectivenessArmArtifacts
        ):
            raise ValueError("MATCHED_BLOCK_ARM_INVALID")
        if type(self.loaded_history) not in {
            LoadedHistoryAvailable,
            LoadedHistoryUnavailable,
        }:
            raise ValueError("MATCHED_BLOCK_HISTORY_INVALID")

    def __repr__(self) -> str:
        return "MatchedResearchEffectivenessBlock(<redacted>)"


_HKey = tuple[Any, ...]
_PatchKey = tuple[tuple[str, str, str], ...]
_PairKey = tuple[_HKey, _PatchKey]


@dataclass(frozen=True, repr=False)
class _ArmEvidence:
    exported_h_keys: tuple[_HKey, ...]
    pair_keys: tuple[_PairKey, ...]
    f_pair_keys: tuple[_PairKey, ...] | None

    def __repr__(self) -> str:
        return "_ArmEvidence(<redacted>)"


@dataclass(frozen=True, repr=False)
class _ArmEvaluation:
    report: dict[str, Any]
    evidence: _ArmEvidence

    def __repr__(self) -> str:
        return "_ArmEvaluation(<redacted>)"


@dataclass(frozen=True)
class _Attempt:
    round_num: int
    accounting_state: str
    budget_admitted: int
    by_request_kind: dict[str, int]
    hypothesis_candidates_completed: int
    hypothesis_candidates_selected: int
    hypotheses_exported: int
    patches_completed: int
    code_candidates_ready: int


@dataclass(frozen=True)
class _ProtocolFacts:
    n_cases: int
    total_pairs: int
    attempted_pairs: int
    valid_pairs: int
    failed_pairs: int
    candidate_failed_pairs: int
    champion_failed_pairs: int
    shared_failed_pairs: int
    bilateral_failed_pairs: int
    protected_regression: bool
    gate_outcome: str
    candidate_attributable_infeasible_pairs: int | None

    @property
    def candidate_only_failure(self) -> bool:
        return self.candidate_failed_pairs - self.bilateral_failed_pairs > 0

    @property
    def any_failure(self) -> bool:
        return any(
            (
                self.failed_pairs,
                self.candidate_failed_pairs,
                self.champion_failed_pairs,
                self.shared_failed_pairs,
                self.bilateral_failed_pairs,
            )
        )

    def exact_initial_matrix(
        self, expectation: ResearchEffectivenessExpectation
    ) -> bool:
        return (
            self.n_cases == expectation.expected_initial_case_count
            and self.total_pairs == expectation.expected_initial_pair_count
            and self.attempted_pairs == expectation.expected_initial_pair_count
            and self.valid_pairs == expectation.expected_initial_pair_count
            and not self.any_failure
        )


@dataclass(frozen=True)
class _JoinedRow:
    summary: Mapping[str, Any]
    history: Mapping[str, Any]
    attempt: _Attempt | None
    h_key: tuple[Any, ...] | None
    patch_key: tuple[tuple[str, str, str], ...] | None
    protocol: _ProtocolFacts | None
    expanded: bool
    canary_classification: str | None
    canary_candidate_attributable_infeasible_pairs: int | None


@dataclass(frozen=True)
class _Physical:
    attempts: tuple[_Attempt, ...]
    rows: tuple[_JoinedRow, ...]
    p_charged: int
    aggregate_by_kind: dict[str, int]
    initial_rows: tuple[_JoinedRow, ...]
    incomplete: bool


@dataclass(frozen=True)
class _OriginQuality:
    candidate_failure: bool = False
    champion_failure: bool = False
    shared_failure: bool = False
    bilateral_failure: bool = False
    protected_regression: bool = False
    candidate_only_failure: bool = False
    candidate_attributable_infeasibility: bool = False

    @property
    def blocks_quality(self) -> bool:
        return (
            self.candidate_failure
            or self.champion_failure
            or self.shared_failure
            or self.bilateral_failure
            or self.protected_regression
        )


def _canary_classification(
    step: Mapping[str, Any], history: Mapping[str, Any]
) -> str | None:
    raw_canary = step.get("canary_result")
    if raw_canary is None:
        return None
    canary = _as_mapping(raw_canary, "SUMMARY_CANARY_INVALID")
    if canary.get("passed") is True:
        return (
            "unknown"
            if "failure_category" in canary or "reason_codes" in canary
            else "passed"
        )
    reason_codes = canary.get("reason_codes")
    decision = history.get("decision")
    decision_codes = (
        _as_mapping(decision, "HISTORY_DECISION_INVALID").get("reason_codes")
        if decision is not None
        else None
    )
    if (
        not isinstance(reason_codes, list)
        or len(reason_codes) != 1
        or not isinstance(reason_codes[0], str)
        or not isinstance(decision_codes, list)
        or reason_codes[0] not in decision_codes
    ):
        return "unknown"
    category = canary.get("failure_category")
    if not isinstance(category, str):
        return "unknown"
    return {
        ("candidate_failure", "CANARY_FAILED"): "candidate",
        ("incomplete_evidence", "CANARY_CHAMPION_FAILURE"): "champion",
        ("incomplete_evidence", "CANARY_SHARED_FAILURE"): "shared",
        ("incomplete_evidence", "CANARY_BILATERAL_FAILURE"): "bilateral",
    }.get((category, reason_codes[0]), "unknown")


def _canary_infeasible_pairs(
    value: Any,
    *,
    classification: str | None,
) -> int | None:
    if value is None:
        return None
    canary = _as_mapping(value, "SUMMARY_CANARY_INVALID")
    count = canary.get("candidate_attributable_infeasible_pairs")
    if type(count) is not int or count not in {0, 1}:
        return None
    if classification == "candidate":
        return count
    if classification in {"passed", "champion", "shared", "bilateral"}:
        return 0 if count == 0 else None
    return None


def _h_key(value: Any) -> tuple[Any, ...] | None:
    if value is None:
        return None
    item = _as_mapping(value, "HYPOTHESIS_VALUE_INVALID")
    if tuple(item) != _H_FIELDS:
        _fail("HYPOTHESIS_VALUE_INVALID")
    for field in ("text", "change_locus", "target_weakness", "expected_effect"):
        if not isinstance(item[field], str):
            _fail("HYPOTHESIS_VALUE_INVALID")
    if any(
        not item[field].strip() for field in ("text", "change_locus", "target_weakness")
    ):
        _fail("HYPOTHESIS_REQUIRED_TEXT_INVALID")
    if item["action"] not in {"modify", "create_new", "remove"}:
        _fail("HYPOTHESIS_ACTION_INVALID")
    if item["predicted_direction"] not in {
        "improve",
        "tradeoff",
        "exploratory",
    }:
        _fail("HYPOTHESIS_DIRECTION_INVALID")
    target = item["target_file"]
    if not isinstance(target, str) or not target.strip():
        _fail("HYPOTHESIS_TARGET_INVALID")
    weight = item["suggested_weight"]
    if weight is not None and (type(weight) is not float or not math.isfinite(weight)):
        _fail("HYPOTHESIS_WEIGHT_INVALID")
    return tuple(item[field] for field in _H_FIELDS)


def _patch_key(value: Any) -> tuple[tuple[str, str, str], ...] | None:
    if value is None:
        return None
    item = _as_mapping(value, "PATCH_VALUE_INVALID")
    if set(item) != {"changes"} or not isinstance(item["changes"], list):
        _fail("PATCH_VALUE_INVALID")
    changes: list[tuple[str, str, str]] = []
    for raw in item["changes"]:
        change = _as_mapping(raw, "PATCH_VALUE_INVALID")
        if tuple(change) != ("file_path", "action", "source"):
            _fail("PATCH_VALUE_INVALID")
        if (
            not isinstance(change["file_path"], str)
            or change["action"] not in {"modify", "create", "delete"}
            or not isinstance(change["source"], str)
        ):
            _fail("PATCH_VALUE_INVALID")
        changes.append((change["file_path"], change["action"], change["source"]))
    if not changes:
        _fail("PATCH_VALUE_INVALID")
    return tuple(changes)


def _history_decision(history: Mapping[str, Any]) -> str | None:
    decision = history.get("decision")
    if decision is None:
        return None
    return str(_as_mapping(decision, "HISTORY_DECISION_INVALID").get("value") or "")


def _reject_forbidden_stage(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        _fail("STAGE_VALUE_INVALID")
    if value.strip().casefold() in _FORBIDDEN_STAGES:
        _fail("FORBIDDEN_M32_STAGE")


def _is_incomplete_reason(value: str) -> bool:
    normalized = value.strip().upper()
    return normalized in _INCOMPLETE_REASON_CODES or any(
        fragment in normalized for fragment in _INCOMPLETE_STOP_FRAGMENTS
    )


def _as_mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        _fail(code)
    return value


def _nonnegative_int(value: Any, code: str) -> int:
    if type(value) is not int or value < 0:
        _fail(code)
    return value


def _positive_int(value: Any, code: str) -> int:
    if type(value) is not int or value <= 0:
        _fail(code)
    return value


def _fail(code: str) -> NoReturn:
    raise ResearchEffectivenessInputError(code)
