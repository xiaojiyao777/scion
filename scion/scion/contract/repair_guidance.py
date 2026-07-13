"""Generic contract repair guidance templates."""
from __future__ import annotations

from typing import Any, Sequence

from scion.core.models import PatchProposal


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


def _ordered_strings(values: Sequence[str]) -> list[str]:
    items: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in items:
            items.append(text)
    return items


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in ({}, [], None, "")}


__all__ = [
    "patch_primary_target_mismatch_template",
]
