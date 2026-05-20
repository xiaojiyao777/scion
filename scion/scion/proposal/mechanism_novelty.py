"""Problem-dispatched semantic novelty gate for proposal hypotheses."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from inspect import signature
from typing import Any, Mapping, Protocol, Sequence

from scion.core.models import HypothesisProposal
from scion.core.telemetry_validation import screened_experiment_effective
from scion.proposal.mechanism_labels import (
    DEFAULT_MECHANISM_LABEL,
    extract_mechanism_label,
)
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
        context: ProposalToolContext | None = None,
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
        repeated = _recent_repeated_mechanism_result(hypothesis, context=context)
        if repeated is not None:
            return repeated
        provider = _provider_from_context(context)
        if provider is None:
            return None
        snapshot = active_solver_snapshot or _active_solver_snapshot_from_observations(
            observations
        )
        kwargs: dict[str, Any] = {
            "active_solver_snapshot": snapshot,
            "observations": observations,
        }
        if _method_accepts_keyword(provider.evaluate_mechanism_novelty, "context"):
            kwargs["context"] = context
        return provider.evaluate_mechanism_novelty(hypothesis, **kwargs)


def _method_accepts_keyword(method: Any, keyword: str) -> bool:
    try:
        params = signature(method).parameters
    except (TypeError, ValueError):
        return False
    return keyword in params or any(
        param.kind == param.VAR_KEYWORD for param in params.values()
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


def _recent_repeated_mechanism_result(
    hypothesis: HypothesisProposal,
    *,
    context: ProposalToolContext | None,
    window: int = 6,
) -> MechanismNoveltyResult | None:
    if context is None or _has_material_difference_claim(hypothesis):
        return None
    recent_steps = list(getattr(context, "step_history", ()) or ())[-window:]
    if not recent_steps:
        return None

    candidate_ids = _mechanism_ids(hypothesis)
    candidate_signature = _novelty_signature_key(hypothesis)
    candidate_family = _mechanism_family(hypothesis, context=context)
    candidate_target = str(hypothesis.target_file or "").strip()

    for step in reversed(recent_steps):
        step_hypothesis = getattr(step, "hypothesis", None)
        if step_hypothesis is None or not _step_is_failed_or_no_effect(step):
            continue
        failure_code = _failure_code(step)
        if not failure_code:
            continue

        overlap = sorted(candidate_ids & _mechanism_ids(step_hypothesis))
        if overlap:
            mechanism = overlap[0]
            return MechanismNoveltyResult(
                premise_check="duplicate",
                failure_category="repeated_mechanism",
                mechanism=mechanism,
                reason=(
                    "Recent campaign history already tried the same declared "
                    f"mechanism id {mechanism!r} and failed with "
                    f"{failure_code}. Retry is blocked unless the hypothesis "
                    "states a materially different trigger, capability, or "
                    "objective tradeoff."
                ),
                evidence=(_step_evidence(step),),
            )

        step_signature = _novelty_signature_key(step_hypothesis)
        if candidate_signature and candidate_signature == step_signature:
            mechanism = _mechanism_family(hypothesis, context=context)
            return MechanismNoveltyResult(
                premise_check="duplicate",
                failure_category="repeated_mechanism",
                mechanism=mechanism,
                reason=(
                    "Recent campaign history already tried the same structured "
                    f"novelty_signature and failed with {failure_code}. "
                    "Choose a materially different mechanism identity before "
                    "entering code generation again."
                ),
                evidence=(_step_evidence(step),),
            )

        step_family = _mechanism_family(step_hypothesis, context=context)
        step_target = str(getattr(step_hypothesis, "target_file", "") or "").strip()
        if (
            candidate_target
            and candidate_target == step_target
            and candidate_family
            and candidate_family != DEFAULT_MECHANISM_LABEL
            and candidate_family == step_family
            and failure_code == _failure_code(step)
        ):
            return MechanismNoveltyResult(
                premise_check="duplicate",
                failure_category="repeated_mechanism",
                mechanism=candidate_family,
                reason=(
                    "Recent campaign history already tried this target/family/"
                    f"failure signature ({candidate_target}, {candidate_family}, "
                    f"{failure_code}). Provide a materially different capability, "
                    "trigger, or objective tradeoff before retrying."
                ),
                evidence=(_step_evidence(step),),
            )
    return None


def _mechanism_ids(hypothesis: HypothesisProposal) -> set[str]:
    ids: set[str] = set()
    for change in getattr(hypothesis, "mechanism_changes", ()) or ():
        value = (
            change.get("id")
            if isinstance(change, Mapping)
            else getattr(change, "id", None)
        )
        text = _normalize_token(value)
        if text:
            ids.add(text)
    signature = getattr(hypothesis, "novelty_signature", None)
    if isinstance(signature, Mapping):
        for key in ("mechanism_id", "improvement_strategy", "acceptance_strategy"):
            value = signature.get(key)
            if isinstance(value, str):
                text = _normalize_token(value)
                if text and text not in {"preserve_existing_acceptance", "preserve"}:
                    ids.add(text)
    return ids


def _novelty_signature_key(hypothesis: HypothesisProposal) -> str:
    signature = getattr(hypothesis, "novelty_signature", None)
    if not isinstance(signature, Mapping) or not signature:
        return ""
    try:
        return json.dumps(signature, sort_keys=True, default=str)
    except TypeError:
        return str(sorted(signature.items()))


def _mechanism_family(
    hypothesis: HypothesisProposal,
    *,
    context: ProposalToolContext | None,
) -> str:
    signature = getattr(hypothesis, "novelty_signature", None)
    if isinstance(signature, Mapping):
        for key in ("algorithm_family", "improvement_strategy", "acceptance_strategy"):
            value = str(signature.get(key) or "").strip()
            if value and not value.startswith("preserve_existing"):
                return _normalize_token(value)
    taxonomy = getattr(getattr(context, "search_memory", None), "family_taxonomy", None)
    return extract_mechanism_label(
        hypothesis.hypothesis_text or "",
        taxonomy=taxonomy,
        preferred_label=hypothesis.change_locus,
    )


def _step_is_failed_or_no_effect(step: Any) -> bool:
    protocol = getattr(step, "protocol_result", None)
    if protocol is None:
        return getattr(step, "failure_stage", None) is not None
    if not screened_experiment_effective(protocol):
        return True
    decision = str(getattr(getattr(step, "decision", None), "value", "") or "")
    if decision in {"promote", "queue_validate", "queue_frozen"}:
        return False
    stats = getattr(protocol, "stats", None)
    if stats is None:
        return True
    try:
        return float(getattr(stats, "win_rate", 0.0) or 0.0) <= 0.0
    except (TypeError, ValueError):
        return True


def _failure_code(step: Any) -> str:
    for value in getattr(step, "decision_reason_codes", ()) or ():
        text = str(value or "").strip()
        if text:
            return text
    protocol = getattr(step, "protocol_result", None)
    if protocol is not None:
        for value in getattr(protocol, "reason_codes", ()) or ():
            text = str(value or "").strip()
            if text:
                return text
    return str(getattr(step, "failure_stage", "") or "").strip()


def _step_evidence(step: Any) -> str:
    protocol = getattr(step, "protocol_result", None)
    if protocol is not None and getattr(protocol, "stats", None) is not None:
        stats = protocol.stats
        return (
            f"round={getattr(step, 'round_num', '')} "
            f"failure_code={_failure_code(step)} "
            f"win_rate={getattr(stats, 'win_rate', None)} "
            f"median_delta={getattr(stats, 'median_delta', None)}"
        )
    return (
        f"round={getattr(step, 'round_num', '')} "
        f"failure_stage={getattr(step, 'failure_stage', '')} "
        f"detail={str(getattr(step, 'failure_detail', '') or '')[:160]}"
    )


def _has_material_difference_claim(hypothesis: HypothesisProposal) -> bool:
    text = " ".join(
        str(value or "")
        for value in (
            hypothesis.hypothesis_text,
            hypothesis.target_weakness,
            hypothesis.expected_effect,
            hypothesis.no_op_condition,
            hypothesis.objective_tradeoff_policy,
        )
    ).lower()
    return bool(
        re.search(
            r"\bmaterially different\b|\bdifferent trigger\b|\bnew trigger\b|"
            r"\bdifferent capability\b|\bnew capability\b|"
            r"\bdifferent objective tradeoff\b|\bdifferent tradeoff\b",
            text,
        )
    )


def _normalize_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


__all__ = ["MechanismNoveltyGate", "MechanismNoveltyResult"]
