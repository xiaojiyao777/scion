"""Problem-dispatched premise gate and duplicate diagnostics for proposals."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from inspect import signature
from typing import Any, Mapping, Protocol, Sequence

from scion.core.models import HypothesisProposal
from scion.problem.providers import active_subject_taxonomy_payload
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
    fact_ids: tuple[str, ...] = ()
    contradicted_fact_ids: tuple[str, ...] = ()
    fact_packet_digest: str | None = None
    fact_provenance: Mapping[str, Any] | None = None
    result_kind: str | None = None
    gate_action: str | None = None
    diagnostic_kind: str | None = None
    variant_allowed: bool | None = None
    contradicted_span: str | None = None
    matched_span: str | None = None
    allowed_variant_guidance: str | None = None

    def __post_init__(self) -> None:
        hard_result_kind = str(self.result_kind or self.failure_category or "")
        if self.premise_check == "contradicted" and hard_result_kind in {
            "boundary_contradicted",
            "objective_policy_contradicted",
        }:
            result_kind = hard_result_kind
            gate_action = "hard_block"
            diagnostic_kind = None
        elif self.premise_check == "contradicted" and self._has_hard_block_evidence():
            result_kind = "mechanism_premise_warning"
            gate_action = "diagnostic"
            diagnostic_kind = "mechanism_premise_warning"
        elif self.premise_check == "contradicted":
            result_kind = "mechanism_premise_warning"
            gate_action = "diagnostic"
            diagnostic_kind = "mechanism_premise_warning"
        else:
            result_kind = "duplicate_diagnostic"
            gate_action = "diagnostic"
            diagnostic_kind = (
                "duplicate_risk"
                if self.premise_check == "duplicate"
                else self.failure_category or self.premise_check
            )
        if self.result_kind is None:
            object.__setattr__(self, "result_kind", result_kind)
        resolved_result_kind = self.result_kind or result_kind
        if self.gate_action is None:
            object.__setattr__(self, "gate_action", gate_action)
        resolved_gate_action = self.gate_action or gate_action
        if self.diagnostic_kind is None:
            if resolved_gate_action == "diagnostic":
                if self.premise_check == "contradicted":
                    diagnostic_kind = "mechanism_premise_warning"
                elif self.premise_check == "duplicate":
                    diagnostic_kind = "duplicate_risk"
                elif resolved_result_kind == "duplicate_diagnostic":
                    diagnostic_kind = "novelty_warning"
            object.__setattr__(self, "diagnostic_kind", diagnostic_kind)
        if resolved_gate_action == "diagnostic" and self.variant_allowed is False:
            object.__setattr__(self, "variant_allowed", None)

    @property
    def is_hard_block(self) -> bool:
        return (
            self.premise_check == "contradicted"
            and self.result_kind
            in {"boundary_contradicted", "objective_policy_contradicted"}
            and self.gate_action == "hard_block"
            and self._has_hard_block_evidence()
        )

    def _has_hard_block_evidence(self) -> bool:
        return bool(
            (self.contradicted_fact_ids or self.fact_ids)
            and self.fact_packet_digest
            and self.fact_provenance
            and (self.contradicted_span or self.matched_span)
        )

    def to_rejection(self, hypothesis: HypothesisProposal) -> dict[str, Any]:
        if not self.is_hard_block:
            raise ValueError(
                "Only boundary_contradicted/objective_policy_contradicted "
                "results with auditable fact ids, fact provenance, fact packet "
                "digest, and a contradicted span can be serialized as hard "
                "rejections; mechanism novelty/premise overlap uses "
                "to_diagnostic()."
            )
        return {
            "artifact_kind": "agentic_mechanism_novelty_rejection",
            "result_kind": self.result_kind,
            "gate_action": self.gate_action,
            "premise_check": self.premise_check,
            "failure_category": self.failure_category,
            "reason": self.reason,
            "selected_surface": hypothesis.change_locus,
            "target_file": hypothesis.target_file,
            "mechanism": self.mechanism,
            "evidence": list(self.evidence),
            "snapshot_digest": self.snapshot_digest,
            "fact_ids": list(self.fact_ids),
            "contradicted_fact_ids": list(self.contradicted_fact_ids),
            "fact_packet_digest": self.fact_packet_digest,
            "fact_provenance": dict(self.fact_provenance or {}),
            "variant_allowed": self.variant_allowed,
            "contradicted_span": self.contradicted_span,
            "matched_span": self.matched_span,
            "allowed_variant_guidance": self.allowed_variant_guidance,
            "patch_generated": False,
            "screening_allowed": False,
            "source": "mechanism_novelty_gate",
            "gate_name": "MechanismNoveltyGate",
        }

    def to_diagnostic(self, hypothesis: HypothesisProposal) -> dict[str, Any]:
        return {
            "artifact_kind": (
                "agentic_mechanism_premise_diagnostic"
                if self.result_kind == "mechanism_premise_warning"
                else "agentic_mechanism_duplicate_diagnostic"
            ),
            "result_kind": self.result_kind,
            "gate_action": self.gate_action,
            "diagnostic_kind": self.diagnostic_kind,
            "premise_check": self.premise_check,
            "failure_category": self.failure_category,
            "reason": self.reason,
            "selected_surface": hypothesis.change_locus,
            "target_file": hypothesis.target_file,
            "mechanism": self.mechanism,
            "evidence": list(self.evidence),
            "snapshot_digest": self.snapshot_digest,
            "fact_ids": list(self.fact_ids),
            "fact_packet_digest": self.fact_packet_digest,
            "fact_provenance": dict(self.fact_provenance or {}),
            "variant_allowed": self.variant_allowed,
            "matched_span": self.matched_span,
            "allowed_variant_guidance": self.allowed_variant_guidance,
            "patch_generated": None,
            "screening_allowed": True,
            "blocking": False,
            "quality_block": False,
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
    """Dispatch premise checks and duplicate diagnostics to the problem adapter.

    Scion core/proposal owns the auditable control point and hard-rejection
    shape. Problem packages own domain semantics for their algorithm
    mechanisms. Mechanism novelty, duplicate risk, and "baseline already has a
    similar mechanism" premise checks are advisory diagnostics; hard blocks are
    reserved for explicit boundary/objective-policy contradictions.
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
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if isinstance(payload.get("active_algorithm_facts"), Mapping):
            return payload
        if isinstance(payload.get("mechanism_summary"), Mapping):
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

    candidate_ids = _mechanism_ids(hypothesis, primary_only=True)
    candidate_signature = _novelty_signature_key(hypothesis, context=context)
    candidate_family = _mechanism_family(hypothesis, context=context)
    candidate_target = str(hypothesis.target_file or "").strip()

    for step in reversed(recent_steps):
        step_hypothesis = getattr(step, "hypothesis", None)
        if step_hypothesis is None or not _step_is_failed_or_no_effect(step):
            continue
        failure_code = _failure_code(step)
        if not failure_code:
            continue

        step_ids = _mechanism_ids(step_hypothesis, primary_only=True)
        overlap = sorted(candidate_ids & step_ids)
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

        step_signature = _novelty_signature_key(step_hypothesis, context=context)
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
        if candidate_ids or step_ids:
            continue
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


