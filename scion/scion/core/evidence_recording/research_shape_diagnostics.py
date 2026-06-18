"""Read-only campaign research-shape diagnostics for status artifacts."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from scion.core.explore_step.generic_mechanism_signature import (
    generic_signature_key_from_hypothesis,
    generic_signature_key_from_parts,
)
from scion.core.models import StepRecord

_SCHEMA_VERSION = "campaign_research_shape_diagnostics.v1"
_DECISION_INPUT_POLICY = "excluded_from_decision_features"
_ACTIVE_STATES = {
    "new",
    "explore",
    "explore_expand",
    "ready_validate",
    "validating",
    "validating_expand",
    "ready_frozen",
    "frozen_testing",
    "blocked_infra",
}


def build_campaign_research_shape_diagnostics(
    *,
    steps: Iterable[StepRecord] = (),
    branch_rows: Iterable[Mapping[str, Any]] = (),
    branch_history_cards: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return summary/status-only diagnostics from persisted branch evidence."""

    step_list = [step for step in steps if isinstance(step, StepRecord)]
    row_list = [row for row in branch_rows if isinstance(row, Mapping)]
    card_list = [card for card in branch_history_cards if isinstance(card, Mapping)]
    if not card_list:
        card_list = _cards_from_rows(row_list)

    step_depths = _step_depths(step_list)
    card_depths = _card_depths(card_list)
    depths = step_depths or card_depths
    family_counts = _mechanism_family_counts(step_list, row_list, card_list)
    branch_family_map = _branch_mechanism_family_map(step_list, row_list, card_list)
    active_rows = [row for row in row_list if _is_active_branch_row(row)]
    active_cards = _active_cards(card_list, active_rows)
    active_families = _active_mechanism_families(active_cards)

    return {
        "schema_version": _SCHEMA_VERSION,
        "policy": "summary_status_observability_only",
        "advisory_only": True,
        "decision_features_excluded": True,
        "decision_input_policy": _DECISION_INPUT_POLICY,
        "source": {
            "step_history": "campaign_summary_step_history" if step_list else "none",
            "branch_rows": "state_branch_rows_snapshot" if row_list else "none",
            "branch_history_cards": (
                "branch_history_cards_snapshot" if card_list else "none"
            ),
            "branch_depth_source": (
                "step_history_branch_counts"
                if step_depths
                else "branch_history_card_observed_depth"
                if card_depths
                else "none"
            ),
        },
        "branch_depth_distribution": _depth_distribution(depths),
        "branch_depth_by_branch": dict(sorted(depths.items())),
        "max_branch_depth": max(depths.values(), default=0),
        "mean_branch_depth": _mean_depth(depths),
        "active_research_shape_signal": {
            "active_branch_count": len(active_rows),
            "active_branch_ids": [
                str(row.get("id") or row.get("branch_id") or "")
                for row in active_rows
                if str(row.get("id") or row.get("branch_id") or "")
            ],
            "active_mechanism_family_count": len(active_families),
            "active_mechanism_families": active_families,
            "shape": _shape_label(
                active_branch_count=len(active_rows),
                max_depth=max(depths.values(), default=0),
            ),
        },
        "mechanism_family_breadth": {
            "family_count": len(family_counts),
            "families": dict(sorted(family_counts.items())),
        },
        "branch_mechanism_family_map": branch_family_map,
    }


