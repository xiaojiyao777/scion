"""Discover host-visible source records for typed edit normalization."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SourceRecord:
    content: str
    provenance: str
    owner: str = ""

    @property
    def digest(self) -> str:
        return source_digest_for_content(self.content)


def source_digest_for_content(content: str) -> str:
    """Return the canonical per-file source digest for typed edit checks."""

    return hashlib.sha256(str(content).encode("utf-8")).hexdigest()


def source_files_from_context(context: Mapping[str, Any] | None) -> dict[str, str]:
    return {
        path: record.content
        for path, record in source_records_from_context(context).items()
    }


def source_records_from_context(
    context: Mapping[str, Any] | None,
) -> dict[str, SourceRecord]:
    if not context:
        return {}
    ledger = context.get("proposal_source_ledger")
    if not isinstance(ledger, Mapping):
        return {}
    # Import lazily because the source-ledger builder uses the canonical digest
    # owned by this module. Every consumer validates the sole durable source
    # owner before treating ledger content as editable source.
    from scion.proposal.context_manager.code_context import (
        _validate_source_ledger,
    )

    ledger = _validate_source_ledger(ledger)
    records: dict[str, SourceRecord] = {}
    for entry in ledger.get("entries") or ():
        if not isinstance(entry, Mapping) or entry.get("visibility") != "full_current":
            continue
        path = _normalize_path(entry.get("path"))
        content = entry.get("content")
        if path and isinstance(content, str):
            _put_source_record(
                records,
                path,
                content,
                str(entry.get("provenance") or "proposal_source_ledger"),
                owner=str(entry.get("owner") or ""),
            )
    return records


def _put_source_record(
    records: dict[str, SourceRecord],
    path: str,
    content: str,
    provenance: str,
    *,
    owner: str = "",
) -> None:
    normalized_path = _normalize_path(path)
    if not normalized_path or content is None:
        return
    records[normalized_path] = SourceRecord(
        content=str(content),
        provenance=provenance,
        owner=owner,
    )


def _normalize_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()