def _mechanism_ids(
    hypothesis: HypothesisProposal,
    *,
    primary_only: bool = False,
) -> set[str]:
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
    if primary_only:
        primary_ids = {
            item for item in ids if not _is_secondary_integration_mechanism_id(item)
        }
        if primary_ids:
            ids = primary_ids
    signature = getattr(hypothesis, "novelty_signature", None)
    if isinstance(signature, Mapping):
        for key in ("mechanism_id", "improvement_strategy"):
            value = signature.get(key)
            if isinstance(value, str):
                text = _normalize_token(value)
                if (
                    text
                    and text != "preserve"
                    and not text.startswith("preserve_existing")
                    and (
                        not primary_only
                        or not _is_secondary_integration_mechanism_id(text)
                    )
                ):
                    ids.add(text)
    return ids


def _is_secondary_integration_mechanism_id(value: str) -> bool:
    text = _normalize_token(value)
    if not text:
        return False
    return bool(
        re.search(
            r"(?:^|_)(?:registry|registration|register|wiring|wire|"
            r"integration|integrate|operator_registry)(?:_|$)",
            text,
        )
    )


def _novelty_signature_key(
    hypothesis: HypothesisProposal,
    *,
    context: ProposalToolContext | None = None,
) -> str:
    signature = getattr(hypothesis, "novelty_signature", None)
    if not isinstance(signature, Mapping) or not signature:
        return ""
    normalized_signature = dict(signature)
    broad_families = _active_subject_broad_family_ids(
        context,
        surface=getattr(hypothesis, "change_locus", None),
    )
    family = _normalize_token(normalized_signature.get("algorithm_family"))
    if family and family in broad_families:
        normalized_signature.pop("algorithm_family", None)
    if not normalized_signature:
        return ""
    try:
        return json.dumps(normalized_signature, sort_keys=True, default=str)
    except TypeError:
        return str(sorted(normalized_signature.items()))


def _mechanism_family(
    hypothesis: HypothesisProposal,
    *,
    context: ProposalToolContext | None,
) -> str:
    signature = getattr(hypothesis, "novelty_signature", None)
    if isinstance(signature, Mapping):
        for key in ("mechanism_id", "improvement_strategy"):
            value = str(signature.get(key) or "").strip()
            if value and not value.startswith("preserve_existing"):
                return _normalize_token(value)
        family = _normalize_token(signature.get("algorithm_family"))
        broad_families = _active_subject_broad_family_ids(
            context,
            surface=getattr(hypothesis, "change_locus", None),
        )
        if family and family not in broad_families:
            return family
    taxonomy = getattr(getattr(context, "search_memory", None), "family_taxonomy", None)
    return extract_mechanism_label(
        hypothesis.hypothesis_text or "",
        taxonomy=taxonomy,
        preferred_label=hypothesis.change_locus,
    )


def _active_subject_broad_family_ids(
    context: ProposalToolContext | None,
    *,
    surface: str | None,
) -> set[str]:
    if context is None:
        return set()
    taxonomy = active_subject_taxonomy_payload(
        context=context,
        problem_spec=getattr(context, "problem_spec", None),
        adapter=getattr(context, "adapter", None),
        surface=surface,
    )
    return {
        _normalize_token(item)
        for item in taxonomy.get("mechanism_broad_family_ids", ()) or ()
        if _normalize_token(item)
    }


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
            f"branch={getattr(step, 'branch_id', '')} "
            f"target={getattr(getattr(step, 'hypothesis', None), 'target_file', '')} "
            f"failure_code={_failure_code(step)} "
            f"win_rate={getattr(stats, 'win_rate', None)} "
            f"median_delta={getattr(stats, 'median_delta', None)}"
        )
    return (
        f"round={getattr(step, 'round_num', '')} "
        f"branch={getattr(step, 'branch_id', '')} "
        f"target={getattr(getattr(step, 'hypothesis', None), 'target_file', '')} "
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
