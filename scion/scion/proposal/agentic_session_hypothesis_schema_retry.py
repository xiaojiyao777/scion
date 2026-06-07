"""Pure schema-retry helpers for agentic hypothesis sessions."""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

from scion.core.models import HypothesisProposal
from scion.proposal.agentic_models import AgenticFailureCategory
from scion.proposal.agentic_utils import _drop_empty_dict, _limit_string


def _schema_retry_preservation_drift(
    hypothesis: HypothesisProposal,
    preview_rejections: list[Mapping[str, Any]],
    *,
    attempt: int,
    structural_activation_refs: set[str] | None = None,
) -> dict[str, Any] | None:
    rejection = _latest_schema_preservation_rejection(
        preview_rejections,
        attempt=attempt,
    )
    if rejection is None:
        return None
    expected = rejection.get("preserve_hypothesis")
    if not isinstance(expected, Mapping):
        return None
    observed = _hypothesis_retry_anchor(hypothesis)
    drift_fields: list[str] = []
    for field in (
        "action",
        "target_file",
        "mechanism_changes",
    ):
        if _canonical_retry_identity_value(expected.get(field)) != (
            _canonical_retry_identity_value(observed.get(field))
        ):
            drift_fields.append(field)
    activation_drift = _schema_retry_activation_identity_drift(
        expected,
        hypothesis,
        structural_activation_refs=structural_activation_refs,
    )
    if activation_drift:
        drift_fields.append("expected_telemetry.activation")
    if not drift_fields:
        return None
    return _drop_empty_dict(
        {
            "source": "hypothesis_preview_retry_preservation_gate",
            "failure_code": "schema_retry_drift",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "retry_source": rejection.get("source"),
            "retry_failure_code": rejection.get("failure_code"),
            "attempt": attempt,
            "drift_fields": drift_fields,
            "expected": {
                field: (
                    activation_drift.get("expected")
                    if field == "expected_telemetry.activation"
                    else expected.get(field)
                )
                for field in drift_fields
            },
            "observed": {
                field: (
                    activation_drift.get("observed")
                    if field == "expected_telemetry.activation"
                    else observed.get(field)
                )
                for field in drift_fields
            },
            "preserve_hypothesis": expected,
            "protected_identity": _schema_retry_protected_identity(expected),
        }
    )


def _schema_retry_corrective_retry_already_used(
    preview_rejections: list[Mapping[str, Any]],
) -> bool:
    return any(
        str(rejection.get("failure_code") or "").strip() == "schema_retry_drift"
        for rejection in preview_rejections
        if isinstance(rejection, Mapping)
    )


def _same_mechanism_preview_retry_pending(
    preview_rejections: list[Mapping[str, Any]],
) -> bool:
    if not preview_rejections:
        return False
    return (
        str(preview_rejections[-1].get("failure_code") or "").strip()
        == "same_mechanism_only_violation"
    )


def _latest_schema_preservation_rejection(
    preview_rejections: list[Mapping[str, Any]],
    *,
    attempt: int,
) -> Mapping[str, Any] | None:
    if not preview_rejections:
        return None
    previous_attempt = attempt - 1
    rejection = preview_rejections[-1]
    try:
        rejection_attempt = int(rejection.get("attempt") or 0)
    except Exception:
        rejection_attempt = 0
    if rejection_attempt != previous_attempt:
        return None
    failure_code = str(rejection.get("failure_code") or "").strip()
    if failure_code not in {
        "C11_expected_telemetry",
        "novelty_signature_missing_fields",
        "schema_retry_drift",
    }:
        return None
    if not isinstance(rejection.get("preserve_hypothesis"), Mapping):
        return None
    return rejection


def _schema_retry_drift_feedback(
    drift: Mapping[str, Any],
    hypothesis: HypothesisProposal,
    *,
    attempt: int,
    structural_activation_refs: set[str] | None = None,
) -> dict[str, Any]:
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "source": "hypothesis_preview_retry_preservation_gate",
            "gate_name": "schema_retry_preservation_gate",
            "failure_code": "schema_retry_drift",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "reason": _schema_retry_drift_failure_detail(drift),
            "corrective_retry": True,
            "drift_fields": list(drift.get("drift_fields") or ()),
            "observed_identity": _schema_retry_observed_identity(
                hypothesis,
                structural_activation_refs=structural_activation_refs,
            ),
            "preserve_hypothesis": drift.get("preserve_hypothesis"),
            "protected_identity": drift.get("protected_identity")
            or _schema_retry_protected_identity(
                drift.get("preserve_hypothesis")
                if isinstance(drift.get("preserve_hypothesis"), Mapping)
                else {}
            ),
            "retry_constraint": (
                "Identity-corrective C11/schema retry: restore the exact "
                "target_file, action, mechanism_changes ids/change_types, and "
                "telemetry activation refs listed in protected_identity. Repair "
                "only expected_telemetry/schema fields for the same hypothesis. "
                "Do not explore, rename, or choose a different mechanism."
            ),
        }
    )


