"""Prompt/response tracing helpers for the proposal engine."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, Mapping

from scion.proposal.llm.config import _is_openai_model
from scion.proposal.session_trace_index import (
    record_trace_finish,
    record_trace_start,
    trace_context_from_prompt_context,
)

_SECTION_HEADING = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


class _TraceWriter:
    """Persist prompt/response artifacts for experiment auditability."""

    def __init__(self, trace_dir: str | None) -> None:
        self._trace_dir = trace_dir

    def write_start(
        self,
        *,
        request_kind: str,
        model: str,
        tool: Dict[str, Any],
        prompt: str,
        system_blocks: "list[dict]",
        context: Dict[str, Any],
        request_policy: Dict[str, Any] | None = None,
    ) -> str | None:
        if not self._trace_dir:
            return None
        os.makedirs(self._trace_dir, exist_ok=True)
        digest = _prompt_hash(system_blocks, prompt)
        created_at = datetime.now().isoformat()
        trace_id = (
            f"{datetime.now().strftime('%Y%m%dT%H%M%S%f')}_"
            f"{request_kind}_{digest[:10]}_{uuid.uuid4().hex[:8]}"
        )
        path = os.path.join(self._trace_dir, f"{trace_id}.json")
        trace_context = trace_context_from_prompt_context(context)
        prompt_manifest_context = (
            context.get("_scion_prompt_manifest")
            if isinstance(context, Mapping)
            else {}
        )
        if not isinstance(prompt_manifest_context, Mapping):
            prompt_manifest_context = {}
        payload = {
            "trace_id": trace_id,
            "request_kind": request_kind,
            "model": model,
            "tool_name": tool.get("name"),
            "prompt_hash": digest,
            "prompt_visibility_ledger": _prompt_visibility_ledger(
                system_blocks=system_blocks,
                user_prompt=prompt,
                prompt_manifest=prompt_manifest_context,
            ),
            "prompt_cache_audit": _prompt_cache_audit(
                model=model,
                system_blocks=system_blocks,
                user_prompt=prompt,
                tool_schema=tool.get("input_schema")
                or tool.get("function", {}).get("parameters"),
            ),
            "created_at": created_at,
            "branch_id": context.get("branch_id"),
            "champion_version": context.get("champion_version"),
            "system_blocks": system_blocks,
            "user_prompt": prompt,
            "tool_schema": tool.get("input_schema")
            or tool.get("function", {}).get("parameters"),
            "ok": None,
        }
        if trace_context.get("session_id"):
            payload["agentic_session"] = trace_context
        if prompt_manifest_context:
            payload["prompt_manifest"] = dict(prompt_manifest_context)
        if request_policy:
            payload["request_policy"] = request_policy
        _write_json(path, payload)
        try:
            record_trace_start(
                trace_dir=self._trace_dir,
                trace_id=trace_id,
                trace_path=path,
                request_kind=request_kind,
                model=model,
                prompt_hash=digest,
                context=context,
                created_at=created_at,
            )
        except Exception:
            pass
        return path

    def write_finish(
        self,
        path: str | None,
        *,
        ok: bool,
        response: Dict[str, Any] | None = None,
        error: str | None = None,
        llm_usage: Dict[str, Any] | None = None,
        llm_retry_events: list[dict[str, Any]] | None = None,
    ) -> None:
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            payload = {}
        finished_at = datetime.now().isoformat()
        payload.update(
            {
                "finished_at": finished_at,
                "ok": ok,
            }
        )
        if response is not None:
            payload["response"] = response
        if error is not None:
            payload["error"] = error
        if llm_usage is not None:
            payload["llm_usage"] = llm_usage
        if llm_retry_events:
            payload["llm_retry_events"] = llm_retry_events
            payload["llm_retry_summary"] = _retry_summary(llm_retry_events)
        _write_json(path, payload)
        agentic_context = payload.get("agentic_session")
        if isinstance(agentic_context, Mapping):
            try:
                record_trace_finish(
                    trace_dir=self._trace_dir,
                    trace_id=str(payload.get("trace_id") or ""),
                    context={
                        **dict(agentic_context),
                        "request_kind": payload.get("request_kind"),
                    },
                    ok=ok,
                    finished_at=finished_at,
                    error=error,
                )
            except Exception:
                pass


def _prompt_hash(system_blocks: "list[dict]", prompt: str) -> str:
    blob = json.dumps(
        {"system_blocks": system_blocks, "user_prompt": prompt},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _prompt_visibility_ledger(
    *,
    system_blocks: "list[dict]",
    user_prompt: str,
    prompt_manifest: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    entries: list[dict[str, Any]] = []
    seen_names: dict[str, int] = {}
    for index, block in enumerate(system_blocks or [], start=1):
        text = block.get("text", "") if isinstance(block, Mapping) else str(block)
        entries.extend(
            _visibility_entries_from_text(
                text,
                prompt_part="system",
                block_index=index,
                seen_names=seen_names,
            )
        )
    entries.extend(
        _visibility_entries_from_text(
            user_prompt or "",
            prompt_part="user",
            block_index=None,
            seen_names=seen_names,
        )
    )
    status_counts = {
        "full": 0,
        "dedicated_projection": 0,
        "summary": 0,
        "truncated": 0,
        "omitted": 0,
    }
    for entry in entries:
        status_counts[str(entry.get("visibility_status") or "omitted")] += 1
    ledger: Dict[str, Any] = {
        "schema_version": "prompt-visibility-ledger.v1",
        "ledger_scope": "provider_visible_prompt_sections_only",
        "semantic_note": (
            "Trace entries are reconstructed from provider-visible prompt "
            "sections only. Manifest visibility_ledger is the source of truth "
            "for full/summary/dedicated_projection/omitted/truncated semantics."
        ),
        "status_values": list(status_counts),
        "entry_count": len(entries),
        "status_counts": status_counts,
        "entries": entries,
    }
    if isinstance(prompt_manifest, Mapping) and prompt_manifest:
        ledger["manifest_source_of_truth"] = {
            "artifact_ref": prompt_manifest.get("artifact_ref"),
            "visibility_ledger_ref": prompt_manifest.get("visibility_ledger_ref"),
            "visibility_ledger_digest": prompt_manifest.get(
                "visibility_ledger_digest"
            ),
            "prompt_hash": prompt_manifest.get("prompt_hash"),
            "ledger_field": "prompt_manifest.visibility_ledger",
        }
        ledger["manifest_status_values"] = [
            "full",
            "summary",
            "dedicated_projection",
            "omitted",
            "truncated",
        ]
    return ledger


def _visibility_entries_from_text(
    text: str,
    *,
    prompt_part: str,
    block_index: int | None,
    seen_names: dict[str, int],
) -> list[dict[str, Any]]:
    if not text:
        return []
    matches = list(_SECTION_HEADING.finditer(text))
    chunks: list[tuple[str, str]] = []
    if not matches:
        label = (
            f"system_{block_index}_preamble"
            if block_index is not None
            else "user_preamble"
        )
        chunks.append((label, text))
    else:
        if matches[0].start() > 0 and text[: matches[0].start()].strip():
            label = (
                f"system_{block_index}_preamble"
                if block_index is not None
                else "user_preamble"
            )
            chunks.append((label, text[: matches[0].start()]))
        for offset, match in enumerate(matches):
            start = match.start()
            end = matches[offset + 1].start() if offset + 1 < len(matches) else len(text)
            chunks.append((match.group(1), text[start:end]))
    entries: list[dict[str, Any]] = []
    for heading, chunk in chunks:
        if not chunk:
            continue
        base_name = _section_name(heading)
        count = seen_names.get(base_name, 0) + 1
        seen_names[base_name] = count
        name = base_name if count == 1 else f"{base_name}_{count}"
        chars = len(chunk)
        status = (
            "omitted"
            if _text_has_marker(chunk, "omitted")
            else "truncated"
            if _text_has_marker(chunk, "truncated")
            else "full"
        )
        entries.append(
            {
                "entry_kind": "section",
                "section_name": name,
                "source": "provider_prompt_section",
                "source_ref": f"section:{name}",
                "visibility_status": status,
                "char_count": chars,
                "token_estimate": _token_estimate(chars),
                "digest": _short_hash(chunk),
                "ref": f"section:{name}",
                "projected_to_section": name,
                "projection_ref": f"section:{name}",
                "prompt_part": prompt_part,
                "block_index": block_index,
            }
        )
    return entries


def _prompt_cache_audit(
    *,
    model: str,
    system_blocks: "list[dict]",
    user_prompt: str,
    tool_schema: Any,
) -> Dict[str, Any]:
    is_openai_compatible = _is_openai_model(str(model or ""))
    provider = "openai_compatible" if is_openai_compatible else "anthropic"
    cache_mode = (
        "automatic_prefix_cache_attempted"
        if is_openai_compatible
        else "explicit_cache_control"
    )
    schema_blob = json.dumps(tool_schema or {}, sort_keys=True, default=str)
    block_records: list[dict[str, Any]] = []
    cacheable_chars = 0
    for index, block in enumerate(system_blocks or [], start=1):
        text = block.get("text", "") if isinstance(block, Mapping) else str(block)
        cache_control = (
            dict(block.get("cache_control") or {})
            if isinstance(block, Mapping)
            else {}
        )
        cacheable = bool(cache_control)
        if cacheable:
            cacheable_chars += len(text)
        block_records.append(
            {
                "block_index": index,
                "chars": len(text),
                "hash": _short_hash(text),
                "cacheable": cacheable,
                "cache_control": cache_control,
                "cache_control_forwarded_to_provider": (
                    cacheable and not is_openai_compatible
                ),
            }
        )
    cacheable_blocks = [record for record in block_records if record["cacheable"]]
    return {
        "provider": provider,
        "cache_mode": cache_mode,
        "cache_accounting_mode": (
            "provider_prompt_tokens_include_cache_read"
            if is_openai_compatible
            else "anthropic_explicit_cache_tokens"
        ),
        "system_block_count": len(block_records),
        "cache_control_block_count": len(cacheable_blocks),
        "cache_control_forwarded_to_provider": (
            bool(cacheable_blocks) and not is_openai_compatible
        ),
        "cacheable_system_chars": cacheable_chars,
        "system_blocks": block_records,
        "cacheable_system_blocks_hash": _short_hash(
            json.dumps(cacheable_blocks, sort_keys=True, default=str)
        ),
        "system_blocks_hash": _short_hash(
            json.dumps(block_records, sort_keys=True, default=str)
        ),
        "tool_schema_chars": len(schema_blob),
        "tool_schema_hash": _short_hash(schema_blob),
        "user_prompt_chars": len(user_prompt or ""),
        "user_prompt_hash": _short_hash(user_prompt or ""),
        "cache_prefix_order": (
            "messages[user_prefix(system text) + user_prompt] + tools"
            if is_openai_compatible
            else "tools -> system -> messages"
        ),
        "cache_strategy_note": (
            "OpenAI-compatible requests do not forward Anthropic cache_control "
            "blocks; provider cache stats, when present, reflect automatic prefix "
            "cache behavior over the provider-visible prompt."
            if is_openai_compatible
            else (
                "Anthropic prompt caching matches the stable prefix through explicit "
                "cache_control breakpoints; dynamic user prompt content is outside "
                "the cacheable system blocks."
            )
        ),
    }


def _short_hash(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]


def _section_name(heading: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(heading).strip().lower()).strip("_")
    return cleaned or "unnamed_section"


def _token_estimate(chars: int) -> int:
    return max(0, (int(chars or 0) + 3) // 4)


def _text_has_marker(text: str, marker: str) -> bool:
    lowered = text.lower()
    if marker == "truncated":
        return bool(
            "<truncated" in lowered
            or "truncated agentic context" in lowered
            or "truncated for compact" in lowered
        )
    if marker == "omitted":
        return "<omitted" in lowered or "... <omitted" in lowered
    return marker.lower() in lowered


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)


def _retry_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    categories: dict[str, int] = {}
    recovered = 0
    for event in events:
        category = str(event.get("error_category") or "unknown")
        categories[category] = categories.get(category, 0) + 1
        if event.get("recovered_success") is True:
            recovered += 1
    return {
        "event_count": len(events),
        "recovered_event_count": recovered,
        "error_categories": categories,
        "recovered_success": bool(events and recovered == len(events)),
    }


def _client_request_policy(
    client: Any,
    *,
    request_kind: str,
    tool: Dict[str, Any],
) -> Dict[str, Any] | None:
    resolver = getattr(client, "resolve_request_policy", None)
    if resolver is None:
        return None
    try:
        policy = resolver(request_kind=request_kind, tool=tool)
    except Exception:
        return None
    return dict(policy) if isinstance(policy, Mapping) else None
