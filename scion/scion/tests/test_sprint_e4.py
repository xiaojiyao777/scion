"""Sprint E4 tests: T22, T27, T28, T29."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from scion.proposal.llm_client import (
    LLMClient,
    LLMFormatError,
    LLMRateLimitError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
)
from scion.runtime.subprocess_runner import (
    LocalSubprocessRunner,
    MAX_INLINE_OUTPUT_BYTES,
    resolve_offloaded,
    _OFFLOAD_PREFIX,
)
from scion.core.campaign import CircuitBreaker, MAX_CONSECUTIVE_LLM_FAILURES


# ---------------------------------------------------------------------------
# T22: LLM Client Graded Retry
# ---------------------------------------------------------------------------

class TestGradedRetry:
    """T22: priority parameter controls retry vs fail-fast on 429."""

    def _client(self, max_retries: int = 2) -> LLMClient:
        return LLMClient(max_retries=max_retries)

    # -- call_with_tool tests --

    def test_foreground_retries_on_429(self):
        """Foreground priority: 429 sleeps and retries (does not consume retry budget)."""
        client = self._client()
        good_result = {"hypothesis": "test"}
        tool = {"name": "test_tool", "input_schema": {"required": []}}

        call_count = 0

        def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise LLMRateLimitError("429", retry_after=0.001)
            resp = MagicMock()
            resp.stop_reason = "tool_use"
            block = MagicMock()
            block.type = "tool_use"
            block.name = "test_tool"
            block.input = good_result
            resp.content = [block]
            resp.usage = None
            return resp

        with patch.object(client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = fake_create
            mock_get.return_value = mock_client
            with patch("scion.proposal.llm_client.time.sleep"):
                result = client.call_with_tool("prompt", tool, priority="foreground")
        assert result == good_result
        assert call_count == 2

    def test_background_fails_fast_on_429(self):
        """Background priority: 429 raises immediately without retry."""
        client = self._client()
        tool = {"name": "test_tool", "input_schema": {"required": []}}

        def fake_create(**kwargs):
            raise LLMRateLimitError("429", retry_after=60.0)

        with patch.object(client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = fake_create
            mock_get.return_value = mock_client
            with patch("scion.proposal.llm_client.time.sleep") as mock_sleep:
                with pytest.raises(LLMRateLimitError):
                    client.call_with_tool("prompt", tool, priority="background")
                # Should not sleep for retry_after duration
                mock_sleep.assert_not_called()

    def test_default_priority_is_foreground(self):
        """Default priority should be 'foreground' (backward compatible)."""
        import inspect
        sig = inspect.signature(LLMClient.call_with_tool)
        assert sig.parameters["priority"].default == "foreground"

        sig2 = inspect.signature(LLMClient.call)
        assert sig2.parameters["priority"].default == "foreground"

    def test_background_fails_fast_on_generic_429_exception(self):
        """Background priority: generic exception with 429 in message fails fast."""
        client = self._client()
        tool = {"name": "test_tool", "input_schema": {"required": []}}

        def fake_create(**kwargs):
            raise Exception("HTTP 429 rate_limit exceeded")

        with patch.object(client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = fake_create
            mock_get.return_value = mock_client
            with patch("scion.proposal.llm_client.time.sleep"):
                with pytest.raises(LLMRateLimitError):
                    client.call_with_tool("prompt", tool, priority="background")

    def test_foreground_retries_on_generic_429(self):
        """Foreground priority: generic 429 exception retries."""
        client = self._client(max_retries=1)
        tool = {"name": "test_tool", "input_schema": {"required": []}}

        call_count = 0

        def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("HTTP 429 rate_limit")
            resp = MagicMock()
            resp.stop_reason = "tool_use"
            block = MagicMock()
            block.type = "tool_use"
            block.name = "test_tool"
            block.input = {"key": "val"}
            resp.content = [block]
            resp.usage = None
            return resp

        with patch.object(client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = fake_create
            mock_get.return_value = mock_client
            with patch("scion.proposal.llm_client.time.sleep"):
                result = client.call_with_tool("prompt", tool, priority="foreground")
        assert result == {"key": "val"}


# ---------------------------------------------------------------------------
# T27: Max-tokens Truncation Recovery
# ---------------------------------------------------------------------------

class TestTruncationRecovery:
    """T27: truncated responses trigger retry with higher max_tokens."""

    def _make_truncated_response(self, stop_reason: str = "max_tokens"):
        resp = MagicMock()
        resp.stop_reason = stop_reason
        resp.content = []  # no tool_use block — forces LLMFormatError after truncation check
        resp.usage = None
        return resp

    def _make_good_response(self, tool_name: str, result: dict):
        resp = MagicMock()
        resp.stop_reason = "tool_use"
        block = MagicMock()
        block.type = "tool_use"
        block.name = tool_name
        block.input = result
        resp.content = [block]
        resp.usage = None
        return resp

    def test_truncation_triggers_retry_with_higher_tokens(self):
        """On max_tokens stop_reason, retry with doubled max_tokens."""
        client = LLMClient(max_tokens=4096)
        tool = {"name": "write", "input_schema": {"required": []}}
        good = self._make_good_response("write", {"code": "x=1"})

        max_tokens_seen = []
        call_count = 0

        def fake_create(**kwargs):
            nonlocal call_count
            max_tokens_seen.append(kwargs["max_tokens"])
            call_count += 1
            if call_count == 1:
                return self._make_truncated_response("max_tokens")
            return good

        with patch.object(client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = fake_create
            mock_get.return_value = mock_client
            with patch("scion.proposal.llm_client.time.sleep"):
                result = client.call_with_tool("prompt", tool)

        assert result == {"code": "x=1"}
        assert call_count == 2
        assert max_tokens_seen[0] == 4096
        assert max_tokens_seen[1] == 8192  # doubled

    def test_truncation_max_retries_respected(self):
        """After MAX_TRUNCATION_RETRIES truncations, returns partial (raises format error)."""
        from scion.proposal.llm_client import MAX_TRUNCATION_RETRIES
        client = LLMClient(max_tokens=4096, max_retries=0)
        tool = {"name": "write", "input_schema": {"required": []}}

        def fake_create(**kwargs):
            return self._make_truncated_response("max_tokens")

        with patch.object(client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = fake_create
            mock_get.return_value = mock_client
            with patch("scion.proposal.llm_client.time.sleep"):
                with pytest.raises(LLMRetryExhaustedError):
                    client.call_with_tool("prompt", tool)

    def test_normal_response_no_truncation_logic(self):
        """Non-truncated response passes through normally."""
        client = LLMClient(max_tokens=4096)
        tool = {"name": "write", "input_schema": {"required": []}}
        good = self._make_good_response("write", {"code": "y=2"})

        call_count = 0

        def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            return good

        with patch.object(client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = fake_create
            mock_get.return_value = mock_client
            result = client.call_with_tool("prompt", tool)

        assert result == {"code": "y=2"}
        assert call_count == 1

    def test_truncation_doubles_up_to_cap(self):
        """max_tokens should not exceed MAX_MAX_TOKENS when doubling."""
        from scion.proposal.llm_client import MAX_MAX_TOKENS
        client = LLMClient(max_tokens=MAX_MAX_TOKENS - 100, max_retries=0)
        tool = {"name": "write", "input_schema": {"required": []}}
        good = self._make_good_response("write", {"code": "z=3"})

        max_tokens_seen = []
        call_count = 0

        def fake_create(**kwargs):
            nonlocal call_count
            max_tokens_seen.append(kwargs["max_tokens"])
            call_count += 1
            if call_count == 1:
                return self._make_truncated_response("max_tokens")
            return good

        with patch.object(client, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = fake_create
            mock_get.return_value = mock_client
            result = client.call_with_tool("prompt", tool)

        assert result == {"code": "z=3"}
        assert max_tokens_seen[1] == MAX_MAX_TOKENS  # capped


# ---------------------------------------------------------------------------
# T28: Tool Result Offload to Disk
# ---------------------------------------------------------------------------

class TestOutputOffload:
    """T28: large subprocess outputs are offloaded to disk."""

    def test_small_output_stays_inline(self, tmp_path):
        runner = LocalSubprocessRunner()
        small = "x" * 100
        result = runner._maybe_offload(small, str(tmp_path), "run1")
        assert result == small
        # No artifacts dir created
        assert not (tmp_path / "artifacts").exists()

    def test_large_output_offloaded(self, tmp_path):
        runner = LocalSubprocessRunner()
        large = "y" * (MAX_INLINE_OUTPUT_BYTES + 1)
        result = runner._maybe_offload(large, str(tmp_path), "run2")
        assert result.startswith(_OFFLOAD_PREFIX)
        path = result[len(_OFFLOAD_PREFIX):]
        assert os.path.exists(path)
        assert Path(path).read_text() == large

    def test_offloaded_ref_readable(self, tmp_path):
        runner = LocalSubprocessRunner()
        large = "z" * (MAX_INLINE_OUTPUT_BYTES + 100)
        ref = runner._maybe_offload(large, str(tmp_path), "run3")
        assert ref.startswith(_OFFLOAD_PREFIX)
        # resolve_offloaded should give back original content
        recovered = resolve_offloaded(ref)
        assert recovered == large

    def test_resolve_offloaded_passthrough_for_inline(self):
        """resolve_offloaded should return inline content unchanged."""
        inline = "small content"
        assert resolve_offloaded(inline) == inline

    def test_artifact_dir_created(self, tmp_path):
        runner = LocalSubprocessRunner()
        large = "w" * (MAX_INLINE_OUTPUT_BYTES + 1)
        runner._maybe_offload(large, str(tmp_path), "run4")
        assert (tmp_path / "artifacts").is_dir()

    def test_offload_at_exact_boundary(self, tmp_path):
        runner = LocalSubprocessRunner()
        # Exactly at threshold — should stay inline
        at_boundary = "a" * MAX_INLINE_OUTPUT_BYTES
        result = runner._maybe_offload(at_boundary, str(tmp_path), "boundary")
        assert result == at_boundary  # inline

        # One byte over — should offload
        over_boundary = "a" * (MAX_INLINE_OUTPUT_BYTES + 1)
        result2 = runner._maybe_offload(over_boundary, str(tmp_path), "over_boundary")
        assert result2.startswith(_OFFLOAD_PREFIX)


# ---------------------------------------------------------------------------
# T29: Circuit Breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    """T29: CircuitBreaker trips after N consecutive failures."""

    def test_circuit_breaker_trips_after_threshold(self):
        cb = CircuitBreaker(threshold=3)
        assert not cb.is_tripped
        cb.record_failure("err1")
        assert not cb.is_tripped
        cb.record_failure("err2")
        assert not cb.is_tripped
        cb.record_failure("err3")
        assert cb.is_tripped

    def test_circuit_breaker_resets_on_success(self):
        cb = CircuitBreaker(threshold=3)
        cb.record_failure("err1")
        cb.record_failure("err2")
        assert not cb.is_tripped
        cb.record_success()
        # Counter reset — need 3 more failures to trip
        cb.record_failure("err3")
        cb.record_failure("err4")
        assert not cb.is_tripped
        cb.record_failure("err5")
        assert cb.is_tripped

    def test_circuit_breaker_default_threshold(self):
        cb = CircuitBreaker()
        assert cb._threshold == MAX_CONSECUTIVE_LLM_FAILURES

    def test_record_failure_returns_trip_status(self):
        cb = CircuitBreaker(threshold=2)
        assert cb.record_failure("e1") is False
        assert cb.record_failure("e2") is True

    def test_last_failure_detail_stored(self):
        cb = CircuitBreaker(threshold=3)
        cb.record_failure("first error")
        cb.record_failure("last error")
        assert cb.last_failure_detail == "last error"


class TestCampaignCircuitBreaker:
    """T29: Campaign stops when circuit breaker trips."""

    def _make_campaign(self, llm_client):
        """Create a minimal CampaignManager with mock dependencies."""
        from scion.core.campaign import CampaignManager
        from scion.core.models import ChampionState
        from scion.config.problem import (
            ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace
        )
        import tempfile

        tmpdir = tempfile.mkdtemp()
        spec = ProblemSpec(
            name="test",
            root_dir=tmpdir,
            operator_categories=["local_search"],
            search_space=SearchSpace(
                editable=["operators/*.py"],
                frozen=["solver.py"],
                import_whitelist=[],
            ),
        )
        protocol = ProtocolConfig()
        split = SplitManifest(screening=["c1"], validation=["c2"], frozen=["c3"])
        seed_ledger = SeedLedgerConfig(screening=[1], validation=[2], frozen=[3])
        champion = ChampionState(
            version=0,
            operator_pool={},
            solver_config_hash="abc",
            code_snapshot_path=tmpdir,
            code_snapshot_hash="def",
        )
        campaign = CampaignManager(
            problem_spec=spec,
            protocol_config=protocol,
            split_manifest=split,
            seed_ledger=seed_ledger,
            llm_client=llm_client,
            champion=champion,
            campaign_dir=tmpdir,
        )
        return campaign

    def test_campaign_stops_on_circuit_breaker(self):
        """Mock LLM to fail 3x, verify campaign stops gracefully."""
        from scion.proposal.mock_client import MockLLMClient

        # LLM always raises LLMRetryExhaustedError
        failing_client = MockLLMClient(mode="exhausted")
        campaign = self._make_campaign(failing_client)

        # Run with enough rounds to trigger circuit breaker
        campaign.run(max_rounds=20)

        assert campaign._circuit_breaker.is_tripped

    def test_circuit_breaker_in_campaign_state(self):
        """CircuitBreaker is initialized on CampaignManager."""
        from scion.proposal.mock_client import MockLLMClient
        client = MockLLMClient(mode="success")
        campaign = self._make_campaign(client)
        assert hasattr(campaign, "_circuit_breaker")
        assert isinstance(campaign._circuit_breaker, CircuitBreaker)

    def test_campaign_summary_has_stopped_reason_on_trip(self):
        """Campaign summary includes stopped_reason=circuit_breaker when tripped."""
        from scion.proposal.mock_client import MockLLMClient
        import json as _json

        failing_client = MockLLMClient(mode="exhausted")
        campaign = self._make_campaign(failing_client)
        campaign.run(max_rounds=20)

        summary_path = Path(campaign._campaign_dir) / "campaign_summary.json"
        if summary_path.exists():
            summary = _json.loads(summary_path.read_text())
            assert summary.get("stopped_reason") == "circuit_breaker"