def _schema_retry_drift_failure_detail(drift: Mapping[str, Any]) -> str:
    fields = ", ".join(str(field) for field in drift.get("drift_fields") or ())
    expected = _limit_string(
        json.dumps(drift.get("expected") or {}, sort_keys=True, default=str),
        800,
    )
    observed = _limit_string(
        json.dumps(drift.get("observed") or {}, sort_keys=True, default=str),
        800,
    )
    return (
        "schema_retry_drift: schema/novelty retry changed protected hypothesis "
        f"identity fields ({fields or 'unknown'}). Schema/telemetry/novelty retries "
        "must preserve action, target_file, mechanism_changes ids/change_types, "
        "and telemetry activation mechanism refs; free-text hypothesis and "
        f"novelty_signature wording may change. expected={expected}; "
        f"observed={observed}"
    )


def _schema_retry_protected_identity(anchor: Mapping[str, Any]) -> dict[str, Any]:
    mechanism_changes = anchor.get("mechanism_changes")
    protected = _drop_empty_dict(
        {
            "action": anchor.get("action"),
            "target_file": anchor.get("target_file"),
            "mechanism_changes": mechanism_changes,
            "protected_mechanism_ids": sorted(_protected_mechanism_ids(anchor)),
        }
    )
    return protected


def _schema_retry_observed_identity(
    hypothesis: HypothesisProposal,
    *,
    structural_activation_refs: set[str] | None = None,
) -> dict[str, Any]:
    anchor = _hypothesis_retry_anchor(hypothesis)
    return _drop_empty_dict(
        {
            "action": anchor.get("action"),
            "target_file": anchor.get("target_file"),
            "mechanism_changes": anchor.get("mechanism_changes"),
            "activation_refs": sorted(
                _telemetry_activation_mechanism_refs(
                    getattr(hypothesis, "expected_telemetry", {}) or {},
                    structural_activation_refs=structural_activation_refs,
                )
            ),
        }
    )


def _canonical_retry_identity_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_retry_identity_value(val)
            for key, val in sorted(value.items(), key=lambda item: str(item[0]))
            if val not in (None, "", [], (), {})
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonical_retry_identity_value(item) for item in value]
    if isinstance(value, str):
        return value.strip()
    return value


def _schema_retry_activation_identity_drift(
    expected_anchor: Mapping[str, Any],
    hypothesis: HypothesisProposal,
    *,
    structural_activation_refs: set[str] | None = None,
) -> dict[str, Any]:
    protected_ids = _protected_mechanism_ids(expected_anchor)
    if not protected_ids:
        return {}
    observed_refs = _telemetry_activation_mechanism_refs(
        getattr(hypothesis, "expected_telemetry", {}) or {},
        structural_activation_refs=structural_activation_refs,
    )
    observed_refs = {
        ref
        for ref in observed_refs
        if _is_structural_activation_ref(ref, protected_ids)
    }
    if not observed_refs:
        return {}
    if any(
        _mechanism_ref_matches(ref, protected)
        for ref in observed_refs
        for protected in protected_ids
    ):
        return {}
    return {
        "expected": {"protected_mechanism_ids": sorted(protected_ids)},
        "observed": {"activation_mechanism_refs": sorted(observed_refs)},
    }


def _protected_mechanism_ids(anchor: Mapping[str, Any]) -> set[str]:
    changes = anchor.get("mechanism_changes")
    ids: set[str] = set()
    if isinstance(changes, (list, tuple)):
        for change in changes:
            if not isinstance(change, Mapping):
                continue
            mechanism_id = _mechanism_ref_token(change.get("id"))
            if mechanism_id:
                ids.add(mechanism_id)
    return ids


def _telemetry_activation_mechanism_refs(
    expected_telemetry: Any,
    *,
    structural_activation_refs: set[str] | None = None,
) -> set[str]:
    if not isinstance(expected_telemetry, Mapping):
        return set()
    activation = expected_telemetry.get("activation")
    text_items = _flatten_telemetry_activation_items(activation)
    refs: set[str] = set()
    for item in text_items:
        refs.update(_mechanism_refs_from_telemetry_path(item))
    structural_refs = structural_activation_refs or set()
    return {ref for ref in refs if ref not in structural_refs}


