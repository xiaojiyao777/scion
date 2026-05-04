"""Lightweight campaign composition boundary tests."""
from __future__ import annotations

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
