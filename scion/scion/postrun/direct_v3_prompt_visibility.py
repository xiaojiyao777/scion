"""Read direct-v3 prompt/source visibility from durable lossless traces."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from scion.proposal.context_manager.code_context import _validate_source_ledger

_DIRECT_V3_HYPOTHESIS_CONTEXT_HEADERS = frozenset(
    {
        "## Direct V3 Static Problem And Champion Context",
        "## Direct V3 Canonical Hypothesis Evidence",
    }
)
_DIRECT_V3_CODE_CONTEXT_HEADER = "## Direct V3 Canonical Code Context"
_DIRECT_V3_CONTEXT_HEADERS = _DIRECT_V3_HYPOTHESIS_CONTEXT_HEADERS | {
    _DIRECT_V3_CODE_CONTEXT_HEADER
}


def load_direct_v3_prompt_context_traces(
    *,
    manifest_path: Path,
    manifest: Mapping[str, Any],
    attempts: list[Any],
) -> dict[str, Any]:
    """Load each referenced trace once and normalize its visibility evidence."""

    campaign_dir = _campaign_dir(manifest_path, manifest)
    if campaign_dir is None:
        return {
            "prompt_manifest_ref_count": 0,
            "prompt_manifest_loaded_count": 0,
            "traces": [],
        }

    prompt_manifest_refs: set[str] = set()
    loaded_trace_paths: set[Path] = set()
    traces: list[dict[str, Any]] = []
    for attempt in attempts:
        if not isinstance(attempt, Mapping):
            continue
        phases = attempt.get("phases")
        if not isinstance(phases, list):
            continue
        for phase in phases:
            if not isinstance(phase, Mapping):
                continue
            fingerprint = _mapping_or_empty(phase.get("prompt_fingerprint"))
            prompt_manifest_ref = str(
                fingerprint.get("prompt_manifest_ref") or ""
            ).strip()
            if prompt_manifest_ref:
                prompt_manifest_refs.add(prompt_manifest_ref)
            trace_ref = str(fingerprint.get("trace_ref") or "").strip()
            if not trace_ref and prompt_manifest_ref:
                trace_ref = prompt_manifest_ref.split("#", 1)[0]
            if not trace_ref:
                continue
            path = direct_v3_trace_path(campaign_dir, trace_ref)
            if path is None or path in loaded_trace_paths:
                continue
            trace_doc = _read_json_object(path)
            if not trace_doc:
                continue
            loaded_trace_paths.add(path)
            normalized = normalize_direct_v3_prompt_context_trace(
                trace_doc,
                fingerprint=fingerprint,
            )
            if normalized:
                traces.append(normalized)

    return {
        "prompt_manifest_ref_count": len(prompt_manifest_refs),
        "prompt_manifest_loaded_count": len(loaded_trace_paths),
        "traces": traces,
    }


def _campaign_dir(
    manifest_path: Path,
    manifest: Mapping[str, Any],
) -> Path | None:
    run_root = manifest_path.parent.parent.parent.resolve()
    raw_campaign_dir = str(manifest.get("campaign_dir") or "").strip()
    if not raw_campaign_dir:
        return None
    campaign_dir = Path(raw_campaign_dir)
    if not campaign_dir.is_absolute():
        campaign_dir = run_root / campaign_dir
    campaign_dir = campaign_dir.resolve()
    return campaign_dir if campaign_dir.is_relative_to(run_root) else None


def direct_v3_trace_path(campaign_dir: Path, trace_ref: str) -> Path | None:
    """Resolve one JSON trace reference without allowing campaign escape."""

    raw_path = trace_ref.split("#", 1)[0].strip()
    relative_path = Path(raw_path)
    if not raw_path or relative_path.is_absolute() or relative_path.suffix != ".json":
        return None
    trace_path = (campaign_dir / relative_path).resolve()
    return trace_path if trace_path.is_relative_to(campaign_dir) else None


def normalize_direct_v3_prompt_context_trace(
    trace_doc: Mapping[str, Any],
    *,
    fingerprint: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify a lossless prompt receipt and project report-only evidence."""

    prompt_manifest = _mapping_or_empty(trace_doc.get("prompt_manifest"))
    if (
        prompt_manifest.get("schema_version") != "api-visible-prompt-manifest.v4"
        or prompt_manifest.get("projection") != "direct_v3_lossless"
        or prompt_manifest.get("rendered_prompt_available") is not True
    ):
        return {}

    call_kinds = (
        str(prompt_manifest.get("call_kind") or ""),
        str(fingerprint.get("request_kind") or ""),
        str(trace_doc.get("request_kind") or ""),
    )
    if not all(call_kinds) or len(set(call_kinds)) != 1:
        return {}
    call_kind = call_kinds[0]
    context_keys = {
        str(key) for key in prompt_manifest.get("context_keys") or [] if str(key)
    }
    rendered = _rendered_context(trace_doc.get("system_blocks"))
    if rendered is None:
        return {}
    rendered_context, rendered_headers = rendered
    if set(rendered_context) != context_keys:
        return {}
    if call_kind == "code":
        if rendered_headers != {_DIRECT_V3_CODE_CONTEXT_HEADER}:
            return {}
    elif call_kind == "hypothesis":
        if rendered_headers != _DIRECT_V3_HYPOTHESIS_CONTEXT_HEADERS:
            return {}
    else:
        return {}
    manifest_context_digest = str(prompt_manifest.get("context_digest") or "")
    fingerprint_context_digest = str(fingerprint.get("context_digest") or "")
    if (
        not manifest_context_digest
        or not fingerprint_context_digest
        or manifest_context_digest != fingerprint_context_digest
    ):
        return {}
    context_digest = manifest_context_digest
    if direct_v3_context_digest(rendered_context) != context_digest:
        return {}

    normalized: dict[str, Any] = {
        "call_kind": call_kind,
        "visibility_ledger_digest": context_digest,
    }
    if call_kind == "code":
        normalized["source_visibility_summary"] = direct_v3_code_source_visibility(
            rendered_context
        )
    elif call_kind == "hypothesis":
        owner_source = rendered_context.get("champion_operators_code")
        owner_source_visible = isinstance(owner_source, str) and bool(
            owner_source.strip()
        )
        normalized["source_visibility_summary"] = {
            "schema_version": "scion.direct_v3_prompt_source_fingerprint.v1",
            "hypothesis_target_source_visibility": {
                "schema_version": ("direct-v3-hypothesis-source-visibility-ledger.v1"),
                "target_source_required": False,
                "visibility_status": (
                    "owner_source_visible_before_target_selection"
                    if owner_source_visible
                    else "not_visible"
                ),
                "owner_source_visible": owner_source_visible,
            },
        }
    return normalized