def _cards_from_rows(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    cards: list[Mapping[str, Any]] = []
    for row in rows:
        card = row.get("branch_card")
        if isinstance(card, Mapping):
            cards.append(card)
    return cards


def _step_depths(steps: Iterable[StepRecord]) -> dict[str, int]:
    depths: Counter[str] = Counter()
    for step in steps:
        branch_id = str(getattr(step, "branch_id", "") or "")
        if not branch_id:
            continue
        depths[branch_id] += 1
    return dict(depths)


def _card_depths(cards: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    depths: dict[str, int] = {}
    for card in cards:
        branch_id = str(card.get("branch_id") or "")
        if not branch_id:
            continue
        depth = _nonnegative_int(
            card.get("observed_depth"),
            card.get("observed_step_count"),
            card.get("step_count"),
            default=0,
        )
        depths[branch_id] = max(depths.get(branch_id, 0), depth)
    return depths


def _depth_distribution(depths: Mapping[str, int]) -> dict[str, int]:
    histogram: Counter[str] = Counter()
    for depth in depths.values():
        histogram[str(max(0, int(depth or 0)))] += 1
    return dict(sorted(histogram.items(), key=lambda item: int(item[0])))


def _mean_depth(depths: Mapping[str, int]) -> float:
    if not depths:
        return 0.0
    total_depth = sum(max(0, int(value or 0)) for value in depths.values())
    return round(total_depth / len(depths), 4)


def _mechanism_family_counts(
    steps: Iterable[StepRecord],
    rows: Iterable[Mapping[str, Any]],
    cards: Iterable[Mapping[str, Any]],
) -> dict[str, int]:
    families: Counter[str] = Counter()
    for step in steps:
        family = _step_mechanism_family(step)
        if family:
            families[family] += 1
    seen_branch_families: set[tuple[str, str]] = set()
    for row in rows:
        branch_id = str(row.get("id") or row.get("branch_id") or "")
        for family in _row_mechanism_families(row):
            key = (branch_id, family)
            if key in seen_branch_families:
                continue
            seen_branch_families.add(key)
            families[family] += 1
    for card in cards:
        branch_id = str(card.get("branch_id") or "")
        for family in _card_mechanism_families(card):
            key = (branch_id, family)
            if key in seen_branch_families:
                continue
            seen_branch_families.add(key)
            families[family] += 1
    return {
        family: count
        for family, count in families.items()
        if family and family != "unknown" and count > 0
    }


def _branch_mechanism_family_map(
    steps: Iterable[StepRecord],
    rows: Iterable[Mapping[str, Any]],
    cards: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    by_branch: dict[str, Counter[str]] = {}
    source_counts: dict[str, Counter[str]] = {}

    def add(branch_id: str, families: Iterable[str], *, source: str) -> None:
        branch = str(branch_id or "").strip()
        if not branch:
            return
        for family in families:
            clean = _clean_token(family)
            if not clean or clean == "unknown":
                continue
            by_branch.setdefault(branch, Counter())[clean] += 1
            source_counts.setdefault(branch, Counter())[source] += 1

    for step in steps:
        add(
            getattr(step, "branch_id", ""),
            (_step_mechanism_family(step),),
            source="step_history",
        )
    for row in rows:
        add(
            str(row.get("id") or row.get("branch_id") or ""),
            _row_mechanism_families(row),
            source="branch_rows",
        )
    for card in cards:
        add(
            str(card.get("branch_id") or ""),
            _card_mechanism_families(card),
            source="branch_history_cards",
        )

    result: dict[str, dict[str, Any]] = {}
    for branch_id, counts in sorted(by_branch.items()):
        if not counts:
            continue
        primary_family, _ = sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[0]
        result[branch_id] = {
            "primary_family": primary_family,
            "families": dict(sorted(counts.items())),
            "sources": dict(
                sorted(source_counts.get(branch_id, Counter()).items())
            ),
        }
    return result


def _step_mechanism_family(step: StepRecord) -> str:
    hypothesis = getattr(step, "hypothesis", None)
    if hypothesis is None:
        return ""
    key = generic_signature_key_from_hypothesis(hypothesis)
    return _clean_token(key[0])


def _row_mechanism_families(row: Mapping[str, Any]) -> list[str]:
    card = row.get("branch_card")
    card_map = card if isinstance(card, Mapping) else {}
    families = _card_mechanism_families(card_map)
    if families:
        return families
    mechanism_ids = row.get("branch_mechanism_ids")
    if isinstance(mechanism_ids, (list, tuple)):
        return _mechanism_id_families(mechanism_ids)
    return []


def _card_mechanism_families(card: Mapping[str, Any]) -> list[str]:
    signature = card.get("generic_mechanism_signature")
    if isinstance(signature, Mapping):
        family = _clean_token(
            signature.get("mechanism_family")
            or signature.get("family")
            or signature.get("mechanism_id")
        )
        if family:
            return [family]
    mechanism_ids = card.get("mechanism_ids") or card.get("branch_mechanism_ids")
    if isinstance(mechanism_ids, (list, tuple)):
        families = _mechanism_id_families(mechanism_ids)
        if families:
            return families
    direction = str(card.get("direction") or "")
    action = ""
    change_locus = ""
    if "/" in direction:
        action, change_locus = direction.split("/", 1)
    key = generic_signature_key_from_parts(
        mechanism_ids=(),
        signature={},
        target_file="",
        action=_clean_token(action),
        change_locus=_clean_token(change_locus),
    )
    return [_clean_token(key[0])] if _clean_token(key[0]) else []


def _is_active_branch_row(row: Mapping[str, Any]) -> bool:
    state = _clean_token(row.get("state"))
    if state in _ACTIVE_STATES:
        return True
    card = row.get("branch_card")
    card_map = card if isinstance(card, Mapping) else {}
    status = _clean_token(card_map.get("status") or card_map.get("lineage_status"))
    return status.startswith("active") or status.startswith("ready")


def _active_cards(
    cards: Iterable[Mapping[str, Any]],
    active_rows: Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    active_ids = {
        str(row.get("id") or row.get("branch_id") or "")
        for row in active_rows
        if str(row.get("id") or row.get("branch_id") or "")
    }
    return [
        card
        for card in cards
        if str(card.get("branch_id") or "") in active_ids
        or _clean_token(card.get("status") or card.get("lineage_status")).startswith(
            "active"
        )
    ]


def _active_mechanism_families(cards: Iterable[Mapping[str, Any]]) -> list[str]:
    families: set[str] = set()
    for card in cards:
        families.update(_card_mechanism_families(card))
    return sorted(family for family in families if family and family != "unknown")


def _mechanism_id_family(value: Any) -> str:
    token = _clean_token(value)
    if not token:
        return ""
    key = generic_signature_key_from_parts(
        mechanism_ids=(token,),
        signature={},
        target_file="",
        action="",
        change_locus="",
    )
    return _clean_token(key[0]) or token


def _mechanism_id_families(values: Iterable[Any]) -> list[str]:
    families: list[str] = []
    for value in values:
        family = _mechanism_id_family(value)
        if family:
            families.append(family)
    return families


def _shape_label(*, active_branch_count: int, max_depth: int) -> str:
    if active_branch_count <= 0:
        return "no_active_research_branch"
    if max_depth <= 1 and active_branch_count >= 3:
        return "wide_shallow"
    if max_depth >= 3 and active_branch_count <= 2:
        return "deep_focused"
    if max_depth >= 2:
        return "mixed_depth"
    return "shallow"


def _clean_token(value: Any) -> str:
    token = str(value or "").strip().lower()
    cleaned = []
    for char in token:
        cleaned.append(char if char.isalnum() or char in {"_", "-", "."} else "_")
    return "_".join(part for part in "".join(cleaned).split("_") if part)


def _nonnegative_int(*values: Any, default: int = 0) -> int:
    for value in values:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue
    return max(0, int(default))
