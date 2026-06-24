"""Problem-neutral typed ports for postrun readiness composition."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol


PostrunInventory = Mapping[str, Any]


class PostrunInventoryPort(Protocol):
    """Load postrun artifacts without judging research quality."""

    def load(self, run_root: Path) -> PostrunInventory:
        """Return a stable inventory mapping for a run root."""


@dataclass(frozen=True)
class RunEvidenceLifecycle:
    """Problem-neutral current-run lifecycle and readiness evidence."""

    status: str
    current_run_evidence: bool
    run_validity_status: str = ""
    run_completeness_status: str = ""
    wrapper_exit_status: int | None = None
    postrun_acceptance_status: str = ""
    invalid_infra_only: bool = False
    failed_required_checks: tuple[str, ...] = ()
    failed_optional_checks: tuple[str, ...] = ()
    detail: Mapping[str, Any] = field(default_factory=dict)
    decision_features_excluded: bool = True

    @property
    def ready(self) -> bool:
        """Return true when generic lifecycle evidence is ready for analysis."""

        return (
            self.current_run_evidence
            and not self.invalid_infra_only
            and not self.failed_required_checks
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "current_run_evidence": self.current_run_evidence,
            "run_validity_status": self.run_validity_status,
            "run_completeness_status": self.run_completeness_status,
            "wrapper_exit_status": self.wrapper_exit_status,
            "postrun_acceptance_status": self.postrun_acceptance_status,
            "invalid_infra_only": self.invalid_infra_only,
            "failed_required_checks": list(self.failed_required_checks),
            "failed_optional_checks": list(self.failed_optional_checks),
            "detail": dict(self.detail),
            "ready": self.ready,
            "decision_features_excluded": self.decision_features_excluded,
        }


class RunEvidenceLifecyclePort(Protocol):
    """Reduce inventory data to problem-neutral lifecycle readiness."""

    def evaluate(self, inventory: PostrunInventory) -> RunEvidenceLifecycle:
        """Return current-run lifecycle readiness."""


@dataclass(frozen=True)
class ExposureSummary:
    """Problem-neutral postrun exposure policy summary."""

    status: str
    raw_prompt_excluded: bool = True
    raw_response_excluded: bool = True
    patch_body_excluded: bool = True
    source_body_excluded: bool = True
    failed_required_checks: tuple[str, ...] = ()
    failed_optional_checks: tuple[str, ...] = ()
    detail: Mapping[str, Any] = field(default_factory=dict)
    decision_features_excluded: bool = True

    @property
    def ready(self) -> bool:
        return not self.failed_required_checks

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "raw_prompt_excluded": self.raw_prompt_excluded,
            "raw_response_excluded": self.raw_response_excluded,
            "patch_body_excluded": self.patch_body_excluded,
            "source_body_excluded": self.source_body_excluded,
            "failed_required_checks": list(self.failed_required_checks),
            "failed_optional_checks": list(self.failed_optional_checks),
            "detail": dict(self.detail),
            "ready": self.ready,
            "decision_features_excluded": self.decision_features_excluded,
        }


class ExposurePolicyPort(Protocol):
    """Summarize exposure boundaries without reading problem semantics."""

    def summarize(self, inventory: PostrunInventory) -> ExposureSummary:
        """Return prompt/source/patch/log exposure readiness."""


@dataclass(frozen=True)
class ProblemReviewSummary:
    """Problem-owned review result consumed by generic readiness."""

    problem_family: str
    review_key: str
    status: str
    interpretation: str = ""
    ready: bool = False
    failed_required_checks: tuple[str, ...] = ()
    failed_optional_checks: tuple[str, ...] = ()
    detail: Mapping[str, Any] = field(default_factory=dict)
    proposal_visibility_only: bool = True
    decision_features_excluded: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "problem_family": self.problem_family,
            "review_key": self.review_key,
            "status": self.status,
            "interpretation": self.interpretation,
            "ready": self.ready,
            "failed_required_checks": list(self.failed_required_checks),
            "failed_optional_checks": list(self.failed_optional_checks),
            "detail": dict(self.detail),
            "proposal_visibility_only": self.proposal_visibility_only,
            "decision_features_excluded": self.decision_features_excluded,
        }


class ProblemReviewPort(Protocol):
    """Problem-owned postrun review semantics."""

    problem_family: str

    def review(self, inventory: PostrunInventory) -> ProblemReviewSummary:
        """Return a problem-owned review summary."""


@dataclass(frozen=True)
class PostrunReadinessSummary:
    """Composed postrun readiness with generic and problem-owned boundaries."""

    run_root: str
    inventory_status: str
    lifecycle: RunEvidenceLifecycle
    exposure: ExposureSummary
    problem_review: ProblemReviewSummary | None = None
    failed_required_checks: tuple[str, ...] = ()
    failed_optional_checks: tuple[str, ...] = ()
    current_run_analysis_ready: bool = False
    delegation_ready: bool = False
    report_only: bool = True
    decision_features_excluded: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "scion.postrun_readiness_summary.v1",
            "run_root": self.run_root,
            "inventory_status": self.inventory_status,
            "lifecycle": self.lifecycle.to_payload(),
            "exposure": self.exposure.to_payload(),
            "problem_review": (
                self.problem_review.to_payload()
                if self.problem_review is not None
                else None
            ),
            "failed_required_checks": list(self.failed_required_checks),
            "failed_optional_checks": list(self.failed_optional_checks),
            "current_run_analysis_ready": self.current_run_analysis_ready,
            "delegation_ready": self.delegation_ready,
            "report_only": self.report_only,
            "decision_features_excluded": self.decision_features_excluded,
        }


class ProblemReviewRegistry:
    """Lookup table for problem-owned review ports."""

    def __init__(self, ports: Mapping[str, ProblemReviewPort] | None = None) -> None:
        self._ports: dict[str, ProblemReviewPort] = {}
        for family, port in (ports or {}).items():
            self.register(family, port)

    def register(self, problem_family: str, port: ProblemReviewPort) -> None:
        family = _normalize_family(problem_family)
        if not family:
            raise ValueError("problem_family must be non-empty")
        self._ports[family] = port

    def get(self, problem_family: str) -> ProblemReviewPort | None:
        return self._ports.get(_normalize_family(problem_family))


def _normalize_family(problem_family: str) -> str:
    return str(problem_family or "").strip().lower()
