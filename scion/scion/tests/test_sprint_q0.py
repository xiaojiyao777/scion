"""Tests for Sprint Q0: token usage persist + tech debt cleanup."""
from __future__ import annotations

import os
import pytest

from scion.core.token_usage import TokenUsageRecord, TokenUsageTracker


# ---------------------------------------------------------------------------
# W13: Token usage tracking
# ---------------------------------------------------------------------------

class TestTokenUsageTracker:
    def test_empty(self) -> None:
        t = TokenUsageTracker()
        assert t.records == []
        s = t.summary()
        assert s["total_calls"] == 0
        assert s["cache_hit_rate"] == 0.0

    def test_record_and_summary(self) -> None:
        t = TokenUsageTracker()
        t.record("hypothesis", "claude-sonnet-4-6", prompt_tokens=1000, completion_tokens=200,
                 cache_read_tokens=500, cache_create_tokens=300)
        t.record("patch", "claude-sonnet-4-6", prompt_tokens=2000, completion_tokens=800)
        t.record("classifier", "claude-sonnet-4-6", prompt_tokens=100, completion_tokens=10,
                 timed_out=True)

        assert len(t.records) == 3
        s = t.summary()
        assert s["total_calls"] == 3
        assert s["total_prompt_tokens"] == 3100
        assert s["total_completion_tokens"] == 1010
        assert s["total_cache_read_tokens"] == 500
        assert s["total_timeouts"] == 1
        assert s["by_kind"]["hypothesis"] == 1
        assert s["by_kind"]["patch"] == 1

    def test_cache_hit_rate(self) -> None:
        t = TokenUsageTracker()
        t.record("hypothesis", "m", prompt_tokens=100, cache_read_tokens=400, cache_create_tokens=500)
        s = t.summary()
        assert s["cache_hit_rate"] == 0.4

    def test_record_immutable(self) -> None:
        r = TokenUsageRecord(
            timestamp="2026-04-20", request_kind="test", model_id="m",
            prompt_tokens=100, completion_tokens=50,
        )
        with pytest.raises(AttributeError):
            r.prompt_tokens = 999  # type: ignore[misc]

    def test_error_tracking(self) -> None:
        t = TokenUsageTracker()
        t.record("hypothesis", "m", error="timeout")
        s = t.summary()
        assert s["total_errors"] == 1

    def test_by_model(self) -> None:
        t = TokenUsageTracker()
        t.record("hypothesis", "claude-opus-4-6", prompt_tokens=100)
        t.record("hypothesis", "claude-sonnet-4-6", prompt_tokens=100)
        t.record("classifier", "claude-sonnet-4-6", prompt_tokens=50)
        s = t.summary()
        assert s["by_model"]["claude-opus-4-6"] == 1
        assert s["by_model"]["claude-sonnet-4-6"] == 2


# ---------------------------------------------------------------------------
# W14: Tech debt cleanup
# ---------------------------------------------------------------------------

class TestTechDebtCleanup:
    def test_state_leak_removed(self) -> None:
        state_leak_path = os.path.join(
            os.path.dirname(__file__), os.pardir, "verification", "state_leak.py"
        )
        assert not os.path.exists(state_leak_path), "state_leak.py should be removed"

    def test_splits_weight_deprecated(self) -> None:
        import inspect
        from scion.protocol.evaluation import compute_delta
        src = inspect.getsource(compute_delta)
        assert "DEPRECATED" in src
