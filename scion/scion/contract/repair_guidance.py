"""Generic contract repair guidance templates."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from scion.core.models import HypothesisProposal, HypothesisRecord, PatchProposal

_DIRECT_SIGNATURE_FIELDS = frozenset(
    {"predicted_direction", "target_objectives", "protected_objectives"}
)


def novelty_signature_missing_fields_template(
    hypothesis: HypothesisProposal | HypothesisRecord | None,
    *,
    surface_name: str,
    missing_fields: Sequence[str],
    required_fields: Sequence[str],
) -> dict[str, Any]:
    """Return generic C10 repair guidance for missing semantic signature fields."""

    mechanism_ids = _mechanism_ids(hypothesis)
    novelty_fields = [
        field
        for field in _ordered_strings(required_fields)
        if field not in _DIRECT_SIGNATURE_FIELDS
    ]
    direct_fields = [
        field for field in _ordered_strings(required_fields) if field in _DIRECT_SIGNATURE_FIELDS
    ]
    novelty_template = {
        field: _novelty_signature_placeholder(field) for field in novelty_fields
    }
    novelty_template.setdefault(
        "mechanism_id",
        (
            mechanism_ids[0]
            if len(mechanism_ids) == 1
            else "<same id as mechanism_changes and expected telemetry>"
        ),
    )
    return _drop_empty(
        {
            "repair_type": "novelty_signature_missing_fields",
            "check": "C10_novelty",
            "severity": "light",
            "surface": surface_name,
            "missing_fields": _ordered_strings(missing_fields),
            "required_fields": _ordered_strings(required_fields),
            "required_template": _drop_empty(
                {
                    "top_level_fields": {
                        field: _direct_signature_placeholder(field)
                        for field in direct_fields
                    },
                    "novelty_signature": novelty_template,
                }
            ),
            "mechanism_id_consistency": _drop_empty(
                {
                    "mechanism_change_ids": mechanism_ids,
                    "instruction": (
                        "Use the same concrete mechanism id in mechanism_changes, "
                        "novelty_signature.mechanism_id when present, "
                        "expected_telemetry mechanism-specific fields, and patch "
                        "telemetry records."
                    ),
                }
            ),
            "agent_instruction": [
                "Do not invent problem facts.",
                (
                    "If a strategy is unchanged, say unchanged and name the "
                    "baseline component from the active solver map or baseline "
                    "component summary."
                ),
                (
                    "Mechanism id must match mechanism_changes and expected "
                    "telemetry mechanism-specific field names."
                ),
            ],
        }
    )


def patch_primary_target_mismatch_template(
    patch: PatchProposal,
    *,
    hypothesis_target_file: str,
    patch_primary_file: str,
    additional_change_files: Sequence[str] = (),
) -> dict[str, Any]:
    """Return generic C4b repair guidance for primary target mismatches."""

    additional = _ordered_strings(additional_change_files)
    helper_candidates = [
        path
        for path in _ordered_strings((hypothesis_target_file, *additional))
        if path != patch_primary_file
    ]
    return _drop_empty(
        {
            "repair_type": "patch_primary_target_mismatch",
            "check": "C4b_patch_action_target",
            "severity": "heavy",
            "observed": {
                "hypothesis_target_file": hypothesis_target_file,
                "patch_primary_file": patch_primary_file,
                "additional_change_files": additional,
            },
            "recommended_shape": {
                "hypothesis_target_file": "<primary integration file>",
                "patch": {
                    "file_path": "<same primary integration file>",
                    "additional_changes": [
                        {"file_path": "<helper module>"}
                    ],
                },
                "recommended_primary_integration_file": (
                    "the file where the mechanism is wired into the active "
                    "algorithm body"
                ),
                "helper_module_candidates": helper_candidates,
            },
            "reasoning": [
                (
                    "The primary target file is where the mechanism is wired "
                    "into the active algorithm body."
                ),
                (
                    "Helper modules may be modified as additional_changes if "
                    "allowlisted and reachable."
                ),
            ],
            "agent_instruction": [
                (
                    "If adding a helper plus registering or scheduling it, use "
                    "the registry or integration file as the hypothesis target "
                    "and patch primary file."
                ),
                (
                    "If changing only a helper body already called by the "
                    "baseline active path, that helper can be primary."
                ),
                (
                    "Do not loosen the contract: regenerate hypothesis/patch "
                    "so patch.file_path exactly matches hypothesis.target_file."
                ),
            ],
        }
    )


def _mechanism_ids(
    hypothesis: HypothesisProposal | HypothesisRecord | None,
) -> list[str]:
    ids: list[str] = []
    for change in getattr(hypothesis, "mechanism_changes", ()) or ():
        if isinstance(change, Mapping):
            value = change.get("id")
        else:
            value = getattr(change, "id", None)
        text = str(value or "").strip()
        if text and text not in ids:
            ids.append(text)
    return ids


def _ordered_strings(values: Sequence[str]) -> list[str]:
    items: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in items:
            items.append(text)
    return items


def _novelty_signature_placeholder(field: str) -> str:
    if field == "algorithm_family":
        return "<generic algorithm or mechanism family>"
    if field == "construction_strategy":
        return "<unchanged|modified|new construction behavior>"
    if field == "improvement_strategy":
        return "<what changes search or improvement behavior>"
    if field == "acceptance_strategy":
        return "<unchanged|modified acceptance behavior>"
    if field == "runtime_budget_strategy":
        return "<how runtime is bounded or reallocated>"
    if field == "mechanism_id":
        return "<same id as mechanism_changes and expected telemetry>"
    return f"<structured identity value for {field}>"


def _direct_signature_placeholder(field: str) -> Any:
    if field == "predicted_direction":
        return "<improve|tradeoff|exploratory>"
    if field == "target_objectives":
        return ["<objective metric name>"]
    if field == "protected_objectives":
        return ["<objective metric name>"]
    return f"<{field}>"


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in ({}, [], None, "")}


__all__ = [
    "novelty_signature_missing_fields_template",
    "patch_primary_target_mismatch_template",
]