def _rendered_context(
    system_blocks: Any,
) -> tuple[dict[str, Any], frozenset[str]] | None:
    if not isinstance(system_blocks, list):
        return None
    context: dict[str, Any] = {}
    headers: set[str] = set()
    for block in system_blocks:
        if not isinstance(block, Mapping):
            continue
        text = str(block.get("text") or "")
        header, separator, raw_json = text.partition("\n")
        if header not in _DIRECT_V3_CONTEXT_HEADERS:
            continue
        if not separator:
            return None
        try:
            block_context = json.loads(raw_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(block_context, Mapping):
            return None
        if set(context).intersection(block_context):
            return None
        context.update({str(key): value for key, value in block_context.items()})
        headers.add(header)
    return (context, frozenset(headers)) if headers else None


def direct_v3_context_digest(context: Mapping[str, Any]) -> str:
    """Return the canonical digest used by the direct-v3 prompt manifest."""

    rendered = json.dumps(
        context,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def direct_v3_code_source_visibility(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Derive visibility only from a canonical validated source ledger."""

    try:
        ledger = _validate_source_ledger(context.get("proposal_source_ledger"))
        ledger_valid = True
    except (TypeError, ValueError):
        ledger = {}
        ledger_valid = False
    approved_target = str(ledger.get("approved_target") or "")
    entries = [
        dict(entry)
        for entry in ledger.get("entries") or []
        if isinstance(entry, Mapping)
    ]
    entries_by_path = {
        str(entry.get("path") or ""): entry
        for entry in entries
        if str(entry.get("path") or "")
    }
    views = _mapping_or_empty(ledger.get("views"))

    def visible_path(path: str) -> bool:
        entry = entries_by_path.get(path)
        if entry is None:
            return False
        visibility = str(entry.get("visibility") or "")
        if path == approved_target and visibility == "new_file_placeholder":
            return True
        return visibility == "full_current"

    def view_paths(*names: str) -> set[str]:
        return {
            str(path) for name in names for path in views.get(name) or [] if str(path)
        }

    api_paths = view_paths("api_reference")
    integration_paths = view_paths("required_full", "integration_full")
    algorithm_paths = view_paths("reference", "champion_research")
    protected_paths = (
        {approved_target}
        | set(entries_by_path)
        | api_paths
        | integration_paths
        | algorithm_paths
        | view_paths("branch_current")
    )
    required_paths = protected_paths
    missing_paths = sorted(path for path in required_paths if not visible_path(path))
    ledger_available = (
        ledger_valid
        and bool(approved_target and entries)
        and bool(api_paths)
        and bool(integration_paths)
        and bool(algorithm_paths)
    )
    if not ledger_available:
        missing_paths = ["proposal_source_ledger"]
    target_entry = entries_by_path.get(approved_target, {})
    target_source_status = str(target_entry.get("visibility") or "unknown")
    target_visible = ledger_available and visible_path(approved_target)
    protected_visible = ledger_available and not missing_paths

    return {
        "schema_version": "scion.direct_v3_prompt_source_fingerprint.v1",
        "code_phase_guarantees": {
            "schema_version": "direct-v3-code-source-visibility-guarantees.v1",
            "target_source_visible": target_visible,
            "protected_source_visible": protected_visible,
            "required_integration_source_visible": (
                ledger_available
                and bool(integration_paths)
                and all(visible_path(path) for path in integration_paths)
            ),
            "algorithm_file_read_source_visible": (
                ledger_available
                and bool(algorithm_paths)
                and all(visible_path(path) for path in algorithm_paths)
            ),
            "missing_required_source_paths": missing_paths,
        },
        "code_file_visibility": {
            "schema_version": "direct-v3-code-source-visibility-ledger.v1",
            "target_source_status": target_source_status,
            "target_prompt_visibility_status": (
                "direct_v3_lossless_visible" if target_visible else "not_visible"
            ),
        },
    }


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = [
    "direct_v3_code_source_visibility",
    "direct_v3_context_digest",
    "direct_v3_trace_path",
    "load_direct_v3_prompt_context_traces",
    "normalize_direct_v3_prompt_context_trace",
]
