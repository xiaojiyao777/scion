"""Structural protocols for the proposal pipeline facade."""
from __future__ import annotations

from typing import Any, Protocol

from scion.core.models import (
    Branch,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
)
from scion.proposal.engine import ProviderCallDiagnostics, PromptTurnSnapshot


class CreativeLayerLike(Protocol):
    def generate_direct_hypothesis(
        self,
        context: dict[str, Any],
        snapshot: PromptTurnSnapshot,
        *,
        call_context: dict[str, Any],
    ) -> tuple[HypothesisProposal, ProviderCallDiagnostics]:
        ...

    def generate_direct_code(
        self,
        context: dict[str, Any],
        snapshot: PromptTurnSnapshot,
        *,
        call_context: dict[str, Any],
    ) -> tuple[PatchProposal, ProviderCallDiagnostics]: ...


class ProblemRuntimeLike(Protocol):
    def build_hypothesis_context(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def build_code_context(self, **kwargs: Any) -> dict[str, Any]:
        ...

class BranchControllerLike(Protocol):
    def get_active_branches(self) -> list[Branch]:
        ...


class HypothesisStoreLike(Protocol):
    def save(self, record: HypothesisRecord) -> None:
        ...

    def mark_status(self, hypothesis_id: str, status: str) -> None:
        ...

    def get_one(self, hypothesis_id: str) -> HypothesisRecord | None:
        ...

    def get_by_status(self, status: str) -> list[HypothesisRecord]:
        ...

    def get_by_branch(self, branch_id: str) -> list[HypothesisRecord]:
        ...


class ClassifierLike(Protocol):
    def classify(self, text: str) -> Any:
        ...
