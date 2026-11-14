"""Structural protocols for the proposal pipeline facade."""

from __future__ import annotations

from copy import deepcopy
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
    selected_hypothesis_research_basis: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if (self.proposal is None) == (self.execution_outcome is None):
            raise ValueError(
                "proposal attempt must contain exactly one of proposal or "
                "execution_outcome"
            )
        if self.selected_hypothesis_research_basis is not None:
            if self.proposal is None:
                raise ValueError(
                    "a failed proposal attempt cannot carry a selected "
                    "hypothesis research basis"
                )
            if not isinstance(self.proposal, HypothesisProposal):
                raise TypeError(
                    "only a selected hypothesis attempt can carry a research basis"
                )
            if not isinstance(self.selected_hypothesis_research_basis, dict):
                raise TypeError(
                    "selected_hypothesis_research_basis must be a primitive mapping"
                )
            object.__setattr__(
                self,
                "selected_hypothesis_research_basis",
                deepcopy(self.selected_hypothesis_research_basis),
            )

    @classmethod
    def success(
        cls,
        proposal: ProposalT,
        *,
        selected_hypothesis_research_basis: dict[str, Any] | None = None,
    ) -> ProposalAttempt[ProposalT]:
        return cls(
            proposal=proposal,
            selected_hypothesis_research_basis=(
                selected_hypothesis_research_basis
            ),
        )

    @classmethod
    def failure(
        cls,
        execution_outcome: ExecutionOutcomeRecord,
    ) -> ProposalAttempt[ProposalT]:
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
