"""Lightweight campaign composition boundary tests."""
from __future__ import annotations

from types import SimpleNamespace

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
from scion.proposal.mock_client import MockLLMClient
from scion.problem.spec import ObjectiveMetricSpec
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager


def _v3_runtime(spec, split_manifest, seed_ledger, tmp_path):
    protocol = ExperimentProtocol(
        ProtocolConfig(),
        SplitManager(split_manifest),
        SeedLedger(seed_ledger),
        runner=object(),
        metrics_dir=str(tmp_path / "metrics"),
        metric_specs=(
            ObjectiveMetricSpec(name="cost", direction="minimize", priority=1),
        ),
        problem_spec=spec,
    )
    return protocol, SimpleNamespace(spec=spec)


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
        problem_spec=spec,
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
        problem_spec=spec,
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
