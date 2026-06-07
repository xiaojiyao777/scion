"""Prompt-cache accounting helpers for campaign summaries."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable, Mapping

logger = logging.getLogger(__name__)


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
    }


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
        }
    for trace_path in sorted(llm_dir.glob("*.json")):
        try:
            payload = json.loads(trace_path.read_text())
        except Exception as exc:  # pragma: no cover - best-effort summary
            logger.debug("failed to read llm trace cache stats %s: %s", trace_path, exc)
            continue
        request_kind = str(payload.get("request_kind") or "")
        audit = payload.get("prompt_cache_audit")
        audit_map = audit if isinstance(audit, Mapping) else {}
        audit_provider = str(audit_map.get("provider") or "")
        usage = payload.get("llm_usage")
        if not isinstance(usage, Mapping):
            provider = audit_provider or _provider_from_model(payload.get("model"))
            pending_key = (request_kind, provider or "unknown")
            pending_no_usage[pending_key] = pending_no_usage.get(pending_key, 0) + 1
            continue
        request_kind = str(
            payload.get("request_kind") or usage.get("request_kind") or ""
        )
        provider = str(usage.get("provider") or audit_provider or "unknown")
        accounting_mode = str(
            usage.get("cache_accounting_mode")
            or audit_map.get("cache_accounting_mode")
            or _default_cache_accounting_mode(provider)
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
            model = str(usage.get("model") or payload.get("model") or "")
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
    }


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
