"""Qualification-only campaign configuration and durable progress facts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

QUALIFICATION_BOUNDARY_REACHED = "qualification_boundary_reached"
QUALIFICATION_NOT_REACHED = "qualification_not_reached"
QUALIFICATION_READY_DISPOSITION = "ready_for_postrun_qualification_audit"


@dataclass(frozen=True)
class QualificationOnlyConfig:
    """Independent hard limits for one explicitly bounded qualification run."""

    max_proposal_attempts: int = 4
    max_verified_candidate_chains: int = 2
    max_formal_screening_stages: int = 4

    def __post_init__(self) -> None:
        for name in (
            "max_proposal_attempts",
            "max_verified_candidate_chains",
            "max_formal_screening_stages",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"qualification-only {name} must be a positive int")

    def to_projection(self) -> dict[str, int]:
        return {
            "max_proposal_attempts": self.max_proposal_attempts,
            "max_verified_candidate_chains": self.max_verified_candidate_chains,
            "max_formal_screening_stages": self.max_formal_screening_stages,
        }


@dataclass(frozen=True)
class QualificationProgress:
    """Terminal/status-safe counters for the qualification-only state machine."""

    config: QualificationOnlyConfig
    proposal_attempts: int = 0
    verified_candidate_chains: int = 0
    formal_screening_stages: int = 0
    initial_screening_stages: int = 0
    expanded_screening_stages: int = 0

    def to_projection(self, *, stop_reason: str = "") -> dict[str, Any]:
        if stop_reason == QUALIFICATION_BOUNDARY_REACHED:
            disposition = QUALIFICATION_READY_DISPOSITION
        elif stop_reason == QUALIFICATION_NOT_REACHED:
            disposition = QUALIFICATION_NOT_REACHED
        elif stop_reason:
            disposition = "incomplete"
        else:
            disposition = "pending"
        return {
            "mode": "qualification_only",
            "limits": self.config.to_projection(),
            "proposal_attempts": self.proposal_attempts,
            "verified_candidate_chains": self.verified_candidate_chains,
            "formal_screening_stages": self.formal_screening_stages,
            "initial_screening_stages": self.initial_screening_stages,
            "expanded_screening_stages": self.expanded_screening_stages,
            "disposition": disposition,
        }


class QualificationProposalBudgetExhausted(RuntimeError):
    """Raised before branch/H creation when no new proposal may be dispatched."""


@dataclass
class QualificationRuntime:
    """Single-threaded qualification dispatch accounting shared by loop/runner."""

    config: QualificationOnlyConfig
    proposal_attempts: int = 0
    formal_screening_stages: int = 0
    initial_screening_stages: int = 0
    expanded_screening_stages: int = 0
    pending_expansion_branch_id: str | None = None
    verified_candidate_branch_ids: set[str] = field(default_factory=set)
    candidate_screening_stage_counts: dict[str, int] = field(default_factory=dict)
    started: bool = False

    def begin_run(self) -> None:
        """Mark this fresh campaign runtime as consumed exactly once."""

        if self.started:
            raise RuntimeError("qualification-only campaign already started")
        self.started = True

    def progress(self) -> QualificationProgress:
        return QualificationProgress(
            config=self.config,
            proposal_attempts=self.proposal_attempts,
            verified_candidate_chains=len(self.verified_candidate_branch_ids),
            formal_screening_stages=self.formal_screening_stages,
            initial_screening_stages=self.initial_screening_stages,
            expanded_screening_stages=self.expanded_screening_stages,
        )

    def can_start_proposal(self) -> bool:
        return (
            self.pending_expansion_branch_id is None
            and self.proposal_attempts < self.config.max_proposal_attempts
            and len(self.verified_candidate_branch_ids)
            < self.config.max_verified_candidate_chains
            and self.formal_screening_stages
            < self.config.max_formal_screening_stages
        )

    def reserve_proposal_attempt(self) -> None:
        if not self.can_start_proposal():
            raise QualificationProposalBudgetExhausted(
                "qualification-only proposal budget exhausted"
            )
        self.proposal_attempts += 1

    def authorize_expansion(self, branch_id: str) -> bool:
        return (
            bool(branch_id)
            and branch_id == self.pending_expansion_branch_id
            and self.formal_screening_stages
            < self.config.max_formal_screening_stages
        )

    def record_verified_candidate(self, branch_id: str) -> None:
        if not branch_id:
            raise ValueError("qualification verified candidate requires branch_id")
        if branch_id in self.verified_candidate_branch_ids:
            return
        if (
            len(self.verified_candidate_branch_ids)
            >= self.config.max_verified_candidate_chains
        ):
            raise ValueError("qualification verified candidate cap exceeded")
        self.verified_candidate_branch_ids.add(branch_id)

    def record_screening_stage(self, branch_id: str, *, expanded: bool) -> None:
        if branch_id not in self.verified_candidate_branch_ids:
            raise ValueError("qualification screening candidate was not verified")
        if (
            self.formal_screening_stages
            >= self.config.max_formal_screening_stages
        ):
            raise ValueError("qualification formal screening stage cap exceeded")
        previous = self.candidate_screening_stage_counts.get(branch_id, 0)
        expected = 1 if expanded else 0
        if previous != expected:
            raise ValueError("qualification candidate screening sequence invalid")
        self.candidate_screening_stage_counts[branch_id] = previous + 1
        self.formal_screening_stages += 1
        if expanded:
            self.expanded_screening_stages += 1
            self.pending_expansion_branch_id = None
        else:
            self.initial_screening_stages += 1

    def request_expansion(self, branch_id: str) -> None:
        if self.candidate_screening_stage_counts.get(branch_id) != 1:
            raise ValueError("qualification expansion requires one initial screen")
        self.pending_expansion_branch_id = branch_id

    def validate_chain_retirement(self, branch_id: str) -> None:
        """Require a pending expansion to retire only its exact branch."""

        pending = self.pending_expansion_branch_id
        if pending is not None and branch_id != pending:
            raise ValueError("qualification pending expansion branch mismatch")

    def record_chain_retired(self, branch_id: str) -> None:
        """Clear exact pending-expansion authority after parking succeeds."""

        self.validate_chain_retirement(branch_id)
        if self.pending_expansion_branch_id == branch_id:
            self.pending_expansion_branch_id = None

    def normal_stop_before_dispatch(self) -> tuple[str, str | None] | None:
        pending = self.pending_expansion_branch_id
        if pending is not None:
            if (
                self.formal_screening_stages
                >= self.config.max_formal_screening_stages
            ):
                return QUALIFICATION_NOT_REACHED, pending
            return None
        if not self.can_start_proposal():
            return QUALIFICATION_NOT_REACHED, None
        return None


def normalize_qualification_only_config(
    value: QualificationOnlyConfig | Mapping[str, Any] | None,
) -> QualificationOnlyConfig | None:
    """Normalize only an explicit opt-in value and reject ambiguous mappings."""

    if value is None:
        return None
    if isinstance(value, QualificationOnlyConfig):
        return value
    if not isinstance(value, Mapping):
        raise TypeError(
            "qualification_only must be a QualificationOnlyConfig, mapping, or None"
        )
    allowed = {
        "max_proposal_attempts",
        "max_verified_candidate_chains",
        "max_formal_screening_stages",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(
            "qualification-only config has unknown fields: "
            + ", ".join(sorted(str(field) for field in unknown))
        )
    return QualificationOnlyConfig(**dict(value))


__all__ = [
    "QUALIFICATION_BOUNDARY_REACHED",
    "QUALIFICATION_NOT_REACHED",
    "QUALIFICATION_READY_DISPOSITION",
    "QualificationOnlyConfig",
    "QualificationProgress",
    "QualificationProposalBudgetExhausted",
    "QualificationRuntime",
    "normalize_qualification_only_config",
]
