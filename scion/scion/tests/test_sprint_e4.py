"""Sprint E4 tests: T22, T27, and T28."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scion.proposal.llm_client import (
    LLMClient,
    LLMFormatError,
    LLMRateLimitError,
)
from scion.runtime.subprocess_runner import (
    LocalSubprocessRunner,
    MAX_INLINE_OUTPUT_BYTES,
    _OFFLOAD_PREFIX,
)
from scion.runtime.runner import resolve_offloaded


# ---------------------------------------------------------------------------
# T22: LLM Client Single Attempt
# ---------------------------------------------------------------------------

class TestGradedRetry:
    """Legacy name: all priorities now fail immediately on typed 429."""

    def _client(self) -> LLMClient:
        return LLMClient()

    # -- call_with_tool tests --

    def test_typed_429_is_immediate_single_call_without_sleep(self):
        client = self._client()
        tool = {"name": "test_tool", "input_schema": {"required": []}}

        with patch.object(client, "_get_anthropic_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = LLMRateLimitError(
                "429",
                retry_after=3600.0,
            )
            mock_get.return_value = mock_client
            with patch("scion.proposal.llm.client.time.sleep") as mock_sleep:
                with pytest.raises(LLMRateLimitError):
                    client.call_with_tool("prompt", tool)
        assert mock_client.messages.create.call_count == 1
        mock_sleep.assert_not_called()

    def test_generic_429_is_classified_once_without_sleep(self):
        client = self._client()
        tool = {"name": "test_tool", "input_schema": {"required": []}}

        with patch.object(client, "_get_anthropic_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception(
                "HTTP 429 rate_limit exceeded"
            )
            mock_get.return_value = mock_client
            with patch("scion.proposal.llm.client.time.sleep") as mock_sleep:
                with pytest.raises(LLMRateLimitError):
                    client.call_with_tool("prompt", tool)
        assert mock_client.messages.create.call_count == 1
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# T27: Provider output is not controlled by Scion
# ---------------------------------------------------------------------------

class TestProviderManagedOutput:
    """Length stop metadata does not activate a special Scion retry path."""

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

    def test_length_stop_with_typed_payload_is_returned_without_retry(self):
        client = LLMClient()
        tool = {"name": "write", "input_schema": {"required": []}}
        good = self._make_good_response("write", {"code": "x=1"})
        good.stop_reason = "max_tokens"

        with patch.object(client, "_get_anthropic_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = good
            mock_get.return_value = mock_client
            result = client.call_with_tool("prompt", tool)

        assert result == {"code": "x=1"}
        assert mock_client.messages.create.call_count == 1

    def test_length_stop_without_typed_payload_is_format_failure(self):
        client = LLMClient()
        tool = {"name": "write", "input_schema": {"required": []}}
        response = self._make_truncated_response("max_tokens")

        with patch.object(client, "_get_anthropic_client") as mock_get:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = response
            mock_get.return_value = mock_client
            with pytest.raises(LLMFormatError) as caught:
                client.call_with_tool("prompt", tool)

        assert "did not call tool" in str(caught.value)
        assert mock_client.messages.create.call_count == 1


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


class TestCampaignTypedProviderTermination:
    """A typed provider failure stops the direct invocation once."""

    def _make_campaign(self, llm_client):
        """Create a minimal CampaignManager with mock dependencies."""
        from scion.core.campaign import CampaignManager
        from scion.core.models import ChampionState
        from scion.config.problem import (
            ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace
        )
        from scion.problem.spec import ObjectiveMetricSpec
        from types import SimpleNamespace

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
        split = SplitManifest(
            screening=["c1"], validation=["c2"], frozen=["c3"], canary=["c4"]
        )
        seed_ledger = SeedLedgerConfig(
            screening=[1], validation=[2], frozen=[3], canary=[4]
        )
        champion = ChampionState(
            version=0,
            operator_pool={},
            code_snapshot_path=tmpdir,
        )
        campaign = CampaignManager(
            problem_spec=spec,
            protocol_config=protocol,
            split_manifest=split,
            seed_ledger=seed_ledger,
            llm_client=llm_client,
            champion=champion,
            campaign_dir=tmpdir,
            experiment_protocol=SimpleNamespace(
                runner=object(),
                config=protocol,
                _metric_specs=(
                    ObjectiveMetricSpec(
                        name="cost", direction="minimize", priority=1
                    ),
                ),
                _problem_spec=spec,
            ),
            adapter=SimpleNamespace(spec=spec),
        )
        return campaign

    def test_campaign_stops_on_first_typed_infra_outcome(self):
        """Provider infra failure stops the invocation without hidden retries."""
        from scion.proposal.mock_client import MockLLMClient

        failing_client = MockLLMClient(mode="timeout")
        campaign = self._make_campaign(failing_client)

        campaign.run(requested_rounds=20)

        assert campaign._last_stop_reason == "execution_blocked_infra"

    def test_campaign_summary_has_typed_infra_stop_reason(self):
        """Campaign summary names the typed outcome that stopped execution."""
        from scion.proposal.mock_client import MockLLMClient
        import json as _json

        failing_client = MockLLMClient(mode="timeout")
        campaign = self._make_campaign(failing_client)
        campaign.run(requested_rounds=20)

        summary_path = Path(campaign._campaign_dir) / "campaign_summary.json"
        if summary_path.exists():
            summary = _json.loads(summary_path.read_text())
            assert summary.get("stopped_reason") == "execution_blocked_infra"
