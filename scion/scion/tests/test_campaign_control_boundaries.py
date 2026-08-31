"""Lightweight campaign composition boundary tests."""

from __future__ import annotations

import json

import pytest

from scion.config.problem import (
    ProblemSpec,
    ProtocolConfig,
    SearchSpace,
    SeedLedgerConfig,
    SplitManifest,
)
from scion.core.campaign import CampaignManager
from scion.core.campaign_composition import required_service_names
from scion.core.models import ChampionState
from scion.core.resource_envelope import ResourceEnvelope
from scion.problem.spec import ObjectiveMetricSpec
from scion.proposal.mock_client import MockLLMClient
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.tests.protocol_adapter_test_support import protocol_test_adapter


def _v3_runtime(spec, split_manifest, seed_ledger, tmp_path):
    adapter = protocol_test_adapter(
        (
            ObjectiveMetricSpec(name="cost", direction="minimize", priority=1),
        ),
        problem_spec=spec,
    )
    protocol = ExperimentProtocol(
        ProtocolConfig(),
        SplitManager(split_manifest),
        SeedLedger(seed_ledger),
        runner=object(),
        metrics_dir=str(tmp_path / "metrics"),
        adapter=adapter,
    )
    return protocol, adapter


def _real_protocol_manager_kwargs(
    tmp_path,
    campaign_dir,
    *,
    research_input=None,
    resource_envelope=None,
):
    code_dir = tmp_path / "code"
    (code_dir / "operators").mkdir(parents=True, exist_ok=True)
    spec = ProblemSpec(
        name="composition_test",
        root_dir=str(code_dir),
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["math", "random"],
        ),
    )
    protocol_config = ProtocolConfig()
    split_manifest = SplitManifest(
        screening=["case-a"],
        validation=["case-b"],
        frozen=["case-c"],
        canary=["case-d"],
    )
    seed_ledger = SeedLedgerConfig(
        screening=[11],
        validation=[17],
        frozen=[23],
        canary=[29],
    )
    metrics_dir = campaign_dir / "metrics"
    adapter = protocol_test_adapter(
        (
            ObjectiveMetricSpec(name="cost", direction="minimize", priority=1),
        ),
        problem_spec=spec,
    )
    experiment_protocol = ExperimentProtocol(
        protocol_config,
        SplitManager(split_manifest),
        SeedLedger(seed_ledger),
        runner=object(),
        metrics_dir=str(metrics_dir),
        adapter=adapter,
    )
    llm_client = MockLLMClient()
    kwargs = {
        "protocol_config": protocol_config,
        "split_manifest": split_manifest,
        "seed_ledger": seed_ledger,
        "llm_client": llm_client,
        "champion": ChampionState(
            version=1,
            operator_pool={},
            code_snapshot_path=str(code_dir),
        ),
        "campaign_dir": str(campaign_dir),
        "experiment_protocol": experiment_protocol,
        "adapter": adapter,
        "research_input": research_input,
        "resource_envelope": resource_envelope,
    }
    return kwargs, llm_client, metrics_dir


def test_campaign_composition_installs_key_services(tmp_path):
    code_dir = tmp_path / "code"
    (code_dir / "operators").mkdir(parents=True)
    spec = ProblemSpec(
        name="composition_test",
        root_dir=str(code_dir),
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["math", "random"],
        ),
    )
    protocol = ProtocolConfig()
    split_manifest = SplitManifest(
        screening=["case-a"],
        validation=["case-b"],
        frozen=["case-c"],
        canary=["case-d"],
    )
    seed_ledger = SeedLedgerConfig(
        screening=[11],
        validation=[17],
        frozen=[23],
        canary=[29],
    )
    experiment_protocol, adapter = _v3_runtime(
        spec, split_manifest, seed_ledger, tmp_path
    )
    manager = CampaignManager(
        protocol_config=protocol,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        llm_client=MockLLMClient(),
        champion=ChampionState(
            version=1,
            operator_pool={},
            code_snapshot_path=str(code_dir),
        ),
        campaign_dir=str(tmp_path / "campaign"),
        experiment_protocol=experiment_protocol,
        adapter=adapter,
    )

    for name in required_service_names():
        assert getattr(manager, name) is not None