def _flatten_telemetry_activation_items(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        items: list[str] = []
        for key, child in value.items():
            items.append(str(key))
            items.extend(_flatten_telemetry_activation_items(child))
        return items
    if isinstance(value, (list, tuple, set, frozenset)):
        items: list[str] = []
        for child in value:
            items.extend(_flatten_telemetry_activation_items(child))
        return items
    return []


def _is_structural_activation_ref(ref: str, protected_ids: set[str]) -> bool:
    token = _mechanism_ref_token(ref)
    if not token:
        return False
    if any(_mechanism_ref_matches(token, protected) for protected in protected_ids):
        return True
    return "_" in token


def _mechanism_refs_from_telemetry_path(path: Any) -> set[str]:
    text = str(path or "").strip()
    if not text:
        return set()
    refs: set[str] = set()
    candidate = text.rsplit(".", 1)[-1] if "." in text else text
    parts = [part for part in re.split(r"[\[\]/:\s]+", candidate) if part]
    for part in parts:
        token = _mechanism_ref_token(part)
        if token:
            refs.add(token)
    return refs


def _mechanism_ref_token(value: Any) -> str:
    token = str(value or "").strip().lower().replace("-", "_")
    if not token:
        return ""
    if token.startswith("solver_algorithm_"):
        return ""
    for suffix in (
        "_iterations",
        "_iteration",
        "_calls",
        "_call",
        "_events",
        "_event",
        "_runtime_ms",
        "_elapsed_ms",
        "_activation",
        "_activations",
        "_count",
        "_counts",
    ):
        if token.endswith(suffix):
            token = token[: -len(suffix)]
            break
    return token.strip("_")


def _mechanism_ref_matches(observed: str, protected: str) -> bool:
    observed = _mechanism_ref_token(observed)
    protected = _mechanism_ref_token(protected)
    return bool(
        observed
        and protected
        and (
            observed == protected
            or observed.startswith(f"{protected}_")
            or protected.startswith(f"{observed}_")
        )
    )


def _hypothesis_retry_anchor(hypothesis: HypothesisProposal) -> dict[str, Any]:
    return _drop_empty_dict(
        {
            "change_locus": hypothesis.change_locus,
            "action": hypothesis.action,
            "target_file": hypothesis.target_file,
            "predicted_direction": hypothesis.predicted_direction,
            "target_objectives": list(hypothesis.target_objectives or ()),
            "protected_objectives": list(hypothesis.protected_objectives or ()),
            "target_runtime_effect": hypothesis.target_runtime_effect,
            "mechanism_changes": [
                _mechanism_change_anchor(change)
                for change in getattr(hypothesis, "mechanism_changes", ()) or ()
            ],
            "novelty_signature": dict(hypothesis.novelty_signature or {}),
            "hypothesis_text_excerpt": _limit_string(
                hypothesis.hypothesis_text,
                360,
            ),
            "target_weakness_excerpt": _limit_string(
                hypothesis.target_weakness,
                240,
            ),
            "expected_effect_excerpt": _limit_string(
                hypothesis.expected_effect,
                240,
            ),
        }
    )


def _mechanism_change_anchor(change: Any) -> dict[str, str]:
    if isinstance(change, Mapping):
        raw = change
        return _drop_empty_identity_fields(
            {
                "id": str(raw.get("id") or ""),
                "name": str(raw.get("name") or ""),
                "change_type": str(raw.get("change_type") or raw.get("action") or ""),
                "target": str(raw.get("target") or raw.get("target_file") or ""),
            }
        )
    return _drop_empty_identity_fields(
        {
            "id": str(getattr(change, "id", "") or ""),
            "name": str(getattr(change, "name", "") or ""),
            "change_type": str(
                getattr(change, "change_type", "")
                or getattr(change, "action", "")
                or ""
            ),
            "target": str(
                getattr(change, "target", "")
                or getattr(change, "target_file", "")
                or ""
            ),
        }
    )


def _drop_empty_identity_fields(value: dict[str, str]) -> dict[str, str]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {}, ())
    }


def _mechanism_id_schema_retry_pending(
    preview_rejections: list[Mapping[str, Any]],
) -> bool:
    if not preview_rejections:
        return False
    return (
        str(preview_rejections[-1].get("failure_code") or "").strip()
        == "invalid_mechanism_id"
    )
