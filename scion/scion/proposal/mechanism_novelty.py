"""Problem-dispatched semantic novelty gate for proposal hypotheses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from scion.core.models import HypothesisProposal
from scion.proposal.tools import ProposalObservation, ProposalToolContext


@dataclass(frozen=True)
class MechanismNoveltyResult:
    premise_check: str
    failure_category: str
    mechanism: str
    reason: str
    evidence: tuple[str, ...] = ()
    snapshot_digest: str | None = None

    def to_rejection(self, hypothesis: HypothesisProposal) -> dict[str, Any]:
        return {
            "artifact_kind": "agentic_mechanism_novelty_rejection",
            "premise_check": self.premise_check,
            "failure_category": self.failure_category,
            "reason": self.reason,
            "selected_surface": hypothesis.change_locus,
            "target_file": hypothesis.target_file,
            "mechanism": self.mechanism,
            "evidence": list(self.evidence),
            "snapshot_digest": self.snapshot_digest,
            "patch_generated": False,
            "screening_allowed": False,
            "source": "mechanism_novelty_gate",
            "gate_name": "MechanismNoveltyGate",
        }


class _MechanismNoveltyProvider(Protocol):
    def evaluate_mechanism_novelty(
        self,
        hypothesis: HypothesisProposal,
        *,
        active_solver_snapshot: Mapping[str, Any] | None = None,
        observations: Sequence[ProposalObservation] = (),
    ) -> MechanismNoveltyResult | None:
        ...


class MechanismNoveltyGate:
    """Dispatch semantic novelty checks to the active problem adapter.

    Scion core/proposal owns the auditable control point and rejection shape.
    Problem packages own domain semantics for their algorithm mechanisms.
    """

    def evaluate(
        self,
        hypothesis: HypothesisProposal,
        *,
        context: ProposalToolContext | None = None,
        active_solver_snapshot: Mapping[str, Any] | None = None,
        observations: Sequence[ProposalObservation] = (),
    ) -> MechanismNoveltyResult | None:
        provider = _provider_from_context(context)
        if provider is None:
            return None
        snapshot = active_solver_snapshot or _active_solver_snapshot_from_observations(
            observations
        )
        return provider.evaluate_mechanism_novelty(
            hypothesis,
            active_solver_snapshot=snapshot,
            observations=observations,
        )


def _provider_from_context(
    context: ProposalToolContext | None,
) -> _MechanismNoveltyProvider | None:
    adapter = getattr(context, "adapter", None)
    if adapter is None:
        return None
    method = getattr(adapter, "mechanism_novelty_provider", None)
    if callable(method):
        provider = method()
        if provider is not None and hasattr(provider, "evaluate_mechanism_novelty"):
            return provider
    if hasattr(adapter, "evaluate_mechanism_novelty"):
        return adapter
    return None


def _active_solver_snapshot_from_observations(
    observations: Sequence[ProposalObservation],
) -> Mapping[str, Any] | None:
    for observation in reversed(tuple(observations)):
        if observation.is_error:
            continue
        if observation.tool_name != "context.read_active_solver_design":
            continue
        payload = observation.structured_payload
        if isinstance(payload, Mapping) and isinstance(
            payload.get("mechanism_summary"), Mapping
        ):
            return payload
    return None


__all__ = ["MechanismNoveltyGate", "MechanismNoveltyResult"]
