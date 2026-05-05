"""Lightweight campaign composition boundary tests."""
from __future__ import annotations

from pathlib import Path

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
    manager = CampaignManager(
        problem_spec=spec,
        protocol_config=protocol,
        split_manifest=SplitManifest(),
        seed_ledger=SeedLedgerConfig(),
        llm_client=MockLLMClient(),
        champion=ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="x",
            code_snapshot_path=str(code_dir),
            code_snapshot_hash="y",
        ),
        campaign_dir=str(tmp_path / "campaign"),
    )

    for name in required_service_names():
        assert getattr(manager, name) is not None
    assert manager._ctx_manager._runtime_slow_threshold == protocol.runtime.max_runtime_ratio


def test_campaign_composition_persists_initial_champion(tmp_path):
    code_dir = tmp_path / "code"
    (code_dir / "operators").mkdir(parents=True)
    (code_dir / "registry.yaml").write_text("operators: []\n", encoding="utf-8")
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
    campaign_dir = tmp_path / "campaign"

    manager = CampaignManager(
        problem_spec=spec,
        protocol_config=ProtocolConfig(),
        split_manifest=SplitManifest(),
        seed_ledger=SeedLedgerConfig(),
        llm_client=MockLLMClient(),
        champion=ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="x",
            code_snapshot_path=str(code_dir),
            code_snapshot_hash="y",
        ),
        campaign_dir=str(campaign_dir),
    )

    current = manager._champion_store.get_current()
    assert current is not None
    assert current.version == 1
    assert Path(current.code_snapshot_path).exists()
    assert Path(current.code_snapshot_path).parent == campaign_dir / "champions"
    assert manager._champion.code_snapshot_path == current.code_snapshot_path


def test_initial_champion_persistence_accepts_legacy_weight_pool(tmp_path):
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

    manager = CampaignManager(
        problem_spec=spec,
        protocol_config=ProtocolConfig(),
        split_manifest=SplitManifest(),
        seed_ledger=SeedLedgerConfig(),
        llm_client=MockLLMClient(),
        champion=ChampionState(
            version=1,
            operator_pool={"local_search": 1.0},
            solver_config_hash="x",
            code_snapshot_path=str(code_dir),
            code_snapshot_hash="y",
        ),
        campaign_dir=str(tmp_path / "campaign"),
    )

    current = manager._champion_store.get_current()
    assert current is not None
    assert current.operator_pool["local_search"].weight == 1.0
