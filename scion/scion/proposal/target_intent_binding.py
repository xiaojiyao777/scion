"""Target-intent binding helpers for agentic hypothesis preflight."""

from __future__ import annotations

import re
from typing import Any, Mapping

from scion.core.models import HypothesisProposal


def target_intent_binding_retry_pending(
    preview_rejections: list[Mapping[str, Any]],
) -> bool:
    if not preview_rejections:
        return False
    return (
        str(preview_rejections[-1].get("failure_code") or "").strip()
        == "target_intent_binding_mismatch"
    )


def target_intent_binding_retry_feedback(
    target_intent: Mapping[str, Any] | None,
    hypothesis: HypothesisProposal,
    *,
    attempt: int,
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    selected = selected_target_intent_payload(target_intent)
    if not selected:
        return None
    formal = formal_hypothesis_target_payload(hypothesis)
    mismatches: list[dict[str, Any]] = []
    for field in ("change_locus", "action", "target_file"):
        expected = str(selected.get(field) or "").strip()
        observed = str(formal.get(field) or "").strip()
        if expected and expected != observed:
            mismatches.append(
                {
                    "field": field,
                    "selected": expected,
                    "formal": observed,
                }
            )
    mechanism_mismatch = _target_intent_mechanism_mismatch(selected, formal)
    if mechanism_mismatch:
        mismatches.append(mechanism_mismatch)
    if not mismatches:
        return None
    reason = _target_intent_binding_reason(mismatches)
    return _drop_empty(
        {
            "attempt": attempt,
            "attempt_kind": "target_intent_binding_repair",
            "repair_classification": "target_intent_binding_repair",
            "source": "hypothesis_target_intent_binding_gate",
            "gate_name": "hypothesis_target_intent_binding_gate",
            "failure_code": "target_intent_binding_mismatch",
            "check": "target_intent_binding",
            "failure_category": "contract_boundary_failure",
            "reason": reason,
            "binding_status": "mismatch",
            "mismatched_fields": [item["field"] for item in mismatches],
            "mismatches": mismatches,
            "selected_target_intent": selected,
            "formal_hypothesis_target": formal,
            "formal_target_source_visibility_ledger": (
                formal_target_source_visibility_from_manifest(manifest, hypothesis)
            ),
            "preserve_hypothesis": selected,
            "protected_identity": {
                "change_locus": selected.get("change_locus"),
                "action": selected.get("action"),
                "target_file": selected.get("target_file"),
                "mechanism_id": selected.get("mechanism_id"),
                "mechanism_family": selected.get("mechanism_family"),
            },
            "final_task": (
                "Rewrite the formal hypothesis under the same selected "
                "target-intent preflight."
            ),
            "retry_constraint": (
                "The selected target-intent is binding for this formal "
                "hypothesis call. Keep change_locus, action, target_file, and "
                "mechanism family/continuation consistent with "
                "selected_target_intent. Do not silently choose another owner "
                "or mechanism. A different target requires an explicit host "
                "target-intent reselect flow before formal hypothesis "
                "generation, not a schema retry."
            ),
            "proposal_failure_accounting": (
                "pre_code_binding_retry; do_not_count_as_code_or_screening_failure"
            ),
        }
    )


def target_intent_mechanism_family(
    *,
    mechanism_family: Any,
    mechanism_id: Any,
    mechanism_sketch: Any,
) -> tuple[str, str]:
    provided = str(mechanism_family or "").strip()
    if provided:
        return provided, "provided"
    from_id = _mechanism_family_from_id(mechanism_id)
    if from_id:
        return from_id, "fallback_from_mechanism_id"
    from_sketch = _mechanism_family_from_sketch(mechanism_sketch)
    if from_sketch:
        return from_sketch, "fallback_from_mechanism_sketch"
    return "optional_missing", "optional_missing"


def selected_target_intent_payload(
    target_intent: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(target_intent, Mapping):
        return {}
    raw_intent = target_intent.get("intent")
    intent = raw_intent if isinstance(raw_intent, Mapping) else target_intent
    action = _normalize_action(intent.get("action"))
    surface = str(intent.get("change_locus") or intent.get("surface") or "").strip()
    return _drop_empty(
        {
            "change_locus": surface,
            "surface": surface,
            "action": action,
            "target_file": _normalize_path(intent.get("target_file")),
            "mechanism_id": intent.get("mechanism_id"),
            "mechanism_family": intent.get("mechanism_family"),
            "mechanism_family_status": intent.get("mechanism_family_status"),
            "mechanism_sketch": intent.get("mechanism_sketch"),
            "confidence": intent.get("confidence"),
        }
    )


def formal_hypothesis_target_payload(
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    novelty_signature = getattr(hypothesis, "novelty_signature", {}) or {}
    family = ""
    if isinstance(novelty_signature, Mapping):
        for key in (
            "mechanism_family",
            "algorithm_family",
            "improvement_strategy",
        ):
            value = str(novelty_signature.get(key) or "").strip()
            if value:
                family = value
                break
    mechanism_ids = [
        mechanism_id
        for mechanism_id in (
            _mechanism_change_id(change)
            for change in getattr(hypothesis, "mechanism_changes", ()) or ()
        )
        if mechanism_id
    ]
    surface = str(hypothesis.change_locus or "").strip()
    return _drop_empty(
        {
            "change_locus": surface,
            "surface": surface,
            "action": _normalize_action(hypothesis.action),
            "target_file": _normalize_path(hypothesis.target_file),
            "mechanism_ids": mechanism_ids,
            "mechanism_family": family,
        }
    )


def formal_target_source_visibility_from_manifest(
    manifest: Mapping[str, Any] | None,
    hypothesis: HypothesisProposal,
) -> dict[str, Any]:
    manifest_map = manifest if isinstance(manifest, Mapping) else {}
    target_file = _normalize_path(hypothesis.target_file)
    action = _normalize_action(hypothesis.action)
    if not target_file:
        return {}
    target_source_required = action in {"modify", "remove"}
    included = manifest_map.get("included_observations")
    included_observations = included if isinstance(included, list) else []
    source_items = [
        item
        for item in included_observations
        if isinstance(item, Mapping)
        and item.get("tool_name") == "context.read_algorithm_file"
        and _normalize_path(item.get("file_path")) == target_file
    ]
    owner_source = _best_formal_target_source_item(source_items)
    visibility_status = (
        "full_dedicated_source_visible"
        if owner_source.get("full_content_visible_in_dedicated_source_section")
        else "source_visible"
        if owner_source.get("content_preview_visible_in_rendered_prompt")
        or owner_source.get("full_content_visible_in_rendered_prompt")
        else "create_new_placeholder_visible"
        if action == "create_new"
        else "not_visible"
    )
    return _drop_empty(
        {
            "schema_version": "formal-target-source-visibility-ledger.v1",
            "call_kind": manifest_map.get("call_kind"),
            "prompt_hash": manifest_map.get("prompt_hash"),
            "formal_target": {
                "change_locus": hypothesis.change_locus,
                "action": action,
                "target_file": target_file,
            },
            "target_source_required": target_source_required,
            "owner_source": owner_source,
            "visibility_status": visibility_status,
            "source_of_truth": (
                "formal_hypothesis_target_file; not preflight target intent"
            ),
        }
    )


def _target_intent_binding_reason(mismatches: list[Mapping[str, Any]]) -> str:
    parts = [
        (
            f"{item.get('field')}: selected={item.get('selected')!r} "
            f"formal={item.get('formal')!r}"
        )
        for item in mismatches
    ]
    return (
        "target_intent_binding_mismatch: formal hypothesis target/action/"
        "mechanism must stay bound to selected hypothesis_target_intent; "
        + "; ".join(parts)
    )


def _mechanism_change_id(change: Any) -> str:
    if isinstance(change, Mapping):
        return str(change.get("id") or "").strip()
    return str(getattr(change, "id", "") or "").strip()


def _target_intent_mechanism_mismatch(
    selected: Mapping[str, Any],
    formal: Mapping[str, Any],
) -> dict[str, Any]:
    selected_id = str(selected.get("mechanism_id") or "").strip()
    selected_family = str(selected.get("mechanism_family") or "").strip()
    formal_ids = [
        str(item).strip()
        for item in (formal.get("mechanism_ids") or ())
        if str(item).strip()
    ]
    formal_family = str(formal.get("mechanism_family") or "").strip()
    if selected_id and formal_ids:
        selected_token = _mechanism_binding_token(selected_id)
        formal_tokens = [_mechanism_binding_token(item) for item in formal_ids]
        if selected_token and any(
            _mechanism_tokens_compatible(selected_token, token)
            for token in formal_tokens
        ):
            return {}
        if selected_token:
            return {
                "field": "mechanism_id",
                "selected": selected_id,
                "formal": formal_ids,
            }
    if selected_family and formal_family:
        selected_token = _mechanism_binding_token(selected_family)
        formal_token = _mechanism_binding_token(formal_family)
        if (
            selected_token
            and formal_token
            and not _mechanism_tokens_compatible(selected_token, formal_token)
        ):
            return {
                "field": "mechanism_family",
                "selected": selected_family,
                "formal": formal_family,
            }
    return {}


def _mechanism_binding_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _mechanism_tokens_compatible(selected: str, formal: str) -> bool:
    if not selected or not formal:
        return False
    if selected == formal:
        return True
    if selected.startswith(f"{formal}_") or formal.startswith(f"{selected}_"):
        return True
    if f"_{selected}_" in f"_{formal}_" or f"_{formal}_" in f"_{selected}_":
        return True
    selected_parts = [part for part in selected.split("_") if part]
    formal_parts = [part for part in formal.split("_") if part]
    if not selected_parts or not formal_parts:
        return False
    min_len = min(len(selected_parts), len(formal_parts), 3)
    return selected_parts[-min_len:] == formal_parts[-min_len:]


def _mechanism_family_from_id(value: Any) -> str:
    token = _mechanism_binding_token(value)
    if not token:
        return ""
    parts = [part for part in token.split("_") if part]
    if len(parts) > 4:
        parts = parts[-4:]
    return "_".join(parts)


def _mechanism_family_from_sketch(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    words = re.findall(r"[a-z0-9]+", text)
    stop_words = {
        "a",
        "an",
        "and",
        "for",
        "in",
        "of",
        "the",
        "to",
        "with",
    }
    words = [word for word in words if word not in stop_words]
    return "_".join(words[:5])


def _best_formal_target_source_item(
    items: list[Mapping[str, Any]],
) -> dict[str, Any]:
    if not items:
        return {}
    ranked = sorted(
        items,
        key=lambda item: (
            bool(item.get("full_content_visible_in_dedicated_source_section")),
            bool(item.get("full_content_visible_in_rendered_prompt")),
            bool(item.get("content_preview_visible_in_rendered_prompt")),
            int(item.get("visible_content_chars") or 0),
        ),
        reverse=True,
    )
    item = ranked[0]
    return _drop_empty(
        {
            "observation_id": item.get("observation_id"),
            "file_path": item.get("file_path"),
            "source": item.get("source"),
            "source_provenance": item.get("source_provenance"),
            "visibility_status": item.get("prompt_visibility_status"),
            "included_in_prompt_for_call": item.get("included_in_prompt_for_call"),
            "full_content_included_in_prompt": item.get(
                "full_content_included_in_prompt"
            ),
            "full_content_visible_in_rendered_prompt": item.get(
                "full_content_visible_in_rendered_prompt"
            ),
            "full_content_visible_in_dedicated_source_section": item.get(
                "full_content_visible_in_dedicated_source_section"
            ),
            "content_preview_visible_in_rendered_prompt": item.get(
                "content_preview_visible_in_rendered_prompt"
            ),
            "content_projection_count": item.get("content_projection_count"),
            "visible_content_projection_count": item.get(
                "visible_content_projection_count"
            ),
        }
    )


def _normalize_action(value: Any) -> str:
    action = str(value or "").strip()
    return "create_new" if action == "create" else action


def _normalize_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], (), {})
    }


__all__ = [
    "formal_hypothesis_target_payload",
    "formal_target_source_visibility_from_manifest",
    "selected_target_intent_payload",
    "target_intent_binding_retry_feedback",
    "target_intent_binding_retry_pending",
    "target_intent_mechanism_family",
]
