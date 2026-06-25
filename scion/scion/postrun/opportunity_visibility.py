"""Postrun visibility summaries for problem opportunity prompt sections."""

from __future__ import annotations

from typing import Any, Mapping


SECTION_FINGERPRINT_SCHEMA = "scion.prompt_section_visibility_fingerprint.v1"
PROBLEM_OPPORTUNITY_VISIBILITY_SCHEMA = (
    "scion.postrun_problem_opportunity_visibility_summary.v1"
)
OPPORTUNITY_COMMITMENT_VISIBILITY_SCHEMA = (
    "scion.postrun_opportunity_evidence_commitment_visibility_summary.v1"
)
PROBLEM_OPPORTUNITY_SECTION = "problem_opportunity_summary"
OPPORTUNITY_COMMITMENT_SECTION = "opportunity_evidence_commitment"


def problem_opportunity_visibility_fingerprint(
    prompt_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Project prompt-manifest visibility for the opportunity section."""

    return _section_visibility_fingerprint(
        prompt_manifest,
        section_name=PROBLEM_OPPORTUNITY_SECTION,
        context_visibility_key="problem_opportunity_summary_visibility",
        context_prompt_key="problem_opportunity_summary_prompt_key",
    )


def opportunity_commitment_visibility_fingerprint(
    prompt_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Project prompt-manifest visibility for the code-phase commitment."""

    commitment_summary = _mapping(
        prompt_manifest.get("opportunity_evidence_commitment_summary")
    )
    return _section_visibility_fingerprint(
        prompt_manifest,
        section_name=OPPORTUNITY_COMMITMENT_SECTION,
        extra={
            "commitment_summary_available": bool(commitment_summary),
            "commitment_summary": commitment_summary,
        },
    )


def _section_visibility_fingerprint(
    prompt_manifest: Mapping[str, Any],
    *,
    section_name: str,
    context_visibility_key: str = "",
    context_prompt_key: str = "",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(prompt_manifest, Mapping) or not prompt_manifest:
        return {}
    section_status = _section_status(prompt_manifest, section_name)
    ledger_entry = _section_ledger_entry(prompt_manifest, section_name)
    metadata = _mapping(prompt_manifest.get("context_profile_metadata"))
    present = bool(section_status) or bool(ledger_entry)
    status = str(
        section_status.get("status")
        or ledger_entry.get("visibility_status")
        or ("absent" if not present else "unknown")
    )
    visible = status in {"included", "full", "summary", "dedicated_projection"}
    if status == "truncated":
        visible = True
    visibility_status = str(ledger_entry.get("visibility_status") or status)
    return _drop_empty(
        {
            "schema_version": SECTION_FINGERPRINT_SCHEMA,
            "section_name": section_name,
            "section_present": present,
            "section_status": status,
            "section_visible": visible,
            "full_section_visible": status in {"included", "full"},
            "block_family": section_status.get("block_family")
            or ledger_entry.get("block_family"),
            "prompt_block_profile": section_status.get("prompt_block_profile")
            or ledger_entry.get("prompt_block_profile"),
            "visibility_status": visibility_status,
            "char_count": _optional_int(
                section_status.get("char_count") or ledger_entry.get("char_count")
            ),
            "token_estimate": _optional_int(ledger_entry.get("token_estimate")),
            "context_visibility": metadata.get(context_visibility_key)
            if context_visibility_key
            else None,
            "context_prompt_key": metadata.get(context_prompt_key)
            if context_prompt_key
            else None,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            **dict(extra or {}),
        }
    )


def empty_problem_opportunity_visibility_aggregate() -> dict[str, Any]:
    """Return an empty postrun aggregate for opportunity-section visibility."""

    return {
        "schema_version": PROBLEM_OPPORTUNITY_VISIBILITY_SCHEMA,
        "report_only": True,
        "decision_features_excluded": True,
        "trace_count": 0,
        "hypothesis_generation_trace_count": 0,
        "section_present_trace_count": 0,
        "hypothesis_generation_section_present_trace_count": 0,
        "section_visible_trace_count": 0,
        "hypothesis_generation_section_visible_trace_count": 0,
        "full_section_visible_trace_count": 0,
        "truncated_section_trace_count": 0,
        "omitted_or_absent_trace_count": 0,
        "section_status_counts": {},
        "visibility_status_counts": {},
        "block_family_counts": {},
        "context_visibility_counts": {},
    }


def empty_opportunity_commitment_visibility_aggregate() -> dict[str, Any]:
    """Return an empty report-only aggregate for commitment visibility."""

    return {
        "schema_version": OPPORTUNITY_COMMITMENT_VISIBILITY_SCHEMA,
        "report_only": True,
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "quality_judgment": False,
        "trace_count": 0,
        "code_trace_count": 0,
        "section_present_trace_count": 0,
        "code_section_present_trace_count": 0,
        "section_visible_trace_count": 0,
        "code_section_visible_trace_count": 0,
        "full_section_visible_trace_count": 0,
        "truncated_section_trace_count": 0,
        "omitted_or_absent_trace_count": 0,
        "commitment_summary_trace_count": 0,
        "section_status_counts": {},
        "visibility_status_counts": {},
        "block_family_counts": {},
        "selected_mechanism_id_counts": {},
        "requirement_id_counts": {},
        "source_summary_digest_counts": {},
        "commitment_digest_counts": {},
    }


def add_problem_opportunity_visibility(
    target: dict[str, Any],
    raw_summary: Any,
    *,
    is_hypothesis_generation: bool,
) -> None:
    """Accumulate one opportunity-section fingerprint into an aggregate."""

    summary = _mapping(raw_summary)
    if not summary:
        return
    target["trace_count"] += 1
    if is_hypothesis_generation:
        target["hypothesis_generation_trace_count"] += 1
    present = summary.get("section_present") is True
    visible = summary.get("section_visible") is True
    full_visible = summary.get("full_section_visible") is True
    status = str(summary.get("section_status") or "unknown")
    visibility_status = str(summary.get("visibility_status") or status)
    if present:
        target["section_present_trace_count"] += 1
        if is_hypothesis_generation:
            target["hypothesis_generation_section_present_trace_count"] += 1
    if visible:
        target["section_visible_trace_count"] += 1
        if is_hypothesis_generation:
            target["hypothesis_generation_section_visible_trace_count"] += 1
    else:
        target["omitted_or_absent_trace_count"] += 1
    if full_visible:
        target["full_section_visible_trace_count"] += 1
    if status == "truncated" or visibility_status == "truncated":
        target["truncated_section_trace_count"] += 1
    _increment_count(target["section_status_counts"], status)
    _increment_count(target["visibility_status_counts"], visibility_status)
    _increment_count(
        target["block_family_counts"],
        str(summary.get("block_family") or "unknown"),
    )
    _increment_count(
        target["context_visibility_counts"],
        str(summary.get("context_visibility") or "unknown"),
    )


def add_opportunity_commitment_visibility(
    target: dict[str, Any],
    raw_summary: Any,
    *,
    is_code_generation: bool,
) -> None:
    """Accumulate one code-phase commitment-section fingerprint."""

    summary = _mapping(raw_summary)
    if not summary:
        return
    target["trace_count"] += 1
    if is_code_generation:
        target["code_trace_count"] += 1
    present = summary.get("section_present") is True
    visible = summary.get("section_visible") is True
    full_visible = summary.get("full_section_visible") is True
    status = str(summary.get("section_status") or "unknown")
    visibility_status = str(summary.get("visibility_status") or status)
    if present:
        target["section_present_trace_count"] += 1
        if is_code_generation:
            target["code_section_present_trace_count"] += 1
    if visible:
        target["section_visible_trace_count"] += 1
        if is_code_generation:
            target["code_section_visible_trace_count"] += 1
    else:
        target["omitted_or_absent_trace_count"] += 1
    if full_visible:
        target["full_section_visible_trace_count"] += 1
    if status == "truncated" or visibility_status == "truncated":
        target["truncated_section_trace_count"] += 1
    _increment_count(target["section_status_counts"], status)
    _increment_count(target["visibility_status_counts"], visibility_status)
    _increment_count(
        target["block_family_counts"],
        str(summary.get("block_family") or "unknown"),
    )
    commitment = _mapping(summary.get("commitment_summary"))
    if not commitment:
        return
    target["commitment_summary_trace_count"] += 1
    for mechanism_id in _string_items(commitment.get("selected_mechanism_ids")):
        _increment_count(target["selected_mechanism_id_counts"], mechanism_id)
    for requirement_id in _string_items(commitment.get("requirement_ids")):
        _increment_count(target["requirement_id_counts"], requirement_id)
    source_digest = str(commitment.get("source_summary_digest") or "").strip()
    if source_digest:
        _increment_count(target["source_summary_digest_counts"], source_digest)
    commitment_digest = str(commitment.get("commitment_digest") or "").strip()
    if commitment_digest:
        _increment_count(target["commitment_digest_counts"], commitment_digest)


def merge_problem_opportunity_visibility(
    target: dict[str, Any],
    source: Mapping[str, Any],
) -> None:
    """Merge one postrun opportunity visibility aggregate into another."""

    if not source:
        return
    for key in (
        "trace_count",
        "hypothesis_generation_trace_count",
        "section_present_trace_count",
        "hypothesis_generation_section_present_trace_count",
        "section_visible_trace_count",
        "hypothesis_generation_section_visible_trace_count",
        "full_section_visible_trace_count",
        "truncated_section_trace_count",
        "omitted_or_absent_trace_count",
    ):
        target[key] += _int(source.get(key))
    for key in (
        "section_status_counts",
        "visibility_status_counts",
        "block_family_counts",
        "context_visibility_counts",
    ):
        _merge_counts(target[key], _mapping(source.get(key)))


def merge_opportunity_commitment_visibility(
    target: dict[str, Any],
    source: Mapping[str, Any],
) -> None:
    """Merge one commitment visibility aggregate into another."""

    if not source:
        return
    for key in (
        "trace_count",
        "code_trace_count",
        "section_present_trace_count",
        "code_section_present_trace_count",
        "section_visible_trace_count",
        "code_section_visible_trace_count",
        "full_section_visible_trace_count",
        "truncated_section_trace_count",
        "omitted_or_absent_trace_count",
        "commitment_summary_trace_count",
    ):
        target[key] += _int(source.get(key))
    for key in (
        "section_status_counts",
        "visibility_status_counts",
        "block_family_counts",
        "selected_mechanism_id_counts",
        "requirement_id_counts",
        "source_summary_digest_counts",
        "commitment_digest_counts",
    ):
        _merge_counts(target[key], _mapping(source.get(key)))


def problem_opportunity_visibility_signature(value: Any) -> dict[str, Any]:
    """Return a stable comparison signature for readiness consistency checks."""

    summary = _mapping(value)
    if not summary:
        return {}
    return {
        "schema_version": str(summary.get("schema_version") or ""),
        "trace_count": _int(summary.get("trace_count")),
        "hypothesis_generation_trace_count": _int(
            summary.get("hypothesis_generation_trace_count")
        ),
        "section_present_trace_count": _int(
            summary.get("section_present_trace_count")
        ),
        "hypothesis_generation_section_present_trace_count": _int(
            summary.get("hypothesis_generation_section_present_trace_count")
        ),
        "section_visible_trace_count": _int(
            summary.get("section_visible_trace_count")
        ),
        "hypothesis_generation_section_visible_trace_count": _int(
            summary.get("hypothesis_generation_section_visible_trace_count")
        ),
        "full_section_visible_trace_count": _int(
            summary.get("full_section_visible_trace_count")
        ),
        "truncated_section_trace_count": _int(
            summary.get("truncated_section_trace_count")
        ),
        "omitted_or_absent_trace_count": _int(
            summary.get("omitted_or_absent_trace_count")
        ),
        "section_status_counts": _int_counts(summary.get("section_status_counts")),
        "visibility_status_counts": _int_counts(
            summary.get("visibility_status_counts")
        ),
        "block_family_counts": _int_counts(summary.get("block_family_counts")),
        "context_visibility_counts": _int_counts(
            summary.get("context_visibility_counts")
        ),
    }


def opportunity_commitment_visibility_signature(value: Any) -> dict[str, Any]:
    """Return a stable comparison signature for commitment visibility."""

    summary = _mapping(value)
    if not summary:
        return {}
    return {
        "schema_version": str(summary.get("schema_version") or ""),
        "trace_count": _int(summary.get("trace_count")),
        "code_trace_count": _int(summary.get("code_trace_count")),
        "section_present_trace_count": _int(
            summary.get("section_present_trace_count")
        ),
        "code_section_present_trace_count": _int(
            summary.get("code_section_present_trace_count")
        ),
        "section_visible_trace_count": _int(
            summary.get("section_visible_trace_count")
        ),
        "code_section_visible_trace_count": _int(
            summary.get("code_section_visible_trace_count")
        ),
        "full_section_visible_trace_count": _int(
            summary.get("full_section_visible_trace_count")
        ),
        "truncated_section_trace_count": _int(
            summary.get("truncated_section_trace_count")
        ),
        "omitted_or_absent_trace_count": _int(
            summary.get("omitted_or_absent_trace_count")
        ),
        "commitment_summary_trace_count": _int(
            summary.get("commitment_summary_trace_count")
        ),
        "section_status_counts": _int_counts(summary.get("section_status_counts")),
        "visibility_status_counts": _int_counts(
            summary.get("visibility_status_counts")
        ),
        "block_family_counts": _int_counts(summary.get("block_family_counts")),
        "selected_mechanism_id_counts": _int_counts(
            summary.get("selected_mechanism_id_counts")
        ),
        "requirement_id_counts": _int_counts(summary.get("requirement_id_counts")),
        "source_summary_digest_counts": _int_counts(
            summary.get("source_summary_digest_counts")
        ),
        "commitment_digest_counts": _int_counts(
            summary.get("commitment_digest_counts")
        ),
    }


def _section_status(
    prompt_manifest: Mapping[str, Any],
    section_name: str,
) -> Mapping[str, Any]:
    statuses = _mapping(prompt_manifest.get("section_statuses"))
    return _mapping(statuses.get(section_name))


def _section_ledger_entry(
    prompt_manifest: Mapping[str, Any],
    section_name: str,
) -> Mapping[str, Any]:
    ledger = _mapping(prompt_manifest.get("visibility_ledger"))
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        return {}
    for entry in entries:
        item = _mapping(entry)
        if item.get("entry_kind") == "section" and item.get("section_name") == section_name:
            return item
    return {}


def _increment_count(target: dict[str, int], key: str, amount: int = 1) -> None:
    target[key] = _int(target.get(key)) + amount


def _merge_counts(target: dict[str, int], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        _increment_count(target, str(key), _int(value))


def _int_counts(value: Any) -> dict[str, int]:
    mapping = _mapping(value)
    return {str(key): _int(raw) for key, raw in sorted(mapping.items())}


def _string_items(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        return ()
    items: list[str] = []
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in items:
            items.append(text)
    return tuple(items)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _drop_empty(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in ("", None, [], {}, ())
    }
