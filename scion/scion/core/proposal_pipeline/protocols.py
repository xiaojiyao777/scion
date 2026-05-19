"""Structural protocols for the proposal pipeline facade."""
from __future__ import annotations

from typing import Any, Protocol

from scion.core.models import (
    Branch,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
)
from scion.proposal.agentic_session import (
    AgenticProposalOutput,
    AgenticProposalRequest,
)


class CreativeLayerLike(Protocol):
    def generate_hypothesis(self, context: dict[str, Any]) -> HypothesisProposal:
        ...

    def generate_code(self, context: dict[str, Any]) -> PatchProposal:
        ...

    def fix_code(self, context: dict[str, Any]) -> PatchProposal | None:
        ...


class ProblemRuntimeLike(Protocol):
    def build_hypothesis_context(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def build_code_context(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def build_fix_context(self, **kwargs: Any) -> dict[str, Any]:
        ...


class AgenticProposalSessionLike(Protocol):
    def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
        ...


class BranchControllerLike(Protocol):
    def get_active_branches(self) -> list[Branch]:
        ...


class HypothesisStoreLike(Protocol):
    def get_by_status(self, status: str) -> list[HypothesisRecord]:
        ...


class ClassifierLike(Protocol):
    def classify(self, text: str) -> Any:
        ...


class CircuitBreakerLike(Protocol):
    def record_success(self) -> None:
        ...

    def record_failure(self, detail: str) -> bool:
        ...
