"""Report-only resume snapshot helpers for prepared handoff artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def load_resume_campaign_summary(
    *,
    root: Path,
    manifest: Mapping[str, Any],
    run_status: Mapping[str, Any],
    current_summary: Any,
) -> Mapping[str, Any]:
    """Return current campaign summary or the quarantined resume summary."""

    if isinstance(current_summary, Mapping):
        return current_summary
    snapshot_path = resume_snapshot_artifact_path(
        root=root,
        manifest=manifest,
        run_status=run_status,
        original_ref="campaign_summary.json",
    )
    if snapshot_path is None:
        return {}
    snapshot_doc = _read_json(snapshot_path)
    if isinstance(snapshot_doc, Mapping):
        return snapshot_doc
    return {}


def resume_snapshot_artifact_path(
    *,
    root: Path,
    manifest: Mapping[str, Any],
    run_status: Mapping[str, Any],
    original_ref: str,
) -> Path | None:
    manifest_ref = _string_or_none(manifest.get("resume_snapshot_ref"))
    if not manifest_ref:
        manifest_ref = _string_or_none(run_status.get("resume_snapshot_ref"))
    if not manifest_ref:
        return None
    snapshot_manifest_path = _root_relative_path(root, manifest_ref)
    if snapshot_manifest_path is None:
        return None
    snapshot_manifest = _read_json(snapshot_manifest_path)
    if not isinstance(snapshot_manifest, Mapping):
        return None
    for item in snapshot_manifest.get("terminal_artifacts") or []:
        if not isinstance(item, Mapping):
            continue
        if item.get("original_ref") != original_ref:
            continue
        snapshot_ref = _string_or_none(item.get("snapshot_ref"))
        if not snapshot_ref:
            return None
        return _root_relative_path(root, snapshot_ref)
    return None


def build_resume_top_branch_summaries(
    *,
    branches: list[dict[str, Any]],
    summary: Mapping[str, Any],
    limit: int = 10,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for branch in branches:
        branch_id = _string_or_none(branch.get("branch_id"))
        if not branch_id:
            continue
        by_id[branch_id] = _drop_empty(
            {
                "branch_id": branch_id,
                "state": branch.get("state"),
                "lineage_id": branch.get("lineage_id") or branch_id,
                "hypothesis_count": branch.get("hypothesis_count"),
                "event_count": branch.get("event_count"),
                "session_count": branch.get("session_count"),
                "trace_count": branch.get("trace_count"),
                "rollback_count": branch.get("rollback_count"),
                "failure_codes": _string_list(branch.get("failure_codes")),
            }
        )

    for card in _resume_branch_cards(summary):
        branch_id = _branch_id(card)
        if not branch_id:
            continue
        merged = dict(by_id.get(branch_id) or {"branch_id": branch_id})
        card_summary = _resume_branch_card_summary(card)
        for key, value in card_summary.items():
            if _value_present(value) or key not in merged:
                merged[key] = value
        by_id[branch_id] = _drop_empty(merged)

    ordered = sorted(
        by_id.values(),
        key=lambda branch: (
            -_resume_branch_priority(branch),
            -_int_or_zero(branch.get("event_count")),
            -_int_or_zero(branch.get("hypothesis_count")),
            str(branch.get("branch_id") or ""),
        ),
    )
    return ordered[:limit]


def _resume_branch_cards(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cards: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for key in ("branch_cards", "branch_history_cards", "branches"):
        values = summary.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, Mapping):
                continue
            branch_id = _branch_id(value) or ""
            card_text = _string_or_none(value.get("branch_card_text")) or ""
            identity = f"{key}:{branch_id}:{card_text[:80]}"
            if identity in seen:
                continue
            seen.add(identity)
            cards.append(value)
    return cards


def _resume_branch_card_summary(card: Mapping[str, Any]) -> dict[str, Any]:
    nested_card = card.get("branch_card")
    if not isinstance(nested_card, Mapping):
        nested_card = {}
    scheduling = card.get("branch_scheduling_status")
    if not isinstance(scheduling, Mapping):
        scheduling = nested_card.get("branch_scheduling_status")
    if not isinstance(scheduling, Mapping):
        scheduling = {}
    classification = card.get("final_branch_classification")
    if not isinstance(classification, Mapping):
        classification = card.get("branch_final_classification")
    if not isinstance(classification, Mapping):
        classification = nested_card.get("final_branch_classification")
    if not isinstance(classification, Mapping):
        classification = {}
    return _drop_empty(
        {
            "branch_id": _branch_id(card),
            "state": _first_present(
                card.get("state"),
                card.get("status"),
                card.get("branch_state"),
                scheduling.get("branch_state"),
                classification.get("branch_state"),
                nested_card.get("state"),
                nested_card.get("status"),
                nested_card.get("branch_state"),
            ),
            "lineage_id": _first_present(
                card.get("lineage_id"),
                nested_card.get("lineage_id"),
            ),
            "branch_code_status": _first_present(
                card.get("branch_code_status"),
                scheduling.get("branch_code_status"),
                classification.get("branch_code_status"),
                nested_card.get("branch_code_status"),
            ),
            "classification": _first_present(
                card.get("branch_final_classification"),
                classification.get("classification"),
            ),
            "classification_reason": _first_present(
                card.get("branch_classification_reason"),
                classification.get("reason"),
            ),
            "scheduling_lane": card.get("branch_scheduling_lane"),
            "scheduling_reason": card.get("branch_scheduling_next_action_reason"),
            "next_action": _first_present(
                card.get("branch_next_action"),
                scheduling.get("next_action"),
                scheduling.get("branch_next_action"),
            ),
            "mechanism_ids": _resume_branch_mechanism_ids(card, nested_card),
            "followup_recommended": _first_present(
                card.get("followup_recommended"),
                nested_card.get("followup_recommended"),
            ),
            "followup_required": _first_present(
                card.get("followup_required"),
                nested_card.get("followup_required"),
            ),
            "allowed_next_actions": _string_list(
                _first_present(
                    card.get("allowed_next_actions"),
                    nested_card.get("allowed_next_actions"),
                )
            ),
            "forbidden_next_actions": _string_list(
                _first_present(
                    card.get("forbidden_next_actions"),
                    nested_card.get("forbidden_next_actions"),
                )
            ),
            "failure_codes": _string_list(card.get("failure_codes")),
            "why_not_promoted_reason_codes": _string_list(
                card.get("why_not_promoted_reason_codes")
            ),
            "why_abandoned_reason_codes": _string_list(
                card.get("why_abandoned_reason_codes")
            ),
            "branch_card_text": _truncate_text(
                _string_or_none(card.get("branch_card_text")),
                1200,
            ),
        }
    )


def _resume_branch_mechanism_ids(
    card: Mapping[str, Any],
    nested_card: Mapping[str, Any],
) -> list[str]:
    values: list[str] = []
    for source in (card, nested_card):
        values.extend(_string_list(source.get("branch_mechanism_ids")))
        values.extend(_string_list(source.get("mechanism_ids")))
        primary = _string_or_none(source.get("primary_mechanism_id"))
        if primary:
            values.append(primary)
        contract = source.get("mechanism_evidence_contract")
        if isinstance(contract, Mapping):
            values.extend(_string_list(contract.get("declared_mechanism_ids")))
            primary = _string_or_none(contract.get("primary_mechanism_id"))
            if primary:
                values.append(primary)
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _resume_branch_priority(branch: Mapping[str, Any]) -> int:
    state = str(branch.get("state") or "").lower()
    classification = str(branch.get("classification") or "").lower()
    branch_code_status = str(branch.get("branch_code_status") or "").lower()
    scheduling_lane = str(branch.get("scheduling_lane") or "").lower()
    if "weak_positive" in scheduling_lane:
        return 70
    if branch_code_status == "clean" and branch.get("followup_recommended") is True:
        return 65
    if branch.get("followup_required") is True and (
        "quality_regression" in branch_code_status or "diagnostic" in scheduling_lane
    ):
        return 45
    if branch.get("followup_required") is True:
        return 60
    if branch.get("followup_recommended") is True:
        return 50
    if "followup" in scheduling_lane:
        return 40
    if "active" in classification or state in {"explore", "explore_expand"}:
        return 30
    if "abandon" in state or "abandon" in classification:
        return 0
    return 10


def _branch_id(doc: Mapping[str, Any]) -> str | None:
    for key in ("branch_id", "id", "branch"):
        value = _string_or_none(doc.get(key))
        if value:
            return value
    nested = doc.get("branch_card")
    if isinstance(nested, Mapping):
        return _branch_id(nested)
    return None


def _root_relative_path(root: Path, ref: str) -> Path | None:
    candidate = (root / ref).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _drop_empty(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if _value_present(item)}


def _value_present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _first_present(*values: Any) -> Any:
    for value in values:
        if _value_present(value):
            return value
    return None


def _truncate_text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return [part.strip() for part in text.split(",") if part.strip()]
        return _string_list(parsed)
    return [str(value)]


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
