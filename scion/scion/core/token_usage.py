"""Token usage tracking — per-call structured records for cost and drift analysis (W13).

Records are accumulated in-memory during a campaign and can be persisted
to lineage (experiment_events) or exported for analysis.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass(frozen=True)
class TokenUsageRecord:
    timestamp: str
    request_kind: str  # "hypothesis" | "patch" | "fix" | "classifier" | "weight_opt"
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    cache_read_tokens: int = 0
    cache_create_tokens: int = 0
    retry_count: int = 0
    timed_out: bool = False
    error: Optional[str] = None


class TokenUsageTracker:
    """Accumulates per-call token usage for a campaign."""

    def __init__(self) -> None:
        self._records: List[TokenUsageRecord] = []

    def record(
        self,
        request_kind: str,
        model_id: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_create_tokens: int = 0,
        retry_count: int = 0,
        timed_out: bool = False,
        error: Optional[str] = None,
    ) -> None:
        self._records.append(TokenUsageRecord(
            timestamp=datetime.now().isoformat(),
            request_kind=request_kind,
            model_id=model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_create_tokens=cache_create_tokens,
            retry_count=retry_count,
            timed_out=timed_out,
            error=error,
        ))

    @property
    def records(self) -> List[TokenUsageRecord]:
        return list(self._records)

    def summary(self) -> Dict[str, int | float]:
        total_prompt = sum(r.prompt_tokens for r in self._records)
        total_completion = sum(r.completion_tokens for r in self._records)
        total_cache_read = sum(r.cache_read_tokens for r in self._records)
        total_cache_create = sum(r.cache_create_tokens for r in self._records)
        total_calls = len(self._records)
        total_retries = sum(r.retry_count for r in self._records)
        total_timeouts = sum(1 for r in self._records if r.timed_out)
        total_errors = sum(1 for r in self._records if r.error)
        total_input = total_prompt + total_cache_read + total_cache_create
        cache_hit_rate = total_cache_read / total_input if total_input > 0 else 0.0

        by_kind: Dict[str, int] = {}
        by_model: Dict[str, int] = {}
        for r in self._records:
            by_kind[r.request_kind] = by_kind.get(r.request_kind, 0) + 1
            by_model[r.model_id] = by_model.get(r.model_id, 0) + 1

        return {
            "total_calls": total_calls,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_cache_read_tokens": total_cache_read,
            "total_cache_create_tokens": total_cache_create,
            "cache_hit_rate": round(cache_hit_rate, 3),
            "total_retries": total_retries,
            "total_timeouts": total_timeouts,
            "total_errors": total_errors,
            "by_kind": by_kind,
            "by_model": by_model,
        }
