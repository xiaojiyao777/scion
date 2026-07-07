"""CVRP-owned mechanism evidence interpretation policy."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.runtime.telemetry_guard.summary_signals import (
    ACTIVATED_NO_POSITIVE_EFFECT,
    EFFECT_ATTRIBUTION_MISSING,
    EVALUATED_NO_EFFECT,
    MECHANISM_EXECUTED_NO_IMPROVEMENT,
    POLICY_OUTCOME_OBSERVED,
)


_POST_VNS_BEST_ANCHOR_ACCEPTANCE_GUARD = "post_vns_best_anchor_acceptance_guard"
_DIRECT_EFFECT_INCOMPLETE_STATUSES = frozenset(
    {"missing", "zero", "not_declared", "not-declared"}
)
_GENERIC_DIRECT_EFFECT_DIAGNOSTICS = frozenset(
    {
        ACTIVATED_NO_POSITIVE_EFFECT,
        EVALUATED_NO_EFFECT,
        EFFECT_ATTRIBUTION_MISSING,
        MECHANISM_EXECUTED_NO_IMPROVEMENT,
    }
)
_POLICY_REPAIR_GUIDANCE = (
    "Do not add direct effect telemetry for this policy mechanism. Use formal "
    "per-case outcome evidence plus guard allow/reject and activation/budget "
    "telemetry for interpretation."
)


class CvrpMechanismEvidencePolicyProvider:
    """Interpret CVRP policy-mechanism evidence without changing generic rules."""

    def apply_mechanism_evidence_policy(
        self,
        summary: Mapping[str, Any],
        *,
        context: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        if _effect_observation_required(summary, context):
            return None
        diagnostics = summary.get("mechanism_diagnostics")
        if not isinstance(diagnostics, Sequence) or isinstance(
            diagnostics,
            (str, bytes, bytearray),
        ):
            return None

        changed = False
        rewritten_diagnostics: list[Any] = []
        for item in diagnostics:
            if isinstance(item, Mapping) and _is_policy_outcome_case(item):
                rewritten_diagnostics.append(_rewrite_policy_outcome(item))
                changed = True
            else:
                rewritten_diagnostics.append(item)
        if not changed:
            return None

        updated = dict(summary)
        updated["mechanism_diagnostics"] = rewritten_diagnostics
        updated["warnings"] = [
            item
            for item in _sequence_items(summary.get("warnings"))
            if not (isinstance(item, Mapping) and _is_policy_effect_warning(item))
        ]
        return updated


def _effect_observation_required(
    summary: Mapping[str, Any],
    context: Mapping[str, Any],
) -> bool:
    value = summary.get("effect_observation_required")
    if value is None:
        value = context.get("effect_observation_required")
    return bool(value)


def _is_policy_outcome_case(diagnostic: Mapping[str, Any]) -> bool:
    if str(diagnostic.get("mechanism") or "").strip() != (
        _POST_VNS_BEST_ANCHOR_ACCEPTANCE_GUARD
    ):
        return False
    if not _activation_observed(diagnostic):
        return False
    if not _direct_effect_incomplete(diagnostic):
        return False
    return bool(
        {
            str(diagnostic.get("diagnostic_kind") or "").strip(),
            str(diagnostic.get("diagnostic_type") or "").strip(),
            str(diagnostic.get("telemetry_outcome") or "").strip(),
        }
        & _GENERIC_DIRECT_EFFECT_DIAGNOSTICS
    )


def _activation_observed(diagnostic: Mapping[str, Any]) -> bool:
    if diagnostic.get("activation_observed") is True:
        return True
    if str(diagnostic.get("activation_status") or "").strip() == "observed":
        return True
    activation = diagnostic.get("activation")
    return isinstance(activation, Mapping) and _positive_count(activation) > 0


def _direct_effect_incomplete(diagnostic: Mapping[str, Any]) -> bool:
    statuses = {
        str(diagnostic.get("effect_status") or "").strip(),
    }
    effect = diagnostic.get("effect")
    if isinstance(effect, Mapping):
        statuses.add(str(effect.get("status") or "").strip())
    if statuses & _DIRECT_EFFECT_INCOMPLETE_STATUSES:
        return True
    return isinstance(effect, Mapping) and _positive_count(effect) <= 0


def _rewrite_policy_outcome(diagnostic: Mapping[str, Any]) -> dict[str, Any]:
    rewritten = dict(diagnostic)
    rewritten["diagnostic_type"] = POLICY_OUTCOME_OBSERVED
    rewritten["diagnostic_kind"] = POLICY_OUTCOME_OBSERVED
    rewritten["diagnostic_signals"] = [POLICY_OUTCOME_OBSERVED]
    rewritten["telemetry_outcome"] = POLICY_OUTCOME_OBSERVED
    rewritten["policy_outcome_observed"] = True
    rewritten["repairable"] = False
    rewritten["repair_guidance"] = [_POLICY_REPAIR_GUIDANCE]
    rewritten.pop("branch_repair_signal", None)
    return rewritten


def _is_policy_effect_warning(item: Mapping[str, Any]) -> bool:
    return (
        str(item.get("code") or "").strip()
        == "TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED"
        and str(item.get("mechanism") or "").strip()
        == _POST_VNS_BEST_ANCHOR_ACCEPTANCE_GUARD
    )


def _sequence_items(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)


def _positive_count(value: Mapping[str, Any]) -> int:
    try:
        return int(value.get("candidate_positive", 0) or 0)
    except (TypeError, ValueError):
        return 0


__all__ = ["CvrpMechanismEvidencePolicyProvider"]
