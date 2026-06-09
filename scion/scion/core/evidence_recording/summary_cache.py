"""Prompt-cache accounting helpers for campaign summaries."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable, Mapping

logger = logging.getLogger(__name__)

_LLM_TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "reasoning_tokens",
    "prompt_tokens_total",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "cache_miss_input_tokens",
    "cache_tokens_total",
)


def _campaign_cache_stats(
    steps: Iterable[Any],
    *,
    campaign_dir: Any,
) -> dict[str, Any]:
    """Return campaign-level prompt-cache statistics.

    Legacy step records may contain coarse cache stats, but agentic LLM calls
    write the authoritative per-call usage to ``llm_traces/*.json``. Prefer the
    trace aggregate when present so campaign summaries reflect actual provider
    cache reads/writes and can surface repeated cache creates for an unchanged
    prompt-cache key.
    """
    step_stats = _step_cache_stats(steps)
    trace_stats = _llm_trace_cache_stats(campaign_dir)
    if trace_stats["calls"] > 0:
        return trace_stats
    return step_stats


def _step_cache_stats(steps: Iterable[Any]) -> dict[str, Any]:
    total_tokens = 0
    cache_read_tokens = 0
    cache_create_tokens = 0
    for step in steps:
        cs = step.cache_stats or {}
        total_tokens += _safe_int(cs.get("total", 0))
        cache_read_tokens += _safe_int(cs.get("cache_read", 0))
        cache_create_tokens += _safe_int(cs.get("cache_create", 0))
    cache_hit_rate = (
        round(cache_read_tokens / total_tokens, 4) if total_tokens > 0 else 0.0
    )
    return {
        "total_tokens": total_tokens,
        "prompt_tokens_total": total_tokens,
        "input_tokens": total_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_miss_tokens": max(0, total_tokens - cache_read_tokens),
        "cache_create_tokens": cache_create_tokens,
        "cache_hit_rate": cache_hit_rate,
        "cache_accounting_modes": {},
        "output_tokens": 0,
        "calls": 0,
        "source": "step_records",
        "by_request_kind_provider": [],
        "repeated_cache_create_groups": [],
        "repeated_cache_key_groups": [],
        "repeated_cache_key_no_read": [],
        "llm_accounting": _empty_llm_accounting(
            source="step_records",
            unavailability_reason=(
                "llm_trace_usage_unavailable; step cache stats do not carry "
                "request_kind, model, provider, output, or reasoning token fields"
            ),
        ),
    }


def _campaign_llm_accounting(campaign_dir: Any) -> dict[str, Any]:
    """Return trace-level LLM usage accounting with explicit availability."""
    return _llm_trace_cache_stats(campaign_dir).get(
        "llm_accounting",
        _empty_llm_accounting(source="llm_traces"),
    )


def _llm_trace_cache_stats(campaign_dir: Any) -> dict[str, Any]:
    trace_dir = getattr(campaign_dir, "joinpath", None)
    if callable(trace_dir):
        llm_dir = campaign_dir.joinpath("llm_traces")
    else:
        llm_dir = Path(campaign_dir) / "llm_traces"
    total_tokens = 0
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_create_tokens = 0
    cache_miss_tokens = 0
    calls = 0
    pending_no_usage: dict[tuple[str, str], int] = {}
    by_request_kind_provider: dict[tuple[str, str], dict[str, Any]] = {}
    accounting_modes: dict[str, int] = {}
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    if not llm_dir.exists():
        llm_accounting = _empty_llm_accounting(
            source="llm_traces",
            unavailability_reason="llm_traces_directory_missing",
        )
        return {
            "total_tokens": 0,
            "prompt_tokens_total": 0,
            "input_tokens": 0,
            "cache_read_tokens": 0,
            "cache_miss_tokens": 0,
            "cache_create_tokens": 0,
            "cache_hit_rate": 0.0,
            "cache_accounting_modes": {},
            "output_tokens": 0,
            "calls": 0,
            "source": "llm_traces",
            "by_request_kind_provider": [],
            "repeated_cache_create_groups": [],
            "repeated_cache_key_groups": [],
            "repeated_cache_key_no_read": [],
            "llm_accounting": llm_accounting,
        }
    trace_paths = sorted(llm_dir.glob("*.json"))
    llm_accounting = _new_llm_accounting(trace_file_count=len(trace_paths))
    for trace_path in trace_paths:
        try:
            payload = json.loads(trace_path.read_text())
        except Exception as exc:  # pragma: no cover - best-effort summary
            logger.debug("failed to read llm trace cache stats %s: %s", trace_path, exc)
            llm_accounting["unreadable_trace_count"] += 1
            continue
        request_kind = str(payload.get("request_kind") or "")
        audit = payload.get("prompt_cache_audit")
        audit_map = audit if isinstance(audit, Mapping) else {}
        audit_provider = str(audit_map.get("provider") or "")
        usage = payload.get("llm_usage")
        if not isinstance(usage, Mapping):
            provider = audit_provider or _provider_from_model(payload.get("model"))
            model = str(payload.get("model") or "")
            _record_llm_trace_identity(
                llm_accounting,
                request_kind=request_kind,
                provider=provider,
                model=model,
                has_usage=False,
            )
            pending_key = (request_kind, provider or "unknown")
            pending_no_usage[pending_key] = pending_no_usage.get(pending_key, 0) + 1
            continue
        request_kind = str(
            payload.get("request_kind") or usage.get("request_kind") or ""
        )
        provider = str(usage.get("provider") or audit_provider or "unknown")
        model = str(usage.get("model") or payload.get("model") or "")
        accounting_mode = str(
            usage.get("cache_accounting_mode")
            or audit_map.get("cache_accounting_mode")
            or _default_cache_accounting_mode(provider)
        )
        _record_llm_trace_identity(
            llm_accounting,
            request_kind=request_kind,
            provider=provider,
            model=model,
            has_usage=True,
        )
        prompt_tokens = _usage_prompt_tokens_total(usage, accounting_mode)
        input_only_tokens = _safe_int(usage.get("input_tokens"))
        cache_create = _safe_int(usage.get("cache_creation_input_tokens"))
        cache_read = _safe_int(usage.get("cache_read_input_tokens"))
        cache_miss = _usage_cache_miss_tokens(
            usage,
            prompt_tokens,
            cache_read,
            accounting_mode,
        )
        _record_llm_token_usage(
            llm_accounting,
            usage=usage,
            prompt_tokens_total=prompt_tokens,
            cache_miss_tokens=cache_miss,
        )
        completion_tokens = _safe_int(usage.get("output_tokens"))
        calls += 1
        accounting_modes[accounting_mode] = accounting_modes.get(accounting_mode, 0) + 1
        total_tokens += prompt_tokens
        input_tokens += input_only_tokens
        output_tokens += completion_tokens
        cache_create_tokens += cache_create
        cache_read_tokens += cache_read
        cache_miss_tokens += cache_miss
        detail_key = (request_kind, provider)
        detail = by_request_kind_provider.setdefault(
            detail_key,
            {
                "request_kind": request_kind,
                "provider": provider,
                "calls": 0,
                "prompt_tokens_total": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_miss_tokens": 0,
                "cache_create_tokens": 0,
                "pending_no_usage_traces": 0,
                "cache_accounting_modes": {},
            },
        )
        detail["calls"] += 1
        detail["prompt_tokens_total"] += prompt_tokens
        detail["input_tokens"] += input_only_tokens
        detail["output_tokens"] += completion_tokens
        detail["cache_read_tokens"] += cache_read
        detail["cache_miss_tokens"] += cache_miss
        detail["cache_create_tokens"] += cache_create
        detail_modes = detail["cache_accounting_modes"]
        detail_modes[accounting_mode] = detail_modes.get(accounting_mode, 0) + 1
        cache_hash = str(audit_map.get("cacheable_system_blocks_hash") or "")
        tool_schema_hash = str(audit_map.get("tool_schema_hash") or "")
        cacheable_chars = _safe_int(audit_map.get("cacheable_system_chars"))
        if cache_hash:
            key = (
                request_kind,
                cache_hash,
                tool_schema_hash,
            )
            group = groups.setdefault(
                key,
                {
                    "request_kind": key[0],
                    "providers": {},
                    "models": {},
                    "cacheable_system_blocks_hash": cache_hash,
                    "tool_schema_hash": tool_schema_hash,
                    "cacheable_system_chars": cacheable_chars,
                    "calls": 0,
                    "cache_create_calls": 0,
                    "cache_read_calls": 0,
                    "cache_miss_calls": 0,
                    "prompt_tokens_total": 0,
                    "cache_create_tokens": 0,
                    "cache_read_tokens": 0,
                    "cache_miss_tokens": 0,
                    "first_trace": trace_path.name,
                    "last_trace": trace_path.name,
                },
            )
            group["calls"] += 1
            group["last_trace"] = trace_path.name
            group["prompt_tokens_total"] += prompt_tokens
            group["providers"][provider] = group["providers"].get(provider, 0) + 1
            if model:
                group["models"][model] = group["models"].get(model, 0) + 1
            if cache_create > 0:
                group["cache_create_calls"] += 1
                group["cache_create_tokens"] += cache_create
            if cache_read > 0:
                group["cache_read_calls"] += 1
                group["cache_read_tokens"] += cache_read
            if cache_miss > 0:
                group["cache_miss_calls"] += 1
                group["cache_miss_tokens"] += cache_miss
    for (request_kind, provider), pending_count in pending_no_usage.items():
        detail = by_request_kind_provider.setdefault(
            (request_kind, provider),
            {
                "request_kind": request_kind,
                "provider": provider,
                "calls": 0,
                "prompt_tokens_total": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_miss_tokens": 0,
                "cache_create_tokens": 0,
                "pending_no_usage_traces": 0,
                "cache_accounting_modes": {},
            },
        )
        detail["pending_no_usage_traces"] += pending_count
    cache_hit_rate = (
        round(cache_read_tokens / total_tokens, 4) if total_tokens > 0 else 0.0
    )
    detail_rows: list[dict[str, Any]] = []
    for detail in by_request_kind_provider.values():
        denominator = _safe_int(detail.get("prompt_tokens_total"))
        detail_rows.append(
            {
                **detail,
                "hit_rate": (
                    round(_safe_int(detail.get("cache_read_tokens")) / denominator, 4)
                    if denominator > 0
                    else 0.0
                ),
            }
        )
    detail_rows.sort(key=lambda item: (str(item["request_kind"]), str(item["provider"])))
    repeated_key_groups = [
        {
            **group,
            "providers": dict(sorted(group["providers"].items())),
            "models": dict(sorted(group["models"].items())),
            "hit_rate": (
                round(group["cache_read_tokens"] / group["prompt_tokens_total"], 4)
                if group["prompt_tokens_total"] > 0
                else 0.0
            ),
            "diagnosis": (
                "same cache key repeated without a read; inspect provider cache "
                "mode/accounting and hidden prefix inputs"
            )
            if group["cache_read_calls"] == 0
            else "same cache key repeated with later provider cache reads",
        }
        for group in groups.values()
        if group["calls"] > 1
    ]
    repeated = [
        {
            **group,
            "providers": dict(sorted(group["providers"].items())),
            "models": dict(sorted(group["models"].items())),
            "diagnosis": (
                "same cache key produced multiple cache writes without a read; "
                "the provider likely has cache warmup/visibility delay, unless "
                "the upstream service treats additional hidden request fields as "
                "part of the cache key"
            )
            if group["cache_read_calls"] == 0
            else (
                "same cache key warmed before later reads; this is expected with "
                "provider-side eventual cache visibility"
            ),
        }
        for group in groups.values()
        if group["cache_create_calls"] > 1
    ]
    repeated_no_read = [
        group for group in repeated_key_groups if group["cache_read_calls"] == 0
    ]
    _finalize_llm_accounting(llm_accounting)
    return {
        "total_tokens": total_tokens,
        "prompt_tokens_total": total_tokens,
        "input_tokens": input_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_miss_tokens": cache_miss_tokens,
        "cache_create_tokens": cache_create_tokens,
        "cache_hit_rate": cache_hit_rate,
        "cache_accounting_modes": accounting_modes,
        "output_tokens": output_tokens,
        "calls": calls,
        "source": "llm_traces",
        "by_request_kind_provider": detail_rows,
        "repeated_cache_create_groups": repeated,
        "repeated_cache_key_groups": repeated_key_groups,
        "repeated_cache_key_no_read": repeated_no_read,
        "llm_accounting": llm_accounting,
    }


def _empty_llm_accounting(
    *,
    source: str,
    unavailability_reason: str = "",
) -> dict[str, Any]:
    accounting = _new_llm_accounting(trace_file_count=0, source=source)
    if unavailability_reason:
        accounting["unavailability_reason"] = unavailability_reason
    _finalize_llm_accounting(accounting)
    return accounting


def _new_llm_accounting(
    *,
    trace_file_count: int,
    source: str = "llm_traces",
) -> dict[str, Any]:
    return {
        "schema_version": "campaign_llm_accounting.v1",
        "source": source,
        "trace_file_count": max(0, int(trace_file_count or 0)),
        "usage_trace_count": 0,
        "no_usage_trace_count": 0,
        "unreadable_trace_count": 0,
        "request_kind_counts": {},
        "provider_counts": {},
        "model_counts": {},
        "unknown_counts": {
            "request_kind": 0,
            "provider": 0,
            "model": 0,
        },
        "token_sums": {field: None for field in _LLM_TOKEN_FIELDS},
        "token_field_availability": {},
        "token_sum_semantics": {
            "input_tokens": "provider-reported input/prompt token field",
            "output_tokens": "provider-reported completion/output token field",
            "total_tokens": (
                "provider total_tokens when present; otherwise "
                "prompt_tokens_total + output_tokens when both are available"
            ),
            "reasoning_tokens": (
                "provider-reported reasoning output tokens; null when unavailable"
            ),
            "prompt_tokens_total": (
                "provider prompt total, with cache-aware derivation matching "
                "cache_stats.prompt_tokens_total"
            ),
            "cache_creation_input_tokens": "provider-reported cache write tokens",
            "cache_read_input_tokens": "provider-reported cache read tokens",
            "cache_miss_input_tokens": (
                "provider-reported or cache-accounting-derived uncached input tokens"
            ),
            "cache_tokens_total": (
                "cache_creation_input_tokens + cache_read_input_tokens for traces "
                "where at least one cache subfield is available"
            ),
        },
        "_token_accumulator": _new_token_accumulator(),
    }


def _new_token_accumulator() -> dict[str, dict[str, int]]:
    return {
        field: {
            "sum": 0,
            "known_usage_traces": 0,
            "missing_usage_traces": 0,
            "null_usage_traces": 0,
            "no_usage_traces": 0,
            "partial_known_usage_traces": 0,
        }
        for field in _LLM_TOKEN_FIELDS
    }


def _record_llm_trace_identity(
    accounting: dict[str, Any],
    *,
    request_kind: str,
    provider: str,
    model: str,
    has_usage: bool,
) -> None:
    if has_usage:
        accounting["usage_trace_count"] += 1
    else:
        accounting["no_usage_trace_count"] += 1
    _increment_identity_count(
        accounting,
        "request_kind",
        _nonempty_label(request_kind),
    )
    _increment_identity_count(accounting, "provider", _nonempty_label(provider))
    _increment_identity_count(accounting, "model", _nonempty_label(model))


def _increment_identity_count(
    accounting: dict[str, Any],
    identity: str,
    value: str,
) -> None:
    label = value if value else "unknown"
    counts_key = f"{identity}_counts"
    counts = accounting[counts_key]
    counts[label] = counts.get(label, 0) + 1
    if label == "unknown":
        accounting["unknown_counts"][identity] += 1


def _record_llm_token_usage(
    accounting: dict[str, Any],
    *,
    usage: Mapping[str, Any],
    prompt_tokens_total: int,
    cache_miss_tokens: int,
) -> None:
    input_known, input_value, input_null = _token_value(usage, ("input_tokens",))
    output_known, output_value, output_null = _token_value(
        usage,
        ("output_tokens", "completion_tokens"),
    )
    prompt_known, prompt_value, prompt_null = _token_value(
        usage,
        ("prompt_tokens_total", "prompt_tokens"),
    )
    if not prompt_known and input_known:
        prompt_known = True
        prompt_value = prompt_tokens_total
    cache_create_known, cache_create_value, cache_create_null = _token_value(
        usage,
        ("cache_creation_input_tokens",),
    )
    cache_read_known, cache_read_value, cache_read_null = _token_value(
        usage,
        ("cache_read_input_tokens", "prompt_cache_hit_tokens"),
    )
    cache_miss_known, cache_miss_value, cache_miss_null = _token_value(
        usage,
        ("cache_miss_input_tokens", "prompt_cache_miss_tokens"),
    )
    if not cache_miss_known and (prompt_known or input_known):
        cache_miss_known = True
        cache_miss_value = cache_miss_tokens
    reasoning_known, reasoning_value, reasoning_null = _token_value(
        usage,
        ("reasoning_output_tokens", "reasoning_tokens"),
    )
    total_known, total_value, total_null = _token_value(
        usage,
        ("total_tokens",),
    )
    if not total_known and prompt_known and output_known:
        total_known = True
        total_value = int(prompt_value or 0) + int(output_value or 0)
    cache_total_known = cache_create_known or cache_read_known
    cache_total_value = int(cache_create_value or 0) + int(cache_read_value or 0)
    cache_total_null = cache_create_null and cache_read_null
    cache_total_partial = int(cache_create_known) + int(cache_read_known) == 1

    _record_token_field(
        accounting,
        "input_tokens",
        known=input_known,
        value=input_value,
        null=input_null,
    )
    _record_token_field(
        accounting,
        "output_tokens",
        known=output_known,
        value=output_value,
        null=output_null,
    )
    _record_token_field(
        accounting,
        "total_tokens",
        known=total_known,
        value=total_value,
        null=total_null,
    )
    _record_token_field(
        accounting,
        "reasoning_tokens",
        known=reasoning_known,
        value=reasoning_value,
        null=reasoning_null,
    )
    _record_token_field(
        accounting,
        "prompt_tokens_total",
        known=prompt_known,
        value=prompt_value,
        null=prompt_null,
    )
    _record_token_field(
        accounting,
        "cache_creation_input_tokens",
        known=cache_create_known,
        value=cache_create_value,
        null=cache_create_null,
    )
    _record_token_field(
        accounting,
        "cache_read_input_tokens",
        known=cache_read_known,
        value=cache_read_value,
        null=cache_read_null,
    )
    _record_token_field(
        accounting,
        "cache_miss_input_tokens",
        known=cache_miss_known,
        value=cache_miss_value,
        null=cache_miss_null,
    )
    _record_token_field(
        accounting,
        "cache_tokens_total",
        known=cache_total_known,
        value=cache_total_value,
        null=cache_total_null,
        partial=cache_total_partial,
    )


def _record_token_field(
    accounting: dict[str, Any],
    field: str,
    *,
    known: bool,
    value: int | None,
    null: bool,
    partial: bool = False,
) -> None:
    accumulator = accounting["_token_accumulator"][field]
    if known:
        accumulator["known_usage_traces"] += 1
        accumulator["sum"] += int(value or 0)
        if partial:
            accumulator["partial_known_usage_traces"] += 1
        return
    if null:
        accumulator["null_usage_traces"] += 1
    else:
        accumulator["missing_usage_traces"] += 1


def _token_value(
    usage: Mapping[str, Any],
    keys: tuple[str, ...],
) -> tuple[bool, int | None, bool]:
    saw_null = False
    for key in keys:
        if key not in usage:
            continue
        value = usage.get(key)
        if value in (None, ""):
            saw_null = True
            continue
        try:
            return True, int(value), False
        except (TypeError, ValueError):
            saw_null = True
    return False, None, saw_null


def _finalize_llm_accounting(accounting: dict[str, Any]) -> None:
    token_accumulator = accounting.pop("_token_accumulator", _new_token_accumulator())
    no_usage_traces = int(accounting.get("no_usage_trace_count") or 0)
    token_sums: dict[str, int | None] = {}
    token_availability: dict[str, dict[str, int | bool]] = {}
    for field in _LLM_TOKEN_FIELDS:
        availability = dict(token_accumulator[field])
        availability["no_usage_traces"] = no_usage_traces
        known_count = int(availability["known_usage_traces"])
        token_sums[field] = availability["sum"] if known_count > 0 else None
        availability["sum_is_null_when_all_values_unavailable"] = known_count == 0
        token_availability[field] = availability
    accounting["token_sums"] = token_sums
    accounting["token_field_availability"] = token_availability
    for key in ("request_kind_counts", "provider_counts", "model_counts"):
        accounting[key] = dict(sorted(accounting[key].items()))


def _nonempty_label(value: Any) -> str:
    return str(value or "").strip() or "unknown"


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _usage_prompt_tokens_total(
    usage: Mapping[str, Any],
    accounting_mode: str,
) -> int:
    explicit_total = _safe_int(usage.get("prompt_tokens_total"))
    if explicit_total:
        return explicit_total
    input_tokens = _safe_int(usage.get("input_tokens"))
    if accounting_mode == "anthropic_explicit_cache_tokens":
        return (
            input_tokens
            + _safe_int(usage.get("cache_creation_input_tokens"))
            + _safe_int(usage.get("cache_read_input_tokens"))
        )
    return input_tokens


def _usage_cache_miss_tokens(
    usage: Mapping[str, Any],
    prompt_tokens_total: int,
    cache_read: int,
    accounting_mode: str,
) -> int:
    explicit_miss = _safe_int(usage.get("cache_miss_input_tokens"))
    if explicit_miss:
        return explicit_miss
    if accounting_mode == "anthropic_explicit_cache_tokens":
        return _safe_int(usage.get("input_tokens"))
    prompt_cache_miss = _safe_int(usage.get("prompt_cache_miss_tokens"))
    if prompt_cache_miss:
        return prompt_cache_miss
    return max(0, prompt_tokens_total - cache_read)


def _provider_from_model(model: Any) -> str:
    model_text = str(model or "").lower()
    if "claude" in model_text:
        return "anthropic"
    if model_text:
        return "openai_compatible"
    return "unknown"


def _default_cache_accounting_mode(provider: str) -> str:
    if provider == "anthropic":
        return "anthropic_explicit_cache_tokens"
    if provider == "openai_compatible":
        return "provider_prompt_tokens_include_cache_read"
    return "legacy_input_tokens"