def test_fresh_campaign_accepts_real_protocol_metrics_inside_campaign(tmp_path):
    campaign_dir = tmp_path / "campaign"
    research_input = {
        "current_question": "Can the generic agent improve this object?",
        "observations": [],
    }
    resource_envelope = ResourceEnvelope(
        provider_call_cap=6,
        outer_hardwall_sec=4500,
    )
    kwargs, llm_client, metrics_dir = _real_protocol_manager_kwargs(
        tmp_path,
        campaign_dir,
        research_input=research_input,
        resource_envelope=resource_envelope,
    )

    assert not campaign_dir.exists()

    manager = CampaignManager(**kwargs)

    assert manager._campaign_dir == str(campaign_dir)
    assert metrics_dir.is_dir()
    assert (
        json.loads((campaign_dir / "research_input.json").read_text(encoding="utf-8"))
        == research_input
    )
    assert (
        json.loads(
            (campaign_dir / "resource_envelope.json").read_text(encoding="utf-8")
        )
        == resource_envelope.to_primitive()
    )
    assert llm_client.call_count == 0


def test_existing_empty_campaign_accepts_real_protocol_metrics_inside_campaign(
    tmp_path,
):
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    kwargs, llm_client, metrics_dir = _real_protocol_manager_kwargs(
        tmp_path,
        campaign_dir,
    )

    manager = CampaignManager(**kwargs)

    assert manager._campaign_dir == str(campaign_dir)
    assert metrics_dir.is_dir()
    assert llm_client.call_count == 0


def test_nonempty_campaign_rejection_preserves_sentinel_and_writes_no_inputs(
    tmp_path,
):
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    sentinel = campaign_dir / "sentinel.bin"
    sentinel_bytes = b"existing-campaign\x00sentinel\n"
    sentinel.write_bytes(sentinel_bytes)
    entries_before = tuple(entry.name for entry in campaign_dir.iterdir())
    kwargs, llm_client, _metrics_dir = _real_protocol_manager_kwargs(
        tmp_path,
        campaign_dir,
        research_input={
            "current_question": "This input must not be recorded.",
            "observations": [],
        },
        resource_envelope=ResourceEnvelope(
            provider_call_cap=6,
            outer_hardwall_sec=4500,
        ),
    )

    with pytest.raises(ValueError, match="campaign output must be fresh"):
        CampaignManager(**kwargs)

    assert tuple(entry.name for entry in campaign_dir.iterdir()) == entries_before
    assert sentinel.read_bytes() == sentinel_bytes
    assert not (campaign_dir / "metrics").exists()
    assert not (campaign_dir / "research_input.json").exists()
    assert not (campaign_dir / "resource_envelope.json").exists()
    assert llm_client.call_count == 0


def test_campaign_composition_passes_only_live_campaign_context_to_proposal_pipeline(
    tmp_path,
):
    code_dir = tmp_path / "code"
    (code_dir / "operators").mkdir(parents=True)
    spec = ProblemSpec(
        name="composition_test",
        root_dir=str(code_dir),
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["math", "random"],
        ),
    )
    split_manifest = SplitManifest(
        screening=["case-a"],
        validation=["case-b"],
        frozen=["case-c"],
        canary=["case-d"],
    )
    seed_ledger = SeedLedgerConfig(
        screening=[11],
        validation=[17],
        frozen=[23],
        canary=[29],
    )
    experiment_protocol, adapter = _v3_runtime(
        spec, split_manifest, seed_ledger, tmp_path
    )

    manager = CampaignManager(
        protocol_config=ProtocolConfig(),
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        llm_client=MockLLMClient(),
        champion=ChampionState(
            version=1,
            operator_pool={},
            code_snapshot_path=str(code_dir),
        ),
        campaign_dir=str(tmp_path / "campaign"),
        experiment_protocol=experiment_protocol,
        adapter=adapter,
    )

    pipeline = manager._proposal_pipeline
    assert not hasattr(pipeline, "problem_id")
    assert not hasattr(pipeline, "problem_spec_hash")
    assert not hasattr(pipeline, "split_manifest_hash")
    assert not hasattr(pipeline, "seed_ledger_hash")
