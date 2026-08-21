"""Structural protocols for the proposal pipeline facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

from scion.core.execution_outcome import ExecutionOutcomeRecord
from scion.core.models import HypothesisProposal, PatchProposal
from scion.proposal.engine import PromptTurnSnapshot

ProposalT = TypeVar("ProposalT", HypothesisProposal, PatchProposal)


@dataclass(frozen=True)
class ProposalAttempt(Generic[ProposalT]):
    """One direct provider attempt: either a proposal or a typed failure."""

    proposal: ProposalT | None = None
    execution_outcome: ExecutionOutcomeRecord | None = None

    def __post_init__(self) -> None:
        if (self.proposal is None) == (self.execution_outcome is None):
            raise ValueError(
                "proposal attempt must contain exactly one of proposal or "
                "execution_outcome"
            )

    @classmethod
    def success(cls, proposal: ProposalT) -> "ProposalAttempt[ProposalT]":
        return cls(proposal=proposal)

    @classmethod
    def failure(
        cls,
        execution_outcome: ExecutionOutcomeRecord,
    ) -> "ProposalAttempt[ProposalT]":
        return cls(execution_outcome=execution_outcome)


class CreativeLayerLike(Protocol):
    def generate_direct_hypothesis(
        self,
        snapshot: PromptTurnSnapshot,
    ) -> HypothesisProposal: ...

    def generate_direct_code(
        self,
        snapshot: PromptTurnSnapshot,
    ) -> PatchProposal: ...

    def call_hypothesis_research_turn(
        self,
        snapshot: PromptTurnSnapshot,
    ) -> dict[str, Any]: ...

    def call_code_research_turn(
        self,
        snapshot: PromptTurnSnapshot,
    ) -> dict[str, Any]: ...

    def call_code_research_finalize(
        self,
        snapshot: PromptTurnSnapshot,
    ) -> dict[str, Any]: ...


class ProblemRuntimeLike(Protocol):
    def build_hypothesis_context(self, **kwargs: Any) -> dict[str, Any]: ...

    def build_code_context(self, **kwargs: Any) -> dict[str, Any]: ...

    def hypothesis_research_public_sources(self) -> tuple[dict[str, str], ...]: ...

    def hypothesis_research_source_prefixes(self) -> tuple[str, ...]: ...
